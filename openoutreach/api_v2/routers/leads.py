"""
Leads Router - Multi-tenant lead management endpoints
"""
import csv
import io
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
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


@router.get("")
async def list_leads(
    user_id: str = Depends(get_current_user),
    campaign_id: Optional[str] = None,
    state: Optional[str] = None,
    search: Optional[str] = None,
    disqualified: Optional[bool] = None,
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

    # Get deals (unfiltered by lead fields first; will narrow by lead after fetching)
    all_deals = list(collection.find(query).sort("creation_date", -1))

    # Apply lead-level filters (search, disqualified) that require joining the leads collection
    if search or disqualified is not None:
        all_lead_ids = list(set(str(d["lead_id"]) for d in all_deals))
        leads_collection = get_mongodb_collection("leads")
        if leads_collection is None:
            raise HTTPException(status_code=503, detail="Database unavailable")

        lead_filter: dict = {"_id": {"$in": all_lead_ids}}
        if disqualified is not None:
            lead_filter["disqualified"] = disqualified

        matching_leads = {
            str(doc["_id"]): doc
            for doc in leads_collection.find(lead_filter)
        }

        if search:
            term = search.lower()
            matching_leads = {
                k: v for k, v in matching_leads.items()
                if (
                    term in (v.get("full_name") or "").lower()
                    or term in (v.get("headline") or "").lower()
                    or term in (v.get("public_identifier") or "").lower()
                    or term in (v.get("api_email") or "").lower()
                    or (
                        isinstance(v.get("contact_info"), dict)
                        and term in (v["contact_info"].get("email") or "").lower()
                    )
                )
            }

        all_deals = [d for d in all_deals if str(d["lead_id"]) in matching_leads]

    total = len(all_deals)
    deals = all_deals[offset: offset + limit]

    # Get unique lead IDs
    lead_ids = list(set(str(d["lead_id"]) for d in deals))

    # Fetch leads
    leads_collection = get_mongodb_collection("leads")
    if leads_collection is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    leads_data = {str(doc["_id"]): doc for doc in leads_collection.find({"_id": {"$in": lead_ids}})}

    # Fetch campaign names for lookup
    campaign_ids = list(set(str(d["campaign_id"]) for d in deals))
    campaigns_collection = get_mongodb_collection("campaigns")
    campaign_names: dict = {}
    if campaigns_collection is not None:
        for cdoc in campaigns_collection.find({"_id": {"$in": campaign_ids}}, {"_id": 1, "name": 1}):
            campaign_names[str(cdoc["_id"])] = cdoc.get("name", "")

    # Build response - flat Lead shape matching frontend Lead interface
    data = []
    for deal in deals:
        lead_data = leads_data.get(str(deal["lead_id"]))
        if lead_data:
            created = lead_data.get("creation_date")
            updated = lead_data.get("update_date") or created
            # Extract display fields from cached_profile (Voyager response shape)
            cp = lead_data.get("cached_profile") or {}
            profile_inner = cp.get("profile", cp)
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
            # Extract company from "Title at Company" headline pattern
            company = None
            if headline:
                at_idx = headline.lower().find(" at ")
                if at_idx > -1:
                    company = headline[at_idx + 4:].strip()
            # Resolve best available email: api_email (enrichment) > contact_info overlay
            api_email = lead_data.get("api_email")
            contact_info_raw = lead_data.get("contact_info") or {}
            overlay_email = contact_info_raw.get("email") if isinstance(contact_info_raw, dict) else None
            best_email = api_email or overlay_email
            phone_numbers = (
                contact_info_raw.get("phone_numbers") or []
                if isinstance(contact_info_raw, dict) else []
            )
            data.append({
                "id": str(lead_data["_id"]),
                "publicIdentifier": lead_data.get("public_identifier", ""),
                "linkedinUrl": lead_data.get("linkedin_url", lead_data.get("url", "")),
                "name": full_name,
                "title": headline,
                "company": company,
                "state": deal.get("state", "DISCOVERED"),
                "outcome": deal.get("outcome"),
                "campaignId": str(deal["campaign_id"]),
                "campaignName": campaign_names.get(str(deal["campaign_id"])),
                "creationDate": created.isoformat() if hasattr(created, "isoformat") else (created or ""),
                "updateDate": updated.isoformat() if hasattr(updated, "isoformat") else (updated or ""),
                "disqualified": lead_data.get("disqualified", False),
                "qualificationHold": bool(deal.get("qualification_hold", False)),
                "qualificationReason": deal.get("qualification_reason"),
                "phone": lead_data.get("phone"),
                "activeChannel": deal.get("active_channel", "linkedin"),
                "channelAvailability": {
                    "linkedin": bool(lead_data.get("linkedin_url") or lead_data.get("url")),
                    "email": bool(lead_data.get("api_email") or (
                        isinstance(lead_data.get("contact_info"), dict)
                        and lead_data["contact_info"].get("email")
                    )),
                    "whatsapp": bool(lead_data.get("phone") and lead_data.get("phone_on_whatsapp") is not False),
                },
                "contactInfo": {
                    "email": best_email,
                    "apiEmail": api_email,
                    "overlayEmail": overlay_email,
                    "phoneNumbers": phone_numbers,
                } if (best_email or phone_numbers) else None,
            })

    page = (offset // limit) + 1 if limit else 1
    pages = (total + limit - 1) // limit if limit else 1
    return {
        "data": data,
        "pagination": {"total": total, "page": page, "limit": limit, "pages": pages},
    }


@router.get("/export", response_class=StreamingResponse)
async def export_leads(
    user_id: str = Depends(get_current_user),
    campaign_id: Optional[str] = None,
    state: Optional[str] = None,
):
    """Export leads as CSV.

    Returns a CSV file with one row per deal (lead × campaign), including all
    available contact information.  Scoped to campaigns the requesting user can
    access.
    """
    collection = get_mongodb_collection("deals")
    if collection is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    query: dict = {}

    if campaign_id:
        campaign = models.Campaign.get(campaign_id)
        if not campaign or not campaign.has_access(user_id):
            raise HTTPException(status_code=403, detail="Campaign access denied")
        query["campaign_id"] = campaign_id
    else:
        campaigns_collection = get_mongodb_collection("campaigns")
        if campaigns_collection is None:
            raise HTTPException(status_code=503, detail="Database unavailable")
        accessible = list(campaigns_collection.find(
            {"$or": [{"user_id": user_id}, {"team_member_ids": user_id}]},
            {"_id": 1},
        ))
        query["campaign_id"] = {"$in": [str(c["_id"]) for c in accessible]}

    if state:
        query["state"] = state

    deals = list(collection.find(query).sort("creation_date", -1))

    lead_ids = list({str(d["lead_id"]) for d in deals})
    leads_collection = get_mongodb_collection("leads")
    if leads_collection is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    leads_map = {
        str(doc["_id"]): doc
        for doc in leads_collection.find({"_id": {"$in": lead_ids}})
    }

    campaign_ids = list({str(d["campaign_id"]) for d in deals})
    campaigns_collection = get_mongodb_collection("campaigns")
    campaign_names: dict = {}
    if campaigns_collection is not None:
        for cdoc in campaigns_collection.find(
            {"_id": {"$in": campaign_ids}}, {"_id": 1, "name": 1}
        ):
            campaign_names[str(cdoc["_id"])] = cdoc.get("name", "")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Name", "Email", "Phone Numbers", "LinkedIn URL",
        "Company", "Title", "State", "Outcome",
        "Campaign", "Created Date", "Disqualified",
    ])

    for deal in deals:
        lead = leads_map.get(str(deal["lead_id"]))
        if not lead:
            continue

        cp = lead.get("cached_profile") or {}
        profile_inner = cp.get("profile", cp)
        first = profile_inner.get("firstName", "") or cp.get("first_name", "")
        last = profile_inner.get("lastName", "") or cp.get("last_name", "")
        full_name = lead.get("full_name") or f"{first} {last}".strip() or ""
        headline = (
            lead.get("headline")
            or profile_inner.get("headline")
            or cp.get("headline", "")
        )
        company = ""
        if headline:
            at_idx = headline.lower().find(" at ")
            if at_idx > -1:
                company = headline[at_idx + 4:].strip()

        api_email = lead.get("api_email", "")
        contact_info_raw = lead.get("contact_info") or {}
        overlay_email = (
            contact_info_raw.get("email", "")
            if isinstance(contact_info_raw, dict) else ""
        )
        best_email = api_email or overlay_email
        phones = (
            "; ".join(contact_info_raw.get("phone_numbers") or [])
            if isinstance(contact_info_raw, dict) else ""
        )

        created = deal.get("creation_date")
        created_str = created.isoformat() if hasattr(created, "isoformat") else str(created or "")

        writer.writerow([
            full_name,
            best_email,
            phones,
            lead.get("linkedin_url") or lead.get("url", ""),
            company,
            headline,
            deal.get("state", ""),
            deal.get("outcome", ""),
            campaign_names.get(str(deal["campaign_id"]), ""),
            created_str,
            "Yes" if lead.get("disqualified") else "No",
        ])

    output.seek(0)
    filename = f"leads-export-{campaign_id or 'all'}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{lead_id}")
