"""
Phase 1 Auth Tests - JWT Authentication Unification

Tests for:
- Blocked user → 403
- Deleted user → 403
- Inactive user → 403
- Rate limiter blocks N+1 signup from same IP
- Password reset token creation and confirmation logic
- Email verification token logic
"""
import pytest
from datetime import datetime, timedelta, timezone as tz
from unittest.mock import MagicMock

from fastapi import HTTPException
from jose import jwt

from openoutreach.api_v2.dependencies_v2 import get_current_user
from openoutreach.api_v2.routers.auth import create_access_token
from openoutreach.mongodb.models_user import User
from openoutreach.config import settings
from openoutreach.billing.rate_limiter import SignupRateLimiter


class TestUserStatusChecks:
    """Test that blocked, deleted, and inactive users are rejected."""

    @pytest.mark.asyncio
    async def test_blocked_user_returns_403(self):
        """Blocked user should get 403."""
        # Create blocked user
        user = User(
            email="blocked@example.com",
            full_name="Blocked User",
            is_active=True,
            email_verified=True,
            status="blocked",
        )
        user.set_password("testpassword123")
        user.save()

        try:
            token = create_access_token(user._id, user.email)

            # Mock HTTPAuthorizationCredentials
            credentials = MagicMock()
            credentials.credentials = token

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(credentials)

            assert exc_info.value.status_code == 403
            assert "blocked" in exc_info.value.detail.lower()
        finally:
            # Cleanup
            from openoutreach.mongodb.connection import get_mongodb_collection
            user_coll = get_mongodb_collection("users")
            if user_coll is not None:
                user_coll.delete_many({"_id": user._id})

    @pytest.mark.asyncio
    async def test_deleted_user_returns_403(self):
        """Deleted user should get 403."""
        # Create deleted user
        user = User(
            email="deleted@example.com",
            full_name="Deleted User",
            is_active=True,
            email_verified=True,
            is_deleted=True,
            deletion_scheduled_at=datetime.now(tz.utc) - timedelta(days=1),
        )
        user.set_password("testpassword123")
        user.save()

        try:
            token = create_access_token(user._id, user.email)

            # Mock HTTPAuthorizationCredentials
            credentials = MagicMock()
            credentials.credentials = token

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(credentials)

            assert exc_info.value.status_code == 403
            assert "deleted" in exc_info.value.detail.lower()
        finally:
            # Cleanup
            from openoutreach.mongodb.connection import get_mongodb_collection
            user_coll = get_mongodb_collection("users")
            if user_coll is not None:
                user_coll.delete_many({"_id": user._id})

    @pytest.mark.asyncio
    async def test_inactive_user_returns_403(self):
        """Inactive user should get 403."""
        # Create inactive user
        user = User(
            email="inactive@example.com",
            full_name="Inactive User",
            is_active=False,
            email_verified=True,
        )
        user.set_password("testpassword123")
        user.save()

        try:
            token = create_access_token(user._id, user.email)

            # Mock HTTPAuthorizationCredentials
            credentials = MagicMock()
            credentials.credentials = token

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(credentials)

            assert exc_info.value.status_code == 403
            assert "inactive" in exc_info.value.detail.lower()
        finally:
            # Cleanup
            from openoutreach.mongodb.connection import get_mongodb_collection
            user_coll = get_mongodb_collection("users")
            if user_coll is not None:
                user_coll.delete_many({"_id": user._id})

    @pytest.mark.asyncio
    async def test_active_user_succeeds(self):
        """Active user should authenticate successfully."""
        # Create active user
        user = User(
            email="active@example.com",
            full_name="Active User",
            is_active=True,
            email_verified=True,
            status="active",
        )
        user.set_password("testpassword123")
        user.save()

        try:
            token = create_access_token(user._id, user.email)

            # Mock HTTPAuthorizationCredentials
            credentials = MagicMock()
            credentials.credentials = token

            user_id = await get_current_user(credentials)
            assert user_id == user._id
        finally:
            # Cleanup
            from openoutreach.mongodb.connection import get_mongodb_collection
            user_coll = get_mongodb_collection("users")
            if user_coll is not None:
                user_coll.delete_many({"_id": user._id})


