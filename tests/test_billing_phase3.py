"""
Phase 3 billing enforcement tests - plan limits, feature gating, trial expiry.
Tests server-side hard blocks for LinkedIn accounts, campaigns, and features.
"""

import pytest
from datetime import datetime, timezone as tz, timedelta
from unittest.mock import patch, MagicMock

from openoutreach.billing.enforcement import PlanEnforcer, user_has_feature
from openoutreach.billing.credential_validator import LinkedInCredentialValidator
from openoutreach.billing.trial_expiry import expire_trials
from openoutreach.billing.downgrade_handler import handle_plan_downgrade
from openoutreach.mongodb.models_user import User


class TestPlanEnforcer:
    """Tests for plan enforcement and limits."""

    def test_can_create_linkedin_account_inactive_subscription(self):
        """Test that inactive subscription blocks account creation."""
        user = User(
            _id="test_user",
            email="test@example.com",
            subscription_status="none",
            linkedin_account_limit=1,
        )

        can_create, error = PlanEnforcer.can_create_linkedin_account(user)
        assert can_create is False
        assert "not active" in error.lower()

    def test_has_feature_all_plans_have_ai_messages(self):
        """Test that all plans include ai_messages feature."""
        for plan_name in ["starter", "pro", "business", "agency", "lifetime"]:
            user = User(_id="test", email="test@example.com", plan=plan_name)
            assert PlanEnforcer.has_feature(user, "ai_messages") is True

    def test_has_feature_pro_plus_only(self):
        """Test pro-only features are not in starter plan."""
        starter_user = User(_id="test", email="test@example.com", plan="starter")
        pro_user = User(_id="test", email="test@example.com", plan="pro")

        assert PlanEnforcer.has_feature(starter_user, "api_access") is False
        assert PlanEnforcer.has_feature(pro_user, "api_access") is True

    def test_has_feature_business_only(self):
        """Test business-only features."""
        pro_user = User(_id="test", email="test@example.com", plan="pro")
        business_user = User(_id="test", email="test@example.com", plan="business")

        assert PlanEnforcer.has_feature(pro_user, "team_members") is False
        assert PlanEnforcer.has_feature(business_user, "team_members") is True

    def test_has_feature_agency_only(self):
        """Test agency-only features."""
        business_user = User(_id="test", email="test@example.com", plan="business")
        agency_user = User(_id="test", email="test@example.com", plan="agency")

        assert PlanEnforcer.has_feature(business_user, "white_label") is False
        assert PlanEnforcer.has_feature(agency_user, "white_label") is True

    def test_can_run_tasks_blocked_user(self):
        """Test that blocked users cannot run tasks."""
        user = User(
            _id="test_user",
            email="test@example.com",
            status="blocked",
            subscription_status="active",
        )

        can_run, error = PlanEnforcer.can_run_tasks(user)
        assert can_run is False
        assert "blocked" in error.lower()

    def test_can_run_tasks_expired_subscription(self):
        """Test that expired subscriptions cannot run tasks."""
        user = User(
            _id="test_user",
            email="test@example.com",
            status="active",
            subscription_status="expired",
        )

        can_run, error = PlanEnforcer.can_run_tasks(user)
        assert can_run is False
        assert "not active" in error.lower()

    def test_trial_days_remaining_calculation(self):
        """Test trial days remaining calculation."""
        future = datetime.now(tz.utc) + timedelta(days=2, hours=5)
        user = User(
            _id="test",
            email="test@example.com",
            subscription_status="trialing",
            trial_ends_at=future,
        )

        days = PlanEnforcer._get_trial_days_remaining(user)
        assert days == 2

    def test_trial_days_expired(self):
        """Test trial that has expired."""
        past = datetime.now(tz.utc) - timedelta(days=1)
        user = User(
            _id="test",
            email="test@example.com",
            subscription_status="trialing",
            trial_ends_at=past,
        )

        is_active = PlanEnforcer._is_subscription_active(user)
        assert is_active is False


