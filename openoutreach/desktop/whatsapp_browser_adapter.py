"""Local WhatsApp execution adapter for materialized v2 snapshots.

The adapter accepts a local session object supplied by the desktop runtime;
it never accepts a backend profile/model and never persists QR or credentials.
"""
from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from typing import Any

from openoutreach.api_v2.daemon_channel_contracts import WhatsAppActionReceipt, WhatsAppState


class UnsupportedWhatsAppAction(RuntimeError):
    pass


class WhatsAppBrowserAdapter:
    SUPPORTED_TASKS = frozenset({"whatsapp_follow_up", "whatsapp_message", "whatsapp_sync", "whatsapp_reconnect"})

    def __init__(self, profile_id: str, session: Any) -> None:
        self.profile_id = profile_id
        self.session = session

    def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        task_type = str(task.get("task_type", ""))
        snapshot = task.get("snapshot") or {}
        if task_type not in self.SUPPORTED_TASKS:
            raise UnsupportedWhatsAppAction(f"Unsupported WhatsApp task: {task_type}")
        if str(snapshot.get("profile_id", self.profile_id)) != self.profile_id:
            raise UnsupportedWhatsAppAction("Profile mismatch")
        if task_type == "whatsapp_reconnect":
            reconnect = getattr(self.session, "reconnect", None)
            if not callable(reconnect):
                raise UnsupportedWhatsAppAction("Session does not support bounded reconnect")
            try:
                result = reconnect()
            except Exception as exc:
                return self._receipt(task, "rejected", "session", type(exc).__name__)
            outcome = "applied" if result is not False else "rejected"
            return self._receipt(task, outcome, "session", "reconnect")
        if task_type == "whatsapp_sync":
            try:
                messages = self.session.sync(cursor=str(snapshot.get("cursor", "")), limit=100)
            except Exception as exc:
                return self._receipt(task, "rejected", "sync", type(exc).__name__)
            bounded = self._bounded_messages(messages)
            return {"outcome": "observed", "messages": bounded,
                    "cursor": str(snapshot.get("cursor", "")), "observed_at": int(time.time()),
                    "sync": {"profile_id": self.profile_id,
                              "cursor": str(snapshot.get("cursor", "")),
                              "messages": bounded}}
        phone = str(snapshot.get("target_phone", "")).strip()
        message = str(snapshot.get("message", "")).strip()
        if not phone or not message:
            raise UnsupportedWhatsAppAction("WhatsApp message requires phone and message")
        effect_key = str(snapshot.get("effect_key") or hashlib.sha256(
            f"{self.profile_id}:{phone}:{message}".encode()).hexdigest())
        try:
            result = self.session.send_message(phone, message)
        except Exception as exc:
            return self._receipt(task, self._provider_outcome(exc), phone, "send")
        if result in (True, "sent", "applied"):
            outcome = "applied"
        elif result in ("already_sent", "duplicate"):
            outcome = "already_applied"
        elif result in ("challenge", "qr", "logged_out"):
            outcome = "challenge"
        else:
            outcome = "rejected"
        return self._receipt(task, outcome, phone, "send", effect_key=effect_key)

    @staticmethod
    def _bounded_messages(messages: Any) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in list(messages or [])[:100]:
            if not isinstance(item, dict):
                continue
            bounded = {str(key)[:64]: str(value)[:2000] for key, value in list(item.items())[:12]}
            identity = bounded.get("id") or bounded.get("message_id") or hashlib.sha256(
                repr(sorted(bounded.items())).encode()
            ).hexdigest()
            if identity in seen:
                continue
            seen.add(identity)
            result.append(bounded)
        return result

    @staticmethod
    def _provider_outcome(exc: Exception) -> str:
        name = type(exc).__name__.lower()
        if any(value in name for value in ("challenge", "qr", "login", "auth")):
            return "challenge"
        if any(value in name for value in ("rate", "limit", "thrott")):
            return "rate_limited"
        if "timeout" in name:
            return "timeout"
        return "rejected"

    def _receipt(self, task: dict[str, Any], outcome: str, target: str,
                 state: str, effect_key: str | None = None) -> dict[str, Any]:
        snapshot = task.get("snapshot") or {}
        effect_key = effect_key or str(snapshot.get("effect_key") or hashlib.sha256(
            f"{self.profile_id}:{target}:{task.get('task_type', '')}".encode()
        ).hexdigest())
        receipt = WhatsAppActionReceipt(
            action={"whatsapp_message": "send", "whatsapp_follow_up": "send",
                    "whatsapp_sync": "sync", "whatsapp_reconnect": "reconnect"}.get(
                        str(task.get("task_type")), "send"),
            target_key=target, effect_key=effect_key, outcome=outcome,
            observed_at=datetime.now(timezone.utc),
        )
        return {"outcome": outcome, "target_key": target, "effect_key": effect_key,
                "state": state, "observed_at": int(time.time()),
                "receipt": receipt.model_dump(mode="json")}

    def observe_session(self) -> dict[str, Any]:
        """Return bounded state; QR bytes and browser storage never leave local process."""
        try:
            if bool(self.session.detect_ban()):
                state = "banned"
            elif bool(self.session.is_alive()):
                state = "connected"
            else:
                state = "disconnected"
        except Exception:
            state = "reconnecting"
        observation = WhatsAppState(
            profile_id=self.profile_id, state=state,
            health="healthy" if state == "connected" else "degraded",
            observed_at=datetime.now(timezone.utc),
        )
        return observation.model_dump(mode="json")
