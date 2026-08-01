"""
FastAPI Auth Router - Multi-Tenant

Implements JWT authentication with proper security:
- Local auth (email + password)
- HTTP-only refresh tokens
- Password reset flow
"""

import logging
from datetime import datetime, timedelta, timezone as tz
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from jose import jwt, JWTError

from openoutreach.config import settings
from openoutreach.api_v2.dependencies_v2 import get_current_user
from openoutreach.api_v2.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
    PasswordResetRequest,
    PasswordResetConfirm,
    PasswordUpdate,
    EmailVerifyRequest,
)
from openoutreach.mongodb.models_user import User
from openoutreach.mongodb import models
from openoutreach.billing.account_lifecycle import (
    request_account_deletion,
    cancel_account_deletion,
    export_user_data,
)
from openoutreach.billing.emails import send_email_verification, send_password_reset

logger = logging.getLogger(__name__)
router = APIRouter()


def _extract_client_ip(request: Request) -> Optional[str]:
    """Extract the real client IP, respecting X-Forwarded-For from proxies."""
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded:
        return forwarded
    return request.client.host if request.client else None


async def _send_password_reset_email(user: User) -> bool:
    """Generate a password reset token and send the reset email. Returns True on success."""
    from datetime import timedelta
    reset_token = jwt.encode(
        {
            "sub": user.email,
            "exp": datetime.now(tz.utc) + timedelta(hours=24),
            "type": "password_reset",
        },
        settings.jwt_secret,
        algorithm=settings.JWT_ALGORITHM,
    )
    user.password_reset_token = reset_token
    user.password_reset_expires = datetime.now(tz.utc) + timedelta(hours=24)
    user.save()

    app_url = settings.APP_URL or "http://localhost:3000"
    reset_url = f"{app_url}/reset-password?token={reset_token}"
    email_sent = send_password_reset(user, reset_url)
    if not email_sent:
        logger.error(f"Failed to send password reset email to {user.email}")
    return email_sent


def create_access_token(user_id: str, email: str) -> str:
    """Create JWT access token."""
    expires = timedelta(minutes=settings.JWT_ACCESS_TOKEN_LIFETIME_MINUTES)
    now = datetime.now(tz.utc)
    expire = now + expires

    payload = {
        "sub": user_id,
        "email": email,
        "exp": expire,
        "iat": now,
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    """Create JWT refresh token."""
    expires = timedelta(days=settings.JWT_REFRESH_TOKEN_LIFETIME_DAYS)
    now = datetime.now(tz.utc)
    expire = now + expires

    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": now,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.JWT_ALGORITHM)


# ==================== REGISTER ====================


@router.post("/register/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, request: Request):
    """
    Register a new user account.

    Creates user + default SiteConfig.
    Returns user info (client must call /login to get tokens).
    """
    # Check IP rate limit
    from openoutreach.billing.rate_limiter import SignupRateLimiter

    client_ip = _extract_client_ip(request) or "unknown"
    allowed, error_msg = SignupRateLimiter.check_ip_limit(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=error_msg or "Rate limit exceeded"
        )

    # Check if email already exists
    existing_user = User.get_by_email(data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create user with subscription_status=none (no subscription until checkout)
    # Email verification required before trial
    verification_token = jwt.encode(
        {
            "sub": data.email,
            "exp": datetime.now(tz.utc) + timedelta(hours=24),
            "type": "email_verification",
        },
        settings.jwt_secret,
        algorithm=settings.JWT_ALGORITHM,
    )

    signup_ip = _extract_client_ip(request)
    user = User(
        email=data.email,
        full_name=data.full_name,
        is_active=True,
        subscription_status="none",
        email_verified=False,
        email_verification_token=verification_token,
        email_verification_expires=datetime.now(tz.utc) + timedelta(hours=24),
        signup_ip=signup_ip,
    )
    user.set_password(data.password)
    user.save()

    # Record signup attempt for IP tracking
    from openoutreach.billing.rate_limiter import SignupRateLimiter
    SignupRateLimiter.record_signup_attempt(client_ip, user._id, user.email)

    # Create default SiteConfig for user
    try:
        site_config = models.SiteConfig(user_id=user._id)
        site_config.save()
    except Exception as e:
        logger.warning(f"Failed to create SiteConfig for {user.email}: {e}")

    # Send verification email
    app_url = settings.APP_URL or "http://localhost:3000"
    verification_url = f"{app_url}/verify-email?token={verification_token}"
    email_sent = send_email_verification(user, verification_url)

    if not email_sent:
        logger.error(f"Failed to send verification email to {user.email}")

    logger.info(f"New user registered: {user.email}")

    return UserResponse(
        id=user._id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        created_at=user.created_at or datetime.now(tz.utc),
        status=user.status,
        admin_notes=user.admin_notes,
        is_admin=user.is_admin,
        admin_role=user.admin_role,
    )


# ==================== LOGIN ====================


@router.post("/login/", response_model=TokenResponse)
async def login(credentials: LoginRequest, response: Response, request: Request):
    """
    Authenticate user with email and password.

    Returns access token + sets HTTP-only refresh token cookie.
    """
    # Find user by email
    user = User.get_by_email(credentials.email)
    if not user:
        logger.warning(f"Login failed: user not found for {credentials.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    # Check if user has a password (local auth)
    if not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This account uses SSO authentication"
        )

    # Verify password
    if not user.verify_password(credentials.password):
        logger.warning(f"Login failed: incorrect password for {credentials.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    # Reject unverified users
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email before logging in"
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )

    # Check if user is deleted
    if user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been deleted"
        )

    # Update last login and capture IP
    user.update_last_login(ip=_extract_client_ip(request))

    # Create tokens
    access_token = create_access_token(user._id, user.email)
    refresh_token = create_refresh_token(user._id)

    # Set refresh token in HTTP-only cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=not settings.DEBUG,  # HTTPS in production
        samesite="lax",
        max_age=settings.JWT_REFRESH_TOKEN_LIFETIME_DAYS * 24 * 60 * 60,
        path="/",
    )

    # Set readable billing_status cookie so Next.js middleware can gate pages
    # without a network round-trip. Not HTTP-only — intentionally readable by JS.
    response.set_cookie(
        key="billing_status",
        value=user.subscription_status or "none",
        httponly=False,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=settings.JWT_REFRESH_TOKEN_LIFETIME_DAYS * 24 * 60 * 60,
        path="/",
    )

    logger.info(f"User login successful: {user.email}")

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_LIFETIME_MINUTES * 60
    )


