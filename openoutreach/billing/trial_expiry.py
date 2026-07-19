"""
Trial expiry enforcement - marks expired trials and blocks access.
Runs as a background job to detect and enforce trial expiration.
"""

import logging
from datetime import datetime, timezone as tz

from openoutreach.mongodb.connection import get_mongodb_collection

logger = logging.getLogger(__name__)


def expire_trials() -> dict[str, int]:
    """
    Find users in trialing state with expired trial_ends_at and mark them as expired.
    Returns count of users affected.
    """
    users_collection = get_mongodb_collection("users")
    if users_collection is None:
        logger.error("Users collection not available")
        return {"expired": 0, "error": True}

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

    count = result.modified_count
    if count > 0:
        logger.info(f"Expired {count} trials")

    return {"expired": count, "error": False}
