"""HTTP client for daemon-to-backend communication.

Desktop daemon uses this to claim tasks, report results, sync cookies,
and report session state to the centralized backend.
"""

from __future__ import annotations

import logging
import platform
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class DaemonConfig:
    """Configuration received from backend for daemon operation."""

    velocity: int
    daily_connect_limit: int
    daily_message_limit: int
    cooldown_minutes: int
    enable_active_hours: bool
    active_start_hour: int
    active_end_hour: int
    active_timezone: str
    active_days: list[int]
    poll_interval_seconds: int
    heartbeat_interval_seconds: int


class RemoteClient:
    """HTTP client for desktop daemon to communicate with backend."""

    def __init__(self, api_url: str, token: str, daemon_id: str):
        self.api_url = api_url.rstrip("/")
        self.daemon_id = daemon_id
        self._client = httpx.AsyncClient(
            base_url=self.api_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, _exc_type, _exc_val, _exc_tb):
        await self.close()

    async def heartbeat(
        self,
        linkedin_profile_id: str,
        version: str,
        uptime_seconds: int,
        browser: str,
    ) -> dict:
        """Send daemon heartbeat to backend."""
        response = await self._client.post(
            "/api/daemon/heartbeat",
            json={
                "daemon_id": self.daemon_id,
                "linkedin_profile_id": linkedin_profile_id,
                "version": version,
                "platform": platform.system().lower().replace("windows", "win32"),
                "uptime_seconds": uptime_seconds,
                "browser": browser,
            },
        )
        response.raise_for_status()
        return response.json()

    async def get_config(self, linkedin_profile_id: str) -> DaemonConfig:
        """Fetch daemon configuration from backend."""
        response = await self._client.get(
            "/api/daemon/config",
            params={"linkedin_profile_id": linkedin_profile_id},
        )
        response.raise_for_status()
        data = response.json()

        return DaemonConfig(
            velocity=data["rate_limits"]["velocity"],
            daily_connect_limit=data["rate_limits"]["daily_connect_limit"],
            daily_message_limit=data["rate_limits"]["daily_message_limit"],
            cooldown_minutes=data["rate_limits"]["cooldown_minutes"],
            enable_active_hours=data["active_hours"]["enabled"],
            active_start_hour=data["active_hours"]["start_hour"],
            active_end_hour=data["active_hours"]["end_hour"],
            active_timezone=data["active_hours"]["timezone"],
            active_days=data["active_hours"]["days"],
            poll_interval_seconds=data["poll_interval_seconds"],
            heartbeat_interval_seconds=data["heartbeat_interval_seconds"],
        )

    async def claim_task(self, linkedin_profile_id: str) -> Optional[dict]:
        """Atomically claim the next available task for this profile.

        Returns:
            Task dict with task_id, task_type, payload, campaign_id if available.
            None if no tasks are ready.
        """
        response = await self._client.post(
            "/api/daemon/tasks/claim",
            params={
                "linkedin_profile_id": linkedin_profile_id,
                "daemon_id": self.daemon_id,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data if data.get("task_id") else None

    async def report_result(
        self,
        task_id: str,
        status: str,
        result: Optional[dict] = None,
        error: Optional[str] = None,
        duration_ms: int = 0,
    ) -> dict:
        """Report task completion or failure to backend."""
        response = await self._client.post(
            "/api/daemon/tasks/result",
            json={
                "task_id": task_id,
                "status": status,
                "result": result,
                "error": error,
                "duration_ms": duration_ms,
            },
        )
        response.raise_for_status()
        return response.json()

    async def sync_cookies(self, linkedin_profile_id: str, cookie_data: str) -> dict:
        """Sync browser cookies from desktop daemon to backend."""
        response = await self._client.post(
            "/api/daemon/cookies/sync",
            json={
                "linkedin_profile_id": linkedin_profile_id,
                "cookie_data": cookie_data,
            },
        )
        response.raise_for_status()
        return response.json()

    async def report_session_state(
        self,
        linkedin_profile_id: str,
        is_logged_in: bool,
        requires_verification: bool = False,
        verification_type: Optional[str] = None,
    ) -> dict:
        """Report session state (login status, verification needed) to backend."""
        response = await self._client.post(
            "/api/daemon/session/state",
            json={
                "linkedin_profile_id": linkedin_profile_id,
                "is_logged_in": is_logged_in,
                "requires_verification": requires_verification,
                "verification_type": verification_type,
            },
        )
        response.raise_for_status()
        return response.json()

    async def get_credentials(self, linkedin_profile_id: str) -> dict:
        """Get LinkedIn credentials for daemon login.

        Returns:
            Dict with email, password, and optional cookie_data.
        """
        response = await self._client.get(
            "/api/daemon/credentials",
            params={"linkedin_profile_id": linkedin_profile_id},
        )
        response.raise_for_status()
        return response.json()
