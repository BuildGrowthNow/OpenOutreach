"""Remote daemon - runs on user's desktop, connects to AWS backend.

The desktop daemon executes LinkedIn automation tasks locally using the user's
residential IP and real browser, while communicating with the centralized backend
for task coordination, cookie sync, and status reporting.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import uuid
from datetime import datetime, timezone as tz
from pathlib import Path
from typing import Any, Optional

from openoutreach.core.browser_detect import BrowserInfo, get_preferred_browser
from openoutreach.core.remote_client import DaemonConfig, RemoteClient

logger = logging.getLogger(__name__)

from openoutreach.desktop.__version__ import __version__


class RemoteDaemonError(Exception):
    """Base exception for remote daemon errors."""


class BrowserNotFoundError(RemoteDaemonError):
    """No supported browser found on the system."""


class RemoteDaemon:
    """Desktop daemon that executes LinkedIn automation locally."""

    def __init__(
        self,
        api_url: str,
        token: str,
        linkedin_profile_id: str,
        data_dir: Optional[Path] = None,
    ):
        self.api_url = api_url
        self.token = token
        self.linkedin_profile_id = linkedin_profile_id
        self.data_dir = data_dir or self._default_data_dir()
        self.daemon_id = self._get_or_create_daemon_id()

        self.client = RemoteClient(api_url, token, self.daemon_id)
        self.config: Optional[DaemonConfig] = None
        self.session = None
        self.browser: Optional[BrowserInfo] = None
        self.running = False
        self.start_time: Optional[datetime] = None
        self.last_task_at: Optional[datetime] = None

        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _default_data_dir(self) -> Path:
        """Get platform-specific data directory."""
        if sys.platform == "darwin":
            return Path.home() / "Library/Application Support/Lengrowth"
        elif sys.platform == "win32":
            return Path.home() / "AppData/Local/Lengrowth"
        return Path.home() / ".lengrowth"

    def _get_or_create_daemon_id(self) -> str:
        """Get or create persistent daemon ID."""
        id_file = self.data_dir / "daemon_id"
        if id_file.exists():
            return id_file.read_text().strip()

        daemon_id = str(uuid.uuid4())
        id_file.parent.mkdir(parents=True, exist_ok=True)
        id_file.write_text(daemon_id)
        return daemon_id

    async def start(self):
        """Start the daemon and run main loops."""
        logger.info("Starting remote daemon v%s...", __version__)
        self.running = True
        self.start_time = datetime.now(tz.utc)

        # Detect browser
        self.browser = get_preferred_browser()
        if not self.browser:
            raise BrowserNotFoundError(
                "No supported browser found. Please install Chrome or Edge."
            )
        logger.info("Using browser: %s", self.browser.name)

        # Fetch config
        self.config = await self.client.get_config(self.linkedin_profile_id)
        logger.info("Config loaded: velocity=%d/hr", self.config.velocity)

        # Start browser session
        await self._start_session()

        # Run loops concurrently
        try:
            await asyncio.gather(
                self._heartbeat_loop(),
                self._task_loop(),
                self._config_refresh_loop(),
                return_exceptions=True,
            )
        except Exception as e:
            logger.exception("Main loop crashed: %s", e)
            raise

    async def stop(self):
        """Stop the daemon gracefully."""
        logger.info("Stopping daemon...")
        self.running = False

        if self.session:
            await self._sync_cookies()
            self.session.close()

        await self.client.close()

    async def _start_session(self):
        """Initialize browser session using user's browser."""
        from linkedin_cli.auth import authenticate
        from linkedin_cli.browser.login import launch_browser

        logger.info("Starting browser session...")

        creds = await self.client.get_credentials(self.linkedin_profile_id)

        # Create mock LinkedInProfile for session compatibility
        class MockLinkedInProfile:
            def __init__(self, profile_id: str):
                self._id = profile_id
                self.linkedin_username = ""
                self.linkedin_password = ""
                self.cookie_data_encrypted = None
                self.user = None

            def refresh_from_db(self, fields: Optional[list] = None):
                pass

            def save(self, update_fields: Optional[list] = None):
                pass

            @property
            def cookie_data(self):
                if not self.cookie_data_encrypted:
                    return None
                try:
                    return json.loads(self.cookie_data_encrypted)
                except (json.JSONDecodeError, TypeError):
                    return None

            @cookie_data.setter
            def cookie_data(self, value):
                if value is None:
                    self.cookie_data_encrypted = None
                else:
                    self.cookie_data_encrypted = json.dumps(value)

        # Create mock session object for linkedin_cli compatibility
        class RemoteSession:
            def __init__(self, profile_id: str):
                self.linkedin_profile = MockLinkedInProfile(profile_id)
                self.page: Any = None
                self.context: Any = None
                self.browser: Any = None
                self.playwright: Any = None
                self.campaign: Any = None
                self.user: Any = None

            def close(self):
                if self.context and hasattr(self.context, "close"):
                    self.context.close()
                if self.browser and hasattr(self.browser, "close"):
                    self.browser.close()
                if self.playwright and hasattr(self.playwright, "stop"):
                    self.playwright.stop()

            def wait(self):
                """Compatibility method for task handlers."""
                pass

        self.session = RemoteSession(self.linkedin_profile_id)

        # Load saved cookies if available
        storage_state = None
        if creds.get("cookie_data"):
            try:
                storage_state = json.loads(creds["cookie_data"])
            except (json.JSONDecodeError, TypeError):
                logger.warning("Invalid cookie data, will authenticate from scratch")

        # Launch browser
        (
            self.session.page,
            self.session.context,
            self.session.browser,
            self.session.playwright,
        ) = launch_browser(storage_state=storage_state)

        try:
            # Authenticate if no valid session
            if not storage_state:
                self.session.linkedin_profile.linkedin_username = creds["email"]
                self.session.linkedin_profile.linkedin_password = creds["password"]
                authenticate(self.session, username=creds["email"], password=creds["password"])
                await self._sync_cookies()

            await self.client.report_session_state(
                linkedin_profile_id=self.linkedin_profile_id,
                is_logged_in=True,
            )
            logger.info("Logged in to LinkedIn")

        except Exception as e:
            logger.error("Login failed: %s", e)
            if "verification" in str(e).lower():
                await self.client.report_session_state(
                    linkedin_profile_id=self.linkedin_profile_id,
                    is_logged_in=False,
                    requires_verification=True,
                )
            raise

    async def _heartbeat_loop(self):
        """Send periodic heartbeats to backend."""
        if not self.config or not self.start_time or not self.browser:
            return

        while self.running:
            try:
                uptime = int((datetime.now(tz.utc) - self.start_time).total_seconds())
                await self.client.heartbeat(
                    linkedin_profile_id=self.linkedin_profile_id,
                    version=__version__,
                    uptime_seconds=uptime,
                    browser=self.browser.name,
                )
            except Exception as e:
                logger.warning("Heartbeat failed: %s", e)

            await asyncio.sleep(self.config.heartbeat_interval_seconds)

    async def _task_loop(self):
        """Main task execution loop."""
        if not self.config:
            return

        while self.running:
            try:
                if not self._is_active_time():
                    await asyncio.sleep(60)
                    continue

                task = await self.client.claim_task(self.linkedin_profile_id)

                if not task:
                    await asyncio.sleep(self.config.poll_interval_seconds)
                    continue

                logger.info("Executing: %s (%s)", task["task_type"], task["task_id"])
                start = datetime.now(tz.utc)

                try:
                    result = await asyncio.to_thread(self._execute_task, task)

                    duration_ms = int((datetime.now(tz.utc) - start).total_seconds() * 1000)
                    await self.client.report_result(
                        task_id=task["task_id"],
                        status="completed",
                        result=result,
                        duration_ms=duration_ms,
                    )

                    self.last_task_at = datetime.now(tz.utc)
                    await self._sync_cookies()

                except Exception as e:
                    duration_ms = int((datetime.now(tz.utc) - start).total_seconds() * 1000)
                    await self.client.report_result(
                        task_id=task["task_id"],
                        status="failed",
                        error=str(e),
                        duration_ms=duration_ms,
                    )
                    logger.error("Task failed: %s", e)

                    if "authentication" in str(e).lower() or "401" in str(e):
                        await self.client.report_session_state(
                            linkedin_profile_id=self.linkedin_profile_id,
                            is_logged_in=False,
                        )

            except Exception as e:
                logger.error("Task loop error: %s", e)
                await asyncio.sleep(30)

    def _execute_task(self, task: dict) -> Optional[dict]:
        """Execute a task using the appropriate handler (runs in thread).

        Args:
            task: Task dict from backend with task_type and payload

        Returns:
            Task result dict
        """
        from openoutreach.linkedin.tasks.check_pending import handle_check_pending
        from openoutreach.linkedin.tasks.connect import handle_connect
        from openoutreach.linkedin.tasks.follow_up import handle_follow_up
        from openoutreach.linkedin.tasks.send_manual_message import handle_send_manual_message

        # Map task types to handlers
        handlers = {
            "connect": handle_connect,
            "check_pending": handle_check_pending,
            "follow_up": handle_follow_up,
            "send_manual_message": handle_send_manual_message,
        }

        handler = handlers.get(task["task_type"])
        if not handler:
            raise ValueError(f"Unknown task type: {task['task_type']}")

        # Build minimal task object for handler
        task_obj = type(
            "Task",
            (),
            {
                "task_type": task["task_type"],
                "payload": task.get("payload", {}),
                "campaign_id": task.get("campaign_id"),
            },
        )()

        # Execute handler synchronously (handlers are not async)
        # qualifiers=None is acceptable for remote daemon - handlers will skip ML features
        result = handler(task=task_obj, session=self.session, qualifiers=None)
        return result if isinstance(result, dict) else None

    async def _config_refresh_loop(self):
        """Periodically refresh config from backend."""
        while self.running:
            await asyncio.sleep(300)
            try:
                self.config = await self.client.get_config(self.linkedin_profile_id)
            except Exception as e:
                logger.warning("Config refresh failed: %s", e)

    async def _sync_cookies(self):
        """Sync cookies to backend."""
        if not self.session or not self.session.context:
            return
        try:
            state = self.session.context.storage_state()
            cookie_data = json.dumps(state)
            await self.client.sync_cookies(self.linkedin_profile_id, cookie_data)
        except Exception as e:
            logger.warning("Cookie sync failed: %s", e)

    def _is_active_time(self) -> bool:
        """Check if within active hours configured in backend."""
        if not self.config or not self.config.enable_active_hours:
            return True

        from zoneinfo import ZoneInfo

        zone = ZoneInfo(self.config.active_timezone)
        now = datetime.now(zone)

        if now.weekday() not in self.config.active_days:
            return False

        return self.config.active_start_hour <= now.hour < self.config.active_end_hour


async def run_daemon(api_url: str, token: str, linkedin_profile_id: str):
    """Entry point for the daemon."""
    daemon = RemoteDaemon(api_url, token, linkedin_profile_id)

    try:
        await daemon.start()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
        await daemon.stop()
    except Exception as e:
        logger.exception("Daemon crashed: %s", e)
        await daemon.stop()
        raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Lengrowth Linkedin Remote Daemon")
    parser.add_argument("--api-url", required=True, help="Backend API URL")
    parser.add_argument("--token", required=True, help="JWT token")
    parser.add_argument("--profile-id", required=True, help="LinkedIn profile ID")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(run_daemon(args.api_url, args.token, args.profile_id))