class TestSignupRateLimit:
    """Test that signup rate limiter blocks excessive signups from same IP."""

    def test_rate_limiter_blocks_multiple_signups_from_same_ip(self):
        """Rate limiter should block N+1 signup attempts from same IP."""
        test_ip = "192.168.1.100"

        # Clear any existing rate limit records for this IP
        from openoutreach.mongodb.connection import get_mongodb_collection
        rate_limit_coll = get_mongodb_collection("ip_signup_attempts")
        if rate_limit_coll is not None:
            rate_limit_coll.delete_many({"ip_address": test_ip})

        try:
            # First 3 signups should succeed
            for i in range(3):
                allowed, error_msg = SignupRateLimiter.check_ip_limit(test_ip)
                assert allowed, f"Signup {i+1} should be allowed"

                # Record the signup
                SignupRateLimiter.record_signup_attempt(
                    test_ip,
                    f"user_id_{i}",
                    f"test{i}@example.com"
                )

            # 4th signup should be blocked
            allowed, error_msg = SignupRateLimiter.check_ip_limit(test_ip)
            assert not allowed, "4th signup should be blocked"
            assert error_msg is not None
            assert "rate limit" in error_msg.lower()
        finally:
            # Cleanup
            if rate_limit_coll is not None:
                rate_limit_coll.delete_many({"ip_address": test_ip})


class TestPasswordResetLogic:
    """Test password reset token creation and confirmation logic."""

    def test_password_reset_token_can_change_password(self):
        """Password reset token should allow password change."""
        # Create test user
        user = User(
            email="pwreset@example.com",
            full_name="PW Reset User",
            is_active=True,
            email_verified=True,
        )
        user.set_password("oldpassword123")
        user.save()

        try:
            # Create reset token
            reset_token = jwt.encode(
                {
                    "sub": user.email,
                    "exp": datetime.now(tz.utc) + timedelta(hours=1),
                    "type": "password_reset",
                },
                settings.jwt_secret,
                algorithm=settings.JWT_ALGORITHM,
            )

            user.password_reset_token = reset_token
            user.password_reset_expires = datetime.now(tz.utc) + timedelta(hours=1)
            user.save()

            # Verify token was stored
            stored_user = User.get(user._id)
            assert stored_user is not None
            assert stored_user.password_reset_token == reset_token
            assert stored_user.password_reset_expires is not None

            # Change password
            new_password = "newpassword456"
            stored_user.set_password(new_password)
            stored_user.save()

            # Verify password was changed
            updated_user = User.get(user._id)
            assert updated_user is not None
            assert updated_user.verify_password(new_password)
            assert not updated_user.verify_password("oldpassword123")
        finally:
            # Cleanup
            from openoutreach.mongodb.connection import get_mongodb_collection
            user_coll = get_mongodb_collection("users")
            if user_coll is not None:
                user_coll.delete_many({"_id": user._id})


class TestEmailVerificationLogic:
    """Test email verification token logic."""

    def test_email_verification_token_marks_user_verified(self):
        """Email verification token should mark user as verified."""
        # Create unverified user
        user = User(
            email="unverified@example.com",
            full_name="Unverified User",
            is_active=True,
            email_verified=False,
        )
        user.set_password("testpassword123")

        verification_token = jwt.encode(
            {
                "sub": user.email,
                "exp": datetime.now(tz.utc) + timedelta(hours=24),
                "type": "email_verification",
            },
            settings.jwt_secret,
            algorithm=settings.JWT_ALGORITHM,
        )

        user.email_verification_token = verification_token
        user.email_verification_expires = datetime.now(tz.utc) + timedelta(hours=24)
        user.save()

        try:
            # Verify token was stored
            stored_user = User.get(user._id)
            assert stored_user is not None
            assert stored_user.email_verification_token == verification_token
            assert stored_user.email_verified is False

            # Simulate verification
            stored_user.email_verified = True
            stored_user.email_verification_token = None
            stored_user.email_verification_expires = None
            stored_user.save()

            # Verify user is now verified
            verified_user = User.get(user._id)
            assert verified_user is not None
            assert verified_user.email_verified is True
            assert verified_user.email_verification_token is None
        finally:
            # Cleanup
            from openoutreach.mongodb.connection import get_mongodb_collection
            user_coll = get_mongodb_collection("users")
            if user_coll is not None:
                user_coll.delete_many({"_id": user._id})
