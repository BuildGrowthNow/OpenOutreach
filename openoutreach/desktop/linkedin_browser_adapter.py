"""Local, API-fed LinkedIn browser execution adapter.

This module deliberately owns only browser state and provider UI actions. It
does not import MongoDB models, server credentials, or campaign repositories.
All action inputs come from the v2 lease snapshot and all durable state is
reported by the secure daemon client.
"""

from __future__ import annotations

import asyncio
import logging
import hashlib
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from openoutreach.core.browser_detect import get_preferred_browser

logger = logging.getLogger(__name__)


class UnsupportedBrowserAction(RuntimeError):
    """The v2 snapshot does not describe an action this adapter supports."""


class LinkedInBrowserAdapter:
    """Execute LinkedIn snapshots in a local, profile-bound browser.

    The provider verbs are imported only inside the browser worker.  This
    keeps the API boundary data-only and makes the adapter testable with a
    fake session without ever giving it a server model or credential.
    """

    # Keep the old public constant for clients which used it as a capability
    # probe; the v2 capability set is deliberately broader.
    SUPPORTED_TASKS = frozenset({"connect", "check_pending", "send_manual_message"})
    SUPPORTED_V2_TASKS = frozenset({"connect", "check_pending", "follow_up", "send_manual_message"})

    def __init__(self, profile_id: str, session_factory: Any = None) -> None:
        self.profile_id = profile_id
        self._session_factory = session_factory
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="linkedin-browser")
        self._page: Any = None
        self._context: Any = None
        self._playwright: Any = None

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        task_type = str(task.get("task_type", ""))
        if task_type not in self.SUPPORTED_V2_TASKS:
            raise UnsupportedBrowserAction(f"Unsupported LinkedIn task: {task_type}")
        snapshot = task.get("snapshot") or {}
        if not isinstance(snapshot, dict) or not snapshot.get("target_public_identifier"):
            raise UnsupportedBrowserAction("Task has no materialized target")
        return await asyncio.get_running_loop().run_in_executor(
            self._executor, self._execute_sync, task
        )

    def _execute_sync(self, task: dict[str, Any]) -> dict[str, Any]:
        from linkedin_cli.actions.connect import send_connection_request
        from linkedin_cli.actions.message import send_raw_message
        from linkedin_cli.actions.status import get_connection_status

        self._ensure_browser()
        snapshot = task.get("snapshot") or task.get("payload") or {}
        target = str(snapshot.get("target_public_identifier", "")).strip()
        if not target:
            raise UnsupportedBrowserAction("Task has no target profile")

        profile: dict[str, Any] = {
            "public_identifier": target,
            "urn": str(snapshot.get("target_urn", "")).strip(),
        }
        task_type = str(task["task_type"])
        if task_type == "check_pending":
            state = get_connection_status(self, profile).value
            return {"outcome": "observed", "target_key": target, "state": state}

        if task_type in {"connect", "follow_up"}:
            state = get_connection_status(self, profile).value
            if state in {"connected", "pending"}:
                if task_type == "connect":
                    return self._receipt(task, "already_applied", target, state)
                if state != "connected":
                    return self._receipt(task, "rejected", target, "pending")
            if task_type == "connect":
                try:
                    result = send_connection_request(self, profile)
                except Exception as exc:
                    return self._receipt(task, self._provider_outcome(exc), target, "connect_failed")
                return self._receipt(task, "applied", target, result.value)

        message = str(snapshot.get("message", ""))
        if not message or not profile["urn"]:
            raise UnsupportedBrowserAction("Manual message requires message and target URN")
        try:
            sent = send_raw_message(self, profile, message)
        except Exception as exc:
            return self._receipt(task, self._provider_outcome(exc), target, "message_failed")
        if not sent:
            return self._receipt(task, "rejected", target, "message_failed")
        return self._receipt(task, "applied", target, "sent")

    @staticmethod
    def _provider_outcome(exc: Exception) -> str:
        """Map provider failures to safe, retry-aware receipt outcomes."""
        name = type(exc).__name__.lower()
        if any(term in name for term in ("challenge", "captcha", "verification")):
            return "challenge"
        if any(term in name for term in ("logout", "login", "auth", "session")):
            return "logged_out"
        if any(term in name for term in ("rate", "limit", "thrott")):
            return "rate_limited"
        if any(term in name for term in ("timeout", "timedout")):
            return "timeout"
        if "duplicate" in name or "already" in name:
            return "duplicate"
        return "rejected"

    @staticmethod
    def _receipt(task: dict[str, Any], outcome: str, target: str, state: str) -> dict[str, Any]:
        snapshot = task.get("snapshot") or {}
        effect_key = str(snapshot.get("effect_key") or hashlib.sha256(
            f"{task.get('task_id', '')}:{task.get('task_type', '')}:{target}:{snapshot.get('message', '')}".encode()
        ).hexdigest())
        return {"outcome": outcome, "target_key": target, "state": state,
                "effect_key": effect_key, "observed_at": int(time.time())}

    def _ensure_browser(self) -> None:
        if self._page is not None and not self._page.is_closed():
            return
        browser = get_preferred_browser()
        if browser is None or browser.channel not in {"chrome", "msedge", "webkit"}:
            raise RuntimeError("No supported local browser found")

        from playwright.sync_api import sync_playwright
        from linkedin_cli.conf import BROWSER_DEFAULT_TIMEOUT_MS, BROWSER_SLOW_MO

        self._playwright = sync_playwright().start()
        profile_dir = Path.home() / ".lengrowth" / "browser_profiles" / self.profile_id
        profile_dir.mkdir(parents=True, exist_ok=True)
        if browser.channel == "webkit":
            self._context = self._playwright.webkit.launch(headless=False, slow_mo=BROWSER_SLOW_MO).new_context()
        else:
            self._context = self._playwright.chromium.launch_persistent_context(
                str(profile_dir), channel=browser.channel, headless=False, slow_mo=BROWSER_SLOW_MO
            )
        self._context.set_default_timeout(BROWSER_DEFAULT_TIMEOUT_MS)
        self._context.set_default_navigation_timeout(BROWSER_DEFAULT_TIMEOUT_MS)
        self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
        if "linkedin.com" not in self._page.url:
            self._page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
        if "/login" in self._page.url or "/checkpoint" in self._page.url:
            raise RuntimeError("LinkedIn requires human login or verification in the local browser")

    @property
    def page(self) -> Any:
        return self._page

    def wait(self, min_delay: float = 0.4, max_delay: float = 0.8) -> None:
        # Keep the provider library's session contract without blocking the
        # async coordinator; this method runs on the dedicated browser thread.
        self._page.wait_for_load_state("domcontentloaded")

    def ensure_browser(self) -> None:
        self._ensure_browser()

    def close(self) -> None:
        def _close() -> None:
            try:
                if self._context:
                    self._context.close()
                if self._playwright:
                    self._playwright.stop()
            finally:
                self._page = self._context = self._playwright = None

        self._executor.submit(_close).result(timeout=15)
        self._executor.shutdown(wait=True, cancel_futures=True)
