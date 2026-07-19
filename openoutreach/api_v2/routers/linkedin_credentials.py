"""
LinkedIn Credentials Router - Full CRUD + verification + health + audit logs

Provides endpoints for managing LinkedIn credentials with encryption,
verification, health monitoring, rotation, and audit logging.
"""

import json
import logging
from datetime import datetime, timezone as tz
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel

from openoutreach.api_v2.dependencies_v2 import get_current_user
from openoutreach.api_v2.schemas.linkedin import (
    LinkedInCredentialCreate,
    LinkedInCredentialResponse,
    LinkedInCredentialUpdate,
    LinkedInCredentialLogResponse,
    LinkedInProfileHealthResponse,
)
from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.mongodb.models import LinkedInCredentials, LinkedInCredentialLog
from openoutreach.linkedin.models import LinkedInProfile

logger = logging.getLogger(__name__)
router = APIRouter()


# Request/Response schemas
class CredentialListResponse(BaseModel):
    """Response schema for credential list."""
    credentials: List[LinkedInCredentialResponse]
    count: int


class VerifyRequest(BaseModel):
    """Request schema for credential verification."""
    test_login: bool = True


class VerifyResponse(BaseModel):
    """Response schema for credential verification."""
    success: bool
    message: str
    status: str
    error: Optional[str] = None


class ConfirmRequest(BaseModel):
    """Request schema for confirming credentials after test."""
    verified: bool
    notes: Optional[str] = None


class RotateResponse(BaseModel):
    """Response schema for credential rotation."""
    success: bool
    message: str
    backup_id: Optional[str] = None
    error: Optional[str] = None


class LogsResponse(BaseModel):
    """Response schema for audit logs."""
    logs: List[LinkedInCredentialLogResponse]
    count: int


# Endpoints

@router.get("/", response_model=CredentialListResponse)
async def list_credentials(
    user_id: str = Depends(get_current_user),
):
    """
    List all LinkedIn credentials for the current user.

    Multi-tenant: returns credentials owned by the authenticated user.
    Includes metadata, status, and recent audit logs.
    """
    try:
        credentials = LinkedInCredentials.find_by_user_id(user_id)

        # Convert to response format
        credential_responses = []
        for cred in credentials:
            # Get recent logs
            logs_collection = get_mongodb_collection("linkedin_credential_logs")
            recent_logs = []
            if logs_collection is not None:
                log_docs = logs_collection.find(
                    {"credential_id": cred._id}
                ).sort("created_at", -1).limit(5)
                recent_logs = [
                    {
                        "id": str(doc["_id"]),
                        "credential_id": doc["credential_id"],
                        "action": doc["action"],
                        "details": doc.get("details", {}),
                        "ip_address": doc.get("ip_address"),
                        "user_agent": doc.get("user_agent", ""),
                        "created_at": doc["created_at"],
                    }
                    for doc in log_docs
                ]

            credential_responses.append(
                LinkedInCredentialResponse(
                    id=cred._id,
                    linkedin_profile_id=cred.linkedin_profile_id,
                    email_encrypted=cred.email_encrypted,
                    username=cred.username,
                    status=cred.status,
                    last_verified=cred.last_verified,
                    verification_failed_at=cred.verification_failed_at,
                    verification_failures=cred.verification_failures,
                    usage_count=cred.usage_count,
                    last_used=cred.last_used,
                    campaign_id=cred.campaign_id,
                    user_id=cred.user_id,
                    created_at=cred.created_at,
                    updated_at=cred.updated_at,
                    expires_at=cred.expires_at,
                    rotated_at=cred.rotated_at,
                    rotation_required_days=cred.rotation_required_days,
                    is_primary=cred.is_primary,
                    is_backup=cred.is_backup,
                    backup_of_id=cred.backup_of_id,
                    security_alert_sent_at=cred.security_alert_sent_at,
                    logs=recent_logs if recent_logs else None,
                )
            )

        return CredentialListResponse(
            credentials=credential_responses,
            count=len(credential_responses)
        )
    except Exception as e:
        logger.error(f"Failed to list credentials: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list credentials: {str(e)}"
        )


