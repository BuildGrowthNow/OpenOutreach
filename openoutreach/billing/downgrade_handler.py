"""
Downgrade handler - deactivates excess LinkedIn/WhatsApp profiles when plan downgraded.
Ensures users comply with new plan limits after downgrade.
"""

import logging

from openoutreach.billing.seats import (
    credentialed_profile_ids,
    credentialed_profile_ids_for_scope,
    org_ids_owned_by,
)
from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.mongodb.models_user import User
from openoutreach.organizations.service import team_workspaces_enabled

logger = logging.getLogger(__name__)


def pause_excess_linkedin_profiles(
    user_id: str,
    new_limit: int,
    *,
    prefer_execution_mode: str | None = None,
) -> dict[str, int]:
    """Pause LinkedIn profiles above the account limit.

    Pausing (not deleting) keeps data and cookies. A used proxy stays assigned
    to its original LinkedIn account and is never recycled.

    ``prefer_execution_mode`` selects which profiles to pause first. Seat
    reductions pass ``"cloud"`` so a Cloud customer never loses a desktop
    profile merely because it was created later.
    """
    collection = get_mongodb_collection("linkedin_profiles")
    if collection is None:
        logger.error("LinkedIn profiles collection not available")
        return {"deactivated": 0, "error": True}

    if team_workspaces_enabled():
        org_ids = org_ids_owned_by(user_id)
        profile_query: dict = {
            "$or": [
                {"org_id": {"$in": org_ids}},
                {"user_id": user_id},
            ],
            "is_active": True,
        }
        active_profiles = list(
            collection.find(profile_query, sort=[("created_at", 1)])
        )
        credentialed_ids = credentialed_profile_ids_for_scope(user_id)
    else:
        active_profiles = list(
            collection.find(
                {"user_id": user_id, "is_active": True},
                sort=[("created_at", 1)],
            )
        )
        credentialed_ids = credentialed_profile_ids(user_id)

    # Orphan profiles without a credential do not consume an account seat and
    # must not be chosen ahead of a real account.
    if credentialed_ids is not None:
        active_profiles = [
            profile
            for profile in active_profiles
            if profile.get("_id") in credentialed_ids
        ]

    if prefer_execution_mode:
        preferred = [
            profile
            for profile in active_profiles
            if profile.get("execution_mode") == prefer_execution_mode
        ]
        others = [
            profile
            for profile in active_profiles
            if profile.get("execution_mode") != prefer_execution_mode
        ]
        # Excess profiles are taken from the tail, so preferred-mode profiles
        # must be last to pause them before unrelated desktop profiles.
        active_profiles = others + preferred

    current_count = len(active_profiles)
    if current_count <= new_limit:
        logger.info(
            "User has %s profiles, limit is %s, no pause needed",
            current_count,
            new_limit,
        )
        return {"deactivated": 0, "error": False}

    profiles_to_pause = active_profiles[new_limit:]
    profile_ids = [p["_id"] for p in profiles_to_pause]

    result = collection.update_many(
        {"_id": {"$in": profile_ids}},
        {"$set": {"is_active": False, "active": False, "daemon_status": "seat_required"}},
    )

    for profile in profiles_to_pause:
        # Phase 2: disable the provider sub-account; keep it bound to this
        # profile so the same identity can resume when a seat is re-added.
        try:
            from openoutreach.proxies.provisioning import disable_massive_for_profile

            disable_massive_for_profile(
                str(profile.get("_id")), reason="seat_limit_reduced"
            )
        except Exception as exc:  # pragma: no cover - pause must still complete
            logger.debug(
                "Could not disable Massive sub-account: %s", type(exc).__name__
            )
        _notify_seat_removed(
            str(profile.get("assigned_user_id") or user_id), profile
        )

    count = result.modified_count
    logger.info("Paused %s LinkedIn profiles for user %s above the account limit", count, user_id)

    return {"deactivated": count, "error": False}


def _notify_seat_removed(user_id: str, profile: dict) -> None:
    """Tell the customer which profile paused after a seat reduction."""
    try:
        from openoutreach.mongodb.models_extended import Notification

        username = profile.get("linkedin_username") or "LinkedIn account"
        Notification(
            recipient_id=user_id,
            notification_type="campaign_error",
            title="Cloud seat removed",
            message=(
                f"{username} was paused because your cloud seat limit changed. "
                "Add a cloud seat or move the account to desktop execution to resume."
            ),
            data={"profile_id": str(profile.get("_id")), "requires_action": True},
        ).save()
    except Exception as e:
        logger.debug("Could not create seat notification: %s", type(e).__name__)


def handle_plan_downgrade(
    user: User,
    new_limit: int,
    *,
    prefer_execution_mode: str | None = None,
) -> dict[str, int]:
    """
    Pause excess LinkedIn profiles when user downgrades plan.

    Args:
        user: The user object
        new_limit: New LinkedIn account limit
        prefer_execution_mode: Optional execution mode to pause first

    Returns:
        {"paused": count, "error": False/True}
    """
    return pause_excess_linkedin_profiles(
        user._id,
        new_limit,
        prefer_execution_mode=prefer_execution_mode,
    )


def handle_wa_plan_downgrade(user: User, new_limit: int) -> dict[str, int]:
    """
    Delete excess WhatsApp profiles when user downgrades plan.
    Deletes oldest profiles first to minimize disruption.

    Args:
        user: The user object
        new_limit: New WhatsApp account limit

    Returns:
        {"deleted": count, "error": False/True}
    """
    collection = get_mongodb_collection("whatsapp_profiles")
    if collection is None:
        logger.error("WhatsApp profiles collection not available")
        return {"deleted": 0, "error": True}

    profiles = list(
        collection.find(
            {"user_id": user._id},
            sort=[("created_at", 1)],
        )
    )

    current_count = len(profiles)
    if current_count <= new_limit:
        logger.info(f"User has {current_count} WA profiles, limit is {new_limit}, no deletion needed")
        return {"deleted": 0, "error": False}

    profiles_to_delete = profiles[new_limit:]
    profile_ids = [p["_id"] for p in profiles_to_delete]

    result = collection.delete_many({"_id": {"$in": profile_ids}})

    count = result.deleted_count
    logger.info(f"Deleted {count} WhatsApp profiles for user {user._id} due to plan downgrade")

    return {"deleted": count, "error": False}
