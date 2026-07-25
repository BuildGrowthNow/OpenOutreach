"""Auto-updater using GitHub releases.

Startup behaviour (Windows frozen exe only):
  check → download (with progress dialog) → replace-via-PowerShell → restart, all silently.

Periodic behaviour (every 6 h, all platforms):
  check → tray notification + menu item → user clicks to download.
"""

import json
import logging
import os
import platform
import subprocess
import sys
import tempfile
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


def save_pending_update(info: dict, exe_path: str) -> None:
    """Persist downloaded update info to disk so the next startup can force-apply it."""
    try:
        _PENDING_UPDATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {**info, "exe_path": exe_path}
        _PENDING_UPDATE_FILE.write_text(json.dumps(payload), encoding="utf-8")
        logger.info("Pending update v%s saved to %s", info.get("version"), _PENDING_UPDATE_FILE)
    except Exception as e:
        logger.warning("Failed to save pending update: %s", e)


def load_pending_update() -> Optional[dict]:
    """Load persisted pending update. Returns None if not present or exe is missing."""
    try:
        if not _PENDING_UPDATE_FILE.exists():
            return None
        data = json.loads(_PENDING_UPDATE_FILE.read_text(encoding="utf-8"))
        exe_path = data.get("exe_path", "")
        if not exe_path or not Path(exe_path).exists():
            # Stale entry — the temp file was cleaned up
            clear_pending_update()
            return None
        return data
    except Exception as e:
        logger.warning("Failed to load pending update: %s", e)
        return None


def clear_pending_update() -> None:
    """Remove the persisted pending update record."""
    try:
        _PENDING_UPDATE_FILE.unlink(missing_ok=True)
    except Exception as e:
        logger.warning("Failed to clear pending update: %s", e)



def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def can_auto_update() -> bool:
    """True only for the distributed Windows exe — the one case where we can safely
    replace the running binary."""
    return sys.platform == "win32" and is_frozen()


def _get_platform_asset_name() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "Lengrowth-macOS.dmg"
    elif system == "windows":
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

            # Release tags are "v{version}-{short_sha}" e.g. "v1.3.4-abc1234"
            # Strip leading "v" then take everything before the first "-"
            if not tag_name.startswith("v"):
                logger.debug("Skipping unrecognised release tag: %s", tag_name)
                return None

            latest_version = tag_name.lstrip("v").split("-")[0]

            try:
                is_newer = version.parse(latest_version) > version.parse(__version__)
            except Exception:
                logger.debug("Could not parse version from tag %s", tag_name)
                return None

            if is_newer:
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


# ---------------------------------------------------------------------------
# Win32 progress dialog (no tkinter dependency)
# ---------------------------------------------------------------------------