@router.post("/", response_model=LinkedInCredentialResponse, status_code=status.HTTP_201_CREATED)
async def create_credential(
    data: LinkedInCredentialCreate,
    request: Request,
    user_id: str = Depends(get_current_user),
):
    """
    Create new LinkedIn credentials.

    Encrypts email and password, creates or attaches to a LinkedIn profile,
    and logs the creation event.
    """
    try:
        # Encrypt credentials
        email_encrypted = LinkedInCredentials.encrypt(data.email)
        password_encrypted = LinkedInCredentials.encrypt(data.password)

        # Get or create LinkedIn profile
        profile = None
        if data.linkedin_profile_id:
            profile = LinkedInProfile.get(data.linkedin_profile_id)
            if not profile:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="LinkedIn profile not found"
                )
            if profile.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="LinkedIn profile belongs to another user"
                )
        else:
            # Auto-create profile for this user
            profile = LinkedInProfile(
                user_id=user_id,
                linkedin_username=data.email,
                active=True,
            )
            profile.save()

        # Create credential
        credential = LinkedInCredentials(
            linkedin_profile_id=profile._id,
            email_encrypted=email_encrypted,
            password_encrypted=password_encrypted,
            username=data.username or "",
            status=LinkedInCredentials.STATUS_STORED,
            campaign_id=data.campaign_id,
            user_id=user_id,
            is_primary=data.is_primary,
            is_backup=data.is_backup,
            backup_of_id=data.backup_of_id,
            rotation_required_days=data.rotation_required_days,
        )
        credential.save()

        # Sync login fields to profile
        profile.linkedin_username = data.email
        profile.linkedin_password = data.password
        profile.save(update_fields=["linkedin_username", "linkedin_password"])

        # Log creation
        log_entry = LinkedInCredentialLog(
            credential_id=credential._id,
            action="created",
            details={"email": data.email, "profile_id": profile._id},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent", ""),
        )
        log_entry.save()

        return LinkedInCredentialResponse(
            id=credential._id,
            linkedin_profile_id=credential.linkedin_profile_id,
            email_encrypted=credential.email_encrypted,
            username=credential.username,
            status=credential.status,
            last_verified=credential.last_verified,
            verification_failed_at=credential.verification_failed_at,
            verification_failures=credential.verification_failures,
            usage_count=credential.usage_count,
            last_used=credential.last_used,
            campaign_id=credential.campaign_id,
            user_id=credential.user_id,
            created_at=credential.created_at,
            updated_at=credential.updated_at,
            expires_at=credential.expires_at,
            rotated_at=credential.rotated_at,
            rotation_required_days=credential.rotation_required_days,
            is_primary=credential.is_primary,
            is_backup=credential.is_backup,
            backup_of_id=credential.backup_of_id,
            security_alert_sent_at=credential.security_alert_sent_at,
            logs=None,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create credential: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create credential: {str(e)}"
        )


@router.get("/{credential_id}", response_model=LinkedInCredentialResponse)
async def get_credential(
    credential_id: str,
    user_id: str = Depends(get_current_user),
):
    """
    Get a specific LinkedIn credential by ID.

    Multi-tenant: verifies ownership before returning.
    """
    credential = LinkedInCredentials.get(credential_id)
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found"
        )

    if credential.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    # Get recent logs
    logs_collection = get_mongodb_collection("linkedin_credential_logs")
    recent_logs = []
    if logs_collection is not None:
        log_docs = logs_collection.find(
            {"credential_id": credential._id}
        ).sort("created_at", -1).limit(10)
        recent_logs = [
            {
                "id": str(doc["_id"]),
                "credential_id": doc["credential_id"],
                "action": doc["action"],
                "details": doc.get("details", {}),
                "ip_address": doc.get("ip_address"),
                "user_agent": doc.get("user_agent", ""),
                "created_at": doc["created_at"],
            }
            for doc in log_docs
        ]

    return LinkedInCredentialResponse(
        id=credential._id,
        linkedin_profile_id=credential.linkedin_profile_id,
        email_encrypted=credential.email_encrypted,
        username=credential.username,
        status=credential.status,
        last_verified=credential.last_verified,
        verification_failed_at=credential.verification_failed_at,
        verification_failures=credential.verification_failures,
        usage_count=credential.usage_count,
        last_used=credential.last_used,
        campaign_id=credential.campaign_id,
        user_id=credential.user_id,
        created_at=credential.created_at,
        updated_at=credential.updated_at,
        expires_at=credential.expires_at,
        rotated_at=credential.rotated_at,
        rotation_required_days=credential.rotation_required_days,
        is_primary=credential.is_primary,
        is_backup=credential.is_backup,
        backup_of_id=credential.backup_of_id,
        security_alert_sent_at=credential.security_alert_sent_at,
        logs=recent_logs if recent_logs else None,
    )


