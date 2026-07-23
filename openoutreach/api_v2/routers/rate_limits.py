"""Rate Limiting API endpoints - MongoDB + FastAPI."""

from datetime import datetime, timezone as tz, timedelta
from typing import List, Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from openoutreach.api_v2.dependencies_v2 import get_current_user
from openoutreach.linkedin.models import (
    SmartRateLimitContext,
    RateLimitWarning,
)
from openoutreach.linkedin.models import LinkedInProfile
from openoutreach.mongodb.connection import get_mongodb_collection

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rate-limits", tags=["Rate Limiting"])


class RateLimitContextResponse(BaseModel):
    """Response model for rate limit context."""
    id: str
    linkedin_profile_id: str
    time_of_day_multiplier: float
    day_of_week_multiplier: float
    detectability_score: int
    detectability_level: str
    last_action_type: Optional[str] = None
    last_action_at: Optional[datetime] = None
    consecutive_actions: int
    effective_limits: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class RateLimitWarningResponse(BaseModel):
    """Response model for rate limit warning."""
    id: str
    linkedin_profile_id: str
    action_type: str
    limit_type: str
    limit_exceeded: int
    actual_count: int
    warning_level: str
    at_time: datetime
    resolved: bool


class UpdateDetectabilityRequest(BaseModel):
    """Request to update detectability score."""
    score_delta: int = Field(..., ge=-100, le=100, description="Score change (-100 to +100)")


@router.get("/profiles/{profile_id}", response_model=RateLimitContextResponse)
async def get_rate_limit_context(
    profile_id: str,
    user_id: str = Depends(get_current_user),
):
    """
    Get rate limit context for a LinkedIn profile.

    Returns current limits, detectability score, and effective limits
    for different action types.
    """
    # Verify profile ownership
    profile = LinkedInProfile.get(profile_id)
    if not profile or profile.user_id != user_id:
        raise HTTPException(status_code=404, detail="LinkedIn profile not found")

    # Get or create context
    context = SmartRateLimitContext.get_or_create(profile_id)

    # Calculate effective limits for each action type
    effective_limits = {
        "connect": context.get_effective_limit("connect"),
        "follow_up": context.get_effective_limit("follow_up"),
        "message": context.get_effective_limit("message"),
        "view_profile": context.get_effective_limit("view_profile"),
    }

    # Get detectability level
    detectability_level = context.get_detectability_level().value

    return RateLimitContextResponse(
        id=context._id,
        linkedin_profile_id=context.linkedin_profile_id,
        time_of_day_multiplier=context.time_of_day_limit_multiplier,
        day_of_week_multiplier=context.day_of_week_limit_multiplier,
        detectability_score=context.detectability_score,
        detectability_level=detectability_level,
        last_action_type=context.last_action_type,
        last_action_at=context.last_action_at,
        consecutive_actions=context.consecutive_actions,
        effective_limits=effective_limits,
        created_at=context.created_at,
        updated_at=context.updated_at,
    )


@router.post("/profiles/{profile_id}/detectability")
async def update_detectability(
    profile_id: str,
    request: UpdateDetectabilityRequest,
    user_id: str = Depends(get_current_user),
):
    """
    Manually adjust detectability score for a profile.

    Use this to increase suspicion after detecting captchas or rate limits,
    or decrease after successful periods.
    """
    # Verify profile ownership
    profile = LinkedInProfile.get(profile_id)
    if not profile or profile.user_id != user_id:
        raise HTTPException(status_code=404, detail="LinkedIn profile not found")

    # Get context
    context = SmartRateLimitContext.get_by_profile(profile_id)
    if not context:
        raise HTTPException(status_code=404, detail="Rate limit context not found")

    # Update detectability
    context.update_detectability(request.score_delta)

    return {
        "success": True,
        "new_score": context.detectability_score,
        "detectability_level": context.get_detectability_level().value,
    }


@router.get("/profiles/{profile_id}/warnings", response_model=List[RateLimitWarningResponse])
async def get_rate_limit_warnings(
    profile_id: str,
    user_id: str = Depends(get_current_user),
    limit: int = Query(default=10, ge=1, le=100),
    unresolved_only: bool = Query(default=False),
):
    """
    Get rate limit warnings for a LinkedIn profile.

    Shows recent violations and their severity.
    """
    # Verify profile ownership
    profile = LinkedInProfile.get(profile_id)
    if not profile or profile.user_id != user_id:
        raise HTTPException(status_code=404, detail="LinkedIn profile not found")

    # Get warnings
    warnings = RateLimitWarning.get_recent(profile_id, limit=limit)

    # Filter if requested
    if unresolved_only:
        warnings = [w for w in warnings if not w.resolved]

    return [
        RateLimitWarningResponse(
            id=w._id,
            linkedin_profile_id=w.linkedin_profile_id,
            action_type=w.action_type,
            limit_type=w.limit_type,
            limit_exceeded=w.limit_exceeded,
            actual_count=w.actual_count,
            warning_level=w.warning_level,
            at_time=w.at_time,
            resolved=w.resolved,
        )
        for w in warnings
    ]


@router.post("/profiles/{profile_id}/warnings/{warning_id}/resolve")
async def resolve_warning(
    profile_id: str,
    warning_id: str,
    user_id: str = Depends(get_current_user),
):
    """Mark a rate limit warning as resolved."""
    # Verify profile ownership
    profile = LinkedInProfile.get(profile_id)
    if not profile or profile.user_id != user_id:
        raise HTTPException(status_code=404, detail="LinkedIn profile not found")

    # Get warning
    collection = get_mongodb_collection("rate_limit_warnings")
    if collection is None:
        raise HTTPException(status_code=500, detail="Database not available")

    warning_data = collection.find_one({"_id": warning_id, "linkedin_profile_id": profile_id})
    if not warning_data:
        raise HTTPException(status_code=404, detail="Warning not found")

    # Update
    collection.update_one(
        {"_id": warning_id},
        {"$set": {"resolved": True}}
    )

    return {"success": True, "message": "Warning resolved"}


@router.get("/profiles/{profile_id}/daily-counts")
async def get_daily_action_counts(
    profile_id: str,
    user_id: str = Depends(get_current_user),
    date: Optional[str] = Query(default=None, description="Date in YYYY-MM-DD format (default: today)"),
):
    """
    Get action counts for a specific day.

    Shows how many connects, messages, etc. were performed.
    """
    # Verify profile ownership
    profile = LinkedInProfile.get(profile_id)
    if not profile or profile.user_id != user_id:
        raise HTTPException(status_code=404, detail="LinkedIn profile not found")

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

    # Count actions
    collection = get_mongodb_collection("action_logs")
    if collection is None:
        raise HTTPException(status_code=500, detail="Database not available")

    counts = {}
    for action_type in ["connect", "follow_up", "message", "view_profile"]:
        count = collection.count_documents({
            "linkedin_profile_id": profile_id,
            "action_type": action_type,
            "created_at": {"$gte": day_start, "$lt": day_end}
        })
        counts[action_type] = count

    # Get effective limits
    context = SmartRateLimitContext.get_by_profile(profile_id)
    effective_limits = {}
    if context:
        for action_type in ["connect", "follow_up", "message", "view_profile"]:
            effective_limits[action_type] = context.get_effective_limit(action_type)

    return {
        "date": target_date.strftime("%Y-%m-%d"),
        "counts": counts,
        "effective_limits": effective_limits,
        "percentage_used": {
            action_type: round((counts[action_type] / effective_limits.get(action_type, 1)) * 100, 1)
            for action_type in counts.keys()
            if effective_limits.get(action_type, 0) > 0
        }
    }
