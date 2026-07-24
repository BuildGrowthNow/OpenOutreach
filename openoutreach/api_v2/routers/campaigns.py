"""
Campaigns Router - FastAPI implementation with multi-tenant support

Provides endpoints for managing campaigns with proper user ownership
and team access control.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel

from openoutreach.api_v2.dependencies_v2 import get_current_user, get_campaign_with_access
from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.mongodb import models
from openoutreach.crm.models.deal import DealState

logger = logging.getLogger(__name__)
router = APIRouter()


# Request/Response schemas
class CampaignCreate(BaseModel):
    """Request schema for campaign creation."""
    name: str
    product_pitch: str
    campaign_objective: str
    linkedin_profile_id: str  # Required: which profile executes
    booking_link: Optional[str] = ""
    velocity: int = 20
    team_member_ids: Optional[List[str]] = None  # Optional: share with team
    icp_titles: Optional[List[str]] = None  # ICP job titles
    follow_up_strategy: Optional[str] = None  # Follow-up strategy text

    class Config:
        json_schema_extra = {
            "example": {
                "name": "SaaS Founders Outreach",
                "product_pitch": "We help SaaS founders automate their lead generation",
                "campaign_objective": "Book 10 discovery calls per week",
                "linkedin_profile_id": "profile_123",
                "booking_link": "https://calendly.com/user/discovery",
                "velocity": 20,
                "team_member_ids": ["user_456"],
                "icp_titles": ["CEO", "CTO", "VP of Engineering"],
                "follow_up_strategy": "Send personalized follow-up after 3 days"
            }
        }


class CampaignUpdate(BaseModel):
    """Request schema for campaign update."""
    name: Optional[str] = None
    product_pitch: Optional[str] = None
    campaign_objective: Optional[str] = None
    linkedin_profile_id: Optional[str] = None
    booking_link: Optional[str] = None
    velocity: Optional[int] = None
    is_paused: Optional[bool] = None
    status: Optional[str] = None  # "active", "paused", or "draft"
    team_member_ids: Optional[List[str]] = None
    icp_titles: Optional[List[str]] = None
    follow_up_strategy: Optional[str] = None


class CampaignStats(BaseModel):
    totalLeads: int = 0
    connected: int = 0
    completed: int = 0
    messagesSent: int = 0
    messagesReplied: int = 0


class CampaignResponse(BaseModel):
    """Response schema for campaign."""
    id: str
    name: str
    product_pitch: str
    campaign_objective: str
    linkedin_profile_id: Optional[str]
    booking_link: str
    velocity: int
    is_paused: bool
    status: str  # "active", "paused", or "draft"
    user_id: str
    team_member_ids: List[str]
    icp_titles: List[str]
    follow_up_strategy: Optional[str]
    created_at: str
    stats: CampaignStats = CampaignStats()


class PaginationInfo(BaseModel):
    total: int
    page: int
    limit: int
    pages: int


class CampaignListResponse(BaseModel):
    """Response schema for campaign list — matches frontend { data, pagination } shape."""
    data: List[CampaignResponse]
    pagination: PaginationInfo


def _on_campaign_activated(campaign: models.Campaign, user_id: str) -> None:
    """Schedule tasks and log a 'campaign_started' event when a campaign goes active."""
    from openoutreach.linkedin.models import LinkedInProfile
    from openoutreach.mongodb.models_extended import ActionLog

    profile = LinkedInProfile.objects.get(_id=campaign.linkedin_profile_id)
    if not profile:
        return

    # Log the campaign_started event
    ActionLog(
        linkedin_profile_id=campaign.linkedin_profile_id,
        campaign_id=campaign._id,
        action_type="campaign_started",
        status="completed",
        user_id=user_id,
        details={"campaign_name": campaign.name},
    ).save()

    # Schedule tasks (reconcile)
    try:
        from openoutreach.core.scheduler import (
            plan_connect_window,
            plan_follow_up_window,
            plan_check_pending_window,
        )

        class _Session:
            def __init__(self, uid: str, prof: LinkedInProfile):
                self.user_id = uid
                self.linkedin_profile = prof
                self.linkedin_profile_id = prof._id

        session = _Session(user_id, profile)
        created = plan_connect_window(session, campaign)
        created += plan_follow_up_window(session, campaign)
        created += plan_check_pending_window(session, campaign)
        logger.info("Campaign %s activated: %d tasks scheduled", campaign._id, created)
    except Exception as e:
        logger.warning("Failed to schedule tasks on activation: %s", e)


# Endpoints

@router.get("", response_model=CampaignListResponse)
async def list_campaigns(
    skip: int = 0,
    limit: int = 100,
    user_id: str = Depends(get_current_user),
):
    """
    List campaigns for the current user.

    Multi-tenant: returns campaigns where user is owner OR team member.
    Supports pagination via skip/limit query params.
    """
    collection = get_mongodb_collection("campaigns")
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Campaigns database unavailable"
        )

    try:
        # Query campaigns where user is owner OR in team_member_ids
        query = {
            "$or": [
                {"user_id": user_id},
                {"team_member_ids": user_id}
            ]
        }
        cursor = collection.find(query).skip(skip).limit(limit)
        docs = list(cursor)

        # Batch-fetch deal stats for all campaigns in one aggregation
        deals_collection = get_mongodb_collection("deals")
        campaign_stats: Dict[str, Dict] = {}
        if deals_collection is not None and docs:
            campaign_ids = [str(doc["_id"]) for doc in docs]
            pipeline = [
                {"$match": {"campaign_id": {"$in": campaign_ids}}},
                {"$group": {
                    "_id": "$campaign_id",
                    "totalLeads": {"$sum": 1},
                    "connected": {"$sum": {"$cond": [{"$eq": ["$state", "Connected"]}, 1, 0]}},
                    "completed": {"$sum": {"$cond": [{"$eq": ["$state", "Completed"]}, 1, 0]}},
                }},
            ]
            for row in deals_collection.aggregate(pipeline):
                campaign_stats[str(row["_id"])] = {
                    "totalLeads": row.get("totalLeads", 0),
                    "connected": row.get("connected", 0),
                    "completed": row.get("completed", 0),
                }

        campaigns = []
        for doc in docs:
            cid = str(doc.get("_id"))
            s = campaign_stats.get(cid, {})
            campaigns.append(CampaignResponse(
                id=cid,
                name=doc.get("name", ""),
                product_pitch=doc.get("product_pitch", ""),
                campaign_objective=doc.get("campaign_objective", ""),
                linkedin_profile_id=doc.get("linkedin_profile_id"),
                booking_link=doc.get("booking_link", ""),
                velocity=doc.get("velocity", 20),
                is_paused=doc.get("is_paused", False),
                status=doc.get("status", "active"),
                user_id=doc.get("user_id", ""),
                team_member_ids=doc.get("team_member_ids", []),
                icp_titles=doc.get("icp_titles", []),
                follow_up_strategy=doc.get("follow_up_strategy"),
                created_at=doc.get("created_at").isoformat() if doc.get("created_at") else "",
                stats=CampaignStats(
                    totalLeads=s.get("totalLeads", 0),
                    connected=s.get("connected", 0),
                    completed=s.get("completed", 0),
                ),
            ))

        count = collection.count_documents(query)
        page = (skip // limit) + 1 if limit else 1
        pages = (count + limit - 1) // limit if limit else 1

        return CampaignListResponse(
            data=campaigns,
            pagination=PaginationInfo(total=count, page=page, limit=limit, pages=pages),
        )

    except Exception as e:
        logger.exception("Failed to list campaigns")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve campaigns: {str(e)}"
        )


@router.post("", response_model=CampaignResponse, status_code=201)
async def create_campaign(
    data: CampaignCreate,
    user_id: str = Depends(get_current_user),
):
    """
    Create a new campaign.

    Multi-tenant: user must own the specified LinkedIn profile.
    Validates profile ownership and team member existence.
    Enforces plan limits before creation.
    """
    from openoutreach.mongodb.models_user import User
    from openoutreach.billing.enforcement import PlanEnforcer

    profiles_collection = get_mongodb_collection("linkedin_profiles")
    campaigns_collection = get_mongodb_collection("campaigns")

    if campaigns_collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Campaigns database unavailable"
        )

    try:
        # Enforce plan limits before creation
        user = User.get(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )

        can_create, error_msg = PlanEnforcer.can_create_campaign(user)
        if not can_create:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_msg or "Cannot create campaign - plan limit reached"
            )

        # Verify user owns the LinkedIn profile
        if profiles_collection is not None:
            profile_doc = profiles_collection.find_one({
                "_id": data.linkedin_profile_id,
                "user_id": user_id
            })
            if not profile_doc:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="LinkedIn profile not found or access denied"
                )
        else:
            logger.warning("LinkedIn profiles collection unavailable, skipping ownership check")

        # Verify team members exist
        team_ids = data.team_member_ids or []
        if team_ids:
            users_collection = get_mongodb_collection("users")
            if users_collection is not None:
                for tid in team_ids:
                    user_doc = users_collection.find_one({"_id": tid})
                    if not user_doc:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Team member {tid} not found"
                        )

        # Create campaign
        campaign = models.Campaign(
            name=data.name,
            product_pitch=data.product_pitch,
            campaign_objective=data.campaign_objective,
            linkedin_profile_id=data.linkedin_profile_id,
            booking_link=data.booking_link or "",
            velocity=data.velocity,
            user_id=user_id,
            team_member_ids=team_ids,
            icp_titles=data.icp_titles or [],
            follow_up_strategy=data.follow_up_strategy,
            status="draft",  # New campaigns start as draft
            is_paused=True,  # Keep is_paused in sync with draft status
        )
        campaign.save()

        logger.info(f"Created campaign {campaign._id} for user {user_id}")

        return CampaignResponse(
            id=campaign._id,
            name=campaign.name,
            product_pitch=campaign.product_pitch,
            campaign_objective=campaign.campaign_objective,
            linkedin_profile_id=campaign.linkedin_profile_id,
            booking_link=campaign.booking_link,
            velocity=campaign.velocity,
            is_paused=campaign.is_paused,
            status=campaign.status,
            user_id=campaign.user_id,
            team_member_ids=campaign.team_member_ids,
            icp_titles=campaign.icp_titles,
            follow_up_strategy=campaign.follow_up_strategy,
            created_at=campaign.created_at.isoformat() if campaign.created_at else "",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to create campaign")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create campaign: {str(e)}"
        )


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign: models.Campaign = Depends(get_campaign_with_access),
):
    """
    Get a single campaign by ID.

    Multi-tenant: verifies user has access (owner OR team member).
    """
    return CampaignResponse(
        id=campaign._id,
        name=campaign.name,
        product_pitch=campaign.product_pitch,
        campaign_objective=campaign.campaign_objective,
        linkedin_profile_id=campaign.linkedin_profile_id,
        booking_link=campaign.booking_link,
        velocity=campaign.velocity,
        is_paused=campaign.is_paused,
        status=campaign.status,
        user_id=campaign.user_id,
        team_member_ids=campaign.team_member_ids,
        icp_titles=campaign.icp_titles,
        follow_up_strategy=campaign.follow_up_strategy,
        created_at=campaign.created_at.isoformat() if campaign.created_at else "",
    )


@router.put("/{campaign_id}", response_model=CampaignResponse)
@router.patch("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: str,
    data: CampaignUpdate,
    user_id: str = Depends(get_current_user),
):
    """
    Update a campaign.

    Multi-tenant: verifies user has access (owner OR team member).
    Only campaign owner can update team_member_ids.
    """
    collection = get_mongodb_collection("campaigns")
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Campaigns database unavailable"
        )

    try:
        # Get campaign and verify access
        campaign = models.Campaign.get(campaign_id)
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )

        if not campaign.has_access(user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        # Build update
        updates = {}
        if data.name is not None:
            updates["name"] = data.name
        if data.product_pitch is not None:
            updates["product_pitch"] = data.product_pitch
        if data.campaign_objective is not None:
            updates["campaign_objective"] = data.campaign_objective
        if data.linkedin_profile_id is not None:
            # Verify user owns the new profile
            profiles_collection = get_mongodb_collection("linkedin_profiles")
            if profiles_collection is not None:
                profile_doc = profiles_collection.find_one({
                    "_id": data.linkedin_profile_id,
                    "user_id": user_id
                })
                if not profile_doc:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="LinkedIn profile not found or access denied"
                    )
            updates["linkedin_profile_id"] = data.linkedin_profile_id
        if data.booking_link is not None:
            updates["booking_link"] = data.booking_link
        if data.velocity is not None:
            updates["velocity"] = data.velocity
        if data.icp_titles is not None:
            updates["icp_titles"] = data.icp_titles
        if data.follow_up_strategy is not None:
            updates["follow_up_strategy"] = data.follow_up_strategy

        # Handle status/is_paused synchronization
        # Priority: if status is provided, use it; otherwise use is_paused
        if data.status is not None:
            # Validate status
            if data.status not in ["active", "paused", "draft"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Status must be 'active', 'paused', or 'draft'"
                )
            updates["status"] = data.status
            # Sync is_paused with status
            updates["is_paused"] = data.status in ["paused", "draft"]
        elif data.is_paused is not None:
            # If only is_paused is provided, sync status
            updates["is_paused"] = data.is_paused
            updates["status"] = "paused" if data.is_paused else "active"

        if data.team_member_ids is not None:
            # Only campaign owner can update team members
            if user_id != campaign.user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only campaign owner can update team members"
                )
            updates["team_member_ids"] = data.team_member_ids

        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )

        # Apply update
        collection.update_one(
            {"_id": campaign_id},
            {"$set": updates}
        )

        # Fetch updated campaign
        updated_campaign = models.Campaign.get(campaign_id)
        if updated_campaign is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found after update"
            )

        # When campaign becomes active, schedule tasks and log the event
        became_active = (
            updates.get("status") == "active"
            and campaign.status != "active"
        )
        if became_active and updated_campaign.linkedin_profile_id:
            _on_campaign_activated(updated_campaign, user_id)

        logger.info(f"Updated campaign {campaign_id} by user {user_id}")

        return CampaignResponse(
            id=updated_campaign._id,
            name=updated_campaign.name,
            product_pitch=updated_campaign.product_pitch,
            campaign_objective=updated_campaign.campaign_objective,
            linkedin_profile_id=updated_campaign.linkedin_profile_id,
            booking_link=updated_campaign.booking_link,
            velocity=updated_campaign.velocity,
            is_paused=updated_campaign.is_paused,
            status=updated_campaign.status,
            user_id=updated_campaign.user_id,
            team_member_ids=updated_campaign.team_member_ids,
            icp_titles=updated_campaign.icp_titles,
            follow_up_strategy=updated_campaign.follow_up_strategy,
            created_at=updated_campaign.created_at.isoformat() if updated_campaign.created_at else "",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to update campaign")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update campaign: {str(e)}"
        )


@router.delete("/{campaign_id}", status_code=204)
async def delete_campaign(
    campaign_id: str,
    user_id: str = Depends(get_current_user),
):
    """
    Delete a campaign.

    Multi-tenant: only campaign owner can delete.
    Safety: prevents deletion if campaign has deals/leads.
    """
    campaigns_collection = get_mongodb_collection("campaigns")
    deals_collection = get_mongodb_collection("deals")

    if campaigns_collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Campaigns database unavailable"
        )

    try:
        # Get campaign and verify ownership
        campaign = models.Campaign.get(campaign_id)
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )

        if user_id != campaign.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only campaign owner can delete campaigns"
            )

        # Check for associated deals
        if deals_collection is not None:
            deal_count = deals_collection.count_documents({"campaign_id": campaign_id})
            if deal_count > 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot delete campaign: {deal_count} deal(s) exist. Archive instead."
                )

        # Delete campaign
        result = campaigns_collection.delete_one({"_id": campaign_id})
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )

        logger.info(f"Deleted campaign {campaign_id} by user {user_id}")
        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to delete campaign")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete campaign: {str(e)}"
        )


@router.post("/{campaign_id}/pause", response_model=CampaignResponse)
async def pause_campaign(
    campaign_id: str,
    user_id: str = Depends(get_current_user),
):
    """
    Pause a campaign.

    Helper endpoint that sets status="paused" and is_paused=True.
    Multi-tenant: verifies user has access (owner OR team member).
    """
    collection = get_mongodb_collection("campaigns")
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Campaigns database unavailable"
        )

    try:
        # Get campaign and verify access
        campaign = models.Campaign.get(campaign_id)
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )

        if not campaign.has_access(user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        # Update to paused
        collection.update_one(
            {"_id": campaign_id},
            {"$set": {"status": "paused", "is_paused": True}}
        )

        # Cancel all pending tasks for this campaign so the daemon doesn't
        # claim them and fail with "campaign not found or inactive".
        tasks_collection = get_mongodb_collection("tasks")
        if tasks_collection is not None:
            cancelled = tasks_collection.update_many(
                {"payload.campaign_id": campaign_id, "status": "pending"},
                {"$set": {"status": "cancelled"}},
            )
            if cancelled.modified_count:
                logger.info(
                    "Cancelled %d pending tasks for paused campaign %s",
                    cancelled.modified_count,
                    campaign_id,
                )

        # Fetch updated campaign
        updated_campaign = models.Campaign.get(campaign_id)
        if updated_campaign is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found after update"
            )

        logger.info(f"Paused campaign {campaign_id} by user {user_id}")

        return CampaignResponse(
            id=updated_campaign._id,
            name=updated_campaign.name,
            product_pitch=updated_campaign.product_pitch,
            campaign_objective=updated_campaign.campaign_objective,
            linkedin_profile_id=updated_campaign.linkedin_profile_id,
            booking_link=updated_campaign.booking_link,
            velocity=updated_campaign.velocity,
            is_paused=updated_campaign.is_paused,
            status=updated_campaign.status,
            user_id=updated_campaign.user_id,
            team_member_ids=updated_campaign.team_member_ids,
            icp_titles=updated_campaign.icp_titles,
            follow_up_strategy=updated_campaign.follow_up_strategy,
            created_at=updated_campaign.created_at.isoformat() if updated_campaign.created_at else "",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to pause campaign")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to pause campaign: {str(e)}"
        )


@router.post("/{campaign_id}/resume", response_model=CampaignResponse)
async def resume_campaign(
    campaign_id: str,
    user_id: str = Depends(get_current_user),
):
    """
    Resume a paused campaign.

    Helper endpoint that sets status="active" and is_paused=False.
    Multi-tenant: verifies user has access (owner OR team member).
    Enforces plan campaign limit — resuming counts the same as creating.
    """
    from openoutreach.mongodb.models_user import User
    from openoutreach.billing.enforcement import PlanEnforcer

    collection = get_mongodb_collection("campaigns")
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Campaigns database unavailable"
        )

    try:
        # Get campaign and verify access
        campaign = models.Campaign.get(campaign_id)
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )

        if not campaign.has_access(user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        # Only check limit when campaign is currently paused/draft (would add to active count)
        if campaign.is_paused:
            user = User.get(user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found"
                )
            can_resume, error_msg = PlanEnforcer.can_create_campaign(user)
            if not can_resume:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=error_msg or "Cannot resume campaign - active campaign limit reached"
                )

        # Update to active
        collection.update_one(
            {"_id": campaign_id},
            {"$set": {"status": "active", "is_paused": False}}
        )

        # Fetch updated campaign
        updated_campaign = models.Campaign.get(campaign_id)
        if updated_campaign is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found after update"
            )

        # Schedule tasks and log event
        if updated_campaign.linkedin_profile_id:
            _on_campaign_activated(updated_campaign, user_id)

        logger.info(f"Resumed campaign {campaign_id} by user {user_id}")

        return CampaignResponse(
            id=updated_campaign._id,
            name=updated_campaign.name,
            product_pitch=updated_campaign.product_pitch,
            campaign_objective=updated_campaign.campaign_objective,
            linkedin_profile_id=updated_campaign.linkedin_profile_id,
            booking_link=updated_campaign.booking_link,
            velocity=updated_campaign.velocity,
            is_paused=updated_campaign.is_paused,
            status=updated_campaign.status,
            user_id=updated_campaign.user_id,
            team_member_ids=updated_campaign.team_member_ids,
            icp_titles=updated_campaign.icp_titles,
            follow_up_strategy=updated_campaign.follow_up_strategy,
            created_at=updated_campaign.created_at.isoformat() if updated_campaign.created_at else "",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to resume campaign")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resume campaign: {str(e)}"
        )


class LeadResponse(BaseModel):
    id: str
    public_identifier: str
    url: str
    full_name: Optional[str] = None
    headline: Optional[str] = None
    location: Optional[str] = None
    disqualified: bool = False
    created_at: Optional[str] = None


class DealResponse(BaseModel):
    id: str
    lead_id: str
    campaign_id: str
    state: str
    outcome: Optional[str] = None
    reason: Optional[str] = None
    creation_date: Optional[str] = None


@router.get("/{campaign_id}/leads", response_model=dict)
async def get_campaign_leads(
    campaign_id: str,
    user_id: str = Depends(get_current_user),
    state: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    Get leads for a specific campaign.

    Multi-tenant: verifies user has access (owner OR team member).
    """
    # Verify campaign access
    campaign = models.Campaign.get(campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )

    if not campaign.has_access(user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    collection = get_mongodb_collection("deals")
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable"
        )

    # Build query
    query = {"campaign_id": campaign_id}
    if state:
        query["state"] = state

    # Get deals
    total = collection.count_documents(query)
    deals = list(collection.find(query).skip(offset).limit(limit).sort("creation_date", -1))

    # Get unique lead IDs
    lead_ids = list(set(str(d["lead_id"]) for d in deals))

    # Fetch leads
    leads_collection = get_mongodb_collection("leads")
    if leads_collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable"
        )
    leads_data = {str(lead_doc["_id"]): lead_doc for lead_doc in leads_collection.find({"_id": {"$in": lead_ids}})}

    # Build response
    results = []
    for deal in deals:
        lead_data = leads_data.get(str(deal["lead_id"]))
        if lead_data:
            # Extract display fields from cached_profile (Voyager response shape)
            cp = lead_data.get("cached_profile") or {}
            profile_inner = cp.get("profile", cp)  # support both flat and nested shapes
            first = profile_inner.get("firstName", "") or cp.get("first_name", "")
            last = profile_inner.get("lastName", "") or cp.get("last_name", "")
            full_name = (
                lead_data.get("full_name")
                or (f"{first} {last}".strip() or None)
            )
            headline = (
                lead_data.get("headline")
                or profile_inner.get("headline")
                or cp.get("headline")
            )
            location = (
                lead_data.get("location")
                or profile_inner.get("locationName")
                or cp.get("location")
            )
            results.append({
                "lead": LeadResponse(
                    id=str(lead_data["_id"]),
                    public_identifier=lead_data.get("public_identifier", ""),
                    url=lead_data.get("linkedin_url", lead_data.get("url", "")),
                    full_name=full_name,
                    headline=headline,
                    location=location,
                    disqualified=lead_data.get("disqualified", False),
                    created_at=lead_data.get("creation_date").isoformat() if lead_data.get("creation_date") else None,
                ),
                "deal": DealResponse(
                    id=str(deal["_id"]),
                    lead_id=str(deal["lead_id"]),
                    campaign_id=str(deal["campaign_id"]),
                    state=deal.get("state", "Discovered"),
                    outcome=deal.get("outcome"),
                    reason=deal.get("reason"),
                    creation_date=deal.get("creation_date").isoformat() if deal.get("creation_date") else None,
                )
            })

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "results": results,
    }


