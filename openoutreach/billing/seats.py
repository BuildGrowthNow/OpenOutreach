"""Atomic LinkedIn seat accounting.

The account limit must be enforced before a profile/credential pair is created,
otherwise two concurrent requests can both pass a count check. This module keeps
one counter document per accounting owner and reserves a slot with a single
conditional MongoDB update.

Phase 3A adds organization scope. A team member's credentialed profiles count
against the workspace owner's pool. The counter id is therefore the accounting
owner (the org owner) rather than the member who created the profile. Personal
users keep the original user-keyed counter semantics.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from openoutreach.config import settings
from openoutreach.mongodb.connection import get_mongodb_collection

from pymongo.errors import DuplicateKeyError

logger = logging.getLogger(__name__)

_COLLECTION = "linkedin_seat_usage"
_PROFILES = "linkedin_profiles"
_CREDENTIALS = "linkedin_credentials"
_ORGANIZATIONS = "organizations"
_MEMBERS = "organization_members"
_USERS = "users"


def _team_enabled() -> bool:
    return bool(getattr(settings, "TEAM_WORKSPACES_ENABLED", False))


def credentialed_profile_ids(user_id: str) -> Optional[set[str]]:
    """Return IDs of profiles owned by ``user_id`` that own a credential."""
    profiles = get_mongodb_collection(_PROFILES)
    credentials = get_mongodb_collection(_CREDENTIALS)
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


def org_ids_owned_by(user_id: str) -> list[str]:
    """Return organization IDs owned by ``user_id`` (personal and shared)."""
    collection = get_mongodb_collection(_ORGANIZATIONS)
    if collection is None:
        return []
    try:
        return [
            str(doc["_id"])
            for doc in collection.find({"owner_user_id": user_id}, {"_id": 1})
        ]
    except Exception:
        return []


def accounting_scope_id(user_id: str) -> str:
    """Return the user/org id whose counter this user's seats count against."""
    if not _team_enabled():
        return user_id
    users = get_mongodb_collection(_USERS)
    orgs = get_mongodb_collection(_ORGANIZATIONS)
    if users is None or orgs is None:
        return user_id
    try:
        user_doc = users.find_one({"_id": user_id}, {"org_id": 1})
        org_id = (user_doc or {}).get("org_id")
        if not org_id:
            return user_id
        org_doc = orgs.find_one({"_id": org_id}, {"owner_user_id": 1})
        owner_id = str((org_doc or {}).get("owner_user_id") or "")
        return owner_id or user_id
    except Exception:
        return user_id


def _credentialed_ids_for_profiles(profile_ids: list[str]) -> Optional[set[str]]:
    if not profile_ids:
        return set()
    credentials = get_mongodb_collection(_CREDENTIALS)
    if credentials is None:
        return None
    try:
        return {
            str(doc["linkedin_profile_id"])
            for doc in credentials.find(
                {"linkedin_profile_id": {"$in": profile_ids}},
                {"linkedin_profile_id": 1},
            )
        }
    except Exception:
        return None


def credentialed_profile_ids_for_org(
    org_id: str, *, execution_mode: Optional[str] = None
) -> Optional[set[str]]:
    """Count credentialed profiles in one organization, active or paused."""
    profiles = get_mongodb_collection(_PROFILES)
    if profiles is None:
        return None
    base_query: dict = {"org_id": org_id}
    if execution_mode:
        base_query["execution_mode"] = execution_mode
    try:
        profile_ids = [
            str(doc["_id"])
            for doc in profiles.find(base_query, {"_id": 1})
        ]
        if not profile_ids:
            # Pre-migration rows may not carry org_id yet. Include only
            # profiles owned by active members of this organization.
            members = get_mongodb_collection(_MEMBERS)
            if members is not None:
                member_ids = [
                    str(doc["user_id"])
                    for doc in members.find(
                        {"org_id": org_id, "status": "active"}, {"user_id": 1}
                    )
                ]
                if member_ids:
                    legacy_query: dict = {
                        "user_id": {"$in": member_ids},
                        "$or": [
                            {"org_id": {"$exists": False}},
                            {"org_id": None},
                        ],
                    }
                    if execution_mode:
                        legacy_query["execution_mode"] = execution_mode
                    profile_ids = [
                        str(doc["_id"])
                        for doc in profiles.find(legacy_query, {"_id": 1})
                    ]
        return _credentialed_ids_for_profiles(profile_ids)
    except Exception:
        return None