@router.patch("/{credential_id}", response_model=LinkedInCredentialResponse)
async def update_credential(
    credential_id: str,
    data: LinkedInCredentialUpdate,
    request: Request,
    user_id: str = Depends(get_current_user),
):
    """
    Update LinkedIn credentials.

    Allows partial updates. Re-encrypts email/password if provided.
    """
    credential = LinkedInCredentials.get(credential_id)
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found"
        )

    if credential.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    try:
        update_fields = []
        changes = {}

        if data.email is not None:
            credential.email_encrypted = LinkedInCredentials.encrypt(data.email)
            update_fields.append("email_encrypted")
            changes["email"] = data.email

            # Sync to profile
            if credential.linkedin_profile_id:
                profile = LinkedInProfile.get(credential.linkedin_profile_id)
                if profile:
                    profile.linkedin_username = data.email
                    profile.save(update_fields=["linkedin_username"])

        if data.password is not None:
            credential.password_encrypted = LinkedInCredentials.encrypt(data.password)
            update_fields.append("password_encrypted")
            changes["password"] = "***updated***"

            # Sync to profile
            if credential.linkedin_profile_id:
                profile = LinkedInProfile.get(credential.linkedin_profile_id)
                if profile:
                    profile.linkedin_password = data.password
                    profile.save(update_fields=["linkedin_password"])

        if data.username is not None:
            credential.username = data.username
            update_fields.append("username")
            changes["username"] = data.username

        if data.status is not None:
            credential.status = data.status
            update_fields.append("status")
            changes["status"] = data.status

        if data.linkedin_profile_id is not None:
            credential.linkedin_profile_id = data.linkedin_profile_id
            update_fields.append("linkedin_profile_id")
            changes["profile_id"] = data.linkedin_profile_id

        if data.campaign_id is not None:
            credential.campaign_id = data.campaign_id
            update_fields.append("campaign_id")
            changes["campaign_id"] = data.campaign_id

        if data.is_primary is not None:
            credential.is_primary = data.is_primary
            update_fields.append("is_primary")
            changes["is_primary"] = data.is_primary

        if data.is_backup is not None:
            credential.is_backup = data.is_backup
            update_fields.append("is_backup")
            changes["is_backup"] = data.is_backup

        if data.rotation_required_days is not None:
            credential.rotation_required_days = data.rotation_required_days
            update_fields.append("rotation_required_days")
            changes["rotation_required_days"] = data.rotation_required_days

        if update_fields:
            credential.save(update_fields=update_fields)

            # Log update
            log_entry = LinkedInCredentialLog(
                credential_id=credential._id,
                action="updated",
                details=changes,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent", ""),
            )
            log_entry.save()

        return LinkedInCredentialResponse(
            id=credential._id,
            linkedin_profile_id=credential.linkedin_profile_id,
            email_encrypted=credential.email_encrypted,
            username=credential.username,
            status=credential.status,
            last_verified=credential.last_verified,
            verification_failed_at=credential.verification_failed_at,
            verification_failures=credential.verification_failures,
            usage_count=credential.usage_count,
            last_used=credential.last_used,
            campaign_id=credential.campaign_id,
            user_id=credential.user_id,
            created_at=credential.created_at,
            updated_at=credential.updated_at,
            expires_at=credential.expires_at,
            rotated_at=credential.rotated_at,
            rotation_required_days=credential.rotation_required_days,
            is_primary=credential.is_primary,
            is_backup=credential.is_backup,
            backup_of_id=credential.backup_of_id,
            security_alert_sent_at=credential.security_alert_sent_at,
            logs=None,
        )
    except Exception as e:
        logger.error(f"Failed to update credential: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update credential: {str(e)}"
        )


