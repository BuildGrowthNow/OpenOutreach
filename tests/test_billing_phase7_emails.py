"""
Tests for Phase 7: Billing emails.
"""
import pytest
from datetime import datetime, timezone as tz
from unittest.mock import Mock, patch

from openoutreach.mongodb.models_user import User
from openoutreach.billing.emails import (
    send_welcome_email,
    send_trial_expiry_warning,
    send_trial_expired,
    send_plan_upgraded,
    send_plan_downgraded,
    send_payment_failed,
    send_account_blocked,
    send_lifetime_deal_purchase,
    ResendProvider,
    SMTPProvider,
    SESProvider,
)


@pytest.fixture
def mock_user():
    """Create a mock user for testing."""
    return User(
        _id="test-user-123",
        email="test@example.com",
        full_name="Test User",
        plan="starter",
        subscription_status="trialing",
        trial_ends_at=datetime.now(tz.utc),
        linkedin_account_limit=1,
        campaign_limit=3,
    )


class TestEmailProviders:
    """Test email provider implementations."""

    @patch("builtins.__import__", side_effect=__import__)
    def test_resend_provider_init(self, _mock_import):
        """Test Resend provider initialization."""
        with patch("openoutreach.billing.emails.ResendProvider.send"):
            provider = ResendProvider(
                api_key="test_key",
                from_address="noreply@test.com",
                from_name="Test",
            )
            assert provider.api_key == "test_key"
            assert provider.from_address == "noreply@test.com"
            assert provider.from_name == "Test"

    def test_smtp_provider_init(self):
        """Test SMTP provider initialization."""
        provider = SMTPProvider(
            host="smtp.example.com",
            port=587,
            username="user@example.com",
            password="password",
            from_address="noreply@test.com",
            from_name="Test",
        )
        assert provider.host == "smtp.example.com"
        assert provider.port == 587
        assert provider.username == "user@example.com"

    def test_smtp_provider_handles_none_values(self):
        """Test SMTP provider handles None values gracefully."""
        provider = SMTPProvider(
            host=None,
            port=587,
            username=None,
            password=None,
            from_address="noreply@test.com",
            from_name="Test",
        )
        assert provider.host == ""
        assert provider.username == ""
        assert provider.password == ""

    @patch("builtins.__import__")
    def test_ses_provider_init(self, mock_import):
        """Test SES provider initialization."""
        mock_import.side_effect = ImportError("boto3 not available")
        provider = SESProvider(
            from_address="noreply@test.com",
            from_name="Test",
        )
        assert provider.from_address == "noreply@test.com"
        assert provider.from_name == "Test"
        assert provider.ses_client is None


