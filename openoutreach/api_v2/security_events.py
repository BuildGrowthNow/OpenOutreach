"""Append-only, redacted security event persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from openoutreach.mongodb.connection import get_mongodb_collection

_FORBIDDEN = {"token", "authorization", "password", "cookie", "secret", "key", "body", "response"}


def append_security_event(event: str, *, outcome: str, actor_type: str, tenant_id: str | None = None, device_id: str | None = None, request_id: str | None = None, metadata: dict[str, Any] | None = None) -> None:
    """Best-effort append of allowlisted metadata; never affect requests."""
    safe_metadata = {
        name: value
        for name, value in (metadata or {}).items()
        if name.lower() not in _FORBIDDEN and isinstance(value, (str, int, float, bool, type(None)))
    }
    collection = get_mongodb_collection("security_audit_events")
    if collection is None:
        return
    try:
        collection.insert_one(
            {
                "_id": str(uuid4()),
                "event": event,
                "outcome": outcome,
                "actor_type": actor_type,
                "tenant_id": tenant_id,
                "device_id": device_id,
                "request_id": request_id,
                "metadata": safe_metadata,
                "created_at": datetime.now(timezone.utc),
            }
        )
    except Exception:
        # Audit persistence is intentionally non-blocking and must not become
        # an availability or information-disclosure side channel.
        return
