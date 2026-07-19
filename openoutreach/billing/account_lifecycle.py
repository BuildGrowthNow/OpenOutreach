"""
Account lifecycle management - deletion, recovery, data export.

Handles:
- Account deletion requests with 30-day grace period
- Recovery from deletion (reactivation)
- Permanent data deletion after grace period
- Data export for GDPR compliance
- Cleanup of user data during permanent deletion
"""

import logging
from datetime import datetime, timedelta, timezone as tz

from openoutreach.mongodb.models_user import User
from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.billing.stripe_service import cancel_subscription

logger = logging.getLogger(__name__)


def request_account_deletion(user_id: str) -> dict:
    """
    User requests account deletion - schedules soft delete for 30 days.

    Returns dict with deletion_scheduled_at timestamp.
    """
    user = User.get(user_id)
    if not user:
        raise ValueError(f"User not found: {user_id}")

    # If already scheduled, just return the existing timestamp
    if user.deletion_scheduled_at:
        return {
            "deletion_scheduled_at": user.deletion_scheduled_at.isoformat(),
            "grace_period_ends_at": (
                user.deletion_scheduled_at + timedelta(days=30)
            ).isoformat(),
        }

    # Cancel subscription (if active)
    if user.stripe_subscription_id:
        try:
            cancel_subscription(user.stripe_subscription_id, immediate=True)
            logger.info(f"Canceled subscription for deletion: {user.email}")
        except Exception as e:
            logger.error(f"Failed to cancel subscription during deletion: {e}")

    # Deactivate all LinkedIn profiles
    try:
        profiles_collection = get_mongodb_collection("linkedin_profiles")
        if profiles_collection is not None:
            profiles_collection.update_many(
                {"user_id": user_id},
                {"$set": {"is_active": False}},
            )
            logger.info(f"Deactivated all profiles for user: {user.email}")
    except Exception as e:
        logger.error(f"Failed to deactivate profiles: {e}")

    # Schedule deletion
    deletion_scheduled_at = user.schedule_deletion()
    grace_period_ends_at = deletion_scheduled_at + timedelta(days=30)

    logger.info(f"Account deletion scheduled for {user.email}: {deletion_scheduled_at}")

    return {
        "deletion_scheduled_at": deletion_scheduled_at.isoformat(),
        "grace_period_ends_at": grace_period_ends_at.isoformat(),
    }


def cancel_account_deletion(user_id: str) -> dict:
    """
    User reactivates account during 30-day grace period.

    Returns updated user status.
    """
    user = User.get(user_id)
    if not user:
        raise ValueError(f"User not found: {user_id}")

    if not user.deletion_scheduled_at:
        raise ValueError("Account deletion not scheduled")

    if user.is_deletion_grace_period_expired():
        raise ValueError("Grace period has expired - account cannot be recovered")

    user.cancel_deletion()

    # Reactivate subscription if it was canceled
    if user.stripe_subscription_id and user.subscription_status == "canceled":
        try:
            from openoutreach.billing.stripe_service import reactivate_subscription
            reactivate_subscription(user.stripe_subscription_id)
            user.subscription_status = "active"
            logger.info(f"Reactivated subscription for user: {user.email}")
        except Exception as e:
            logger.error(f"Failed to reactivate subscription: {e}")
            # Continue with profile reactivation even if subscription fails

    # Reactivate LinkedIn profiles
    try:
        profiles_collection = get_mongodb_collection("linkedin_profiles")
        if profiles_collection is not None:
            profiles_collection.update_many(
                {"user_id": user_id},
                {"$set": {"is_active": True}},
            )
            logger.info(f"Reactivated all profiles for user: {user.email}")
    except Exception as e:
        logger.error(f"Failed to reactivate profiles: {e}")

    logger.info(f"Account deletion canceled for: {user.email}")

    return {
        "status": "active",
        "subscription_status": user.subscription_status,
        "message": "Your account has been reactivated. Please resubscribe to resume using the service.",
    }


