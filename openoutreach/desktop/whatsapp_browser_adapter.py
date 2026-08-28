"""Local WhatsApp execution adapter for materialized v2 snapshots.

The adapter accepts a local session object supplied by the desktop runtime;
it never accepts a backend profile/model and never persists QR or credentials.
"""
from __future__ import annotations

import hashlib
import time
from typing import Any


class UnsupportedWhatsAppAction(RuntimeError):
    pass


class WhatsAppBrowserAdapter:
    SUPPORTED_TASKS = frozenset({"whatsapp_follow_up", "whatsapp_message", "whatsapp_sync"})

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
        if task_type == "whatsapp_sync":
            messages = self.session.sync(cursor=str(snapshot.get("cursor", "")), limit=100)
            return {"outcome": "observed", "messages": list(messages)[:100],
                    "cursor": str(snapshot.get("cursor", "")), "observed_at": int(time.time())}
        phone = str(snapshot.get("target_phone", "")).strip()
        message = str(snapshot.get("message", "")).strip()
        if not phone or not message:
            raise UnsupportedWhatsAppAction("WhatsApp message requires phone and message")
        effect_key = str(snapshot.get("effect_key") or hashlib.sha256(
            f"{self.profile_id}:{phone}:{message}".encode()).hexdigest())
        result = self.session.send_message(phone, message)
        if result in (True, "sent", "applied"):
            outcome = "applied"
        elif result in ("already_sent", "duplicate"):
            outcome = "already_applied"
        elif result in ("challenge", "qr", "logged_out"):
            outcome = "challenge"
        else:
            outcome = "rejected"
        return {"outcome": outcome, "target_key": phone, "effect_key": effect_key,
                "observed_at": int(time.time())}

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
        return {"profile_id": self.profile_id, "state": state,
                "health": "healthy" if state == "connected" else "degraded",
                "observed_at": int(time.time())}
