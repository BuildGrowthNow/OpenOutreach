"""
Desktop daemon status and heartbeat endpoints.
Allows desktop app to report connection status and frontend to check daemon health.
"""
import logging
from datetime import datetime, timezone as tz, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from openoutreach.api_v2.dependencies_v2 import get_current_user
from openoutreach.linkedin.models import LinkedInProfile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/desktop-daemon", tags=["desktop-daemon"])


class HeartbeatRequest(BaseModel):
    """Desktop daemon heartbeat payload."""
    profile_id: str
    daemon_version: Optional[str] = None
    platform: Optional[str] = None
    browser: Optional[str] = None


class HeartbeatResponse(BaseModel):
    """Heartbeat acknowledgment."""
    status: str
    next_heartbeat_seconds: int = 60


class ProfileStatusResponse(BaseModel):
    """Status for a single profile."""
    id: str
    email: str
    execution_mode: str
    is_connected: bool
    last_seen: Optional[str]
    daemon_status: str


class DaemonStatusResponse(BaseModel):
    """Overall daemon status for the user."""
    profiles: list[ProfileStatusResponse]


@router.post("/heartbeat", response_model=HeartbeatResponse)
async def desktop_heartbeat(
    request: HeartbeatRequest,
    http_request: Request,
    user_id: str = Depends(get_current_user),
) -> HeartbeatResponse:
    """
    Desktop daemon calls this every 60s to report status.
    Updates last_heartbeat timestamp and daemon metadata.
    """
    try:
        profile = LinkedInProfile.objects.get(_id=request.profile_id, user_id=user_id)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found or access denied",
            )

        # Update heartbeat timestamp and daemon info
        profile.last_heartbeat = datetime.now(tz.utc)
        profile.daemon_status = "connected"

        if request.daemon_version:
            profile.daemon_version = request.daemon_version
        if request.platform:
            profile.daemon_platform = request.platform
        if request.browser:
            profile.daemon_browser = request.browser

        # Capture the IP the daemon is connecting from (useful for debugging and transparency)
        client_ip = http_request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (
            http_request.client.host if http_request.client else None
        )
        if client_ip:
            profile.daemon_ip = client_ip

        profile.save()

        logger.debug(f"Heartbeat received for profile {profile._id} (user {user_id})")

        return HeartbeatResponse(
            status="ok",
            next_heartbeat_seconds=60,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Heartbeat error; profile_id=%s exception_type=%s",
            request.profile_id,
            type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process heartbeat",
        )


@router.get("/status", response_model=DaemonStatusResponse)
async def get_daemon_status(
    user_id: str = Depends(get_current_user),
) -> DaemonStatusResponse:
    """
    Frontend calls this to check desktop daemon connection status.
    Returns connection status for all user's profiles.
    """
    try:
        profiles = LinkedInProfile.objects.filter(user_id=user_id)

        profile_statuses = []
        now = datetime.now(tz.utc)
        connection_timeout = timedelta(minutes=2)  # Consider disconnected after 2min

        for profile in profiles:
            # Check if last heartbeat was recent
            is_connected = False
            if profile.last_heartbeat:
                hb = profile.last_heartbeat if profile.last_heartbeat.tzinfo else profile.last_heartbeat.replace(tzinfo=tz.utc)
                time_since_heartbeat = now - hb
                is_connected = time_since_heartbeat < connection_timeout

            # Update daemon_status based on heartbeat
            if is_connected:
                daemon_status = "connected"
            elif profile.last_heartbeat:
                daemon_status = "disconnected"
            else:
                daemon_status = "never_connected"

            profile_statuses.append(
                ProfileStatusResponse(
                    id=profile._id,
                    email=profile.linkedin_username,
                    execution_mode=profile.execution_mode,
                    is_connected=is_connected,
                    last_seen=profile.last_heartbeat.isoformat() if profile.last_heartbeat else None,
                    daemon_status=daemon_status,
                )
            )

        return DaemonStatusResponse(profiles=profile_statuses)

    except Exception as e:
        logger.error(
            "Failed to get daemon status; user_id=%s exception_type=%s",
            user_id,
            type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve daemon status",
        )
