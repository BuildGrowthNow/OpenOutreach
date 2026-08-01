"""
FastAPI Dependencies - Multi-Tenant Auth

Local JWT (HS256) authentication only.
"""
import logging
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

from openoutreach.config import settings
from openoutreach.mongodb.models_user import User

logger = logging.getLogger(__name__)
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Validate local JWT token, return user_id."""
    token = credentials.credentials

    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])

        if payload.get("type") not in ("access", "refresh"):
            raise HTTPException(status_code=401, detail="Invalid token format")

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Token missing 'sub' claim")

        user = User.get(user_id)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        if user.status == "blocked":
            raise HTTPException(status_code=403, detail="Account blocked")

        if user.is_deleted or user.deletion_scheduled_at:
            raise HTTPException(status_code=403, detail="Account has been deleted")

        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account is inactive")

        return user._id

    except JWTError as e:
        logger.debug(f"JWT verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")
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
