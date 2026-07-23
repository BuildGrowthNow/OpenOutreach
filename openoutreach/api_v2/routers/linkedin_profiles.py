"""
LinkedIn Profiles Router - FastAPI implementation

Provides endpoints for managing LinkedIn profiles, uploading cookies,
and checking profile health status.
"""

import json
import logging
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status, Body
from pydantic import BaseModel

from openoutreach.api_v2.dependencies_v2 import get_current_user
from openoutreach.api_v2.schemas.linkedin import (
    LinkedInProfileResponse,
)
from openoutreach.mongodb.connection import get_mongodb_collection

logger = logging.getLogger(__name__)
router = APIRouter()


# Request/Response schemas
class CookieUploadRequest(BaseModel):
    """Request schema for cookie upload."""
    cookie_data: str | Dict | List

    class Config:
        json_schema_extra = {
            "example": {
                "cookie_data": {
                    "cookies": [
                        {
                            "name": "li_at",
                            "value": "AQEDATxxxxxxxx...",
                            "domain": ".linkedin.com",
                            "path": "/",
                            "expires": -1,
                            "httpOnly": True,
                            "secure": True,
                            "sameSite": "None"
                        }
                    ]
                }
            }
        }


class CookieUploadResponse(BaseModel):
    """Response schema for cookie upload."""
    success: bool
    message: str
    error: Optional[str] = None


class ProfileListResponse(BaseModel):
    """Response schema for profile list."""
    profiles: List[Dict]
    count: int


# Helper functions
def normalize_cookie(cookie: Dict) -> Dict:
    """Transform EditThisCookie/Cookie-Editor format to Playwright format."""
    normalized = {
        "name": cookie.get("name"),
        "value": cookie.get("value"),
        "domain": cookie.get("domain", ".linkedin.com"),
        "path": cookie.get("path", "/"),
    }

    # Transform expirationDate (Unix timestamp) to expires (Unix timestamp or -1)
    if "expires" in cookie:
        normalized["expires"] = cookie["expires"]
    elif "expirationDate" in cookie:
        normalized["expires"] = int(cookie["expirationDate"])
    else:
        normalized["expires"] = -1

    # Transform sameSite
    same_site = cookie.get("sameSite")
    if same_site == "no_restriction":
        normalized["sameSite"] = "None"
    elif same_site in ["Lax", "Strict", "None"]:
        normalized["sameSite"] = same_site
    else:
        normalized["sameSite"] = "Lax"

    # Copy other fields
    if "httpOnly" in cookie:
        normalized["httpOnly"] = cookie["httpOnly"]
    if "secure" in cookie:
        normalized["secure"] = cookie["secure"]

    return normalized


def encrypt_cookie_data(storage_state: Dict) -> str:
    """Encrypt cookie storage state for database storage."""
    try:
        from openoutreach.mongodb.crypto import encrypt_text
        json_str = json.dumps(storage_state)
        return encrypt_text(json_str)
    except Exception as e:
        logger.error(f"Failed to encrypt cookie data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Encryption failed: {str(e)}"
        )


# Endpoints

@router.get("", response_model=ProfileListResponse)
async def list_linkedin_profiles(
    skip: int = 0,
    limit: int = 100,
    user_id: str = Depends(get_current_user),
):
    """
    List LinkedIn profiles for the current user.

    Multi-tenant: filters by user_id from authenticated token.
    Supports pagination via skip/limit query params.
    """
    collection = get_mongodb_collection("linkedin_profiles")
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LinkedIn profiles database unavailable"
        )

    try:
        # Query profiles for this user
        cursor = collection.find(
            {"user_id": user_id}
        ).skip(skip).limit(limit)

        profiles = []
        for doc in cursor:
            profiles.append({
                "id": str(doc.get("_id")),
                "linkedin_username": doc.get("linkedin_username", ""),
                "active": doc.get("active", True),
                "connect_daily_limit": doc.get("connect_daily_limit", 20),
                "follow_up_daily_limit": doc.get("follow_up_daily_limit", 25),
            })

        count = collection.count_documents({"user_id": user_id})

        return ProfileListResponse(profiles=profiles, count=count)

    except Exception as e:
        logger.exception("Failed to list LinkedIn profiles")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve profiles: {str(e)}"
        )


