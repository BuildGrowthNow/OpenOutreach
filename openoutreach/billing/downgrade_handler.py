"""
Downgrade handler - deactivates excess LinkedIn profiles when plan downgraded.
Ensures users comply with new plan limits after downgrade.
"""

import logging

from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.mongodb.models_user import User

logger = logging.getLogger(__name__)


def handle_plan_downgrade(user: User, new_limit: int) -> dict[str, int]:
    """
    Deactivate excess LinkedIn profiles when user downgrades plan.
    Deactivates oldest profiles first to minimize disruption.
    Sets is_active=False to prevent daemon execution.

    Args:
        user: The user object
        new_limit: New LinkedIn account limit

    Returns:
        {"deactivated": count, "error": False/True}
    """
    collection = get_mongodb_collection("linkedin_profiles")
    if collection is None:
        logger.error("LinkedIn profiles collection not available")
        return {"deactivated": 0, "error": True}

    active_profiles = list(
        collection.find(
            {"user_id": user._id, "active": True, "is_active": True},
            sort=[("created_at", 1)],
        )
    )

    current_count = len(active_profiles)
    if current_count <= new_limit:
        logger.info(f"User has {current_count} profiles, limit is {new_limit}, no deactivation needed")
        return {"deactivated": 0, "error": False}

    profiles_to_deactivate = active_profiles[new_limit:]
    profile_ids = [p["_id"] for p in profiles_to_deactivate]

    result = collection.update_many(
        {"_id": {"$in": profile_ids}},
        {"$set": {"is_active": False}},
    )

    count = result.modified_count
    logger.info(f"Deactivated {count} LinkedIn profiles for user {user._id} due to plan downgrade")

    return {"deactivated": count, "error": False}
