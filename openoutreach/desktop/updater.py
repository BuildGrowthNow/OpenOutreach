"""Auto-updater using GitHub releases.

Startup behaviour (Windows frozen exe only):
  check → download (with progress dialog) → replace-via-PowerShell → restart, all silently.

Periodic behaviour (every 6 h, all platforms):
  check → tray notification + menu item → user clicks to download.
"""

import json
import hashlib
import logging
import os
import platform
import re
import subprocess
import sys
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Optional

import httpx
from packaging import version

from openoutreach.desktop.__version__ import __version__

logger = logging.getLogger(__name__)

GITHUB_RELEASES_URL = (
    "https://api.github.com/repos/Lengrowth/outbound/releases/latest"
)


_PENDING_UPDATE_FILE = Path.home() / ".lengrowth" / "pending_update.json"


def _normalized_sha256(value: str | None) -> str | None:
    """Return a canonical SHA-256 digest or None for untrusted metadata."""
    if not value:
        return None
    digest = value.removeprefix("sha256:").lower()
    return digest if re.fullmatch(r"[0-9a-f]{64}", digest) else None


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_pending_update(info: dict, exe_path: str) -> None:
    """Persist downloaded update info to disk so the next startup can force-apply it."""
    try:
        _PENDING_UPDATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {**info, "exe_path": exe_path}
        _PENDING_UPDATE_FILE.write_text(json.dumps(payload), encoding="utf-8")
        logger.info("Pending update v%s saved to %s", info.get("version"), _PENDING_UPDATE_FILE)
    except Exception as e:
        logger.warning("Failed to save pending update: %s", type(e).__name__)


def load_pending_update() -> Optional[dict]:
    """Load persisted pending update. Returns None if not present or exe is missing."""
    try:
        if not _PENDING_UPDATE_FILE.exists():
            return None
        data = json.loads(_PENDING_UPDATE_FILE.read_text(encoding="utf-8"))
        exe_path = data.get("exe_path", "")
        path = Path(exe_path)
        expected = _normalized_sha256(data.get("digest"))
        if not exe_path or not path.exists() or not expected:
            # Stale entry - the temp file was cleaned up
            clear_pending_update()
            return None
        if _file_sha256(path) != expected:
            logger.warning("Discarding pending update with a digest mismatch")
            clear_pending_update()
            return None
        return data
    except Exception as e:
        logger.warning("Failed to load pending update: %s", type(e).__name__)
        return None


def clear_pending_update() -> None:
    """Remove the persisted pending update record."""
    try:
        _PENDING_UPDATE_FILE.unlink(missing_ok=True)
    except Exception as e:
        logger.warning("Failed to clear pending update: %s", type(e).__name__)



def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def can_auto_update() -> bool:
    """True only for the distributed Windows exe - the one case where we can safely
    replace the running binary."""
    return sys.platform == "win32" and is_frozen()


def _get_platform_asset_name(release_version: str = "") -> str:
    system = platform.system().lower()
    if system == "darwin":
        return f"Lengrowth-{release_version}.dmg" if release_version else "Lengrowth-macOS.dmg"
    elif system == "windows":
        return f"Lengrowth-{release_version}-Setup.exe" if release_version else "Lengrowth.exe"
    return ""


def _get_platform_asset_names(release_version: str = "") -> tuple[str, ...]:
    """Return accepted release asset names, newest branding first.

    The packaging scripts produce ``Lengrowth-*`` files, while older releases
    used ``OpenOutreach-*``.  Accepting both keeps upgrades working across the
    rename and avoids silently falling back to the release page.
    """
    system = platform.system().lower()
    if system == "darwin":
        if not release_version:
            return ("Lengrowth-macOS.dmg", "OpenOutreach-macOS.dmg")
        return (f"Lengrowth-{release_version}.dmg", f"OpenOutreach-{release_version}.dmg")
    if system == "windows":
        # The updater replaces the running standalone executable.  Installer
        # packages must never be selected here: copying an installer over the
        # running exe produces an unusable installation.
        if not release_version:
            return ("Lengrowth.exe", "OpenOutreach.exe")
        return (
            "Lengrowth.exe",
            "OpenOutreach.exe",
            f"Lengrowth-{release_version}.exe",
            f"OpenOutreach-{release_version}.exe",
        )
    return ()