@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    credential_id: str,
    request: Request,
    user_id: str = Depends(get_current_user),
):
    """
    Delete LinkedIn credentials.

    Also clears synced login fields from the linked profile.
    """
    credential = LinkedInCredentials.get(credential_id)
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found"
        )

    if credential.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    try:
        # Clear synced fields from profile
        if credential.linkedin_profile_id:
            profile = LinkedInProfile.get(credential.linkedin_profile_id)
            if profile:
                profile.linkedin_username = ""
                profile.linkedin_password = ""
                profile.cookie_data_encrypted = None
                profile.save(update_fields=["linkedin_username", "linkedin_password", "cookie_data_encrypted"])

        # Log deletion
        log_entry = LinkedInCredentialLog(
            credential_id=credential._id,
            action="deleted",
            details={"email": credential.get_public_email()},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent", ""),
        )
        log_entry.save()

        # Delete credential
        LinkedInCredentials.delete(credential_id)

        return None
    except Exception as e:
        logger.error(f"Failed to delete credential: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete credential: {str(e)}"
        )


@router.post("/{credential_id}/verify", response_model=VerifyResponse)
async def verify_credential(
    credential_id: str,
    data: VerifyRequest,
    request: Request,
    user_id: str = Depends(get_current_user),
):
    """
    Verify LinkedIn credentials by attempting a test login.

    Opens a browser session, attempts login, and updates status.
    """
    credential = LinkedInCredentials.get(credential_id)
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found"
        )

    if credential.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    if not data.test_login:
        # Just mark as tested without actual verification
        credential.status = LinkedInCredentials.STATUS_TESTED
        credential.last_verified = datetime.now(tz.utc)
        credential.save(update_fields=["status", "last_verified"])

        log_entry = LinkedInCredentialLog(
            credential_id=credential._id,
            action="verified",
            details={"method": "manual", "status": "success"},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent", ""),
        )
        log_entry.save()

        return VerifyResponse(
            success=True,
            message="Credentials marked as tested",
            status=LinkedInCredentials.STATUS_TESTED
        )

    # Actual browser-based verification
    from linkedin_cli.auth import authenticate
    from linkedin_cli.browser.login import launch_browser
    from linkedin_cli.page_state import IllegalPageTransition

    # Get profile for proxy and VNC configuration (outside try block so it's accessible in except)
    profile = None
    if credential.linkedin_profile_id:
        profile = LinkedInProfile.get(credential.linkedin_profile_id)

    try:
        email = credential.get_email()
        password = credential.get_password()

        # Extract proxy configuration from profile (web daemon only)
        proxy_server = None
        proxy_username = None
        proxy_password = None
        display_override = None

        if profile:
            proxy_server = profile.proxy_server
            proxy_username = profile.proxy_username
            proxy_password = profile.proxy_password

            # Get VNC display for this profile (web daemon only)
            try:
                from openoutreach.core.vnc_manager import get_or_create_vnc_session
                vnc_session = get_or_create_vnc_session(str(profile.pk))
                if vnc_session:
                    display_override = vnc_session.display
                    logger.debug("Using VNC display %s for verification", display_override)
            except Exception as e:
                logger.debug("Could not get VNC display: %s", e)

        # Launch browser with proxy and VNC support
        page, context, browser, playwright = launch_browser(
            proxy_server=proxy_server,
            proxy_username=proxy_username,
            proxy_password=proxy_password,
            display_override=display_override,
        )

        # Create mock profile for session
        class MockProfile:
            def __init__(self, cred: LinkedInCredentials):
                self._id = cred.linkedin_profile_id or str(uuid4())
                self.linkedin_username = email
                self.linkedin_password = password
                self._cookie_data_json = None

            def save(self, update_fields: Optional[List[str]] = None):
                pass

            def refresh_from_db(self, fields: Optional[List[str]] = None):
                pass

            @property
            def cookie_data(self):
                return None

            @cookie_data.setter
            def cookie_data(self, value):
                pass

            @property
            def pk(self):
                return self._id

        # Create session
        class MockSession:
            def __init__(self, profile_obj):
                self.linkedin_profile = profile_obj
                self.page = page
                self.context = context
                self.browser = browser
                self.playwright = playwright
                self.campaign = None
                self.user = None

            def close(self):
                if context:
                    context.close()
                if browser:
                    browser.close()
                if playwright:
                    playwright.stop()

        mock_profile = MockProfile(credential)
        session = MockSession(mock_profile)

        try:
            # Attempt authentication
            authenticate(session, username=email, password=password)

            # Success
            credential.mark_verified()
            credential.verification_failures = 0
            credential.verification_failed_at = None
            credential.save(update_fields=["status", "last_verified", "verification_failures", "verification_failed_at"])

            # Update profile session state
            if profile:
                profile.is_logged_in = True
                profile.requires_verification = False
                profile.verification_type = None
                profile.session_updated_at = datetime.now(tz.utc)
                profile.save(update_fields=["is_logged_in", "requires_verification", "verification_type", "session_updated_at"])

            log_entry = LinkedInCredentialLog(
                credential_id=credential._id,
                action="verified",
                details={"method": "browser_login", "status": "success"},
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent", ""),
            )
            log_entry.save()

            return VerifyResponse(
                success=True,
                message="Credentials verified successfully",
                status=credential.status
            )
        finally:
            session.close()

    except IllegalPageTransition as e:
        # Challenge/verification detected
        logger.warning(f"Verification requires challenge: {e}")

        # Update profile to indicate verification required
        if profile:
            profile.is_logged_in = False
            profile.requires_verification = True
            profile.verification_type = "challenge"
            profile.session_updated_at = datetime.now(tz.utc)
            profile.save(update_fields=["is_logged_in", "requires_verification", "verification_type", "session_updated_at"])

        log_entry = LinkedInCredentialLog(
            credential_id=credential._id,
            action="awaiting_challenge",
            details={"method": "browser_login", "message": str(e)},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent", ""),
        )
        log_entry.save()

        return VerifyResponse(
            success=False,
            message="LinkedIn requires verification. Please complete the challenge.",
            status=credential.status,
            error=json.dumps({"errorType": "awaiting_challenge", "message": str(e)})
        )

    except Exception as e:
        logger.error(f"Verification failed: {e}")

        # Mark as failed
        credential.mark_verification_failed()
        credential.save(update_fields=["status", "verification_failed_at", "verification_failures"])

        log_entry = LinkedInCredentialLog(
            credential_id=credential._id,
            action="failed",
            details={"method": "browser_login", "error": str(e)},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent", ""),
        )
        log_entry.save()

        return VerifyResponse(
            success=False,
            message="Verification failed",
            status=credential.status,
            error=str(e)
        )