@router.post(
    "/{profile_id}/cookies",
    response_model=CookieUploadResponse,
    status_code=status.HTTP_200_OK,
)
async def upload_profile_cookies(
    profile_id: str,
    request: CookieUploadRequest,
    user_id: str = Depends(get_current_user),
):
    """
    Upload and store LinkedIn session cookies for a profile.

    Accepts:
    - Full Playwright storage_state JSON (object with "cookies" array)
    - EditThisCookie/Cookie-Editor format (array of cookie objects)
    - Single li_at cookie string (wrapped into minimal storage_state)

    Multi-tenant: validates user owns the profile before updating.
    Returns 404 if profile not found or user doesn't own it.
    """
    collection = get_mongodb_collection("linkedin_profiles")
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LinkedIn profiles database unavailable"
        )

    # Verify profile exists and user owns it
    try:
        profile = collection.find_one({"_id": profile_id, "user_id": user_id})
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found or access denied"
            )
    except Exception as e:
        logger.error(f"Failed to find profile {profile_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )

    # Normalize cookie payload into storage_state dict
    cookie_payload = request.cookie_data
    storage_state = None

    try:
        if isinstance(cookie_payload, str):
            # Try to parse JSON first
            try:
                parsed = json.loads(cookie_payload)
                if isinstance(parsed, dict) and "cookies" in parsed:
                    # Playwright storage_state format: {"cookies": [...]}
                    storage_state = {"cookies": [normalize_cookie(c) for c in parsed["cookies"]]}
                elif isinstance(parsed, list):
                    # EditThisCookie/Cookie-Editor format: [{...}, {...}]
                    storage_state = {"cookies": [normalize_cookie(c) for c in parsed]}
            except Exception:
                # Treat as li_at value
                li_at = cookie_payload.strip()
                if not li_at:
                    raise ValueError("Empty cookie string")
                storage_state = {
                    "cookies": [
                        {
                            "name": "li_at",
                            "value": li_at,
                            "domain": ".linkedin.com",
                            "path": "/",
                            "expires": -1,
                            "httpOnly": True,
                            "secure": True,
                            "sameSite": "None",
                        }
                    ]
                }
        elif isinstance(cookie_payload, dict):
            if "cookies" in cookie_payload:
                storage_state = {"cookies": [normalize_cookie(c) for c in cookie_payload["cookies"]]}
        elif isinstance(cookie_payload, list):
            # EditThisCookie/Cookie-Editor format sent directly as array
            storage_state = {"cookies": [normalize_cookie(c) for c in cookie_payload]}
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc)
        )
    except Exception as e:
        logger.error(f"Failed to parse cookie data: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid cookie format: {str(e)}"
        )

    if not storage_state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid cookie_data format"
        )

    # Validate li_at cookie exists
    li_at_present = any(
        c.get("name") == "li_at" for c in storage_state.get("cookies", [])
    )
    if not li_at_present:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="li_at cookie missing"
        )

    # Encrypt and save the cookie data
    try:
        encrypted_data = encrypt_cookie_data(storage_state)

        result = collection.update_one(
            {"_id": profile_id, "user_id": user_id},
            {"$set": {"cookie_data_encrypted": encrypted_data}}
        )

        if result.modified_count == 0 and result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found or access denied"
            )

        return CookieUploadResponse(
            success=True,
            message="Cookie saved successfully. The session will activate within 30 seconds."
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to save cookie data")
        return CookieUploadResponse(
            success=False,
            message="",
            error=str(e)
        )


@router.post("", response_model=LinkedInProfileResponse, status_code=201)
async def create_profile(
    linkedin_username: str = Body(...),
    connect_daily_limit: int = Body(20),
    follow_up_daily_limit: int = Body(25),
    user_id: str = Depends(get_current_user),
):
    """
    Create a new LinkedIn profile for the current user.

    Multi-tenant: automatically assigns user_id from authenticated token.
    Creates SmartRateLimitContext for the new profile.
    """
    from openoutreach.linkedin.models import LinkedInProfile
    from openoutreach.mongodb.models_user import User
    from openoutreach.billing.enforcement import PlanEnforcer

    collection = get_mongodb_collection("linkedin_profiles")
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LinkedIn profiles database unavailable"
        )

    # Enforce plan limit
    user = User.get(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    allowed, error_msg = PlanEnforcer.can_create_linkedin_account(user)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)

    # Check for duplicate
    existing = collection.find_one({
        "user_id": user_id,
        "linkedin_username": linkedin_username
    })
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Profile '{linkedin_username}' already exists"
        )

    try:
        # Create profile
        profile = LinkedInProfile(
            user_id=user_id,
            linkedin_username=linkedin_username,
            connect_daily_limit=connect_daily_limit,
            follow_up_daily_limit=follow_up_daily_limit,
            active=True,
        )
        profile.save()

        # Create SmartRateLimitContext for this profile
        try:
            rate_ctx_collection = get_mongodb_collection("smart_rate_limit_contexts")
            if rate_ctx_collection is not None:
                rate_ctx_collection.insert_one({
                    "_id": str(uuid4()),
                    "linkedin_profile_id": profile._id,
                    "detectability_score": 0.5,  # Default neutral
                    "time_multiplier": 1.0,
                    "day_multiplier": 1.0,
                    "campaign_context": {},
                })
                logger.info(f"Created SmartRateLimitContext for profile {profile._id}")
        except Exception as e:
            logger.warning(f"Failed to create SmartRateLimitContext: {e}")

        return LinkedInProfileResponse(
            id=profile._id,
            user_id=profile.user_id or "",
            linkedin_username=profile.linkedin_username or "",
            active=profile.active,
            connect_daily_limit=profile.connect_daily_limit,
            follow_up_daily_limit=profile.follow_up_daily_limit,
            cookie_data_encrypted=profile.cookie_data_encrypted,
            campaign_id=profile.campaign_id,
            self_lead_id=profile.self_lead_id,
            created_at=None,
            updated_at=None,
        )

    except Exception as e:
        logger.exception("Failed to create LinkedIn profile")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create profile: {str(e)}"
        )


