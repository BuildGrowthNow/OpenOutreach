"""
Plan enforcement and feature gating for subscription limits and permissions.

Server-side hard blocks for LinkedIn accounts, campaigns, and feature access.
Phase 3A resolves limits through the active organization: a member inherits the
workspace owner's plan and cloud seat pool, while personal users keep their own.
"""

import logging
from datetime import datetime, timezone as tz
from typing import Optional

from openoutreach.mongodb.models_user import User
from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.billing.cloud_seats import cloud_seat_units_for_scope
from openoutreach.billing.plans import get_plan
from openoutreach.billing.seats import accounting_scope_id, count_credentialed_profiles
from openoutreach.organizations.enforcement import EffectivePlan, resolve_effective_plan

logger = logging.getLogger(__name__)


class PlanEnforcer:
    """Enforces plan limits and feature gates for a user."""

    @staticmethod
    def can_create_linkedin_account(user: User) -> tuple[bool, Optional[str]]:
        """
        Check if user can create another LinkedIn account.
        Returns (can_create, error_message).
        """
        effective = resolve_effective_plan(user)
        if not effective.is_active:
            return False, "Subscription is not active"

        if (
            get_mongodb_collection("linkedin_profiles") is None
            or get_mongodb_collection("linkedin_credentials") is None
        ):
            return False, "Database error"

        # Count every profile that owns a credential, active or paused. A seat
        # is assigned to an account; pausing does not free the seat.
        count = count_credentialed_profiles(user._id)
        limit = effective.linkedin_account_limit
        if count >= limit:
            return False, f"LinkedIn account limit reached ({count}/{limit})"

        return True, None

    @staticmethod
    def can_create_campaign(user: User) -> tuple[bool, Optional[str]]:
        """
        Check if user can create another campaign.
        Returns (can_create, error_message).
        """
        effective = resolve_effective_plan(user)
        if not effective.is_active:
            return False, "Subscription is not active"

        campaign_limit = effective.campaign_limit
        if campaign_limit is None:
            return True, None

        collection = get_mongodb_collection("campaigns")
        if collection is None:
            return False, "Database error"

        count = collection.count_documents({
            "user_id": user._id,
            "is_paused": False,
        })

        if count >= campaign_limit:
            return False, f"Campaign limit reached ({count}/{campaign_limit})"

        return True, None

    @staticmethod
    def can_use_cloud_execution(
        user: User,
        *,
        exclude_profile_id: Optional[str] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if user can add a cloud-executed LinkedIn credential.

        Cloud execution means the server-side daemon will run the browser session.
        Users without cloud_execution access must use the desktop daemon instead.
        ``exclude_profile_id`` lets verification of an already-created profile
        count that profile's own seat without blocking the check.
        Returns (allowed, error_message).
        """
        effective = resolve_effective_plan(user)
        if not effective.is_active:
            return False, "Subscription is not active"

        # Cloud plan includes one seat; add-on seats add one each. The unified
        # pool counts cloud LinkedIn and cloud WhatsApp browser accounts, with
        # a Cloud Duo sharing one seat across its two channels.
        seat_limit = effective.cloud_seat_limit
        if seat_limit <= 0:
            return False, "Cloud execution requires a Cloud Add-on or eligible plan. Use the desktop app instead."

        scope_id = accounting_scope_id(user._id)
        units = cloud_seat_units_for_scope(scope_id)
        if exclude_profile_id:
            units = [
                unit
                for unit in units
                if unit.get("profile_id") != exclude_profile_id
                and unit.get("whatsapp_profile_id") != exclude_profile_id
            ]
        used = len(units)
        if used < seat_limit:
            return True, None
        return False, f"Cloud execution seat limit reached ({used}/{seat_limit})"

    @staticmethod
    def can_run_tasks(user: User) -> tuple[bool, Optional[str]]:
        """
        Check if user can run automated tasks.
        Returns (can_run, error_message).
        """
        if user.status == "blocked":
            return False, "Account blocked"

        effective = resolve_effective_plan(user)
        if not effective.is_active:
            return False, "Subscription is not active"

        return True, None

    @staticmethod
    def has_feature(user: User, feature: str) -> bool:
        """Check if the user's effective plan has a specific feature."""
        effective = resolve_effective_plan(user)
        plan = get_plan(effective.plan)
        if not plan:
            return False

        return feature in plan.get("features", [])

    @staticmethod
    def get_usage_stats(user: User) -> dict:
        """Get user's current usage vs limits."""
        effective = resolve_effective_plan(user)
        stats = {
            "linkedin_accounts_used": 0,
            "linkedin_accounts_limit": effective.linkedin_account_limit,
            "campaigns_used": 0,
            "campaigns_limit": effective.campaign_limit,
            "subscription_status": effective.subscription_status,
            "plan": effective.plan,
            "trial_days_remaining": PlanEnforcer._get_trial_days_remaining(user),
        }

        stats["linkedin_accounts_used"] = count_credentialed_profiles(user._id)

        campaigns_collection = get_mongodb_collection("campaigns")
        if campaigns_collection is not None:
            stats["campaigns_used"] = campaigns_collection.count_documents({
                "user_id": user._id,
                "is_paused": False,
            })

        return stats

    @staticmethod
    def _effective(user: User) -> EffectivePlan:
        return resolve_effective_plan(user)

    @staticmethod
    def _is_subscription_active(user: User) -> bool:
        """Check if the effective subscription is in active/trialing state."""
        try:
            return PlanEnforcer._effective(user).is_active
        except Exception:
            status = user.subscription_status
            if status not in ("active", "trialing"):
                return False
            if status == "trialing" and user.trial_ends_at:
                trial_ends = user.trial_ends_at
                if trial_ends.tzinfo is None:
                    trial_ends = trial_ends.replace(tzinfo=tz.utc)
                if datetime.now(tz.utc) > trial_ends:
                    return False
            return True

    @staticmethod
    def _get_trial_days_remaining(user: User) -> Optional[int]:
        """Calculate days remaining in trial, or None if not in trial."""
        try:
            effective = PlanEnforcer._effective(user)
            status = effective.subscription_status
            trial_ends = effective.trial_ends_at
        except Exception:
            status = user.subscription_status
            trial_ends = user.trial_ends_at

        if status != "trialing" or not trial_ends:
            return None

        if trial_ends.tzinfo is None:
            trial_ends = trial_ends.replace(tzinfo=tz.utc)
        delta = trial_ends - datetime.now(tz.utc)
        days = delta.days
        return max(0, days)


def user_has_feature(user: User, feature_name: str) -> bool:
    """Utility function to check if user has a feature."""
    return PlanEnforcer.has_feature(user, feature_name)