@router.post("/{credential_id}/confirm", response_model=VerifyResponse)
async def confirm_credential(
    credential_id: str,
    data: ConfirmRequest,
    request: Request,
    user_id: str = Depends(get_current_user),
):
    """
    Confirm credentials after manual test (e.g., via VNC viewer).

    Used when automated verification is not possible (challenges, CAPTCHA).
    Checks if user successfully logged in via VNC by verifying the browser session state.
    """
    credential = LinkedInCredentials.get(credential_id)
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found"
        )

    if credential.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    # Get profile to check session state
    profile = None
    if credential.linkedin_profile_id:
        profile = LinkedInProfile.get(credential.linkedin_profile_id)

    # Auto-verify by checking if profile shows logged in state
    auto_verified = False
    if profile and profile.is_logged_in and not profile.requires_verification:
        auto_verified = True
        data.verified = True

    if data.verified:
        credential.mark_verified()
        credential.verification_failures = 0
        credential.verification_failed_at = None
        credential.save(update_fields=["status", "last_verified", "verification_failures", "verification_failed_at"])

        # Update profile session state
        if profile:
            profile.requires_verification = False
            profile.verification_type = None
            profile.session_updated_at = datetime.now(tz.utc)
            profile.save(update_fields=["requires_verification", "verification_type", "session_updated_at"])

        log_entry = LinkedInCredentialLog(
            credential_id=credential._id,
            action="verified",
            details={
                "method": "manual_confirmation" if not auto_verified else "auto_verified",
                "notes": data.notes,
            },
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent", ""),
        )
        log_entry.save()

        return VerifyResponse(
            success=True,
            message="Credentials confirmed",
            status=credential.status
        )
    else:
        # Check if challenge is still incomplete (user hasn't finished yet)
        if profile and profile.requires_verification:
            return VerifyResponse(
                success=False,
                message="Challenge not complete yet",
                status=credential.status,
                error=json.dumps({"errorType": "challenge_incomplete"})
            )

        # User explicitly marked as failed
        credential.mark_verification_failed()
        credential.save(update_fields=["status", "verification_failed_at", "verification_failures"])

        log_entry = LinkedInCredentialLog(
            credential_id=credential._id,
            action="failed",
            details={"method": "manual_confirmation", "notes": data.notes},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent", ""),
        )
        log_entry.save()

        return VerifyResponse(
            success=False,
            message="Credentials marked as failed",
            status=credential.status
        )