# Static routes MUST be registered before /{profile_id} to prevent FastAPI
# from matching "health" or "daemon" as a profile_id path parameter.

@router.get("/health")
async def get_profile_health(
    user_id: str = Depends(get_current_user),
):
    """
    Get health status for all user's LinkedIn profiles.

    Returns aggregated health metrics including:
    - Overall profile status
    - Credential verification status
    - Health scores and recommendations
    - Active alerts

    Multi-tenant: filters by user_id from authenticated token.
    """
    profiles_collection = get_mongodb_collection("linkedin_profiles")
    credentials_collection = get_mongodb_collection("linkedin_credentials")
    logs_collection = get_mongodb_collection("linkedin_credential_logs")

    if profiles_collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LinkedIn profiles database unavailable"
        )

    try:
        # Get all profiles for this user
        profiles_cursor = profiles_collection.find({"user_id": user_id})
        profiles = list(profiles_cursor)
        total_profiles = len(profiles)

        profile_health_data = []

        for profile in profiles:
            profile_id = str(profile.get("_id"))
            linkedin_username = profile.get("linkedin_username", "")
            active = profile.get("active", True)

            # Get associated credentials
            credentials_status = "unknown"
            health_score = 100
            last_error = None
            last_verification = None

            if credentials_collection is not None:
                credential = credentials_collection.find_one({
                    "linkedin_profile_id": profile_id
                })

                if credential:
                    credentials_status = credential.get("status", "unknown")

                    # Calculate health score based on credential status
                    if credentials_status == "invalid":
                        health_score = 0
                    elif credentials_status == "locked":
                        health_score = 40
                    elif credentials_status == "expired":
                        health_score = 60
                    elif credentials_status == "tested":
                        health_score = 80
                    elif credentials_status == "active":
                        health_score = 100

                    # Get last verification timestamp
                    last_verified = credential.get("last_verified")
                    if last_verified:
                        last_verification = last_verified.isoformat()

                    # Get last error from logs
                    if logs_collection is not None:
                        try:
                            error_log = logs_collection.find_one(
                                {
                                    "credential_id": str(credential.get("_id")),
                                    "action": {"$nin": ["verified", "usage"]}
                                },
                                sort=[("created_at", -1)]
                            )

                            if error_log:
                                details = error_log.get("details", {})
                                last_error = (
                                    details.get("error_message") or
                                    details.get("message") or
                                    details.get("reason")
                                )
                        except Exception as e:
                            logger.error(f"Failed to get error logs: {e}")
                            last_error = None

            # Determine overall health status
            if not active:
                health_status = "inactive"
            elif credentials_status == "active":
                health_status = "active"
            elif credentials_status == "invalid":
                health_status = "invalid"
            elif credentials_status == "expired":
                health_status = "expired"
            elif credentials_status == "locked":
                health_status = "locked"
            elif credentials_status == "tested":
                health_status = "tested"
            elif credentials_status == "stored":
                health_status = "stored"
            else:
                health_status = "active" if active else "inactive"

            needs_attention = credentials_status in ["invalid", "locked", "expired"]

            profile_health_data.append({
                "id": profile_id,
                "linkedin_username": linkedin_username,
                "status": active,
                "credentials_status": credentials_status,
                "health_score": health_score,
                "health_status": health_status,
                "needs_attention": needs_attention,
                "last_error": last_error,
                "last_verification": last_verification,
            })

        needs_attention_count = sum(
            1 for p in profile_health_data if p["needs_attention"]
        )

        return {
            "profiles": profile_health_data,
            "count": len(profile_health_data),
            "total_profiles": total_profiles,
            "needs_attention_count": needs_attention_count,
        }

    except Exception as e:
        logger.exception("Failed to get profile health")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve profile health: {str(e)}"
        )


