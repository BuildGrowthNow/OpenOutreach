"""
Campaigns Router - FastAPI implementation with multi-tenant support

Provides endpoints for managing campaigns with proper user ownership
and team access control.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, cast

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
    linkedin_profile_id: Optional[str] = None  # Required for linkedin channel; optional for WA-only
    booking_link: Optional[str] = ""
    velocity: int = 20
    team_member_ids: Optional[List[str]] = None  # Optional: share with team
    icp_titles: Optional[List[str]] = None  # ICP job titles
    target_company_size: Optional[str] = None  # Target company size description
    follow_up_strategy: Optional[str] = None  # Follow-up strategy text
    target_degrees: Optional[List[int]] = None  # Target connection degrees (1, 2, 3)
    channel_sequence: Optional[List[str]] = None  # e.g. ["whatsapp", "linkedin"]
    channel_settings: Optional[Dict[str, Any]] = None  # per-channel config
    whatsapp_profile_id: Optional[str] = None  # WhatsAppProfile executing WA tasks
    lead_source: Optional[str] = None  # "linkedin_search" | "google_maps" | "csv_import"
    maps_query: Optional[str] = None
    maps_country_code: Optional[str] = None
    maps_backends: Optional[List[str]] = None
    maps_location: Optional[str] = None
    classified_sites: Optional[List[str]] = None

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
                "follow_up_strategy": "Send personalized follow-up after 3 days",
                "target_degrees": [1, 2, 3]
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
    target_company_size: Optional[str] = None
    follow_up_strategy: Optional[str] = None
    target_degrees: Optional[List[int]] = None
    channel_sequence: Optional[List[str]] = None
    channel_settings: Optional[Dict[str, Any]] = None
    whatsapp_profile_id: Optional[str] = None
    lead_source: Optional[str] = None
    maps_query: Optional[str] = None
    maps_country_code: Optional[str] = None
    maps_backends: Optional[List[str]] = None
    maps_location: Optional[str] = None
    classified_sites: Optional[List[str]] = None


class CampaignStats(BaseModel):
    totalLeads: int = 0
    connected: int = 0
    completed: int = 0
    messagesSent: int = 0
    messagesReplied: int = 0
    noEmailCount: int = 0
    todayConnectBudget: Optional[int] = None
    emailQueued: int = 0
    emailSent: int = 0
    emailOpened: int = 0
    emailReplied: int = 0
    emailBounced: int = 0


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
    target_company_size: Optional[str] = None
    follow_up_strategy: Optional[str]
    target_degrees: List[int] = [1, 2, 3]
    created_at: str
    stats: CampaignStats = CampaignStats()
    channel_sequence: List[str] = ["linkedin"]
    channel_settings: Optional[Dict[str, Any]] = None
    whatsapp_profile_id: Optional[str] = None
    lead_source: str = "linkedin_search"
    maps_query: Optional[str] = None
    maps_country_code: Optional[str] = None
    maps_backends: List[str] = []
    maps_location: Optional[str] = None
    classified_sites: List[str] = []


class PaginationInfo(BaseModel):
    total: int
    page: int
    limit: int
    pages: int


class CampaignListResponse(BaseModel):
    """Response schema for campaign list - matches frontend { data, pagination } shape."""
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
        action_logs_collection = get_mongodb_collection("action_logs")
        campaign_stats: Dict[str, Dict] = {}
        if deals_collection is not None and docs:
            campaign_ids = [str(doc["_id"]) for doc in docs]
            pipeline = [
                {"$match": {"campaign_id": {"$in": campaign_ids}}},
                {"$group": {
                    "_id": "$campaign_id",
                    "totalLeads": {"$sum": 1},
                    "completed": {"$sum": {"$cond": [{"$eq": ["$state", "Completed"]}, 1, 0]}},
                    "noEmailCount": {"$sum": {"$cond": [{"$eq": ["$state", "No Email"]}, 1, 0]}},
                    "emailQueued": {"$sum": {"$cond": [{"$eq": ["$state", "email_queued"]}, 1, 0]}},
                    "emailSent": {"$sum": {"$cond": [{"$eq": ["$state", "email_sent"]}, 1, 0]}},
                    "emailOpened": {"$sum": {"$cond": [{"$eq": ["$state", "email_opened"]}, 1, 0]}},
                    "emailReplied": {"$sum": {"$cond": [{"$eq": ["$state", "email_replied"]}, 1, 0]}},
                    "emailBounced": {"$sum": {"$cond": [{"$eq": ["$state", "email_bounced"]}, 1, 0]}},
                }},
            ]
            for row in deals_collection.aggregate(pipeline):
                campaign_stats[str(row["_id"])] = {
                    "totalLeads": row.get("totalLeads", 0),
                    "connected": 0,
                    "completed": row.get("completed", 0),
                    "noEmailCount": row.get("noEmailCount", 0),
                    "emailQueued": row.get("emailQueued", 0),
                    "emailSent": row.get("emailSent", 0),
                    "emailOpened": row.get("emailOpened", 0),
                    "emailReplied": row.get("emailReplied", 0),
                    "emailBounced": row.get("emailBounced", 0),
                }

        # Compute today's remaining connect budget per campaign.
        # Budget = floor((profile.connect_daily_limit - today_connects) / active_campaigns_on_profile).
        profile_budget: Dict[str, int] = {}
        if docs:
            from openoutreach.mongodb.connection import get_mongodb_collection as _get_col
            from datetime import datetime, timezone as _tz
            profiles_col = _get_col("linkedin_profiles")
            action_logs_col = _get_col("action_logs")
            if profiles_col is not None and action_logs_col is not None:
                # Group active campaigns by profile
                profile_campaign_count: Dict[str, int] = {}
                profile_ids_needed: set = set()
                for doc in docs:
                    pid = str(doc.get("linkedin_profile_id", ""))
                    if pid and doc.get("status") == "active":
                        profile_campaign_count[pid] = profile_campaign_count.get(pid, 0) + 1
                        profile_ids_needed.add(pid)
                today_start = datetime.now(_tz.utc).replace(hour=0, minute=0, second=0, microsecond=0)
                for profile_doc in profiles_col.find({"_id": {"$in": list(profile_ids_needed)}}):
                    pid = str(profile_doc["_id"])
                    daily_limit = profile_doc.get("connect_daily_limit", 20)
                    today_count = action_logs_col.count_documents({
                        "linkedin_profile_id": pid,
                        "action_type": "connect",
                        "status": "completed",
                        "created_at": {"$gte": today_start},
                    })
                    remaining = max(0, daily_limit - today_count)
                    n = max(1, profile_campaign_count.get(pid, 1))
                    profile_budget[pid] = max(0, remaining // n)

        # connections_accepted = actual connect actions from ActionLog, not deal state.
        # Deal state includes 1st-degree leads auto-transitioned to CONNECTED without
        # ever sending a connection request, which inflates the count.
        if action_logs_collection is not None and docs:
            campaign_ids = [str(doc["_id"]) for doc in docs]
            connect_pipeline = [
                {"$match": {
                    "campaign_id": {"$in": campaign_ids},
                    "action_type": "connect",
                    "status": {"$nin": ["failed", "error"]},
                }},
                {"$group": {"_id": "$campaign_id", "connected": {"$sum": 1}}},
            ]
            for row in action_logs_collection.aggregate(connect_pipeline):
                cid = str(row["_id"])
                if cid in campaign_stats:
                    campaign_stats[cid]["connected"] = row.get("connected", 0)
                else:
                    campaign_stats[cid] = {"totalLeads": 0, "connected": row.get("connected", 0), "completed": 0}

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
                target_company_size=doc.get("target_company_size"),
                follow_up_strategy=doc.get("follow_up_strategy"),
                target_degrees=doc.get("target_degrees", [1, 2, 3]),
                created_at=doc.get("created_at").isoformat() if doc.get("created_at") else "",
                channel_sequence=doc.get("channel_sequence") or ["linkedin"],
                channel_settings=doc.get("channel_settings"),
                whatsapp_profile_id=doc.get("whatsapp_profile_id"),
                lead_source=doc.get("lead_source", "linkedin_search"),
                maps_query=doc.get("maps_query"),
                maps_country_code=doc.get("maps_country_code"),
                maps_backends=doc.get("maps_backends") or [],
                maps_location=doc.get("maps_location"),
                classified_sites=doc.get("classified_sites") or [],
                stats=CampaignStats(
                    totalLeads=s.get("totalLeads", 0),
                    connected=s.get("connected", 0),
                    completed=s.get("completed", 0),
                    noEmailCount=s.get("noEmailCount", 0),
                    todayConnectBudget=profile_budget.get(str(doc.get("linkedin_profile_id", ""))) if doc.get("status") == "active" else None,
                    emailQueued=s.get("emailQueued", 0),
                    emailSent=s.get("emailSent", 0),
                    emailOpened=s.get("emailOpened", 0),
                    emailReplied=s.get("emailReplied", 0),
                    emailBounced=s.get("emailBounced", 0),
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

        # Verify user owns the LinkedIn profile (only when one is provided)
        channel_seq = data.channel_sequence or ["linkedin"]
        invalid_channels = set(channel_seq) - {"linkedin", "email", "whatsapp"}
        if invalid_channels:
            raise HTTPException(status_code=422, detail=f"Unsupported campaign channel(s): {', '.join(sorted(invalid_channels))}")
        linkedin_required = "linkedin" in channel_seq
        if data.linkedin_profile_id and profiles_collection is not None:
            profile_doc = profiles_collection.find_one({
                "_id": data.linkedin_profile_id,
                "user_id": user_id
            })
            if not profile_doc:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="LinkedIn profile not found or access denied"
                )
        elif linkedin_required and not data.linkedin_profile_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="linkedin_profile_id is required when linkedin channel is active"
            )

        if "whatsapp" in channel_seq:
            wa_col = get_mongodb_collection("whatsapp_profiles")
            if not data.whatsapp_profile_id or wa_col is None:
                raise HTTPException(status_code=400, detail="A WhatsApp profile is required when WhatsApp is active")
            wa_doc = wa_col.find_one({"_id": data.whatsapp_profile_id, "user_id": user_id})
            if not wa_doc or wa_doc.get("status") not in ("connected", "active"):
                raise HTTPException(status_code=400, detail="WhatsApp profile is not connected or access was denied")
            wa_settings = (data.channel_settings or {}).get("whatsapp", {})
            if not isinstance(wa_settings, dict) or not str(wa_settings.get("message_template", "")).strip():
                raise HTTPException(status_code=422, detail="WhatsApp requires a non-empty message template")

        if "email" in channel_seq:
            mailbox_col = get_mongodb_collection("mailboxes")
            if mailbox_col is None or mailbox_col.count_documents({"user_id": user_id, "paused": {"$ne": True}}) == 0:
                raise HTTPException(status_code=400, detail="Connect an active mailbox before enabling email")

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
            target_company_size=data.target_company_size,
            follow_up_strategy=data.follow_up_strategy,
            target_degrees=data.target_degrees if data.target_degrees is not None else [1, 2, 3],
            channel_sequence=data.channel_sequence or ["linkedin"],
            channel_settings=data.channel_settings,
            whatsapp_profile_id=data.whatsapp_profile_id,
            lead_source=data.lead_source or "linkedin_search",
            maps_query=data.maps_query,
            maps_country_code=data.maps_country_code,
            maps_backends=data.maps_backends or [],
            maps_location=data.maps_location,
            classified_sites=data.classified_sites or [],
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
            target_company_size=campaign.target_company_size,
            follow_up_strategy=campaign.follow_up_strategy,
            target_degrees=campaign.target_degrees,
            created_at=campaign.created_at.isoformat() if campaign.created_at else "",
            channel_sequence=campaign.channel_sequence or ["linkedin"],
            channel_settings=campaign.channel_settings,
            whatsapp_profile_id=campaign.whatsapp_profile_id,
            lead_source=campaign.lead_source,
            maps_query=campaign.maps_query,
            maps_country_code=campaign.maps_country_code,
            maps_backends=campaign.maps_backends,
            maps_location=campaign.maps_location,
            classified_sites=campaign.classified_sites or [],
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
        target_company_size=campaign.target_company_size,
        follow_up_strategy=campaign.follow_up_strategy,
        target_degrees=campaign.target_degrees,
        created_at=campaign.created_at.isoformat() if campaign.created_at else "",
        channel_sequence=campaign.channel_sequence or ["linkedin"],
        channel_settings=campaign.channel_settings,
        whatsapp_profile_id=campaign.whatsapp_profile_id,
        lead_source=campaign.lead_source,
        maps_query=campaign.maps_query,
        maps_country_code=campaign.maps_country_code,
        maps_backends=campaign.maps_backends or [],
        maps_location=campaign.maps_location,
        classified_sites=campaign.classified_sites or [],
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

        # Resolve the effective channel configuration before applying an edit.
        # This prevents campaign updates from bypassing the stricter create-time
        # WhatsApp checks (e.g. selecting another user's or disconnected profile).
        effective_channels = data.channel_sequence if data.channel_sequence is not None else (campaign.channel_sequence or ["linkedin"])
        effective_wa_id = data.whatsapp_profile_id if data.whatsapp_profile_id is not None else campaign.whatsapp_profile_id
        effective_settings = data.channel_settings if data.channel_settings is not None else (campaign.channel_settings or {})
        requested_active = data.status == "active" or data.is_paused is False
        if "whatsapp" in effective_channels and (requested_active or data.channel_sequence is not None or data.whatsapp_profile_id is not None or data.channel_settings is not None):
            wa_col = get_mongodb_collection("whatsapp_profiles")
            wa_doc = wa_col.find_one({"_id": effective_wa_id, "user_id": user_id}) if wa_col is not None and effective_wa_id else None
            if not wa_doc or wa_doc.get("status") not in ("connected", "active"):
                raise HTTPException(status_code=400, detail="WhatsApp profile is not connected or access was denied")
            wa_settings = effective_settings.get("whatsapp", {}) if isinstance(effective_settings, dict) else {}
            if not isinstance(wa_settings, dict) or not str(wa_settings.get("message_template", "")).strip():
                raise HTTPException(status_code=422, detail="WhatsApp requires a non-empty message template")

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
        if data.target_company_size is not None:
            updates["target_company_size"] = data.target_company_size
        if data.follow_up_strategy is not None:
            updates["follow_up_strategy"] = data.follow_up_strategy
        if data.target_degrees is not None:
            updates["target_degrees"] = data.target_degrees
        if data.channel_sequence is not None:
            updates["channel_sequence"] = data.channel_sequence
        if data.channel_settings is not None:
            updates["channel_settings"] = data.channel_settings
        if data.whatsapp_profile_id is not None:
            updates["whatsapp_profile_id"] = data.whatsapp_profile_id
        if data.lead_source is not None:
            updates["lead_source"] = data.lead_source
        if data.maps_query is not None:
            updates["maps_query"] = data.maps_query
        if data.maps_country_code is not None:
            updates["maps_country_code"] = data.maps_country_code
        if data.maps_backends is not None:
            updates["maps_backends"] = data.maps_backends
        if data.maps_location is not None:
            updates["maps_location"] = data.maps_location
        if data.classified_sites is not None:
            updates["classified_sites"] = data.classified_sites

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
            target_company_size=updated_campaign.target_company_size,
            follow_up_strategy=updated_campaign.follow_up_strategy,
            target_degrees=updated_campaign.target_degrees,
            created_at=updated_campaign.created_at.isoformat() if updated_campaign.created_at else "",
            channel_sequence=updated_campaign.channel_sequence or ["linkedin"],
            channel_settings=updated_campaign.channel_settings,
            whatsapp_profile_id=updated_campaign.whatsapp_profile_id,
            lead_source=updated_campaign.lead_source,
            maps_query=updated_campaign.maps_query,
            maps_country_code=updated_campaign.maps_country_code,
            maps_backends=updated_campaign.maps_backends,
            maps_location=updated_campaign.maps_location,
            classified_sites=updated_campaign.classified_sites or [],
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

        # Cascade-delete all related data
        tasks_collection = get_mongodb_collection("tasks")
        chat_messages_collection = get_mongodb_collection("chat_messages")

        if deals_collection is not None:
            deal_ids = [d["_id"] for d in deals_collection.find({"campaign_id": campaign_id}, {"_id": 1})]
            if deal_ids and chat_messages_collection is not None:
                chat_messages_collection.delete_many({"deal_id": {"$in": deal_ids}})
            deals_collection.delete_many({"campaign_id": campaign_id})

        if tasks_collection is not None:
            tasks_collection.delete_many({"payload.campaign_id": campaign_id})

        # Delete campaign
        result = campaigns_collection.delete_one({"_id": campaign_id})
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )

        logger.info("Deleted campaign %s by user %s", campaign_id, user_id)
        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to delete campaign")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete campaign: {str(e)}"
        )


@router.delete("/{campaign_id}/errors", status_code=204)
async def clear_campaign_errors(
    campaign_id: str,
    user_id: str = Depends(get_current_user),
):
    """Delete all failed/error ActionLog entries for a campaign."""
    campaign = models.Campaign.get(campaign_id)
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    if user_id != campaign.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    action_logs_collection = get_mongodb_collection("action_logs")
    if action_logs_collection is not None:
        action_logs_collection.delete_many({
            "campaign_id": campaign_id,
            "status": {"$in": ["failed", "error"]},
        })
    return None


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
            target_company_size=updated_campaign.target_company_size,
            follow_up_strategy=updated_campaign.follow_up_strategy,
            target_degrees=updated_campaign.target_degrees,
            created_at=updated_campaign.created_at.isoformat() if updated_campaign.created_at else "",
            channel_sequence=updated_campaign.channel_sequence or ["linkedin"],
            channel_settings=updated_campaign.channel_settings,
            whatsapp_profile_id=updated_campaign.whatsapp_profile_id,
            lead_source=updated_campaign.lead_source,
            maps_query=updated_campaign.maps_query,
            maps_country_code=updated_campaign.maps_country_code,
            maps_backends=updated_campaign.maps_backends,
            maps_location=updated_campaign.maps_location,
            classified_sites=updated_campaign.classified_sites or [],
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
    Enforces plan campaign limit - resuming counts the same as creating.
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
            target_company_size=updated_campaign.target_company_size,
            follow_up_strategy=updated_campaign.follow_up_strategy,
            target_degrees=updated_campaign.target_degrees,
            created_at=updated_campaign.created_at.isoformat() if updated_campaign.created_at else "",
            channel_sequence=updated_campaign.channel_sequence or ["linkedin"],
            channel_settings=updated_campaign.channel_settings,
            whatsapp_profile_id=updated_campaign.whatsapp_profile_id,
            lead_source=updated_campaign.lead_source,
            maps_query=updated_campaign.maps_query,
            maps_country_code=updated_campaign.maps_country_code,
            maps_backends=updated_campaign.maps_backends,
            maps_location=updated_campaign.maps_location,
            classified_sites=updated_campaign.classified_sites or [],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to resume campaign")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resume campaign: {str(e)}"
        )


class LeadChannelAvailability(BaseModel):
    linkedin: bool
    email: bool
    whatsapp: bool


class LeadResponse(BaseModel):
    id: str
    public_identifier: str
    url: str
    full_name: Optional[str] = None
    company: Optional[str] = None
    headline: Optional[str] = None
    location: Optional[str] = None
    disqualified: bool = False
    created_at: Optional[str] = None
    phone: Optional[str] = None
    channel_availability: Optional[LeadChannelAvailability] = None


class DealResponse(BaseModel):
    id: str
    lead_id: str
    campaign_id: str
    state: str
    outcome: Optional[str] = None
    reason: Optional[str] = None
    creation_date: Optional[str] = None
    last_outgoing_at: Optional[str] = None
    next_follow_up_at: Optional[str] = None
    unanswered_count: int = 0
    active_channel: str = "linkedin"
    qualification_hold: bool = False
    qualification_reason: Optional[str] = None
    email_sequence_step: int = 0
    email_sent_at: Optional[str] = None


@router.get("/{campaign_id}/leads")
async def get_campaign_leads(
    campaign_id: str,
    user_id: str = Depends(get_current_user),
    state: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    qualification_hold: Optional[bool] = Query(None),
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

    leads_collection = get_mongodb_collection("leads")
    if leads_collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable"
        )

    # Build query
    query: Dict[str, Any] = {"campaign_id": campaign_id}
    if state:
        query["state"] = state
    if qualification_hold is True:
        query["state"] = "Discovered"
        query["qualification_hold"] = True
    elif qualification_hold is False:
        query["qualification_hold"] = {"$ne": True}

    if search:
        # Join with leads to filter by name/identifier - fetch all deals first then filter
        all_deals = list(collection.find(query).sort("creation_date", -1))
        all_lead_ids = list(set(str(d["lead_id"]) for d in all_deals))
        term = search.lower()
        matching_ids: set = set()
        for lead_doc in leads_collection.find(
            {"_id": {"$in": all_lead_ids}},
            {"_id": 1, "full_name": 1, "public_identifier": 1, "headline": 1},
        ):
            if (
                term in (lead_doc.get("full_name") or "").lower()
                or term in (lead_doc.get("public_identifier") or "").lower()
                or term in (lead_doc.get("headline") or "").lower()
            ):
                matching_ids.add(str(lead_doc["_id"]))
        filtered_deals = [d for d in all_deals if str(d["lead_id"]) in matching_ids]
        total = len(filtered_deals)
        deals = filtered_deals[offset: offset + limit]
    else:
        total = collection.count_documents(query)
        deals = list(collection.find(query).skip(offset).limit(limit).sort("creation_date", -1))

    # Get unique lead IDs for the current page
    lead_ids = list(set(str(d["lead_id"]) for d in deals))

    # Fetch leads
    leads_data = {str(lead_doc["_id"]): lead_doc for lead_doc in leads_collection.find({"_id": {"$in": lead_ids}})}

    # Batch-compute nudge counts for CONNECTED deals so the UI can show cooldown info.
    # For each deal: count outgoing messages since the last incoming reply.
    messages_collection = get_mongodb_collection("chat_messages")
    deal_nudge_info: Dict[str, Dict] = {}
    if messages_collection is not None:
        connected_deal_ids = [str(d["_id"]) for d in deals if d.get("state") == "Connected"]
        if connected_deal_ids:
            # Aggregate: per deal_id, count outgoing messages after the latest incoming one
            pipeline = [
                {"$match": {"deal_id": {"$in": connected_deal_ids}}},
                {"$sort": {"creation_date": -1}},
                {"$group": {
                    "_id": "$deal_id",
                    "messages": {"$push": {"is_outgoing": "$is_outgoing", "creation_date": "$creation_date"}},
                }},
            ]
            for row in messages_collection.aggregate(pipeline):
                msgs = row["messages"]
                last_incoming_idx = next(
                    (i for i, m in enumerate(msgs) if not m.get("is_outgoing", False)), None
                )
                if last_incoming_idx is None:
                    nudge_count = sum(1 for m in msgs if m.get("is_outgoing", False))
                else:
                    nudge_count = last_incoming_idx  # outgoing msgs before first incoming (newest-first)
                last_outgoing = next(
                    (m["creation_date"] for m in msgs if m.get("is_outgoing", False)), None
                )
                next_follow_up_at = None
                if nudge_count > 0 and last_outgoing:
                    wait_days = max(1, nudge_count) * 3
                    nfa = last_outgoing + timedelta(days=wait_days)
                    if nfa.tzinfo is None:
                        nfa = nfa.replace(tzinfo=timezone.utc)
                    next_follow_up_at = nfa.isoformat() + "Z"
                deal_nudge_info[str(row["_id"])] = {
                    "unanswered_count": nudge_count,
                    "next_follow_up_at": next_follow_up_at,
                }

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
            # company: stored directly or derived from headline " at X" for legacy leads
            company = lead_data.get("company")
            if not company and headline:
                at_idx = headline.lower().find(" at ")
                if at_idx > -1:
                    company = headline[at_idx + 4:].strip() or None
            deal_id_str = str(deal["_id"])
            nudge = deal_nudge_info.get(deal_id_str, {})
            last_outgoing_at = deal.get("last_outgoing_at")
            has_email = bool(
                lead_data.get("api_email")
                or (lead_data.get("contact_info") or {}).get("email")
            )
            has_phone = bool(lead_data.get("phone"))
            has_whatsapp = has_phone and lead_data.get("phone_on_whatsapp") is not False
            results.append({
                "lead": LeadResponse(
                    id=str(lead_data["_id"]),
                    public_identifier=lead_data.get("public_identifier", ""),
                    url=lead_data.get("linkedin_url", lead_data.get("url", "")),
                    full_name=full_name,
                    company=company,
                    headline=headline,
                    location=location,
                    disqualified=lead_data.get("disqualified", False),
                    created_at=lead_data.get("creation_date").isoformat() if lead_data.get("creation_date") else None,
                    phone=lead_data.get("phone"),
                    channel_availability=LeadChannelAvailability(
                        linkedin=bool(lead_data.get("linkedin_url") or lead_data.get("url")),
                        email=has_email,
                        whatsapp=has_whatsapp,
                    ),
                ),
                "deal": DealResponse(
                    id=deal_id_str,
                    lead_id=str(deal["lead_id"]),
                    campaign_id=str(deal["campaign_id"]),
                    state=deal.get("state", "Discovered"),
                    outcome=deal.get("outcome"),
                    reason=deal.get("reason"),
                    creation_date=deal.get("creation_date").isoformat() if deal.get("creation_date") else None,
                    last_outgoing_at=last_outgoing_at.isoformat() + "Z" if last_outgoing_at else None,
                    next_follow_up_at=nudge.get("next_follow_up_at"),
                    unanswered_count=nudge.get("unanswered_count", 0),
                    active_channel=deal.get("active_channel", "linkedin"),
                    qualification_hold=bool(deal.get("qualification_hold", False)),
                    qualification_reason=deal.get("qualification_reason"),
                    email_sequence_step=deal.get("email_sequence_step", 0),
                    email_sent_at=deal.get("email_sent_at").isoformat() if deal.get("email_sent_at") else None,
                )
            })

    # Fix #6: return pipeline counts as DB aggregates so UI shows full campaign totals
    pipeline_agg = [
        {"$match": {"campaign_id": campaign_id}},
        {"$group": {"_id": "$state", "count": {"$sum": 1}}},
    ]
    state_counts: Dict[str, int] = {}
    for row in collection.aggregate(pipeline_agg):
        state_counts[row["_id"]] = row["count"]

    # Count "Needs Review" leads: DISCOVERED deals with qualification_hold=True
    needs_review_count = collection.count_documents({
        "campaign_id": campaign_id,
        "state": "Discovered",
        "qualification_hold": True,
    })

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "results": results,
        "pipelineCounts": {
            "qualified": state_counts.get("Qualified", 0),
            "completed": state_counts.get("Completed", 0),
            "failed": state_counts.get("Failed", 0),
            "connected": state_counts.get("Connected", 0),
            "pending": state_counts.get("Pending", 0),
            "discovered": state_counts.get("Discovered", 0),
            "readyToConnect": state_counts.get("ReadyToConnect", 0),
            "noEmail": state_counts.get("No Email", 0),
            "needsReview": needs_review_count,
        },
    }


class ManualQualifyRequest(BaseModel):
    decision: str  # "qualify" | "reject" | "retry"
    reason: Optional[str] = None


@router.post("/{campaign_id}/leads/{lead_id}/qualify-manual")
async def manual_qualify_lead(
    campaign_id: str,
    lead_id: str,
    body: ManualQualifyRequest,
    user_id: str = Depends(get_current_user),
):
    """Manually qualify, reject, or retry AI qualification for a held lead.

    decision:
      "qualify" — promote DISCOVERED deal to QUALIFIED (skip AI, run enrichment)
      "reject"  — mark deal FAILED, disqualify lead
      "retry"   — clear qualification_hold so the daemon re-evaluates with AI
    """
    campaign = models.Campaign.get(campaign_id)
    if not campaign or not campaign.has_access(user_id):
        raise HTTPException(status_code=403, detail="Access denied")

    deals_col = get_mongodb_collection("deals")
    leads_col = get_mongodb_collection("leads")
    if deals_col is None or leads_col is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    deal_doc = deals_col.find_one({
        "lead_id": lead_id,
        "campaign_id": campaign_id,
    })
    if not deal_doc:
        raise HTTPException(status_code=404, detail="Deal not found")

    reason = body.reason or "Manual override"
    decision = body.decision

    if decision == "qualify":
        deals_col.update_one(
            {"_id": deal_doc["_id"]},
            {"$set": {
                "state": "Qualified",
                "qualification_hold": False,
                "qualification_reason": reason,
            }},
        )
        # Trigger email enrichment via free waterfall
        try:
            from openoutreach.mongodb.models import Lead as LeadModel
            lead = LeadModel.get(lead_id)
            if lead:
                result = lead.resolve_api_email()
                if result is False:
                    deals_col.update_one(
                        {"_id": deal_doc["_id"]},
                        {"$set": {"state": "No Email"}},
                    )
        except Exception:
            pass
        return {"success": True, "decision": "qualify", "message": "Lead manually qualified"}

    elif decision == "reject":
        deals_col.update_one(
            {"_id": deal_doc["_id"]},
            {"$set": {
                "state": "Failed",
                "outcome": "wrong_fit",
                "qualification_hold": False,
                "qualification_reason": reason,
            }},
        )
        leads_col.update_one(
            {"_id": lead_id},
            {"$set": {"disqualified": True}},
        )
        return {"success": True, "decision": "reject", "message": "Lead rejected"}

    elif decision == "retry":
        deals_col.update_one(
            {"_id": deal_doc["_id"]},
            {"$unset": {"qualification_hold": "", "qualification_reason": ""}},
        )
        return {"success": True, "decision": "retry", "message": "Re-queued for AI qualification"}

    raise HTTPException(status_code=400, detail=f"Unknown decision: {decision!r}")


@router.get("/{campaign_id}/leads/{lead_id}/sequence-timeline")
async def get_lead_sequence_timeline(
    campaign_id: str,
    lead_id: str,
    user_id: str = Depends(get_current_user),
):
    campaign = models.Campaign.get(campaign_id)
    if not campaign or not campaign.has_access(user_id):
        raise HTTPException(status_code=403, detail="Access denied")

    deals_col = get_mongodb_collection("deals")
    if deals_col is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    deal_doc = deals_col.find_one({"lead_id": lead_id, "campaign_id": campaign_id})
    if not deal_doc:
        raise HTTPException(status_code=404, detail="Deal not found")

    steps = campaign.sequence_steps or []
    edges = campaign.sequence_edges or []
    current_position = deal_doc.get("sequence_position")
    sequence_done = deal_doc.get("sequence_done", False)

    step_by_id = {s["id"]: s for s in steps}
    edge_targets = {e["target"] for e in edges}
    root_ids = [s["id"] for s in steps if s["id"] not in edge_targets]
    root_id = root_ids[0] if root_ids else (steps[0]["id"] if steps else None)

    # Find the path actually taken by this deal: BFS from root to current_position.
    # This correctly handles branching — only the branch the deal traversed is shown.
    def _find_path(from_id: str, to_id: Optional[str]) -> List[str]:
        """BFS returning shortest path from from_id to to_id (inclusive)."""
        if to_id is None:
            # Deal not started yet — walk main path (first edge at each branch)
            path: List[str] = []
            cursor_inner = from_id
            visited_inner: set = set()
            while cursor_inner and cursor_inner not in visited_inner:
                path.append(cursor_inner)
                visited_inner.add(cursor_inner)
                out = [e for e in edges if e["source"] == cursor_inner]
                cursor_inner = out[0]["target"] if out else None
            return path
        if from_id == to_id:
            return [from_id]
        from collections import deque
        queue: deque = deque([[from_id]])
        visited_bfs: set = set()
        while queue:
            path = queue.popleft()
            node = path[-1]
            if node in visited_bfs:
                continue
            visited_bfs.add(node)
            for e in edges:
                if e["source"] == node:
                    new_path = path + [e["target"]]
                    if e["target"] == to_id:
                        return new_path
                    queue.append(new_path)
        # target not reachable from root via any path — fall back to linear walk
        fallback: List[str] = []
        c = from_id
        vis: set = set()
        while c and c not in vis:
            fallback.append(c)
            vis.add(c)
            if c == to_id:
                break
            out = [e for e in edges if e["source"] == c]
            c = out[0]["target"] if out else None
        return fallback

    ordered = _find_path(root_id, current_position) if root_id else []

    # Append pending steps after current_position (follow first edge from here)
    if current_position and not sequence_done:
        cursor = current_position
        visited_tail: set = set(ordered)
        out = [e for e in edges if e["source"] == cursor]
        nxt = out[0]["target"] if out else None
        while nxt and nxt not in visited_tail:
            ordered.append(nxt)
            visited_tail.add(nxt)
            cursor = nxt
            out = [e for e in edges if e["source"] == cursor]
            nxt = out[0]["target"] if out else None

    completed_ids: set = set()
    if current_position:
        for sid in ordered:
            if sid == current_position:
                break
            completed_ids.add(sid)
    elif sequence_done:
        # Mark all steps on the traversed path as completed (not unvisited branches).
        completed_ids = set(ordered)

    # Fetch per-step task completion timestamps (populated since Bug 10 fix stores step_id)
    tasks_col = get_mongodb_collection("tasks")
    step_completed_at: Dict[str, Any] = {}
    if tasks_col is not None and completed_ids:
        for task_doc in tasks_col.find(
            {
                "payload.deal_id": str(deal_doc["_id"]),
                "payload.step_id": {"$in": list(completed_ids)},
                "status": "completed",
            },
            projection={"payload.step_id": 1, "completed_at": 1},
        ):
            sid_key = (task_doc.get("payload") or {}).get("step_id")
            if sid_key:
                step_completed_at[sid_key] = task_doc.get("completed_at")

    timeline = []
    for sid in ordered:
        step = step_by_id.get(sid)
        if not step:
            continue
        data = step.get("data") or {}
        if sequence_done and not current_position:
            status_val = "completed"
        elif sid in completed_ids:
            status_val = "completed"
        elif sid == current_position:
            status_val = "active"
        else:
            status_val = "pending"
        entry: Dict[str, Any] = {
            "stepId": sid,
            "type": step.get("type"),
            "label": data.get("label") or step.get("type", ""),
            "channel": data.get("channel"),
            "action": data.get("action"),
            "waitDays": data.get("wait_days", 0),
            "waitHours": data.get("wait_hours", 0),
            "status": status_val,
            "completedAt": step_completed_at.get(sid),
        }
        timeline.append(entry)

    return {
        "sequenceActive": campaign.sequence_active,
        "sequenceDone": sequence_done,
        "currentPosition": current_position,
        "timeline": timeline,
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

    # Find the next scheduled task for this campaign so the UI can show "Next action at X"
    next_action_at = None
    tasks_col = get_mongodb_collection("tasks")
    if tasks_col is not None:
        from datetime import datetime, timezone as _tz
        next_task = tasks_col.find_one(
            {
                "status": "pending",
                "payload.campaign_id": campaign_id,
                "scheduled_at": {"$gte": datetime.now(_tz.utc)},
            },
            sort=[("scheduled_at", 1)],
            projection={"scheduled_at": 1},
        )
        if next_task and next_task.get("scheduled_at"):
            dt = next_task["scheduled_at"]
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=_tz.utc)
            next_action_at = dt.isoformat() + "Z"

    return {"status": campaign.status, "is_paused": campaign.is_paused, "nextActionAt": next_action_at}


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
    since = datetime.now(timezone.utc) - timedelta(days=period_days) if period_days else datetime(2000, 1, 1, tzinfo=timezone.utc)

    connections_sent = 0
    connections_accepted = 0
    messages_sent = 0
    messages_replied = 0
    conversions = 0
    errors = 0

    _LI_MSG_TYPES = ["follow_up", "send_manual_message"]
    _WA_MSG_TYPES = ["whatsapp_message", "whatsapp_follow_up"]

    if action_logs_collection is not None:
        connections_sent = action_logs_collection.count_documents({
            "campaign_id": campaign_id,
            "action_type": "connect",
            "status": {"$nin": ["failed", "error"]},
            "created_at": {"$gte": since},
        })
        messages_sent = action_logs_collection.count_documents({
            "campaign_id": campaign_id,
            "action_type": {"$in": _LI_MSG_TYPES},
            "status": {"$nin": ["failed", "error"]},
            "created_at": {"$gte": since},
        })
        errors = action_logs_collection.count_documents({
            "campaign_id": campaign_id,
            "status": {"$in": ["failed", "error"]},
            "created_at": {"$gte": since},
        })

    if deals_collection is not None:
        _accepted_pipeline = [
            {"$match": {"campaign_id": campaign_id, "state": DealState.CONNECTED.value}},
            {"$lookup": {"from": "leads", "localField": "lead_id", "foreignField": "_id", "as": "lead"}},
            {"$unwind": {"path": "$lead", "preserveNullAndEmptyArrays": True}},
            {"$match": {"$or": [
                {"lead.connection_degree": {"$exists": False}},
                {"lead.connection_degree": None},
                {"lead.connection_degree": {"$ne": 1}},
            ]}},
            {"$count": "total"},
        ]
        _accepted_result = list(deals_collection.aggregate(_accepted_pipeline))
        connections_accepted = _accepted_result[0]["total"] if _accepted_result else 0
        conversions = deals_collection.count_documents({
            "campaign_id": campaign_id,
            "state": DealState.COMPLETED.value,
        })

    distinct_deals_messaged = 0
    li_messages_sent = messages_sent
    li_messages_replied = 0
    li_distinct_messaged = 0
    wa_messages_sent = 0
    wa_messages_replied = 0
    wa_distinct_messaged = 0

    if action_logs_collection is not None:
        wa_messages_sent = action_logs_collection.count_documents({
            "campaign_id": campaign_id,
            "action_type": {"$in": _WA_MSG_TYPES},
            "status": {"$nin": ["failed", "error"]},
            "created_at": {"$gte": since},
        })

    email_messages_sent = 0
    email_messages_replied = 0
    email_distinct_messaged = 0
    email_opens = 0
    email_clicks = 0
    email_bounces = 0

    if messages_collection is not None:
        try:
            def _agg_count(match_extra: Dict[str, Any]) -> int:
                base: Dict[str, Any] = {"creation_date": {"$gte": since}}
                base.update(match_extra)
                pipeline = [
                    {"$match": base},
                    {"$lookup": {"from": "deals", "localField": "deal_id", "foreignField": "_id", "as": "deal"}},
                    {"$unwind": "$deal"},
                    {"$match": {"deal.campaign_id": campaign_id}},
                    {"$group": {"_id": "$deal_id"}},
                    {"$count": "total"},
                ]
                res = list(messages_collection.aggregate(pipeline))
                return res[0]["total"] if res else 0

            messages_replied = _agg_count({"is_outgoing": False})
            distinct_deals_messaged = _agg_count({"is_outgoing": True})
            li_messages_replied = _agg_count({"is_outgoing": False, "channel": "linkedin"})
            li_distinct_messaged = _agg_count({"is_outgoing": True, "channel": "linkedin"})
            wa_messages_replied = _agg_count({"is_outgoing": False, "channel": "whatsapp"})
            wa_distinct_messaged = _agg_count({"is_outgoing": True, "channel": "whatsapp"})
            email_messages_replied = _agg_count({"is_outgoing": False, "channel": "email"})
            email_distinct_messaged = _agg_count({"is_outgoing": True, "channel": "email"})
            email_messages_sent = email_distinct_messaged
        except Exception:
            pass

    if deals_collection is not None:
        try:
            email_opens = deals_collection.count_documents({
                "campaign_id": campaign_id,
                "state": {"$in": ["email_opened", "email_replied"]},
            })
            email_clicks = deals_collection.count_documents({
                "campaign_id": campaign_id,
                "email_clicked_at": {"$exists": True, "$ne": None},
            })
            email_bounces = deals_collection.count_documents({
                "campaign_id": campaign_id,
                "state": "email_bounced",
            })
        except Exception:
            pass

    connection_accept_rate = round((connections_accepted / connections_sent * 100), 2) if connections_sent else 0.0
    response_rate = round((messages_replied / distinct_deals_messaged * 100), 2) if distinct_deals_messaged else 0.0
    conversion_rate = round((conversions / connections_accepted * 100), 2) if connections_accepted else 0.0
    li_response_rate = round((li_messages_replied / li_distinct_messaged * 100), 2) if li_distinct_messaged else 0.0
    wa_response_rate = round((wa_messages_replied / wa_distinct_messaged * 100), 2) if wa_distinct_messaged else 0.0
    email_open_rate = round((email_opens / email_messages_sent * 100), 2) if email_messages_sent else 0.0
    email_reply_rate = round((email_messages_replied / email_messages_sent * 100), 2) if email_messages_sent else 0.0
    email_click_rate = round((email_clicks / email_messages_sent * 100), 2) if email_messages_sent else 0.0

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
            "messages_sent": messages_sent + wa_messages_sent,
            "messages_replied": messages_replied,
            "responses": messages_replied,
            "response_rate": response_rate,
            "conversions": conversions,
            "conversion_rate": conversion_rate,
            "errors": errors,
            "rate_limit_warnings": 0,
        },
        "channels": {
            "linkedin": {
                "connections_sent": connections_sent,
                "connections_accepted": connections_accepted,
                "connection_accept_rate": connection_accept_rate,
                "messages_sent": li_messages_sent,
                "messages_replied": li_messages_replied,
                "response_rate": li_response_rate,
            },
            "whatsapp": {
                "messages_sent": wa_messages_sent,
                "messages_replied": wa_messages_replied,
                "response_rate": wa_response_rate,
            },
            "email": {
                "emails_sent": email_messages_sent,
                "emails_opened": email_opens,
                "emails_clicked": email_clicks,
                "emails_replied": email_messages_replied,
                "emails_bounced": email_bounces,
                "open_rate": email_open_rate,
                "click_rate": email_click_rate,
                "reply_rate": email_reply_rate,
            },
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
    leads_collection = get_mongodb_collection("leads")
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

        # Collect public_identifiers that need lead-name enrichment (missing or blank lead_name)
        pids_to_enrich: set[str] = set()
        for log in logs:
            details = log.get("details") or {}
            if not details.get("lead_name") and details.get("public_identifier"):
                pids_to_enrich.add(details["public_identifier"])

        # Batch-fetch names for those leads
        pid_to_name: Dict[str, str] = {}
        if pids_to_enrich and leads_collection is not None:
            for lead_doc in leads_collection.find(
                {"public_identifier": {"$in": list(pids_to_enrich)}},
                {"public_identifier": 1, "cached_profile": 1},
            ):
                pid = lead_doc.get("public_identifier", "")
                cp = lead_doc.get("cached_profile") or {}
                profile_inner = cp.get("profile", cp)
                first = profile_inner.get("firstName", "") or cp.get("first_name", "")
                last = profile_inner.get("lastName", "") or cp.get("last_name", "")
                name = f"{first} {last}".strip() or pid
                pid_to_name[pid] = name

        for log in logs:
            details = log.get("details") or {}
            if not details.get("lead_name") and details.get("public_identifier"):
                pid = details["public_identifier"]
                details = {**details, "lead_name": pid_to_name.get(pid, pid)}
            entries.append({
                "id": str(log.get("_id", "")),
                "source": "action",
                "type": log.get("action_type", ""),
                "status": log.get("status", "completed"),
                "error": log.get("error_message") or None,
                "durationMs": log.get("duration_ms"),
                "timestamp": (log["created_at"].isoformat() + "Z") if log.get("created_at") else "",
                "details": details if details else None,
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
                now_utc = datetime.now(timezone.utc)
                if scheduled_at.tzinfo is None:
                    scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
                delta = (scheduled_at - now_utc).total_seconds()
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


class LeadsImportResponse(BaseModel):
    imported: int
    updated: int
    skipped: int
    errors: List[str]


@router.post("/{campaign_id}/leads/import", response_model=LeadsImportResponse)
async def import_leads_with_column_map(
    campaign_id: str,
    file: bytes = __import__("fastapi").File(...),
    column_map: str = __import__("fastapi").Form("{}"),
    user_id: str = Depends(get_current_user),
):
    """Import leads from CSV with explicit column mapping.

    Accepts multipart/form-data with:
    - file: CSV file
    - column_map: JSON string mapping field names to CSV column headers

    Supported keys: linkedin_url, first_name, last_name, company, title,
    email, phone, company_domain.
    """
    import csv as csv_mod
    import io
    import json
    from datetime import datetime, timezone as _tz
    from uuid import uuid4

    campaign = models.Campaign.get(campaign_id)
    if not campaign or not campaign.has_access(user_id):
        raise HTTPException(status_code=404, detail="Campaign not found")

    try:
        col_map: Dict[str, str] = json.loads(column_map) if column_map else {}
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="column_map must be valid JSON")

    try:
        text = file.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = file.decode("latin-1")

    reader = csv_mod.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise HTTPException(status_code=400, detail="CSV has no header row")

    rows = list(reader)
    if len(rows) > 5000:
        raise HTTPException(status_code=400, detail="CSV exceeds 5000 row limit")

    leads_col = get_mongodb_collection("leads")
    deals_col = get_mongodb_collection("deals")
    if leads_col is None or deals_col is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    now = datetime.now(_tz.utc)
    imported = 0
    updated = 0
    skipped = 0
    errors: List[str] = []

    def _get(row: Dict[str, Any], field: str) -> str:
        col = col_map.get(field)
        if not col:
            return ""
        return (row.get(col) or "").strip()

    for i, row in enumerate(rows, start=2):
        linkedin_url = _get(row, "linkedin_url")
        email = _get(row, "email")

        if not linkedin_url and not email:
            errors.append(f"row {i}: no linkedin_url or email")
            skipped += 1
            continue

        first_name = _get(row, "first_name")
        last_name = _get(row, "last_name")
        full_name = f"{first_name} {last_name}".strip() or None
        company = _get(row, "company") or None
        phone = _get(row, "phone") or None

        public_identifier = ""
        if linkedin_url:
            parts = [p for p in linkedin_url.rstrip("/").split("/") if p]
            public_identifier = parts[-1] if parts else ""

        filter_q: dict = {}
        if linkedin_url and public_identifier:
            filter_q = {"public_identifier": public_identifier}
        elif email:
            filter_q = {"api_email": email}
        else:
            filter_q = {"linkedin_url": linkedin_url}

        try:
            existing_doc = leads_col.find_one(filter_q, {"_id": 1, "phone": 1, "api_email": 1})
            if existing_doc:
                actual_lead_id = str(existing_doc["_id"])
                set_fields: dict = {}
                if email and not existing_doc.get("api_email"):
                    set_fields["api_email"] = email
                    set_fields["email_source"] = "csv_import"
                if phone and not existing_doc.get("phone"):
                    set_fields["phone"] = phone
                    set_fields["phone_source"] = "csv_import"
                if set_fields:
                    leads_col.update_one({"_id": actual_lead_id}, {"$set": set_fields})
                # Count as updated regardless — even if no new data was written,
                # the deal link below may still be created for this lead.
                updated += 1
            else:
                new_id = str(uuid4())
                insert_doc: dict = {
                    "_id": new_id,
                    "linkedin_url": linkedin_url or None,
                    "public_identifier": public_identifier,
                    "full_name": full_name,
                    "user_id": user_id,
                    "disqualified": False,
                    "creation_date": now,
                }
                if email:
                    insert_doc["api_email"] = email
                    insert_doc["email_source"] = "csv_import"
                if phone:
                    insert_doc["phone"] = phone
                    insert_doc["phone_source"] = "csv_import"
                if company:
                    insert_doc["company"] = company
                leads_col.insert_one(insert_doc)
                actual_lead_id = new_id
                imported += 1

            existing_deal = deals_col.find_one(
                {"lead_id": actual_lead_id, "campaign_id": campaign_id},
                {"_id": 1},
            )
            if not existing_deal:
                from openoutreach.crm.models.deal import DealState as DS
                deals_col.insert_one({
                    "_id": str(uuid4()),
                    "lead_id": actual_lead_id,
                    "campaign_id": campaign_id,
                    "state": DS.DISCOVERED,
                    "user_id": user_id,
                    "creation_date": now,
                })
        except Exception as exc:
            errors.append(f"row {i}: {exc}")

    return LeadsImportResponse(
        imported=imported,
        updated=updated,
        skipped=skipped,
        errors=errors,
    )


@router.get("/{campaign_id}/coverage")
async def get_campaign_coverage(
    campaign_id: str,
    user_id: str = Depends(get_current_user),
):
    """Return per-channel lead coverage counts for a campaign."""
    campaign = models.Campaign.get(campaign_id)
    if not campaign or not campaign.has_access(user_id):
        raise HTTPException(status_code=404, detail="Campaign not found")

    leads_col = get_mongodb_collection("leads")
    deals_col = get_mongodb_collection("deals")
    if leads_col is None or deals_col is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    deal_docs = list(deals_col.find({"campaign_id": campaign_id}, {"lead_id": 1}))
    lead_ids = [d["lead_id"] for d in deal_docs]
    total = len(lead_ids)
    if total == 0:
        return {"total": 0, "channel_coverage": {
            "linkedin": {"count": 0, "pct": 0},
            "email": {"count": 0, "pct": 0},
            "whatsapp": {"count": 0, "pct": 0},
        }}

    lead_docs = list(leads_col.find(
        {"_id": {"$in": lead_ids}},
        {"linkedin_url": 1, "url": 1, "api_email": 1, "contact_info": 1, "phone": 1, "phone_on_whatsapp": 1},
    ))

    li = 0
    em = 0
    wa = 0
    for ld in lead_docs:
        if ld.get("linkedin_url") or ld.get("url"):
            li += 1
        has_email = bool(ld.get("api_email") or (
            isinstance(ld.get("contact_info"), dict) and ld["contact_info"].get("email")
        ))
        if has_email:
            em += 1
        if ld.get("phone") and ld.get("phone_on_whatsapp") is not False:
            wa += 1

    def pct(n: int) -> int:
        return round(n * 100 / total) if total else 0

    return {
        "total": total,
        "channel_coverage": {
            "linkedin": {"count": li, "pct": pct(li)},
            "email": {"count": em, "pct": pct(em)},
            "whatsapp": {"count": wa, "pct": pct(wa)},
        },
    }


class SequencePatch(BaseModel):
    steps: Optional[List[Dict[str, Any]]] = None
    edges: Optional[List[Dict[str, Any]]] = None
    active: Optional[bool] = None


def _validate_sequence_graph(steps: List[Dict[str, Any]], edges: List[Dict[str, Any]], *, require_launchable: bool = False) -> List[str]:
    """Validate and return human-readable graph errors before persisting."""
    errors: List[str] = []
    ids = [str(s.get("id", "")) for s in steps]
    known = set(ids)
    if len(ids) != len(set(ids)):
        errors.append("Step IDs must be unique.")
    valid_types = {"action", "wait", "condition", "end"}
    for s in steps:
        if not s.get("id") or s.get("type") not in valid_types:
            errors.append(f"Invalid step type or ID: {s.get('id', '<missing>')}.")
        data = s.get("data") or {}
        if s.get("type") == "action":
            if data.get("action") not in {"connect", "follow_up", "send_email", "send_whatsapp"}:
                errors.append(f"Action step {s.get('id')} has an invalid action.")
            expected = {"connect": "linkedin", "follow_up": "linkedin", "send_email": "email", "send_whatsapp": "whatsapp"}.get(cast(str, data.get("action")))
            if expected and data.get("channel") != expected:
                errors.append(f"Action step {s.get('id')} has an incompatible channel.")
        if s.get("type") == "wait":
            try:
                if float(data.get("wait_days", 0) or 0) < 0 or float(data.get("wait_hours", 0) or 0) < 0:
                    errors.append(f"Wait step {s.get('id')} cannot be negative.")
                if require_launchable and float(data.get("wait_days", 0) or 0) + float(data.get("wait_hours", 0) or 0) <= 0:
                    errors.append(f"Wait step {s.get('id')} must have a positive duration.")
            except (TypeError, ValueError):
                errors.append(f"Wait step {s.get('id')} has an invalid duration.")
    outgoing: Dict[str, List[Dict[str, Any]]] = {sid: [] for sid in known}
    incoming: Dict[str, int] = {sid: 0 for sid in known}
    edge_keys = set()
    for e in edges:
        source, target = cast(str, e.get("source")), cast(str, e.get("target"))
        if source not in known or target not in known or source == target:
            errors.append(f"Edge {e.get('id', '<missing>')} references an invalid node.")
            continue
        key = (source, target, (e.get("data") or {}).get("condition", "always"))
        if key in edge_keys:
            errors.append(f"Duplicate edge from {source} to {target}.")
        edge_keys.add(key)
        outgoing[source].append(e)
        incoming[target] += 1
    roots = [sid for sid, count in incoming.items() if count == 0]
    if steps and len(roots) != 1:
        errors.append("Sequence must have exactly one entry point.")
    if steps:
        reachable = set()
        stack = roots[:1]
        while stack:
            cur = stack.pop()
            if cur in reachable:
                continue
            reachable.add(cur)
            stack.extend(cast(str, e.get("target")) for e in outgoing.get(cur, []) if e.get("target"))
        if len(reachable) != len(known):
            errors.append("All steps must be reachable from the entry point.")
        visiting: set[str] = set()
        visited: set[str] = set()
        def visit(node: str) -> None:
            if node in visiting:
                errors.append("Sequence graph contains a cycle.")
                return
            if node in visited:
                return
            visiting.add(node)
            for child in outgoing.get(node, []):
                visit(cast(str, child.get("target")))
            visiting.remove(node)
            visited.add(node)
        for root in (roots or list(known)):
            visit(root)
    for s in steps:
        sid, typ = cast(str, s.get("id")), s.get("type")
        outs = outgoing.get(sid, [])
        if typ != "end" and not outs:
            errors.append(f"Step {sid} has no outgoing connection.")
        if typ == "condition":
            branches = {(e.get("data") or {}).get("condition") for e in outs}
            if branches != {"yes", "no"}:
                errors.append(f"Condition step {sid} must have exactly Yes and No paths.")
    if require_launchable:
        if not steps:
            errors.append("Sequence has no steps.")
        if not any(s.get("type") == "action" for s in steps):
            errors.append("Sequence needs at least one action step.")
        if not any(s.get("type") == "end" for s in steps):
            errors.append("Sequence needs an End step.")
        if sum(1 for s in steps if s.get("type") == "action" and (s.get("data") or {}).get("action") == "send_email") > 3:
            errors.append("A sequence supports at most three email actions.")
    return errors


@router.get("/{campaign_id}/sequence")
async def get_sequence(
    campaign_id: str,
    user_id: str = Depends(get_current_user),
):
    """Return the campaign's sequence steps, edges, active flag, and per-step coverage."""
    campaign = models.Campaign.get(campaign_id)
    if not campaign or not campaign.has_access(user_id):
        raise HTTPException(status_code=404, detail="Campaign not found")

    leads_col = get_mongodb_collection("leads")
    deals_col = get_mongodb_collection("deals")

    coverage_per_step: Dict[str, int] = {}
    if leads_col is not None and deals_col is not None:
        deal_docs = list(deals_col.find({"campaign_id": campaign_id}, {"lead_id": 1}))
        lead_ids = [d["lead_id"] for d in deal_docs]
        total = len(lead_ids)
        if total > 0:
            for step in campaign.sequence_steps:
                requires: List[str] = step.get("data", {}).get("requires", [])
                if not requires:
                    coverage_per_step[step["id"]] = 100
                    continue
                query: Dict[str, Any] = {"_id": {"$in": lead_ids}}
                if "api_email" in requires:
                    query["$or"] = [
                        {"api_email": {"$exists": True, "$nin": [None, ""]}},
                        {"contact_info.email": {"$exists": True, "$nin": [None, ""]}},
                    ]
                if "phone" in requires:
                    query["phone"] = {"$exists": True, "$nin": [None, ""]}
                count = leads_col.count_documents(query)
                coverage_per_step[step["id"]] = round(count * 100 / total)

    return {
        "steps": campaign.sequence_steps,
        "edges": campaign.sequence_edges,
        "active": campaign.sequence_active,
        "coverage_per_step": coverage_per_step,
    }


