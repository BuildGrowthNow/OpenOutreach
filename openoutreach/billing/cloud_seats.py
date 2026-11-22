"""Unified, org-scoped cloud seat accounting (Phase 4).

A cloud seat is one browser account: one cloud LinkedIn profile **or** one
cloud WhatsApp number, plus one email slot and one proxy identity. A Cloud Duo
is one real-world identity with one LinkedIn account and one WhatsApp number;
it consumes **one** seat whether the channels share a proxy (shared IP) or use
two proxies (separate IPs).

The counter is keyed by the accounting owner (the organization owner) and is
reserved with a single conditional MongoDB update so two concurrent account
creations cannot both pass a count check.

A seat is released only when the profile/credential is deleted. Pausing,
removing a seat assignment, cancellation, and member removal never release a
seat. The counter heals upward from real database rows on every reservation;
downward healing is explicit through :func:`reconcile_cloud_seat_usage`.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from pymongo.errors import DuplicateKeyError

from openoutreach.billing.seats import accounting_scope_id, org_ids_owned_by
from openoutreach.config import settings
from openoutreach.mongodb.connection import get_mongodb_collection

logger = logging.getLogger(__name__)

_COLLECTION = "cloud_seat_usage"
_PROFILES = "linkedin_profiles"
_CREDENTIALS = "linkedin_credentials"
_WHATSAPP = "whatsapp_profiles"
_ORGANIZATIONS = "organizations"
_USERS = "users"


def _team_enabled() -> bool:
    return bool(getattr(settings, "TEAM_WORKSPACES_ENABLED", False))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _created_sort_key(value: Any) -> tuple[int, str]:
    if isinstance(value, datetime):
        return (0, value.isoformat())
    if value:
        return (1, str(value))
    return (2, "")


def _scope_query(scope_id: str) -> dict[str, Any]:
    """Profiles that count against ``scope_id``'s pool.

    Includes the owner's personal organization, every shared workspace they
    own, and legacy personal rows without ``org_id``. This mirrors the
    LinkedIn seat counter so the two pools never disagree during rollout.
    """
    org_ids = org_ids_owned_by(scope_id) if _team_enabled() else []
    clauses: list[dict[str, Any]] = [
        {"org_id": {"$exists": False}, "user_id": scope_id},
        {"org_id": None, "user_id": scope_id},
    ]
    if org_ids:
        clauses.insert(0, {"org_id": {"$in": org_ids}})
    return {"$or": clauses}


def _org_query(org_id: str, owner_user_id: Optional[str] = None) -> dict[str, Any]:
    clauses: list[dict[str, Any]] = [{"org_id": org_id}]
    if owner_user_id:
        clauses.extend(
            [
                {"org_id": {"$exists": False}, "user_id": owner_user_id},
                {"org_id": None, "user_id": owner_user_id},
            ]
        )
    return {"$or": clauses}


def _credentialed_ids(profile_ids: list[str]) -> set[str]:
    if not profile_ids:
        return set()
    credentials = get_mongodb_collection(_CREDENTIALS)
    if credentials is None:
        return set()
    try:
        return {
            str(doc["linkedin_profile_id"])
            for doc in credentials.find(
                {"linkedin_profile_id": {"$in": profile_ids}},
                {"linkedin_profile_id": 1},
            )
        }
    except Exception:
        return set()


def _build_units(query: dict[str, Any]) -> list[dict[str, Any]]:
    """Return ordered seat units for the profile rows matching ``query``.

    Each unit is ``{"key", "channel", "profile_id", "whatsapp_profile_id"}``.
    A cloud WhatsApp profile paired with a credentialed cloud LinkedIn profile
    of the same ``identity_id`` shares the LinkedIn unit. Every other browser
    account is its own unit.
    """
    profiles = get_mongodb_collection(_PROFILES)
    whatsapp = get_mongodb_collection(_WHATSAPP)
    if profiles is None:
        return []

    linkedin_docs = list(
        profiles.find(
            {**query, "execution_mode": "cloud"},
            {"_id": 1, "identity_id": 1, "user_id": 1, "org_id": 1, "created_at": 1},
        )
    )
    credentialed = _credentialed_ids([str(doc["_id"]) for doc in linkedin_docs])
    linkedin_docs = [
        doc for doc in linkedin_docs if str(doc["_id"]) in credentialed
    ]
    linkedin_docs.sort(key=lambda doc: _created_sort_key(doc.get("created_at")))

    units: list[dict[str, Any]] = []
    identity_to_unit: dict[tuple[str, str], dict[str, Any]] = {}
    for doc in linkedin_docs:
        profile_id = str(doc["_id"])
        identity = str(
            doc.get("identity_id") or doc.get("user_id") or profile_id
        )
        org_key = str(doc.get("org_id") or "")
        unit = {
            "key": f"li:{profile_id}",
            "channel": "linkedin",
            "profile_id": profile_id,
            "whatsapp_profile_id": None,
        }
        units.append(unit)
        # Two LinkedIn accounts under the same identity each consume a seat;
        # only the first can pair with one WhatsApp number. Pairing is scoped
        # to the same workspace: a personal-org LinkedIn account must never
        # share a seat with a WhatsApp number in a different workspace, even
        # when both carry the same owner-derived identity_id.
        identity_to_unit.setdefault((org_key, identity), unit)

    if whatsapp is not None:
        whatsapp_docs = list(
            whatsapp.find(
                {**query, "execution_mode": "cloud"},
                {
                    "_id": 1,
                    "identity_id": 1,
                    "user_id": 1,
                    "org_id": 1,
                    "created_at": 1,
                },
            )
        )
        whatsapp_docs.sort(key=lambda doc: _created_sort_key(doc.get("created_at")))
        for doc in whatsapp_docs:
            profile_id = str(doc["_id"])
            identity = str(
                doc.get("identity_id") or doc.get("user_id") or profile_id
            )
            org_key = str(doc.get("org_id") or "")
            paired = identity_to_unit.get((org_key, identity))
            if paired is not None and paired.get("whatsapp_profile_id") is None:
                paired["whatsapp_profile_id"] = profile_id
                paired["channel"] = "duo"
                continue
            units.append(
                {
                    "key": f"wa:{profile_id}",
                    "channel": "whatsapp",
                    "profile_id": profile_id,
                    "whatsapp_profile_id": profile_id,
                }
            )
    return units


def cloud_seat_units_for_scope(scope_id: str) -> list[dict[str, Any]]:
    """Return the ordered seat units in one accounting scope."""
    return _build_units(_scope_query(scope_id))


def cloud_seat_units_for_org(
    org_id: str, owner_user_id: Optional[str] = None
) -> list[dict[str, Any]]:
    """Return the ordered seat units in one workspace."""
    return _build_units(_org_query(org_id, owner_user_id))


def cloud_seat_count_for_scope(scope_id: str) -> int:
    return len(cloud_seat_units_for_scope(scope_id))


def cloud_seat_count_for_org(
    org_id: str, owner_user_id: Optional[str] = None
) -> int:
    return len(cloud_seat_units_for_org(org_id, owner_user_id))


def cloud_seat_key_for_profile(
    profile_id: str,
    channel: str,
    *,
    org_id: Optional[str] = None,
    owner_user_id: Optional[str] = None,
) -> str:
    """Return the seat unit key that owns a LinkedIn or WhatsApp profile."""
    units = (
        cloud_seat_units_for_org(org_id, owner_user_id)
        if org_id
        else cloud_seat_units_for_scope(owner_user_id or profile_id)
    )
    for unit in units:
        if channel == "linkedin" and unit["profile_id"] == profile_id:
            return str(unit["key"])
        if channel == "whatsapp" and unit["whatsapp_profile_id"] == profile_id:
            return str(unit["key"])
    prefix = "li" if channel == "linkedin" else "wa"
    return f"{prefix}:{profile_id}"


def whatsapp_consumes_cloud_seat(
    profile_id: str,
    *,
    org_id: Optional[str] = None,
    owner_user_id: Optional[str] = None,
) -> bool:
    """True when deleting this WhatsApp number would release a seat.

    A Cloud Duo WhatsApp number shares the LinkedIn unit and does not release a
    seat when the number alone is deleted. A WhatsApp-only number (and a
    separate-IP Duo whose LinkedIn profile is already gone) does.
    """
    key = cloud_seat_key_for_profile(
        profile_id,
        "whatsapp",
        org_id=org_id,
        owner_user_id=owner_user_id,
    )
    return key.startswith("wa:")


def linkedin_profile_shares_seat_with_whatsapp(
    profile_id: str,
    *,
    org_id: Optional[str] = None,
    owner_user_id: Optional[str] = None,
) -> bool:
    """True when deleting this LinkedIn profile leaves a Duo WhatsApp unit.

    The WhatsApp number then becomes its own seat unit, so the cloud seat
    counter must not be decremented.
    """
    units = (
        cloud_seat_units_for_org(org_id, owner_user_id)
        if org_id
        else cloud_seat_units_for_scope(owner_user_id or profile_id)
    )
    return any(
        unit.get("profile_id") == profile_id and unit.get("channel") == "duo"
        for unit in units
    )


def allowed_cloud_seat_units(scope_id: str, limit: int) -> set[str]:
    """Return the unit keys the cloud daemon may run for a workspace.

    Units are ordered by creation time, so the first ``limit`` accounts keep
    running during an over-limit downgrade. Paused accounts still consume their
    unit; this function only decides which accounts may hold a live browser.
    """
    if limit <= 0:
        return set()
    return {
        str(unit["key"])
        for unit in cloud_seat_units_for_scope(scope_id)[:limit]
    }


def _reserve(scope_id: str, limit: int, actual: int) -> tuple[bool, Optional[str]]:
    if limit <= 0:
        return False, "Cloud seat limit reached"

    collection = get_mongodb_collection(_COLLECTION)
    if collection is None:
        return False, "Database error"

    now = _now()
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

    # Heal upward only. A paired Duo never increments this counter, so a
    # lower database count is the result of an explicit reconciliation.
    collection.update_one(
        {"_id": scope_id, "count": {"$lt": actual}},
        {"$set": {"count": actual, "updated_at": now}},
    )
    current_doc = collection.find_one({"_id": scope_id}, {"count": 1})
    current = int((current_doc or {}).get("count") or 0)

    reserved = collection.find_one_and_update(
        {"_id": scope_id, "count": {"$lt": limit}},
        {"$inc": {"count": 1}, "$set": {"updated_at": now}},
        return_document=True,
    )
    if reserved is None:
        return False, f"Cloud seat limit reached ({max(actual, current)}/{limit})"
    return True, None


def reserve_cloud_seat(user_id: str, limit: int) -> tuple[bool, Optional[str]]:
    """Atomically reserve one cloud seat in the user's accounting scope."""
    scope_id = accounting_scope_id(user_id)
    actual = cloud_seat_count_for_scope(scope_id)
    return _reserve(scope_id, limit, actual)