@router.get("/daemon/status")
async def get_daemon_status(user_id: str = Depends(get_current_user)):
    """Get desktop daemon status for the current user.

    Returns daemon health, session state, and verification requirements.
    """
    from datetime import datetime, timezone
    from openoutreach.linkedin.models import LinkedInProfile

    try:
        profiles = LinkedInProfile.objects.filter(user_id=user_id, active=True)

        if not profiles:
            return {
                "has_daemon": False,
                "profiles": [],
            }

        daemon_statuses = []
        for profile in profiles:
            daemon_info = {
                "profile_id": profile.pk,
                "username": profile.linkedin_username,
                "daemon_active": False,
                "last_seen": None,
                "version": None,
                "platform": None,
                "browser": None,
                "is_logged_in": profile.is_logged_in,
                "requires_verification": profile.requires_verification,
                "verification_type": profile.verification_type,
                "session_updated_at": profile.session_updated_at.isoformat() if profile.session_updated_at else None,
                "status": "offline",
            }

            # Check if daemon was seen recently (within 2 minutes = 2 heartbeats)
            if profile.daemon_last_seen:
                now = datetime.now(timezone.utc)
                # Handle timezone-naive datetime
                last_seen = profile.daemon_last_seen
                if last_seen.tzinfo is None:
                    from datetime import timezone as tz
                    last_seen = last_seen.replace(tzinfo=tz.utc)

                seconds_since_seen = (now - last_seen).total_seconds()
                daemon_info["last_seen"] = last_seen.isoformat()
                daemon_info["version"] = profile.daemon_version
                daemon_info["platform"] = profile.daemon_platform
                daemon_info["browser"] = profile.daemon_browser

                if seconds_since_seen < 120:  # 2 minutes
                    daemon_info["daemon_active"] = True
                    daemon_info["status"] = "online"
                elif seconds_since_seen < 600:  # 10 minutes
                    daemon_info["status"] = "stale"
                else:
                    daemon_info["status"] = "offline"

            daemon_statuses.append(daemon_info)

        return {
            "has_daemon": len(daemon_statuses) > 0,
            "profiles": daemon_statuses,
        }

    except Exception as e:
        logger.exception("Failed to get daemon status")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve daemon status: {str(e)}"
        )