@router.get("/{campaign_id}/sequence/metrics")
async def get_sequence_metrics(campaign_id: str, user_id: str = Depends(get_current_user)):
    """Operational sequence health: per-step outcomes and stuck/error counts."""
    campaign = models.Campaign.get(campaign_id)
    if not campaign or not campaign.has_access(user_id):
        raise HTTPException(status_code=404, detail="Campaign not found")
    events = get_mongodb_collection("sequence_events")
    deals = get_mongodb_collection("deals")
    by_step: Dict[str, Dict[str, int]] = {}
    if events is not None:
        for row in events.find({"campaign_id": campaign_id}, {"step_id": 1, "event": 1, "reason": 1}):
            sid = str(row.get("step_id", "unknown"))
            bucket = by_step.setdefault(sid, {"task_created": 0, "skipped": 0, "failed": 0})
            key = row.get("event")
            if key in bucket:
                bucket[key] += 1
    stuck = 0
    errors = 0
    if deals is not None:
        stuck = deals.count_documents({"campaign_id": campaign_id, "sequence_position": {"$exists": True}, "sequence_done": {"$ne": True}, "sequence_error": {"$exists": True}})
        errors = deals.count_documents({"campaign_id": campaign_id, "sequence_error": {"$exists": True}})
    return {"campaign_id": campaign_id, "active": campaign.sequence_active, "by_step": by_step, "stuck_deals": stuck, "error_deals": errors}


