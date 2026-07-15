"""
Campaigns Router - FastAPI implementation with multi-tenant support

Provides endpoints for managing campaigns with proper user ownership
and team access control.
"""

import logging
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status, Body
from pydantic import BaseModel

from openoutreach.api_v2.dependencies_v2 import get_current_user, get_campaign_with_access
from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.mongodb import models

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

    class Config:
        json_schema_extra = {
            "example": {
                "name": "SaaS Founders Outreach",
                "product_pitch": "We help SaaS founders automate their lead generation",
                "campaign_objective": "Book 10 discovery calls per week",
                "linkedin_profile_id": "profile_123",
                "booking_link": "https://calendly.com/user/discovery",
                "velocity": 20,
                "team_member_ids": ["user_456"]
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
    team_member_ids: Optional[List[str]] = None


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
    user_id: str
    team_member_ids: List[str]
    created_at: str


class CampaignListResponse(BaseModel):
    """Response schema for campaign list."""
    campaigns: List[CampaignResponse]
    count: int


# Endpoints

@router.get("/", response_model=CampaignListResponse)
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

        campaigns = []
        for doc in cursor:
            campaigns.append(CampaignResponse(
                id=str(doc.get("_id")),
                name=doc.get("name", ""),
                product_pitch=doc.get("product_pitch", ""),
                campaign_objective=doc.get("campaign_objective", ""),
                linkedin_profile_id=doc.get("linkedin_profile_id"),
                booking_link=doc.get("booking_link", ""),
                velocity=doc.get("velocity", 20),
                is_paused=doc.get("is_paused", False),
                user_id=doc.get("user_id", ""),
                team_member_ids=doc.get("team_member_ids", []),
                created_at=doc.get("created_at").isoformat() if doc.get("created_at") else "",
            ))

        count = collection.count_documents(query)

        return CampaignListResponse(campaigns=campaigns, count=count)

    except Exception as e:
        logger.exception("Failed to list campaigns")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve campaigns: {str(e)}"
        )


@router.post("/", response_model=CampaignResponse, status_code=201)
async def create_campaign(
    data: CampaignCreate,
    user_id: str = Depends(get_current_user),
):
    """
    Create a new campaign.

    Multi-tenant: user must own the specified LinkedIn profile.
    Validates profile ownership and team member existence.
    """
    from openoutreach.linkedin.models import LinkedInProfile

    profiles_collection = get_mongodb_collection("linkedin_profiles")
    campaigns_collection = get_mongodb_collection("campaigns")

    if campaigns_collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Campaigns database unavailable"
        )

    try:
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
            user_id=campaign.user_id,
            team_member_ids=campaign.team_member_ids,
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
        user_id=campaign.user_id,
        team_member_ids=campaign.team_member_ids,
        created_at=campaign.created_at.isoformat() if campaign.created_at else "",
    )


@router.put("/{campaign_id}", response_model=CampaignResponse)
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
        if data.is_paused is not None:
            updates["is_paused"] = data.is_paused
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
            user_id=updated_campaign.user_id,
            team_member_ids=updated_campaign.team_member_ids,
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
