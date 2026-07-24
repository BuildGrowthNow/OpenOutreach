"""
Remote daemon communication endpoints.

Desktop app daemons use these to:
1. Claim and execute tasks
2. Report task results
3. Sync cookies/session state
4. Report health/status
5. Check subscription status (Phase 11)
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import logging

from openoutreach.api_v2.dependencies_v2 import get_current_user
from openoutreach.linkedin.models import LinkedInProfile
from openoutreach.core.models import Task, SiteConfig
from openoutreach.mongodb.models_user import User

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

    now = datetime.now(timezone.utc)
    collection.update_one(
        {"_id": heartbeat.linkedin_profile_id},
        {
            "$set": {
                "daemon_last_seen": now,
                "last_heartbeat": now,
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
    from openoutreach.billing.enforcement import PlanEnforcer

    user = User.get(user_id)
    if not user:
        raise HTTPException(401, "User not found")

    can_run, block_reason = PlanEnforcer.can_run_tasks(user)
    if not can_run:
        raise HTTPException(402, block_reason or "Subscription inactive")

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
    """Sync browser cookies from desktop daemon to backend.

    Expects cookie_data as a JSON string (not encrypted). Server handles encryption.
    """
    profile = LinkedInProfile.objects.get(
        _id=request.linkedin_profile_id,
        user_id=user_id,
    )
    if not profile:
        raise HTTPException(404, "LinkedIn profile not found")

    # Parse and encrypt the cookie data
    import json
    try:
        cookie_dict = json.loads(request.cookie_data)
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(400, "Invalid cookie_data format")

    # Use the model's cookie_data setter to handle encryption
    profile.cookie_data = cookie_dict
    profile.save()

    # Update metadata
    from openoutreach.mongodb.connection import get_mongodb_collection
    collection = get_mongodb_collection("linkedin_profiles")
    if collection is None:
        raise HTTPException(503, "Database unavailable")

    collection.update_one(
        {"_id": request.linkedin_profile_id},
        {
            "$set": {
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
    """Get daemon configuration (rate limits, active hours, etc).

    Load real user settings via SiteConfig.load() not global singleton.
    """
    profile = LinkedInProfile.objects.get(
        _id=linkedin_profile_id,
        user_id=user_id,
    )
    if not profile:
        raise HTTPException(404, "LinkedIn profile not found")

    config = SiteConfig.load(user_id=user_id)

    # Parse active days string to list
    active_days = [int(d.strip()) for d in config.active_days.split(",") if d.strip()]

    from openoutreach.config import settings as app_settings

    return {
        "rate_limits": {
            "velocity": config.velocity,
            "daily_connect_limit": profile.connect_daily_limit,
            "daily_message_limit": profile.follow_up_daily_limit,
            "cooldown_minutes": 5,
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
        "mongodb_uri": app_settings.MONGODB_URI or None,
        "mongodb_name": app_settings.MONGODB_NAME,
    }


@router.post("/reconcile")
async def reconcile_tasks(
    linkedin_profile_id: str,
    user_id: str = Depends(get_current_user),
):
    """Run task scheduler for all active campaigns owned by this user.

    Creates pending tasks (connect, check_pending, follow_up) if the queue
    is empty for a campaign. Called by the desktop daemon on startup and
    periodically to ensure tasks exist for claiming.
    """
    from openoutreach.mongodb.connection import get_mongodb_collection
    from openoutreach.core.scheduler import (
        plan_connect_window,
        plan_follow_up_window,
        plan_check_pending_window,
    )

    profile = LinkedInProfile.objects.get(
        _id=linkedin_profile_id,
        user_id=user_id,
    )
    if not profile:
        raise HTTPException(404, "LinkedIn profile not found")

    campaigns_collection = get_mongodb_collection("campaigns")
    if campaigns_collection is None:
        raise HTTPException(503, "Database unavailable")

    campaigns_data = list(campaigns_collection.find({
        "user_id": user_id,
        "linkedin_profile_id": linkedin_profile_id,
        "status": "active",
        "is_paused": False,
    }))

    from openoutreach.mongodb.models import Campaign

    tasks_created = 0
    for doc in campaigns_data:
        campaign = Campaign.from_dict(doc)

        class _FakeSession:
            def __init__(self, uid, prof):
                self.user_id = uid
                self.linkedin_profile = prof
                self.linkedin_profile_id = prof._id

        session = _FakeSession(user_id, profile)
        tasks_created += plan_connect_window(session, campaign)
        tasks_created += plan_follow_up_window(session, campaign)
        tasks_created += plan_check_pending_window(session, campaign)

    logger.info("Reconcile for profile %s: %d tasks created across %d campaigns",
                linkedin_profile_id, tasks_created, len(campaigns_data))

    return {"tasks_created": tasks_created, "campaigns": len(campaigns_data)}


@router.get("/credentials")
async def get_credentials(
    linkedin_profile_id: str,
    user_id: str = Depends(get_current_user),
):
    """Get LinkedIn credentials for daemon login.

    Returns decrypted cookie_data as JSON string for remote daemon consumption.
    """
    profile = LinkedInProfile.objects.get(
        _id=linkedin_profile_id,
        user_id=user_id,
    )
    if not profile:
        raise HTTPException(404, "LinkedIn profile not found")

    # Return credentials with DECRYPTED cookie_data
    # profile.cookie_data property handles decryption automatically
    import json
    cookie_data_json = None
    if profile.cookie_data:
        cookie_data_json = json.dumps(profile.cookie_data)

    return {
        "email": profile.linkedin_username,
        "password": profile.linkedin_password,
        "cookie_data": cookie_data_json,  # JSON string, not encrypted
    }


@router.get("/subscription/status")
async def get_subscription_status(
    user_id: str = Depends(get_current_user),
):
    """Get user subscription status for daemon operation.

    Returns subscription info to determine if daemon should run.
    Called on startup and periodically during operation.
    """
    user = User.get(user_id)
    if not user:
        raise HTTPException(404, "User not found")

    is_active = False
    block_reason = None

    if user.status == "blocked":
        is_active = False
        block_reason = user.admin_notes or "Account blocked by administrator"
    elif user.subscription_status in ("active", "trialing"):
        is_active = True
    elif user.subscription_status == "expired":
        is_active = False
    elif user.subscription_status == "canceled":
        is_active = False
    elif user.subscription_status == "past_due":
        is_active = False
    else:
        is_active = False

    return {
        "is_active": is_active,
        "plan": user.plan or "starter",
        "subscription_status": user.subscription_status or "none",
        "user_status": user.status or "active",
        "trial_ends_at": (
            user.trial_ends_at.isoformat()
            if user.trial_ends_at
            else None
        ),
        "current_period_end": (
            user.current_period_end.isoformat()
            if user.current_period_end
            else None
        ),
        "block_reason": block_reason,
    }


@router.get("/profile/{linkedin_profile_id}")
async def get_profile_details(
    linkedin_profile_id: str,
    user_id: str = Depends(get_current_user),
):
    """Get LinkedIn profile details needed for daemon execution.

    Daemon queries this when executing tasks to avoid local Mongo requirement.
    """
    profile = LinkedInProfile.objects.get(
        _id=linkedin_profile_id,
        user_id=user_id,
    )
    if not profile:
        raise HTTPException(404, "LinkedIn profile not found")

    return {
        "id": str(profile._id),
        "user_id": profile.user_id,
        "linkedin_username": profile.linkedin_username or "",
        "linkedin_password": profile.linkedin_password or "",
        "cookie_data": profile.cookie_data or {},
        "proxy_server": profile.proxy_server or None,
        "proxy_username": profile.proxy_username or None,
        "proxy_password": profile.proxy_password or None,
        "connect_daily_limit": profile.connect_daily_limit or 50,
        "follow_up_daily_limit": profile.follow_up_daily_limit or 30,
    }


@router.get("/campaign/{campaign_id}")
async def get_campaign_details(
    campaign_id: str,
    user_id: str = Depends(get_current_user),
):
    """Get campaign details needed for daemon execution.

    Daemon queries this when executing tasks to avoid local Mongo requirement.
    """
    from openoutreach.mongodb.models import Campaign

    campaign = Campaign.objects.get(_id=campaign_id, user_id=user_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    return {
        "id": str(campaign._id),
        "user_id": campaign.user_id,
        "name": campaign.name or "",
        "product_pitch": campaign.product_pitch or "",
        "follow_up_strategy": campaign.follow_up_strategy or "",
        "icp_titles": campaign.icp_titles or [],
        "linkedin_profile_id": str(campaign.linkedin_profile_id) if campaign.linkedin_profile_id else None,
        "is_paused": campaign.is_paused or False,
        "status": campaign.status or "draft",
    }
