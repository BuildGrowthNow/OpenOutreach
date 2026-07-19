"""
FastAPI Dependencies - Auth delegates to dependencies_v2.py

This module maintains backwards compatibility but all auth logic
has been moved to dependencies_v2.py for JWT-only authentication.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """
    Extract and validate JWT token, return user_id.

    Supports:
    1. Local JWT (HS256 with JWT_SECRET_KEY) - production multi-tenant
    2. Supabase JWT (HS256/RS256/ES256) - backwards compatibility

    Returns user_id string.
    Raises 403 if user is blocked, deleted, or inactive.
    """
    # Delegate to production dependency
    from openoutreach.api_v2.dependencies_v2 import get_current_user as get_current_user_v2
    return await get_current_user_v2(credentials)


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
