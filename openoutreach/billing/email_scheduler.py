"""
Email scheduler for billing lifecycle events.
Handles sending emails at appropriate times (e.g., trial warnings, account actions).
"""
import logging
from datetime import datetime, timedelta, timezone as tz

from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.mongodb.models_user import User
from openoutreach.billing.emails import (
    send_trial_expiry_warning,
    send_trial_expired,
    send_account_blocked,
)

logger = logging.getLogger(__name__)


def send_trial_expiry_warnings() -> int:
    """
    Send trial expiry warnings to users whose trial ends in 1 day.
    Returns count of emails sent.
    """
    users_collection = get_mongodb_collection("users")
    if users_collection is None:
        logger.warning("Cannot send trial warnings: users collection not available")
        return 0

    now = datetime.now(tz.utc)
    tomorrow = now + timedelta(days=1)
    two_days_from_now = now + timedelta(days=2)

    users = users_collection.find(
        {
            "subscription_status": "trialing",
            "trial_ends_at": {
                "$gte": tomorrow,
                "$lt": two_days_from_now,
            },
        }
    )

    sent_count = 0
    for user_doc in users:
        try:
            user = User.from_dict(user_doc)
            if send_trial_expiry_warning(user, 1):
                sent_count += 1
        except Exception as e:
            logger.error(f"Failed to send trial warning to {user_doc.get('email')}: {e}")

    if sent_count > 0:
        logger.info(f"Sent {sent_count} trial expiry warnings")

    return sent_count


def expire_trials() -> int:
    """
    Expire trials for users whose trial period has ended.
    Sets subscription_status to 'expired' and blocks access.
    Returns count of users expired.
    """
    users_collection = get_mongodb_collection("users")
    if users_collection is None:
        logger.warning("Cannot expire trials: users collection not available")
        return 0

    now = datetime.now(tz.utc)

    result = users_collection.update_many(
        {
            "subscription_status": "trialing",
            "trial_ends_at": {"$lt": now},
        },
        {
            "$set": {
                "subscription_status": "expired",
                "updated_at": now,
            }
        },
    )

    expired_count = result.modified_count

    if expired_count > 0:
        logger.info(f"Expired {expired_count} user trials")

    # Send trial expiry email within 24 hours of expiration
    users = users_collection.find(
        {
            "subscription_status": "expired",
            "trial_ends_at": {"$gte": now - timedelta(hours=24), "$lt": now},
        }
    )

    for user_doc in users:
        try:
            user = User.from_dict(user_doc)
            send_trial_expired(user)
        except Exception as e:
            logger.error(f"Failed to send trial expired email to {user_doc.get('email')}: {e}")

    return expired_count


def send_account_blocked_notifications() -> int:
    """
    Send notifications to newly blocked accounts.
    Returns count of emails sent.
    """
    users_collection = get_mongodb_collection("users")
    if users_collection is None:
        logger.warning("Cannot send blocked notifications: users collection not available")
        return 0

    blocked_notifications = get_mongodb_collection("blocked_notifications")
    if blocked_notifications is None:
        logger.warning("Cannot send blocked notifications: collection not available")
        return 0

    users = users_collection.find({"status": "blocked"})

    sent_count = 0
    for user_doc in users:
        user_id = str(user_doc.get("_id"))

        already_notified = blocked_notifications.find_one({"user_id": user_id})
        if already_notified:
            continue

        try:
            user = User.from_dict(user_doc)
            reason = user_doc.get("admin_notes") or "violation of our terms of service"
            if send_account_blocked(user, reason):
                blocked_notifications.insert_one(
                    {
                        "user_id": user_id,
                        "sent_at": datetime.now(tz.utc),
                    }
                )
                sent_count += 1
        except Exception as e:
            logger.error(f"Failed to send blocked notification to {user_doc.get('email')}: {e}")

    if sent_count > 0:
        logger.info(f"Sent {sent_count} account blocked notifications")

    return sent_count