class TestLinkedInCredentialValidator:
    """Tests for LinkedIn account uniqueness validation."""

    @patch("openoutreach.billing.credential_validator.get_mongodb_collection")
    def test_linkedin_account_available(self, mock_get_collection):
        """Test that unused LinkedIn account is available."""
        mock_collection = MagicMock()
        mock_collection.find_one.return_value = None
        mock_get_collection.return_value = mock_collection

        is_available, error = LinkedInCredentialValidator.is_linkedin_account_available(
            "john.doe"
        )

        assert is_available is True
        assert error is None

    @patch("openoutreach.billing.credential_validator.get_mongodb_collection")
    def test_linkedin_account_taken(self, mock_get_collection):
        """Test that used LinkedIn account is rejected."""
        mock_collection = MagicMock()
        mock_collection.find_one.return_value = {"_id": "existing", "user_id": "other_user"}
        mock_get_collection.return_value = mock_collection

        is_available, error = LinkedInCredentialValidator.is_linkedin_account_available(
            "john.doe"
        )

        assert is_available is False
        assert "already connected" in error.lower()

    @patch("openoutreach.billing.credential_validator.get_mongodb_collection")
    def test_linkedin_account_same_user_allowed(self, mock_get_collection):
        """Test that same user can reuse own username (update case)."""
        mock_collection = MagicMock()
        mock_collection.find_one.return_value = None
        mock_get_collection.return_value = mock_collection

        is_available, _ = LinkedInCredentialValidator.is_linkedin_account_available(
            "john.doe",
            exclude_user_id="same_user",
        )

        assert is_available is True


class TestTrialExpiry:
    """Tests for trial expiry enforcement."""

    @patch("openoutreach.billing.trial_expiry.get_mongodb_collection")
    def test_expire_trials_updates_expired(self, mock_get_collection):
        """Test that expired trials are marked as expired."""
        mock_collection = MagicMock()
        mock_collection.update_many.return_value = MagicMock(modified_count=3)
        mock_get_collection.return_value = mock_collection

        result = expire_trials()

        assert result["expired"] == 3
        assert result["error"] is False
        mock_collection.update_many.assert_called_once()


class TestDowngradeHandler:
    """Tests for plan downgrade profile deactivation."""

    @patch("openoutreach.billing.downgrade_handler.get_mongodb_collection")
    def test_deactivate_excess_profiles(self, mock_get_collection):
        """Test that excess profiles are deactivated on downgrade."""
        mock_collection = MagicMock()
        mock_collection.find.return_value = [
            {"_id": "p1", "created_at": datetime.now(tz.utc)},
            {"_id": "p2", "created_at": datetime.now(tz.utc) + timedelta(hours=1)},
            {"_id": "p3", "created_at": datetime.now(tz.utc) + timedelta(hours=2)},
        ]
        mock_collection.update_many.return_value = MagicMock(modified_count=2)
        mock_get_collection.return_value = mock_collection

        user = User(_id="test_user", email="test@example.com")
        result = handle_plan_downgrade(user, new_limit=1)

        assert result["deactivated"] == 2
        assert result["error"] is False

    @patch("openoutreach.billing.downgrade_handler.get_mongodb_collection")
    def test_no_deactivation_if_under_limit(self, mock_get_collection):
        """Test that no deactivation happens if under limit."""
        mock_collection = MagicMock()
        mock_collection.find.return_value = [
            {"_id": "p1", "created_at": datetime.now(tz.utc)},
        ]
        mock_get_collection.return_value = mock_collection

        user = User(_id="test_user", email="test@example.com")
        result = handle_plan_downgrade(user, new_limit=1)

        assert result["deactivated"] == 0
        mock_collection.update_many.assert_not_called()


class TestUserHasFeatureUtility:
    """Tests for user_has_feature utility function."""

    def test_user_has_feature_wrapper(self):
        """Test the user_has_feature utility wrapper."""
        user = User(_id="test", email="test@example.com", plan="pro")
        assert user_has_feature(user, "api_access") is True
        assert user_has_feature(user, "white_label") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
