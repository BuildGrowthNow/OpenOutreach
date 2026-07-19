"""
Plan enforcement and feature gating for subscription limits and permissions.
Server-side hard blocks for LinkedIn accounts, campaigns, and feature access.
Enforces plan limits across all operations for multi-tenant SaaS security.
"""

import logging
from datetime import datetime, timezone as tz
from typing import Optional

from openoutreach.mongodb.models_user import User
from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.billing.plans import get_plan

logger = logging.getLogger(__name__)


class PlanEnforcer:
    """Enforces plan limits and feature gates for a user."""

    @staticmethod
    def can_create_linkedin_account(user: User) -> tuple[bool, Optional[str]]:
        """
        Check if user can create another LinkedIn account.
        Returns (can_create, error_message).
        """
        if not PlanEnforcer._is_subscription_active(user):
            return False, "Subscription is not active"

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
        """
        Check if user can create another campaign.
        Returns (can_create, error_message).
        """
        if not PlanEnforcer._is_subscription_active(user):
            return False, "Subscription is not active"

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
    def can_run_tasks(user: User) -> tuple[bool, Optional[str]]:
        """
        Check if user can run automated tasks.
        Returns (can_run, error_message).
        """
        if user.status == "blocked":
            return False, "Account blocked"

        if not PlanEnforcer._is_subscription_active(user):
            return False, "Subscription is not active"

        return True, None

    @staticmethod
    def has_feature(user: User, feature: str) -> bool:
        """Check if user's plan has a specific feature."""
        plan = get_plan(user.plan)
        if not plan:
            return False

        return feature in plan.get("features", [])

    @staticmethod
    def get_usage_stats(user: User) -> dict:
        """Get user's current usage vs limits."""
        stats = {
            "linkedin_accounts_used": 0,
            "linkedin_accounts_limit": user.linkedin_account_limit,
            "campaigns_used": 0,
            "campaigns_limit": user.campaign_limit,
            "subscription_status": user.subscription_status,
            "plan": user.plan,
            "trial_days_remaining": PlanEnforcer._get_trial_days_remaining(user),
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

    @staticmethod
    def _is_subscription_active(user: User) -> bool:
        """Check if subscription is in active/trialing state."""
        status = user.subscription_status
        if status not in ("active", "trialing"):
            return False

        if status == "trialing" and user.trial_ends_at:
            if datetime.now(tz.utc) > user.trial_ends_at:
                return False

        return True

    @staticmethod
    def _get_trial_days_remaining(user: User) -> Optional[int]:
        """Calculate days remaining in trial, or None if not in trial."""
        if user.subscription_status != "trialing" or not user.trial_ends_at:
            return None

        delta = user.trial_ends_at - datetime.now(tz.utc)
        days = delta.days
        return max(0, days)


def user_has_feature(user: User, feature_name: str) -> bool:
    """Utility function to check if user has a feature."""
    return PlanEnforcer.has_feature(user, feature_name)