# ==================== REFRESH TOKEN ====================


@router.post("/refresh/", response_model=TokenResponse)
async def refresh_token(request: Request, response: Response):
    """
    Refresh access token.

    Accepts refresh token from HTTP-only cookie (web) or JSON body (desktop daemon).
    """
    # Prefer cookie (web); fall back to JSON body (desktop)
    refresh_token = request.cookies.get("refresh_token")

    if not refresh_token:
        try:
            body = await request.json()
            refresh_token = body.get("refresh_token")
        except Exception:
            pass

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required"
        )

    try:
        # Decode and verify refresh token
        payload = jwt.decode(
            refresh_token,
            settings.jwt_secret,
            algorithms=[settings.JWT_ALGORITHM]
        )

        # Verify token type
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )

        # Verify user still exists and is active
        user = User.get(user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )

        # Create new access token
        access_token = create_access_token(user._id, user.email)

        # Keep billing_status cookie in sync with current subscription state
        response.set_cookie(
            key="billing_status",
            value=user.subscription_status or "none",
            httponly=False,
            secure=not settings.DEBUG,
            samesite="lax",
            max_age=settings.JWT_REFRESH_TOKEN_LIFETIME_DAYS * 24 * 60 * 60,
            path="/",
        )

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            refresh_token=None,
            expires_in=settings.JWT_ACCESS_TOKEN_LIFETIME_MINUTES * 60
        )

    except JWTError as e:
        logger.warning(f"Token refresh failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )


# ==================== GET CURRENT USER ====================


@router.get("/me/", response_model=UserResponse)
async def get_current_user_info(user_id: str = Depends(get_current_user)):
    """
    Get current authenticated user information.

    Requires valid access token.
    """
    user = User.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return UserResponse(
        id=user._id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        created_at=user.created_at or datetime.now(tz.utc),
        status=user.status,
        admin_notes=user.admin_notes,
        is_admin=user.is_admin,
        admin_role=user.admin_role,
    )


# ==================== LOGOUT ====================


@router.post("/logout/")
async def logout(response: Response, user_id: str = Depends(get_current_user)):
    """
    Logout user by clearing refresh token cookie.

    Access token remains valid until expiration (client should discard it).
    """
    # Clear auth and billing cookies
    response.delete_cookie(key="refresh_token", path="/")
    response.delete_cookie(key="billing_status", path="/")

    logger.info(f"User logged out: {user_id}")

    return {"status": "success", "message": "Successfully logged out"}


# ==================== EMAIL VERIFICATION ====================


@router.post("/verify-email/")
async def verify_email(body: EmailVerifyRequest):
    """
    Verify user email with token from verification link.
    """
    token = body.token
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.JWT_ALGORITHM]
        )

        if payload.get("type") != "email_verification":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token type"
            )

        email = payload.get("sub")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token"
            )

        user = User.get_by_email(email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User not found"
            )

        if user.email_verified:
            return {"status": "success", "message": "Email already verified"}

        user.email_verified = True
        user.email_verification_token = None
        user.email_verification_expires = None

        # Auto-start trial so verified users can use the app immediately
        if user.subscription_status == "none":
            from openoutreach.billing.config import get_trial_duration_days
            from openoutreach.billing.plans import get_plan
            trial_days = get_trial_duration_days()
            user.subscription_status = "trialing"
            user.plan = user.plan or "starter"
            user.trial_ends_at = datetime.now(tz.utc) + timedelta(days=trial_days)
            plan_def = get_plan(user.plan)
            if plan_def:
                user.linkedin_account_limit = plan_def["max_linkedin_accounts"]
                user.campaign_limit = plan_def["max_campaigns"]

        user.save()

        logger.info(f"Email verified for user: {email}")

        return {"status": "success", "message": "Email verified successfully"}

    except JWTError as e:
        logger.warning(f"Email verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Email verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred. Please try again."
        )


