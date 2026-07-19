"""
API security enforcement for billing and subscription endpoints.
Ensures plan enforcement cannot be bypassed and data isolation is maintained.
"""
import logging
from typing import Optional

from openoutreach.mongodb.models_user import User
from openoutreach.billing.enforcement import PlanEnforcer

logger = logging.getLogger(__name__)


class BillingAPISecurity:
    """Security enforcement for billing API endpoints."""

    @staticmethod
    def verify_user_owns_subscription(user_id: str, target_user_id: str) -> bool:
        """
        Verify that a user owns a subscription or is admin accessing another user's data.
        Returns True if authorized.
        """
        if user_id == target_user_id:
            return True

        user = User.get(user_id)
        if not user:
            return False

        if user.is_admin:
            return True

        return False

    @staticmethod
    def enforce_admin_only(user: User) -> bool:
        """Check if user is an admin."""
        return user.is_admin

    @staticmethod
    def mask_stripe_customer_id(user: User, requester_id: str) -> Optional[str]:
        """
        Return Stripe customer ID only if requester owns the account.
        Returns None otherwise (security: never expose to non-owner).
        """
        if user._id == requester_id:
            return user.stripe_customer_id

        requester = User.get(requester_id)
        if requester and requester.is_admin:
            return user.stripe_customer_id

        return None

    @staticmethod
    def enforce_plan_limits_api(user: User) -> tuple[bool, Optional[str]]:
        """
        Enforce that plan limits haven't been bypassed via direct API calls.
        Returns (is_valid, error_message).
        """
        if user.status == "blocked":
            return False, "Account is blocked"

        can_run, error = PlanEnforcer.can_run_tasks(user)
        if not can_run:
            return False, error

        return True, None

    @staticmethod
    def validate_plan_name(plan_name: str) -> tuple[bool, Optional[str]]:
        """
        Validate that plan_name is a known plan.
        Returns (is_valid, error_message).
        """
        from openoutreach.billing.plans import PLANS

        valid_plans = [p["name"] for p in PLANS]
        if plan_name not in valid_plans:
            return False, f"Invalid plan: {plan_name}. Must be one of: {', '.join(valid_plans)}"

        return True, None

    @staticmethod
    def validate_billing_period(period: str) -> tuple[bool, Optional[str]]:
        """
        Validate that billing_period is monthly, annual, or lifetime.
        Returns (is_valid, error_message).
        """
        valid_periods = ["monthly", "annual", "lifetime"]
        if period not in valid_periods:
            return False, f"Invalid billing period: {period}. Must be one of: {', '.join(valid_periods)}"

        return True, None

    @staticmethod
    def prevent_jwt_staleness(user: User) -> Optional[str]:
        """
        Ensure JWT token doesn't have stale plan data.
        Returns error message if plan was just downgraded/changed, else None.
        Always fetch fresh from DB rather than trusting JWT claims.
        """
        fresh = User.get(user._id)
        if not fresh:
            return "User not found"

        if fresh.plan != user.plan:
            return f"Plan was updated. Please refresh. New plan: {fresh.plan}"

        if fresh.subscription_status != user.subscription_status:
            return f"Subscription status changed. Please refresh. New status: {fresh.subscription_status}"

        if fresh.status != user.status:
            return "Account status changed. Please refresh."

        return None
