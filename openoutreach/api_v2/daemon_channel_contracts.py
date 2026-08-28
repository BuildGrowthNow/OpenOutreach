"""Strict, non-secret v2 channel contracts exchanged with desktop adapters."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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
    outcome: Literal["applied", "already_applied", "rejected", "challenge"]
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