class TestEmailFunctions:
    """Test email sending functions."""

    @patch("openoutreach.billing.emails._send_billing_email")
    def test_welcome_email(self, mock_send, mock_user):
        """Test welcome email contains trial info."""
        mock_send.return_value = True
        result = send_welcome_email(mock_user)
        assert mock_send.called
        assert result is True

    @patch("openoutreach.billing.emails._send_billing_email")
    def test_trial_expiry_warning(self, mock_send, mock_user):
        """Test trial expiry warning email."""
        mock_send.return_value = True
        result = send_trial_expiry_warning(mock_user, 1)
        assert mock_send.called
        call_args = mock_send.call_args
        assert "trial ends tomorrow" in call_args[0][1].lower()
        assert result is True

    @patch("openoutreach.billing.emails._send_billing_email")
    def test_trial_expired(self, mock_send, mock_user):
        """Test trial expired notification email."""
        mock_send.return_value = True
        result = send_trial_expired(mock_user)
        assert mock_send.called
        call_args = mock_send.call_args
        assert "trial has ended" in call_args[0][1].lower()
        assert result is True

    @patch("openoutreach.billing.emails._send_billing_email")
    def test_plan_upgraded(self, mock_send, mock_user):
        """Test plan upgrade confirmation email."""
        mock_send.return_value = True
        mock_user.plan = "pro"
        result = send_plan_upgraded(mock_user, "starter", "pro")
        assert mock_send.called
        call_args = mock_send.call_args
        assert "pro" in call_args[0][1].lower()
        assert result is True

    @patch("openoutreach.billing.emails._send_billing_email")
    def test_plan_downgraded(self, mock_send, mock_user):
        """Test plan downgrade notification email."""
        mock_send.return_value = True
        effective_date = datetime.now(tz.utc)
        result = send_plan_downgraded(mock_user, "pro", "starter", effective_date)
        assert mock_send.called
        call_args = mock_send.call_args
        assert "plan change" in call_args[0][1].lower()
        assert result is True

    @patch("openoutreach.billing.emails._send_billing_email")
    def test_payment_failed(self, mock_send, mock_user):
        """Test payment failed notification email."""
        mock_send.return_value = True
        result = send_payment_failed(mock_user)
        assert mock_send.called
        call_args = mock_send.call_args
        assert "payment failed" in call_args[0][1].lower()
        assert result is True

    @patch("openoutreach.billing.emails._send_billing_email")
    def test_account_blocked(self, mock_send, mock_user):
        """Test account blocked notification email."""
        mock_send.return_value = True
        result = send_account_blocked(mock_user, "violating terms")
        assert mock_send.called
        call_args = mock_send.call_args
        assert "suspended" in call_args[0][1].lower()
        assert result is True

    @patch("openoutreach.billing.emails._send_billing_email")
    def test_lifetime_deal_purchase(self, mock_send, mock_user):
        """Test lifetime deal purchase confirmation email."""
        mock_send.return_value = True
        mock_user.plan = "lifetime"
        result = send_lifetime_deal_purchase(mock_user)
        assert mock_send.called
        call_args = mock_send.call_args
        assert "lifetime" in call_args[0][1].lower()
        assert result is True

    @patch("openoutreach.billing.emails._get_email_provider")
    def test_send_billing_email_no_email(self, _mock_get_provider, mock_user):
        """Test sending email when user has no email address."""
        mock_user.email = None
        from openoutreach.billing.emails import _send_billing_email

        result = _send_billing_email(mock_user, "Subject", "<html></html>", "text")
        assert result is False

    @patch("openoutreach.billing.emails._get_email_provider")
    def test_send_billing_email_no_provider(self, mock_get_provider, mock_user):
        """Test sending email when no provider is configured."""
        mock_get_provider.return_value = None
        from openoutreach.billing.emails import _send_billing_email

        result = _send_billing_email(mock_user, "Subject", "<html></html>", "text")
        assert result is False


class TestEmailScheduler:
    """Test email scheduler functions."""

    @patch("openoutreach.billing.email_scheduler.get_mongodb_collection")
    @patch("openoutreach.billing.email_scheduler.send_trial_expiry_warning")
    def test_send_trial_expiry_warnings(self, mock_send, mock_get_collection):
        """Test sending trial expiry warnings."""
        from openoutreach.billing.email_scheduler import send_trial_expiry_warnings

        mock_collection = Mock()
        mock_get_collection.return_value = mock_collection

        user_data = {
            "_id": "user-1",
            "email": "test@example.com",
            "full_name": "Test User",
            "subscription_status": "trialing",
        }
        mock_collection.find.return_value = [user_data]
        mock_send.return_value = True

        send_trial_expiry_warnings()
        assert mock_send.called

    @patch("openoutreach.billing.email_scheduler.get_mongodb_collection")
    @patch("openoutreach.billing.email_scheduler.send_trial_expired")
    def test_expire_trials(self, _mock_send, mock_get_collection):
        """Test expiring trials."""
        from openoutreach.billing.email_scheduler import expire_trials

        mock_collection = Mock()
        mock_get_collection.return_value = mock_collection
        mock_collection.update_many.return_value = Mock(modified_count=5)
        mock_collection.find.return_value = []

        result = expire_trials()
        assert mock_collection.update_many.called
        assert result == 5

    @patch("openoutreach.billing.email_scheduler.get_mongodb_collection")
    def test_send_account_blocked_notifications(self, mock_get_collection):
        """Test sending blocked account notifications."""
        from openoutreach.billing.email_scheduler import send_account_blocked_notifications

        mock_users_collection = Mock()
        mock_notifications_collection = Mock()

        def get_collection_side_effect(name):
            if name == "users":
                return mock_users_collection
            elif name == "blocked_notifications":
                return mock_notifications_collection
            return None

        mock_get_collection.side_effect = get_collection_side_effect

        user_data = {
            "_id": "user-1",
            "email": "test@example.com",
            "status": "blocked",
            "admin_notes": "Violation",
        }
        mock_users_collection.find.return_value = [user_data]
        mock_notifications_collection.find_one.return_value = None

        send_account_blocked_notifications()
        assert mock_users_collection.find.called