@router.post("/resend-verification/")
async def resend_verification(email: str, request: Request):
    """
    Resend email verification link.

    Always returns success to prevent email enumeration.
    """
    from openoutreach.billing.rate_limiter import EmailRateLimiter

    client_ip = _extract_client_ip(request) or "unknown"
    allowed, error_msg = EmailRateLimiter.check(client_ip, "resend-verification")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=error_msg or "Rate limit exceeded"
        )

    try:
        user = User.get_by_email(email)

        EmailRateLimiter.record(client_ip, "resend-verification")

        if user and not user.email_verified:
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

            app_url = settings.APP_URL or "http://localhost:3000"
            verification_url = f"{app_url}/verify-email?token={verification_token}"
            email_sent = send_email_verification(user, verification_url)

            if not email_sent:
                logger.error(f"Failed to resend verification email to {user.email}")

            logger.info(f"Verification email resent to: {email}")

        return {"status": "success", "message": "If an unverified account exists, a verification link has been sent"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resend verification error: {e}")
        return {"status": "success", "message": "If an unverified account exists, a verification link has been sent"}


# ==================== PASSWORD RESET REQUEST ====================


@router.post("/password-reset/request/")
async def password_reset_request(request: PasswordResetRequest, http_request: Request):
    """
    Request a password reset.

    Always returns success to prevent email enumeration attacks.
    Sends email with reset link.
    """
    from openoutreach.billing.rate_limiter import EmailRateLimiter

    client_ip = _extract_client_ip(http_request) or "unknown"
    allowed, error_msg = EmailRateLimiter.check(client_ip, "password-reset")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=error_msg or "Rate limit exceeded"
        )

    try:
        EmailRateLimiter.record(client_ip, "password-reset")

        user = User.get_by_email(request.email)

        if user and user.hashed_password:
            await _send_password_reset_email(user)
            logger.info(f"Password reset requested for: {request.email}")

        return {"status": "success", "message": "If an account exists, a reset link has been sent"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password reset request error: {e}")
        return {"status": "success", "message": "If an account exists, a reset link has been sent"}


# ==================== PASSWORD RESET CONFIRM ====================


@router.post("/password-reset/confirm/")
async def password_reset_confirm(request: PasswordResetConfirm):
    """
    Confirm password reset with token and new password.
    """
    try:
        # Decode and verify token
        payload = jwt.decode(
            request.token,
            settings.jwt_secret,
            algorithms=[settings.JWT_ALGORITHM]
        )

        # Verify token type
        if payload.get("type") != "password_reset":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token type"
            )

        email = payload.get("sub")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token"
            )

        # Find user
        user = User.get_by_email(email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token"
            )

        # Update password
        user.set_password(request.new_password)
        user.save()

        logger.info(f"Password reset successful for: {email}")

        return {"status": "success", "message": "Password successfully reset"}

    except JWTError as e:
        logger.warning(f"Password reset confirm failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password reset confirm error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred. Please try again."
        )


# ==================== UPDATE PASSWORD ====================


@router.post("/update-password/")
async def update_password(
    request: PasswordUpdate,
    user_id: str = Depends(get_current_user)
):
    """
    Update password for authenticated user.

    Requires current password verification.
    """
    user = User.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Check if user has a password (local auth only)
    if not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account uses SSO authentication"
        )

    # Verify old password
    if not user.verify_password(request.old_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    # Update password
    user.set_password(request.new_password)
    user.save()

    logger.info(f"Password updated for user: {user.email}")

    return {"status": "success", "message": "Password successfully updated"}


# ==================== ACCOUNT LIFECYCLE ====================


@router.post("/account/request-deletion/")
async def request_deletion(user_id: str = Depends(get_current_user)):
    """
    Request account deletion with 30-day grace period.

    Cancels subscription and deactivates all profiles immediately.
    User can recover account by logging in within 30 days.
    """
    try:
        result = request_account_deletion(user_id)
        logger.info(f"Deletion requested for user: {user_id}")
        return result
    except Exception as e:
        logger.error(f"Deletion request error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process deletion request"
        )


@router.post("/account/cancel-deletion/")
async def cancel_deletion(user_id: str = Depends(get_current_user)):
    """
    Cancel account deletion during 30-day grace period.

    Reactivates account and user data.
    """
    try:
        result = cancel_account_deletion(user_id)
        logger.info(f"Deletion canceled for user: {user_id}")
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Cancel deletion error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel deletion"
        )


@router.get("/account/export-data/")
async def export_data(user_id: str = Depends(get_current_user)):
    """
    Export all user data in JSON format (GDPR compliance).

    Returns user profile, billing info, campaigns, leads, messages, etc.
    """
    try:
        data = export_user_data(user_id)
        logger.info(f"Data exported for user: {user_id}")
        return data
    except Exception as e:
        logger.error(f"Export data error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export data"
        )