async def get_lead(
    lead_id: str,
    user_id: str = Depends(get_current_user),
):
    """
    Get a single lead by ID.
    User must have access via at least one campaign.
    Returns the same camelCase shape as the list endpoint, plus full profile and deal details.
    """
    deals_collection = get_mongodb_collection("deals")
    if deals_collection is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    deals = list(deals_collection.find({"lead_id": lead_id}))

    if not deals:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Verify user has access to at least one campaign; keep first accessible deal for state
    accessible_deal = None
    for deal in deals:
        campaign = models.Campaign.get(str(deal["campaign_id"]))
        if campaign and campaign.has_access(user_id):
            if accessible_deal is None:
                accessible_deal = deal

    if accessible_deal is None:
        raise HTTPException(status_code=403, detail="Access denied")

    leads_collection = get_mongodb_collection("leads")
    if leads_collection is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    lead_data = leads_collection.find_one({"_id": lead_id})

    if not lead_data:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Build profile shape from cached_profile (Voyager response)
    cp = lead_data.get("cached_profile") or {}
    first = cp.get("first_name", "")
    last = cp.get("last_name", "")
    full_name = lead_data.get("full_name") or (f"{first} {last}".strip() or None)
    headline = lead_data.get("headline") or cp.get("headline")
    location = lead_data.get("location") or cp.get("location_name")

    company = None
    if headline:
        at_idx = headline.lower().find(" at ")
        if at_idx > -1:
            company = headline[at_idx + 4:].strip()

    # Build experience list from positions
    positions = cp.get("positions") or []
    experience = []
    for pos in positions:
        if not isinstance(pos, dict):
            continue
        dr = pos.get("date_range") or {}
        start = dr.get("start") or {}
        end = dr.get("end") or {}

        def _year_month(d: dict) -> Optional[str]:
            if not d:
                return None
            y, m = d.get("year"), d.get("month")
            if y and m:
                return f"{m}/{y}"
            return str(y) if y else None

        start_str = _year_month(start)
        end_str = _year_month(end) or "Present"
        duration = f"{start_str} - {end_str}" if start_str else None
        experience.append({
            "title": pos.get("title"),
            "company": pos.get("company_name"),
            "duration": duration,
        })

    # Build education list
    educations = cp.get("educations") or []
    education = []
    for edu in educations:
        if not isinstance(edu, dict):
            continue
        dr = edu.get("date_range") or {}
        end = dr.get("end") or {}
        year = str(end.get("year")) if end.get("year") else None
        education.append({
            "school": edu.get("school_name"),
            "degree": edu.get("degree_name"),
            "year": year,
        })

    profile_shape = {
        "firstName": first,
        "lastName": last,
        "headline": headline,
        "summary": cp.get("summary"),
        "location": location,
        "experience": experience,
        "education": education,
    } if cp else None

    # Contact info
    api_email = lead_data.get("api_email")
    contact_info_raw = lead_data.get("contact_info") or {}
    overlay_email = contact_info_raw.get("email") if isinstance(contact_info_raw, dict) else None
    best_email = api_email or overlay_email
    phone_numbers = (
        contact_info_raw.get("phone_numbers") or []
        if isinstance(contact_info_raw, dict) else []
    )

    created = lead_data.get("creation_date")
    updated = lead_data.get("update_date") or created

    # Collect all deals the user can see for this lead
    all_deals = []
    campaigns_collection = get_mongodb_collection("campaigns")
    campaign_names: dict = {}
    if campaigns_collection is not None:
        for cdoc in campaigns_collection.find(
            {"_id": {"$in": [str(d["campaign_id"]) for d in deals]}},
            {"_id": 1, "name": 1},
        ):
            campaign_names[str(cdoc["_id"])] = cdoc.get("name", "")

    for deal in deals:
        campaign_obj = models.Campaign.get(str(deal["campaign_id"]))
        if campaign_obj and campaign_obj.has_access(user_id):
            all_deals.append({
                "dealId": str(deal["_id"]),
                "campaignId": str(deal["campaign_id"]),
                "campaignName": campaign_names.get(str(deal["campaign_id"])),
                "state": deal.get("state", "DISCOVERED"),
                "outcome": deal.get("outcome"),
            })

    # Populate messagesCount and lastMessageAt from chat_messages (Fix #9)
    accessible_deal_ids = [d["dealId"] for d in all_deals]
    messages_count = 0
    last_message_at = None
    if accessible_deal_ids:
        messages_col = get_mongodb_collection("chat_messages")
        if messages_col is not None:
            messages_count = messages_col.count_documents({"deal_id": {"$in": accessible_deal_ids}})
            last_msg = messages_col.find_one(
                {"deal_id": {"$in": accessible_deal_ids}},
                sort=[("creation_date", -1)],
            )
            if last_msg and last_msg.get("creation_date"):
                last_message_at = last_msg["creation_date"].isoformat()

    return {
        "id": str(lead_data["_id"]),
        "publicIdentifier": lead_data.get("public_identifier", ""),
        "linkedinUrl": lead_data.get("linkedin_url", lead_data.get("url", "")),
        "name": full_name,
        "title": headline,
        "company": company,
        "state": accessible_deal.get("state", "DISCOVERED"),
        "outcome": accessible_deal.get("outcome"),
        "campaignId": str(accessible_deal["campaign_id"]),
        "campaignName": campaign_names.get(str(accessible_deal["campaign_id"])),
        "creationDate": created.isoformat() if hasattr(created, "isoformat") else (str(created) if created else ""),
        "updateDate": updated.isoformat() if hasattr(updated, "isoformat") else (str(updated) if updated else ""),
        "disqualified": lead_data.get("disqualified", False),
        "phone": lead_data.get("phone"),
        "activeChannel": accessible_deal.get("active_channel", "linkedin"),
        "channelAvailability": {
            "linkedin": bool(lead_data.get("linkedin_url") or lead_data.get("url")),
            "email": bool(lead_data.get("api_email") or (
                isinstance(lead_data.get("contact_info"), dict)
                and lead_data["contact_info"].get("email")
            )),
            "whatsapp": bool(lead_data.get("phone") and lead_data.get("phone_on_whatsapp") is not False),
        },
        "notes": lead_data.get("notes"),
        "contactInfo": {
            "email": best_email,
            "apiEmail": api_email,
            "overlayEmail": overlay_email,
            "phoneNumbers": phone_numbers,
        } if (best_email or phone_numbers) else None,
        "profile": profile_shape,
        "deals": all_deals,
        "connectionDegree": lead_data.get("connection_degree"),
        "messagesCount": messages_count,
        "lastMessageAt": last_message_at,
    }


