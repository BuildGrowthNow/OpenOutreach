"""Atomic LinkedIn seat accounting.

The account limit must be enforced before a profile/credential pair is created,
otherwise two concurrent requests can both pass a count check. This module keeps
one counter document per user and reserves a slot with a single conditional
MongoDB update.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from openoutreach.mongodb.connection import get_mongodb_collection

_COLLECTION = "linkedin_seat_usage"


def credentialed_profile_ids(user_id: str) -> Optional[set[str]]:
    """Return IDs of profiles that own a credential, or None if unavailable."""
    profiles = get_mongodb_collection("linkedin_profiles")
    credentials = get_mongodb_collection("linkedin_credentials")
    if profiles is None or credentials is None:
        return None

    try:
        profile_ids = [
            doc["_id"]
            for doc in profiles.find({"user_id": user_id}, {"_id": 1})
        ]
        if not profile_ids:
            return set()
        return {
            doc["linkedin_profile_id"]
            for doc in credentials.find(
                {
                    "user_id": user_id,
                    "linkedin_profile_id": {"$in": profile_ids},
                },
                {"linkedin_profile_id": 1},
            )
        }
    except Exception:
        return None


def count_credentialed_profiles(user_id: str) -> int:
    """Count profiles that own at least one credential, active or paused."""
    ids = credentialed_profile_ids(user_id)
    return len(ids) if ids is not None else 0


def reserve_linkedin_seat(user_id: str, limit: int) -> tuple[bool, Optional[str]]:
    """Atomically reserve one LinkedIn account slot.

    The counter is initialized from the real credentialed-profile count the
    first time it is used, so existing users are accounted for without a
    separate backfill migration.
    """
    if limit <= 0:
        return False, "LinkedIn account limit reached"

    collection = get_mongodb_collection(_COLLECTION)
    if collection is None:
        return False, "Database error"

    now = datetime.now(timezone.utc)
    actual = count_credentialed_profiles(user_id)

    # Create the counter lazily, then heal it upward if profiles were created
    # before this counter existed.
    collection.update_one(
        {"_id": user_id},
        {"$setOnInsert": {"count": actual, "created_at": now}},
        upsert=True,
    )
    collection.update_one(
        {"_id": user_id, "count": {"$lt": actual}},
        {"$set": {"count": actual, "updated_at": now}},
    )

    reserved = collection.find_one_and_update(
        {"_id": user_id, "count": {"$lt": limit}},
        {
            "$inc": {"count": 1},
            "$set": {"updated_at": now},
        },
        return_document=True,
    )
    if reserved is None:
        return False, f"LinkedIn account limit reached ({actual}/{limit})"
    return True, None


def release_linkedin_seat(user_id: str) -> None:
    """Release one reserved slot after a failed create or a profile delete."""
    collection = get_mongodb_collection(_COLLECTION)
    if collection is None:
        return
    collection.update_one(
        {"_id": user_id, "count": {"$gt": 0}},
        {
            "$inc": {"count": -1},
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
    )


def reconcile_linkedin_seat_usage(user_id: str) -> int:
    """Rebuild the counter from credentialed profiles; returns the new count."""
    collection = get_mongodb_collection(_COLLECTION)
    actual = count_credentialed_profiles(user_id)
    if collection is None:
        return actual
    now = datetime.now(timezone.utc)
    collection.update_one(
        {"_id": user_id},
        {
            "$set": {"count": actual, "updated_at": now},
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    return actual
