"""Remote daemon - runs on user's desktop, connects to AWS backend.

The desktop daemon executes LinkedIn automation tasks locally using the user's
residential IP and real browser, while communicating with the centralized backend
for task coordination, cookie sync, and status reporting.
"""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import sys
import threading
import uuid
from collections.abc import Callable
from datetime import datetime, timezone as tz
from pathlib import Path
from typing import Any, Optional

import httpx

from openoutreach.core.browser_detect import BrowserInfo, get_preferred_browser
from openoutreach.core.remote_client import (
    DaemonConfig,
    RemoteClient,
    SessionExpiredError,
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
        on_started: Optional[Callable[[], None]] = None,
    ):
        self.api_url = api_url
        self.token = token
        self.linkedin_profile_id = linkedin_profile_id
        self.data_dir = data_dir or self._default_data_dir()
        self.daemon_id = self._get_or_create_daemon_id()
        self.on_token_refresh = on_token_refresh
        self.on_started = on_started

        self.client = RemoteClient(
            api_url, token, self.daemon_id, refresh_token, on_token_refresh=on_token_refresh
        )
        self.config: Optional[DaemonConfig] = None
        self.session = None
        self.browser: Optional[BrowserInfo] = None
        self.running = False
        self.start_time: Optional[datetime] = None
        self.last_task_at: Optional[datetime] = None
        self._pending_cookie_state: Optional[dict] = None

        # All Playwright sync API calls must run on the same OS thread.
        # We keep one dedicated thread alive for the lifetime of the daemon and
        # dispatch work to it via a queue.  Each item is (fn, result_future).
        self._pw_queue: queue.Queue = queue.Queue()
        self._pw_thread: Optional[threading.Thread] = None

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

    def _start_pw_thread(self) -> None:
        """Start the dedicated Playwright thread that drains _pw_queue."""
        def _worker():
            while True:
                item = self._pw_queue.get()
                if item is None:  # sentinel — shut down
                    break
                fn, fut, loop = item
                try:
                    result = fn()
                    loop.call_soon_threadsafe(fut.set_result, result)
                except Exception as exc:
                    loop.call_soon_threadsafe(fut.set_exception, exc)

        self._pw_thread = threading.Thread(target=_worker, daemon=True, name="pw-worker")
        self._pw_thread.start()

    def _stop_pw_thread(self) -> None:
        """Send the sentinel to stop the Playwright thread."""
        self._pw_queue.put(None)
        if self._pw_thread:
            self._pw_thread.join(timeout=10)

    async def _run_on_pw_thread(self, fn: Callable) -> Any:
        """Schedule *fn* on the Playwright thread and await its result."""
        loop = asyncio.get_event_loop()
        fut: asyncio.Future = loop.create_future()
        self._pw_queue.put((fn, fut, loop))
        return await fut

    async def _startup_request(self, label: str, coro_fn, *, max_wait: int = 300):
        """Retry *coro_fn* on transient server errors (502/503/connect failures).

        Keeps retrying with exponential back-off (up to 30 s) for *max_wait*
        seconds total so a server deploy mid-startup doesn't crash the daemon.
        Raises immediately on auth errors (401/403) or once *max_wait* is
        exceeded.
        """
        delay = 5
        elapsed = 0
        while True:
            try:
                return await coro_fn()
            except httpx.HTTPStatusError as e:
                code = e.response.status_code
                if code in (502, 503, 504):
                    if elapsed >= max_wait:
                        raise
                    logger.warning(
                        "%s: server returned %d (deploy in progress?) — retrying in %ds",
                        label, code, delay,
                    )
                elif code == 401 and self.client._refresh_token:
                    logger.info("Got 401 on %s, attempting token refresh", label)
                    new_token = await self.client.refresh_access_token()
                    if not new_token:
                        raise
                    # retry once after refresh — fall through to next loop iteration
                else:
                    raise
            except (httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadError) as e:
                if elapsed >= max_wait:
                    raise
                logger.warning(
                    "%s: connection error (%s) — retrying in %ds", label, e, delay,
                )
            await asyncio.sleep(delay)
            elapsed += delay
            delay = min(delay * 2, 30)

    async def start(self):
        """Start the daemon and run main loops."""
        logger.info("Starting remote daemon v%s...", __version__)
        self.running = True
        self.start_time = datetime.now(tz.utc)
        self._start_pw_thread()

        # Check subscription status — retry through deploys (502/503) for up to 5 min
        try:
            sub_status = await self._startup_request(
                "subscription check", self.client.check_subscription_status
            )
        except Exception as e:
            logger.error("Subscription check failed: %s", e)
            self.running = False
            return

        if not self._check_subscription_status(sub_status):
            return

        # Notify the tray now that we've passed auth — running=True was set at the
        # top of start(), but the tray menu was built before that so it showed Stopped.
        if self.on_started:
            try:
                self.on_started()
            except Exception:
                pass

        # Detect browser
        self.browser = get_preferred_browser()
        if not self.browser:
            raise BrowserNotFoundError(
                "No supported browser found. Please install Chrome or Edge."
            )
        logger.info("Using browser: %s", self.browser.name)

        # Fetch config — retry through deploys for up to 5 min
        try:
            self.config = await self._startup_request(
                "get config",
                lambda: self.client.get_config(self.linkedin_profile_id),
            )
        except Exception as e:
            logger.error("Failed to fetch config: %s", e)
            self.running = False
            return
        assert self.config is not None
        logger.info("Config loaded: velocity=%d/hr", self.config.velocity)

        # Fetch bootstrap secrets (secret_key + MongoDB URI) via dedicated endpoint.
        # Separate from get_config so secrets are never mixed into the polling path.
        try:
            bootstrap = await self._startup_request(
                "get bootstrap",
                lambda: self.client.bootstrap(self.linkedin_profile_id),
            )
        except Exception as e:
            logger.error("Failed to fetch bootstrap secrets: %s", e)
            self.running = False
            return

        # Inject server-side env for the desktop process (no local .env available).
        # Sets os.environ first (for mongodb/crypto.py), then patches the pydantic
        # settings singleton (for core/crypto.py and llm.py).
        self._apply_server_env(bootstrap, self.config)

        # Connect to Atlas using the URI provided by the backend
        mongodb_uri = bootstrap.get("mongodb_uri")
        mongodb_name = bootstrap.get("mongodb_name", "openoutreach")
        if mongodb_uri:
            from openoutreach.mongodb.connection import initialize_mongodb_with_uri
            ok = initialize_mongodb_with_uri(mongodb_uri, mongodb_name)
            if ok:
                logger.info("MongoDB Atlas connected (db: %s)", mongodb_name)
            else:
                logger.warning("MongoDB Atlas connection failed — task execution may be degraded")
        else:
            logger.warning("No MongoDB URI in bootstrap — task execution will fail")

        # Schedule tasks for active campaigns
        try:
            result = await self.client.reconcile(self.linkedin_profile_id)
            logger.info("Reconcile: %d tasks across %d campaigns",
                        result.get("tasks_created", 0), result.get("campaigns", 0))
        except Exception as e:
            logger.warning("Initial reconcile failed: %s", e)

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

    def _apply_server_env(self, bootstrap: dict, config: "DaemonConfig") -> None:
        """Inject server-side env values for the desktop process.

        The desktop exe has no .env file, so modules that read os.environ or
        the pydantic settings singleton directly need these injected at runtime.
        Sets os.environ first (for mongodb/crypto.py), then patches the settings
        object (for core/crypto.py and llm.py).

        bootstrap: dict from /api/daemon/bootstrap (secret_key, mongodb_uri, mongodb_name)
        config: DaemonConfig from /api/daemon/config (llm fields)
        """
        import os
        from openoutreach.config import settings as app_settings

        mapping = {
            "SECRET_KEY": bootstrap.get("secret_key"),
            "LLM_API_KEY": config.llm_api_key,
            "LLM_API_BASE": config.llm_api_base,
            "AI_MODEL": config.ai_model,
            "LLM_PROVIDER": config.llm_provider,
            "MONGODB_URI": bootstrap.get("mongodb_uri"),
            "MONGODB_NAME": bootstrap.get("mongodb_name", "openoutreach"),
            "MONGODB_ENABLED": "true",
        }
        for env_key, value in mapping.items():
            if value:
                os.environ[env_key] = str(value)
                try:
                    object.__setattr__(app_settings, env_key, value)
                except Exception:
                    pass

        logger.info("Server env applied to desktop process")

    async def stop(self):
        """Stop the daemon gracefully."""
        logger.info("Stopping daemon...")
        self.running = False

        if self.session:
            await self._sync_cookies()
            # Close the browser on the Playwright thread so greenlet is happy.
            session = self.session
            try:
                await self._run_on_pw_thread(session.close)
            except Exception as e:
                logger.debug("Session close error: %s", e)

        self._stop_pw_thread()
        await self.client.close()

    async def _start_session(self):
        """Initialize browser session using user's browser."""
        from linkedin_cli.auth import authenticate

        logger.info("Starting browser session...")

        creds = await self.client.get_credentials(self.linkedin_profile_id)

        # Fetch proxy config from backend — no local MongoDB required
        profile_details = await self.client.get_profile_details(self.linkedin_profile_id)

        # Daily limits come from the config already loaded from the API
        connect_daily_limit = self.config.daily_connect_limit if self.config else 50
        follow_up_daily_limit = self.config.daily_message_limit if self.config else 30

        # Create self-contained mock profile — no local DB delegation
        class MockLinkedInProfile:
            def __init__(self, profile_id: str, _connect_limit: int, _follow_up_limit: int):
                self._id = profile_id
                self.linkedin_username = ""
                self.linkedin_password = ""
                self._cookie_data_json = None
                self.user = None
                self.user_id: Optional[str] = None
                self._connect_daily_limit = _connect_limit
                self._follow_up_daily_limit = _follow_up_limit
                self._exhausted: dict = {}

            def refresh_from_db(self, fields: Optional[list] = None):
                pass

            def save(self, update_fields: Optional[list] = None):
                pass

            def can_execute(self, action_type: str) -> bool:
                from datetime import datetime, timezone
                exhausted_date = self._exhausted.get(action_type)
                if exhausted_date is not None and exhausted_date == datetime.now(timezone.utc).date():
                    return False
                return True

            def record_action(self, action_type: str, campaign, details: Optional[dict] = None):
                from openoutreach.linkedin.models import ActionLog
                action_log = ActionLog(
                    linkedin_profile_id=self._id,
                    campaign_id=campaign._id if campaign else "",
                    action_type=action_type,
                    status="completed",
                    details=details or {},
                )
                action_log.save()

            def mark_exhausted(self, action_type: str):
                from datetime import datetime, timezone
                self._exhausted[action_type] = datetime.now(timezone.utc).date()

            @property
            def pk(self):
                return self._id

            @property
            def connect_daily_limit(self):
                return self._connect_daily_limit

            @property
            def follow_up_daily_limit(self):
                return self._follow_up_daily_limit

            @property
            def cookie_data(self):
                if not self._cookie_data_json:
                    return None
                try:
                    return json.loads(self._cookie_data_json)
                except (json.JSONDecodeError, TypeError):
                    return None

            @cookie_data.setter
            def cookie_data(self, value):
                if value is None:
                    self._cookie_data_json = None
                else:
                    self._cookie_data_json = json.dumps(value)

        # Create mock session object for linkedin_cli compatibility
        class RemoteSession:
            def __init__(self, profile_id: str, _connect_limit: int, _follow_up_limit: int):
                self.linkedin_profile = MockLinkedInProfile(profile_id, _connect_limit, _follow_up_limit)
                self.page: Any = None
                self.context: Any = None
                self.browser: Any = None
                self.playwright: Any = None
                self.campaign: Optional[Any] = None  # Set before task execution
                self.user: Optional[Any] = None  # Set per-task in _execute_task
                self.user_id: Optional[str] = None  # Set per-task in _execute_task
                self.linkedin_profile_id: str = profile_id
                self._self_profile: Optional[dict] = None

            @property
            def self_profile(self) -> dict:
                if self._self_profile is None:
                    from linkedin_cli.setup.self_profile import discover_self_profile
                    self._self_profile = discover_self_profile(self)
                return self._self_profile

            def close(self):
                if self.context and hasattr(self.context, "close"):
                    self.context.close()
                if self.browser and hasattr(self.browser, "close"):
                    self.browser.close()
                if self.playwright and hasattr(self.playwright, "stop"):
                    self.playwright.stop()

            def ensure_browser(self):
                """No-op: browser is always live in the remote daemon."""
                pass

            def wait(self, min_seconds=None, max_seconds=None):
                """Compatibility method for task handlers."""
                pass

        self.session = RemoteSession(self.linkedin_profile_id, connect_daily_limit, follow_up_daily_limit)

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

        # Decrypt proxy credentials — server sends Fernet-encrypted values
        from openoutreach.mongodb.crypto import safe_decrypt

        proxy_server = profile_details.get("proxy_server")
        proxy_username = safe_decrypt(profile_details.get("proxy_username_encrypted") or "")
        proxy_password = safe_decrypt(profile_details.get("proxy_password_encrypted") or "")

        logger.info("Launching %s (channel: %s)", self.browser.name, self.browser.channel)

        # sync_playwright() cannot run inside an asyncio event loop — run in a thread
        # Local aliases avoid Optional-type false positives inside the nested function.
        session = self.session
        browser_info = self.browser  # already asserted non-None above

        profile_dir = self._get_profile_data_dir()
        is_new_profile = not any(profile_dir.iterdir())

        def _launch_and_auth(headless: bool = True):
            page, context, browser, playwright = self._launch_browser_with_channel(
                storage_state,
                browser_info.channel,
                proxy_server,
                proxy_username,
                proxy_password,
                headless=headless,
                is_new_profile=is_new_profile,
            )
            session.page = page
            session.context = context
            session.browser = browser
            session.playwright = playwright

            # Only authenticate when there is no existing persistent profile.
            # On subsequent restarts the profile dir already holds the session,
            # so we skip authenticate() to avoid a fresh login (and a new-device email).
            # webkit has no persistent profile, so always fall back to storage_state check.
            needs_auth = (browser_info.channel == "webkit" and not storage_state) or (
                browser_info.channel != "webkit" and is_new_profile and not storage_state
            )
            if needs_auth:
                from openoutreach.mongodb.crypto import safe_decrypt
                password = safe_decrypt(creds.get("encrypted_password") or "")
                session.linkedin_profile.linkedin_username = creds["email"]
                session.linkedin_profile.linkedin_password = password
                authenticate(session, username=creds["email"], password=password)
                # Return fresh cookies so the async caller can sync them to the backend
                return context.storage_state()
            # No fresh auth — ensure the page is on linkedin.com so that
            # page.evaluate(fetch(...)) runs from a linkedin.com origin.
            # Persistent Chrome may reopen on chrome://newtab or any other URL
            # which causes "TypeError: Failed to fetch" for all Voyager API calls.
            current_url = page.url
            if "linkedin.com" not in current_url:
                page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
            return None

        try:
            fresh_state = await self._run_on_pw_thread(lambda: _launch_and_auth(True))
        except Exception as e:
            from linkedin_cli.exceptions import CheckpointChallengeError
            if isinstance(e, CheckpointChallengeError):
                # Challenge detected in headless mode — close and relaunch headed
                # so the user can interact with the verification in a visible window.
                logger.warning("LinkedIn challenge detected — relaunching browser headed for user interaction")
                await self._run_on_pw_thread(session.close)
                try:
                    fresh_state = await self._run_on_pw_thread(lambda: _launch_and_auth(False))
                except Exception as e2:
                    logger.error("Login failed after challenge relaunch: %s", e2)
                    await self.client.report_session_state(
                        linkedin_profile_id=self.linkedin_profile_id,
                        is_logged_in=False,
                        requires_verification=True,
                        verification_type="challenge",
                    )
                    self._show_verification_notification(is_desktop=True)
                    raise
            else:
                logger.error("Login failed: %s", e)
                raise

        if fresh_state:
            cookie_json = json.dumps(fresh_state)
            await self.client.sync_cookies(self.linkedin_profile_id, cookie_json)

        # Discover the real LinkedIn public identifier post-login and report it.
        discovered_username: Optional[str] = None
        try:
            from linkedin_cli.setup.self_profile import discover_self_profile
            self_profile = await self._run_on_pw_thread(lambda: discover_self_profile(session))
            discovered_username = self_profile.get("public_identifier")
            if discovered_username:
                logger.info("Discovered LinkedIn username: %s", discovered_username)
        except Exception as e:
            logger.warning("Could not discover LinkedIn username: %s", e)

        await self.client.report_session_state(
            linkedin_profile_id=self.linkedin_profile_id,
            is_logged_in=True,
            linkedin_username=discovered_username,
        )
        logger.info("Logged in to LinkedIn")

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
            except SessionExpiredError:
                logger.error("Session expired (refresh token invalid) — stopping daemon. Please re-login.")
                await self.stop()
                return
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
                    logger.info("Outside active hours — sleeping 60s")
                    await asyncio.sleep(60)
                    continue

                task = await self.client.claim_task(self.linkedin_profile_id)

                if not task:
                    logger.debug("No tasks ready — polling again in %ds", self.config.poll_interval_seconds)
                    await asyncio.sleep(self.config.poll_interval_seconds)
                    continue

                logger.info("Executing: %s (%s)", task["task_type"], task["task_id"])
                start = datetime.now(tz.utc)

                try:
                    result = await self._run_on_pw_thread(lambda t=task: self._execute_task(t))

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
                    # Write a failed ActionLog entry so the UI activity feed shows errors
                    self._log_task_failure(task, str(e))

                    if "authentication" in str(e).lower() or "401" in str(e):
                        await self.client.report_session_state(
                            linkedin_profile_id=self.linkedin_profile_id,
                            is_logged_in=False,
                        )
                        # Trigger token refresh if callback provided
                        if self.on_token_refresh and self.client._token != self.token:
                            self.on_token_refresh(self.client._token)

            except SessionExpiredError:
                logger.error("Session expired (refresh token invalid) — stopping daemon. Please re-login.")
                await self.stop()
                return
            except Exception as e:
                logger.error("Task loop error: %s", e)
                await asyncio.sleep(30)

    def _log_task_failure(self, task: dict, error: str) -> None:
        """Write a failed ActionLog row so the UI activity feed shows the error."""
        try:
            from openoutreach.linkedin.models import ActionLog
            campaign_id = task.get("payload", {}).get("campaign_id", "")
            log = ActionLog(
                linkedin_profile_id=self.linkedin_profile_id,
                campaign_id=campaign_id,
                action_type=task.get("task_type", ""),
                status="failed",
                error_message=error,
                details={"task_id": task.get("task_id", "")},
            )
            log.save()
        except Exception as e:
            logger.debug("Failed to write ActionLog for task failure: %s", e)

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
            logger.info("Skipping task — campaign %s is not active (status=%s)",
                        campaign_id, campaign.status if campaign else "not found")
            return None

        # Verify session is initialized
        if not self.session:
            raise RuntimeError("Session not initialized")

        # Set campaign on session (required by all handlers)
        self.session.campaign = campaign

        # Set user and user_id on session (required by task handlers and LLM calls)
        from openoutreach.mongodb.models_user import User
        if campaign.user_id:
            self.session.user_id = campaign.user_id
            self.session.user = User.get(campaign.user_id)
            self.session.linkedin_profile.user_id = campaign.user_id

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

        # Snapshot cookies here — we're already on the Playwright thread so
        # storage_state() won't raise the greenlet cross-thread error.
        try:
            self._pending_cookie_state = self.session.context.storage_state()
        except Exception as e:
            logger.debug("Cookie snapshot failed: %s", e)

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
        """Periodically refresh config and reconcile tasks."""
        while self.running:
            await asyncio.sleep(300)
            try:
                self.config = await self.client.get_config(self.linkedin_profile_id)
            except Exception as e:
                logger.warning("Config refresh failed: %s", e)
            try:
                await self.client.reconcile(self.linkedin_profile_id)
            except Exception as e:
                logger.warning("Reconcile failed: %s", e)

    async def _sync_cookies(self):
        """Sync cookies to backend.

        storage_state() is a Playwright sync call that must run on the same
        greenlet/thread where the browser was created.  _execute_task() already
        runs there (via asyncio.to_thread), so it snapshots the state into
        self._pending_cookie_state at the end of each task.  This coroutine just
        ships that snapshot over HTTP — no thread crossing required.
        """
        state = self._pending_cookie_state
        if not state:
            return
        self._pending_cookie_state = None
        try:
            cookie_json = json.dumps(state)
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

        if (now.weekday() + 1) not in self.config.active_days:
            logger.info("Outside active days (today=%d, active=%s)", now.weekday() + 1, self.config.active_days)
            return False

        in_hours = self.config.active_start_hour <= now.hour < self.config.active_end_hour
        if not in_hours:
            logger.info("Outside active hours (%02d:xx, window=%d-%d %s)",
                        now.hour, self.config.active_start_hour, self.config.active_end_hour, self.config.active_timezone)
        return in_hours

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
                    trial_end = datetime.fromisoformat(status.trial_ends_at)
                    if trial_end.tzinfo is None:
                        trial_end = trial_end.replace(tzinfo=tz.utc)
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
                # Escape double quotes for PowerShell string literals
                title_ps = title.replace('"', '`"')
                body_ps = body.replace('"', '`"')
                ps_lines = [
                    "[Windows.UI.Notifications.ToastNotificationManager, "
                    "Windows.UI.Notifications] | Out-Null",
                    "[Windows.Data.Xml.Dom.XmlDocument] | Out-Null",
                    "$t = [Windows.UI.Notifications.ToastNotificationManager]"
                    "::GetTemplateContent(0)",
                    # $xml is a .NET XmlDocument (editable); $x is the WinRT type
                    # required by ToastNotification. Edit $xml first, then reload
                    # into $x — do NOT reassign $xml before loading into $x.
                    "$xml = [xml]$t.GetXml()",
                    f'$xml.toast.visual.binding.text[0].InnerText = "{title_ps}"',
                    f'$xml.toast.visual.binding.text[1].InnerText = "{body_ps}"',
                    "$x = [Windows.Data.Xml.Dom.XmlDocument]::new()",
                    "$x.LoadXml($xml.OuterXml)",
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

    def _get_profile_data_dir(self) -> Path:
        """Return a stable per-LinkedIn-profile browser data directory.

        A persistent user data dir means Chrome reuses the same device fingerprint,
        localStorage, and cookies across daemon restarts — LinkedIn sees the same
        device every time, preventing "Remember me on new device" emails.
        """
        profile_dir = Path.home() / ".lengrowth" / "browser_profiles" / str(self.linkedin_profile_id)
        profile_dir.mkdir(parents=True, exist_ok=True)
        return profile_dir

    def _launch_browser_with_channel(
        self,
        storage_state,
        channel: str,
        proxy_server: Optional[str] = None,
        proxy_username: Optional[str] = None,
        proxy_password: Optional[str] = None,
        headless: bool = False,
        is_new_profile: bool = False,
    ):
        """Launch browser using a persistent context (stable user data dir per profile).

        Uses the user's installed browser (chrome/msedge/webkit) via channel.
        The persistent profile dir gives Chrome a stable device identity so
        LinkedIn stops sending "Remember me on a new device" emails on every restart.
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

        profile_dir = self._get_profile_data_dir()
        user_data_dir = str(profile_dir)

        # Remove stale Chrome singleton lock files left behind by a prior crash.
        # When these exist Chrome detects "another instance is running" and exits
        # immediately with code 0, causing Playwright's TargetClosedError.
        for lock_name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
            lock_path = profile_dir / lock_name
            try:
                if lock_path.exists() or lock_path.is_symlink():
                    lock_path.unlink()
                    logger.info("Removed stale Chrome lock: %s", lock_path)
            except OSError:
                pass

        logger.debug("Launching Playwright with channel=%s, persistent profile=%s (new=%s)",
                     channel, user_data_dir, is_new_profile)
        playwright = sync_playwright().start()

        # Build launch options
        context_options: dict = {
            "headless": headless,
            "slow_mo": BROWSER_SLOW_MO,
        }

        # Seed storage_state only on the very first launch so we don't overwrite
        # a fresher Chrome-native session that already lives in the profile dir.
        if storage_state and is_new_profile:
            context_options["storage_state"] = storage_state

        # Priority: per-profile proxy > environment proxy > no proxy
        if proxy_server:
            proxy_config: dict = {"server": proxy_server}
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

        # webkit (Safari on macOS) doesn't support launch_persistent_context —
        # fall back to an ephemeral context seeded with storage_state instead.
        if channel == "webkit":
            browser = playwright.webkit.launch(headless=headless, slow_mo=BROWSER_SLOW_MO)
            ctx_opts = {k: v for k, v in context_options.items()
                        if k not in ("headless", "slow_mo")}
            if storage_state:
                ctx_opts["storage_state"] = storage_state
            context = browser.new_context(**ctx_opts)
            context.set_default_timeout(BROWSER_DEFAULT_TIMEOUT_MS)
            context.set_default_navigation_timeout(BROWSER_DEFAULT_TIMEOUT_MS)
            context.route("**/*", lambda route: (
                route.abort() if route.request.resource_type in ["image", "media", "font", "stylesheet"]
                and not any(domain in route.request.url for domain in ["linkedin.com", "licdn.com"])
                else route.continue_()
            ))
            Stealth().apply_stealth_sync(context)
            page = context.new_page()
            return page, context, browser, playwright

        # Chrome and Edge support launch_persistent_context — same user data dir
        # across restarts gives a stable device fingerprint, stopping new-device emails.
        if channel == "msedge":
            context = playwright.chromium.launch_persistent_context(
                user_data_dir, channel="msedge", **context_options
            )
        else:  # chrome
            context = playwright.chromium.launch_persistent_context(
                user_data_dir, channel="chrome", **context_options
            )

        context.set_default_timeout(BROWSER_DEFAULT_TIMEOUT_MS)
        context.set_default_navigation_timeout(BROWSER_DEFAULT_TIMEOUT_MS)

        # Block resource-heavy content to reduce bandwidth
        context.route("**/*", lambda route: (
            route.abort() if route.request.resource_type in ["image", "media", "font", "stylesheet"]
            and not any(domain in route.request.url for domain in ["linkedin.com", "licdn.com"])
            else route.continue_()
        ))

        Stealth().apply_stealth_sync(context)
        # Persistent context may already have pages open; reuse the first one
        page = context.pages[0] if context.pages else context.new_page()
        # No separate browser object with persistent context — close via context
        return page, context, None, playwright


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
