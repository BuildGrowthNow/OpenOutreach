"""Strict v2-only HTTP client shipped in the untrusted desktop artifact."""

from __future__ import annotations

import json
import logging
import platform
import secrets
import time
from collections.abc import Callable
from typing import Any, Optional
from urllib.parse import urlencode

import httpx

from openoutreach.desktop.__version__ import __version__
from openoutreach.desktop.proof import canonical_request, token_id_without_verification

logger = logging.getLogger(__name__)


class SessionExpiredError(Exception):
    """The device refresh family is expired or revoked."""


class DesktopRemoteClient:
    """Only expose enrollment, v2 leases, and typed event operations."""

    def __init__(
        self,
        api_url: str,
        token: str,
        device_id: str,
        refresh_token: Optional[str] = None,
        on_token_refresh: Optional[Callable[[str], None]] = None,
        device_signer: Optional[Callable[[bytes], str]] = None,
        on_credentials_rotated: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.device_id = device_id
        self._token = token
        self._refresh_token = refresh_token
        self._on_token_refresh = on_token_refresh
        self._device_signer = device_signer
        self._on_credentials_rotated = on_credentials_rotated
        self._client = httpx.AsyncClient(
            base_url=self.api_url,
            headers={
                "Authorization": f"Bearer {token}",
                "X-Daemon-Version": __version__,
            },
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def get_compatibility(self) -> dict[str, Any]:
        return (await self._request(
            "GET", "/api/daemon/v2/compatibility", params={"version": __version__}
        )).json()

    async def enroll_device(self, code: str, public_key: str) -> dict[str, Any]:
        response = await self._client.post(
            "/api/daemon/v2/devices/enroll",
            json={
                "code": code,
                "public_key": public_key,
                "version": __version__,
                "platform": platform.system().lower().replace("windows", "win32"),
                "capabilities": ["device-auth", "task-leases", "typed-events"],
            },
        )
        response.raise_for_status()
        return response.json()

    async def exchange_device_token(
        self, device_id: str, refresh_token: str, sign: Callable[[bytes], str]
    ) -> dict[str, Any]:
        timestamp = int(time.time())
        nonce = secrets.token_urlsafe(24)
        body = json.dumps(
            {"device_id": device_id, "refresh_token": refresh_token},
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        canonical = canonical_request(
            "POST", "/api/daemon/v2/tokens/exchange", "", body,
            timestamp, nonce, device_id,
        )
        response = await self._client.post(
            "/api/daemon/v2/tokens/exchange",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Daemon-Timestamp": str(timestamp),
                "X-Daemon-Nonce": nonce,
                "X-Daemon-Signature": sign(canonical),
            },
        )
        response.raise_for_status()
        data = response.json()
        self._set_credentials(data["access_token"], data["refresh_token"])
        if self._on_credentials_rotated:
            self._on_credentials_rotated(device_id, data["refresh_token"])
        return data

    async def refresh_device_token(self) -> Optional[str]:
        if not self._refresh_token or not self._device_signer:
            return None
        try:
            data = await self.exchange_device_token(
                self.device_id, self._refresh_token, self._device_signer
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {401, 404}:
                raise SessionExpiredError("Device enrollment must be renewed") from exc
            raise
        if self._on_token_refresh:
            self._on_token_refresh(data["access_token"])
        return data["access_token"]

    async def claim_task_v2(
        self, profile_id: str, channel: str, task_types: list[str] | None = None
    ) -> Optional[dict[str, Any]]:
        response = await self._request(
            "POST", "/api/daemon/v2/tasks/claim",
            json={"profile_id": profile_id, "channel": channel,
                  "supported_task_types": task_types or []},
        )
        data = response.json()
        return data if data else None

    async def renew_task_v2(self, task_id: str, lease_id: str) -> dict[str, Any]:
        return (await self._request(
            "POST", f"/api/daemon/v2/tasks/{task_id}/renew",
            json={"lease_id": lease_id},
        )).json()

    async def complete_task_v2(
        self, task_id: str, lease_id: str, idempotency_key: str, result: dict[str, Any]
    ) -> dict[str, Any]:
        return (await self._request(
            "POST", f"/api/daemon/v2/tasks/{task_id}/complete",
            json={"lease_id": lease_id, "idempotency_key": idempotency_key,
                  "result": result},
        )).json()

    async def fail_task_v2(
        self, task_id: str, lease_id: str, category: str, error: str = ""
    ) -> dict[str, Any]:
        return (await self._request(
            "POST", f"/api/daemon/v2/tasks/{task_id}/fail",
            json={"lease_id": lease_id, "category": category,
                  "error": error[:500]},
        )).json()

    async def ingest_events_v2(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        return (await self._request(
            "POST", "/api/daemon/v2/events/batch", json={"events": events}
        )).json()

    async def post_typed_observation(
        self, channel: str, profile_id: str, kind: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return (await self._request(
            "POST", f"/api/daemon/v2/{channel}/{profile_id}/{kind}", json=payload
        )).json()

    async def execute_email(
        self, profile_id: str, task_id: str, lease_id: str,
        idempotency_key: str, operation: str, mailbox_grant: dict[str, Any],
        *, recipient: str = "", subject: str = "", body: str = "", cursor: str = "",
    ) -> dict[str, Any]:
        """Run a backend email operation without transferring mailbox credentials."""
        return (await self._request(
            "POST", f"/api/daemon/v2/email/{profile_id}/execute",
            json={"task_id": task_id, "lease_id": lease_id,
                  "idempotency_key": idempotency_key, "operation": operation,
                  "mailbox_grant": mailbox_grant, "recipient": recipient,
                  "subject": subject, "body": body, "cursor": cursor},
        )).json()

    async def get_configuration(
        self, profile_id: str, channel: str = "linkedin", etag: str | None = None
    ) -> tuple[int, dict[str, Any] | None, str | None]:
        headers = {"If-None-Match": etag} if etag else {}
        response = await self._request(
            "GET", "/api/daemon/v2/configuration",
            params={"profile_id": profile_id, "channel": channel},
            headers=headers,
        )
        return response.status_code, (None if response.status_code == 304 else response.json()), response.headers.get("ETag")

    def _set_credentials(self, access_token: str, refresh_token: str) -> None:
        self._token = access_token
        self._refresh_token = refresh_token
        self._client.headers["Authorization"] = f"Bearer {access_token}"

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        response = await self._send(method, path, **kwargs)
        if response.status_code == 401 and self._refresh_token and self._device_signer:
            await self.refresh_device_token()
            response = await self._send(method, path, **kwargs)
        response.raise_for_status()
        return response

    async def _send(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = {**kwargs.pop("headers", {})}
        # Compatibility and enrollment are intentionally public/unauthenticated.
        # Every request made after token exchange is proof-bound.
        if self._token and self._device_signer:
            headers.update(self._request_proof(method, path, kwargs))
        return await self._client.request(method, path, headers=headers, **kwargs)

    def _request_proof(self, method: str, path: str, kwargs: dict[str, Any]) -> dict[str, str]:
        timestamp = int(time.time())
        nonce = secrets.token_urlsafe(24)
        body_value = kwargs.get("json")
        body = json.dumps(body_value, separators=(",", ":"), ensure_ascii=False).encode() if body_value is not None else b""
        query = urlencode(sorted((str(key), str(value)) for key, value in (kwargs.get("params") or {}).items()))
        token_id = token_id_without_verification(self._token)
        canonical = canonical_request(method, path, query, body, timestamp, nonce, token_id)
        return {
            "X-Daemon-Timestamp": str(timestamp),
            "X-Daemon-Nonce": nonce,
            "X-Daemon-Signature": self._device_signer(canonical) if self._device_signer else "",
        }
