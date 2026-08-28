"""API-only desktop daemon entry point.

This module intentionally has no MongoDB, server crypto, provider, or domain
model imports. Browser adapters will be attached to the v2 lease client as
their contracts land.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import Awaitable, Callable, Optional

from openoutreach.core.remote_client import RemoteClient
from openoutreach.desktop.device_identity import DeviceIdentity

logger = logging.getLogger(__name__)


class SecureDaemonError(Exception):
    """Expected secure-daemon startup failure."""


class BrowserNotFoundError(SecureDaemonError):
    """Retained for the desktop UI's expected error classification."""


class SecureRemoteDaemon:
    """Fail-closed API-only daemon coordinator."""

    def __init__(
        self,
        api_url: str,
        token: str,
        linkedin_profile_id: str,
        refresh_token: Optional[str] = None,
        on_token_refresh: Optional[Callable[[str], None]] = None,
        on_started: Optional[Callable[[], None]] = None,
        identity: Optional[DeviceIdentity] = None,
        execute_task: Optional[Callable[[dict], Awaitable[dict]]] = None,
        on_credentials_rotated: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self.identity = identity or DeviceIdentity.load_or_create()
        self.client = RemoteClient(api_url, token, self.identity.device_id or "secure-v2", refresh_token, on_token_refresh, secure_v2=True, device_signer=self.identity.sign)
        self.linkedin_profile_id = linkedin_profile_id
        self.on_started = on_started
        self.execute_task = execute_task
        self.on_credentials_rotated = on_credentials_rotated
        self.running = False
        self._stop = asyncio.Event()
        self._offline_completions: deque[tuple[str, str, str, dict]] = deque(maxlen=100)

    async def start(self) -> None:
        compatibility = await self.client.get_compatibility()
        if compatibility.get("force_update", False):
            raise SecureDaemonError("Secure desktop update required")
        if not self.identity.device_id or not self.client._refresh_token:
            raise SecureDaemonError("Secure desktop enrollment is required")
        exchanged = await self.client.exchange_device_token(self.identity.device_id, self.client._refresh_token, self.identity.sign)
        if self.on_credentials_rotated:
            self.on_credentials_rotated(self.identity.device_id, exchanged["refresh_token"])
        self.running = True
        if self.on_started:
            self.on_started()
        # The browser executor is deliberately injected. This coordinator never
        # imports domain models or persists channel state locally.
        if self.execute_task:
            while not self._stop.is_set():
                await self._flush_offline_completions()
                task = await self.client.claim_task_v2(self.linkedin_profile_id, "linkedin")
                if task:
                    await self._execute(task)
                else:
                    try:
                        await asyncio.wait_for(self._stop.wait(), timeout=5)
                    except asyncio.TimeoutError:
                        pass

    async def stop(self) -> None:
        self._stop.set()
        self.running = False
        await self.client.close()

    async def _execute(self, task: dict) -> None:
        try:
            result = await self.execute_task(task)
            completion = (task["task_id"], task["lease_id"], task.get("idempotency_key", task["lease_id"]), result)
            try:
                await self.client.complete_task_v2(*completion)
            except Exception:
                if len(self._offline_completions) == self._offline_completions.maxlen:
                    self._offline_completions.popleft()
                self._offline_completions.append(completion)
        except Exception as exc:
            logger.warning("Secure daemon task failed: %s", type(exc).__name__)
            await self.client.fail_task_v2(task["task_id"], task["lease_id"], "retryable", "local execution failed")

    async def _flush_offline_completions(self) -> None:
        while self._offline_completions:
            task_id, lease_id, idempotency_key, result = self._offline_completions[0]
            try:
                await self.client.complete_task_v2(task_id, lease_id, idempotency_key, result)
            except Exception:
                return
            self._offline_completions.popleft()

    async def enroll(self, code: str) -> dict:
        data = await self.client.enroll_device(code, self.identity.public_key_pem.decode("ascii"))
        self.identity.remember_device(data["device_id"])
        self.client._refresh_token = data["refresh_token"]
        exchanged = await self.client.exchange_device_token(data["device_id"], data["refresh_token"], self.identity.sign)
        if self.on_credentials_rotated:
            self.on_credentials_rotated(data["device_id"], exchanged["refresh_token"])
        return data