async def _manifest_digest(client: httpx.AsyncClient, assets: list, asset_name: str) -> str | None:
    """Read a release's SHA256SUMS.txt when GitHub has no asset digest.

    GitHub's API digest field is not consistently populated for assets uploaded
    by release actions, while our publishing workflow already uploads this
    checksum manifest.  Keeping the fail-closed behavior and using the
    manifest makes older and newly published releases work alike.
    """
    manifest = next((asset for asset in assets if asset.get("name") == "SHA256SUMS.txt"), None)
    if not manifest:
        return None
    try:
        response = await client.get(manifest["browser_download_url"])
        response.raise_for_status()
        for line in response.text.splitlines():
            fields = line.split()
            if len(fields) >= 2 and Path(fields[-1]).name == asset_name:
                return _normalized_sha256(fields[0])
    except Exception as e:
        logger.warning("Failed to read release checksum manifest: %s", type(e).__name__)
    return None


async def check_for_updates() -> Optional[dict]:
    """Check GitHub for a newer version.

    Returns a dict with at minimum ``version`` and ``download_url`` if an
    update is available, or None.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(GITHUB_RELEASES_URL)
            if response.status_code != 200:
                logger.warning("Failed to check for updates: %s", response.status_code)
                return None

            release = response.json()
            tag_name = release["tag_name"]

            # Release tags are "v{version}-{short_sha}" e.g. "v1.3.4-abc1234"
            # Strip leading "v" then take everything before the first "-"
            if not (tag_name.startswith("v") or tag_name.startswith("desktop-v")):
                logger.debug("Skipping unrecognised release tag: %s", tag_name)
                return None

            latest_version = tag_name.removeprefix("desktop-").lstrip("v").split("-")[0]

            try:
                is_newer = version.parse(latest_version) > version.parse(__version__)
            except Exception:
                logger.debug("Could not parse version from tag %s", tag_name)
                return None

            if is_newer:
                assets = release.get("assets", [])
                platform_url = None
                platform_digest = None

                expected_names = _get_platform_asset_names(latest_version)
                if expected_names:
                    for asset in assets:
                        if asset.get("name") in expected_names:
                            platform_url = asset["browser_download_url"]
                            platform_digest = asset.get("digest")
                            if not platform_digest:
                                platform_digest = await _manifest_digest(
                                    client, assets, asset["name"]
                                )
                            break
                download_url = platform_url or release["html_url"]

                return {
                    "version": latest_version,
                    "download_url": download_url,
                    "release_page": release["html_url"],
                    "notes": release.get("body", ""),
                    "tag_name": tag_name,
                    "digest": platform_digest,
                }

            return None

    except Exception as e:
        logger.warning("Update check failed: %s", type(e).__name__)
        return None


async def download_update(
    url: str, version: str = "", expected_digest: str | None = None
) -> Optional[str]:
    """Download the update exe silently to a per-user location.

    Stored under ~/.lengrowth/ (same dir as pending_update.json) so it
    persists across sessions and is isolated per user on multi-user Windows.
    Any existing partial/stale download is removed before starting.

    Returns the local path on success, None on failure.
    """
    dest_dir = _PENDING_UPDATE_FILE.parent
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = str(dest_dir / "Lengrowth_update.exe")
    partial = f"{dest}.part"

    if not expected_digest:
        logger.error("Refusing update download without a SHA-256 digest")
        return None
    expected = _normalized_sha256(expected_digest)
    if not expected:
        logger.error("Refusing update download with an invalid SHA-256 digest")
        return None

    # Remove any stale partial download before starting
    try:
        if os.path.exists(dest):
            os.remove(dest)
        if os.path.exists(partial):
            os.remove(partial)
    except Exception:
        pass

    try:
        async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                downloaded = 0
                with open(partial, "wb") as fh:
                    async for chunk in response.aiter_bytes(chunk_size=65536):
                        fh.write(chunk)
                        downloaded += len(chunk)
        if _file_sha256(Path(partial)) != expected:
            raise ValueError("downloaded update digest does not match GitHub asset digest")
        os.replace(partial, dest)
        ver_tag = f"v{version} " if version else ""
        logger.info("Update %sdownloaded to %s (%d bytes)", ver_tag, dest, downloaded)
        return dest
    except Exception as e:
        logger.error("Update download failed: %s", type(e).__name__)
        # Remove incomplete file so load_pending_update won't find a corrupt exe
        try:
            if os.path.exists(dest):
                os.remove(dest)
            if os.path.exists(partial):
                os.remove(partial)
        except Exception:
            pass
        return None


def apply_update_windows(new_exe_path: str, download_url: str = "") -> None:
    """Replace the current exe with new_exe_path and restart.

    Uses a hidden PowerShell script that waits for the current process to exit
    by PID, copies the new exe over, then relaunches it - no visible CMD window.
    On copy failure opens the download page in the browser as a fallback.
    """
    current_exe = sys.executable
    current_pid = os.getpid()
    # Use the per-user ~/.lengrowth dir so multiple Windows users don't clobber
    # each other's update scripts.  tempfile.gettempdir() is shared on RDS/TS.
    _update_dir = _PENDING_UPDATE_FILE.parent
    _update_dir.mkdir(parents=True, exist_ok=True)
    ps_path = str(_update_dir / "lengrowth_update.ps1")
    log_path = str(_update_dir / "lengrowth_update.log")

    fallback_url = download_url or "https://github.com/Lengrowth/outbound/releases/latest"

    pending_json = str(_PENDING_UPDATE_FILE).replace("'", "''")

    ps_script = f"""
