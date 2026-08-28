"""Strict, non-secret v2 channel contracts exchanged with desktop adapters."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SessionState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_id: str = Field(min_length=1, max_length=128)
    state: Literal["logged_in", "logged_out", "challenge", "verification", "disconnected"]
    observed_at: datetime
    reason: str = Field(default="", max_length=300)


class LinkedInObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_id: str
    observation: Literal["connection", "pending", "message", "contact"]
    target_key: str = Field(min_length=1, max_length=256)
    observed_at: datetime
    state: str = Field(max_length=80)


class LinkedInActionReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["connect", "pending_check", "follow_up", "manual_send"]
    target_key: str = Field(min_length=1, max_length=256)
    effect_key: str = Field(min_length=1, max_length=256)
    outcome: Literal["applied", "already_applied", "rejected", "challenge", "logged_out", "rate_limited", "timeout", "duplicate"]
    observed_at: datetime


class WhatsAppState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_id: str
    state: Literal["qr", "connected", "disconnected", "banned", "reconnecting"]
    observed_at: datetime
    health: Literal["healthy", "degraded", "unknown"] = "unknown"


class WhatsAppSyncBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_id: str
    cursor: str = Field(default="", max_length=256)
    messages: list[dict[str, str]] = Field(default_factory=list, max_length=100)

    @field_validator("messages")
    @classmethod
    def messages_are_bounded(cls, value: list[dict[str, str]]) -> list[dict[str, str]]:
        if any(len(message) > 12 or any(len(str(k)) > 64 or len(str(v)) > 2000 for k, v in message.items()) for message in value):
            raise ValueError("message entry exceeds contract bounds")
        return value


class EmailReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mailbox_id: str
    effect_key: str = Field(min_length=1, max_length=256)
    outcome: Literal["sent", "delivered", "bounced", "replied", "unsubscribed", "failed"]
    observed_at: datetime


class MailboxGrant(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: str
    mailbox_id: str
    expires_at: datetime
    purpose: Literal["send", "reply_scan"]

    @field_validator("expires_at")
    @classmethod
    def grant_window_is_short(cls, value: datetime) -> datetime:
        now = datetime.now(timezone.utc)
        normalized = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if normalized <= now or normalized > now + timedelta(seconds=60):
            raise ValueError("mailbox grant must expire within 60 seconds")
        return value


class LinkedInTaskSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_id: str = Field(min_length=1, max_length=128)
    target_public_identifier: str = Field(min_length=1, max_length=256)
    target_urn: str = Field(default="", max_length=256)
    message: str = Field(default="", max_length=20000)
    effect_key: str = Field(min_length=1, max_length=256)


class WhatsAppTaskSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_id: str = Field(min_length=1, max_length=128)
    target_phone: str = Field(default="", max_length=32)
    message: str = Field(default="", max_length=20000)
    cursor: str = Field(default="", max_length=256)
    effect_key: str = Field(min_length=1, max_length=256)


class EmailTaskSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_id: str = Field(min_length=1, max_length=128)
    recipient: str = Field(default="", max_length=320)
    subject: str = Field(default="", max_length=998)
    body: str = Field(default="", max_length=20000)
    mailbox_grant: MailboxGrant | None = None
    cursor: str = Field(default="", max_length=256)
    effect_key: str = Field(min_length=1, max_length=256)


class WhatsAppActionReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["send", "sync", "reconnect"]
    target_key: str = Field(min_length=1, max_length=256)
    effect_key: str = Field(min_length=1, max_length=256)
    outcome: Literal["applied", "already_applied", "rejected", "challenge", "rate_limited", "timeout", "duplicate"]
    observed_at: datetime


class EmailActionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mailbox_grant: MailboxGrant
    recipient: str = Field(min_length=3, max_length=320)
    subject: str = Field(max_length=998)
    body: str = Field(min_length=1, max_length=20000)
    effect_key: str = Field(min_length=1, max_length=256)
