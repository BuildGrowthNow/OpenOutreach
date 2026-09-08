"""Versioned, tenant-scoped campaign workflow templates."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from openoutreach.api_v2.dependencies_v2 import get_current_user
from openoutreach.core.sequence_schema import SEQUENCE_SCHEMA_VERSION, validate_sequence_graph
from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.mongodb.models import Campaign, TrackedLink
from openoutreach.mongodb.models_extended import CampaignTemplate

router = APIRouter()


class TemplateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)
    category: str = Field(default="general", max_length=80)
    channels: list[str] = Field(default_factory=list)
    sequence_schema_version: int = SEQUENCE_SCHEMA_VERSION
    sequence_steps: list[dict[str, Any]] = Field(default_factory=list)
    sequence_edges: list[dict[str, Any]] = Field(default_factory=list)
    campaign_defaults: dict[str, Any] = Field(default_factory=dict)
    link_definitions: list[dict[str, Any]] = Field(default_factory=list)
    safety_defaults: dict[str, Any] = Field(default_factory=dict)
    visibility: str = Field(default="private", pattern="^(private|team)$")
    team_member_ids: list[str] = Field(default_factory=list, max_length=100)
    # Accepted only as a migration convenience; stored under campaign_defaults.
    product_pitch: Optional[str] = None
    campaign_objective: Optional[str] = None
    booking_link: Optional[str] = None
    icp_titles: Optional[list[str]] = None
    follow_up_strategy: Optional[str] = None


class TemplatePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Optional[str] = Field(None, min_length=1, max_length=160)
    description: Optional[str] = Field(None, max_length=2000)
    category: Optional[str] = Field(None, max_length=80)
    channels: Optional[list[str]] = None
    sequence_steps: Optional[list[dict[str, Any]]] = None
    sequence_edges: Optional[list[dict[str, Any]]] = None
    campaign_defaults: Optional[dict[str, Any]] = None
    link_definitions: Optional[list[dict[str, Any]]] = None
    safety_defaults: Optional[dict[str, Any]] = None
    visibility: Optional[str] = Field(None, pattern="^(private|team)$")
    team_member_ids: Optional[list[str]] = Field(None, max_length=100)


class CreateCampaignFromTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=160)
    product_pitch: Optional[str] = None
    campaign_objective: Optional[str] = None
    booking_link: Optional[str] = None
    linkedin_profile_id: Optional[str] = None
    whatsapp_profile_id: Optional[str] = None
    channel_sequence: Optional[list[str]] = None
    channel_settings: Optional[dict[str, Any]] = None
    lead_source: Optional[str] = None
    icp_titles: Optional[list[str]] = None
    target_company_size: Optional[str] = None
    maps_query: Optional[str] = None
    maps_country_code: Optional[str] = None
    maps_backends: Optional[list[str]] = None
    maps_location: Optional[str] = None
    classified_sites: Optional[list[str]] = None
    links: dict[str, str] = Field(default_factory=dict)


def _node(node_id: str, kind: str, label: str, **data: Any) -> dict[str, Any]:
    return {"id": node_id, "type": kind, "data": {"label": label, **data}, "position": {"x": 0, "y": 0}}


def _edge(source: str, target: str, branch: Optional[str] = None) -> dict[str, Any]:
    return {"id": f"{source}-{target}-{branch or 'always'}", "source": source, "target": target, "data": {"condition": branch} if branch else {}}


def _system_templates() -> list[dict[str, Any]]:
    common = {"content_mode": "static", "body": "Hi {{lead.first_name}}, I thought this could be useful for your team.", "link_refs": ["demo"], "stop_on_reply": True}
    linkedin_message = {**common, "link_refs": []}
    linkedin = {
        "_id": "system_linkedin_only", "owner_user_id": "system", "name": "LinkedIn follow-up", "description": "A simple LinkedIn connection and follow-up sequence.", "category": "recommended", "channels": ["linkedin"],
        "sequence_steps": [_node("connect", "action", "LinkedIn connection", action="connect", channel="linkedin", requires=[]), _node("wait", "wait", "Wait 3 days", wait_days=3), _node("follow", "action", "LinkedIn follow-up", action="follow_up", channel="linkedin", message=linkedin_message, requires=[]), _node("end", "end", "End")],
        "sequence_edges": [_edge("connect", "wait"), _edge("wait", "follow"), _edge("follow", "end")], "campaign_defaults": {}, "link_definitions": [], "safety_defaults": {}, "visibility": "system", "version": 1, "sequence_schema_version": 1,
    }
    multichannel = {
        "_id": "system_email_fallback", "owner_user_id": "system", "name": "Email fallback", "description": "Connect on LinkedIn, then email leads with an address and finish with a follow-up.", "category": "recommended", "channels": ["linkedin", "email"],
        "sequence_steps": [_node("connect", "action", "LinkedIn connection", action="connect", channel="linkedin", requires=[]), _node("wait", "wait", "Wait 3 days", wait_days=3), _node("has_email", "condition", "Has email?", condition="lead_has_email"), _node("email", "action", "Send email", action="send_email", channel="email", requires=["api_email"], message={**common, "subject": "A useful idea for your team"}), _node("follow", "action", "LinkedIn follow-up", action="follow_up", channel="linkedin", message=common, requires=[]), _node("yes_end", "end", "End after email"), _node("no_end", "end", "End without email")],
        "sequence_edges": [_edge("connect", "wait"), _edge("wait", "has_email"), _edge("has_email", "email", "yes"), _edge("has_email", "no_end", "no"), _edge("email", "follow"), _edge("follow", "yes_end")], "campaign_defaults": {}, "link_definitions": [{"key": "demo", "name": "Demo booking page", "destination_mode": "campaign_booking_link", "default_destination_url": None, "default_utm": {"source": "{{channel}}", "medium": "outreach", "campaign": "{{campaign_id}}", "content": "{{step_id}}"}}], "safety_defaults": {}, "visibility": "system", "version": 1, "sequence_schema_version": 1,
    }
    return [linkedin, multichannel]


def _clean_defaults(values: Any) -> Any:
    forbidden = ("credential", "password", "secret", "mailbox_id", "profile_id", "session", "cookie", "token", "tracking_url", "signed_url", "recipient", "analytics", "lead_id", "deal_id", "user_id")
    if isinstance(values, dict):
        return {
            key: _clean_defaults(value) if isinstance(value, (dict, list)) else value
            for key, value in values.items()
            if not any(term in key.lower() for term in forbidden)
        }
    if isinstance(values, list):
        return [_clean_defaults(value) if isinstance(value, (dict, list)) else value for value in values]
    return values


def _document(template: CampaignTemplate | dict[str, Any]) -> dict[str, Any]:
    data = template if isinstance(template, dict) else template.to_dict()
    steps = data.get("sequence_steps", [])
    data = dict(data)
    data["id"] = str(data.pop("_id", data.get("id", "")))
    data["owner_user_id"] = str(data.get("owner_user_id") or data.get("created_by_id") or "")
    data["action_count"] = sum(1 for step in steps if step.get("type") == "action")
    data["required_data"] = sorted({required for step in steps for required in (step.get("data") or {}).get("requires", [])})
    data["approximate_duration_days"] = round(sum(
        float((step.get("data") or {}).get("wait_days", 0) or 0)
        + float((step.get("data") or {}).get("wait_hours", 0) or 0) / 24
        for step in steps
    ), 2)
    return data


def _get_template(template_id: str, user_id: str) -> CampaignTemplate | dict[str, Any]:
    system = next((item for item in _system_templates() if item["_id"] == template_id), None)
    if system:
        return system
    collection = get_mongodb_collection("campaign_templates")
    doc = collection.find_one({"_id": template_id}) if collection is not None else None
    if not doc:
        raise HTTPException(status_code=404, detail="Template not found")
    owner = str(doc.get("owner_user_id") or doc.get("created_by_id") or "")
    if owner != user_id and user_id not in (doc.get("team_member_ids") or []):
        raise HTTPException(status_code=404, detail="Template not found")
    return CampaignTemplate.from_dict(doc)


def _input_payload(data: TemplateInput) -> dict[str, Any]:
    payload = data.model_dump(exclude_none=True)
    defaults = _clean_defaults(payload.pop("campaign_defaults", {}))
    for key in ("product_pitch", "campaign_objective", "booking_link", "icp_titles", "follow_up_strategy"):
        if payload.get(key) is not None:
            defaults[key] = payload.pop(key)
    payload["campaign_defaults"] = defaults
    payload["sequence_steps"] = _clean_defaults(payload.get("sequence_steps", []))
    payload["sequence_edges"] = _clean_defaults(payload.get("sequence_edges", []))
    payload["link_definitions"] = _clean_defaults(payload.get("link_definitions", []))
    payload["safety_defaults"] = _clean_defaults(payload.get("safety_defaults", {}))
    payload["sequence_schema_version"] = SEQUENCE_SCHEMA_VERSION
    return payload


@router.get("")
@router.get("/")
async def list_campaign_templates(public: Optional[str] = Query(None), user_id: str = Depends(get_current_user)):
    data = [_document(template) for template in _system_templates()]
    collection = get_mongodb_collection("campaign_templates")
    if collection is not None:
        query = {"$or": [{"owner_user_id": user_id}, {"created_by_id": user_id}, {"visibility": "team", "team_member_ids": user_id}]}
        data.extend(_document(CampaignTemplate.from_dict(doc)) for doc in collection.find(query).sort("updated_at", -1))
    if public in {"true", "1"}:
        data = [item for item in data if item.get("visibility") in {"team", "system"}]
    return {"data": data, "count": len(data)}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_campaign_template(data: TemplateInput, user_id: str = Depends(get_current_user)):
    payload = _input_payload(data)
    errors = validate_sequence_graph(payload["sequence_steps"], payload["sequence_edges"], available_links={item.get("key") for item in payload["link_definitions"]})
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    collection = get_mongodb_collection("campaign_templates")
    if collection is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    now = datetime.now(timezone.utc)
    template = CampaignTemplate(_id=str(uuid4()), owner_user_id=user_id, created_by_id=user_id, created_at=now, updated_at=now, **payload)
    template.save()
    return _document(template)


@router.get("/{template_id}")
async def get_campaign_template(template_id: str, user_id: str = Depends(get_current_user)):
    return _document(_get_template(template_id, user_id))


@router.patch("/{template_id}")
async def update_campaign_template(template_id: str, data: TemplatePatch, user_id: str = Depends(get_current_user)):
    template = _get_template(template_id, user_id)
    if isinstance(template, dict):
        raise HTTPException(status_code=409, detail="System templates are immutable")
    if str(template.owner_user_id or template.created_by_id) != str(user_id):
        raise HTTPException(status_code=403, detail="Only the template owner can edit this template")
    updates = data.model_dump(exclude_unset=True)
    steps = updates.get("sequence_steps", template.sequence_steps)
    edges = updates.get("sequence_edges", template.sequence_edges)
    links = updates.get("link_definitions", template.link_definitions)
    errors = validate_sequence_graph(steps, edges, available_links={item.get("key") for item in links})
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    collection = get_mongodb_collection("campaign_templates")
    if collection is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    updates["version"] = template.version + 1
    updates["updated_at"] = datetime.now(timezone.utc)
    updates["sequence_schema_version"] = SEQUENCE_SCHEMA_VERSION
    if "campaign_defaults" in updates:
        updates["campaign_defaults"] = _clean_defaults(updates["campaign_defaults"])
    result = collection.update_one({"_id": template._id, "owner_user_id": user_id}, {"$set": updates})
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Template not found")
    updated = collection.find_one({"_id": template._id, "owner_user_id": user_id})
    if not updated:
        raise HTTPException(status_code=404, detail="Template not found")
    return _document(CampaignTemplate.from_dict(updated))


@router.delete("/{template_id}")
async def delete_campaign_template(template_id: str, user_id: str = Depends(get_current_user)):
    template = _get_template(template_id, user_id)
    if isinstance(template, dict):
        raise HTTPException(status_code=409, detail="System templates are immutable")
    collection = get_mongodb_collection("campaign_templates")
    result = collection.delete_one({"_id": template._id, "owner_user_id": user_id}) if collection is not None else None
    return {"success": bool(result and result.deleted_count)}


@router.post("/{template_id}/clone", status_code=status.HTTP_201_CREATED)
async def clone_campaign_template(template_id: str, data: dict[str, Any] | None = None, user_id: str = Depends(get_current_user)):
    source = _get_template(template_id, user_id)
    source_doc = _document(source)
    payload = {key: source_doc.get(key) for key in ("name", "description", "category", "channels", "sequence_schema_version", "sequence_steps", "sequence_edges", "campaign_defaults", "link_definitions", "safety_defaults")}
    payload["name"] = (data or {}).get("name") or f"{payload['name']} (copy)"
    payload["visibility"] = "private"
    payload["team_member_ids"] = []
    collection = get_mongodb_collection("campaign_templates")
    if collection is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    template = CampaignTemplate(_id=str(uuid4()), owner_user_id=user_id, created_by_id=user_id, **payload)
    template.save()
    return _document(template)


@router.post("/{template_id}/create-campaign", status_code=status.HTTP_201_CREATED)
async def create_campaign_from_template(template_id: str, data: CreateCampaignFromTemplate, user_id: str = Depends(get_current_user)):
    source = _get_template(template_id, user_id)
    source_doc = _document(source)
    steps = copy.deepcopy(source_doc.get("sequence_steps") or [])
    edges = copy.deepcopy(source_doc.get("sequence_edges") or [])
    defaults = _clean_defaults(source_doc.get("campaign_defaults") or {})
    booking_link = data.booking_link or defaults.get("booking_link") or ""
    channels = data.channel_sequence or source_doc.get("channels") or sorted({(step.get("data") or {}).get("channel") for step in steps if (step.get("data") or {}).get("channel")})
    link_definitions = source_doc.get("link_definitions") or []
    link_keys = {item.get("key") for item in link_definitions if item.get("key")}
    errors = validate_sequence_graph(steps, edges, available_links=link_keys)
    if errors:
        raise HTTPException(status_code=422, detail={"validation_errors": errors})
    from openoutreach.emails.tracking import _validate_destination_url
    for definition in link_definitions:
        key = definition.get("key")
        destination = data.links.get(key) or (booking_link if definition.get("destination_mode") == "campaign_booking_link" else definition.get("default_destination_url"))
        if destination:
            try:
                _validate_destination_url(destination)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=f"Link '{key}' has an unsafe destination") from exc

    campaign_id = str(uuid4())
    campaigns_collection = get_mongodb_collection("campaigns")
    links_collection = get_mongodb_collection("tracked_links")
    if campaigns_collection is None or (link_definitions and links_collection is None):
        raise HTTPException(status_code=503, detail="Database unavailable")
    campaign = Campaign(
        _id=campaign_id,
        name=data.name,
        product_pitch=data.product_pitch or defaults.get("product_pitch", ""),
        campaign_objective=data.campaign_objective or defaults.get("campaign_objective", ""),
        booking_link=booking_link,
        user_id=user_id,
        # Template visibility grants template access only; it must never grant
        # campaign access to every member of the source template.
        team_member_ids=[],
        linkedin_profile_id=data.linkedin_profile_id,
        whatsapp_profile_id=data.whatsapp_profile_id,
        channel_sequence=channels,
        channel_settings=data.channel_settings or defaults.get("channel_settings", {}),
        lead_source=data.lead_source or defaults.get("lead_source", "linkedin_search"),
        icp_titles=data.icp_titles if data.icp_titles is not None else defaults.get("icp_titles", []),
        target_company_size=data.target_company_size if data.target_company_size is not None else defaults.get("target_company_size"),
        maps_query=data.maps_query if data.maps_query is not None else defaults.get("maps_query"),
        maps_country_code=data.maps_country_code if data.maps_country_code is not None else defaults.get("maps_country_code"),
        maps_backends=data.maps_backends if data.maps_backends is not None else defaults.get("maps_backends", []),
        maps_location=data.maps_location if data.maps_location is not None else defaults.get("maps_location"),
        classified_sites=data.classified_sites if data.classified_sites is not None else defaults.get("classified_sites", []),
        safety_defaults=copy.deepcopy(source_doc.get("safety_defaults") or {}),
        sequence_steps=steps,
        sequence_edges=edges,
        sequence_schema_version=source_doc.get("sequence_schema_version", SEQUENCE_SCHEMA_VERSION),
        sequence_revision=source_doc.get("version", 1),
        source_template_id=template_id,
        source_template_version=source_doc.get("version", 1),
        template_snapshot=copy.deepcopy(source_doc),
        status="draft",
        is_paused=True,
        sequence_active=False,
    )
    created_links = []
    try:
        # Keep the public operation all-or-nothing even on deployments where
        # MongoDB transactions are unavailable (for example standalone test
        # replicas). The cleanup preserves the same contract for failures.
        campaign.save()
        for definition in link_definitions:
            key = definition.get("key")
            destination = data.links.get(key) or (booking_link if definition.get("destination_mode") == "campaign_booking_link" else definition.get("default_destination_url"))
            if not destination:
                continue
            link = TrackedLink(_id=str(uuid4()), campaign_id=campaign_id, user_id=user_id, key=key, name=definition.get("name", key), destination_url=destination, original_url=destination, short_code=str(uuid4()).replace("-", "")[:12], default_utm=definition.get("default_utm", {}))
            link.save()
            created_links.append(link.to_dict())
    except HTTPException:
        campaigns_collection.delete_one({"_id": campaign_id})
        if links_collection is not None:
            links_collection.delete_many({"campaign_id": campaign_id, "user_id": user_id})
        raise
    except Exception as exc:
        campaigns_collection.delete_one({"_id": campaign_id})
        if links_collection is not None:
            links_collection.delete_many({"campaign_id": campaign_id, "user_id": user_id})
        raise HTTPException(status_code=503, detail="Campaign creation failed") from exc
    readiness = []
    if "linkedin" in channels and not data.linkedin_profile_id:
        readiness.append("LinkedIn steps require a profile before activation.")
    if "email" in channels:
        mailboxes = get_mongodb_collection("mailboxes")
        if mailboxes is None or mailboxes.count_documents({"user_id": user_id, "paused": {"$ne": True}}) == 0:
            readiness.append("Email steps require an active mailbox before activation.")
    required_link_keys = {
        ref
        for step in steps
        for ref in ((step.get("data") or {}).get("message") or (step.get("data") or {})).get("link_refs", [])
    }
    required_link_keys.update(
        (step.get("data") or {}).get("link_key")
        for step in steps
        if (step.get("data") or {}).get("condition") in {"link_clicked", "link_not_clicked"}
        and (step.get("data") or {}).get("link_key")
    )
    created_keys = {item.get("key") for item in created_links}
    for key in sorted(required_link_keys - created_keys):
        readiness.append(f"Link '{key}' needs a destination before activation.")
    return {"campaign": campaign.to_dict(), "links": created_links, "validation_errors": [], "readiness": readiness, "status": "draft"}
