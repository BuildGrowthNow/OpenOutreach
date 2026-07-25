"""
Settings Router - FastAPI implementation for SiteConfig management

Provides endpoints for managing per-user site configuration including
LLM settings, rate limits, active hours, and AI behavior rules.
"""

import logging
from datetime import datetime, timezone as tz, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from openoutreach.api_v2.dependencies_v2 import get_current_user
from openoutreach.api_v2.schemas.settings import SiteConfigResponse, SiteConfigUpdate
from openoutreach.mongodb.models import SiteConfig
from openoutreach.mongodb.connection import get_mongodb_collection

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Settings"])


def _get_linkedin_profile_info(user_id: str) -> tuple[str, str]:
    """Return (username, first_campaign_name) for the user's first active LinkedIn profile."""
    username = ""
    campaign_name = ""
    try:
        from openoutreach.linkedin.models import LinkedInProfile
        from openoutreach.mongodb.models import Campaign

        profiles = LinkedInProfile.find_by_user_id(user_id)
        profile = next((p for p in profiles if p.active), None)

        if profile:
            raw = profile.linkedin_username or ""
            # linkedin_username may hold the login email before first login — show it as-is
            # but strip an email so the UI doesn't show "fern2gue@gmail.com" as the handle
            if "@" in raw and "." in raw.split("@")[-1]:
                username = ""  # not yet resolved to a real handle
            else:
                username = raw

            if profile.campaign_id:
                try:
                    campaigns = Campaign.objects.filter(_id=profile.campaign_id)
                    if campaigns:
                        campaign_name = campaigns[0].name
                except Exception:
                    pass

        if not campaign_name:
            # fallback: first active campaign for the user
            try:
                campaigns = Campaign.objects.filter(user_id=user_id, active=True)
                if campaigns:
                    campaign_name = campaigns[0].name
            except Exception:
                pass
    except Exception:
        pass
    return username, campaign_name


@router.get("")
async def get_settings(
    user_id: str = Depends(get_current_user),
):
    """
    Get site configuration for the current user.

    Returns all SiteConfig fields including LLM settings, rate limits,
    active hours configuration, and AI behavior rules.
    """
    config = SiteConfig.load(user_id=user_id)

    # Map active_days list to comma-separated string if needed
    active_days_str = config.active_days
    if isinstance(active_days_str, list):
        active_days_str = ",".join(map(str, active_days_str))

    li_username, li_campaign = _get_linkedin_profile_info(user_id)

    return {
        "llm": {
            "provider": config.llm_provider or "",
            "apiKey": config.llm_api_key or "",
            "model": config.ai_model or "",
            "apiBase": config.llm_api_base or "",
            "writingStyle": getattr(config, "ai_writing_style", "") or "",
            "sayRules": getattr(config, "ai_say_rules", "") or "",
            "avoidRules": getattr(config, "ai_avoid_rules", "") or "",
        },
        "rateLimits": {
            "dailyConnectionLimit": config.daily_connection_limit,
            "dailyFollowUpLimit": config.daily_follow_up_limit,
            "velocity": config.velocity,
            "cooldownMinutes": getattr(config, "cooldown_minutes", 0),
            "enableSmartRateLimiting": getattr(config, "enable_smart_rate_limiting", False),
            "aggressivenessPreset": getattr(config, "aggressiveness_preset", "average") or "average",
        },
        "activeHours": {
            "enableActiveHours": getattr(config, "enable_active_hours", False),
            "activeStartHour": getattr(config, "active_start_hour", 9),
            "activeEndHour": getattr(config, "active_end_hour", 18),
            "activeTimezone": getattr(config, "active_timezone", "UTC") or "UTC",
            "activeDays": active_days_str or "1,2,3,4,5",
        },
        "linkedinProfile": {
            "username": li_username,
            "campaign": li_campaign,
        },
        "finder": {
            "apiKey": config.finder_api_key or "",
            "bettercontactApiKey": config.bettercontact_api_key or "",
        },
    }


@router.get("/rate-limits")
async def get_rate_limits(
    user_id: str = Depends(get_current_user),
):
    """
    Get rate limit configuration for the current user.

    Returns the camelCase shape expected by the frontend Settings["rateLimits"] type:
    dailyConnectionLimit, dailyFollowUpLimit, velocity, enableSmartRateLimiting, aggressivenessPreset.
    """
    config = SiteConfig.load(user_id=user_id)
    return {
        "dailyConnectionLimit": config.daily_connection_limit,
        "dailyFollowUpLimit": config.daily_follow_up_limit,
        "velocity": config.velocity,
        "enableSmartRateLimiting": getattr(config, "enable_smart_rate_limiting", False),
        "aggressivenessPreset": getattr(config, "aggressiveness_preset", "average") or "average",
    }