@router.get("/{profile_id}", response_model=LinkedInProfileResponse)
async def get_profile(
    profile_id: str,
    user_id: str = Depends(get_current_user),
):
    """
    Get a single LinkedIn profile by ID.

    Multi-tenant: verifies user owns the profile.
    Returns 404 if profile not found or access denied.
    """
    collection = get_mongodb_collection("linkedin_profiles")
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LinkedIn profiles database unavailable"
        )

    try:
        profile_doc = collection.find_one({"_id": profile_id, "user_id": user_id})
        if not profile_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found or access denied"
            )

        return LinkedInProfileResponse(
            id=str(profile_doc.get("_id")),
            user_id=profile_doc.get("user_id", ""),
            linkedin_username=profile_doc.get("linkedin_username", ""),
            active=profile_doc.get("active", True),
            connect_daily_limit=profile_doc.get("connect_daily_limit", 20),
            follow_up_daily_limit=profile_doc.get("follow_up_daily_limit", 25),
            cookie_data_encrypted=profile_doc.get("cookie_data_encrypted"),
            campaign_id=profile_doc.get("campaign_id"),
            self_lead_id=profile_doc.get("self_lead_id"),
            created_at=profile_doc.get("created_at"),
            updated_at=profile_doc.get("updated_at"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get LinkedIn profile")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve profile: {str(e)}"
        )


@router.put("/{profile_id}", response_model=LinkedInProfileResponse)
async def update_profile(
    profile_id: str,
    linkedin_username: Optional[str] = Body(None),
    active: Optional[bool] = Body(None),
    connect_daily_limit: Optional[int] = Body(None),
    follow_up_daily_limit: Optional[int] = Body(None),
    proxy_server: Optional[str] = Body(None),
    proxy_username: Optional[str] = Body(None),
    proxy_password: Optional[str] = Body(None),
    user_id: str = Depends(get_current_user),
):
    """
    Update a LinkedIn profile.

    Multi-tenant: verifies user owns the profile before updating.
    Only provided fields are updated.
    Supports proxy configuration (pass empty string to clear proxy).
    """
    collection = get_mongodb_collection("linkedin_profiles")
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LinkedIn profiles database unavailable"
        )

    try:
        # Verify ownership
        profile_doc = collection.find_one({"_id": profile_id, "user_id": user_id})
        if not profile_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found or access denied"
            )

        # Build update
        updates = {}
        if linkedin_username is not None:
            updates["linkedin_username"] = linkedin_username
        if active is not None:
            updates["active"] = active
            updates["is_active"] = active  # keep both fields in sync
        if connect_daily_limit is not None:
            updates["connect_daily_limit"] = connect_daily_limit
        if follow_up_daily_limit is not None:
            updates["follow_up_daily_limit"] = follow_up_daily_limit
        # Proxy fields - support clearing with empty string
        if proxy_server is not None:
            updates["proxy_server"] = proxy_server if proxy_server else None
        if proxy_username is not None:
            updates["proxy_username"] = proxy_username if proxy_username else None
        if proxy_password is not None:
            updates["proxy_password"] = proxy_password if proxy_password else None

        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )

        # Apply update
        collection.update_one(
            {"_id": profile_id, "user_id": user_id},
            {"$set": updates}
        )

        # Fetch updated profile
        updated_doc = collection.find_one({"_id": profile_id})
        if not updated_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found after update"
            )

        return LinkedInProfileResponse(
            id=str(updated_doc.get("_id")),
            user_id=updated_doc.get("user_id", ""),
            linkedin_username=updated_doc.get("linkedin_username", ""),
            active=updated_doc.get("active", True),
            connect_daily_limit=updated_doc.get("connect_daily_limit", 20),
            follow_up_daily_limit=updated_doc.get("follow_up_daily_limit", 25),
            cookie_data_encrypted=updated_doc.get("cookie_data_encrypted"),
            campaign_id=updated_doc.get("campaign_id"),
            self_lead_id=updated_doc.get("self_lead_id"),
            created_at=updated_doc.get("created_at"),
            updated_at=updated_doc.get("updated_at"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to update LinkedIn profile")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update profile: {str(e)}"
        )


@router.post("/{profile_id}/proxy/test")
async def test_proxy(
    profile_id: str,
    proxy_server: str = Body(...),
    proxy_username: Optional[str] = Body(None),
    proxy_password: Optional[str] = Body(None),
    user_id: str = Depends(get_current_user),
):
    """
    Test proxy connectivity before saving.

    Multi-tenant: verifies user owns the profile.
    Returns connectivity status and any errors.
    """
    collection = get_mongodb_collection("linkedin_profiles")
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LinkedIn profiles database unavailable"
        )

    try:
        # Verify ownership
        profile_doc = collection.find_one({"_id": profile_id, "user_id": user_id})
        if not profile_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found or access denied"
            )

        # Test proxy connectivity
        import httpx

        proxy_url = proxy_server
        if proxy_username and proxy_password:
            # Inject auth into URL if provided
            from urllib.parse import urlparse, urlunparse
            parsed = urlparse(proxy_server)
            netloc_with_auth = f"{proxy_username}:{proxy_password}@{parsed.hostname}"
            if parsed.port:
                netloc_with_auth += f":{parsed.port}"
            proxy_url = urlunparse((
                parsed.scheme,
                netloc_with_auth,
                parsed.path,
                parsed.params,
                parsed.query,
                parsed.fragment
            ))

        try:
            async with httpx.AsyncClient(proxy=proxy_url, timeout=10.0) as client:
                # Test with a simple request to LinkedIn
                response = await client.get("https://www.linkedin.com/")
                if response.status_code in [200, 301, 302, 403]:
                    # 403 is OK - it means proxy connected but LinkedIn blocked
                    return {
                        "success": True,
                        "message": "Proxy connection successful",
                        "status_code": response.status_code,
                    }
                else:
                    return {
                        "success": False,
                        "message": f"Unexpected status code: {response.status_code}",
                        "error": f"HTTP {response.status_code}",
                    }
        except httpx.ProxyError as e:
            return {
                "success": False,
                "message": "Proxy connection failed",
                "error": str(e),
            }
        except httpx.TimeoutException:
            return {
                "success": False,
                "message": "Proxy connection timeout",
                "error": "Request timed out after 10 seconds",
            }
        except Exception as e:
            return {
                "success": False,
                "message": "Proxy test failed",
                "error": str(e),
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to test proxy")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test proxy: {str(e)}"
        )


