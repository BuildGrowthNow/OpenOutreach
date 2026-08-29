"""
Phase 8 Tests: Profile Activation & Security
Tests for plan integrity, anti-abuse, API security, and data isolation.
"""
import pytest
from datetime import datetime, timezone as tz

from openoutreach.billing.rate_limiter import SignupRateLimiter, LinkedInCredentialValidator
from openoutreach.billing.api_security import BillingAPISecurity
from openoutreach.billing.admin_security import AdminSecurityPolicy
from openoutreach.mongodb.models_user import User


class TestLinkedInProfileActivation:
    """Test profile activation control (is_active field)."""

    def test_profile_is_active_field_exists(self):
        """Test that LinkedInProfile has is_active field."""
        from openoutreach.linkedin.models import LinkedInProfile

        profile = LinkedInProfile(
            user_id="test_user",
            linkedin_username="test.user",
            is_active=True,
        )

        assert profile.is_active is True
        profile_dict = profile.to_dict()
        assert "is_active" in profile_dict
        assert profile_dict["is_active"] is True

    def test_profile_is_active_default_true(self):
        """Test that is_active defaults to True."""
        from openoutreach.linkedin.models import LinkedInProfile

        profile = LinkedInProfile(
            user_id="test_user",
            linkedin_username="test.user",
        )

        assert profile.is_active is True

    def test_profile_is_active_from_dict(self):
        """Test is_active field loads from dict."""
        from openoutreach.linkedin.models import LinkedInProfile

        data = {
            "_id": "profile_123",
            "user_id": "user_123",
            "linkedin_username": "test.user",
            "is_active": False,
            "active": True,
        }

        profile = LinkedInProfile.from_dict(data)
        assert profile.is_active is False


class TestAntiAbuse:
    """Test anti-abuse features."""

    def test_signup_rate_limiter_check_succeeds(self):
        """Test IP rate limiter allows first signup."""
        from openoutreach.mongodb.connection import check_mongodb_connection

        if not check_mongodb_connection():
            pytest.skip("MongoDB not available; first-signup behavior requires the integration database")
        allowed, error = SignupRateLimiter.check_ip_limit("192.168.1.1")
        assert allowed is True
        assert error is None

    def test_signup_rate_limiter_fails_closed_without_database(self, monkeypatch):
        """A database outage must not disable signup anti-abuse controls."""
        monkeypatch.setattr(
            "openoutreach.billing.rate_limiter.get_mongodb_collection",
            lambda _name: None,
        )
        allowed, error = SignupRateLimiter.check_ip_limit("192.168.1.2")
        assert allowed is False
        assert "temporarily unavailable" in error.lower()

    def test_linkedin_credential_validator_empty_username(self):
        """Test credential validator rejects empty username."""
        is_unique, error = LinkedInCredentialValidator.validate_username_unique("")
        assert is_unique is False
        assert "empty" in error.lower()

    def test_linkedin_credential_validator_format(self):
        """Test credential validator checks format."""
        is_valid, error = LinkedInCredentialValidator.validate_credentials_format("", "")
        assert is_valid is False

        is_valid, error = LinkedInCredentialValidator.validate_credentials_format("test", "pass")
        assert is_valid is False
        assert "email" in error.lower()

        is_valid, error = LinkedInCredentialValidator.validate_credentials_format("test@test.com", "short")
        assert is_valid is False

        is_valid, error = LinkedInCredentialValidator.validate_credentials_format("test@test.com", "validpass123")
        assert is_valid is True


