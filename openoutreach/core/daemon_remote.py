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
from collections.abc import Callable
from datetime import datetime, timezone as tz
from pathlib import Path
from typing import Any, Optional

from openoutreach.core.browser_detect import BrowserInfo, get_preferred_browser
from openoutreach.core.remote_client import (
    DaemonConfig,
    RemoteClient,
    SubscriptionStatus,
)
from openoutreach.desktop.__version__ import __version__

try:
    import numpy as np  # Required for BayesianQualifier
except ImportError:
    np = None  # type: ignore

logger = logging.getLogger(__name__)


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
        refresh_token: Optional[str] = None,
        on_token_refresh: Optional[Callable[[str], None]] = None,
    ):
        self.api_url = api_url
        self.token = token
        self.linkedin_profile_id = linkedin_profile_id
        self.data_dir = data_dir or self._default_data_dir()
        self.daemon_id = self._get_or_create_daemon_id()
        self.on_token_refresh = on_token_refresh

        self.client = RemoteClient(api_url, token, self.daemon_id, refresh_token)
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

        # Check subscription status before starting
        sub_status = await self.client.check_subscription_status()
        if not self._check_subscription_status(sub_status):
            return

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
                self._subscription_check_loop(),
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

        logger.info("Starting browser session...")

        # Initialize MongoDB connection (required for rate limiting)
        from openoutreach.mongodb.connection import initialize_mongodb_connection
        if not initialize_mongodb_connection():
            logger.warning("MongoDB connection failed - rate limiting will be bypassed")

        creds = await self.client.get_credentials(self.linkedin_profile_id)

        # Load the real LinkedInProfile from database for rate limiting
        from openoutreach.linkedin.models import LinkedInProfile as RealLinkedInProfile

        real_profile = RealLinkedInProfile.get(self.linkedin_profile_id)
        if not real_profile:
            raise RuntimeError(f"LinkedIn profile {self.linkedin_profile_id} not found in database")

        # Create mock wrapper that delegates to real profile for rate limiting
        class MockLinkedInProfile:
            def __init__(self, profile_id: str, real_profile: RealLinkedInProfile):
                self._id = profile_id
                self.linkedin_username = ""
                self.linkedin_password = ""
                self._cookie_data_json = None
                self.user = None
                self._real_profile = real_profile

            def refresh_from_db(self, fields: Optional[list] = None):
                """Refresh from database."""
                self._real_profile.refresh_from_db(fields=fields)

            def save(self, update_fields: Optional[list] = None):
                """Save to database."""
                self._real_profile.save(update_fields=update_fields)

            def can_execute(self, action_type: str) -> bool:
                """Delegate to real profile for rate limit checks."""
                return self._real_profile.can_execute(action_type)

            def record_action(self, action_type: str, campaign, details: Optional[dict] = None):
                """Delegate to real profile for action logging."""
                self._real_profile.record_action(action_type, campaign, details)

            def mark_exhausted(self, action_type: str):
                """Delegate to real profile."""
                self._real_profile.mark_exhausted(action_type)

            @property
            def connect_daily_limit(self):
                return self._real_profile.connect_daily_limit

            @property
            def follow_up_daily_limit(self):
                return self._real_profile.follow_up_daily_limit

            @property
            def cookie_data(self):
                """Return parsed cookie dict from JSON string."""
                if not self._cookie_data_json:
                    return None
                try:
                    return json.loads(self._cookie_data_json)
                except (json.JSONDecodeError, TypeError):
                    return None

            @cookie_data.setter
            def cookie_data(self, value):
                """Store cookie dict as JSON string."""
                if value is None:
                    self._cookie_data_json = None
                else:
                    self._cookie_data_json = json.dumps(value)

        # Create mock session object for linkedin_cli compatibility
        class RemoteSession:
            def __init__(self, profile_id: str, real_profile: RealLinkedInProfile):
                self.linkedin_profile = MockLinkedInProfile(profile_id, real_profile)
                self.page: Any = None
                self.context: Any = None
                self.browser: Any = None
                self.playwright: Any = None
                self.campaign: Optional[Any] = None  # Set before task execution
                # Load user from the real profile (lazy loaded via property)
                self.user: Optional[Any] = real_profile.user

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

        self.session = RemoteSession(self.linkedin_profile_id, real_profile)

        # Load saved cookies if available
        # API returns cookie_data as JSON string (already decrypted)
        storage_state = None
        if creds.get("cookie_data"):
            try:
                storage_state = json.loads(creds["cookie_data"])
                # Store in mock profile for session compatibility
                self.session.linkedin_profile._cookie_data_json = creds["cookie_data"]
            except (json.JSONDecodeError, TypeError):
                logger.warning("Invalid cookie data, will authenticate from scratch")

        # Launch browser using user's native browser (not Playwright's bundled Chromium)
        if not self.browser:
            raise BrowserNotFoundError("Browser not detected")

        # Extract proxy configuration from profile
        proxy_server = real_profile.proxy_server
        proxy_username = real_profile.proxy_username
        proxy_password = real_profile.proxy_password

        logger.info("Launching %s (channel: %s)", self.browser.name, self.browser.channel)
        (
            self.session.page,
            self.session.context,
            self.session.browser,
            self.session.playwright,
        ) = self._launch_browser_with_channel(
            storage_state,
            self.browser.channel,
            proxy_server,
            proxy_username,
            proxy_password,
        )

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
            if "verification" in str(e).lower() or "challenge" in str(e).lower():
                await self.client.report_session_state(
                    linkedin_profile_id=self.linkedin_profile_id,
                    is_logged_in=False,
                    requires_verification=True,
                    verification_type="challenge",
                )
                # Desktop daemon can show challenge directly in local browser
                self._show_verification_notification(is_desktop=True)
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
                        # Trigger token refresh if callback provided
                        if self.on_token_refresh and self.client._token != self.token:
                            self.on_token_refresh(self.client._token)

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
        from openoutreach.mongodb.models import Campaign

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

        # Validate campaign (same as local daemon does)
        campaign_id = task.get("payload", {}).get("campaign_id")
        if not campaign_id:
            raise ValueError("Task missing campaign_id in payload")

        campaign = Campaign.get(campaign_id)
        if not campaign or campaign.status != Campaign.Status.ACTIVE:
            raise ValueError(f"Campaign {campaign_id} not found or inactive")

        # Verify session is initialized
        if not self.session:
            raise RuntimeError("Session not initialized")

        # Set campaign on session (required by all handlers)
        self.session.campaign = campaign

        # Set user on session (required for some operations)
        from openoutreach.mongodb.models_user import User
        if campaign.user_id:
            self.session.user = User.get(campaign.user_id)

        # Build minimal task object for handler
        task_obj = type(
            "Task",
            (),
            {
                "task_type": task["task_type"],
                "payload": task.get("payload", {}),
                "campaign_id": campaign_id,
            },
        )()

        # Build qualifiers for this campaign (same as local daemon does)
        qualifiers = self._build_qualifiers_for_campaign(campaign)

        # Execute handler synchronously (handlers are not async)
        result = handler(task=task_obj, session=self.session, qualifiers=qualifiers)
        return result if isinstance(result, dict) else None

    def _build_qualifiers_for_campaign(self, campaign) -> dict:
        """Build qualifiers dict with a single campaign's qualifier.

        Remote daemon builds qualifiers lazily per task to avoid loading
        all campaigns upfront. Returns {campaign.pk: qualifier}.
        """
        from openoutreach.core.conf import CAMPAIGN_CONFIG
        from openoutreach.linkedin.ml.qualifier import BayesianQualifier
        from openoutreach.crm.models import Lead

        q = BayesianQualifier(
            seed=42,
            n_mc_samples=CAMPAIGN_CONFIG["qualification_n_mc_samples"],
            campaign=campaign,
        )

        # Warm-start if we have labeled data
        X, y = Lead.get_labeled_arrays(campaign)
        if len(X) > 0:
            q.warm_start(X, y)
            logger.debug(
                "GP qualifier warm-started on %d samples (%d+, %d-) for campaign %s",
                len(y), int((y == 1).sum()), int((y == 0).sum()), campaign.pk,
            )

        return {campaign.pk: q}

    async def _config_refresh_loop(self):
        """Periodically refresh config from backend."""
        while self.running:
            await asyncio.sleep(300)
            try:
                self.config = await self.client.get_config(self.linkedin_profile_id)
            except Exception as e:
                logger.warning("Config refresh failed: %s", e)

    async def _sync_cookies(self):
        """Sync cookies to backend.

        Sends cookie data as JSON string (NOT encrypted).
        The backend API handles encryption before storing in LinkedInProfile.cookie_data_encrypted.
        """
        if not self.session or not self.session.context:
            return
        try:
            state = self.session.context.storage_state()
            cookie_json = json.dumps(state)
            # Send plaintext - API will encrypt before storing
            await self.client.sync_cookies(self.linkedin_profile_id, cookie_json)
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

    def _check_subscription_status(self, status: SubscriptionStatus) -> bool:
        """Check subscription status and log if daemon cannot run.

        Returns:
            True if daemon can run, False otherwise.
        """
        if status.user_status == "blocked":
            logger.error("Account is blocked: %s", status.block_reason or "Unknown reason")
            self.running = False
            self._show_block_notification(status.block_reason)
            return False

        if not status.is_active:
            if status.subscription_status == "expired":
                logger.error("Trial has expired")
                self.running = False
                self._show_trial_expired_notification()
            elif status.subscription_status == "canceled":
                logger.error("Subscription has been canceled")
                self.running = False
                self._show_subscription_canceled_notification()
            elif status.subscription_status == "past_due":
                logger.error("Payment is past due")
                self.running = False
                self._show_payment_failed_notification()
            else:
                logger.error("Subscription is not active: %s", status.subscription_status)
                self.running = False
            return False

        return True

    async def _subscription_check_loop(self) -> None:
        """Periodically check subscription status and stop if needed."""
        if not self.config:
            return

        last_trial_warning_sent: Optional[datetime] = None

        while self.running:
            try:
                status = await self.client.check_subscription_status()
                if not self._check_subscription_status(status):
                    await self.stop()
                    break

                # Send trial ending notification (once per day, 1 day before expiry)
                if status.subscription_status == "trialing" and status.trial_ends_at:
                    trial_end = datetime.fromisoformat(status.trial_ends_at.replace("Z", "+00:00"))
                    now = datetime.now(tz.utc)
                    time_until_expiry = trial_end - now

                    # If less than 24 hours and we haven't sent warning yet today
                    if time_until_expiry.total_seconds() < 86400:
                        seconds_since_last_warning = (
                            (now - last_trial_warning_sent).total_seconds()
                            if last_trial_warning_sent
                            else 999999
                        )
                        if (
                            not last_trial_warning_sent
                            or seconds_since_last_warning > 86400
                        ):
                            hours_left = int(time_until_expiry.total_seconds() / 3600)
                            self._show_trial_ending_notification(hours_left)
                            last_trial_warning_sent = now

            except Exception as e:
                logger.warning("Subscription check failed: %s", e)

            await asyncio.sleep(300)  # Check every 5 minutes

    def _show_block_notification(self, reason: Optional[str] = None) -> None:
        """Show system notification for blocked account."""
        message_title = "Lengrowth - Account Blocked"
        message_body = (
            f"Your account has been blocked: {reason}\n"
            "Please log in to the web platform or contact support for more information."
        )

        self._show_system_notification(message_title, message_body)

    def _show_trial_ending_notification(self, hours_left: int) -> None:
        """Show system notification for trial ending soon."""
        if hours_left > 1:
            time_text = f"{hours_left} hours"
        else:
            time_text = "1 hour"

        message_title = "Lengrowth - Trial Ending Soon"
        message_body = (
            f"Your trial ends in {time_text}. Please log in to the web platform "
            "to choose a plan and continue using Lengrowth."
        )

        self._show_system_notification(message_title, message_body)

    def _show_trial_expired_notification(self) -> None:
        """Show system notification for expired trial."""
        message_title = "Lengrowth - Trial Expired"
        message_body = (
            "Your trial has ended. Please log in to the web platform to choose a plan "
            "and continue using Lengrowth."
        )

        self._show_system_notification(message_title, message_body)

    def _show_subscription_canceled_notification(self) -> None:
        """Show system notification for canceled subscription."""
        message_title = "Lengrowth - Subscription Canceled"
        message_body = (
            "Your subscription has been canceled. Please log in to the web platform "
            "to reactivate or choose a new plan."
        )

        self._show_system_notification(message_title, message_body)

    def _show_payment_failed_notification(self) -> None:
        """Show system notification for payment failure."""
        message_title = "Lengrowth - Payment Failed"
        message_body = (
            "Your payment has failed. Please log in to the web platform to update "
            "your payment method."
        )

        self._show_system_notification(message_title, message_body)

    def _show_system_notification(self, title: str, body: str) -> None:
        """Show cross-platform system notification."""
        try:
            import subprocess
            import platform

            system = platform.system()
            if system == "Darwin":  # macOS
                subprocess.run([
                    "osascript",
                    "-e",
                    f'display notification "{body}" with title "{title}"'
                ], check=False, timeout=5)
            elif system == "Windows":
                ps_lines = [
                    "[Windows.UI.Notifications.ToastNotificationManager, "
                    "Windows.UI.Notifications] | Out-Null",
                    "[Windows.Data.Xml.Dom.XmlDocument] | Out-Null",
                    "$t = [Windows.UI.Notifications.ToastNotificationManager]"
                    "::GetTemplateContent(0)",
                    "$x = [xml]$t.GetXml()",
                    f'$x.toast.visual.binding.text[0].InnerText = "{title}"',
                    f'$x.toast.visual.binding.text[1].InnerText = "{body}"',
                    "$x = [Windows.Data.Xml.Dom.XmlDocument]::new()",
                    "$x.LoadXml($t.GetXml())",
                    "$o = [Windows.UI.Notifications.ToastNotification]::new($x)",
                    "[Windows.UI.Notifications.ToastNotificationManager]"
                    '::CreateToastNotifier("Lengrowth").Show($o)',
                ]
                ps_script = ";".join(ps_lines)
                subprocess.run(
                    ["powershell", "-Command", ps_script],
                    check=False,
                    timeout=5,
                )
            logger.info("Notification shown: %s", title)
        except Exception as e:
            logger.debug("Could not show system notification: %s", e)

    def _show_verification_notification(self, is_desktop: bool = True) -> None:
        """Show system notification for LinkedIn verification requirement.

        Args:
            is_desktop: If True, desktop daemon shows challenge in local browser.
                       If False, redirect to web platform.
        """
        message_title = "Lengrowth - Action Required"
        if is_desktop:
            message_body = (
                "LinkedIn requires verification. Complete the challenge in "
                "the browser and restart the daemon."
            )
        else:
            message_body = (
                "LinkedIn requires verification. Log in to the web platform "
                "to complete the challenge."
            )

        self._show_system_notification(message_title, message_body)

    def _launch_browser_with_channel(
        self,
        storage_state,
        channel: str,
        proxy_server: Optional[str] = None,
        proxy_username: Optional[str] = None,
        proxy_password: Optional[str] = None,
    ):
        """Launch browser using Playwright with specified channel (chrome/msedge/webkit).

        This uses the user's installed browser instead of Playwright's bundled Chromium.
        Accepts optional per-profile proxy configuration.
        """
        from playwright.sync_api import sync_playwright
        from linkedin_cli.conf import (
            BROWSER_PROXY_SERVER,
            BROWSER_PROXY_USERNAME,
            BROWSER_PROXY_PASSWORD,
            BROWSER_SLOW_MO,
            BROWSER_DEFAULT_TIMEOUT_MS,
        )
        from playwright_stealth import Stealth

        logger.debug("Launching Playwright with channel=%s", channel)
        playwright = sync_playwright().start()

        # Launch with channel to use installed browser
        if channel == "webkit":
            browser = playwright.webkit.launch(headless=False, slow_mo=BROWSER_SLOW_MO)
        elif channel == "msedge":
            browser = playwright.chromium.launch(
                headless=False,
                slow_mo=BROWSER_SLOW_MO,
                channel="msedge",
            )
        else:  # chrome
            browser = playwright.chromium.launch(
                headless=False,
                slow_mo=BROWSER_SLOW_MO,
                channel="chrome",
            )

        # Build context options
        context_options = {"storage_state": storage_state}

        # Priority: per-profile proxy > environment proxy > no proxy
        if proxy_server:
            proxy_config = {"server": proxy_server}
            if proxy_username and proxy_password:
                proxy_config["username"] = proxy_username
                proxy_config["password"] = proxy_password
            context_options["proxy"] = proxy_config
            logger.info("Using profile-specific proxy: %s", proxy_server)
        elif BROWSER_PROXY_SERVER:
            proxy_config = {"server": BROWSER_PROXY_SERVER}
            if BROWSER_PROXY_USERNAME and BROWSER_PROXY_PASSWORD:
                proxy_config["username"] = BROWSER_PROXY_USERNAME
                proxy_config["password"] = BROWSER_PROXY_PASSWORD
            context_options["proxy"] = proxy_config
            logger.info("Using environment proxy: %s", BROWSER_PROXY_SERVER)

        context = browser.new_context(**context_options)
        context.set_default_timeout(BROWSER_DEFAULT_TIMEOUT_MS)
        context.set_default_navigation_timeout(BROWSER_DEFAULT_TIMEOUT_MS)

        # Block resource-heavy content to reduce bandwidth
        context.route("**/*", lambda route: (
            route.abort() if route.request.resource_type in ["image", "media", "font", "stylesheet"]
            and not any(domain in route.request.url for domain in ["linkedin.com", "licdn.com"])
            else route.continue_()
        ))

        Stealth().apply_stealth_sync(context)
        page = context.new_page()
        return page, context, browser, playwright


async def run_daemon(
    api_url: str,
    token: str,
    linkedin_profile_id: str,
    refresh_token: Optional[str] = None,
    on_token_refresh: Optional[Callable[[str], None]] = None,
):
    """Entry point for the daemon."""
    daemon = RemoteDaemon(
        api_url,
        token,
        linkedin_profile_id,
        refresh_token=refresh_token,
        on_token_refresh=on_token_refresh,
    )

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