@router.post("/{campaign_id}/sequence/preview")
async def preview_sequence(campaign_id: str, body: Dict[str, Any] = {}, user_id: str = Depends(get_current_user)):
    """Dry-run graph traversal for selected deals without creating tasks."""
    campaign = models.Campaign.get(campaign_id)
    if not campaign or not campaign.has_access(user_id):
        raise HTTPException(status_code=404, detail="Campaign not found")
    deals = get_mongodb_collection("deals")
    leads = get_mongodb_collection("leads")
    if deals is None or leads is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    wanted = [str(x) for x in (body.get("deal_ids") or [])][:25]
    query: Dict[str, Any] = {"campaign_id": campaign_id}
    if wanted:
        query["_id"] = {"$in": wanted}
    step_by_id = {s.get("id"): s for s in campaign.sequence_steps}
    results = []
    for deal_doc in deals.find(query, limit=25):
        current = deal_doc.get("sequence_position") or next((s.get("id") for s in campaign.sequence_steps if s.get("id") not in {e.get("target") for e in campaign.sequence_edges}), None)
        path: List[str] = []
        seen: set[str] = set()
        while current and current not in seen and len(path) < 100:
            seen.add(current)
            path.append(current)
            outs = [e for e in campaign.sequence_edges if e.get("source") == current]
            step = step_by_id.get(current) or {}
            if step.get("type") == "condition":
                branch = (step.get("data") or {}).get("condition", "always")
                wanted_branch = "yes" if branch in ("always", "replied") else "no"
                chosen = next((e for e in outs if (e.get("data") or {}).get("condition") == wanted_branch), None)
                current = chosen.get("target") if chosen else None
            else:
                current = outs[0].get("target") if outs else None
        results.append({"deal_id": str(deal_doc.get("_id")), "path": path, "labels": [(step_by_id.get(s) or {}).get("data", {}).get("label", s) for s in path]})
    return {"campaign_id": campaign_id, "dry_run": True, "results": results}