class _ProgressWindow:
    """Minimal update-progress dialog using win32 APIs via ctypes.

    Creates a real Win32 window so it works inside a frozen exe without any
    Python UI framework.  Runs its own message loop on a background thread.
    """

    def __init__(self, label_text: str):
        self._label = label_text
        self._hwnd = None
        self._hwnd_label = None
        self._hwnd_bar = None
        self._hwnd_status = None
        self._thread = None
        self._pct = 0.0
        self._status = "Downloading…"
        self._alive = False

    def show(self) -> None:
        if sys.platform != "win32":
            return
        import threading
        self._alive = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            import ctypes
            import ctypes.wintypes as wt

            HINST = ctypes.windll.kernel32.GetModuleHandleW(None)
            WS_OVERLAPPED = 0x00000000
            WS_CAPTION = 0x00C00000
            WS_SYSMENU = 0x00080000
            WS_VISIBLE = 0x10000000
            WS_CHILD = 0x40000000
            WS_BORDER = 0x00800000
            PBS_SMOOTH = 0x01
            WM_CLOSE = 0x0010
            WM_DESTROY = 0x0002
            SS_CENTER = 0x01

            SW_SHOWNORMAL = 1

            # Forward declarations so the WndProc closure works
            hwnd_ref = [None]

            WNDPROCTYPE = ctypes.WINFUNCTYPE(ctypes.c_long, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)

            def wnd_proc(hwnd, msg, wp, lp):
                if msg in (WM_CLOSE, WM_DESTROY):
                    return 0
                return ctypes.windll.user32.DefWindowProcW(hwnd, msg, wp, lp)

            wnd_proc_cb = WNDPROCTYPE(wnd_proc)

            class WNDCLASSW(ctypes.Structure):
                _fields_ = [
                    ("style", wt.UINT), ("lpfnWndProc", WNDPROCTYPE),
                    ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                    ("hInstance", wt.HINSTANCE), ("hIcon", wt.HICON),
                    ("hCursor", wt.HANDLE), ("hbrBackground", wt.HBRUSH),
                    ("lpszMenuName", wt.LPCWSTR), ("lpszClassName", wt.LPCWSTR),
                ]

            wc = WNDCLASSW()
            wc.lpfnWndProc = wnd_proc_cb
            wc.hInstance = HINST
            wc.hbrBackground = ctypes.windll.gdi32.CreateSolidBrush(0x001B1B1B)  # dark bg
            wc.lpszClassName = "LengrowthUpdateDlg"
            ctypes.windll.user32.RegisterClassW(ctypes.byref(wc))

            W, H = 380, 140
            SM_CXSCREEN, SM_CYSCREEN = 0, 1
            sw = ctypes.windll.user32.GetSystemMetrics(SM_CXSCREEN)
            sh = ctypes.windll.user32.GetSystemMetrics(SM_CYSCREEN)
            x = (sw - W) // 2
            y = (sh - H) // 2

            WS_EX_TOPMOST = 0x00000008
            hwnd = ctypes.windll.user32.CreateWindowExW(
                WS_EX_TOPMOST,
                "LengrowthUpdateDlg",
                "Lengrowth Update",
                WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_VISIBLE,
                x, y, W, H,
                None, None, HINST, None,
            )
            hwnd_ref[0] = hwnd
            self._hwnd = hwnd

            # Title label
            self._hwnd_label = ctypes.windll.user32.CreateWindowExW(
                0, "STATIC", self._label,
                WS_CHILD | WS_VISIBLE | SS_CENTER,
                10, 14, W - 20, 24,
                hwnd, None, HINST, None,
            )

            # Status label
            self._hwnd_status = ctypes.windll.user32.CreateWindowExW(
                0, "STATIC", self._status,
                WS_CHILD | WS_VISIBLE | SS_CENTER,
                10, 42, W - 20, 20,
                hwnd, None, HINST, None,
            )

            # Progress bar  (requires comctl32 init)
            ctypes.windll.comctl32.InitCommonControls()
            PROGRESS_CLASS = "msctls_progress32"
            self._hwnd_bar = ctypes.windll.user32.CreateWindowExW(
                0, PROGRESS_CLASS, None,
                WS_CHILD | WS_VISIBLE | WS_BORDER | PBS_SMOOTH,
                20, 72, W - 40, 22,
                hwnd, None, HINST, None,
            )
            PBM_SETRANGE = 0x0401
            PBM_SETPOS = 0x0402
            ctypes.windll.user32.SendMessageW(self._hwnd_bar, PBM_SETRANGE, 0, (100 << 16) | 0)
            ctypes.windll.user32.SendMessageW(self._hwnd_bar, PBM_SETPOS, 0, 0)

            ctypes.windll.user32.ShowWindow(hwnd, SW_SHOWNORMAL)
            ctypes.windll.user32.UpdateWindow(hwnd)

            # Message loop
            class MSG(ctypes.Structure):
                _fields_ = [
                    ("hwnd", wt.HWND), ("message", wt.UINT),
                    ("wParam", wt.WPARAM), ("lParam", wt.LPARAM),
                    ("time", wt.DWORD), ("pt", wt.POINT),
                ]

            msg = MSG()
            PM_REMOVE = 0x0001
            WM_QUIT = 0x0012
            while self._alive:
                if ctypes.windll.user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                    if msg.message == WM_QUIT:
                        break
                    ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
                    ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
                else:
                    import time
                    time.sleep(0.02)

        except Exception as e:
            logger.debug("Progress window error: %s", e)

    def update(self, pct: float, status: str = "") -> None:
        self._pct = pct
        if status:
            self._status = status
        if sys.platform != "win32" or not self._hwnd:
            return
        try:
            import ctypes
            PBM_SETPOS = 0x0402
            ctypes.windll.user32.SendMessageW(self._hwnd_bar, PBM_SETPOS, int(pct), 0)
            if status and self._hwnd_status:
                ctypes.windll.user32.SetWindowTextW(self._hwnd_status, status)
            ctypes.windll.user32.UpdateWindow(self._hwnd)
        except Exception:
            pass

    def close(self) -> None:
        self._alive = False
        if sys.platform != "win32" or not self._hwnd:
            return
        try:
            import ctypes
            WM_CLOSE = 0x0010
            ctypes.windll.user32.PostMessageW(self._hwnd, WM_CLOSE, 0, 0)
        except Exception:
            pass
        self._hwnd = None


