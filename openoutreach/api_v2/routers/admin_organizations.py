"""Minimal admin organization view and audited seat overrides (Phase 3A)."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from openoutreach.api_v2.dependencies_v2 import get_admin_user
from openoutreach.billing.admin_security import AdminSecurityPolicy
from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.mongodb.models_user import User
from openoutreach.organizations.audit import list_org_audit_events
from openoutreach.organizations.models import (
    ORGANIZATIONS_COLLECTION,
    Organization,
)
from openoutreach.organizations.service import (
    OrganizationError,
    apply_seat_override,
    get_org,
    list_active_members,
    seat_summary,
)

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/admin/organizations",
    tags=["admin-organizations"],
    dependencies=[Depends(get_admin_user)],
)


class OrganizationAdminResponse(BaseModel):
    id: str
    name: str
    owner_user_id: str
    owner_email: Optional[str] = None
    plan: str
    status: str
    is_personal: bool
    seat_override: bool
    cloud_seats: int
    linkedin_account_limit: int
    whatsapp_account_limit: int
    members_count: int
    credentialed_profiles: int
    assigned_profiles: int
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class AdminMemberResponse(BaseModel):
    user_id: str
    email: str
    full_name: Optional[str] = None
    role: str
    status: str
    joined_at: Optional[str] = None


class AdminOrgDetailResponse(BaseModel):
    organization: OrganizationAdminResponse
    members: list[AdminMemberResponse]
    profiles: list[dict]
    audit_events: list[dict]


class SeatOverrideRequest(BaseModel):
    cloud_seats: int = Field(ge=0, le=10_000)
    reason: str = Field(min_length=3, max_length=500)
    plan: Optional[str] = None


def _iso(value) -> Optional[str]:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return None


def _admin_org_response(org: Organization) -> OrganizationAdminResponse:
    summary = seat_summary(org)
    owner = User.get(org.owner_user_id)
    return OrganizationAdminResponse(
        id=org._id,
        name=org.name,
        owner_user_id=org.owner_user_id,
        owner_email=owner.email if owner else None,
        plan=org.plan,
        status=org.status,
        is_personal=org.is_personal,
        seat_override=org.seat_override,
        cloud_seats=org.cloud_seats,
        linkedin_account_limit=org.linkedin_account_limit,
        whatsapp_account_limit=org.whatsapp_account_limit,
        members_count=summary["members"],
        credentialed_profiles=summary["credentialed_profiles"],
        assigned_profiles=summary["assigned_profiles"],
        stripe_customer_id=org.stripe_customer_id,
        stripe_subscription_id=org.stripe_subscription_id,
        created_at=_iso(org.created_at),
        updated_at=_iso(org.updated_at),
    )


@router.get("", response_model=dict)
async def list_organizations(
    search: Optional[str] = Query(None, max_length=200),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    collection = get_mongodb_collection(ORGANIZATIONS_COLLECTION)
    if collection is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    query: dict = {}
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"owner_user_id": search},
        ]
    total = collection.count_documents(query)
    docs = list(collection.find(query).sort("created_at", -1).skip(skip).limit(limit))
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "organizations": [
            _admin_org_response(Organization.from_dict(doc)) for doc in docs
        ],
    }


@router.get("/{org_id}", response_model=AdminOrgDetailResponse)
async def get_organization(org_id: str) -> AdminOrgDetailResponse:
    org = get_org(org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    users = get_mongodb_collection("users")
    members = list_active_members(org._id)
    user_docs = {}
    if users is not None and members:
        user_docs = {
            str(doc["_id"]): doc
            for doc in users.find(
                {"_id": {"$in": [member.user_id for member in members]}},
                {"full_name": 1, "email": 1},
            )
        }
    profiles = get_mongodb_collection("linkedin_profiles")
    profile_docs: list[dict] = []
    if profiles is not None:
        profile_docs = [
            {
                "id": str(doc.get("_id")),
                "linkedin_username": doc.get("linkedin_username"),
                "execution_mode": doc.get("execution_mode"),
                "assigned_user_id": doc.get("assigned_user_id"),
                "active": bool(doc.get("active", doc.get("is_active", False))),
                "proxy_assigned": bool(doc.get("proxy_id") or doc.get("proxy_mode")),
                "proxy_mode": doc.get("proxy_mode"),
            }
            for doc in profiles.find({"org_id": org._id})
        ]
    return AdminOrgDetailResponse(
        organization=_admin_org_response(org),
        members=[
            AdminMemberResponse(
                user_id=member.user_id,
                email=member.email,
                full_name=(user_docs.get(member.user_id) or {}).get("full_name"),
                role=member.role,
                status=member.status,
                joined_at=_iso(member.joined_at),
            )
            for member in members
        ],
        profiles=profile_docs,
        audit_events=[
            {
                "id": str(event.get("_id")),
                "event": event.get("event"),
                "actor_user_id": event.get("actor_user_id"),
                "target_user_id": event.get("target_user_id"),
                "target_email": event.get("target_email"),
                "metadata": event.get("metadata") or {},
                "created_at": _iso(event.get("created_at")),
            }
            for event in list_org_audit_events(org._id, limit=100)
        ],
    )


@router.patch("/{org_id}/seats", response_model=OrganizationAdminResponse)
async def override_seats(
    org_id: str,
    body: SeatOverrideRequest,
    admin_user_id: str = Depends(get_admin_user),
) -> OrganizationAdminResponse:
    org = get_org(org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    if body.plan is not None:
        from openoutreach.billing.plans import get_plan

        if not get_plan(body.plan) or body.plan == "cloud_addon":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid plan")
    try:
        org = apply_seat_override(
            org,
            admin_user_id,
            body.cloud_seats,
            body.reason,
            plan=body.plan,
        )
    except OrganizationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    AdminSecurityPolicy.log_admin_action(
        admin_user_id,
        "organization_seat_override",
        org.owner_user_id,
        {
            "org_id": org._id,
            "cloud_seats": body.cloud_seats,
            "plan": org.plan,
            "reason": body.reason,
        },
    )
    return _admin_org_response(org)
