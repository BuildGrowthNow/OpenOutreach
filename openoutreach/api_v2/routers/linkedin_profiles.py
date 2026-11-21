"""
LinkedIn Profiles Router - FastAPI implementation

Provides endpoints for managing LinkedIn profiles, uploading cookies,
and checking profile health status.
"""

import json
import logging
from typing import Dict, List, Optional
from urllib.parse import urlparse, urlunparse
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status, Body
from pydantic import BaseModel, ConfigDict

from openoutreach.api_v2.dependencies_v2 import get_current_user
from openoutreach.api_v2.schemas.linkedin import (
    LinkedInProfileResponse,
)
from openoutreach.billing.seats import release_linkedin_seat
from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.mongodb.crypto import safe_decrypt, safe_encrypt
from openoutreach.mongodb.models_user import User
from openoutreach.organizations.access import (
    can_delete_profile,
    profile_access_query,
    resolve_org_context,
)
from openoutreach.organizations.permissions import can_manage_proxies

logger = logging.getLogger(__name__)
router = APIRouter()

_ALLOWED_PROXY_SCHEMES = {"http", "https", "socks5", "socks5h"}


def _profile_query(user_id: str) -> dict:
    """Return the org-aware profile predicate for an authenticated user."""
    user = User.get(user_id)
    if user is None:
        # Unit tests and legacy callers without a user row fall back to the
        # original user-owned predicate. Production authentication always
        # resolves a real user before this helper is reached.
        return {"user_id": user_id}
    return profile_access_query(user)


def _load_accessible_profile(user_id: str, profile_id: str) -> dict:
    collection = get_mongodb_collection("linkedin_profiles")
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LinkedIn profiles database unavailable",
        )
    profile_doc = collection.find_one({"_id": profile_id, **_profile_query(user_id)})
    if not profile_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found or access denied",
        )
    return profile_doc


def _normalize_proxy_server(proxy_server: str) -> str:
    """Validate a proxy URL and default to HTTP when no scheme is supplied."""
    value = (proxy_server or "").strip()
    if not value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Proxy server URL is required",
        )
    if "://" not in value:
        value = f"http://{value}"
    parsed = urlparse(value)
    if parsed.scheme.lower() not in _ALLOWED_PROXY_SCHEMES or not parsed.hostname:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Invalid proxy URL. Use http://host:port, https://host:port, "
                "or socks5://host:port"
            ),
        )
    if parsed.username is not None or parsed.password is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Do not embed credentials in the proxy URL. Enter the proxy "
                "username and password in their separate fields."
            ),
        )
    from openoutreach.proxies.service import ProxyError, validate_proxy_host

    try:
        validate_proxy_host(parsed.hostname)
    except ProxyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Proxy host is invalid or not publicly routable",
        )
    return value


def _mask_proxy_username(username: Optional[str], proxy_mode: str) -> Optional[str]:
    """Never return a full managed-proxy username to the client."""
    if proxy_mode == "managed" and username:
        return "***"
    return username


def _public_proxy_server(proxy_server: Optional[str]) -> Optional[str]:
    """Strip embedded userinfo so a BYO password never appears in a response."""
    if not proxy_server:
        return proxy_server
    parsed = urlparse(proxy_server)
    if parsed.username is None and parsed.password is None:
        return proxy_server
    netloc = parsed.hostname or ""
    if parsed.port:
        netloc += f":{parsed.port}"
    return urlunparse(
        (parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment)
    )


def _encrypt_proxy_password(proxy_password: str) -> str:
    """Encrypt a proxy password for storage, failing closed on crypto errors."""
    try:
        encrypted = safe_encrypt(proxy_password)
    except Exception as e:
        logger.error("Failed to encrypt proxy password; exception_type=%s", type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to encrypt proxy credentials",
        )
    if not encrypted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to encrypt proxy credentials",
        )
    return encrypted