def export_user_data(user_id: str) -> dict:
    """
    Export all user data for GDPR/data export requests.

    Returns dict with all user-related data in JSON-serializable format.
    """
    user = User.get(user_id)
    if not user:
        raise ValueError(f"User not found: {user_id}")

    data = {
        "user": {
            "id": user._id,
            "email": user.email,
            "full_name": user.full_name,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "status": user.status,
            "plan": user.plan,
            "subscription_status": user.subscription_status,
        },
        "billing": {},
        "linkedin_profiles": [],
        "campaigns": [],
        "leads": [],
        "deals": [],
        "messages": [],
        "action_logs": [],
    }

    try:
        profiles_collection = get_mongodb_collection("linkedin_profiles")
        if profiles_collection is not None:
            profiles = list(profiles_collection.find({"user_id": user_id}))
            data["linkedin_profiles"] = [
                {
                    "id": str(p.get("_id")),
                    "username": p.get("display_username"),
                    "created_at": p.get("created_at").isoformat()
                    if p.get("created_at")
                    else None,
                }
                for p in profiles
            ]
    except Exception as e:
        logger.warning(f"Failed to export linkedin_profiles: {e}")

    try:
        campaigns_collection = get_mongodb_collection("campaigns")
        if campaigns_collection is not None:
            campaigns = list(campaigns_collection.find({"user_id": user_id}))
            data["campaigns"] = [
                {
                    "id": str(c.get("_id")),
                    "name": c.get("name"),
                    "created_at": c.get("created_at").isoformat()
                    if c.get("created_at")
                    else None,
                }
                for c in campaigns
            ]
    except Exception as e:
        logger.warning(f"Failed to export campaigns: {e}")

    try:
        leads_collection = get_mongodb_collection("leads")
        if leads_collection is not None:
            leads = list(leads_collection.find({"user_id": user_id}).limit(100))
            data["leads"] = [
                {
                    "id": str(l.get("_id")),
                    "public_identifier": l.get("public_identifier"),
                    "discovered_at": l.get("created_at").isoformat()
                    if l.get("created_at")
                    else None,
                }
                for l in leads
            ]
    except Exception as e:
        logger.warning(f"Failed to export leads: {e}")

    try:
        deals_collection = get_mongodb_collection("deals")
        if deals_collection is not None:
            deals = list(deals_collection.find({"user_id": user_id}).limit(100))
            data["deals"] = [
                {
                    "id": str(d.get("_id")),
                    "state": d.get("state"),
                    "created_at": d.get("created_at").isoformat()
                    if d.get("created_at")
                    else None,
                }
                for d in deals
            ]
    except Exception as e:
        logger.warning(f"Failed to export deals: {e}")

    logger.info(f"Exported data for user: {user.email}")
    return data


def permanently_delete_user_data(user_id: str):
    """
    Permanently delete all user data (called after grace period expires).

    Deletes:
    - User record
    - LinkedIn profiles and credentials
    - Campaigns and tasks
    - Leads and deals
    - Messages and chat history
    - Action logs
    """
    user = User.get(user_id)
    if not user:
        logger.warning(f"User not found for deletion: {user_id}")
        return

    logger.info(f"Permanently deleting all data for user: {user.email}")

    # Delete from all collections
    collections_to_clean = [
        "linkedin_profiles",
        "linkedin_credentials",
        "campaigns",
        "tasks",
        "leads",
        "deals",
        "chat_messages",
        "action_logs",
        "linkedin_account_actions",
        "smart_rate_limit_contexts",
    ]

    for collection_name in collections_to_clean:
        try:
            collection = get_mongodb_collection(collection_name)
            if collection is not None:
                result = collection.delete_many({"user_id": user_id})
                logger.info(
                    f"Deleted {result.deleted_count} docs from {collection_name}"
                )
        except Exception as e:
            logger.error(f"Failed to delete from {collection_name}: {e}")

    # Finally, delete user record
    try:
        user.permanently_delete()
        logger.info(f"User permanently deleted: {user.email}")
    except Exception as e:
        logger.error(f"Failed to delete user record: {e}")


def cleanup_expired_deletions():
    """
    Cron job: clean up users whose 30-day grace period has expired.

    Call this periodically (daily recommended) to permanently delete
    users who requested deletion more than 30 days ago.
    """
    users_collection = get_mongodb_collection("users")
    if users_collection is None:
        logger.warning("Users collection not available")
        return

    try:
        # Find users with deletion_scheduled_at more than 30 days ago
        grace_period_threshold = datetime.now(tz.utc) - timedelta(days=30)

        deleted_users = users_collection.find(
            {
                "deletion_scheduled_at": {
                    "$exists": True,
                    "$ne": None,
                    "$lt": grace_period_threshold,
                }
            }
        )

        count = 0
        for user_doc in deleted_users:
            try:
                permanently_delete_user_data(user_doc["_id"])
                count += 1
            except Exception as e:
                logger.error(f"Failed to cleanup user {user_doc['_id']}: {e}")

        if count > 0:
            logger.info(f"Cleaned up {count} expired user deletions")

    except Exception as e:
        logger.error(f"Cleanup job failed: {e}")
