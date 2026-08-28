"""HTTP client for daemon-to-backend communication.

Desktop daemon uses this to claim tasks, report results, sync cookies,
and report session state to the centralized backend.
"""

from __future__ import annotations

import logging
import platform
from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional

import httpx
import inspect
import json
import secrets
import time
from urllib.parse import urlencode
from openoutreach.api_v2.daemon_auth import canonical_request, token_id_without_verification
from openoutreach.desktop.__version__ import __version__

logger = logging.getLogger(__name__)


def _status_code(response) -> int:
    """Read status safely from real httpx responses and lightweight test doubles."""
    value = getattr(response, "status_code", 200)
    return value if isinstance(value, int) else 200


def _request_for(response, method: str, url: str) -> httpx.Request:
    try:
        return response.request
    except (AttributeError, RuntimeError):
        return httpx.Request(method, url)


class SessionExpiredError(Exception):
    """Raised when the refresh token has expired and re-login is required."""


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


@dataclass
class SubscriptionStatus:
    """Subscription status for daemon operation."""

    is_active: bool
    plan: str
    subscription_status: str  # active, trialing, canceled, expired, past_due
    user_status: str  # active, blocked
    trial_ends_at: Optional[str] = None
    current_period_end: Optional[str] = None
    block_reason: Optional[str] = None