# Request/Response schemas
class CookieUploadRequest(BaseModel):
    """Request schema for cookie upload."""
    cookie_data: str | Dict | List

    model_config = ConfigDict(json_schema_extra={
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
        })


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
        logger.error("Failed to encrypt cookie data; exception_type=%s", type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Encryption failed"
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
        # Query profiles in the caller's active organization scope.
        query = _profile_query(user_id)
        cursor = collection.find(query).skip(skip).limit(limit)
        docs = list(cursor)
        profile_ids = [str(doc.get("_id")) for doc in docs]

        # Build a profile_id -> credential email map for fallback display label
        creds_collection = get_mongodb_collection("linkedin_credentials")
        cred_email_by_profile: dict = {}
        if creds_collection is not None and profile_ids:
            for cred in creds_collection.find(
                {"linkedin_profile_id": {"$in": profile_ids}},
                {"linkedin_profile_id": 1, "email": 1},
            ):
                pid = cred.get("linkedin_profile_id")
                if pid and "email" in cred:
                    cred_email_by_profile[str(pid)] = cred["email"]

        profiles = []
        for doc in docs:
            profile_id = str(doc.get("_id"))
            username = doc.get("linkedin_username") or cred_email_by_profile.get(profile_id, "")
            profiles.append({
                "id": profile_id,
                "linkedin_username": username,
                "active": doc.get("active", True),
                "has_cookies": bool(doc.get("cookie_data_encrypted")),
                "connect_daily_limit": doc.get("connect_daily_limit", 20),
                "follow_up_daily_limit": doc.get("follow_up_daily_limit", 25),
                "org_id": doc.get("org_id"),
                "assigned_user_id": doc.get("assigned_user_id"),
                "execution_mode": doc.get("execution_mode", "desktop"),
                "proxy_mode": doc.get("proxy_mode", "none"),
            })

        count = collection.count_documents(query)

        return ProfileListResponse(profiles=profiles, count=count)

    except Exception as e:
        logger.error("Failed to list LinkedIn profiles; exception_type=%s", type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve profiles"
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

    # Verify profile exists and user has org-scoped access
    try:
        access_query = _profile_query(user_id)
        profile = collection.find_one({"_id": profile_id, **access_query})
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found or access denied"
            )
    except Exception as e:
        logger.error("Failed to find profile %s; exception_type=%s", profile_id, type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error"
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
        logger.warning("Rejected invalid LinkedIn cookie payload; exception_type=%s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid cookie format"
        )
    except Exception as e:
        logger.error("Failed to parse cookie data; exception_type=%s", type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid cookie format"
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
            {"_id": profile_id, **access_query},
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
        logger.error("Failed to save cookie data; exception_type=%s", type(e).__name__)
        return CookieUploadResponse(
            success=False,
            message="",
            error="Unable to save cookie data"
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
        ctx = resolve_org_context(user)
        # Create profile
        profile = LinkedInProfile(
            user_id=user_id,
            org_id=ctx.org_id,
            assigned_user_id=user_id,
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
            logger.warning("Failed to create SmartRateLimitContext; exception_type=%s", type(e).__name__)

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
        logger.error("Failed to create LinkedIn profile; exception_type=%s", type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create profile"
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
        # Get all profiles in the caller's organization scope
        profiles_cursor = profiles_collection.find(_profile_query(user_id))
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
                            logger.error("Failed to get error logs; exception_type=%s", type(e).__name__)
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
                "linkedinUsername": linkedin_username,
                "status": active,
                "credentialsStatus": credentials_status,
                "healthScore": health_score,
                "healthStatus": health_status,
                "needsAttention": needs_attention,
                "lastError": last_error,
                "lastVerification": last_verification,
            })

        needs_attention_count = sum(
            1 for p in profile_health_data if p["needsAttention"]
        )

        return {
            "profiles": profile_health_data,
            "count": len(profile_health_data),
            "totalProfiles": total_profiles,
            "needsAttentionCount": needs_attention_count,
        }

    except Exception as e:
        logger.error("Failed to get profile health; exception_type=%s", type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve profile health"
        )


@router.get("/daemon/status")
async def get_daemon_status(user_id: str = Depends(get_current_user)):
    """Get desktop daemon status for the current user.

    Returns daemon health, session state, and verification requirements.
    """
    from datetime import datetime, timezone
    from openoutreach.linkedin.models import LinkedInProfile

    try:
        collection = get_mongodb_collection("linkedin_profiles")
        if collection is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LinkedIn profiles database unavailable",
            )
        profiles = [
            LinkedInProfile.from_dict(doc)
            for doc in collection.find({**_profile_query(user_id), "active": True})
        ]

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
        logger.error("Failed to get daemon status; exception_type=%s", type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve daemon status"
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
        profile_doc = collection.find_one({"_id": profile_id, **_profile_query(user_id)})
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
        logger.error("Failed to get LinkedIn profile; exception_type=%s", type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve profile"
        )


@router.put("/{profile_id}", response_model=LinkedInProfileResponse)
async def update_profile(
    profile_id: str,
    linkedin_username: Optional[str] = Body(None),
    active: Optional[bool] = Body(None),
    connect_daily_limit: Optional[int] = Body(None),
    follow_up_daily_limit: Optional[int] = Body(None),
    user_id: str = Depends(get_current_user),
):
    """
    Update a LinkedIn profile.

    Multi-tenant: verifies user owns the profile before updating.
    Only provided fields are updated. Proxy changes go through the dedicated
    ``PUT /{profile_id}/proxy`` endpoint so managed proxies stay read-only.
    """
    collection = get_mongodb_collection("linkedin_profiles")
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LinkedIn profiles database unavailable"
        )

    try:
        # Verify ownership
        profile_doc = collection.find_one({"_id": profile_id, **_profile_query(user_id)})
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

        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )

        # Apply update
        collection.update_one(
            {"_id": profile_id, **_profile_query(user_id)},
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
        logger.error("Failed to update LinkedIn profile; exception_type=%s", type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )


@router.put("/{profile_id}/proxy")
async def update_proxy_config(
    profile_id: str,
    proxy_server: Optional[str] = Body(None),
    proxy_username: Optional[str] = Body(None),
    proxy_password: Optional[str] = Body(None),
    user_id: str = Depends(get_current_user),
):
    """
    Set or clear the proxy for one LinkedIn profile.

    Each cloud-executed LinkedIn account should have its own proxy or sticky
    session; the server daemon passes this configuration to Playwright when it
    launches that profile's browser.

    - Empty/null ``proxy_server`` clears the whole proxy configuration.
    - An empty ``proxy_username`` clears the stored username.
    - An empty ``proxy_password`` keeps the stored password, because the UI
      never displays the existing secret.
    """
    collection = get_mongodb_collection("linkedin_profiles")
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LinkedIn profiles database unavailable",
        )

    try:
        profile_doc = collection.find_one({"_id": profile_id, **_profile_query(user_id)})
        if not profile_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found or access denied",
            )

        stored_proxy_id = profile_doc.get("proxy_id")
        stored_proxy_mode = profile_doc.get("proxy_mode")

        user = User.get(user_id)
        if user is not None and not can_manage_proxies(resolve_org_context(user).role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only workspace owners and admins can manage proxies",
            )

        if stored_proxy_mode == "managed" or stored_proxy_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Managed proxies are read-only. Contact support to change "
                    "or remove the proxy for this account."
                ),
            )

        if not proxy_server or not proxy_server.strip():
            updates: dict[str, object] = {
                "proxy_server": None,
                "proxy_username": None,
                "proxy_password": None,
                "proxy_password_encrypted": None,
                "proxy_id": None,
                "proxy_mode": "none",
            }
            if stored_proxy_id:
                from openoutreach.proxies.service import retire_proxy_for_profile

                retire_proxy_for_profile(profile_id)
        else:
            normalized_server = _normalize_proxy_server(proxy_server)
            unchanged_managed = bool(
                stored_proxy_id
                and profile_doc.get("proxy_server") == normalized_server
            )
            previous_server = _public_proxy_server(profile_doc.get("proxy_server"))
            same_server = bool(previous_server) and previous_server == normalized_server
            updates = {
                "proxy_server": normalized_server,
                "proxy_id": stored_proxy_id if unchanged_managed else None,
                "proxy_mode": stored_proxy_mode if unchanged_managed else "byo",
            }
            if stored_proxy_id and not unchanged_managed:
                from openoutreach.proxies.service import retire_proxy_for_profile

                retire_proxy_for_profile(profile_id)
            if not same_server:
                # A stored password belongs to the old host. Never carry it to
                # a new endpoint; that would send the previous secret to a host
                # chosen in this request.
                updates["proxy_username"] = None
                updates["proxy_password"] = None
                updates["proxy_password_encrypted"] = None
            if proxy_username is not None:
                updates["proxy_username"] = proxy_username.strip() or None
            if proxy_password:
                updates["proxy_password"] = None
                updates["proxy_password_encrypted"] = _encrypt_proxy_password(
                    proxy_password
                )
            if profile_doc.get("execution_mode") == "cloud":
                from openoutreach.organizations.enforcement import resolve_effective_plan

                user = User.get(user_id)
                if user:
                    effective = resolve_effective_plan(user)
                    seat_limit = effective.cloud_seat_limit
                    ctx = resolve_org_context(user)
                    other_active = collection.count_documents({
                        "org_id": ctx.org_id,
                        "is_active": True,
                        "execution_mode": "cloud",
                        "_id": {"$ne": profile_id},
                    })
                    if seat_limit > 0 and other_active < seat_limit:
                        updates["active"] = True
                        updates["is_active"] = True
                        updates["daemon_status"] = "proxy_ready"

        collection.update_one(
            {"_id": profile_id, **_profile_query(user_id)},
            {"$set": updates},
        )

        updated_doc = collection.find_one({"_id": profile_id, **_profile_query(user_id)})
        if not updated_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found after update",
            )

        updated_mode = updated_doc.get("proxy_mode", "none")
        return {
            "success": True,
            "has_proxy": bool(updated_doc.get("proxy_server")),
            "proxy_server": _public_proxy_server(updated_doc.get("proxy_server")),
            "proxy_username": _mask_proxy_username(
                updated_doc.get("proxy_username"), updated_mode
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update proxy config; exception_type=%s", type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update proxy config",
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
        profile_doc = collection.find_one({"_id": profile_id, **_profile_query(user_id)})
        if not profile_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found or access denied"
            )

        user = User.get(user_id)
        if user is not None and not can_manage_proxies(resolve_org_context(user).role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only workspace owners and admins can manage proxies",
            )

        # Test proxy connectivity. The neutral IP check is the primary signal;
        # LinkedIn is a secondary check because it may block the request while
        # the proxy itself is healthy.
        stored_password = safe_decrypt(
            profile_doc.get("proxy_password_encrypted")
            or profile_doc.get("proxy_password")
            or ""
        )
        stored_username = profile_doc.get("proxy_username")
        if not proxy_password and stored_password:
            stored_server = _public_proxy_server(profile_doc.get("proxy_server")) or ""
            try:
                same_server = bool(stored_server) and (
                    _normalize_proxy_server(stored_server)
                    == _normalize_proxy_server(proxy_server)
                )
            except HTTPException:
                same_server = False
            if same_server:
                proxy_password = stored_password
                if not proxy_username or "…" in proxy_username or "***" in proxy_username:
                    proxy_username = stored_username

        from openoutreach.proxies.service import check_proxy_connection

        result = await check_proxy_connection(
            _normalize_proxy_server(proxy_server),
            proxy_username,
            proxy_password,
        )
        return {
            "success": result.get("success", False),
            "message": result.get("message", "Proxy test failed"),
            "ip": result.get("ip"),
            "status_code": result.get("status_code"),
            "latency_ms": result.get("latency_ms"),
            "error": result.get("error"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to test proxy; exception_type=%s", type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to test proxy"
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
        profile_doc = collection.find_one({"_id": profile_id, **_profile_query(user_id)})
        if not profile_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found or access denied"
            )

        proxy_server = _public_proxy_server(profile_doc.get("proxy_server"))
        proxy_mode = profile_doc.get("proxy_mode", "none")
        proxy_username = _mask_proxy_username(
            profile_doc.get("proxy_username"), proxy_mode
        )
        has_proxy_password = bool(
            profile_doc.get("proxy_password_encrypted")
            or profile_doc.get("proxy_password")
        )
        proxy_id = profile_doc.get("proxy_id")
        proxy_health: dict = {}
        if proxy_id:
            from openoutreach.proxies.models import Proxy

            proxy = Proxy.get(proxy_id)
            if proxy:
                proxy_health = {
                    "proxy_status": proxy.status,
                    "last_tested_at": (
                        proxy.last_tested_at.isoformat()
                        if proxy.last_tested_at
                        else None
                    ),
                    "last_test_ip": proxy.last_test_ip,
                    "last_test_country": proxy.last_test_country,
                    "last_test_latency_ms": proxy.last_test_latency_ms,
                    "last_error": proxy.last_error,
                    "country_mismatch": proxy.country_mismatch,
                }

        return {
            "profile_id": profile_id,
            "proxy_server": proxy_server,
            "proxy_username": proxy_username,
            "proxy_password": "********" if has_proxy_password else None,
            "has_proxy": proxy_server is not None,
            "proxy_mode": proxy_mode,
            "proxy_id": proxy_id,
            "proxy_region_country": profile_doc.get("proxy_region_country"),
            "proxy_region_subdivision": profile_doc.get("proxy_region_subdivision"),
            "proxy_region_city": profile_doc.get("proxy_region_city"),
            **proxy_health,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get proxy config; exception_type=%s", type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve proxy config"
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
        # Verify org-scoped access
        profile_doc = profiles_collection.find_one({"_id": profile_id, **_profile_query(user_id)})
        if not profile_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found or access denied"
            )

        deleting_user = User.get(user_id)
        if deleting_user is not None and not can_delete_profile(deleting_user, profile_doc):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only workspace owners and admins can delete a profile",
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
            logger.warning("Failed to delete SmartRateLimitContext; exception_type=%s", type(e).__name__)

        # A seat is consumed only when the profile owns a credential. A Cloud
        # Duo WhatsApp number that survives the LinkedIn deletion becomes its
        # own unit, so the counter must not be decremented in that case.
        credentials_collection = get_mongodb_collection("linkedin_credentials")
        had_credentials = bool(
            credentials_collection is not None
            and credentials_collection.count_documents(
                {"linkedin_profile_id": profile_id}
            )
            > 0
        )
        from openoutreach.billing.cloud_seats import (
            linkedin_profile_shares_seat_with_whatsapp,
        )

        seat_survives_for_whatsapp = (
            had_credentials
            and profile_doc.get("execution_mode") == "cloud"
            and linkedin_profile_shares_seat_with_whatsapp(
                profile_id,
                org_id=profile_doc.get("org_id"),
                owner_user_id=profile_doc.get("user_id"),
            )
        )
        is_cloud_profile = profile_doc.get("execution_mode") == "cloud"

        # Delete profile
        result = profiles_collection.delete_one({"_id": profile_id})
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found or access denied"
            )

        # Never recycle a used proxy identity. Retiring keeps the record for
        # audit and blocks assignment to a different LinkedIn account.
        from openoutreach.proxies.service import retire_proxy_for_profile

        retire_proxy_for_profile(profile_id)
        if had_credentials and not seat_survives_for_whatsapp:
            release_linkedin_seat(user_id)
            if is_cloud_profile:
                from openoutreach.billing.cloud_seats import release_cloud_seat

                release_cloud_seat(user_id)

        logger.info(f"Deleted LinkedIn profile {profile_id} for user {user_id}")
        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete LinkedIn profile; exception_type=%s", type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete profile"
        )
