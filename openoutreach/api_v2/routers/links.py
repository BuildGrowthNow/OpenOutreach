"""Campaign-scoped tracked-link assets and real click analytics."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ConfigDict

from openoutreach.api_v2.dependencies_v2 import get_current_user
from openoutreach.api_v2.schemas.link import LinkCreate, LinkUpdate
from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.mongodb.models import Campaign, TrackedLink

router = APIRouter(tags=["Links"])


class LinkCreateRequest(LinkCreate):
    model_config = ConfigDict(extra="forbid")
    campaign_id: Optional[str] = None


def _campaign_or_404(campaign_id: str, user_id: str) -> Campaign:
    campaign = Campaign.get(campaign_id)
    if not campaign or not campaign.has_access(user_id):
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


def _response(link: TrackedLink) -> dict:
    default_utm = link.default_utm or {}
    data = {
        "id": str(link._id), "user_id": str(link.user_id or ""), "campaign_id": str(link.campaign_id or ""),
        "key": link.key, "name": link.name, "destination_url": link.destination_url,
        "is_active": link.is_active, "default_utm": default_utm,
        "utm_source": default_utm.get("source") or default_utm.get("utm_source", ""),
        "utm_medium": default_utm.get("medium") or default_utm.get("utm_medium", ""),
        "utm_campaign": default_utm.get("campaign") or default_utm.get("utm_campaign", ""),
        "utm_term": default_utm.get("term") or default_utm.get("utm_term", ""),
        "utm_content": default_utm.get("content") or default_utm.get("utm_content", ""),
        "total_clicks": link.total_clicks, "unique_clicks": link.unique_clicks,
        "created_at": link.created_at, "updated_at": link.updated_at,
        "last_clicked_at": link.last_clicked_at,
        # Read-only aliases keep existing list components compatible during rollout.
        "original_url": link.destination_url, "short_code": link.short_code,
    }
    return data


def _find_link(link_id: str, campaign_id: str, user_id: str) -> TrackedLink:
    campaign = _campaign_or_404(campaign_id, user_id)
    links = get_mongodb_collection("tracked_links")
    doc = links.find_one({"_id": link_id, "campaign_id": campaign_id, "user_id": campaign.user_id}) if links is not None else None
    if not doc:
        raise HTTPException(status_code=404, detail="Link not found")
    return TrackedLink.from_dict(doc)


def _save_link(request: LinkCreateRequest, campaign_id: str, user_id: str) -> dict:
    campaign = _campaign_or_404(campaign_id, user_id)
    links = get_mongodb_collection("tracked_links")
    if links is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    owner_id = campaign.user_id
    if links.find_one({"campaign_id": campaign_id, "key": request.key, "user_id": owner_id}):
        raise HTTPException(status_code=409, detail="A link with this key already exists in the campaign")
    now = datetime.now(timezone.utc)
    link = TrackedLink(
        _id=str(uuid4()), campaign_id=campaign_id, user_id=owner_id, key=request.key,
        name=request.name, destination_url=request.destination_url, original_url=request.destination_url,
        short_code=str(uuid4()).replace("-", "")[:12], is_active=request.is_active,
        default_utm=request.default_utm, created_at=now, updated_at=now,
    )
    link.save()
    return _response(link)


@router.get("/links")
@router.get("/links/")
async def list_links(campaign_id: Optional[str] = Query(None), user_id: str = Depends(get_current_user)):
    if campaign_id:
        _campaign_or_404(campaign_id, user_id)
    collection = get_mongodb_collection("tracked_links")
    if collection is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    query = {"user_id": user_id}
    if campaign_id:
        query["campaign_id"] = campaign_id
        query.pop("user_id", None)
    data = [_response(TrackedLink.from_dict(doc)) for doc in collection.find(query).sort("created_at", -1)]
    return {"data": data, "count": len(data)}


@router.post("/links", status_code=status.HTTP_201_CREATED)
async def create_link(request: LinkCreateRequest, user_id: str = Depends(get_current_user)):
    if not request.campaign_id:
        raise HTTPException(status_code=422, detail="campaign_id is required")
    return _save_link(request, request.campaign_id, user_id)


@router.get("/campaigns/{campaign_id}/links")
async def list_campaign_links(campaign_id: str, user_id: str = Depends(get_current_user)):
    return await list_links(campaign_id, user_id)


@router.post("/campaigns/{campaign_id}/links", status_code=status.HTTP_201_CREATED)
async def create_campaign_link(campaign_id: str, request: LinkCreate, user_id: str = Depends(get_current_user)):
    return _save_link(LinkCreateRequest(**request.model_dump(), campaign_id=campaign_id), campaign_id, user_id)


@router.get("/campaigns/{campaign_id}/links/{link_id}")
async def get_campaign_link(campaign_id: str, link_id: str, user_id: str = Depends(get_current_user)):
    return _response(_find_link(link_id, campaign_id, user_id))


@router.patch("/campaigns/{campaign_id}/links/{link_id}")
async def update_campaign_link(campaign_id: str, link_id: str, request: LinkUpdate, user_id: str = Depends(get_current_user)):
    link = _find_link(link_id, campaign_id, user_id)
    updates = request.model_dump(exclude_unset=True)
    if "key" in updates:
        links = get_mongodb_collection("tracked_links")
        if links is not None and links.find_one({"campaign_id": campaign_id, "user_id": link.user_id, "key": updates["key"], "_id": {"$ne": link_id}}):
            raise HTTPException(status_code=409, detail="A link with this key already exists in the campaign")
    for key, value in updates.items():
        if key == "destination_url":
            link.destination_url = link.original_url = value
        else:
            setattr(link, key, value)
    link.save()
    return _response(link)


@router.delete("/campaigns/{campaign_id}/links/{link_id}")
async def delete_campaign_link(campaign_id: str, link_id: str, user_id: str = Depends(get_current_user)):
    link = _find_link(link_id, campaign_id, user_id)
    campaigns = get_mongodb_collection("campaigns")
    if link.is_active and campaigns is not None and campaigns.find_one({
        "_id": campaign_id, "sequence_active": True,
        "sequence_steps": {"$elemMatch": {"$or": [{"data.message.link_refs": link.key}, {"data.link_refs": link.key}, {"data.link_key": link.key}]}},
    }):
        raise HTTPException(status_code=409, detail="An active sequence references this link; deactivate it first")
    links = get_mongodb_collection("tracked_links")
    if links is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    # Keep historical click attribution; deactivation is the safe delete operation.
    links.update_one({"_id": link_id, "campaign_id": campaign_id, "user_id": link.user_id}, {"$set": {"is_active": False, "updated_at": datetime.now(timezone.utc)}})
    return {"status": "deactivated", "id": link_id}


@router.get("/campaigns/{campaign_id}/links/{link_id}/analytics")
async def campaign_link_analytics(campaign_id: str, link_id: str, user_id: str = Depends(get_current_user)):
    link = _find_link(link_id, campaign_id, user_id)
    events = get_mongodb_collection("tracking_events")
    query = {"tracked_link_id": link_id, "campaign_id": campaign_id, "event": "click"}
    total = events.count_documents(query) if events is not None else 0
    unique = events.count_documents({**query, "is_unique": True}) if events is not None else 0
    return {"link": _response(link), "analytics": {"total_clicks": total, "unique_clicks": unique}}


# Backward-compatible aliases for existing clients; all remain tenant-scoped.
@router.get("/links/{link_id}")
async def get_link(link_id: str, user_id: str = Depends(get_current_user)):
    collection = get_mongodb_collection("tracked_links")
    doc = collection.find_one({"_id": link_id}) if collection is not None else None
    if not doc:
        raise HTTPException(status_code=404, detail="Link not found")
    return await get_campaign_link(str(doc.get("campaign_id")), link_id, user_id)


@router.patch("/links/{link_id}")
async def update_link(link_id: str, request: LinkUpdate, user_id: str = Depends(get_current_user)):
    collection = get_mongodb_collection("tracked_links")
    doc = collection.find_one({"_id": link_id}) if collection is not None else None
    if not doc:
        raise HTTPException(status_code=404, detail="Link not found")
    return await update_campaign_link(str(doc.get("campaign_id")), link_id, request, user_id)


@router.delete("/links/{link_id}")
async def delete_link(link_id: str, user_id: str = Depends(get_current_user)):
    collection = get_mongodb_collection("tracked_links")
    doc = collection.find_one({"_id": link_id}) if collection is not None else None
    if not doc:
        raise HTTPException(status_code=404, detail="Link not found")
    return await delete_campaign_link(str(doc.get("campaign_id")), link_id, user_id)


@router.get("/links/{link_id}/analytics")
async def legacy_link_analytics(link_id: str, user_id: str = Depends(get_current_user)):
    collection = get_mongodb_collection("tracked_links")
    doc = collection.find_one({"_id": link_id}) if collection is not None else None
    if not doc:
        raise HTTPException(status_code=404, detail="Link not found")
    _campaign_or_404(str(doc.get("campaign_id")), user_id)
    link = TrackedLink.from_dict(doc)
    events = get_mongodb_collection("tracking_events")
    query = {"tracked_link_id": link_id, "campaign_id": str(link.campaign_id), "event": "click"}
    total = events.count_documents(query) if events is not None else link.total_clicks
    unique = events.count_documents({**query, "is_unique": True}) if events is not None else link.unique_clicks
    return {"status": "ok", "link": _response(link), "breakdown": {}, "analytics": {"total_clicks": total, "unique_clicks": unique}}


@router.get("/links/{link_id}/clicks")
async def legacy_link_clicks(link_id: str, user_id: str = Depends(get_current_user)):
    collection = get_mongodb_collection("tracked_links")
    doc = collection.find_one({"_id": link_id}) if collection is not None else None
    if not doc:
        raise HTTPException(status_code=404, detail="Link not found")
    _campaign_or_404(str(doc.get("campaign_id")), user_id)
    clicks = get_mongodb_collection("link_clicks")
    data = list(clicks.find({"link_id": link_id}, {"ip_address": 0}).sort("clicked_at", -1)) if clicks is not None else []
    return {"data": data, "count": len(data)}
