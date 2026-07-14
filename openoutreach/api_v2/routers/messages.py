"""
Messages Router - Multi-tenant chat message management
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from openoutreach.mongodb import models
from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.api_v2.dependencies import get_current_user

router = APIRouter()


class MessageResponse(BaseModel):
    id: str
    deal_id: str
    campaign_id: str
    sender_name: Optional[str] = None
    content: str
    is_outgoing: bool
    creation_date: Optional[datetime] = None
    event_urn: Optional[str] = None


class MessageCreate(BaseModel):
    deal_id: str
    content: str


@router.get("/", response_model=dict)
async def list_messages(
    user_id: str = Depends(get_current_user),
    campaign_id: Optional[str] = None,
    deal_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    List messages accessible to the user.

    Filters:
    - campaign_id: Messages from campaigns user has access to
    - deal_id: Messages for a specific deal
    """
    collection = get_mongodb_collection("chat_messages")
    if not collection:
        raise HTTPException(status_code=503, detail="Database unavailable")

    # Build query
    query = {}

    if deal_id:
        # Verify deal access via campaign
        deal = models.Deal.get(deal_id)
        if not deal:
            raise HTTPException(status_code=404, detail="Deal not found")

        campaign = models.Campaign.get(deal.campaign_id)
        if not campaign or not campaign.has_access(user_id):
            raise HTTPException(status_code=403, detail="Access denied")

        query["deal_id"] = deal_id

    elif campaign_id:
        # Verify campaign access
        campaign = models.Campaign.get(campaign_id)
        if not campaign or not campaign.has_access(user_id):
            raise HTTPException(status_code=403, detail="Campaign access denied")

        # Get all deals for this campaign
        deals_collection = get_mongodb_collection("deals")
        deals = list(deals_collection.find({"campaign_id": campaign_id}, {"_id": 1}))
        deal_ids = [str(d["_id"]) for d in deals]
        query["deal_id"] = {"$in": deal_ids}

    else:
        # Get all campaigns user has access to
        campaigns_collection = get_mongodb_collection("campaigns")
        accessible_campaigns = list(campaigns_collection.find({
            "$or": [
                {"user_id": user_id},
                {"team_member_ids": user_id}
            ]
        }, {"_id": 1}))
        campaign_ids = [str(c["_id"]) for c in accessible_campaigns]

        # Get all deals for accessible campaigns
        deals_collection = get_mongodb_collection("deals")
        deals = list(deals_collection.find({"campaign_id": {"$in": campaign_ids}}, {"_id": 1}))
        deal_ids = [str(d["_id"]) for d in deals]
        query["deal_id"] = {"$in": deal_ids}

    # Get messages
    total = collection.count_documents(query)
    messages = list(collection.find(query).skip(offset).limit(limit).sort("creation_date", -1))

    # Get campaign IDs for enrichment
    deal_ids = list(set(str(m["deal_id"]) for m in messages))
    deals_collection = get_mongodb_collection("deals")
    deals_data = {str(d["_id"]): d for d in deals_collection.find({"_id": {"$in": deal_ids}})}

    results = []
    for msg in messages:
        deal_data = deals_data.get(str(msg["deal_id"]))
        results.append(MessageResponse(
            id=str(msg["_id"]),
            deal_id=str(msg["deal_id"]),
            campaign_id=str(deal_data["campaign_id"]) if deal_data else "",
            sender_name=msg.get("sender_name"),
            content=msg.get("content", ""),
            is_outgoing=msg.get("is_outgoing", False),
            creation_date=msg.get("creation_date"),
            event_urn=msg.get("event_urn"),
        ))

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "results": results,
    }


@router.get("/{message_id}", response_model=MessageResponse)
async def get_message(
    message_id: str,
    user_id: str = Depends(get_current_user),
):
    """Get a single message by ID (access via campaign)."""
    collection = get_mongodb_collection("chat_messages")
    if not collection:
        raise HTTPException(status_code=503, detail="Database unavailable")

    msg = collection.find_one({"_id": message_id})
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    # Verify access via deal → campaign
    deal = models.Deal.get(str(msg["deal_id"]))
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    campaign = models.Campaign.get(deal.campaign_id)
    if not campaign or not campaign.has_access(user_id):
        raise HTTPException(status_code=403, detail="Access denied")

    return MessageResponse(
        id=str(msg["_id"]),
        deal_id=str(msg["deal_id"]),
        campaign_id=deal.campaign_id,
        sender_name=msg.get("sender_name"),
        content=msg.get("content", ""),
        is_outgoing=msg.get("is_outgoing", False),
        creation_date=msg.get("creation_date"),
        event_urn=msg.get("event_urn"),
    )


@router.get("/deals/{deal_id}/messages", response_model=dict)
async def list_deal_messages(
    deal_id: str,
    user_id: str = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List messages for a specific deal (thread view)."""
    return await list_messages(user_id=user_id, deal_id=deal_id, limit=limit, offset=offset)
