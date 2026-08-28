"""Local email adapter using a task-bound mailbox provider.

The provider is intentionally injected.  Production supplies a short-lived
desktop grant; tests can supply a deterministic fake.  No mailbox password,
cookie, or server credential is part of this adapter's API.
"""
from __future__ import annotations

import hashlib
import time
from typing import Any


class UnsupportedEmailAction(RuntimeError):
    pass


class EmailAdapter:
    SUPPORTED_TASKS = frozenset({"email_follow_up", "email_send", "email_reply_scan"})

    def __init__(self, provider: Any) -> None:
        self.provider = provider

    def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        task_type = str(task.get("task_type", ""))
        snapshot = task.get("snapshot") or {}
        if task_type not in self.SUPPORTED_TASKS:
            raise UnsupportedEmailAction(f"Unsupported email task: {task_type}")
        grant = snapshot.get("mailbox_grant")
        if not isinstance(grant, dict) or not grant.get("task_id") or not grant.get("mailbox_id"):
            raise UnsupportedEmailAction("Email task requires a task-bound mailbox grant")
        if task.get("task_id") and str(grant["task_id"]) != str(task["task_id"]):
            raise UnsupportedEmailAction("Mailbox grant is bound to another task")
        if task_type == "email_reply_scan":
            result = self.provider.scan_replies(grant, str(snapshot.get("cursor", "")))
            return {"outcome": "observed", "replies": list(result)[:100], "observed_at": int(time.time())}
        recipient = str(snapshot.get("recipient", "")).strip()
        subject = str(snapshot.get("subject", "")).strip()
        body = str(snapshot.get("body", ""))
        if not recipient or not subject or not body:
            raise UnsupportedEmailAction("Email send requires recipient, subject, and body")
        effect_key = str(snapshot.get("effect_key") or hashlib.sha256(
            f"{grant['task_id']}:{recipient}:{subject}:{body}".encode()).hexdigest())
        result = self.provider.send(grant, recipient, subject, body, effect_key)
        outcome = "already_applied" if result in ("duplicate", "already_sent") else ("applied" if result else "rejected")
        return {"outcome": outcome, "target_key": recipient, "effect_key": effect_key,
                "observed_at": int(time.time())}
