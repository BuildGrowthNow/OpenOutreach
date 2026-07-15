"""
Leads Router - Multi-tenant lead management endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from openoutreach.mongodb import models
from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.api_v2.dependencies_v2 import get_current_user

router = APIRouter()


class LeadResponse(BaseModel):
    id: str
    public_identifier: str
    url: str
    full_name: Optional[str] = None
    headline: Optional[str] = None
    location: Optional[str] = None
    disqualified: bool = False
    created_at: Optional[datetime] = None


class LeadDetailResponse(LeadResponse):
    """Extended lead response with full profile data"""
    cached_profile: Optional[dict] = None
    contact_info: Optional[dict] = None
    api_email: Optional[str] = None


class DealResponse(BaseModel):
    id: str
    lead_id: str
    campaign_id: str
    state: str
    outcome: Optional[str] = None
    reason: Optional[str] = None
    creation_date: Optional[datetime] = None


@router.get("/", response_model=dict)
async def list_leads(
    user_id: str = Depends(get_current_user),
    campaign_id: Optional[str] = None,
    state: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    List leads accessible to the user.

    Filters:
    - campaign_id: Only leads in campaigns user has access to
    - state: Filter by deal state (Discovered, Qualified, etc.)
    """
    collection = get_mongodb_collection("deals")
    if collection is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    # Build query - get deals from campaigns user has access to
    query = {}

    if campaign_id:
        # Verify campaign access
        campaign = models.Campaign.get(campaign_id)
        if not campaign or not campaign.has_access(user_id):
            raise HTTPException(status_code=403, detail="Campaign access denied")
        query["campaign_id"] = campaign_id
    else:
        # Get all campaigns user has access to
        campaigns_collection = get_mongodb_collection("campaigns")
        if campaigns_collection is None:
            raise HTTPException(status_code=503, detail="Database unavailable")
        accessible_campaigns = list(campaigns_collection.find({
            "$or": [
                {"user_id": user_id},
                {"team_member_ids": user_id}
            ]
        }, {"_id": 1}))
        campaign_ids = [str(c["_id"]) for c in accessible_campaigns]
        query["campaign_id"] = {"$in": campaign_ids}

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
        raise HTTPException(status_code=503, detail="Database unavailable")
    leads_data = {str(l["_id"]): l for l in leads_collection.find({"_id": {"$in": lead_ids}})}

    # Build response
    results = []
    for deal in deals:
        lead_data = leads_data.get(str(deal["lead_id"]))
        if lead_data:
            results.append({
                "lead": LeadResponse(
                    id=str(lead_data["_id"]),
                    public_identifier=lead_data.get("public_identifier", ""),
                    url=lead_data.get("url", ""),
                    full_name=lead_data.get("full_name"),
                    headline=lead_data.get("headline"),
                    location=lead_data.get("location"),
                    disqualified=lead_data.get("disqualified", False),
                    created_at=lead_data.get("creation_date"),
                ),
                "deal": DealResponse(
                    id=str(deal["_id"]),
                    lead_id=str(deal["lead_id"]),
                    campaign_id=str(deal["campaign_id"]),
                    state=deal.get("state", "Discovered"),
                    outcome=deal.get("outcome"),
                    reason=deal.get("reason"),
                    creation_date=deal.get("creation_date"),
                )
            })

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "results": results,
    }


@router.get("/{lead_id}", response_model=LeadDetailResponse)
async def get_lead(
    lead_id: str,
    user_id: str = Depends(get_current_user),
):
    """
    Get a single lead by ID.
    User must have access via at least one campaign.
    """
    # Check if user has access to this lead via any campaign
    deals_collection = get_mongodb_collection("deals")
    if deals_collection is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    deals = list(deals_collection.find({"lead_id": lead_id}))

    if not deals:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Verify user has access to at least one campaign
    has_access = False
    for deal in deals:
        campaign = models.Campaign.get(str(deal["campaign_id"]))
        if campaign and campaign.has_access(user_id):
            has_access = True
            break

    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get lead
    leads_collection = get_mongodb_collection("leads")
    if leads_collection is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    lead_data = leads_collection.find_one({"_id": lead_id})

    if not lead_data:
        raise HTTPException(status_code=404, detail="Lead not found")

    return LeadDetailResponse(
        id=str(lead_data["_id"]),
        public_identifier=lead_data.get("public_identifier", ""),
        url=lead_data.get("url", ""),
        full_name=lead_data.get("full_name"),
        headline=lead_data.get("headline"),
        location=lead_data.get("location"),
        disqualified=lead_data.get("disqualified", False),
        created_at=lead_data.get("creation_date"),
        cached_profile=lead_data.get("cached_profile"),
        contact_info=lead_data.get("contact_info"),
        api_email=lead_data.get("api_email"),
    )


@router.get("/campaigns/{campaign_id}/leads", response_model=dict)
async def list_campaign_leads(
    campaign_id: str,
    user_id: str = Depends(get_current_user),
    state: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List leads for a specific campaign (owner OR team member can access)."""
    # Verify campaign access
    campaign = models.Campaign.get(campaign_id)
    if not campaign or not campaign.has_access(user_id):
        raise HTTPException(status_code=403, detail="Campaign access denied")

    # Use the main list endpoint logic
    return await list_leads(user_id=user_id, campaign_id=campaign_id, state=state, limit=limit, offset=offset)