class RemoteClient:
    """HTTP client for desktop daemon to communicate with backend."""

    def __init__(
        self,
        api_url: str,
        token: str,
        daemon_id: str,
        refresh_token: Optional[str] = None,
        on_token_refresh: Optional[Callable[[str], None]] = None,
        secure_v2: bool = False,
        device_signer: Optional[Callable[[bytes], str]] = None,
    ):
        self.api_url = api_url.rstrip("/")
        self.daemon_id = daemon_id
        self._token = token
        self._refresh_token = refresh_token
        self._on_token_refresh = on_token_refresh
        self._secure_v2 = secure_v2
        self._device_signer = device_signer
        self._client = httpx.AsyncClient(
            base_url=self.api_url,
            headers={
                "Authorization": f"Bearer {token}",
                "X-Daemon-Version": __version__,
            },
            timeout=30.0,
        )

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

    async def get_compatibility(self) -> dict:
        """Read the safe v2 compatibility document; no credentials are returned."""
        response = await self._request_with_retry("GET", "/api/daemon/v2/compatibility")
        return response.json()

    async def enroll_device(self, code: str, public_key: str) -> dict:
        """Redeem a human-approved one-time enrollment code."""
        response = await self._client.post("/api/daemon/v2/devices/enroll", json={
            "code": code, "public_key": public_key, "version": __version__,
            "platform": platform.system().lower().replace("windows", "win32"),
            "capabilities": ["task-leases", "typed-events"],
        })
        response.raise_for_status()
        return response.json()

    async def exchange_device_token(self, device_id: str, refresh_token: str, sign) -> dict:
        timestamp = int(time.time())
        nonce = secrets.token_urlsafe(24)
        body = json.dumps({"device_id": device_id, "refresh_token": refresh_token}, separators=(",", ":"), sort_keys=True).encode()
        canonical = canonical_request("POST", "/api/daemon/v2/tokens/exchange", "", body, timestamp, nonce, device_id)
        response = await self._client.post("/api/daemon/v2/tokens/exchange", content=body, headers={
            "Content-Type": "application/json", "X-Daemon-Timestamp": str(timestamp),
            "X-Daemon-Nonce": nonce, "X-Daemon-Signature": sign(canonical),
        })
        response.raise_for_status()
        data = response.json()
        self._refresh_token = data["refresh_token"]
        self._token = data["access_token"]
        self._client.headers["Authorization"] = f"Bearer {self._token}"
        return data

    async def refresh_device_token(self, device_id: str) -> Optional[str]:
        if not self._refresh_token or not self._device_signer:
            return None
        data = await self.exchange_device_token(device_id, self._refresh_token, self._device_signer)
        if self._on_token_refresh:
            self._on_token_refresh(data["access_token"])
        return data["access_token"]

    async def claim_task_v2(self, profile_id: str, channel: str, task_types: list[str] | None = None) -> Optional[dict]:
        response = await self._request_with_retry("POST", "/api/daemon/v2/tasks/claim", json={
            "profile_id": profile_id, "channel": channel, "supported_task_types": task_types or [],
        })
        data = response.json()
        return data if data else None

    async def renew_task_v2(self, task_id: str, lease_id: str) -> dict:
        response = await self._request_with_retry("POST", f"/api/daemon/v2/tasks/{task_id}/renew", json={"lease_id": lease_id})
        return response.json()

    async def complete_task_v2(self, task_id: str, lease_id: str, idempotency_key: str, result: dict) -> dict:
        response = await self._request_with_retry("POST", f"/api/daemon/v2/tasks/{task_id}/complete", json={"lease_id": lease_id, "idempotency_key": idempotency_key, "result": result})
        return response.json()

    async def fail_task_v2(self, task_id: str, lease_id: str, category: str, error: str = "") -> dict:
        response = await self._request_with_retry("POST", f"/api/daemon/v2/tasks/{task_id}/fail", json={"lease_id": lease_id, "category": category, "error": error[:500]})
        return response.json()

    async def ingest_events_v2(self, events: list[dict]) -> dict:
        response = await self._request_with_retry("POST", "/api/daemon/v2/events/batch", json={"events": events})
        return response.json()

    async def post_typed_observation(self, channel: str, profile_id: str, kind: str, payload: dict) -> dict:
        """Send one validated channel/session observation to the v2 gateway."""
        response = await self._request_with_retry("POST", f"/api/daemon/v2/{channel}/{profile_id}/{kind}", json=payload)
        return response.json()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        await self.close()

    async def heartbeat(
        self,
        linkedin_profile_id: str,
        version: str,
        uptime_seconds: int,
        browser: str,
    ) -> dict:
        """Send daemon heartbeat to backend."""
        response = await self._request_with_retry(
            "POST",
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
        return response.json()

    async def get_config(self, linkedin_profile_id: str) -> DaemonConfig:
        """Fetch daemon configuration from backend."""
        response = await self._request_with_retry(
            "GET",
            "/api/daemon/config",
            params={"linkedin_profile_id": linkedin_profile_id},
        )
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

    async def reconcile(self, linkedin_profile_id: str) -> dict:
        """Ask backend to schedule tasks for all active campaigns.

        Should be called on startup and periodically (every 5 min) to ensure
        the task queue is populated for claiming.
        """
        response = await self._request_with_retry(
            "POST",
            "/api/daemon/reconcile",
            params={"linkedin_profile_id": linkedin_profile_id},
        )
        return response.json()

    async def claim_task(self, linkedin_profile_id: str) -> Optional[dict]:
        """Atomically claim the next available task for this profile.

        Returns:
            Task dict with task_id, task_type, payload, campaign_id if available.
            None if no tasks are ready.
        """
        response = await self._request_with_retry(
            "POST",
            "/api/daemon/tasks/claim",
            params={
                "linkedin_profile_id": linkedin_profile_id,
                "daemon_id": self.daemon_id,
            },
        )
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
        response = await self._request_with_retry(
            "POST",
            "/api/daemon/tasks/result",
            json={
                "task_id": task_id,
                "status": status,
                "result": result,
                "error": error,
                "duration_ms": duration_ms,
            },
        )
        return response.json()

    async def sync_cookies(self, linkedin_profile_id: str, cookie_data: str) -> dict:
        """Sync browser cookies from desktop daemon to backend."""
        response = await self._request_with_retry(
            "POST",
            "/api/daemon/cookies/sync",
            json={
                "linkedin_profile_id": linkedin_profile_id,
                "cookie_data": cookie_data,
            },
        )
        return response.json()

    async def report_session_state(
        self,
        linkedin_profile_id: str,
        is_logged_in: bool,
        requires_verification: bool = False,
        verification_type: Optional[str] = None,
        linkedin_username: Optional[str] = None,
    ) -> dict:
        """Report session state (login status, verification needed) to backend."""
        payload: dict = {
            "linkedin_profile_id": linkedin_profile_id,
            "is_logged_in": is_logged_in,
            "requires_verification": requires_verification,
            "verification_type": verification_type,
        }
        if linkedin_username:
            payload["linkedin_username"] = linkedin_username
        response = await self._request_with_retry(
            "POST",
            "/api/daemon/session/state",
            json=payload,
        )
        return response.json()

    async def get_credentials(self, linkedin_profile_id: str) -> dict:
        """Get LinkedIn credentials for daemon login.

        Returns:
            Dict with email, password, and optional cookie_data.
        """
        response = await self._request_with_retry(
            "GET",
            "/api/daemon/credentials",
            params={"linkedin_profile_id": linkedin_profile_id},
        )
        return response.json()

    async def check_subscription_status(self) -> SubscriptionStatus:
        """Check subscription status for daemon operation.

        Returns:
            SubscriptionStatus object indicating if daemon can run.
        """
        response = await self._request_with_retry(
            "GET",
            "/api/daemon/subscription/status",
        )
        data = response.json()

        return SubscriptionStatus(
            is_active=data["is_active"],
            plan=data["plan"],
            subscription_status=data["subscription_status"],
            user_status=data["user_status"],
            trial_ends_at=data.get("trial_ends_at"),
            current_period_end=data.get("current_period_end"),
            block_reason=data.get("block_reason"),
        )

    async def refresh_access_token(self) -> Optional[str]:
        """Refresh the JWT access token using the refresh token.

        Returns:
            New access token if successful, None otherwise.
        """
        if not self._refresh_token:
            logger.warning("No refresh token available")
            return None

        try:
            response = await self._client.post(
                "/api/auth/refresh/",
                json={"refresh_token": self._refresh_token},
            )
            if _status_code(response) >= 400:
                request = _request_for(response, "POST", "/api/auth/refresh/")
                raise httpx.HTTPStatusError("refresh failed", request=request, response=response)
            data = response.json()
            if inspect.isawaitable(data):
                data = await data
            new_token = data.get("access_token")
            if new_token:
                self._token = new_token
                self._client.headers["Authorization"] = f"Bearer {new_token}"
                logger.info("Access token refreshed successfully")
                # Notify callback (e.g., desktop app to update keychain)
                if self._on_token_refresh:
                    try:
                        self._on_token_refresh(new_token)
                    except Exception as e:
                        logger.warning("Token refresh callback failed: %s", e)
                return new_token
            return None
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise SessionExpiredError("Refresh token expired - re-login required") from e
            logger.error("Token refresh failed: %s", e)
            return None
        except Exception as e:
            logger.error("Token refresh failed: %s", e)
            return None

    async def get_profile_details(self, linkedin_profile_id: str) -> dict:
        """Get LinkedIn profile details from backend.

        Returns:
            Profile dict with all data needed for task execution.
        """
        response = await self._request_with_retry(
            "GET",
            f"/api/daemon/profile/{linkedin_profile_id}",
        )
        return response.json()

    async def get_campaign_details(self, campaign_id: str) -> dict:
        """Get campaign details from backend.

        Returns:
            Campaign dict with all data needed for task execution.
        """
        response = await self._request_with_retry(
            "GET",
            f"/api/daemon/campaign/{campaign_id}",
        )
        return response.json()

    async def _request_with_retry(self, method: str, url: str, **kwargs):
        """Make HTTP request with automatic token refresh on 401."""
        if self._secure_v2 and self._token:
            kwargs["headers"] = {**kwargs.pop("headers", {}), **self._request_proof(method, url, kwargs)}
        try:
            if method == "GET":
                response = await self._client.get(url, **kwargs)
            elif method == "POST":
                response = await self._client.post(url, **kwargs)
            else:
                raise ValueError(f"Unsupported method: {method}")

            if _status_code(response) >= 400:
                request = _request_for(response, method, url)
                raise httpx.HTTPStatusError("request failed", request=request, response=response)
            return response
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401 and self._secure_v2 and self.daemon_id:
                new_token = await self.refresh_device_token(self.daemon_id)
                if new_token:
                    retry_kwargs = {**kwargs, "headers": {**kwargs.get("headers", {}), **self._request_proof(method, url, kwargs)}}
                    retry_response = await self._client.request(method, url, **retry_kwargs)
                    if _status_code(retry_response) < 400:
                        return retry_response
            elif e.response.status_code == 401 and self._refresh_token:
                logger.info("Got 401, attempting token refresh")
                new_token = await self.refresh_access_token()
                if new_token:
                    # Retry the request with new token
                    retry_response = None
                    if method == "GET":
                        retry_response = await self._client.get(url, **kwargs)
                    elif method == "POST":
                        retry_response = await self._client.post(url, **kwargs)
                    if retry_response:
                        if _status_code(retry_response) >= 400:
                            request = _request_for(retry_response, method, url)
                            raise httpx.HTTPStatusError("retry failed", request=request, response=retry_response)
                        return retry_response
            raise

    def _request_proof(self, method: str, url: str, kwargs: dict) -> dict[str, str]:
        timestamp = int(time.time())
        nonce = secrets.token_urlsafe(24)
        body_value = kwargs.get("json")
        body = json.dumps(body_value, separators=(",", ":"), ensure_ascii=False).encode() if body_value is not None else b""
        token_id = token_id_without_verification(self._token)
        query = urlencode(sorted((str(key), str(value)) for key, value in (kwargs.get("params") or {}).items()))
        canonical = canonical_request(method, url.split("?", 1)[0], query, body, timestamp, nonce, token_id)
        return {"X-Daemon-Timestamp": str(timestamp), "X-Daemon-Nonce": nonce,
                "X-Daemon-Signature": self._device_signer(canonical) if self._device_signer else ""}