@router.post("/{credential_id}/rotate", response_model=RotateResponse)
async def rotate_credential(
    credential_id: str,
    request: Request,
    user_id: str = Depends(get_current_user),
):
    """
    Rotate credentials by creating a backup and prompting for new credentials.

    Marks current credential as backup, returns backup_id for client to create new primary.
    """
    credential = LinkedInCredentials.get(credential_id)
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found"
        )

    if credential.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    try:
        # Create backup using model method
        backup = credential.create_backup()

        # Mark current credential as rotated
        credential.rotated_at = datetime.now(tz.utc)
        credential.save(update_fields=["rotated_at"])

        # Log rotation
        log_entry = LinkedInCredentialLog(
            credential_id=credential._id,
            action="rotated",
            details={"backup_id": backup._id},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent", ""),
        )
        log_entry.save()

        return RotateResponse(
            success=True,
            message="Backup created, please create new primary credentials",
            backup_id=backup._id
        )
    except Exception as e:
        logger.error(f"Failed to rotate credential: {e}")
        return RotateResponse(
            success=False,
            message="Rotation failed",
            error=str(e)
        )


@router.get("/{credential_id}/health", response_model=LinkedInProfileHealthResponse)
async def get_credential_health(
    credential_id: str,
    user_id: str = Depends(get_current_user),
):
    """
    Get health status for a credential's linked profile.

    Returns health metrics, risk score, and recommendations.
    """
    credential = LinkedInCredentials.get(credential_id)
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found"
        )

    if credential.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    if not credential.linkedin_profile_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No linked profile found"
        )

    profile = LinkedInProfile.get(credential.linkedin_profile_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Linked profile not found"
        )

    # Calculate health metrics
    from openoutreach.mongodb.connection import get_mongodb_collection

    action_logs = get_mongodb_collection("action_logs")
    deals = get_mongodb_collection("deals")

    # Get recent activity
    last_active = None
    if action_logs is not None:
        recent_action = action_logs.find_one(
            {"linkedin_profile_id": profile._id},
            sort=[("created_at", -1)]
        )
        if recent_action:
            last_active = recent_action.get("created_at")

    # Calculate connection rate
    connection_rate = 0.0
    if action_logs is not None:
        sent = action_logs.count_documents({
            "linkedin_profile_id": profile._id,
            "action": "connect"
        })
        if sent > 0:
            # Count accepted connections
            accepted = 0
            if deals is not None:
                accepted = deals.count_documents({
                    "linkedin_profile_id": profile._id,
                    "state": "CONNECTED"
                })
            connection_rate = accepted / sent if sent > 0 else 0.0

    # Calculate response rate
    response_rate = 0.0
    messages_collection = get_mongodb_collection("messages")
    if messages_collection is not None:
        sent_msgs = messages_collection.count_documents({
            "sender": "seller",
            "linkedin_profile_id": profile._id
        })
        if sent_msgs > 0:
            replied = messages_collection.count_documents({
                "sender": "lead",
                "linkedin_profile_id": profile._id
            })
            response_rate = replied / sent_msgs if sent_msgs > 0 else 0.0

    # Daily limit usage
    daily_limit_usage = {}
    if action_logs is not None:
        today_start = datetime.now(tz.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        connect_count = action_logs.count_documents({
            "linkedin_profile_id": profile._id,
            "action": "connect",
            "created_at": {"$gte": today_start}
        })
        daily_limit_usage["connect"] = {
            "used": connect_count,
            "limit": profile.connect_daily_limit
        }

        followup_count = action_logs.count_documents({
            "linkedin_profile_id": profile._id,
            "action": "follow_up",
            "created_at": {"$gte": today_start}
        })
        daily_limit_usage["follow_up"] = {
            "used": followup_count,
            "limit": profile.follow_up_daily_limit
        }

    # Risk score (simple heuristic)
    risk_score = 0.0
    if credential.verification_failures > 0:
        risk_score += 0.2
    if credential.status == LinkedInCredentials.STATUS_LOCKED:
        risk_score += 0.5
    if connection_rate < 0.2:
        risk_score += 0.1
    risk_score = min(1.0, risk_score)

    # Recommendations
    recommendations = []
    if credential.status != LinkedInCredentials.STATUS_ACTIVE:
        recommendations.append("Verify credentials to activate profile")
    if connection_rate < 0.3:
        recommendations.append("Low connection rate - consider refining targeting")
    if response_rate < 0.2:
        recommendations.append("Low response rate - review message templates")
    if daily_limit_usage.get("connect", {}).get("used", 0) >= profile.connect_daily_limit:
        recommendations.append("Daily connection limit reached")
    if not recommendations:
        recommendations.append("Profile health looks good - maintain current cadence")

    # Alerts
    alerts = []
    if credential.verification_failures > 2:
        alerts.append({
            "severity": "warning",
            "message": f"{credential.verification_failures} consecutive verification failures"
        })
    if credential.status == LinkedInCredentials.STATUS_LOCKED:
        alerts.append({
            "severity": "critical",
            "message": "Credential is locked - manual intervention required"
        })

    # Overall status
    overall_status = "healthy"
    if credential.status in (LinkedInCredentials.STATUS_LOCKED, LinkedInCredentials.STATUS_INVALID):
        overall_status = "critical"
    elif credential.verification_failures > 0 or risk_score > 0.3:
        overall_status = "warning"

    return LinkedInProfileHealthResponse(
        profile_id=profile._id,
        overall_status=overall_status,
        credential_status=credential.status,
        last_active=last_active,
        connection_rate=connection_rate,
        response_rate=response_rate,
        daily_limit_usage=daily_limit_usage,
        risk_score=risk_score,
        recommendations=recommendations,
        alerts=alerts,
    )


@router.get("/{credential_id}/logs", response_model=LogsResponse)
async def get_credential_logs(
    credential_id: str,
    limit: int = 50,
    user_id: str = Depends(get_current_user),
):
    """
    Get audit logs for a credential.

    Returns paginated log entries showing verification, usage, and security events.
    """
    credential = LinkedInCredentials.get(credential_id)
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found"
        )

    if credential.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    logs_collection = get_mongodb_collection("linkedin_credential_logs")
    if logs_collection is None:
        return LogsResponse(logs=[], count=0)

    log_docs = logs_collection.find(
        {"credential_id": credential._id}
    ).sort("created_at", -1).limit(limit)

    logs = [
        LinkedInCredentialLogResponse(
            id=str(doc["_id"]),
            credential_id=doc["credential_id"],
            action=doc["action"],
            details=doc.get("details", {}),
            ip_address=doc.get("ip_address"),
            user_agent=doc.get("user_agent", ""),
            created_at=doc["created_at"],
        )
        for doc in log_docs
    ]

    return LogsResponse(logs=logs, count=len(logs))