$pid_to_wait = {current_pid}
$target = '{current_exe.replace("'", "''")}'
$backup = "$target.previous"
$source = '{new_exe_path.replace("'", "''")}'
$log = '{log_path.replace("'", "''")}'
$fallback_url = '{fallback_url.replace("'", "''")}'
$pending_json = '{pending_json}'

function Write-Log($msg) {{
    $ts = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    Add-Content -Path $log -Value "$ts $msg" -Encoding UTF8
}}

Write-Log "Update script started. source=$source target=$target pid=$pid_to_wait"

# Wait up to 30 s for the old process to exit
$deadline = (Get-Date).AddSeconds(30)
while ((Get-Process -Id $pid_to_wait -ErrorAction SilentlyContinue) -and (Get-Date) -lt $deadline) {{
    Start-Sleep -Milliseconds 500
}}

if (Get-Process -Id $pid_to_wait -ErrorAction SilentlyContinue) {{
    Write-Log "ERROR: old process still running after 30s - aborting"
    Start-Process $fallback_url
    exit 1
}}

Write-Log "Old process exited. Attempting copy..."

# Extra pause so Windows releases file handle
Start-Sleep -Milliseconds 1000

try {{
    if (Test-Path $target) {{
        Copy-Item -Path $target -Destination $backup -Force -ErrorAction Stop
        Write-Log "Previous executable backed up to $backup"
    }}
    Copy-Item -Path $source -Destination $target -Force -ErrorAction Stop
    Write-Log "Copy succeeded."
}} catch {{
    Write-Log "ERROR: Copy-Item failed: $_"
    if (Test-Path $backup) {{
        Copy-Item -Path $backup -Destination $target -Force -ErrorAction SilentlyContinue
        Write-Log "Previous executable restored from backup."
    }}
    # Open download page so user can update manually
    Start-Process $fallback_url
    exit 1
}}

# Clean up temp exe and pending marker - prevents reapply loop on next launch
Remove-Item -Path $source -Force -ErrorAction SilentlyContinue
Remove-Item -Path $pending_json -Force -ErrorAction SilentlyContinue

Write-Log "Relaunching $target"
Start-Process -FilePath $target

# Remove this script
Remove-Item -Path '{ps_path.replace("'", "''")}' -Force -ErrorAction SilentlyContinue
"""

    try:
        with open(ps_path, "w", encoding="utf-8") as fh:
            fh.write(ps_script)
        # Clear any stale log from a previous attempt
        try:
            if os.path.exists(log_path):
                os.remove(log_path)
        except Exception:
            pass

        subprocess.Popen(
            [
                "powershell.exe",
                "-NonInteractive",
                "-NoProfile",
                "-WindowStyle", "Hidden",
                "-ExecutionPolicy", "Bypass",
                "-File", ps_path,
            ],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
            close_fds=True,
        )
        logger.info("Update PowerShell script launched - exiting for replacement")
    except Exception as e:
        logger.error("Failed to launch update script: %s", type(e).__name__)
        return

    os._exit(0)


def prompt_update(update_info: dict) -> None:
    """Open browser to the platform download URL (fallback / macOS path)."""
    try:
        url = update_info.get("download_url", update_info.get("release_page"))
        if url:
            parsed = urllib.parse.urlsplit(str(url))
            safe_url = urllib.parse.urlunsplit(
                (parsed.scheme, parsed.netloc, parsed.path, "", "")
            )
            logger.info("Opening update URL: %s", safe_url)
            webbrowser.open(url)
    except Exception as e:
        logger.error("Failed to open update URL: %s", type(e).__name__)
