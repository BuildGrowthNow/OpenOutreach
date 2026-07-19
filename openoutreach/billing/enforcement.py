"""
Plan enforcement - checking user subscription status and plan limits.
"""
import logging
from typing import Optional

from openoutreach.mongodb.models_user import User
from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.billing.plans import get_plan

logger = logging.getLogger(__name__)


class PlanEnforcer:
    """Utility for checking plan limits and features."""

    @staticmethod
    def can_create_linkedin_account(user: User) -> tuple[bool, Optional[str]]:
        """Check if user can create another LinkedIn account."""
        if user.subscription_status not in ("active", "trialing"):
            return False, "Subscription not active"

        collection = get_mongodb_collection("linkedin_profiles")
        if collection is None:
            return False, "Database error"

        count = collection.count_documents({
            "user_id": user._id,
            "is_active": True,
        })

        if count >= user.linkedin_account_limit:
            return False, f"LinkedIn account limit reached ({count}/{user.linkedin_account_limit})"

        return True, None

    @staticmethod
    def can_create_campaign(user: User) -> tuple[bool, Optional[str]]:
        """Check if user can create another campaign."""
        if user.subscription_status not in ("active", "trialing"):
            return False, "Subscription not active"

        if user.campaign_limit is None:
            return True, None

        collection = get_mongodb_collection("campaigns")
        if collection is None:
            return False, "Database error"

        count = collection.count_documents({
            "user_id": user._id,
            "is_paused": False,
        })

        if count >= user.campaign_limit:
            return False, f"Campaign limit reached ({count}/{user.campaign_limit})"

        return True, None

    @staticmethod
    def has_feature(user: User, feature: str) -> bool:
        """Check if user's plan has a feature."""
        plan = get_plan(user.plan)
        if not plan:
            return False

        return feature in plan["features"]

    @staticmethod
    def can_run_tasks(user: User) -> tuple[bool, Optional[str]]:
        """Check if user can run automated tasks."""
        if user.status == "blocked":
            return False, "Account blocked"

        if user.subscription_status == "expired":
            return False, "Trial expired"

        if user.subscription_status == "past_due":
            return False, "Payment failed"

        if user.subscription_status not in ("active", "trialing"):
            return False, "No active subscription"

        return True, None

    @staticmethod
    def get_usage_stats(user: User) -> dict[str, int]:
        """Get user's current usage stats."""
        stats = {
            "linkedin_accounts_used": 0,
            "linkedin_accounts_limit": user.linkedin_account_limit,
            "campaigns_used": 0,
            "campaigns_limit": user.campaign_limit or 0,
        }

        profiles_collection = get_mongodb_collection("linkedin_profiles")
        if profiles_collection is not None:
            stats["linkedin_accounts_used"] = profiles_collection.count_documents({
                "user_id": user._id,
                "is_active": True,
            })

        campaigns_collection = get_mongodb_collection("campaigns")
        if campaigns_collection is not None:
            stats["campaigns_used"] = campaigns_collection.count_documents({
                "user_id": user._id,
                "is_paused": False,
            })

        return stats
