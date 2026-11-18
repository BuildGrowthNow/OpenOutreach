"""Mongo-backed rate limits for privileged admin proxy operations."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from openoutreach.config import settings
from openoutreach.mongodb.connection import get_mongodb_collection

_COLLECTION = "admin_rate_limit_events"


class AdminActionRateLimiter:
    """Count admin actions in a rolling window.

    The limiter is intentionally simple and Mongo-backed so it works across
    API workers. Import and test are the two expensive proxy operations.
    """

    ACTIONS = {"proxy_import", "proxy_test"}

    @staticmethod
    def _limit(action: str) -> tuple[int, int]:
        if action == "proxy_import":
            return (
                max(1, int(getattr(settings, "PROXY_IMPORT_RATE_LIMIT", 10))),
                max(1, int(getattr(settings, "PROXY_IMPORT_RATE_WINDOW_SECONDS", 3600))),
            )
        return (
            max(1, int(getattr(settings, "PROXY_TEST_RATE_LIMIT", 120))),
            max(1, int(getattr(settings, "PROXY_TEST_RATE_WINDOW_SECONDS", 3600))),
        )

    @classmethod
    def check(cls, admin_user_id: str, action: str) -> tuple[bool, Optional[str]]:
        if action not in cls.ACTIONS:
            return False, "Unknown rate-limited action"
        collection = get_mongodb_collection(_COLLECTION)
        if collection is None:
            return False, "Rate limiter is unavailable"
        limit, window_seconds = cls._limit(action)
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
        count = collection.count_documents({
            "admin_user_id": admin_user_id,
            "action": action,
            "created_at": {"$gte": cutoff},
        })
        if count >= limit:
            return False, (
                f"Rate limit reached for {action.replace('_', ' ')}. "
                "Try again later."
            )
        return True, None

    @classmethod
    def record(cls, admin_user_id: str, action: str) -> None:
        collection = get_mongodb_collection(_COLLECTION)
        if collection is None:
            return
        try:
            collection.insert_one({
                "admin_user_id": admin_user_id,
                "action": action,
                "created_at": datetime.now(timezone.utc),
            })
        except Exception:
            # Rate-limit telemetry must never break a successful operation.
            pass
