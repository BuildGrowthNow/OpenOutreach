"""
Remote daemon communication endpoints.

Desktop app daemons use these to:
1. Claim and execute tasks
2. Report task results
3. Sync cookies/session state
4. Report health/status
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import logging

from openoutreach.api_v2.dependencies_v2 import get_current_user
from openoutreach.linkedin.models import LinkedInProfile
from openoutreach.core.models import Task, SiteConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/daemon", tags=["daemon"])


class DaemonHeartbeat(BaseModel):
    daemon_id: str
    linkedin_profile_id: str
    version: str
    platform: str  # "darwin" | "win32"
    uptime_seconds: int
    browser: str  # "chrome" | "edge" | "safari"


class TaskClaimResponse(BaseModel):
    task_id: Optional[str] = None
    task_type: Optional[str] = None
    payload: Optional[dict] = None
    campaign_id: Optional[str] = None


class TaskResultRequest(BaseModel):
    task_id: str
    status: str  # "completed" | "failed"
    result: Optional[dict] = None
    error: Optional[str] = None
    duration_ms: int


class CookieSyncRequest(BaseModel):
    linkedin_profile_id: str
    cookie_data: str  # encrypted


class SessionStateRequest(BaseModel):
    linkedin_profile_id: str
    is_logged_in: bool
    requires_verification: bool = False
    verification_type: Optional[str] = None


@router.post("/heartbeat")
async def daemon_heartbeat(
    heartbeat: DaemonHeartbeat,
    user_id: str = Depends(get_current_user),
):
    """Receive daemon health heartbeat. Called every 30s."""
    profile = LinkedInProfile.objects.get(
        _id=heartbeat.linkedin_profile_id,
        user_id=user_id,
    )
    if not profile:
        raise HTTPException(404, "LinkedIn profile not found")

    # Update daemon tracking fields
    from openoutreach.mongodb.connection import get_mongodb_collection
    collection = get_mongodb_collection("linkedin_profiles")
    if collection is None:
        raise HTTPException(503, "Database unavailable")

    collection.update_one(
        {"_id": heartbeat.linkedin_profile_id},
        {
            "$set": {
                "daemon_last_seen": datetime.now(timezone.utc),
                "daemon_version": heartbeat.version,
                "daemon_platform": heartbeat.platform,
                "daemon_browser": heartbeat.browser,
            }
        }
    )

    return {"status": "ok", "server_time": datetime.now(timezone.utc).isoformat()}


@router.post("/tasks/claim", response_model=TaskClaimResponse)
async def claim_task(
    linkedin_profile_id: str,
    daemon_id: str,
    user_id: str = Depends(get_current_user),
):
    """Atomically claim the next available task for this profile."""
    profile = LinkedInProfile.objects.get(
        _id=linkedin_profile_id,
        user_id=user_id,
    )
    if not profile:
        raise HTTPException(404, "LinkedIn profile not found")

    # Find next task for this profile
    from openoutreach.mongodb.connection import get_mongodb_collection
    collection = get_mongodb_collection("tasks")
    if collection is None:
        raise HTTPException(503, "Database unavailable")

    now = datetime.now(timezone.utc)

    # Atomically claim the next pending task
    task_data = collection.find_one_and_update(
        {
            "status": Task.Status.PENDING,
            "scheduled_at": {"$lte": now},
            "linkedin_profile_id": linkedin_profile_id,
        },
        {
            "$set": {
                "status": Task.Status.RUNNING,
                "started_at": datetime.now(timezone.utc),
            }
        },
        sort=[("scheduled_at", 1)],
        return_document=True,
    )

    if not task_data:
        return TaskClaimResponse()

    task = Task.from_dict(task_data)

    return TaskClaimResponse(
        task_id=str(task.id),
        task_type=task.task_type,
        payload=task.payload,
        campaign_id=task.payload.get("campaign_id"),
    )


@router.post("/tasks/result")
async def report_task_result(
    request: TaskResultRequest,
    user_id: str = Depends(get_current_user),
):
    """Report task completion or failure."""
    task = Task.objects().get(_id=request.task_id)
    if not task:
        raise HTTPException(404, "Task not found")

    # Verify ownership via profile
    if "linkedin_profile_id" in task.payload:
        profile = LinkedInProfile.objects.get(
            _id=task.payload["linkedin_profile_id"],
            user_id=user_id,
        )
        if not profile:
            raise HTTPException(403, "Not authorized")

    # Update task status
    if request.status == "completed":
        task.mark_completed()
    else:
        task.mark_failed(error_message=request.error)

    # Store additional metadata in payload
    if request.result:
        task.payload["result"] = request.result
        task.save(update_fields=["payload"])

    return {"status": "ok"}


@router.post("/cookies/sync")
async def sync_cookies(
    request: CookieSyncRequest,
    user_id: str = Depends(get_current_user),
):
    """Sync browser cookies from desktop daemon to backend."""
    profile = LinkedInProfile.objects.get(
        _id=request.linkedin_profile_id,
        user_id=user_id,
    )
    if not profile:
        raise HTTPException(404, "LinkedIn profile not found")

    # Update cookies
    from openoutreach.mongodb.connection import get_mongodb_collection
    collection = get_mongodb_collection("linkedin_profiles")
    if collection is None:
        raise HTTPException(503, "Database unavailable")

    collection.update_one(
        {"_id": request.linkedin_profile_id},
        {
            "$set": {
                "cookie_data_encrypted": request.cookie_data,
                "cookies_updated_at": datetime.now(timezone.utc),
            }
        }
    )

    return {"status": "ok"}


@router.post("/session/state")
async def report_session_state(
    request: SessionStateRequest,
    user_id: str = Depends(get_current_user),
):
    """Report session state (login status, verification needed)."""
    profile = LinkedInProfile.objects.get(
        _id=request.linkedin_profile_id,
        user_id=user_id,
    )
    if not profile:
        raise HTTPException(404, "LinkedIn profile not found")

    # Update session state
    from openoutreach.mongodb.connection import get_mongodb_collection
    collection = get_mongodb_collection("linkedin_profiles")
    if collection is None:
        raise HTTPException(503, "Database unavailable")

    collection.update_one(
        {"_id": request.linkedin_profile_id},
        {
            "$set": {
                "is_logged_in": request.is_logged_in,
                "requires_verification": request.requires_verification,
                "verification_type": request.verification_type,
                "session_updated_at": datetime.now(timezone.utc),
            }
        }
    )

    return {"status": "ok"}


@router.get("/config")
async def get_daemon_config(
    linkedin_profile_id: str,
    user_id: str = Depends(get_current_user),
):
    """Get daemon configuration (rate limits, active hours, etc)."""
    profile = LinkedInProfile.objects.get(
        _id=linkedin_profile_id,
        user_id=user_id,
    )
    if not profile:
        raise HTTPException(404, "LinkedIn profile not found")

    config = SiteConfig.load()

    # Parse active days string to list
    active_days = [int(d.strip()) for d in config.active_days.split(",") if d.strip()]

    return {
        "rate_limits": {
            "velocity": config.velocity,
            "daily_connect_limit": profile.connect_daily_limit,
            "daily_message_limit": profile.follow_up_daily_limit,
            "cooldown_minutes": 5,  # Default cooldown
        },
        "active_hours": {
            "enabled": config.enable_active_hours,
            "start_hour": config.active_start_hour,
            "end_hour": config.active_end_hour,
            "timezone": config.active_timezone,
            "days": active_days,
        },
        "poll_interval_seconds": 30,
        "heartbeat_interval_seconds": 30,
    }


@router.get("/credentials")
async def get_credentials(
    linkedin_profile_id: str,
    user_id: str = Depends(get_current_user),
):
    """Get LinkedIn credentials for daemon login."""
    profile = LinkedInProfile.objects.get(
        _id=linkedin_profile_id,
        user_id=user_id,
    )
    if not profile:
        raise HTTPException(404, "LinkedIn profile not found")

    # Return credentials
    return {
        "email": profile.linkedin_username,
        "password": profile.linkedin_password,
        "cookie_data": profile.cookie_data_encrypted,
    }