def release_cloud_seat(user_id: str) -> None:
    """Release one seat after a failed create or a profile/credential delete."""
    scope_id = accounting_scope_id(user_id)
    collection = get_mongodb_collection(_COLLECTION)
    if collection is None:
        return
    collection.update_one(
        {"_id": scope_id, "count": {"$gt": 0}},
        {"$inc": {"count": -1}, "$set": {"updated_at": _now()}},
    )


def reconcile_cloud_seat_usage(user_id: str) -> int:
    """Rebuild one counter from real rows; returns the new count."""
    scope_id = accounting_scope_id(user_id)
    actual = cloud_seat_count_for_scope(scope_id)
    collection = get_mongodb_collection(_COLLECTION)
    if collection is None:
        return actual
    now = _now()
    collection.update_one(
        {"_id": scope_id},
        {
            "$set": {"count": actual, "updated_at": now},
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    return actual


def _all_accounting_scopes() -> set[str]:
    scopes: set[str] = set()
    organizations = get_mongodb_collection(_ORGANIZATIONS)
    if organizations is not None:
        try:
            scopes.update(
                str(doc["owner_user_id"])
                for doc in organizations.find(
                    {"owner_user_id": {"$ne": None}}, {"owner_user_id": 1}
                )
                if doc.get("owner_user_id")
            )
        except Exception:
            pass
    users = get_mongodb_collection(_USERS)
    if users is not None:
        try:
            scopes.update(
                str(doc["_id"]) for doc in users.find({}, {"_id": 1})
            )
        except Exception:
            pass
    return scopes


def reconcile_all_cloud_seat_usage(*, dry_run: bool = True) -> dict[str, Any]:
    """Idempotent backfill/heal for every accounting owner.

    Dry-run by default. ``--apply`` is safe to run repeatedly; it only writes
    the counter, never profile or proxy data.
    """
    collection = get_mongodb_collection(_COLLECTION)
    scopes = sorted(_all_accounting_scopes())
    changes: list[dict[str, Any]] = []
    written = 0
    for scope_id in scopes:
        actual = cloud_seat_count_for_scope(scope_id)
        current = None
        if collection is not None:
            try:
                doc = collection.find_one({"_id": scope_id}, {"count": 1})
                current = int((doc or {}).get("count") or 0)
            except Exception:
                current = None
        if current != actual:
            changes.append(
                {"scope_id": scope_id, "before": current, "after": actual}
            )
            if not dry_run and collection is not None:
                now = _now()
                collection.update_one(
                    {"_id": scope_id},
                    {
                        "$set": {"count": actual, "updated_at": now},
                        "$setOnInsert": {"created_at": now},
                    },
                    upsert=True,
                )
                written += 1
    return {
        "dry_run": dry_run,
        "scopes": len(scopes),
        "changed": len(changes),
        "written": written,
        "changes": changes,
    }


def cloud_seat_summary_for_org(
    org_id: str,
    owner_user_id: Optional[str] = None,
    *,
    limit: Optional[int] = None,
) -> dict[str, Any]:
    """Return unified usage and a per-channel bundle breakdown."""
    units = cloud_seat_units_for_org(org_id, owner_user_id)
    linkedin = sum(1 for unit in units if unit["channel"] == "linkedin")
    whatsapp = sum(1 for unit in units if unit["channel"] == "whatsapp")
    duo = sum(1 for unit in units if unit["channel"] == "duo")
    return {
        "used": len(units),
        "limit": limit,
        "linkedin": linkedin,
        "whatsapp_only": whatsapp,
        "duo": duo,
        "whatsapp_total": whatsapp + duo,
        "units": units,
    }


def cloud_seat_alerts() -> list[dict[str, Any]]:
    """Internal alerts when a workspace is over its unified seat pool."""
    organizations = get_mongodb_collection(_ORGANIZATIONS)
    if organizations is None:
        return []
    alerts: list[dict[str, Any]] = []
    try:
        docs = list(
            organizations.find(
                {},
                {
                    "_id": 1,
                    "name": 1,
                    "owner_user_id": 1,
                    "plan": 1,
                    "cloud_seats": 1,
                    "seat_override": 1,
                },
            )
        )
    except Exception:
        return []
    for doc in docs:
        owner_id = str(doc.get("owner_user_id") or "")
        if not owner_id:
            continue
        from openoutreach.billing.plans import effective_cloud_seat_limit
        from openoutreach.mongodb.models_user import User

        owner = User.get(owner_id)
        if owner is None:
            continue
        if doc.get("seat_override"):
            limit = effective_cloud_seat_limit(
                str(doc.get("plan") or owner.plan or "starter"),
                int(doc.get("cloud_seats") or 0),
            )
        else:
            limit = effective_cloud_seat_limit(
                owner.plan or "starter", int(owner.cloud_profiles or 0)
            )
        summary = cloud_seat_summary_for_org(str(doc["_id"]), owner_id, limit=limit)
        if summary["used"] > limit:
            alerts.append(
                {
                    "type": "cloud_seat_over_limit",
                    "org_id": str(doc["_id"]),
                    "org_name": doc.get("name"),
                    "owner_user_id": owner_id,
                    "used": summary["used"],
                    "limit": limit,
                    "linkedin": summary["linkedin"],
                    "whatsapp_only": summary["whatsapp_only"],
                    "duo": summary["duo"],
                }
            )
    return alerts


__all__ = [
    "allowed_cloud_seat_units",
    "cloud_seat_alerts",
    "cloud_seat_count_for_org",
    "cloud_seat_count_for_scope",
    "cloud_seat_key_for_profile",
    "cloud_seat_summary_for_org",
    "cloud_seat_units_for_org",
    "cloud_seat_units_for_scope",
    "linkedin_profile_shares_seat_with_whatsapp",
    "reconcile_all_cloud_seat_usage",
    "reconcile_cloud_seat_usage",
    "release_cloud_seat",
    "reserve_cloud_seat",
    "whatsapp_consumes_cloud_seat",
]
