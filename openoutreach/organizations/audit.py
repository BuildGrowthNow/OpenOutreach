"""Organization audit events.

Events are written to ``organization_audit_logs`` and deliberately contain only
opaque IDs and non-secret metadata. Invite tokens, proxy passwords, cookies,
and provider keys must never be passed here.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.organizations.models import AUDIT_COLLECTION

logger = logging.getLogger(__name__)

# Event names required by the Phase 3A acceptance criteria.
EVENT_ORG_INVITE = "org.invite"
EVENT_ORG_ACCEPT = "org.accept"
EVENT_ORG_REMOVE = "org.remove"
EVENT_ORG_ROLE_CHANGE = "org.role_change"
EVENT_SEAT_ASSIGN = "seat.assign"
EVENT_SEAT_UNASSIGN = "seat.unassign"
EVENT_SEAT_REMOVE = "seat.remove"
EVENT_SEAT_OVERRIDE = "seat.override"
EVENT_ORG_ACTIVATE = "org.activate"

_FORBIDDEN_KEYS = {
    "password",
    "proxy_password",
    "token",
    "invite_token",
    "cookie",
    "cookies",
    "secret",
    "api_key",
    "authorization",
}


def _safe_metadata(metadata: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Drop obvious secret-bearing keys from audit metadata."""
    if not metadata:
        return {}
    cleaned: dict[str, Any] = {}
    for key, value in metadata.items():
        if any(term in str(key).lower() for term in _FORBIDDEN_KEYS):
            continue
        if isinstance(value, dict):
            cleaned[str(key)] = _safe_metadata(value)
        elif isinstance(value, (list, tuple)):
            cleaned[str(key)] = [
                _safe_metadata(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            cleaned[str(key)] = value
    return cleaned


def record_org_audit(
    event: str,
    *,
    org_id: str,
    actor_user_id: Optional[str] = None,
    target_user_id: Optional[str] = None,
    target_email: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    """Persist one organization audit event. Never raises to the caller."""
    collection = get_mongodb_collection(AUDIT_COLLECTION)
    if collection is None:
        logger.warning("organization_audit_unavailable event=%s", event)
        return
    try:
        collection.insert_one(
            {
                "_id": str(uuid4()),
                "org_id": org_id,
                "event": event,
                "actor_user_id": actor_user_id,
                "target_user_id": target_user_id,
                "target_email": (target_email or "").lower().strip() or None,
                "metadata": _safe_metadata(metadata),
                "created_at": datetime.now(timezone.utc),
            }
        )
    except Exception as exc:  # pragma: no cover - audit must not break mutation
        logger.warning(
            "organization_audit_failed event=%s exception_type=%s",
            event,
            type(exc).__name__,
        )


def list_org_audit_events(org_id: str, limit: int = 100) -> list[dict[str, Any]]:
    """Return recent audit events for an organization (admin/support use)."""
    collection = get_mongodb_collection(AUDIT_COLLECTION)
    if collection is None:
        return []
    return list(collection.find({"org_id": org_id}).sort("created_at", -1).limit(limit))