def credentialed_profile_ids_for_scope(scope_id: str) -> Optional[set[str]]:
    """Return credentialed profile IDs across every org owned by ``scope_id``.

    This includes the owner's personal organization and any shared workspaces
    they own. Legacy personal rows without ``org_id`` are included so the
    counter heals correctly before the migration runs.
    """
    if not _team_enabled():
        return credentialed_profile_ids(scope_id)

    org_ids = org_ids_owned_by(scope_id)
    profiles = get_mongodb_collection(_PROFILES)
    if profiles is None:
        return None
    if not org_ids:
        return credentialed_profile_ids(scope_id)
    try:
        query = {
            "$or": [
                {"org_id": {"$in": org_ids}},
                {"org_id": {"$exists": False}, "user_id": scope_id},
                {"org_id": None, "user_id": scope_id},
            ]
        }
        profile_ids = [
            str(doc["_id"]) for doc in profiles.find(query, {"_id": 1})
        ]
        return _credentialed_ids_for_profiles(profile_ids)
    except Exception:
        return None


def count_credentialed_profiles(user_id: str) -> int:
    """Count credentialed profiles in the user's accounting scope."""
    if not _team_enabled():
        ids = credentialed_profile_ids(user_id)
        return len(ids) if ids is not None else 0
    scope_id = accounting_scope_id(user_id)
    ids = credentialed_profile_ids_for_scope(scope_id)
    return len(ids) if ids is not None else 0


def _reserve(scope_id: str, limit: int, actual: int) -> tuple[bool, Optional[str]]:
    if limit <= 0:
        return False, "LinkedIn account limit reached"

    collection = get_mongodb_collection(_COLLECTION)
    if collection is None:
        return False, "Database error"

    now = datetime.now(timezone.utc)

    # Create the counter lazily, then heal it upward if profiles were created
    # before this counter existed. Downward healing is explicit via
    # reconcile_linkedin_seat_usage so concurrent reservations are never
    # reset below a just-incremented value.
    try:
        collection.update_one(
            {"_id": scope_id},
            {"$setOnInsert": {"count": actual, "created_at": now}},
            upsert=True,
        )
    except DuplicateKeyError:
        # A concurrent request created the counter first. Its value is the
        # authoritative starting point; continue with the conditional update.
        pass
    collection.update_one(
        {"_id": scope_id, "count": {"$lt": actual}},
        {"$set": {"count": actual, "updated_at": now}},
    )

    reserved = collection.find_one_and_update(
        {"_id": scope_id, "count": {"$lt": limit}},
        {
            "$inc": {"count": 1},
            "$set": {"updated_at": now},
        },
        return_document=True,
    )
    if reserved is None:
        return False, f"LinkedIn account limit reached ({actual}/{limit})"
    return True, None


def reserve_linkedin_seat(user_id: str, limit: int) -> tuple[bool, Optional[str]]:
    """Atomically reserve one LinkedIn account slot in the user's scope."""
    if not _team_enabled():
        actual = count_credentialed_profiles(user_id)
        return _reserve(user_id, limit, actual)
    scope_id = accounting_scope_id(user_id)
    ids = credentialed_profile_ids_for_scope(scope_id)
    if ids is None:
        return False, "Database error"
    actual = len(ids)
    return _reserve(scope_id, limit, actual)


def release_linkedin_seat(user_id: str) -> None:
    """Release one reserved slot after a failed create or a profile delete."""
    scope_id = accounting_scope_id(user_id)
    collection = get_mongodb_collection(_COLLECTION)
    if collection is None:
        return
    collection.update_one(
        {"_id": scope_id, "count": {"$gt": 0}},
        {
            "$inc": {"count": -1},
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
    )


def reconcile_linkedin_seat_usage(user_id: str) -> int:
    """Rebuild the counter from credentialed profiles; returns the new count."""
    scope_id = accounting_scope_id(user_id)
    collection = get_mongodb_collection(_COLLECTION)
    if not _team_enabled():
        actual = count_credentialed_profiles(user_id)
    else:
        ids = credentialed_profile_ids_for_scope(scope_id)
        actual = len(ids) if ids is not None else 0
    if collection is None:
        return actual
    now = datetime.now(timezone.utc)
    collection.update_one(
        {"_id": scope_id},
        {
            "$set": {"count": actual, "updated_at": now},
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    return actual
