"""
FastAPI Dependencies - Auth supports both Supabase JWT and local JWT
"""
import os
import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError, jwk
from typing import Optional
import logging

from openoutreach.mongodb import models

logger = logging.getLogger(__name__)
security = HTTPBearer()

# Settings from environment
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")

# JWKS cache for Supabase RS256 verification
_jwks_cache = None


async def _fetch_supabase_jwks():
    """Fetch JWKS from Supabase for RS256/ES256 verification."""
    global _jwks_cache
    if _jwks_cache:
        return _jwks_cache

    urls_to_try = [
        f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json",
        f"{SUPABASE_URL}/.well-known/jwks.json",
    ]

    async with httpx.AsyncClient() as client:
        for url in urls_to_try:
            try:
                resp = await client.get(url, timeout=5.0)
                if resp.status_code == 200:
                    _jwks_cache = resp.json()
                    logger.info(f"Fetched JWKS from {url}")
                    return _jwks_cache
            except Exception as e:
                logger.debug(f"Failed to fetch JWKS from {url}: {e}")
                continue
    return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """
    Extract and validate JWT token, return user_id.

    Supports:
    1. Supabase JWT (HS256 with service key, or RS256/ES256 with JWKS)
    2. Local JWT (HS256 with JWT_SECRET_KEY)

    On first Supabase login, creates/links user in MongoDB.
    """
    token = credentials.credentials

    try:
        # Decode header to determine algorithm
        unverified_header = jwt.get_unverified_header(token)
        algorithm = unverified_header.get("alg", "HS256")

        payload = None

        # Try Supabase HS256 (service key)
        if algorithm == "HS256" and SUPABASE_SERVICE_KEY:
            try:
                payload = jwt.decode(
                    token,
                    SUPABASE_SERVICE_KEY,
                    algorithms=["HS256"],
                    options={"verify_aud": False}
                )
                logger.debug("Token verified with Supabase service key")
            except JWTError as e:
                logger.debug(f"Supabase HS256 verification failed: {e}")

        # Try local JWT
        if payload is None and algorithm == "HS256" and JWT_SECRET_KEY:
            try:
                payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
                logger.debug("Token verified with local JWT secret")
            except JWTError as e:
                logger.debug(f"Local JWT verification failed: {e}")

        # Try Supabase RS256/ES256 with JWKS
        if payload is None and algorithm in ("RS256", "ES256"):
            jwks_data = await _fetch_supabase_jwks()
            if jwks_data:
                kid = unverified_header.get("kid")
                for key_data in jwks_data.get("keys", []):
                    if key_data.get("kid") == kid:
                        public_key = jwk.construct(key_data)
                        payload = jwt.decode(
                            token,
                            public_key,
                            algorithms=[algorithm],
                            options={"verify_aud": False}
                        )
                        logger.debug(f"Token verified with JWKS {algorithm}")
                        break

        if payload is None:
            raise HTTPException(status_code=401, detail="Invalid token")

        # Extract user info
        sub = payload.get("sub")
        email = payload.get("email", "")

        if not sub:
            raise HTTPException(status_code=401, detail="Token missing 'sub' claim")

        # Check if this is a Supabase token (has 'aud' or 'role' claims)
        if payload.get("aud") or payload.get("role"):
            # Supabase token - get or create local user
            user = models.SupabaseUser.get(sub)
            if not user:
                # First login - create user
                user = models.SupabaseUser(
                    supabase_user_id=sub,
                    email=email,
                    full_name=payload.get("user_metadata", {}).get("full_name", ""),
                    is_active=True,
                )
                user.save()
                logger.info(f"Created new user from Supabase: {email}")

            return user._id
        else:
            # Local JWT - sub IS the user_id
            from openoutreach.mongodb.connection import get_mongodb_collection
            users_collection = get_mongodb_collection("supabase_users")
            if users_collection is not None:
                user_doc = users_collection.find_one({"_id": sub, "is_active": True})
                if not user_doc:
                    raise HTTPException(status_code=401, detail="User not found or inactive")
            return sub

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
) -> Optional[str]:
    """Optional auth - returns None if no token."""
    if credentials is None:
        return None
    return await get_current_user(credentials)


async def get_admin_user(user_id: str = Depends(get_current_user)) -> str:
    """Ensure user is an admin."""
    from openoutreach.mongodb.models_user import User

    user = User.get(user_id)
    if not user or not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user_id


async def check_subscription_active(user_id: str = Depends(get_current_user)) -> str:
    """Ensure user has an active subscription."""
    from openoutreach.mongodb.models_user import User

    user = User.get(user_id)
    if not user or user.subscription_status not in ("active", "trialing"):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Active subscription required",
        )
    return user_id


async def check_linkedin_account_limit(user_id: str = Depends(get_current_user)) -> str:
    """Ensure user hasn't exceeded LinkedIn account limit."""
    from openoutreach.mongodb.models_user import User
    from openoutreach.mongodb.connection import get_mongodb_collection

    user = User.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    collection = get_mongodb_collection("linkedin_profiles")
    if collection is None:
        return user_id

    count = collection.count_documents({
        "user_id": user_id,
        "is_active": True,
    })

    if count >= user.linkedin_account_limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="LinkedIn account limit reached",
        )
    return user_id


async def check_campaign_limit(user_id: str = Depends(get_current_user)) -> str:
    """Ensure user hasn't exceeded campaign limit."""
    from openoutreach.mongodb.models_user import User
    from openoutreach.mongodb.connection import get_mongodb_collection

    user = User.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if user.campaign_limit is None:
        return user_id

    collection = get_mongodb_collection("campaigns")
    if collection is None:
        return user_id

    count = collection.count_documents({
        "user_id": user_id,
        "is_paused": False,
    })

    if count >= user.campaign_limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Campaign limit reached",
        )
    return user_id