@router.get("/{campaign_id}/status")
async def get_campaign_status(
    campaign_id: str,
    user_id: str = Depends(get_current_user),
):
    """Get lightweight campaign status for polling."""
    campaign = models.Campaign.get(campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )
    if not campaign.has_access(user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    return {"status": campaign.status, "is_paused": campaign.is_paused}


@router.get("/{campaign_id}/analytics")
async def get_campaign_analytics(
    campaign_id: str,
    user_id: str = Depends(get_current_user),
    period: str = Query("30d", pattern="^(7d|30d|90d|all)$"),
):
    """Get analytics for a specific campaign."""
    campaign = models.Campaign.get(campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )
    if not campaign.has_access(user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    deals_collection = get_mongodb_collection("deals")
    action_logs_collection = get_mongodb_collection("action_logs")
    messages_collection = get_mongodb_collection("chat_messages")

    period_days = {"7d": 7, "30d": 30, "90d": 90}.get(period, 0)
    since = datetime.utcnow() - timedelta(days=period_days) if period_days else datetime(2000, 1, 1)

    connections_sent = 0
    connections_accepted = 0
    messages_sent = 0
    messages_replied = 0
    conversions = 0
    errors = 0

    if action_logs_collection is not None:
        connections_sent = action_logs_collection.count_documents({
            "campaign_id": campaign_id,
            "action_type": "connect",
            "status": {"$nin": ["failed", "error"]},
            "created_at": {"$gte": since},
        })
        messages_sent = action_logs_collection.count_documents({
            "campaign_id": campaign_id,
            "action_type": "follow_up",
            "status": {"$nin": ["failed", "error"]},
            "created_at": {"$gte": since},
        })
        errors = action_logs_collection.count_documents({
            "campaign_id": campaign_id,
            "status": {"$in": ["failed", "error"]},
            "created_at": {"$gte": since},
        })

    if deals_collection is not None:
        connections_accepted = deals_collection.count_documents({
            "campaign_id": campaign_id,
            "state": DealState.CONNECTED.value,
        })
        conversions = deals_collection.count_documents({
            "campaign_id": campaign_id,
            "state": DealState.COMPLETED.value,
        })

    if messages_collection is not None:
        try:
            pipeline = [
                {"$match": {"is_outgoing": False, "creation_date": {"$gte": since}}},
                {"$lookup": {"from": "deals", "localField": "deal_id", "foreignField": "_id", "as": "deal"}},
                {"$unwind": "$deal"},
                {"$match": {"deal.campaign_id": campaign_id}},
                {"$group": {"_id": "$deal_id"}},
                {"$count": "total"},
            ]
            result = list(messages_collection.aggregate(pipeline))
            messages_replied = result[0]["total"] if result else 0
        except Exception:
            pass

    connection_accept_rate = round((connections_accepted / connections_sent * 100), 2) if connections_sent else 0.0
    response_rate = round((messages_replied / messages_sent * 100), 2) if messages_sent else 0.0
    conversion_rate = round((conversions / connections_sent * 100), 2) if connections_sent else 0.0

    # Pipeline counts
    pipeline_stats: Dict[str, int] = {}
    if deals_collection is not None:
        for state in DealState:
            pipeline_stats[state.value.lower()] = deals_collection.count_documents({
                "campaign_id": campaign_id,
                "state": state.value,
            })

    return {
        "campaign_id": campaign_id,
        "period": period,
        "stats": {
            "connections_sent": connections_sent,
            "connections_accepted": connections_accepted,
            "connection_accept_rate": connection_accept_rate,
            "messages_sent": messages_sent,
            "messages_replied": messages_replied,
            "responses": messages_replied,
            "response_rate": response_rate,
            "conversions": conversions,
            "conversion_rate": conversion_rate,
            "errors": errors,
            "rate_limit_warnings": 0,
        },
        "daily_breakdown": [],
        "pipeline": pipeline_stats,
    }


@router.get("/{campaign_id}/activity")
async def get_campaign_activity(
    campaign_id: str,
    user_id: str = Depends(get_current_user),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """Get activity log for a specific campaign."""
    campaign = models.Campaign.get(campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )
    if not campaign.has_access(user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    action_logs_collection = get_mongodb_collection("action_logs")
    tasks_collection = get_mongodb_collection("tasks")

    entries: List[Dict[str, Any]] = []

    if action_logs_collection is not None:
        skip = (page - 1) * limit
        total = action_logs_collection.count_documents({"campaign_id": campaign_id})
        logs = list(
            action_logs_collection.find({"campaign_id": campaign_id})
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
        for log in logs:
            entries.append({
                "id": str(log.get("_id", "")),
                "source": "action",
                "type": log.get("action_type", ""),
                "status": log.get("status", "completed"),
                "error": log.get("error_message") or None,
                "durationMs": log.get("duration_ms"),
                "timestamp": (log["created_at"].isoformat() + "Z") if log.get("created_at") else "",
                "details": log.get("details"),
            })
    else:
        total = 0

    # Get next scheduled task
    next_task = None
    if tasks_collection is not None:
        upcoming = tasks_collection.find_one(
            {"payload.campaign_id": campaign_id, "status": "pending"},
            sort=[("scheduled_at", 1)],
        )
        if upcoming:
            scheduled_at = upcoming.get("scheduled_at")
            eta = 0
            if scheduled_at:
                delta = (scheduled_at - datetime.utcnow()).total_seconds()
                eta = max(0, int(delta))
            next_task = {
                "id": str(upcoming.get("_id", "")),
                "taskType": upcoming.get("task_type", ""),
                "scheduledAt": scheduled_at.isoformat() if scheduled_at else "",
                "etaSeconds": eta,
            }

    pending_count = 0
    if tasks_collection is not None:
        pending_count = tasks_collection.count_documents({
            "payload.campaign_id": campaign_id,
            "status": "pending",
        })

    has_more = (page * limit) < total

    return {
        "data": entries,
        "nextTask": next_task,
        "pendingCount": pending_count,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "hasMore": has_more,
        },
    }
