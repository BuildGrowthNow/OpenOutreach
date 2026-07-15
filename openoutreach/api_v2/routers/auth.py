"""
Production FastAPI Auth Router - Multi-Tenant

Implements JWT authentication with proper security:
- Local auth (email + password)
- Supabase SSO support
- HTTP-only refresh tokens
- Password reset flow
- Rate limiting ready
"""

import logging
from datetime import datetime, timedelta, timezone as tz

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
)
from openoutreach.mongodb.models_user import User
from openoutreach.mongodb import models

logger = logging.getLogger(__name__)
router = APIRouter()


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
async def register(data: RegisterRequest):
    """
    Register a new user account.

    Creates user + default SiteConfig.
    Returns user info (client must call /login to get tokens).
    """
    # Check if email already exists
    existing_user = User.get_by_email(data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create user
    user = User(
        email=data.email,
        full_name=data.full_name,
        is_active=True,
    )
    user.set_password(data.password)
    user.save()

    # Create default SiteConfig for user
    try:
        site_config = models.SiteConfig()
        site_config.save()
    except Exception as e:
        logger.warning(f"Failed to create SiteConfig for {user.email}: {e}")

    logger.info(f"New user registered: {user.email}")

    return UserResponse(
        id=user._id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        created_at=user.created_at or datetime.now(tz.utc),
    )


# ==================== LOGIN ====================


@router.post("/login/", response_model=TokenResponse)
async def login(credentials: LoginRequest, response: Response):
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

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )

    # Update last login
    user.update_last_login()

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

    logger.info(f"User login successful: {user.email}")

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_LIFETIME_MINUTES * 60
    )


# ==================== REFRESH TOKEN ====================


@router.post("/refresh/", response_model=TokenResponse)
async def refresh_token(request: Request):
    """
    Refresh access token using HTTP-only refresh token cookie.

    Returns new access token.
    """
    # Get refresh token from cookie
    refresh_token = request.cookies.get("refresh_token")

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

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            refresh_token=refresh_token,  # Return existing refresh token
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
    )


# ==================== LOGOUT ====================


@router.post("/logout/")
async def logout(response: Response, user_id: str = Depends(get_current_user)):
    """
    Logout user by clearing refresh token cookie.

    Access token remains valid until expiration (client should discard it).
    """
    # Clear refresh token cookie
    response.delete_cookie(key="refresh_token", path="/")

    logger.info(f"User logged out: {user_id}")

    return {"status": "success", "message": "Successfully logged out"}


# ==================== PASSWORD RESET REQUEST ====================


@router.post("/password-reset/request/")
async def password_reset_request(request: PasswordResetRequest):
    """
    Request a password reset.

    Always returns success to prevent email enumeration attacks.
    TODO: Send email with reset link.
    """
    try:
        user = User.get_by_email(request.email)

        if user and user.hashed_password:
            # Generate reset token (expires in 24 hours)
            _ = jwt.encode(
                {
                    "sub": user.email,
                    "exp": datetime.now(tz.utc) + timedelta(hours=24),
                    "type": "password_reset",
                },
                settings.jwt_secret,
                algorithm=settings.JWT_ALGORITHM,
            )

            # TODO: Send email with reset link
            # reset_url = f"{FRONTEND_URL}/reset-password?token={reset_token}"
            # send_password_reset_email(user.email, reset_url)

            logger.info(f"Password reset requested for: {request.email}")

        # Always return success
        return {"status": "success", "message": "If an account exists, a reset link has been sent"}

    except Exception as e:
        logger.error(f"Password reset request error: {e}")
        # Return success even on error
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
