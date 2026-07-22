"""Desktop tray application.

Provides:
- System tray icon with status
- Start/Stop daemon control
- Open web dashboard
- Login flow
"""

import asyncio
import logging
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Optional

import pystray
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


def _register_autostart() -> None:
    """Register the app to start on login (Windows registry / macOS LaunchAgent)."""
    if sys.platform == "win32":
        _autostart_windows(enable=True)
    elif sys.platform == "darwin":
        _autostart_macos(enable=True)


def _unregister_autostart() -> None:
    """Remove the auto-start entry."""
    if sys.platform == "win32":
        _autostart_windows(enable=False)
    elif sys.platform == "darwin":
        _autostart_macos(enable=False)


def _autostart_windows(enable: bool) -> None:
    import winreg

    run_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, run_key, 0, winreg.KEY_SET_VALUE
        ) as key:
            if enable:
                exe = sys.executable
                winreg.SetValueEx(key, _AUTOSTART_NAME, 0, winreg.REG_SZ, f'"{exe}"')
                logger.info("Auto-start registered")
            else:
                try:
                    winreg.DeleteValue(key, _AUTOSTART_NAME)
                    logger.info("Auto-start removed")
                except FileNotFoundError:
                    pass
    except Exception as e:
        logger.warning("Auto-start (Windows) failed: %s", e)