@router.patch("/{campaign_id}/sequence")
async def patch_sequence(
    campaign_id: str,
    body: SequencePatch,
    user_id: str = Depends(get_current_user),
):
    """Save sequence steps/edges and/or toggle the sequence active flag."""
    campaign = models.Campaign.get(campaign_id)
    if not campaign or not campaign.has_access(user_id):
        raise HTTPException(status_code=404, detail="Campaign not found")
    if campaign.user_id != user_id:
        raise HTTPException(status_code=403, detail="Only the campaign owner can edit or activate its sequence")
    if campaign.sequence_active and (body.steps is not None or body.edges is not None) and body.active is not False:
        raise HTTPException(status_code=409, detail="Deactivate the sequence before editing its graph; this protects in-progress deals from orphaned steps")

    col = get_mongodb_collection("campaigns")
    if col is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    update: Dict[str, Any] = {}
    candidate_steps = body.steps if body.steps is not None else (campaign.sequence_steps or [])
    candidate_edges = body.edges if body.edges is not None else (campaign.sequence_edges or [])
    graph_errors = _validate_sequence_graph(candidate_steps, candidate_edges, require_launchable=body.active is True)
    if graph_errors:
        raise HTTPException(status_code=422, detail=graph_errors)
    if body.steps is not None:
        update["sequence_steps"] = body.steps
    if body.edges is not None:
        update["sequence_edges"] = body.edges
    if body.active is not None:
        if body.active:
            # Validate before activating (graph validation above is canonical).
            steps_to_check = body.steps if body.steps is not None else (campaign.sequence_steps or [])
            edges_to_check = body.edges if body.edges is not None else (campaign.sequence_edges or [])

            edge_targets = {e["target"] for e in edges_to_check}
            edge_sources = {e["source"] for e in edges_to_check}
            all_in_edges = edge_targets | edge_sources

            action_steps = [s for s in steps_to_check if s.get("type") == "action"]
            end_steps = [s for s in steps_to_check if s.get("type") == "end"]

            # Nodes that appear in neither source nor target of any edge
            disconnected = [
                (s.get("data") or {}).get("label") or s["id"]
                for s in steps_to_check
                if s["id"] not in all_in_edges and len(steps_to_check) > 1
            ]

            # Non-end nodes with no outgoing edge
            no_outgoing = [
                (s.get("data") or {}).get("label") or s["id"]
                for s in steps_to_check
                if s.get("type") != "end" and s["id"] not in edge_sources
            ]

            errors: List[str] = []
            if not steps_to_check:
                errors.append("Sequence has no steps.")
            if not action_steps:
                errors.append("Sequence must have at least one action step.")
            if not end_steps:
                errors.append("Sequence must have at least one End node.")
            if disconnected:
                errors.append(f"Disconnected nodes: {', '.join(disconnected)}.")
            if no_outgoing:
                errors.append(f"Nodes with no outgoing connection: {', '.join(no_outgoing)}.")

            # Each condition node must have both yes and no outgoing branches.
            # Edges from condition nodes store data.condition = "yes" or "no"
            # (not sourceHandle — that is only a React Flow runtime property).
            condition_steps = [s for s in steps_to_check if s.get("type") == "condition"]
            for cs in condition_steps:
                branches = {
                    (e.get("data") or {}).get("condition")
                    for e in edges_to_check
                    if e["source"] == cs["id"]
                }
                if "yes" not in branches or "no" not in branches:
                    label = (cs.get("data") or {}).get("label") or cs["id"]
                    errors.append(f'Branch node "{label}" must have both Yes and No paths connected.')

            if errors:
                raise HTTPException(status_code=422, detail=errors)
            # Re-check runtime channel readiness at activation time; channels
            # may have been added long after campaign creation.
            actions = [s.get("data") or {} for s in steps_to_check if s.get("type") == "action"]
            channels = {a.get("channel") for a in actions}
            readiness_errors: List[str] = []
            if channels & {"linkedin"} and not campaign.linkedin_profile_id:
                readiness_errors.append("LinkedIn steps require a LinkedIn profile.")
            if "email" in channels:
                mailboxes = get_mongodb_collection("mailboxes")
                if mailboxes is None or mailboxes.count_documents({"user_id": user_id, "paused": {"$ne": True}}) == 0:
                    readiness_errors.append("Email steps require an active mailbox.")
            if "whatsapp" in channels:
                wa_col = get_mongodb_collection("whatsapp_profiles")
                wa_settings = (campaign.channel_settings or {}).get("whatsapp", {})
                wa_doc = wa_col.find_one({"_id": campaign.whatsapp_profile_id, "user_id": user_id}) if wa_col is not None and campaign.whatsapp_profile_id else None
                if not wa_doc or wa_doc.get("status") not in ("connected", "active"):
                    readiness_errors.append("WhatsApp steps require a connected WhatsApp profile.")
                if not isinstance(wa_settings, dict) or not str(wa_settings.get("message_template", "")).strip():
                    readiness_errors.append("WhatsApp steps require a message template.")
            if readiness_errors:
                raise HTTPException(status_code=422, detail=readiness_errors)
            if any((s.get("data") or {}).get("condition") == "no_open" for s in steps_to_check) and not os.getenv("TRACKING_BASE_URL"):
                raise HTTPException(status_code=422, detail="A no-open condition requires TRACKING_BASE_URL to be configured")
        update["sequence_active"] = body.active

    if update:
        col.update_one({"_id": campaign_id}, {"$set": update})

    # Prevent stale work from crossing the sequence lifecycle boundary.
    if body.active is False:
        tasks_col = get_mongodb_collection("tasks")
        if tasks_col is not None:
            tasks_col.update_many(
                {"payload.campaign_id": campaign_id, "status": {"$in": ["pending"]}, "payload.step_id": {"$exists": True}},
                {"$set": {"status": "cancelled", "cancel_reason": "sequence_deactivated"}},
            )
    elif body.active is True:
        # Supersede legacy planner tasks so activation cannot double-send.
        tasks_col = get_mongodb_collection("tasks")
        if tasks_col is not None:
            tasks_col.update_many(
                {"payload.campaign_id": campaign_id, "status": "pending", "payload.step_id": {"$exists": False}},
                {"$set": {"status": "cancelled", "cancel_reason": "sequence_activated"}},
            )

    return {"ok": True}