@router.patch("")
async def update_settings(
    updates: SiteConfigUpdate,
    user_id: str = Depends(get_current_user),
):
    """
    Update site configuration for the current user.

    Only provided fields will be updated. All fields are optional.
    """
    config = SiteConfig.load(user_id=user_id)

    # Update only provided fields
    update_data = updates.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if hasattr(config, field):
            setattr(config, field, value)

    # Save updates
    config.save()

    # Return updated config
    active_days_str = config.active_days
    if isinstance(active_days_str, list):
        active_days_str = ",".join(map(str, active_days_str))

    return {
        "success": True,
        "message": "Settings updated successfully",
        "config": SiteConfigResponse(
            id=config._id,
            llm_provider=config.llm_provider or "",
            llm_api_key=config.llm_api_key or "",
            ai_model=config.ai_model or "",
            llm_api_base=config.llm_api_base or "",
            ai_writing_style=getattr(config, "ai_writing_style", "") or "",
            ai_say_rules=getattr(config, "ai_say_rules", "") or "",
            ai_avoid_rules=getattr(config, "ai_avoid_rules", "") or "",
            finder_api_key=config.finder_api_key or "",
            linkedin_username=config.linkedin_username or "",
            linkedin_campaign=config.linkedin_campaign or "",
            enable_smart_rate_limiting=getattr(config, "enable_smart_rate_limiting", False),
            aggressiveness_preset=getattr(config, "aggressiveness_preset", "average") or "average",
            daily_connection_limit=config.daily_connection_limit,
            daily_follow_up_limit=config.daily_follow_up_limit,
            velocity=config.velocity,
            cooldown_minutes=getattr(config, "cooldown_minutes", 0),
            enable_active_hours=getattr(config, "enable_active_hours", False),
            active_start_hour=getattr(config, "active_start_hour", 9),
            active_end_hour=getattr(config, "active_end_hour", 18),
            active_timezone=getattr(config, "active_timezone", "UTC") or "UTC",
            active_days=active_days_str or "1,2,3,4,5",
            bettercontact_api_key=config.bettercontact_api_key or "",
            contacts_api_token=config.contacts_api_token or "",
            contacts_api_url=config.contacts_api_url or "",
        )
    }


@router.get("/daily-usage")
async def get_daily_usage(
    user_id: str = Depends(get_current_user),
    date: Optional[str] = Query(default=None, description="Date in YYYY-MM-DD format (default: today)"),
):
    """
    Get daily action usage counts for the current user.

    Returns connection requests and follow-up messages sent today,
    along with configured daily limits and percentage used.
    """
    # Parse date
    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=tz.utc)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    else:
        target_date = datetime.now(tz.utc)

    # Calculate day boundaries
    day_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    # Get user's LinkedIn profiles
    profiles_collection = get_mongodb_collection("linkedin_profiles")
    if profiles_collection is None:
        raise HTTPException(status_code=500, detail="Database not available")

    # Get all active profiles for this user
    profile_ids = [
        doc["_id"]
        for doc in profiles_collection.find(
            {"user_id": user_id, "is_active": True},
            {"_id": 1}
        )
    ]

    # Count actions across all user's profiles
    collection = get_mongodb_collection("action_logs")
    if collection is None:
        raise HTTPException(status_code=500, detail="Database not available")

    connect_count = collection.count_documents({
        "linkedin_profile_id": {"$in": profile_ids},
        "action_type": "connect",
        "status": {"$nin": ["failed", "error"]},
        "created_at": {"$gte": day_start, "$lt": day_end}
    })

    follow_up_count = collection.count_documents({
        "linkedin_profile_id": {"$in": profile_ids},
        "action_type": "follow_up",
        "status": {"$nin": ["failed", "error"]},
        "created_at": {"$gte": day_start, "$lt": day_end}
    })

    # Get user's configured limits
    config = SiteConfig.load(user_id=user_id)
    connect_limit = config.daily_connection_limit
    follow_up_limit = config.daily_follow_up_limit

    connect_remaining = max(0, connect_limit - connect_count)
    total_remaining = connect_remaining + max(0, follow_up_limit - follow_up_count)

    # Determine rate limit status
    connect_pct = (connect_count / connect_limit * 100) if connect_limit > 0 else 0
    if connect_pct >= 100:
        rate_limit_status = "exceeded"
    elif connect_pct >= 80:
        rate_limit_status = "warning"
    elif connect_pct >= 60:
        rate_limit_status = "caution"
    else:
        rate_limit_status = "normal"

    return {
        "date": target_date.strftime("%Y-%m-%d"),
        "daily_connections_sent": connect_count,
        "daily_messages_sent": follow_up_count,
        "daily_limit": connect_limit,
        "effective_limit": connect_limit,
        "remaining": total_remaining,
        "rate_limit_status": rate_limit_status,
        "warning_message": None,
        "last_reset": target_date.strftime("%Y-%m-%dT00:00:00Z"),
        "reset_frequency": "daily",
        "linkedin_profiles": [],
        # Legacy nested fields kept for any backend consumers
        "counts": {
            "connect": connect_count,
            "follow_up": follow_up_count,
        },
        "limits": {
            "connect": connect_limit,
            "follow_up": follow_up_limit,
        },
    }
