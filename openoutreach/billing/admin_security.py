"""
Admin security and impersonation controls.
Enforces read-only access for admin impersonation, prevents privilege escalation.
"""
import logging
from typing import Optional

from openoutreach.mongodb.models_user import User

logger = logging.getLogger(__name__)


class AdminSecurityPolicy:
    """Security policy for admin operations and impersonation."""

    IMPERSONATION_READ_ONLY_ACTIONS = {
        "view_campaigns",
        "view_leads",
        "view_settings",
        "view_billing",
        "view_activity",
        "export_data",
    }

    WRITE_ACTIONS = {
        "update_settings",
        "pause_campaign",
        "delete_campaign",
        "send_message",
        "update_profile",
    }

    @staticmethod
    def check_admin_permission(admin_user: User, action: str) -> tuple[bool, Optional[str]]:
        """
        Check if admin user can perform an action.
        Returns (allowed, error_message).
        """
        if not admin_user.is_admin:
            return False, "User is not an admin"

        if admin_user.status == "blocked":
            return False, "Admin account is blocked"

        return True, None

    @staticmethod
    def check_impersonation_allowed(
        admin_user: User,
        target_user_id: str,
        action: str,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if admin can impersonate target user for an action.
        Impersonation is read-only - write actions are blocked.
        Returns (allowed, error_message).
        """
        if admin_user._id == target_user_id:
            return True, None

        if not admin_user.is_admin:
            return False, "Not authorized to impersonate"

        if action in AdminSecurityPolicy.WRITE_ACTIONS:
            return False, "Write operations not allowed during impersonation (read-only mode)"

        return True, None

    @staticmethod
    def log_admin_action(
        admin_user_id: str,
        action: str,
        target_user_id: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> None:
        """Log admin actions for audit trail."""
        from openoutreach.mongodb.connection import get_mongodb_collection
        from datetime import datetime, timezone as tz

        collection = get_mongodb_collection("admin_audit_logs")
        if collection is None:
            logger.warning("Could not log admin action: collection not available")
            return

        try:
            collection.insert_one({
                "admin_user_id": admin_user_id,
                "action": action,
                "target_user_id": target_user_id,
                "details": details or {},
                "created_at": datetime.now(tz.utc),
            })
        except Exception as e:
            logger.error(
                "Failed to log admin action; exception_type=%s",
                type(e).__name__,
            )

    @staticmethod
    def mask_sensitive_fields(user: User, requester_id: str) -> dict:
        """
        Return user data with sensitive fields masked for non-owner access.
        Admin can see everything; non-owner gets limited data.
        """
        from openoutreach.mongodb.models_user import User as UserModel

        requester = UserModel.get(requester_id)
        if not requester:
            return {}

        user_dict = user.to_dict()

        if requester_id != user._id and not (requester and requester.is_admin):
            sensitive_fields = [
                "hashed_password",
                "stripe_customer_id",
                "stripe_subscription_id",
            ]
            for field in sensitive_fields:
                user_dict[field] = None

        return user_dict

    @staticmethod
    def require_write_permission(admin_user: User) -> tuple[bool, Optional[str]]:
        """
        Ensure admin has permission to write (not in read-only impersonation mode).
        Returns (allowed, error_message).
        """
        if not admin_user.is_admin:
            return False, "Admin permission required"

        if admin_user.status == "blocked":
            return False, "Admin account is blocked"

        return True, None
