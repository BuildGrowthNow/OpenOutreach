"""Desktop tray + webview application.

Opens linkedin.lengrowth.com in a native window (pywebview) on launch.
Tray icon controls the automation daemon and lets the user show/hide the window.
"""

import asyncio
import ctypes
import logging
import sys
import threading
from pathlib import Path
from typing import Optional

import pystray
import webview
from PIL import Image, ImageDraw
from pystray import MenuItem as Item

from openoutreach.core.daemon_remote import RemoteDaemon
from openoutreach.desktop.__version__ import __version__
from openoutreach.desktop.auth import AuthManager
from openoutreach.desktop.config import AppConfig
from openoutreach.desktop.protocol_handler import (
    handle_protocol_url,
    register_protocol_handler,
)
from openoutreach.desktop.updater import check_for_updates, prompt_update

logger = logging.getLogger(__name__)

_AUTOSTART_NAME = "LengrowthOutreach"
_MACOS_LAUNCHAGENT_LABEL = "io.lengrowth.linkedin"

_WINDOW_TITLE = "Lengrowth"
_WINDOW_W = 1280
_WINDOW_H = 820

# Injected into every page load:
# 1. Sets window.__LENGROWTH_DESKTOP__ so the frontend badge persists across navigation
# 2. Intercepts window.location.href = 'lengrowth://...' so the auth callback is
#    handled by Python instead of causing a failed navigation inside the webview
_INJECT_JS = """
(function() {
    window.__LENGROWTH_DESKTOP__ = true;

    var _origDesc = Object.getOwnPropertyDescriptor(Location.prototype, 'href');
    if (_origDesc && _origDesc.set) {
        Object.defineProperty(Location.prototype, 'href', {
            get: _origDesc.get,
            set: function(url) {
                if (typeof url === 'string' && url.indexOf('lengrowth://') === 0) {
                    var _poll = function(tries) {
                        if (window.pywebview && window.pywebview.api) {
                            window.pywebview.api.handle_lengrowth_url(url);
                        } else if (tries > 0) {
                            setTimeout(function() { _poll(tries - 1); }, 50);
                        }
                    };
                    _poll(20);
                    return;
                }
                _origDesc.set.call(this, url);
            },
            configurable: true,
            enumerable: true
        });
    }
})();
"""


# ---------------------------------------------------------------------------
# Auto-start helpers
# ---------------------------------------------------------------------------

def _register_autostart() -> None:
    if sys.platform == "win32":
        _autostart_windows(enable=True)
    elif sys.platform == "darwin":
        _autostart_macos(enable=True)


def _unregister_autostart() -> None:
    if sys.platform == "win32":
        _autostart_windows(enable=False)
    elif sys.platform == "darwin":
        _autostart_macos(enable=False)


def _autostart_windows(enable: bool) -> None:
    import winreg
    run_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key, 0, winreg.KEY_SET_VALUE) as key:
            if enable:
                winreg.SetValueEx(key, _AUTOSTART_NAME, 0, winreg.REG_SZ, f'"{sys.executable}"')
            else:
                try:
                    winreg.DeleteValue(key, _AUTOSTART_NAME)
                except FileNotFoundError:
                    pass
    except Exception as e:
        logger.warning("Auto-start (Windows) failed: %s", e)


def _autostart_macos(enable: bool) -> None:
    plist_path = (
        Path.home() / "Library" / "LaunchAgents" / f"{_MACOS_LAUNCHAGENT_LABEL}.plist"
    )
    if enable:
        plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>{_MACOS_LAUNCHAGENT_LABEL}</string>
    <key>ProgramArguments</key><array><string>{sys.executable}</string></array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><false/>