async def download_update(url: str, version: str = "", silent: bool = False) -> Optional[str]:
    """Download the update exe to a temp file.

    When ``silent=False`` (default for blocking startup path) shows a progress dialog.
    When ``silent=True`` (background download) runs quietly with no UI.

    Returns the local path on success, None on failure.
    """
    dest = os.path.join(tempfile.gettempdir(), "Lengrowth_update.exe")
    label_text = f"Updating to Lengrowth v{version}…" if version else "Downloading Lengrowth update…"

    win = _ProgressWindow(label_text) if not silent else None
    if win:
        win.show()

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
                        if win:
                            if total:
                                pct = downloaded / total * 100
                                mb = downloaded / 1_048_576
                                total_mb = total / 1_048_576
                                win.update(pct, f"{mb:.1f} / {total_mb:.1f} MB")
                            else:
                                win.update(50, f"{downloaded / 1_048_576:.1f} MB…")

        if win:
            win.update(100, "Installing…")
        logger.info("Update downloaded to %s", dest)
        if win:
            win.close()
        return dest
    except Exception as e:
        logger.error("Update download failed: %s", e)
        if win:
            win.close()
        return None


def apply_update_windows(new_exe_path: str) -> None:
    """Replace the current exe with new_exe_path and restart.

    Uses a hidden PowerShell script that waits for the current process to exit
    by PID, copies the new exe over, then relaunches it — no visible CMD window.
    """
    current_exe = sys.executable
    current_pid = os.getpid()
    ps_path = os.path.join(tempfile.gettempdir(), "lengrowth_update.ps1")

    # Wait for THIS process to exit (by PID), then replace and relaunch.
    # The -WindowStyle Hidden on the outer call keeps the PowerShell console invisible.
    ps_script = f"""
$pid_to_wait = {current_pid}
$target = '{current_exe.replace("'", "''")}'
$source = '{new_exe_path.replace("'", "''")}'

# Wait up to 15 s for the old process to exit
$deadline = (Get-Date).AddSeconds(15)
while ((Get-Process -Id $pid_to_wait -ErrorAction SilentlyContinue) -and (Get-Date) -lt $deadline) {{
    Start-Sleep -Milliseconds 200
}}

# Copy new exe over old one
Copy-Item -Path $source -Destination $target -Force

# Clean up temp file
Remove-Item -Path $source -Force -ErrorAction SilentlyContinue

# Relaunch
Start-Process -FilePath $target

# Remove this script
Remove-Item -Path '{ps_path.replace("'", "''")}' -Force -ErrorAction SilentlyContinue
"""

    try:
        with open(ps_path, "w", encoding="utf-8") as fh:
            fh.write(ps_script)

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
        logger.info("Update PowerShell script launched — exiting for replacement")
    except Exception as e:
        logger.error("Failed to launch update script: %s", e)
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