def _autostart_macos(enable: bool) -> None:
    plist_path = (
        Path.home()
        / "Library"
        / "LaunchAgents"
        / f"{_MACOS_LAUNCHAGENT_LABEL}.plist"
    )
    if enable:
        exe = sys.executable
        plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{_MACOS_LAUNCHAGENT_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{exe}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
"""
        try:
            plist_path.parent.mkdir(parents=True, exist_ok=True)
            plist_path.write_text(plist)
            logger.info("Auto-start LaunchAgent written")
        except Exception as e:
            logger.warning("Auto-start (macOS) failed: %s", e)
    else:
        try:
            plist_path.unlink(missing_ok=True)
            logger.info("Auto-start LaunchAgent removed")
        except Exception as e:
            logger.warning("Auto-start removal (macOS) failed: %s", e)


class TrayApp:
    """System tray application."""

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

    def run(self):
        """Run the tray application."""
        icon = pystray.Icon(
            "Lengrowth Outreach",
            self._create_icon(),
            "Lengrowth Outreach",
            menu=self._create_menu(),
        )
        self.icon = icon
        icon.run(setup=self._on_setup)

    def _create_icon(self) -> Image.Image:
        """Create tray icon."""
        # sys._MEIPASS is set by PyInstaller; fall back to source tree for dev
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

    def _create_menu(self) -> pystray.Menu:
        """Create tray menu based on auth state."""
        if not self.auth.is_logged_in():
            items = [
                Item(f"Lengrowth Outreach v{__version__}", None, enabled=False),
                pystray.Menu.SEPARATOR,
                Item("Login to Lengrowth", self._on_login),
            ]

            if self._pending_update:
                items.extend([
                    pystray.Menu.SEPARATOR,
                    Item(
                        f"Update Available: v{self._pending_update['version']}",
                        self._on_download_update,
                    ),
                ])

            items.append(Item("Quit", self._on_quit))
            return pystray.Menu(*items)

        daemon_running = "Running" if self._is_running() else "Stopped"

        items = [
            Item(f"Lengrowth Outreach v{__version__}", None, enabled=False),
            Item(f"Status: {daemon_running}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            Item(
                "Stop Automation" if self._is_running() else "Start Automation",
                self._on_toggle_daemon,
            ),
            Item("Open Dashboard", self._on_open_dashboard),
            Item("Manage Subscription", self._on_manage_subscription),
        ]

        if self._pending_update:
            items.extend([
                pystray.Menu.SEPARATOR,
                Item(
                    f"Update Available: v{self._pending_update['version']}",
                    self._on_download_update,
                ),
            ])

        items.extend([
            pystray.Menu.SEPARATOR,
            Item("Logout", self._on_logout),
            Item("Quit", self._on_quit),
        ])

        return pystray.Menu(*items)

    def _update_menu(self):
        """Update the tray menu and icon."""
        if self.icon:
            self.icon.menu = self._create_menu()
            self.icon.icon = self._create_icon()

    def _is_running(self) -> bool:
        """Check if daemon is running."""
        return (
            self.daemon is not None
            and self.daemon.running
            and self.daemon_thread is not None
            and self.daemon_thread.is_alive()
        )

    def _get_platform_url(self) -> str:
        """Resolve the Next.js platform URL from the configured API URL."""
        import urllib.parse
        parsed = urllib.parse.urlparse(self.config.api_url)
        if "linkedin-api." in parsed.netloc:
            return self.config.api_url.replace("linkedin-api.", "linkedin.")
        return self.config.api_url

    def _on_setup(self, icon):
        """Called when tray icon is ready."""
        icon.visible = True

        # Fire deferred login notification (protocol callback arrived before icon existed)
        if self._pending_login_notification:
            self._pending_login_notification = False
            icon.notify("Login successful", "You can now start automation")

        # Auto-start daemon if logged in
        if self.auth.is_logged_in():
            self._start_daemon()

        # Register auto-start on first-ever launch (idempotent)
        _register_autostart()

        # Start periodic update checks
        self._start_update_checker()

    def _on_login(self):
        """Open login page in browser."""
        login_url = f"{self._get_platform_url()}/login?desktop=true&callback=lengrowth://auth"
        webbrowser.open(login_url)

    def _on_logout(self):
        """Log out and stop daemon."""
        self._stop_daemon()
        self.auth.logout()
        _unregister_autostart()
        self._update_menu()

    def _on_toggle_daemon(self):
        """Toggle daemon on/off."""
        if self._is_running():
            self._stop_daemon()
        else:
            self._start_daemon()
        self._update_menu()

    def _on_open_dashboard(self):
        """Open web dashboard."""
        webbrowser.open(self._get_platform_url())

    def _on_manage_subscription(self):
        """Open subscription management page."""
        webbrowser.open(f"{self._get_platform_url()}/settings/billing")

    def _on_quit(self):
        """Quit the application."""
        self._stopping = True
        self._stop_daemon()
        if self.icon:
            self.icon.stop()

    def _on_download_update(self):
        """Open browser to download the latest update."""
        if self._pending_update:
            prompt_update(self._pending_update)

    def _start_daemon(self):
        """Start the daemon in a background thread."""
        if self._is_running():
            logger.warning("Daemon already running")
            return

        if not self.auth.is_logged_in():
            logger.error("Not logged in")
            return

        token = self.auth.get_token()
        refresh_token = self.auth.get_refresh_token()
        profile_id = self.auth.get_profile_id()

        if not token:
            logger.error("Missing access token")
            return

        # profile_id may be empty when the web callback didn't include it;
        # resolve it from the API and persist for next time
        if not profile_id:
            profile_id = self._resolve_profile_id(token)
            if profile_id:
                self.auth.login(token, profile_id, refresh_token=refresh_token)
            else:
                logger.error("No LinkedIn profile found for this account")
                if self.icon:
                    self.icon.notify(
                        "No LinkedIn Profile",
                        "Add a LinkedIn profile in the dashboard before starting automation.",
                    )
                return

        def on_token_refresh(new_token: str):
            logger.info("Access token refreshed, updating keychain")
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
                logger.info("Daemon interrupted")
            except Exception as e:
                from openoutreach.core.daemon_remote import BrowserNotFoundError

                logger.exception("Daemon error: %s", e)
                if isinstance(e, BrowserNotFoundError):
                    error_msg = "No supported browser found. Please install Chrome or Edge."
                else:
                    error_msg = "Lengrowth daemon encountered an error. Check logs for details."

                if self.icon:
                    self.icon.notify("Daemon Error", error_msg)
            finally:
                self._loop.close()
                self._loop = None

        self.daemon_thread = threading.Thread(target=run_daemon, daemon=True)
        self.daemon_thread.start()

        logger.info("Daemon started")
        self._update_menu()

    def _resolve_profile_id(self, token: str) -> Optional[str]:
        """Fetch the first active LinkedIn profile ID from the backend."""
        import json
        import urllib.request

        api_url = self.config.api_url.rstrip("/")
        req = urllib.request.Request(
            f"{api_url}/api/linkedin-profiles/",
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
        """Stop the daemon."""
        if not self._is_running():
            return

        if self._loop and self.daemon:
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self.daemon.stop(),
                    self._loop,
                )
                future.result(timeout=10)
            except Exception as e:
                logger.warning("Error stopping daemon: %s", e)

        if self.daemon_thread and self.daemon_thread.is_alive():
            self.daemon_thread.join(timeout=5)

        self.daemon = None
        self.daemon_thread = None

        logger.info("Daemon stopped")
        self._update_menu()

    def _start_update_checker(self):
        """Start background update checker (no-op if already running)."""
        if (
            self._update_check_thread is not None
            and self._update_check_thread.is_alive()
        ):
            return

        async def update_checker_loop():
            await asyncio.sleep(10)

            while not self._stopping:
                try:
                    update_info = await check_for_updates()

                    if update_info and not self._pending_update:
                        logger.info(
                            "Update available: v%s -> v%s",
                            __version__,
                            update_info["version"],
                        )
                        self._pending_update = update_info
                        self._update_menu()

                        if self.icon:
                            self.icon.notify(
                                f"Update Available: v{update_info['version']}",
                                "Click the tray icon to download",
                            )

                except Exception as e:
                    logger.warning("Update check failed: %s", e)

                await asyncio.sleep(3600 * 6)

        def run_update_checker():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(update_checker_loop())
            finally:
                loop.close()

        self._update_check_thread = threading.Thread(
            target=run_update_checker, daemon=True
        )
        self._update_check_thread.start()


def _acquire_single_instance_lock():
    """Return a lock handle that prevents a second instance from starting.

    On Windows uses a named mutex; on other platforms a lock file.
    Returns the handle (must stay alive for the lifetime of the process).
    Returns None if another instance is already running.
    """
    if sys.platform == "win32":
        import ctypes
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


def main():
    """Entry point for desktop application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    logger.info("Starting Lengrowth Outreach desktop app v%s", __version__)

    # Prevent multiple instances — if a second process starts, exit immediately
    _lock = _acquire_single_instance_lock()
    if _lock is None:
        logger.info("Another instance is already running. Exiting.")
        sys.exit(0)

    # Register protocol handler on Windows
    register_protocol_handler()

    app = TrayApp()

    # Capture pending protocol URL to handle after the icon is ready
    pending_protocol_url = None
    if len(sys.argv) > 1 and sys.argv[1].startswith("lengrowth://"):
        pending_protocol_url = sys.argv[1]

    if pending_protocol_url:
        if handle_protocol_url(pending_protocol_url, app.auth):
            app._update_menu()
            # Notification deferred to _on_setup since icon isn't ready yet
            app._pending_login_notification = True

    try:
        app.run()
    except KeyboardInterrupt:
        logger.info("Interrupted")
        sys.exit(0)
    except Exception as e:
        logger.exception("Fatal error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