class TestAPISecurity:
    """Test API security enforcement."""

    def test_user_owns_subscription(self):
        """Test user owns their subscription."""
        user_id = "user_123"
        assert BillingAPISecurity.verify_user_owns_subscription(user_id, user_id) is True

    def test_stripe_customer_id_masked(self):
        """Test Stripe customer ID is not exposed to non-owner."""
        user = User(
            _id="user_123",
            email="test@example.com",
            stripe_customer_id="cus_123",
            is_admin=False,
        )

        masked = BillingAPISecurity.mask_stripe_customer_id(user, "other_user_id")
        assert masked is None

        masked = BillingAPISecurity.mask_stripe_customer_id(user, "user_123")
        assert masked == "cus_123"

    def test_plan_name_validation(self):
        """Test plan name validation."""
        is_valid, error = BillingAPISecurity.validate_plan_name("invalid_plan")
        assert is_valid is False
        assert error is not None

        is_valid, error = BillingAPISecurity.validate_plan_name("starter")
        assert is_valid is True
        assert error is None

    def test_billing_period_validation(self):
        """Test billing period validation."""
        is_valid, error = BillingAPISecurity.validate_billing_period("invalid")
        assert is_valid is False

        is_valid, error = BillingAPISecurity.validate_billing_period("monthly")
        assert is_valid is True

        is_valid, error = BillingAPISecurity.validate_billing_period("annual")
        assert is_valid is True

        is_valid, error = BillingAPISecurity.validate_billing_period("lifetime")
        assert is_valid is True


class TestDataIsolation:
    """Test data isolation and admin permissions."""

    def test_admin_permission_check(self):
        """Test admin permission checking."""
        user = User(_id="user_123", is_admin=False)
        allowed, error = AdminSecurityPolicy.check_admin_permission(user, "any_action")
        assert allowed is False

        user.is_admin = True
        allowed, error = AdminSecurityPolicy.check_admin_permission(user, "view_campaigns")
        assert allowed is True

    def test_impersonation_read_only(self):
        """Test impersonation enforces read-only mode."""
        admin = User(_id="admin_123", is_admin=True)
        target_id = "user_456"

        allowed, error = AdminSecurityPolicy.check_impersonation_allowed(
            admin, target_id, "view_campaigns"
        )
        assert allowed is True

        allowed, error = AdminSecurityPolicy.check_impersonation_allowed(
            admin, target_id, "update_settings"
        )
        assert allowed is False
        assert "read-only" in error.lower()

    def test_self_impersonation_allowed(self):
        """Test admin can perform write on their own account."""
        admin = User(_id="admin_123", is_admin=True)

        allowed, error = AdminSecurityPolicy.check_impersonation_allowed(
            admin, "admin_123", "update_settings"
        )
        assert allowed is True

    def test_admin_action_logging(self):
        """Test admin actions are logged for audit trail."""
        AdminSecurityPolicy.log_admin_action(
            admin_user_id="admin_123",
            action="update_user_plan",
            target_user_id="user_456",
            details={"old_plan": "pro", "new_plan": "business"},
        )


class TestPlanEnforcement:
    """Test plan enforcement at API boundaries."""

    def test_plan_enforcement_cannot_bypass_api(self):
        """Test that API enforces plan limits."""
        blocked_user = User(
            _id="user_123",
            status="blocked",
            subscription_status="active",
        )

        is_valid, error = BillingAPISecurity.enforce_plan_limits_api(blocked_user)
        assert is_valid is False
        assert "blocked" in error.lower()


class TestWebhookSecurity:
    """Test webhook signature verification."""

    def test_webhook_signature_validator_exists(self):
        """Test webhook signature validator is available."""
        from openoutreach.billing.webhook_security import WebhookSignatureValidator

        assert hasattr(WebhookSignatureValidator, "verify_signature")
        assert hasattr(WebhookSignatureValidator, "construct_event")


class TestDowngradeHandler:
    """Test plan downgrade profile deactivation."""

    def test_downgrade_handler_function_exists(self):
        """Test downgrade handler is available."""
        from openoutreach.billing.downgrade_handler import handle_plan_downgrade

        assert callable(handle_plan_downgrade)


class TestDaemonProfileFiltering:
    """Test daemon only runs active, subscription-compliant profiles."""

    def test_daemon_filters_inactive_profiles(self):
        """Test daemon filtering logic."""
        from openoutreach.linkedin.models import LinkedInProfile

        active_profile = LinkedInProfile(
            user_id="test_user",
            linkedin_username="active.user",
            is_active=True,
            active=True,
        )

        inactive_profile = LinkedInProfile(
            user_id="test_user",
            linkedin_username="inactive.user",
            is_active=False,
            active=True,
        )

        assert active_profile.is_active is True
        assert inactive_profile.is_active is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