@router.get("/{profile_id}/proxy")
async def get_proxy_config(
    profile_id: str,
    user_id: str = Depends(get_current_user),
):
    """
    Get proxy configuration for a profile.

    Multi-tenant: verifies user owns the profile.
    Returns proxy settings (password is masked).
    """
    collection = get_mongodb_collection("linkedin_profiles")
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LinkedIn profiles database unavailable"
        )

    try:
        profile_doc = collection.find_one({"_id": profile_id, "user_id": user_id})
        if not profile_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found or access denied"
            )

        proxy_server = profile_doc.get("proxy_server")
        proxy_username = profile_doc.get("proxy_username")
        proxy_password = profile_doc.get("proxy_password")

        return {
            "profile_id": profile_id,
            "proxy_server": proxy_server,
            "proxy_username": proxy_username,
            "proxy_password": "********" if proxy_password else None,
            "has_proxy": proxy_server is not None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get proxy config")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve proxy config: {str(e)}"
        )


@router.delete("/{profile_id}", status_code=204)
async def delete_profile(
    profile_id: str,
    user_id: str = Depends(get_current_user),
):
    """
    Delete a LinkedIn profile.

    Multi-tenant: verifies user owns the profile before deleting.
    Safety: blocks deletion if any active campaigns use this profile.
    Also removes associated SmartRateLimitContext.
    """
    profiles_collection = get_mongodb_collection("linkedin_profiles")
    campaigns_collection = get_mongodb_collection("campaigns")

    if profiles_collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LinkedIn profiles database unavailable"
        )

    try:
        # Verify ownership
        profile_doc = profiles_collection.find_one({"_id": profile_id, "user_id": user_id})
        if not profile_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found or access denied"
            )

        # Check for active campaigns
        if campaigns_collection is not None:
            active_campaigns = campaigns_collection.count_documents({
                "linkedin_profile_id": profile_id,
                "is_paused": False
            })
            if active_campaigns > 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot delete profile: {active_campaigns} active campaign(s) use this profile"
                )

        # Delete SmartRateLimitContext
        try:
            rate_ctx_collection = get_mongodb_collection("smart_rate_limit_contexts")
            if rate_ctx_collection is not None:
                rate_ctx_collection.delete_one({"linkedin_profile_id": profile_id})
                logger.info(f"Deleted SmartRateLimitContext for profile {profile_id}")
        except Exception as e:
            logger.warning(f"Failed to delete SmartRateLimitContext: {e}")

        # Delete profile
        result = profiles_collection.delete_one({"_id": profile_id, "user_id": user_id})
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found or access denied"
            )

        logger.info(f"Deleted LinkedIn profile {profile_id} for user {user_id}")
        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to delete LinkedIn profile")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete profile: {str(e)}"
        )
