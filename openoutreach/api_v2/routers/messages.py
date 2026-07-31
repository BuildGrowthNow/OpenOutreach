"""
Messages Router - Multi-tenant chat message management
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime, timezone

from openoutreach.mongodb import models
from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.api_v2.dependencies_v2 import get_current_user

router = APIRouter()


class MessageResponse(BaseModel):
    id: str
    dealId: str
    leadId: Optional[str] = None
    campaignId: str
    campaignName: Optional[str] = None
    senderName: Optional[str] = None
    content: str
    isOutgoing: bool
    creationDate: Optional[datetime] = None
    recipientName: Optional[str] = None
    recipientUrl: Optional[str] = None
    sender: str = "me"

    @field_validator("creationDate", mode="before")
    @classmethod
    def ensure_utc(cls, v):
        if isinstance(v, datetime) and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v


def _extract_lead_name(lead_doc: dict) -> Optional[str]:
    cp = lead_doc.get("cached_profile") or {}
    profile_inner = cp.get("profile", cp)
    first = profile_inner.get("firstName", "") or cp.get("first_name", "")
    last = profile_inner.get("lastName", "") or cp.get("last_name", "")
    return lead_doc.get("full_name") or (f"{first} {last}".strip() or None)


class MessageCreate(BaseModel):
    deal_id: str
    content: str


@router.get("", response_model=dict)
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
    if collection is None:
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
        if deals_collection is None:
            raise HTTPException(status_code=503, detail="Database unavailable")
        deals = list(deals_collection.find({"campaign_id": campaign_id}, {"_id": 1}))
        deal_ids = [str(d["_id"]) for d in deals]
        query["deal_id"] = {"$in": deal_ids}

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

        # Get all deals for accessible campaigns
        deals_collection = get_mongodb_collection("deals")
        if deals_collection is None:
            raise HTTPException(status_code=503, detail="Database unavailable")
        deals = list(deals_collection.find({"campaign_id": {"$in": campaign_ids}}, {"_id": 1}))
        deal_ids = [str(d["_id"]) for d in deals]
        query["deal_id"] = {"$in": deal_ids}

    # Get messages
    total = collection.count_documents(query)
    messages = list(collection.find(query).skip(offset).limit(limit).sort("creation_date", -1))

    # Enrich messages with deal → lead name + campaign name
    msg_deal_ids = list(set(str(m["deal_id"]) for m in messages))
    deals_collection = get_mongodb_collection("deals")
    if deals_collection is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    deals_data = {str(d["_id"]): d for d in deals_collection.find({"_id": {"$in": msg_deal_ids}})}

    lead_ids = list(set(str(d["lead_id"]) for d in deals_data.values() if d.get("lead_id")))
    leads_collection = get_mongodb_collection("leads")
    leads_map: dict = {}
    if leads_collection is not None and lead_ids:
        leads_map = {str(d["_id"]): d for d in leads_collection.find({"_id": {"$in": lead_ids}})}

    enrich_campaign_ids = list(set(str(d["campaign_id"]) for d in deals_data.values() if d.get("campaign_id")))
    campaigns_collection2 = get_mongodb_collection("campaigns")
    campaigns_map: dict = {}
    if campaigns_collection2 is not None and enrich_campaign_ids:
        campaigns_map = {
            str(c["_id"]): c.get("name", "")
            for c in campaigns_collection2.find({"_id": {"$in": enrich_campaign_ids}}, {"_id": 1, "name": 1})
        }

    results = []
    for msg in messages:
        deal_data = deals_data.get(str(msg["deal_id"]))
        lead_id = str(deal_data["lead_id"]) if deal_data and deal_data.get("lead_id") else None
        campaign_id_str = str(deal_data["campaign_id"]) if deal_data else ""
        lead_doc = leads_map.get(lead_id) if lead_id else None
        lead_name = _extract_lead_name(lead_doc) if lead_doc else None
        campaign_name = campaigns_map.get(campaign_id_str) if campaign_id_str else None
        is_outgoing = msg.get("is_outgoing", False)
        results.append(MessageResponse(
            id=str(msg["_id"]),
            dealId=str(msg["deal_id"]),
            leadId=lead_id,
            campaignId=campaign_id_str,
            campaignName=campaign_name,
            senderName=msg.get("sender_name"),
            content=msg.get("content", ""),
            isOutgoing=is_outgoing,
            creationDate=msg.get("creation_date"),
            sender="me" if is_outgoing else "them",
            recipientName=lead_name or msg.get("sender_name") or "",
            recipientUrl=lead_doc.get("linkedin_url", "") if lead_doc else "",
        ))

    return {
        "data": results,
        "pagination": {
            "page": (offset // limit) + 1,
            "limit": limit,
            "total": total,
            "total_pages": max(1, (total + limit - 1) // limit),
        },
    }


@router.get("/stats", response_model=dict)
async def get_message_stats(
    user_id: str = Depends(get_current_user),
    campaign_id: Optional[str] = None,
):
    """
    Return true message totals for the stat cards on the Messages page.
    Counts across all accessible messages, not just the current page.
    """
    collection = get_mongodb_collection("chat_messages")
    if collection is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    # Resolve accessible deal_ids (same scoping logic as list_messages)
    if campaign_id:
        campaign = models.Campaign.get(campaign_id)
        if not campaign or not campaign.has_access(user_id):
            raise HTTPException(status_code=403, detail="Campaign access denied")
        deals_collection = get_mongodb_collection("deals")
        if deals_collection is None:
            raise HTTPException(status_code=503, detail="Database unavailable")
        deals = list(deals_collection.find({"campaign_id": campaign_id}, {"_id": 1}))
        deal_ids = [str(d["_id"]) for d in deals]
    else:
        campaigns_collection = get_mongodb_collection("campaigns")
        if campaigns_collection is None:
            raise HTTPException(status_code=503, detail="Database unavailable")
        accessible = list(campaigns_collection.find(
            {"$or": [{"user_id": user_id}, {"team_member_ids": user_id}]},
            {"_id": 1},
        ))
        accessible_campaign_ids = [str(c["_id"]) for c in accessible]
        deals_collection = get_mongodb_collection("deals")
        if deals_collection is None:
            raise HTTPException(status_code=503, detail="Database unavailable")
        deals = list(deals_collection.find(
            {"campaign_id": {"$in": accessible_campaign_ids}}, {"_id": 1, "campaign_id": 1}
        ))
        deal_ids = [str(d["_id"]) for d in deals]
        # Build campaign-id set for activeCampaigns count
        deal_campaign_ids = {str(d["campaign_id"]) for d in deals if d.get("campaign_id")}

    query: dict = {"deal_id": {"$in": deal_ids}}
    total_sent = collection.count_documents({**query, "is_outgoing": True})
    total_received = collection.count_documents({**query, "is_outgoing": False})
    # distinct deals that have at least one reply
    replied_deal_ids = collection.distinct("deal_id", {**query, "is_outgoing": False})
    response_rate = round((len(replied_deal_ids) / max(total_sent, 1)) * 100) if total_sent else 0

    if campaign_id:
        active_campaigns = 1
    else:
        # campaigns that have at least one message
        msg_deal_ids = collection.distinct("deal_id", query)
        if deals_collection is not None and msg_deal_ids:
            active_deal_campaigns = {
                str(d["campaign_id"])
                for d in deals_collection.find({"_id": {"$in": msg_deal_ids}}, {"campaign_id": 1})
                if d.get("campaign_id")
            }
            active_campaigns = len(active_deal_campaigns)
        else:
            active_campaigns = 0

    return {
        "totalSent": total_sent,
        "totalReceived": total_received,
        "responseRate": response_rate,
        "activeCampaigns": active_campaigns,
    }


@router.get("/{message_id}", response_model=MessageResponse)
async def get_message(
    message_id: str,
    user_id: str = Depends(get_current_user),
):
    """Get a single message by ID (access via campaign)."""
    collection = get_mongodb_collection("chat_messages")
    if collection is None:
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

    leads_col = get_mongodb_collection("leads")
    lead_doc = leads_col.find_one({"_id": deal.lead_id}) if leads_col is not None and deal.lead_id else None
    lead_name = _extract_lead_name(lead_doc) if lead_doc else None
    is_outgoing = msg.get("is_outgoing", False)
    return MessageResponse(
        id=str(msg["_id"]),
        dealId=str(msg["deal_id"]),
        leadId=deal.lead_id if deal else None,
        campaignId=deal.campaign_id,
        campaignName=campaign.name if campaign else None,
        senderName=msg.get("sender_name"),
        content=msg.get("content", ""),
        isOutgoing=is_outgoing,
        creationDate=msg.get("creation_date"),
        sender="me" if is_outgoing else "them",
        recipientName=lead_name or msg.get("sender_name") or "",
        recipientUrl=lead_doc.get("linkedin_url", "") if lead_doc else "",
    )


@router.get("/deals/{deal_id}/messages", response_model=dict)
async def list_deal_messages(
    deal_id: str,
    sync: bool = Query(True, description="Sync messages from LinkedIn before returning"),
    user_id: str = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List messages for a specific deal (thread view).

    By default, syncs messages from LinkedIn before returning (sync=true).
    This ensures users see real-time messages instead of stale data.
    Set sync=false to skip sync and just read from DB (for polling/background).
    """
    # Verify deal access
    deal = models.Deal.get(deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    campaign = models.Campaign.get(deal.campaign_id)
    if not campaign or not campaign.has_access(user_id):
        raise HTTPException(status_code=403, detail="Access denied")

    # Sync messages from LinkedIn if requested
    if sync:
        try:
            from openoutreach.linkedin.db.chat import sync_conversation
            from openoutreach.linkedin.browser.session import AccountSession
            from openoutreach.mongodb.models import Lead
            from openoutreach.linkedin.models import LinkedInProfile

            lead = Lead.get(deal.lead_id)
            if lead and lead.public_identifier and campaign.linkedin_profile_id:
                # Load the LinkedIn profile
                linkedin_profile = LinkedInProfile.objects.get(_id=campaign.linkedin_profile_id)
                if linkedin_profile:
                    # Create minimal session for sync
                    session = AccountSession(linkedin_profile)
                    session.campaign = campaign
                    sync_conversation(session, lead.public_identifier)
        except Exception as e:
            # Log but don't fail - just return stale data
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Message sync failed for deal {deal_id}: {e}")

    return await list_messages(user_id=user_id, deal_id=deal_id, limit=limit, offset=offset)
