"""Auto-updater using GitHub releases.

Startup behaviour (Windows frozen exe only):
  check → download → replace-via-bat → restart, all silently.

Periodic behaviour (every 6 h, all platforms):
  check → tray notification + menu item → user clicks to download.
"""

import logging
import os
import platform
import subprocess
import sys
import tempfile
import webbrowser
from typing import Optional

import httpx
from packaging import version

from openoutreach.desktop.__version__ import __version__

logger = logging.getLogger(__name__)

GITHUB_RELEASES_URL = (
    "https://api.github.com/repos/Lengrowth/outbound/releases/latest"
)


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def can_auto_update() -> bool:
    """True only for the distributed Windows exe — the one case where we can safely
    replace the running binary by writing a detached .bat."""
    return sys.platform == "win32" and is_frozen()


def _get_platform_asset_name() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "Lengrowth-macOS.dmg"
    elif system == "windows":
        # Standalone exe — simpler to replace than the installer
        return "Lengrowth.exe"
    return ""


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

            # Tags are like "v1.2.13-a3f2b1c" — extract semver prefix
            latest_version = tag_name.lstrip("v").split("-")[0]

            if version.parse(latest_version) > version.parse(__version__):
                assets = release.get("assets", [])
                expected_name = _get_platform_asset_name()
                platform_url = None

                if expected_name:
                    for asset in assets:
                        if asset["name"] == expected_name:
                            platform_url = asset["browser_download_url"]
                            break

                download_url = platform_url or release["html_url"]

                return {
                    "version": latest_version,
                    "download_url": download_url,
                    "release_page": release["html_url"],
                    "notes": release.get("body", ""),
                    "tag_name": tag_name,
                }

            return None

    except Exception as e:
        logger.warning("Update check failed: %s", e)
        return None


async def download_update(url: str, version: str = "") -> Optional[str]:
    """Download the update exe to a temp file, showing a progress window.

    Returns the local path on success, None on failure.
    The progress window runs on a dedicated thread so it doesn't block the
    asyncio event loop.
    """
    dest = os.path.join(tempfile.gettempdir(), "Lengrowth_update.exe")
    label_text = version or "latest"

    # --- tkinter progress window (Windows only, safe to import here) ---
    win = None
    progress_var = None
    status_var = None
    try:
        import tkinter as tk
        from tkinter import ttk

        win = tk.Tk()
        win.title("Lengrowth Update")
        win.resizable(False, False)
        win.attributes("-topmost", True)

        w, h = 360, 130
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        win.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
        win.configure(bg="#09090b")

        tk.Label(
            win,
            text=f"Updating to Lengrowth v{label_text}…",
            bg="#09090b",
            fg="#f4f4f5",
            font=("Segoe UI", 11, "bold"),
        ).pack(pady=(18, 4))

        status_var = tk.StringVar(value="Downloading…")
        tk.Label(
            win,
            textvariable=status_var,
            bg="#09090b",
            fg="#a1a1aa",
            font=("Segoe UI", 9),
        ).pack()

        progress_var = tk.DoubleVar(value=0)
        bar = ttk.Progressbar(win, variable=progress_var, maximum=100, length=300)
        bar.pack(pady=(8, 0))

        # Run the tkinter event loop on its own thread
        import threading

        def _run_tk():
            win.mainloop()

        tk.Thread = threading.Thread  # type: ignore[attr-defined]  # unused alias
        _tk_thread = threading.Thread(target=_run_tk, daemon=True)
        _tk_thread.start()
    except Exception as e:
        logger.debug("Progress window unavailable: %s", e)
        win = None

    def _set_progress(pct: float, msg: str = "") -> None:
        if win is None:
            return
        try:
            if progress_var is not None:
                progress_var.set(pct)
            if status_var is not None and msg:
                status_var.set(msg)
            win.update_idletasks()
        except Exception:
            pass

    def _close_win() -> None:
        if win is None:
            return
        try:
            win.destroy()
        except Exception:
            pass

    try:
        async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                total = int(response.headers.get("content-length", 0))
                downloaded = 0
                with open(dest, "wb") as fh:
                    async for chunk in response.aiter_bytes(chunk_size=65536):
                        fh.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            pct = downloaded / total * 100
                            mb = downloaded / 1_048_576
                            total_mb = total / 1_048_576
                            _set_progress(pct, f"{mb:.1f} / {total_mb:.1f} MB")
                        else:
                            _set_progress(50, f"{downloaded / 1_048_576:.1f} MB…")

        _set_progress(100, "Installing…")
        logger.info("Update downloaded to %s", dest)
        _close_win()
        return dest
    except Exception as e:
        logger.error("Update download failed: %s", e)
        _close_win()
        return None


def apply_update_windows(new_exe_path: str) -> None:
    """Replace the current exe with new_exe_path and restart.

    Writes a detached .bat that waits for this process to exit, copies the new
    exe over the old one, then relaunches it.  Terminates this process via
    os._exit so all threads are killed immediately (sys.exit only raises in the
    calling thread).
    """
    current_exe = sys.executable
    bat_path = os.path.join(tempfile.gettempdir(), "lengrowth_update.bat")
    bat = (
        "@echo off\n"
        "timeout /t 3 /nobreak > nul\n"
        f'copy /Y "{new_exe_path}" "{current_exe}"\n'
        f'start "" "{current_exe}"\n'
        f'del "{new_exe_path}"\n'
        'del "%~f0"\n'
    )
    try:
        with open(bat_path, "w") as fh:
            fh.write(bat)
        subprocess.Popen(
            ["cmd", "/c", bat_path],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
            close_fds=True,
        )
        logger.info("Update bat launched — exiting for replacement")
    except Exception as e:
        logger.error("Failed to launch update bat: %s", e)
        return
    os._exit(0)


def prompt_update(update_info: dict) -> None:
    """Open browser to the platform download URL (fallback / macOS path)."""
    try:
        url = update_info.get("download_url", update_info.get("release_page"))
        if url:
            logger.info("Opening update URL: %s", url)
            webbrowser.open(url)
    except Exception as e:
        logger.error("Failed to open update URL: %s", e)