@router.get("/campaigns/{campaign_id}/leads")
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


@router.get("/{lead_id}/messages")
async def get_lead_messages(
    lead_id: str,
    user_id: str = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    Get messages for a lead across all campaigns user has access to.
    Returns all messages from deals linking this lead to accessible campaigns.
    """
    # Check if user has access to this lead via any campaign
    deals_collection = get_mongodb_collection("deals")
    if deals_collection is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    deals = list(deals_collection.find({"lead_id": lead_id}))

    if not deals:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Verify user has access to at least one campaign
    accessible_deal_ids = []
    for deal in deals:
        campaign = models.Campaign.get(str(deal["campaign_id"]))
        if campaign and campaign.has_access(user_id):
            accessible_deal_ids.append(str(deal["_id"]))

    if not accessible_deal_ids:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get messages for accessible deals
    messages_collection = get_mongodb_collection("chat_messages")
    if messages_collection is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    query = {"deal_id": {"$in": accessible_deal_ids}}
    total = messages_collection.count_documents(query)
    messages = list(messages_collection.find(query).skip(offset).limit(limit).sort("creation_date", -1))

    results = []
    for msg in messages:
        results.append({
            "id": str(msg["_id"]),
            "deal_id": str(msg["deal_id"]),
            "sender_name": msg.get("sender_name"),
            "content": msg.get("content", ""),
            "is_outgoing": msg.get("is_outgoing", False),
            "creation_date": msg.get("creation_date"),
            "event_urn": msg.get("event_urn"),
        })

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "results": results,
    }


class SendMessageRequest(BaseModel):
    content: str
    campaign_id: Optional[str] = None


@router.post("/{lead_id}/messages")
async def send_message_to_lead(
    lead_id: str,
    body: SendMessageRequest,
    user_id: str = Depends(get_current_user),
):
    """
    Send a message to a lead.
    Creates a Message record and enqueues a send_manual_message task for the daemon.
    The message is not sent synchronously - the daemon picks it up and sends via Playwright.
    """
    deals_collection = get_mongodb_collection("deals")
    if deals_collection is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    # If campaign_id specified, look for deal in that campaign; otherwise find any accessible deal
    if body.campaign_id:
        campaign = models.Campaign.get(body.campaign_id)
        if not campaign or not campaign.has_access(user_id):
            raise HTTPException(status_code=403, detail="Campaign access denied")
        deal_doc = deals_collection.find_one({"lead_id": lead_id, "campaign_id": body.campaign_id})
        if not deal_doc:
            raise HTTPException(status_code=404, detail="Deal not found for this lead in the specified campaign")
    else:
        deals = list(deals_collection.find({"lead_id": lead_id}))
        if not deals:
            raise HTTPException(status_code=404, detail="Lead not found")

        deal_doc = None
        campaign = None
        for d in deals:
            c = models.Campaign.get(str(d["campaign_id"]))
            if c and c.has_access(user_id):
                deal_doc = d
                campaign = c
                break

        if not deal_doc or not campaign:
            raise HTTPException(status_code=403, detail="Access denied")

    deal_id = str(deal_doc["_id"])
    campaign_id = str(deal_doc["campaign_id"])

    # Create the Message record (pending send)
    msg = models.Message(
        deal_id=deal_id,
        content=body.content,
        is_outgoing=True,
        user_id=user_id,
    )
    msg.save()

    # Find the LinkedIn profile for this campaign to scope the task
    campaign_obj = campaign or models.Campaign.get(campaign_id)
    linkedin_profile_id = campaign_obj.linkedin_profile_id if campaign_obj else None
    if not linkedin_profile_id:
        raise HTTPException(
            status_code=400,
            detail="Campaign has no linked LinkedIn profile - cannot send messages"
        )

    # Enqueue a send_manual_message task for the daemon
    task = models.Task(
        task_type=models.Task.TaskType.SEND_MANUAL_MESSAGE,
        payload={
            "campaign_id": campaign_id,
            "message_id": msg.pk,
            "lead_id": lead_id,
        },
        user_id=user_id,
        linkedin_profile_id=linkedin_profile_id,
    )
    task.save()

    return {
        "success": True,
        "message_id": msg.pk,
        "task_id": task.pk,
        "status": "queued",
    }


class StateUpdate(BaseModel):
    state: str


@router.patch("/{lead_id}/campaigns/{campaign_id}/state")
async def update_deal_state(
    lead_id: str,
    campaign_id: str,
    state_update: StateUpdate,
    user_id: str = Depends(get_current_user),
):
    """
    Update the deal state for a lead in a specific campaign.
    Validates state against DealState enum.
    """
    from openoutreach.crm.models.deal import DealState

    # Verify campaign access
    campaign = models.Campaign.get(campaign_id)
    if not campaign or not campaign.has_access(user_id):
        raise HTTPException(status_code=403, detail="Campaign access denied")

    # Validate state
    try:
        new_state = DealState(state_update.state)
    except ValueError:
        valid_states = [s.value for s in DealState]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid state: {state_update.state}. Valid states: {', '.join(valid_states)}"
        )

    # Find the deal
    deals_collection = get_mongodb_collection("deals")
    if deals_collection is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    deal = deals_collection.find_one({"lead_id": lead_id, "campaign_id": campaign_id})
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    # Update the state
    deals_collection.update_one(
        {"_id": deal["_id"]},
        {"$set": {"state": new_state.value}}
    )

    return {
        "success": True,
        "message": f"Deal state updated to {new_state.value}",
        "deal_id": str(deal["_id"]),
        "state": new_state.value
    }


class LeadUpdate(BaseModel):
    notes: Optional[str] = None
    disqualified: Optional[bool] = None


@router.patch("/{lead_id}")
async def update_lead(
    lead_id: str,
    body: LeadUpdate,
    user_id: str = Depends(get_current_user),
):
    """
    Update editable fields on a lead (notes, disqualified status).
    User must have access via at least one campaign.
    """
    deals_collection = get_mongodb_collection("deals")
    if deals_collection is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    deals = list(deals_collection.find({"lead_id": lead_id}))

    if not deals:
        raise HTTPException(status_code=404, detail="Lead not found")

    has_access = False
    for deal in deals:
        campaign = models.Campaign.get(str(deal["campaign_id"]))
        if campaign and campaign.has_access(user_id):
            has_access = True
            break

    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied")

    leads_collection = get_mongodb_collection("leads")
    if leads_collection is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    update_doc = {}
    if body.notes is not None:
        update_doc["notes"] = body.notes
    if body.disqualified is not None:
        update_doc["disqualified"] = body.disqualified

    if not update_doc:
        raise HTTPException(status_code=400, detail="No fields to update")

    leads_collection.update_one({"_id": lead_id}, {"$set": update_doc})

    # Return updated lead via the same shape as get_lead
    return await get_lead(lead_id=lead_id, user_id=user_id)


class AddToCampaignRequest(BaseModel):
    campaign_id: str


@router.post("/{lead_id}/add-to-campaign")
async def add_lead_to_campaign(
    lead_id: str,
    body: AddToCampaignRequest,
    user_id: str = Depends(get_current_user),
):
    """
    Add an existing lead to a campaign by creating a Deal linking them.
    The deal starts in DISCOVERED state for qualification.
    """
    from openoutreach.crm.models.deal import DealState

    campaign = models.Campaign.get(body.campaign_id)
    if not campaign or not campaign.has_access(user_id):
        raise HTTPException(status_code=403, detail="Campaign access denied")

    leads_collection = get_mongodb_collection("leads")
    if leads_collection is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    lead_doc = leads_collection.find_one({"_id": lead_id})
    if not lead_doc:
        raise HTTPException(status_code=404, detail="Lead not found")

    deals_collection = get_mongodb_collection("deals")
    if deals_collection is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    # Check if already linked
    existing = deals_collection.find_one({"lead_id": lead_id, "campaign_id": body.campaign_id})
    if existing:
        raise HTTPException(status_code=409, detail="Lead already in this campaign")

    deal = models.Deal(
        lead_id=lead_id,
        campaign_id=body.campaign_id,
        state=DealState.DISCOVERED,
        reason="Added manually by operator",
    )
    deal.save()

    return {
        "success": True,
        "deal_id": deal.pk,
        "state": DealState.DISCOVERED,
    }
