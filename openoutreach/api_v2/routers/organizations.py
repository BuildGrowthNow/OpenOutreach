"""Organization, team, invite, and seat APIs (Phase 3A).

All routes are org-scoped. Team surfaces are gated by
``TEAM_WORKSPACES_ENABLED``; when the flag is off, ``/current`` still returns
the personal organization so the client can fall back without deleting data.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from openoutreach.api_v2.dependencies_v2 import get_current_user
from openoutreach.billing.emails import send_organization_invite
from openoutreach.config import settings
from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.mongodb.models_user import User
from openoutreach.organizations import audit
from openoutreach.organizations.access import resolve_org_context
from openoutreach.organizations.models import (
    ROLE_ADMIN,
    ROLE_MEMBER,
    ROLE_OWNER,
    Organization,
    OrganizationMember,
)
from openoutreach.organizations.permissions import (
    can_manage_team,
    can_view_all_profiles,
    can_view_billing,
)
from openoutreach.organizations.rate_limit import (
    check_invite_acceptance,
    check_invite_creation,
)
from openoutreach.organizations.service import (
    InviteEmailMismatchError,
    InviteInvalidError,
    MemberAlreadyExistsError,
    MemberNotFoundError,
    OrganizationError,
    OrganizationPermissionError,
    SeatAssignmentError,
    SeatLimitError,
    accept_invite,
    activate_org,
    assign_desktop_profile,
    assign_seat,
    change_member_role,
    get_invite_by_token,
    get_membership,
    get_org,
    invite_member,
    list_active_members,
    list_pending_invites,
    list_user_orgs,
    remove_member,
    remove_seat,
    revoke_invite,
    seat_summary,
    team_workspaces_enabled,
    unassign_seat,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/organizations", tags=["organizations"])


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded:
        return forwarded
    return request.client.host if request.client else "unknown"


def _require_team_enabled() -> None:
    if not team_workspaces_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Team workspaces are disabled",
        )


def _load_user(user_id: str) -> User:
    user = User.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def _load_org(org_id: str, user: User) -> Organization:
    org = get_org(org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    ctx = resolve_org_context(user)
    if org._id != ctx.org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization access denied")
    return org


class OrganizationResponse(BaseModel):
    id: str
    name: str
    owner_user_id: str
    plan: str
    role: str
    is_personal: bool
    is_shared: bool
    team_workspaces_enabled: bool
    cloud_seat_limit: Optional[int] = None
    cloud_seats: Optional[int] = None
    linkedin_account_limit: Optional[int] = None
    members_count: int
    assigned_profiles: int
    created_at: Optional[str] = None


class MemberResponse(BaseModel):
    user_id: str
    email: str
    full_name: Optional[str] = None
    role: str
    status: str
    invited_at: Optional[str] = None
    joined_at: Optional[str] = None


class InviteResponse(BaseModel):
    id: str
    email: str
    role: str
    expires_at: datetime
    created_at: datetime
    email_sent: bool = False
    debug_invite_url: Optional[str] = None


class InvitePreviewResponse(BaseModel):
    org_id: str
    org_name: str
    email: str
    role: str
    expires_at: datetime


class InviteCreateRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role: str = Field(default=ROLE_MEMBER)


class MemberRoleRequest(BaseModel):
    role: str


class SeatAssignRequest(BaseModel):
    profile_id: str = Field(min_length=1, max_length=128)
    assigned_user_id: str = Field(min_length=1, max_length=128)


class SeatProfileRequest(BaseModel):
    profile_id: str = Field(min_length=1, max_length=128)


class SeatSummaryResponse(BaseModel):
    cloud_seat_limit: Optional[int]
    cloud_profiles: int
    credentialed_profiles: int
    assigned_profiles: int
    unassigned_profiles: int
    members: int


class SeatProfileResponse(BaseModel):
    profile_id: str
    linkedin_username: Optional[str] = None
    assigned_user_id: Optional[str] = None
    execution_mode: Optional[str] = None
    active: bool = False
    proxy_assigned: bool = False
    proxy_mode: Optional[str] = None


class OrganizationUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


def _iso(value) -> Optional[str]:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return None


def _member_map(org_id: str) -> dict[str, dict]:
    collection = get_mongodb_collection("users")
    members = list_active_members(org_id)
    if collection is None:
        return {member.user_id: {} for member in members}
    ids = [member.user_id for member in members]
    return {
        str(doc["_id"]): doc
        for doc in collection.find({"_id": {"$in": ids}}, {"full_name": 1, "email": 1})
    }


def _org_response(org: Organization, user: User) -> OrganizationResponse:
    ctx = resolve_org_context(user)
    if org._id == ctx.org_id:
        role = ctx.role
        team_enabled = ctx.team_enabled
        is_shared = ctx.is_shared
    else:
        member = get_membership(org._id, user._id)
        if member is not None:
            role = member.role
        elif org.owner_user_id == user._id:
            role = ROLE_OWNER
        else:
            role = ROLE_MEMBER
        team_enabled = team_workspaces_enabled()
        is_shared = len(list_active_members(org._id)) > 1
    summary = seat_summary(org)
    show_billing = can_view_billing(role)
    return OrganizationResponse(
        id=org._id,
        name=org.name,
        owner_user_id=org.owner_user_id,
        plan=org.plan,
        role=role,
        is_personal=org.is_personal,
        is_shared=is_shared,
        team_workspaces_enabled=team_enabled,
        cloud_seat_limit=summary["cloud_seat_limit"] if show_billing else None,
        cloud_seats=org.cloud_seats if show_billing else None,
        linkedin_account_limit=org.linkedin_account_limit if show_billing else None,
        members_count=summary["members"],
        assigned_profiles=summary["assigned_profiles"],
        created_at=_iso(org.created_at),
    )


def _member_response(member: OrganizationMember, users: dict[str, dict]) -> MemberResponse:
    user_doc = users.get(member.user_id, {})
    return MemberResponse(
        user_id=member.user_id,
        email=member.email,
        full_name=user_doc.get("full_name"),
        role=member.role,
        status=member.status,
        invited_at=_iso(member.invited_at),
        joined_at=_iso(member.joined_at),
    )


def _profile_response(profile: dict) -> SeatProfileResponse:
    return SeatProfileResponse(
        profile_id=str(profile.get("_id")),
        linkedin_username=profile.get("linkedin_username"),
        assigned_user_id=profile.get("assigned_user_id"),
        execution_mode=profile.get("execution_mode"),
        active=bool(profile.get("active", profile.get("is_active", False))),
        proxy_assigned=bool(profile.get("proxy_id") or profile.get("proxy_mode")),
        proxy_mode=profile.get("proxy_mode"),
    )


def _org_error(exc: OrganizationError) -> HTTPException:
    if isinstance(exc, OrganizationPermissionError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, MemberNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, MemberAlreadyExistsError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, SeatLimitError):
        return HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=str(exc))
    if isinstance(exc, SeatAssignmentError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, (InviteInvalidError, InviteEmailMismatchError)):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("", response_model=list[OrganizationResponse])
async def list_organizations(user_id: str = Depends(get_current_user)):
    user = _load_user(user_id)
    if not team_workspaces_enabled():
        ctx = resolve_org_context(user)
        return [_org_response(ctx.org, user)]
    return [_org_response(org, user) for org in list_user_orgs(user)]


@router.get("/current", response_model=OrganizationResponse)
async def current_organization(user_id: str = Depends(get_current_user)):
    user = _load_user(user_id)
    ctx = resolve_org_context(user)
    return _org_response(ctx.org, user)


@router.post("/{org_id}/activate", response_model=OrganizationResponse)
async def activate_org_route(
    org_id: str,
    user_id: str = Depends(get_current_user),
):
    _require_team_enabled()
    user = _load_user(user_id)
    try:
        org = activate_org(user, org_id)
    except OrganizationPermissionError as exc:
        raise _org_error(exc)
    except OrganizationError as exc:
        raise _org_error(exc)
    return _org_response(org, user)


@router.patch("/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: str,
    body: OrganizationUpdateRequest,
    user_id: str = Depends(get_current_user),
):
    _require_team_enabled()
    user = _load_user(user_id)
    org = _load_org(org_id, user)
    ctx = resolve_org_context(user)
    if ctx.role != ROLE_OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the owner can rename the workspace")
    collection = get_mongodb_collection("organizations")
    if collection is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    collection.update_one({"_id": org._id}, {"$set": {"name": body.name.strip()}})
    org.name = body.name.strip()
    audit.record_org_audit(
        "org.update",
        org_id=org._id,
        actor_user_id=user_id,
        metadata={"name": org.name},
    )
    return _org_response(org, user)


@router.get("/{org_id}/members", response_model=list[MemberResponse])
async def list_members(org_id: str, user_id: str = Depends(get_current_user)):
    _require_team_enabled()
    user = _load_user(user_id)
    org = _load_org(org_id, user)
    ctx = resolve_org_context(user)
    if not can_manage_team(ctx.role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Team management access required")
    users = _member_map(org._id)
    return [_member_response(member, users) for member in list_active_members(org._id)]


@router.get("/{org_id}/invites", response_model=list[InviteResponse])
async def list_invites(org_id: str, user_id: str = Depends(get_current_user)):
    _require_team_enabled()
    user = _load_user(user_id)
    org = _load_org(org_id, user)
    ctx = resolve_org_context(user)
    if not can_manage_team(ctx.role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Team management access required")
    return [
        InviteResponse(
            id=invite._id,
            email=invite.email,
            role=invite.role,
            expires_at=invite.expires_at,
            created_at=invite.created_at,
        )
        for invite in list_pending_invites(org._id)
    ]


@router.post("/{org_id}/invites", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
async def create_invite(
    org_id: str,
    body: InviteCreateRequest,
    request: Request,
    user_id: str = Depends(get_current_user),
):
    _require_team_enabled()
    allowed, error = check_invite_creation(user_id)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=error)
    user = _load_user(user_id)
    org = _load_org(org_id, user)
    if body.role not in (ROLE_ADMIN, ROLE_MEMBER):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invite role")
    try:
        invite, token = invite_member(org, user_id, body.email, body.role)
    except OrganizationError as exc:
        raise _org_error(exc)

    app_url = settings.APP_URL or "http://localhost:3000"
    invite_url = f"{app_url}/team/accept?token={token}"
    email_sent = False
    try:
        email_sent = send_organization_invite(
            invite.email,
            org.name,
            user.full_name or user.email,
            invite.role,
            invite_url,
            invite.expires_at,
        )
    except Exception as exc:
        logger.warning("organization_invite_email_failed exception_type=%s", type(exc).__name__)

    return InviteResponse(
        id=invite._id,
        email=invite.email,
        role=invite.role,
        expires_at=invite.expires_at,
        created_at=invite.created_at,
        email_sent=email_sent,
        debug_invite_url=invite_url if settings.DEBUG else None,
    )


@router.delete("/{org_id}/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invite(
    org_id: str,
    invite_id: str,
    user_id: str = Depends(get_current_user),
):
    _require_team_enabled()
    user = _load_user(user_id)
    org = _load_org(org_id, user)
    try:
        revoke_invite(org, user_id, invite_id)
    except OrganizationError as exc:
        raise _org_error(exc)
    return None


@router.get("/invites/{token}", response_model=InvitePreviewResponse)
async def preview_invite(token: str, request: Request):
    allowed, error = check_invite_acceptance(_client_ip(request))
    if not allowed:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=error)
    try:
        invite = get_invite_by_token(token)
    except OrganizationError as exc:
        raise _org_error(exc)
    org = get_org(invite.org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return InvitePreviewResponse(
        org_id=org._id,
        org_name=org.name,
        email=invite.email,
        role=invite.role,
        expires_at=invite.expires_at,
    )


@router.post("/invites/{token}/accept", response_model=OrganizationResponse)
async def accept(
    token: str,
    request: Request,
    user_id: str = Depends(get_current_user),
):
    _require_team_enabled()
    allowed, error = check_invite_acceptance(_client_ip(request))
    if not allowed:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=error)
    user = _load_user(user_id)
    try:
        org, _member = accept_invite(token, user)
    except OrganizationError as exc:
        raise _org_error(exc)
    return _org_response(org, user)


@router.patch("/{org_id}/members/{member_user_id}", response_model=MemberResponse)
async def update_member_role(
    org_id: str,
    member_user_id: str,
    body: MemberRoleRequest,
    user_id: str = Depends(get_current_user),
):
    _require_team_enabled()
    user = _load_user(user_id)
    org = _load_org(org_id, user)
    if body.role not in (ROLE_ADMIN, ROLE_MEMBER):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")
    try:
        member = change_member_role(org, user_id, member_user_id, body.role)
    except OrganizationError as exc:
        raise _org_error(exc)
    users = _member_map(org._id)
    return _member_response(member, users)


@router.delete("/{org_id}/members/{member_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_member(
    org_id: str,
    member_user_id: str,
    user_id: str = Depends(get_current_user),
):
    _require_team_enabled()
    user = _load_user(user_id)
    org = _load_org(org_id, user)
    try:
        remove_member(org, user_id, member_user_id)
    except OrganizationError as exc:
        raise _org_error(exc)
    return None


@router.get("/{org_id}/seats", response_model=SeatSummaryResponse)
async def get_seats(org_id: str, user_id: str = Depends(get_current_user)):
    _require_team_enabled()
    user = _load_user(user_id)
    org = _load_org(org_id, user)
    ctx = resolve_org_context(user)
    summary = seat_summary(org)
    if not can_view_billing(ctx.role):
        summary = {**summary, "cloud_seat_limit": None, "credentialed_profiles": 0}
    return SeatSummaryResponse(**summary)


@router.post("/{org_id}/seats/assign", response_model=SeatProfileResponse)
async def assign(
    org_id: str,
    body: SeatAssignRequest,
    user_id: str = Depends(get_current_user),
):
    _require_team_enabled()
    user = _load_user(user_id)
    org = _load_org(org_id, user)
    try:
        profile = assign_seat(org, user_id, body.profile_id, body.assigned_user_id)
    except OrganizationError as exc:
        raise _org_error(exc)
    return _profile_response(profile)


@router.post("/{org_id}/seats/assign-desktop", response_model=SeatProfileResponse)
async def assign_desktop(
    org_id: str,
    body: SeatAssignRequest,
    user_id: str = Depends(get_current_user),
):
    _require_team_enabled()
    user = _load_user(user_id)
    org = _load_org(org_id, user)
    try:
        profile = assign_desktop_profile(
            org, user_id, body.profile_id, body.assigned_user_id
        )
    except OrganizationError as exc:
        raise _org_error(exc)
    return _profile_response(profile)


@router.post("/{org_id}/seats/unassign", response_model=SeatProfileResponse)
async def unassign(
    org_id: str,
    body: SeatProfileRequest,
    user_id: str = Depends(get_current_user),
):
    _require_team_enabled()
    user = _load_user(user_id)
    org = _load_org(org_id, user)
    try:
        profile = unassign_seat(org, user_id, body.profile_id)
    except OrganizationError as exc:
        raise _org_error(exc)
    return _profile_response(profile)


@router.post("/{org_id}/seats/remove", response_model=SeatProfileResponse)
async def remove(
    org_id: str,
    body: SeatProfileRequest,
    user_id: str = Depends(get_current_user),
):
    _require_team_enabled()
    user = _load_user(user_id)
    org = _load_org(org_id, user)
    try:
        profile = remove_seat(org, user_id, body.profile_id)
    except OrganizationError as exc:
        raise _org_error(exc)
    return _profile_response(profile)


@router.get("/{org_id}/profiles", response_model=list[SeatProfileResponse])
async def list_org_profiles(org_id: str, user_id: str = Depends(get_current_user)):
    _require_team_enabled()
    user = _load_user(user_id)
    org = _load_org(org_id, user)
    ctx = resolve_org_context(user)
    collection = get_mongodb_collection("linkedin_profiles")
    if collection is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    query: dict = {"org_id": org._id}
    if not can_view_all_profiles(ctx.role):
        query["assigned_user_id"] = user._id
    docs = collection.find(
        query,
        {
            "_id": 1,
            "linkedin_username": 1,
            "execution_mode": 1,
            "assigned_user_id": 1,
            "active": 1,
            "is_active": 1,
            "proxy_id": 1,
            "proxy_mode": 1,
        },
    )
    return [_profile_response(doc) for doc in docs]


@router.get("/{org_id}/audit", response_model=list[dict])
async def org_audit_events(org_id: str, user_id: str = Depends(get_current_user)):
    _require_team_enabled()
    user = _load_user(user_id)
    org = _load_org(org_id, user)
    ctx = resolve_org_context(user)
    if not can_manage_team(ctx.role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Team management access required")
    return audit.list_org_audit_events(org._id)
