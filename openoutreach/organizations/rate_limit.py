"""Rate limits for organization invite creation and acceptance."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from openoutreach.config import settings
from openoutreach.mongodb.connection import get_mongodb_collection

logger = logging.getLogger(__name__)

_COLLECTION = "organization_rate_limit_events"


def _check_and_record(scope: str, action: str, limit: int, window_seconds: int) -> tuple[bool, str | None]:
    collection = get_mongodb_collection(_COLLECTION)
    if collection is None:
        # Fail closed: invite endpoints are security-sensitive.
        return False, "Invite service temporarily unavailable"
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=max(1, window_seconds))
    try:
        count = collection.count_documents(
            {"scope": scope, "action": action, "created_at": {"$gte": cutoff}}
        )
        if count >= limit:
            return False, "Too many requests. Please wait before trying again."
        collection.insert_one(
            {
                "scope": scope,
                "action": action,
                "created_at": now,
            }
        )
    except Exception as exc:
        logger.warning(
            "organization_rate_limit_failed action=%s exception_type=%s",
            action,
            type(exc).__name__,
        )
        return False, "Invite service temporarily unavailable"
    return True, None


def check_invite_creation(scope: str) -> tuple[bool, str | None]:
    return _check_and_record(
        scope,
        "invite.create",
        int(getattr(settings, "ORGANIZATION_INVITE_RATE_LIMIT", 30) or 30),
        int(getattr(settings, "ORGANIZATION_INVITE_RATE_WINDOW_SECONDS", 3600) or 3600),
    )


def check_invite_acceptance(scope: str) -> tuple[bool, str | None]:
    return _check_and_record(
        scope,
        "invite.accept",
        int(getattr(settings, "ORGANIZATION_ACCEPT_RATE_LIMIT", 30) or 30),
        int(getattr(settings, "ORGANIZATION_ACCEPT_RATE_WINDOW_SECONDS", 3600) or 3600),
    )
