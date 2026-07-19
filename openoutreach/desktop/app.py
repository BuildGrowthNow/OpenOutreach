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
        self._update_check_task: Optional[asyncio.Task] = None

    def run(self):
        """Run the tray application."""
        icon = pystray.Icon(
            "OpenOutreach",
            self._create_icon(),
            "OpenOutreach LinkedIn",
            menu=self._create_menu(),
        )
        self.icon = icon
        icon.run(setup=self._on_setup)

    def _create_icon(self) -> Image.Image:
        """Create tray icon."""
        icon_path = Path(__file__).parent / "assets" / "icon.png"
        if icon_path.exists():
            try:
                return Image.open(icon_path)
            except Exception as e:
                logger.warning("Failed to load icon: %s", e)

        # Fallback: create simple colored circle
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        color = (34, 197, 94) if self._is_running() else (156, 163, 175)
        draw.ellipse([8, 8, 56, 56], fill=color)
        return img

    def _create_menu(self) -> pystray.Menu:
        """Create tray menu based on auth state."""
        if not self.auth.is_logged_in():
            items = [
                Item(f"OpenOutreach LinkedIn v{__version__}", None, enabled=False),
                pystray.Menu.SEPARATOR,
                Item("Login to OpenOutreach", self._on_login),
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

        # Build status line showing subscription status
        daemon_running = "Running" if self._is_running() else "Stopped"
        status_text = f"Status: {daemon_running}"

        items = [
            Item(f"OpenOutreach LinkedIn v{__version__}", None, enabled=False),
            Item(
                status_text,
                None,
                enabled=False,
            ),
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

    def _on_setup(self, icon):
        """Called when tray icon is ready."""
        icon.visible = True

        # Auto-start daemon if logged in
        if self.auth.is_logged_in():
            self._start_daemon()

        # Start periodic update checks
        self._start_update_checker()

    def _on_login(self):
        """Open login page in browser."""
        # Open web platform (Next.js), not API backend
        # Extract base URL properly (handles localhost, custom domains, etc.)
        import urllib.parse
        parsed = urllib.parse.urlparse(self.config.api_url)
        # For production: replace linkedin-api subdomain with linkedin
        # For localhost/custom: use as-is
        if "linkedin-api." in parsed.netloc:
            platform_url = self.config.api_url.replace("linkedin-api.", "linkedin.")
        else:
            platform_url = self.config.api_url
        login_url = f"{platform_url}/login?desktop=true&callback=openoutreach://auth"
        webbrowser.open(login_url)

    def _on_logout(self):
        """Log out and stop daemon."""
        self._stop_daemon()
        self.auth.logout()
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
        # Open web platform (Next.js), not API backend
        # Extract base URL properly (handles localhost, custom domains, etc.)
        import urllib.parse
        parsed = urllib.parse.urlparse(self.config.api_url)
        # For production: replace linkedin-api subdomain with linkedin
        # For localhost/custom: use as-is
        if "linkedin-api." in parsed.netloc:
            platform_url = self.config.api_url.replace("linkedin-api.", "linkedin.")
        else:
            platform_url = self.config.api_url
        webbrowser.open(platform_url)

    def _on_manage_subscription(self):
        """Open subscription management page."""
        # Extract base URL properly (handles localhost, custom domains, etc.)
        import urllib.parse
        parsed = urllib.parse.urlparse(self.config.api_url)
        # For production: replace linkedin-api subdomain with linkedin
        # For localhost/custom: use as-is
        if "linkedin-api." in parsed.netloc:
            platform_url = self.config.api_url.replace("linkedin-api.", "linkedin.")
        else:
            platform_url = self.config.api_url
        webbrowser.open(f"{platform_url}/settings/billing")

    def _on_quit(self):
        """Quit the application."""
        self._stopping = True
        self._stop_daemon()
        self._stop_update_checker()
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

        if not token or not profile_id:
            logger.error("Missing credentials")
            return

        def on_token_refresh(new_token: str):
            """Callback when token is refreshed."""
            logger.info("Access token refreshed, updating keychain")
            self.auth.update_token(new_token)

        def run_daemon():
            """Background thread entry point."""
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
                # Show specific error for missing browser
                if isinstance(e, BrowserNotFoundError):
                    error_msg = "No supported browser found. Please install Chrome or Edge."
                else:
                    error_msg = "OpenOutreach daemon encountered an error. Check logs for details."

                if self.icon:
                    self.icon.notify(
                        "Daemon Error",
                        error_msg,
                    )
            finally:
                self._loop.close()
                self._loop = None

        self.daemon_thread = threading.Thread(target=run_daemon, daemon=True)
        self.daemon_thread.start()

        logger.info("Daemon started")
        self._update_menu()

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

        # Wait for thread to finish
        if self.daemon_thread and self.daemon_thread.is_alive():
            self.daemon_thread.join(timeout=5)

        self.daemon = None
        self.daemon_thread = None

        logger.info("Daemon stopped")
        self._update_menu()

    def _start_update_checker(self):
        """Start background update checker."""
        if self._update_check_task is not None:
            return

        async def update_checker_loop():
            """Periodically check for updates."""
            await asyncio.sleep(10)  # Initial delay

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

                await asyncio.sleep(3600 * 6)  # Check every 6 hours

        def run_update_checker():
            """Run update checker in background thread."""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(update_checker_loop())
            finally:
                loop.close()

        update_thread = threading.Thread(target=run_update_checker, daemon=True)
        update_thread.start()

    def _stop_update_checker(self):
        """Stop the update checker."""
        if self._update_check_task:
            self._update_check_task.cancel()
            self._update_check_task = None


def main():
    """Entry point for desktop application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Reduce noise from third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    logger.info("Starting OpenOutreach desktop app v%s", __version__)

    # Register protocol handler on Windows
    register_protocol_handler()

    app = TrayApp()

    # Handle protocol URL if passed as argument
    if len(sys.argv) > 1 and sys.argv[1].startswith("openoutreach://"):
        if handle_protocol_url(sys.argv[1], app.auth):
            app._update_menu()
            if app.icon:
                app.icon.notify("Login successful", "You can now start automation")

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
