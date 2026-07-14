"""
FastAPI Auth Router

Implements 8 authentication endpoints:
- Login (POST /auth/login/)
- Register (POST /auth/register/)
- Token refresh (POST /auth/refresh/)
- Token verify (POST /auth/verify/)
- Auth status (GET /auth/status/)
- Logout (POST /auth/logout/)
- Password reset request (POST /auth/password-reset/request/)
- Password reset confirm (POST /auth/password-reset/confirm/)
- Password update (POST /auth/update-password/)

Plus 3 Supabase auth endpoints:
- Link Supabase user (POST /auth/link-supabase-user/)
- Get Supabase user info (GET /auth/supabase-user/{id}/)
- Verify Supabase token (POST /auth/verify-supabase-token/)
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Response
from jose import jwt, JWTError
from passlib.context import CryptContext

from openoutreach.api_v2.dependencies import get_current_user
from openoutreach.api_v2.schemas.auth import (
    LoginRequest,
    TokenResponse,
    UserResponse,
    PasswordResetRequest,
    PasswordResetConfirm,
    PasswordUpdate,
    SupabaseUserLink,
)
from openoutreach.mongodb import models
from openoutreach.mongodb.connection import get_mongodb_collection

logger = logging.getLogger(__name__)
router = APIRouter()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings from environment
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")


def hash_password(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Create a JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "iat": datetime.utcnow(), "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def create_password_reset_token(email: str) -> str:
    """Create a password reset token (expires in 24 hours)."""
    expire = datetime.utcnow() + timedelta(hours=24)
    to_encode = {"sub": email, "exp": expire, "type": "password_reset"}
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


# ==================== LOGIN ====================

@router.post("/login/", response_model=TokenResponse)
async def login(credentials: LoginRequest, response: Response):
    """
    POST /api/auth/login/

    Authenticate user with email and password, return JWT tokens.

    Request:
        {
            "email": "user@example.com",
            "password": "password123"
        }

    Response:
        {
            "access_token": "eyJ...",
            "token_type": "bearer",
            "refresh_token": "eyJ...",
            "expires_in": 3600
        }
    """
    collection = get_mongodb_collection("supabase_users")
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable"
        )

    # Find user by email
    user_doc = collection.find_one({"email": credentials.email.lower()})
    if not user_doc:
        logger.warning(f"Login failed: user not found for email {credentials.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    user = models.SupabaseUser.from_dict(user_doc)

    # Check if user has a password (local auth users only)
    if not user_doc.get("password_hash"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This account uses SSO authentication"
        )

    # Verify password
    if not verify_password(credentials.password, user_doc["password_hash"]):
        logger.warning(f"Login failed: incorrect password for {credentials.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive"
        )

    # Update last login
    collection.update_one(
        {"_id": user._id},
        {"$set": {"last_login": datetime.utcnow()}}
    )

    # Create tokens
    access_token = create_access_token(data={"sub": user._id, "email": user.email})
    refresh_token = create_refresh_token(data={"sub": user._id})

    # Set refresh token in HTTP-only cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    )

    logger.info(f"User login successful: {user.email}")

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        refresh_token=refresh_token,
        expires_in=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


# ==================== REGISTER ====================

@router.post("/register/", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(credentials: LoginRequest, response: Response):
    """
    POST /api/auth/register/

    Register a new local user account.

    Request:
        {
            "email": "user@example.com",
            "password": "password123"
        }

    Response:
        {
            "access_token": "eyJ...",
            "token_type": "bearer",
            "refresh_token": "eyJ...",
            "expires_in": 3600
        }
    """
    collection = get_mongodb_collection("supabase_users")
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable"
        )

    # Check if user already exists
    existing_user = collection.find_one({"email": credentials.email.lower()})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Hash password
    password_hash = hash_password(credentials.password)

    # Create user
    user = models.SupabaseUser(
        email=credentials.email.lower(),
        full_name="",
        is_active=True,
    )

    # Insert with password hash
    doc = user.to_dict()
    doc["password_hash"] = password_hash
    collection.insert_one(doc)

    logger.info(f"New user registered: {user.email}")

    # Create tokens
    access_token = create_access_token(data={"sub": user._id, "email": user.email})
    refresh_token = create_refresh_token(data={"sub": user._id})

    # Set refresh token in HTTP-only cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        refresh_token=refresh_token,
        expires_in=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


# ==================== TOKEN REFRESH ====================

@router.post("/refresh/", response_model=TokenResponse)
async def refresh_token(response: Response, refresh_token: Optional[str] = None):
    """
    POST /api/auth/refresh/

    Refresh access token using refresh token from cookie or body.

    Request (optional body):
        {
            "refresh_token": "eyJ..."
        }

    Response:
        {
            "access_token": "eyJ...",
            "token_type": "bearer",
            "expires_in": 3600
        }
    """
    # Try to get refresh token from cookie first
    # (Note: In real implementation, this would come from request.cookies)
    # For now, require it in the body

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required"
        )

    try:
        payload = jwt.decode(refresh_token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])

        # Verify it's a refresh token
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )

        # Verify user still exists and is active
        collection = get_mongodb_collection("supabase_users")
        if not collection:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection unavailable"
            )

        user_doc = collection.find_one({"_id": user_id, "is_active": True})
        if not user_doc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )

        # Create new access token
        access_token = create_access_token(
            data={"sub": user_id, "email": user_doc.get("email", "")}
        )

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

    except JWTError as e:
        logger.warning(f"Token refresh failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )


# ==================== TOKEN VERIFY ====================

@router.post("/verify/")
async def verify_token(user_id: str = Depends(get_current_user)):
    """
    POST /api/auth/verify/

    Verify the validity of the access token.

    Headers:
        Authorization: Bearer <token>

    Response:
        {
            "status": "valid",
            "user_id": "abc123"
        }
    """
    return {
        "status": "valid",
        "user_id": user_id
    }


# ==================== AUTH STATUS ====================

@router.get("/status/", response_model=UserResponse)
async def auth_status(user_id: str = Depends(get_current_user)):
    """
    GET /api/auth/status/

    Get current authenticated user information.

    Headers:
        Authorization: Bearer <token>

    Response:
        {
            "id": "abc123",
            "email": "user@example.com",
            "full_name": "John Doe",
            "is_active": true,
            "supabase_user_id": "uuid",
            "created_at": "2024-01-01T00:00:00"
        }
    """
    collection = get_mongodb_collection("supabase_users")
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable"
        )

    user_doc = collection.find_one({"_id": user_id})
    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    user = models.SupabaseUser.from_dict(user_doc)

    return UserResponse(
        _id=user._id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        supabase_user_id=user.supabase_user_id,
        created_at=user.created_at
    )


# ==================== LOGOUT ====================

@router.post("/logout/")
async def logout(response: Response, user_id: str = Depends(get_current_user)):
    """
    POST /api/auth/logout/

    Logout user by clearing refresh token cookie.

    Headers:
        Authorization: Bearer <token>

    Response:
        {
            "status": "success",
            "message": "Successfully logged out"
        }
    """
    # Clear refresh token cookie
    response.delete_cookie("refresh_token")

    logger.info(f"User logged out: {user_id}")

    return {
        "status": "success",
        "message": "Successfully logged out"
    }


# ==================== PASSWORD RESET REQUEST ====================

@router.post("/password-reset/request/")
async def password_reset_request(request: PasswordResetRequest):
    """
    POST /api/auth/password-reset/request/

    Request a password reset email.

    Request:
        {
            "email": "user@example.com"
        }

    Response:
        {
            "status": "success",
            "message": "Password reset instructions sent to your email"
        }

    Note: Always returns success to prevent email enumeration attacks.
    """
    collection = get_mongodb_collection("supabase_users")
    if not collection:
        # Return success even on error to prevent enumeration
        return {
            "status": "success",
            "message": "Password reset instructions sent to your email"
        }

    try:
        # Find user by email
        user_doc = collection.find_one({"email": request.email.lower()})

        if user_doc and user_doc.get("password_hash"):
            # Generate reset token
            reset_token = create_password_reset_token(request.email.lower())

            # Store token in database
            collection.update_one(
                {"_id": user_doc["_id"]},
                {
                    "$set": {
                        "password_reset_token": reset_token,
                        "password_reset_expires": datetime.utcnow() + timedelta(hours=24)
                    }
                }
            )

            # TODO: Send email with reset link
            # reset_url = f"{FRONTEND_URL}/reset-password?token={reset_token}"
            # send_password_reset_email(request.email, reset_url)

            logger.info(f"Password reset requested for: {request.email}")

        # Always return success to prevent email enumeration
        return {
            "status": "success",
            "message": "Password reset instructions sent to your email"
        }

    except Exception as e:
        logger.error(f"Password reset request error: {e}")
        # Return success even on error
        return {
            "status": "success",
            "message": "Password reset instructions sent to your email"
        }


# ==================== PASSWORD RESET CONFIRM ====================

@router.post("/password-reset/confirm/")
async def password_reset_confirm(request: PasswordResetConfirm):
    """
    POST /api/auth/password-reset/confirm/

    Confirm password reset with token and new password.

    Request:
        {
            "token": "eyJ...",
            "new_password": "newpassword123"
        }

    Response:
        {
            "status": "success",
            "message": "Password successfully reset"
        }
    """
    try:
        # Decode and verify token
        payload = jwt.decode(request.token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])

        # Verify it's a password reset token
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
        collection = get_mongodb_collection("supabase_users")
        if not collection:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection unavailable"
            )

        user_doc = collection.find_one({"email": email})
        if not user_doc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token"
            )

        # Verify token matches stored token
        if user_doc.get("password_reset_token") != request.token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired token"
            )

        # Hash new password
        password_hash = hash_password(request.new_password)

        # Update password and clear reset token
        collection.update_one(
            {"_id": user_doc["_id"]},
            {
                "$set": {"password_hash": password_hash},
                "$unset": {"password_reset_token": "", "password_reset_expires": ""}
            }
        )

        logger.info(f"Password reset successful for: {email}")

        return {
            "status": "success",
            "message": "Password successfully reset"
        }

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
    POST /api/auth/update-password/

    Update password for authenticated user.

    Headers:
        Authorization: Bearer <token>

    Request:
        {
            "old_password": "oldpassword",
            "new_password": "newpassword123"
        }

    Response:
        {
            "status": "success",
            "message": "Password successfully updated"
        }
    """
    collection = get_mongodb_collection("supabase_users")
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable"
        )

    # Get user
    user_doc = collection.find_one({"_id": user_id})
    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Check if user has a password (local auth only)
    if not user_doc.get("password_hash"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account uses SSO authentication"
        )

    # Verify old password
    if not verify_password(request.old_password, user_doc["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    # Hash new password
    password_hash = hash_password(request.new_password)

    # Update password
    collection.update_one(
        {"_id": user_id},
        {"$set": {"password_hash": password_hash}}
    )

    logger.info(f"Password updated for user: {user_doc.get('email')}")

    return {
        "status": "success",
        "message": "Password successfully updated"
    }


# ==================== SUPABASE AUTH ENDPOINTS ====================

@router.post("/link-supabase-user/")
async def link_supabase_user(request: SupabaseUserLink):
    """
    POST /api/auth/link-supabase-user/

    Link or create MongoDB user from Supabase JWT token.

    Request:
        {
            "supabase_user_id": "uuid",
            "email": "user@example.com",
            "full_name": "John Doe"
        }

    Response:
        {
            "status": "success",
            "user_id": "abc123",
            "email": "user@example.com"
        }
    """
    collection = get_mongodb_collection("supabase_users")
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable"
        )

    try:
        # Check if user already exists
        user = models.SupabaseUser.get(request.supabase_user_id)

        if user:
            # Update existing user
            collection.update_one(
                {"supabase_user_id": request.supabase_user_id},
                {
                    "$set": {
                        "email": request.email.lower(),
                        "full_name": request.full_name or "",
                        "last_login": datetime.utcnow()
                    }
                }
            )
            logger.info(f"Updated Supabase user: {request.email}")
        else:
            # Create new user
            user = models.SupabaseUser(
                supabase_user_id=request.supabase_user_id,
                email=request.email.lower(),
                full_name=request.full_name or "",
                is_active=True,
            )
            user.save()
            logger.info(f"Created new Supabase user: {request.email}")

        return {
            "status": "success",
            "user_id": user._id,
            "email": user.email
        }

    except Exception as e:
        logger.error(f"Link Supabase user error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred. Please try again."
        )


@router.get("/supabase-user/{supabase_user_id}/", response_model=UserResponse)
async def get_supabase_user_info(
    supabase_user_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    GET /api/auth/supabase-user/{supabase_user_id}/

    Get MongoDB user info linked to Supabase user ID.

    Headers:
        Authorization: Bearer <token>

    Response:
        {
            "id": "abc123",
            "email": "user@example.com",
            "full_name": "John Doe",
            "is_active": true,
            "supabase_user_id": "uuid",
            "created_at": "2024-01-01T00:00:00"
        }
    """
    user = models.SupabaseUser.get(supabase_user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return UserResponse(
        _id=user._id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        supabase_user_id=user.supabase_user_id,
        created_at=user.created_at
    )


@router.post("/verify-supabase-token/")
async def verify_supabase_token(token: str):
    """
    POST /api/auth/verify-supabase-token/

    Verify Supabase JWT token validity.

    Request:
        {
            "token": "eyJ..."
        }

    Response:
        {
            "status": "success",
            "valid": true,
            "user_id": "uuid",
            "email": "user@example.com"
        }
    """
    try:
        # Decode without verification to get payload
        unverified_payload = jwt.decode(
            token,
            options={"verify_signature": False}
        )

        # Verify with Supabase service key if available
        if SUPABASE_SERVICE_KEY:
            payload = jwt.decode(
                token,
                SUPABASE_SERVICE_KEY,
                algorithms=["HS256"],
                options={"verify_aud": False}
            )
        else:
            payload = unverified_payload

        return {
            "status": "success",
            "valid": True,
            "user_id": payload.get("sub"),
            "email": payload.get("email")
        }

    except JWTError as e:
        logger.warning(f"Supabase token verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid token: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Verify Supabase token error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred. Please try again."
        )
