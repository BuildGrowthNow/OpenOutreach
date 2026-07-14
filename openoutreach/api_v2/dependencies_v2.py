"""
Production FastAPI Dependencies - Multi-Tenant Auth

Supports both local JWT and Supabase JWT authentication.
Uses the new User model from models_user.py.
"""
import logging
from typing import Optional

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError, jwk

from openoutreach.config import settings
from openoutreach.mongodb.models_user import User
from openoutreach.mongodb.models import SupabaseUser

logger = logging.getLogger(__name__)
security = HTTPBearer()

# JWKS cache for Supabase RS256 verification
_jwks_cache = None


async def _fetch_supabase_jwks():
    """Fetch JWKS from Supabase for RS256/ES256 verification."""
    global _jwks_cache
    if _jwks_cache:
        return _jwks_cache

    if not settings.SUPABASE_URL:
        return None

    urls_to_try = [
        f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json",
        f"{settings.SUPABASE_URL}/.well-known/jwks.json",
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
    1. Local JWT (HS256 with JWT_SECRET_KEY) - production multi-tenant
    2. Supabase JWT (HS256/RS256/ES256) - backwards compatibility

    Returns user_id string.
    """
    token = credentials.credentials

    try:
        # Decode header to determine algorithm
        unverified_header = jwt.get_unverified_header(token)
        algorithm = unverified_header.get("alg", "HS256")

        payload = None

        # Try local JWT first (production multi-tenant)
        if algorithm == "HS256" and settings.jwt_secret:
            try:
                payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])

                # Check if it's a local token (has 'type' claim)
                if payload.get("type") in ("access", "refresh"):
                    user_id = payload.get("sub")
                    if not user_id:
                        raise HTTPException(status_code=401, detail="Token missing 'sub' claim")

                    # Verify user exists and is active
                    user = User.get(user_id)
                    if not user or not user.is_active:
                        raise HTTPException(status_code=401, detail="User not found or inactive")

                    logger.debug("Token verified with local JWT secret")
                    return user._id
            except JWTError as e:
                logger.debug(f"Local JWT verification failed: {e}")

        # Try Supabase HS256 (backwards compatibility)
        if payload is None and algorithm == "HS256" and settings.SUPABASE_SERVICE_KEY:
            try:
                payload = jwt.decode(
                    token,
                    settings.SUPABASE_SERVICE_KEY,
                    algorithms=["HS256"],
                    options={"verify_aud": False}
                )
                logger.debug("Token verified with Supabase service key")
            except JWTError as e:
                logger.debug(f"Supabase HS256 verification failed: {e}")

        # Try Supabase RS256/ES256 with JWKS (backwards compatibility)
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
            # First check new User model
            user = User.get_by_supabase_id(sub)
            if user:
                return user._id

            # Check legacy SupabaseUser model
            supabase_user = SupabaseUser.get(sub)
            if supabase_user:
                # Migrate to new User model
                user = User(
                    email=email,
                    full_name=supabase_user.full_name,
                    is_active=supabase_user.is_active,
                    supabase_user_id=sub,
                )
                user.save()
                logger.info(f"Migrated Supabase user to User model: {email}")
                return user._id

            # First login - create user
            user = User(
                email=email,
                full_name=payload.get("user_metadata", {}).get("full_name", ""),
                is_active=True,
                supabase_user_id=sub,
            )
            user.save()
            logger.info(f"Created new user from Supabase: {email}")
            return user._id
        else:
            # Local JWT token already handled above
            raise HTTPException(status_code=401, detail="Invalid token format")

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


async def get_campaign_with_access(campaign_id: str, user_id: str = Depends(get_current_user)):
    """
    Get campaign and verify user has access (owner OR team member).

    Raises 404 if campaign not found, 403 if access denied.
    """
    from openoutreach.mongodb import models

    campaign = models.Campaign.get(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if not campaign.has_access(user_id):
        raise HTTPException(status_code=403, detail="Access denied")

    return campaign
