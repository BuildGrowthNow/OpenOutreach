"""Local, API-fed LinkedIn browser execution adapter.

This module deliberately owns only browser state and provider UI actions. It
does not import MongoDB models, server credentials, or campaign repositories.
All action inputs come from the v2 lease snapshot and all durable state is
reported by the secure daemon client.
"""

from __future__ import annotations

import asyncio
import logging
import platform
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from openoutreach.core.browser_detect import get_preferred_browser

logger = logging.getLogger(__name__)


class UnsupportedBrowserAction(RuntimeError):
    """The v2 snapshot does not describe an action this adapter supports."""


class LinkedInBrowserAdapter:
    """Execute a narrow, typed LinkedIn action set in a local browser."""

    SUPPORTED_TASKS = frozenset({"connect", "check_pending", "send_manual_message"})

    def __init__(self, profile_id: str) -> None:
        self.profile_id = profile_id
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="linkedin-browser")
        self._page: Any = None
        self._context: Any = None
        self._playwright: Any = None

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        task_type = str(task.get("task_type", ""))
        if task_type not in self.SUPPORTED_TASKS:
            raise UnsupportedBrowserAction(f"Unsupported LinkedIn task: {task_type}")
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

        if task_type == "connect":
            state = get_connection_status(self, profile).value
            if state in {"connected", "pending"}:
                return {"outcome": "already_applied", "target_key": target, "state": state}
            result = send_connection_request(self, profile)
            return {"outcome": "applied", "target_key": target, "state": result.value}

        message = str(snapshot.get("message", ""))
        if not message or not profile["urn"]:
            raise UnsupportedBrowserAction("Manual message requires message and target URN")
        if not send_raw_message(self, profile, message):
            raise RuntimeError("LinkedIn message action failed")
        return {"outcome": "applied", "target_key": target, "state": "sent"}

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

