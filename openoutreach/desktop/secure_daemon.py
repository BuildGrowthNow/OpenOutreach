"""API-only desktop daemon entry point.

This module intentionally has no MongoDB, server crypto, provider, or domain
model imports. Browser adapters will be attached to the v2 lease client as
their contracts land.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections import deque
from typing import Awaitable, Callable, Optional

from openoutreach.desktop.remote_client import DesktopRemoteClient
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
        execute_task: Optional[Callable[[dict], Awaitable[dict] | dict]] = None,
        on_credentials_rotated: Optional[Callable[[str, str], None]] = None,
        channel_executors: Optional[dict[str, Callable[[dict], Awaitable[dict] | dict]]] = None,
        channel_profile_ids: Optional[dict[str, str | list[str]]] = None,
        profile_executors: Optional[dict[tuple[str, str], Callable[[dict], Awaitable[dict] | dict]]] = None,
    ) -> None:
        self.identity = identity or DeviceIdentity.load_or_create()
        self.client = DesktopRemoteClient(
            api_url, token, self.identity.device_id or "secure-v2",
            refresh_token, on_token_refresh, self.identity.sign,
            on_credentials_rotated,
        )
        self.linkedin_profile_id = linkedin_profile_id
        # A channel profile is an authorization binding, not a fallback.  In
        # particular, WhatsApp historically reused the LinkedIn field in
        # server task documents, so the desktop must never infer its profile
        # from the LinkedIn profile passed to this coordinator.
        self.channel_profile_ids = {
            "linkedin": linkedin_profile_id,
            **{
                channel: (values[0] if isinstance(values, list) and values else values)
                for channel, values in (channel_profile_ids or {}).items()
                if values
            },
        }
        self.channel_profile_bindings: dict[str, list[str]] = {
            "linkedin": [linkedin_profile_id] if linkedin_profile_id else [],
            **{
                channel: ([str(value) for value in values] if isinstance(values, list)
                          else [str(values)])
                for channel, values in (channel_profile_ids or {}).items()
                if values
            },
        }
        self.on_started = on_started
        self.execute_task = execute_task
        self.channel_executors = channel_executors or ({"linkedin": execute_task} if execute_task else {})
        self.profile_executors = profile_executors or {}
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
        server_bindings = exchanged.get("channel_profile_ids")
        if isinstance(server_bindings, dict):
            self.channel_profile_bindings = {
                str(channel): [str(value) for value in values]
                for channel, values in server_bindings.items()
                if isinstance(values, list) and values
            }
            for channel, values in self.channel_profile_bindings.items():
                self.channel_profile_ids[channel] = values[0]
        self.running = True
        if self.on_started:
            self.on_started()
        # The browser executor is deliberately injected. This coordinator never
        # imports domain models or persists channel state locally.
        if self.channel_executors:
            while not self._stop.is_set():
                await self._flush_offline_completions()
                claimed = False
                for channel, executor in self.channel_executors.items():
                    profile_ids = self.channel_profile_bindings.get(channel, [])
                    if not profile_ids:
                        logger.warning("Skipping channel %s: no bound profile configured", channel)
                        continue
                    for profile_id in profile_ids:
                        executor_for_profile = self.profile_executors.get(
                            (channel, profile_id), self.channel_executors.get(channel)
                        )
                        if executor_for_profile is None:
                            logger.warning("Skipping %s profile %s: no executor configured", channel, profile_id)
                            continue
                        task = await self.client.claim_task_v2(profile_id, channel)
                        if task:
                            claimed = True
                            await self._execute(task, executor_for_profile)
                            break
                    if claimed:
                        break
                if not claimed:
                    try:
                        await asyncio.wait_for(self._stop.wait(), timeout=5)
                    except asyncio.TimeoutError:
                        pass

    async def stop(self) -> None:
        self._stop.set()
        self.running = False
        closed: set[int] = set()
        for executor in (*self.channel_executors.values(), *self.profile_executors.values()):
            close = getattr(executor, "__self__", None)
            if close is not None and id(close) not in closed and hasattr(close, "close"):
                closed.add(id(close))
                await asyncio.get_running_loop().run_in_executor(None, close.close)
        await self.client.close()

    async def _execute(self, task: dict, executor: Callable[[dict], Awaitable[dict] | dict]) -> None:
        renewal_stop = asyncio.Event()
        renewal = asyncio.create_task(self._renew_lease(task, renewal_stop))
        try:
            # Synchronous adapters (WhatsApp and the email bridge) may make
            # blocking provider calls. Keep them off the lease/event loop;
            # async browser adapters remain directly awaitable.
            if inspect.iscoroutinefunction(executor):
                result = executor(task)
            else:
                result = await asyncio.get_running_loop().run_in_executor(
                    None, executor, task
                )
            if inspect.isawaitable(result):
                result = await result
            if not isinstance(result, dict):
                raise SecureDaemonError("Channel adapter returned an invalid receipt")
            await self._publish_typed_event(task, result)
            outcome = str(result.get("outcome", "")).lower()
            if outcome in {"applied", "already_applied", "observed"}:
                completion = (task["task_id"], task["lease_id"], task.get("idempotency_key", task["lease_id"]), result)
                try:
                    await self.client.complete_task_v2(*completion)
                except Exception:
                    if len(self._offline_completions) == self._offline_completions.maxlen:
                        self._offline_completions.popleft()
                    self._offline_completions.append(completion)
            else:
                category = self._failure_category(outcome)
                await self.client.fail_task_v2(
                    task["task_id"], task["lease_id"], category,
                    f"local adapter outcome: {outcome or 'rejected'}",
                )
        except Exception as exc:
            logger.warning("Secure daemon task failed: %s", type(exc).__name__)
            try:
                await self.client.fail_task_v2(task["task_id"], task["lease_id"], "retryable", "local execution failed")
            except Exception:
                logger.warning("Unable to report local task failure")
        finally:
            renewal_stop.set()
            await renewal

    @staticmethod
    def _failure_category(outcome: str) -> str:
        """Map bounded adapter outcomes to the backend retry policy."""
        if outcome in {"rate_limited"}:
            return "rate_limited"
        if outcome in {"challenge", "logged_out"}:
            return "auth"
        if outcome in {"timeout", "reconnecting", "retryable"}:
            return "retryable"
        return "permanent"

    async def _renew_lease(self, task: dict, stop: asyncio.Event) -> None:
        """Keep a long-running local browser action owned by this device."""
        while True:
            try:
                try:
                    await asyncio.wait_for(stop.wait(), timeout=120)
                    return
                except asyncio.TimeoutError:
                    pass
                await self.client.renew_task_v2(task["task_id"], task["lease_id"])
            except asyncio.CancelledError:
                return
            except Exception:
                logger.warning("Task lease renewal failed")
                return

    async def _publish_typed_event(self, task: dict, result: dict) -> None:
        """Persist only adapter-produced typed observations/receipts."""
        snapshot = task.get("snapshot") or {}
        profile_id = str(snapshot.get("profile_id") or self.linkedin_profile_id)
        channel = str(task.get("channel") or "linkedin")
        if channel == "linkedin":
            if isinstance(result.get("receipt"), dict):
                await self.client.post_typed_observation("linkedin", profile_id, "receipts", result["receipt"])
            if isinstance(result.get("observation"), dict):
                await self.client.post_typed_observation("linkedin", profile_id, "observations", result["observation"])
        elif channel == "whatsapp":
            if isinstance(result.get("sync"), dict):
                await self.client.post_typed_observation("whatsapp", profile_id, "sync", result["sync"])
            if isinstance(result.get("receipt"), dict):
                await self.client.post_typed_observation("whatsapp", profile_id, "receipts", result["receipt"])
        elif channel == "email" and isinstance(result.get("receipt"), dict):
            await self.client.post_typed_observation("email", profile_id, "receipts", result["receipt"])

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
        return data