</dict>
</plist>"""
        try:
            plist_path.parent.mkdir(parents=True, exist_ok=True)
            plist_path.write_text(plist)
        except Exception as e:
            logger.warning("Auto-start (macOS) failed: %s", e)
    else:
        try:
            plist_path.unlink(missing_ok=True)
        except Exception as e:
            logger.warning("Auto-start removal (macOS) failed: %s", e)


# ---------------------------------------------------------------------------
# Single-instance lock
# ---------------------------------------------------------------------------

def _acquire_single_instance_lock():
    if sys.platform == "win32":
        handle = ctypes.windll.kernel32.CreateMutexW(None, True, "LengrowthOutreachSingleInstance")
        if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            return None
        return handle
    else:
        import fcntl
        lock_path = Path.home() / ".lengrowth" / "app.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(lock_path, "w")
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fh
        except OSError:
            fh.close()
            return None


# ---------------------------------------------------------------------------
# TrayApp
# ---------------------------------------------------------------------------

class DesktopAPI:
    """Python API exposed to the webview via window.pywebview.api.*"""

    def __init__(self, app: "TrayApp"):
        self._app = app

    def handle_lengrowth_url(self, url: str) -> None:
        """Called by JS when window.location.href is set to lengrowth://..."""
        logger.info("Protocol callback received: %s", url[:80])
        if handle_protocol_url(url, self._app.auth):
            self._app._update_menu()
            self._app._pending_login_notification = False
            if self._app.icon:
                self._app.icon.notify("Login successful", "Lengrowth is ready")
            if self._app.auth.is_logged_in():
                self._app._start_daemon()


