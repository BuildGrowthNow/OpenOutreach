"""Local email adapter using a task-bound mailbox provider.

The provider is intentionally injected.  Production supplies a short-lived
desktop grant; tests can supply a deterministic fake.  No mailbox password,
cookie, or server credential is part of this adapter's API.
"""
from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from openoutreach.api_v2.daemon_channel_contracts import EmailReceipt, MailboxGrant


class UnsupportedEmailAction(RuntimeError):
    pass


class RemoteMailboxProvider:
    """Bridge email operations to the authenticated daemon API."""

    def __init__(self, submit: Any) -> None:
        self._submit = submit
        self._task: dict[str, Any] = {}

    def set_task(self, task: dict[str, Any]) -> None:
        self._task = task

    def send(self, grant: dict[str, Any], recipient: str, subject: str,
             body: str, effect_key: str) -> Any:
        return self._submit(self._task, "send", grant, recipient, subject, body, effect_key)

    def scan_replies(self, grant: dict[str, Any], cursor: str) -> Any:
        return self._submit(self._task, "reply_scan", grant, "", "", "", "", cursor)


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
        try:
            typed_grant = MailboxGrant.model_validate(grant)
        except ValidationError as exc:
            raise UnsupportedEmailAction("Mailbox grant is invalid or expired") from exc
        if task.get("task_id") and str(grant["task_id"]) != str(task["task_id"]):
            raise UnsupportedEmailAction("Mailbox grant is bound to another task")
        set_task = getattr(self.provider, "set_task", None)
        if callable(set_task):
            set_task(task)
        if task_type == "email_reply_scan":
            if typed_grant.purpose != "reply_scan":
                raise UnsupportedEmailAction("Mailbox grant purpose mismatch")
            try:
                result = self.provider.scan_replies(typed_grant.model_dump(mode="json"), str(snapshot.get("cursor", "")))
            except Exception as exc:
                return self._result_with_receipt(
                    task, typed_grant, "", self._provider_outcome(exc),
                    target=str(typed_grant.mailbox_id),
                )
            replies = self._bounded_replies(
                result.get("replies", []) if isinstance(result, dict) else result
            )
            return {"outcome": "observed", "replies": replies, "observed_at": int(time.time())}
        if typed_grant.purpose != "send":
            raise UnsupportedEmailAction("Mailbox grant purpose mismatch")
        recipient = str(snapshot.get("recipient", "")).strip()
        subject = str(snapshot.get("subject", "")).strip()
        body = str(snapshot.get("body", ""))
        if not recipient or not subject or not body:
            raise UnsupportedEmailAction("Email send requires recipient, subject, and body")
        effect_key = str(snapshot.get("effect_key") or hashlib.sha256(
            f"{grant['task_id']}:{recipient}:{subject}:{body}".encode()).hexdigest())
        try:
            result = self.provider.send(typed_grant.model_dump(mode="json"), recipient, subject, body, effect_key)
        except Exception as exc:
            return self._result_with_receipt(
                task, typed_grant, effect_key, self._provider_outcome(exc), target=recipient,
            )
        provider_status = result.get("status") if isinstance(result, dict) else result
        outcome = "already_applied" if provider_status in ("duplicate", "already_sent") else ("applied" if provider_status in (True, "sent", "applied") else "rejected")
        receipt = EmailReceipt(
            mailbox_id=typed_grant.mailbox_id,
            effect_key=effect_key,
            outcome="sent" if outcome in {"applied", "already_applied"} else "failed",
            observed_at=datetime.now(timezone.utc),
        )
        return {"outcome": outcome, "target_key": recipient, "effect_key": effect_key,
                "observed_at": int(time.time()), "receipt": receipt.model_dump(mode="json")}

    @staticmethod
    def _result_with_receipt(task: dict[str, Any], grant: MailboxGrant,
                             effect_key: str, outcome: str, *, target: str) -> dict[str, Any]:
        """Return a bounded result and a typed failure receipt for retries."""
        snapshot = task.get("snapshot") or {}
        key = effect_key or str(snapshot.get("effect_key") or hashlib.sha256(
            f"{grant.task_id}:{target}:{task.get('task_type', '')}".encode()
        ).hexdigest())
        receipt = EmailReceipt(
            mailbox_id=grant.mailbox_id,
            effect_key=key,
            outcome="failed",
            observed_at=datetime.now(timezone.utc),
        )
        return {"outcome": outcome, "target_key": target, "effect_key": key,
                "observed_at": int(time.time()), "receipt": receipt.model_dump(mode="json")}

    @staticmethod
    def _bounded_replies(result: Any) -> list[dict[str, str]]:
        replies: list[dict[str, str]] = []
        for item in list(result or [])[:100]:
            if not isinstance(item, dict):
                continue
            replies.append({str(key)[:64]: str(value)[:2000] for key, value in list(item.items())[:12]})
        return replies

    @staticmethod
    def _provider_outcome(exc: Exception) -> str:
        name = type(exc).__name__.lower()
        if any(value in name for value in ("auth", "login", "credential", "grant")):
            return "logged_out"
        if any(value in name for value in ("rate", "limit", "thrott")):
            return "rate_limited"
        if "timeout" in name:
            return "timeout"
        return "rejected"