class TrayApp:
    def __init__(self):
        self.config = AppConfig.load()
        self.auth = AuthManager(self.config)
        self.daemon: Optional[RemoteDaemon] = None
        self.daemon_thread: Optional[threading.Thread] = None
        self.icon: Optional[pystray.Icon] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stopping = False
        self._pending_update: Optional[dict] = None
        self._update_check_thread: Optional[threading.Thread] = None
        self._pending_login_notification = False
        self._window: Optional[webview.Window] = None

    # ------------------------------------------------------------------
    # Icon helpers
    # ------------------------------------------------------------------

    def _create_icon(self) -> Image.Image:
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent.parent.parent))
        icon_path = base / "openoutreach" / "desktop" / "assets" / "icon.png"
        if not icon_path.exists():
            icon_path = Path(__file__).parent / "assets" / "icon.png"
        if icon_path.exists():
            try:
                return Image.open(icon_path)
            except Exception as e:
                logger.warning("Failed to load icon: %s", e)
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        color = (34, 197, 94) if self._is_running() else (156, 163, 175)
        draw.ellipse([8, 8, 56, 56], fill=color)
        return img

    # ------------------------------------------------------------------
    # URL helpers
    # ------------------------------------------------------------------

    def _platform_url(self) -> str:
        url = self.config.api_url
        if "linkedin-api." in url:
            return url.replace("linkedin-api.", "linkedin.")
        return url

    def _app_url(self, path: str = "") -> str:
        base = self._platform_url().rstrip("/")
        suffix = f"/{path.lstrip('/')}" if path else ""
        return f"{base}{suffix}"

    # ------------------------------------------------------------------
    # Tray menu
    # ------------------------------------------------------------------

    def _create_menu(self) -> pystray.Menu:
        daemon_label = "Stop Automation" if self._is_running() else "Start Automation"
        status_label = f"Status: {'Running ●' if self._is_running() else 'Stopped ○'}"

        items = [
            Item(f"Lengrowth v{__version__}", None, enabled=False),
            Item(status_label, None, enabled=False),
            pystray.Menu.SEPARATOR,
            Item("Open Lengrowth", self._on_show_window),
            pystray.Menu.SEPARATOR,
            Item(daemon_label, self._on_toggle_daemon, enabled=self.auth.is_logged_in()),
        ]

        if self._pending_update:
            items.extend([
                pystray.Menu.SEPARATOR,
                Item(f"Update Available: v{self._pending_update['version']}", self._on_download_update),
            ])

        items.extend([
            pystray.Menu.SEPARATOR,
            Item("Quit", self._on_quit),
        ])

        return pystray.Menu(*items)

    def _update_menu(self):
        if self.icon:
            self.icon.menu = self._create_menu()
            self.icon.icon = self._create_icon()

    # ------------------------------------------------------------------
    # Window
    # ------------------------------------------------------------------

    def _start_window(self):
        """Create and show the pywebview window. Blocks until the window closes."""
        url = self._app_url() if self.auth.is_logged_in() else self._app_url("login")
        logger.info("Opening window: %s", url)

        api = DesktopAPI(self)

        self._window = webview.create_window(
            title=_WINDOW_TITLE,
            url=url,
            width=_WINDOW_W,
            height=_WINDOW_H,
            min_size=(800, 600),
            resizable=True,
            on_top=False,
            background_color="#09090b",  # zinc-950 matches the dark theme
            js_api=api,
        )
        self._window.events.closed += self._on_window_closed
        self._window.events.loaded += self._on_loaded

        # pywebview.start() is blocking — run in current thread
        webview.start(debug=False)

    def _on_loaded(self):
        """Called after each page navigation — re-inject the desktop globals."""
        if self._window:
            try:
                self._window.evaluate_js(_INJECT_JS)
            except Exception as e:
                logger.debug("JS inject failed: %s", e)

    def _on_window_closed(self):
        """Called when the user closes the window — hide it, don't quit."""
        self._window = None
        logger.info("Window closed")

    def _on_show_window(self):
        """Show or restore the main window."""
        if self._window is not None:
            try:
                self._window.show()
                return
            except Exception:
                pass

        # Window was closed — open a new one in a thread so the tray keeps running
        threading.Thread(target=self._start_window, daemon=True).start()

    # ------------------------------------------------------------------
    # Tray callbacks
    # ------------------------------------------------------------------

    def _on_quit(self):
        self._stopping = True
        self._stop_daemon()
        if self._window:
            try:
                self._window.destroy()
            except Exception:
                pass
        if self.icon:
            self.icon.stop()

    def _on_toggle_daemon(self):
        if self._is_running():
            self._stop_daemon()
        else:
            self._start_daemon()
        self._update_menu()

    def _on_download_update(self):
        if self._pending_update:
            prompt_update(self._pending_update)

    # ------------------------------------------------------------------
    # Tray setup
    # ------------------------------------------------------------------

    def _on_setup(self, icon):
        icon.visible = True

        if self._pending_login_notification:
            self._pending_login_notification = False
            icon.notify("Login successful", "Lengrowth is ready")

        if self.auth.is_logged_in():
            self._start_daemon()

        _register_autostart()
        self._start_update_checker()

    # ------------------------------------------------------------------
    # Daemon
    # ------------------------------------------------------------------

    def _is_running(self) -> bool:
        return (
            self.daemon is not None
            and self.daemon.running
            and self.daemon_thread is not None
            and self.daemon_thread.is_alive()
        )

    def _start_daemon(self):
        if self._is_running():
            return
        if not self.auth.is_logged_in():
            return

        token = self.auth.get_token()
        refresh_token = self.auth.get_refresh_token()
        profile_id = self.auth.get_profile_id()

        if not token:
            return

        if not profile_id:
            profile_id = self._resolve_profile_id(token)
            if profile_id:
                self.auth.login(token, profile_id, refresh_token=refresh_token)
            else:
                logger.error("No LinkedIn profile found")
                if self.icon:
                    self.icon.notify("No LinkedIn Profile", "Add a LinkedIn profile in the dashboard first.")
                return

        def on_token_refresh(new_token: str):
            self.auth.update_token(new_token)

        def run_daemon():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self.daemon = RemoteDaemon(
                api_url=self.config.api_url,
                token=token,
                linkedin_profile_id=profile_id,
                refresh_token=refresh_token,
                on_token_refresh=on_token_refresh,
            )
            try:
                self._loop.run_until_complete(self.daemon.start())
            except KeyboardInterrupt:
                pass
            except Exception as e:
                from openoutreach.core.daemon_remote import BrowserNotFoundError
                logger.exception("Daemon error: %s", e)
                msg = "No supported browser found." if isinstance(e, BrowserNotFoundError) else "Daemon error — check logs."
                if self.icon:
                    self.icon.notify("Daemon Error", msg)
            finally:
                self._loop.close()
                self._loop = None

        self.daemon_thread = threading.Thread(target=run_daemon, daemon=True)
        self.daemon_thread.start()
        self._update_menu()

    def _resolve_profile_id(self, token: str) -> Optional[str]:
        import json
        import urllib.request
        req = urllib.request.Request(
            f"{self.config.api_url.rstrip('/')}/api/linkedin-profiles/",
            headers={"Authorization": f"Bearer {token}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                profiles = data if isinstance(data, list) else data.get("profiles", [])
                if profiles:
                    pid = profiles[0].get("id") or profiles[0].get("_id")
                    return str(pid) if pid else None
        except Exception as e:
            logger.error("Failed to resolve profile_id: %s", e)
        return None

    def _stop_daemon(self):
        if not self._is_running():
            return
        if self._loop and self.daemon:
            try:
                asyncio.run_coroutine_threadsafe(self.daemon.stop(), self._loop).result(timeout=10)
            except Exception as e:
                logger.warning("Error stopping daemon: %s", e)
        if self.daemon_thread and self.daemon_thread.is_alive():
            self.daemon_thread.join(timeout=5)
        self.daemon = None
        self.daemon_thread = None
        self._update_menu()

    # ------------------------------------------------------------------
    # Update checker
    # ------------------------------------------------------------------

    def _start_update_checker(self):
        if self._update_check_thread and self._update_check_thread.is_alive():
            return

        async def loop():
            await asyncio.sleep(10)
            while not self._stopping:
                try:
                    info = await check_for_updates()
                    if info and not self._pending_update:
                        self._pending_update = info
                        self._update_menu()
                        if self.icon:
                            self.icon.notify(f"Update Available: v{info['version']}", "Click the tray icon to download")
                except Exception as e:
                    logger.warning("Update check failed: %s", e)
                await asyncio.sleep(3600 * 6)

        def run():
            lp = asyncio.new_event_loop()
            asyncio.set_event_loop(lp)
            try:
                lp.run_until_complete(loop())
            finally:
                lp.close()

        self._update_check_thread = threading.Thread(target=run, daemon=True)
        self._update_check_thread.start()

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self, pending_protocol_url: Optional[str] = None):
        # Handle protocol callback that arrived before the window existed
        if pending_protocol_url:
            if handle_protocol_url(pending_protocol_url, self.auth):
                self._pending_login_notification = True

        # Start tray icon in background thread (pystray owns its own loop)
        tray_icon = pystray.Icon(
            "Lengrowth",
            self._create_icon(),
            "Lengrowth",
            menu=self._create_menu(),
        )
        self.icon = tray_icon
        tray_thread = threading.Thread(
            target=lambda: tray_icon.run(setup=self._on_setup),
            daemon=True,
        )
        tray_thread.start()

        # Open the main window — this blocks until the app quits
        self._start_window()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    logger.info("Starting Lengrowth desktop app v%s", __version__)

    _lock = _acquire_single_instance_lock()
    if _lock is None:
        logger.info("Another instance is already running. Exiting.")
        sys.exit(0)

    register_protocol_handler()

    pending_protocol_url = None
    if len(sys.argv) > 1 and sys.argv[1].startswith("lengrowth://"):
        pending_protocol_url = sys.argv[1]

    app = TrayApp()
    try:
        app.run(pending_protocol_url=pending_protocol_url)
    except KeyboardInterrupt:
        logger.info("Interrupted")
        sys.exit(0)
    except Exception as e:
        logger.exception("Fatal error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
