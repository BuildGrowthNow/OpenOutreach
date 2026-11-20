"""Org-aware authorization helpers.

Identifiers supplied by a client are locators only. Every profile, campaign,
proxy, seat, and daemon query must include the server-derived organization
context so a member can never read or mutate another tenant's data.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.mongodb.models_user import User
from openoutreach.organizations.models import (
    MEMBERS_COLLECTION,
    ROLE_OWNER,
    STATUS_ACTIVE,
    Organization,
    OrganizationMember,
)
from openoutreach.organizations.permissions import is_admin_or_owner
from openoutreach.organizations.service import (
    ensure_personal_org,
    get_active_org,
    get_membership,
    team_workspaces_enabled,
)

_PROFILES_COLLECTION = "linkedin_profiles"


@dataclass(frozen=True)
class OrgContext:
    """Resolved access context for one authenticated user."""

    user: User
    org: Organization
    member: Optional[OrganizationMember]
    role: str
    team_enabled: bool
    is_shared: bool
    profile_query: dict[str, Any] = field(default_factory=dict)

    @property
    def org_id(self) -> str:
        return self.org._id

    @property
    def is_owner(self) -> bool:
        return self.role == ROLE_OWNER

    @property
    def is_admin(self) -> bool:
        return self.role in (ROLE_OWNER, "admin")

    @property
    def can_view_all_profiles(self) -> bool:
        return is_admin_or_owner(self.role)

    @property
    def accounting_owner_id(self) -> str:
        return self.org.owner_user_id


def _member_count(org_id: str) -> int:
    collection = get_mongodb_collection(MEMBERS_COLLECTION)
    if collection is None:
        return 1
    return int(collection.count_documents({"org_id": org_id, "status": STATUS_ACTIVE}))


def resolve_org_context(user: User) -> OrgContext:
    """Resolve the active organization and the caller's effective role.

    When ``TEAM_WORKSPACES_ENABLED`` is false the personal organization is
    always used, even if ``User.org_id`` still points at a team workspace.
    This is the rollback path: no data is deleted and billing falls back to the
    user's own plan.
    """
    enabled = team_workspaces_enabled()
    if not enabled:
        org = ensure_personal_org(user)
        member = get_membership(org._id, user._id)
        role = ROLE_OWNER if org.owner_user_id == user._id else (
            member.role if member else "member"
        )
        return OrgContext(
            user=user,
            org=org,
            member=member,
            role=role,
            team_enabled=False,
            is_shared=False,
            profile_query=_personal_profile_query(user._id, org._id),
        )

    org = get_active_org(user)
    member = get_membership(org._id, user._id)
    if member is None and org.owner_user_id == user._id:
        role = ROLE_OWNER
    elif member is not None:
        role = member.role
    else:
        # Defensive fallback: never let a non-member inherit another org.
        personal = ensure_personal_org(user)
        return OrgContext(
            user=user,
            org=personal,
            member=get_membership(personal._id, user._id),
            role=ROLE_OWNER,
            team_enabled=True,
            is_shared=False,
            profile_query=_personal_profile_query(user._id, personal._id),
        )

    return OrgContext(
        user=user,
        org=org,
        member=member,
        role=role,
        team_enabled=True,
        is_shared=_member_count(org._id) > 1,
        profile_query=_org_profile_query(user._id, org._id, role),
    )


def _personal_profile_query(user_id: str, org_id: str) -> dict[str, Any]:
    return {
        "$or": [
            {"org_id": org_id},
            # Legacy rows created before organizations existed.
            {"org_id": {"$exists": False}, "user_id": user_id},
            {"org_id": None, "user_id": user_id},
        ]
    }


def _org_profile_query(user_id: str, org_id: str, role: str) -> dict[str, Any]:
    if is_admin_or_owner(role):
        return {"org_id": org_id}
    return {"org_id": org_id, "assigned_user_id": user_id}


def profile_access_query(user: User) -> dict[str, Any]:
    """Return the Mongo predicate for profiles the user may read."""
    return resolve_org_context(user).profile_query


def assigned_profile_ids(user: User, org_id: Optional[str] = None) -> set[str]:
    collection = get_mongodb_collection(_PROFILES_COLLECTION)
    if collection is None:
        return set()
    query: dict[str, Any] = {"assigned_user_id": user._id}
    if org_id:
        query["org_id"] = org_id
    return {str(doc["_id"]) for doc in collection.find(query, {"_id": 1})}


def can_access_profile_doc(user: User, profile: Optional[dict[str, Any]]) -> bool:
    if not profile:
        return False
    ctx = resolve_org_context(user)
    profile_org = profile.get("org_id")
    if profile_org == ctx.org_id:
        if ctx.can_view_all_profiles:
            return True
        return profile.get("assigned_user_id") == user._id
    if not profile_org and profile.get("user_id") == user._id:
        # Legacy personal row without an org id.
        return True
    return False


def can_manage_profile(user: User, profile: Optional[dict[str, Any]]) -> bool:
    """Members may edit assigned profiles; destructive actions use the role gate."""
    return can_access_profile_doc(user, profile)


def can_delete_profile(user: User, profile: Optional[dict[str, Any]]) -> bool:
    if not profile:
        return False
    ctx = resolve_org_context(user)
    if profile.get("org_id") == ctx.org_id:
        return ctx.can_view_all_profiles
    return profile.get("user_id") == user._id and not profile.get("org_id")


def profile_authorized_for_tenant(
    tenant_id: str, profile_id: str, channel: str, *, require_exists: bool = False
) -> bool:
    """Check a daemon tenant still owns/has the channel profile assigned.

    Used at enrollment and task-claim time so a stale device binding cannot
    outlive a seat reassignment or organization removal. When the profile
    document cannot be read, the caller's existing device binding remains the
    authorization source; ``require_exists`` makes enrollment strict.
    """
    user = User.get(tenant_id)
    if channel != "linkedin":
        collection = get_mongodb_collection(
            "whatsapp_profiles" if channel == "whatsapp" else "mailboxes"
        )
        if collection is None:
            return not require_exists
        doc = collection.find_one({"_id": profile_id})
        if doc is None:
            return not require_exists
        if user is None:
            return False
        if channel == "whatsapp" and doc.get("execution_mode") == "cloud":
            # Cloud WhatsApp has no proxy support until Phase 4.
            return False
        return can_access_channel_doc(user, doc)
    collection = get_mongodb_collection(_PROFILES_COLLECTION)
    if collection is None:
        return not require_exists
    profile = collection.find_one({"_id": profile_id})
    if profile is None:
        return not require_exists
    if user is None:
        return False
    # The desktop daemon must never enroll a cloud profile: cloud profiles
    # are owned by the server daemon and carry a managed proxy.
    if profile.get("execution_mode") == "cloud":
        return False
    return can_access_profile_doc(user, profile)


def org_member_user_ids(org_id: str) -> set[str]:
    collection = get_mongodb_collection(MEMBERS_COLLECTION)
    if collection is None:
        return set()
    return {
        str(doc["user_id"])
        for doc in collection.find({"org_id": org_id, "status": STATUS_ACTIVE})
    }


def channel_access_query(user: User) -> dict[str, Any]:
    """Return the Mongo predicate for org-scoped WhatsApp/mailbox rows.

    Owners and admins see every channel in the workspace; members see only the
    rows assigned to them. Legacy personal rows without ``org_id`` stay visible
    to their owner during rollout.
    """
    ctx = resolve_org_context(user)
    if not ctx.team_enabled:
        return {
            "$or": [
                {"org_id": ctx.org_id},
                {"org_id": {"$exists": False}, "user_id": user._id},
                {"org_id": None, "user_id": user._id},
            ]
        }
    legacy = [
        {"org_id": {"$exists": False}, "user_id": user._id},
        {"org_id": None, "user_id": user._id},
    ]
    if ctx.can_view_all_profiles:
        return {"$or": [{"org_id": ctx.org_id}, *legacy]}
    return {
        "$or": [
            {"org_id": ctx.org_id, "assigned_user_id": user._id},
            *legacy,
        ]
    }


def can_access_channel_doc(user: User, doc: Optional[dict[str, Any]]) -> bool:
    """Return whether the user may read or mutate one channel row."""
    if not doc:
        return False
    ctx = resolve_org_context(user)
    doc_org = doc.get("org_id")
    if doc_org == ctx.org_id:
        if ctx.can_view_all_profiles:
            return True
        return doc.get("assigned_user_id") == user._id
    if not doc_org and doc.get("user_id") == user._id:
        return True
    return False


def _legacy_campaign_clauses(user_id: str) -> list[dict[str, Any]]:
    """Campaigns created before organizations existed stay personal.

    These rows have no ``org_id``. They must remain visible to their creator
    when the personal organization is active, but they must not keep a removed
    member connected to a team workspace.
    """
    return [
        {"org_id": {"$exists": False}, "user_id": user_id},
        {"org_id": None, "user_id": user_id},
    ]


def campaign_access_query(user: User) -> dict[str, Any]:
    ctx = resolve_org_context(user)
    if not ctx.team_enabled:
        return {"$or": [{"user_id": user._id}, {"team_member_ids": user._id}]}

    legacy = _legacy_campaign_clauses(user._id)
    if ctx.can_view_all_profiles:
        # Owners/admins see every campaign in the active workspace plus their
        # own pre-migration personal rows. A bare user_id match is deliberately
        # absent: after a member is removed or switches workspace, campaigns
        # from the former team must not remain visible through that field.
        return {"$or": [{"org_id": ctx.org_id}, *legacy]}

    assigned = assigned_profile_ids(user, ctx.org_id)
    clauses: list[dict[str, Any]] = [
        {"org_id": ctx.org_id, "user_id": user._id},
        {"org_id": ctx.org_id, "team_member_ids": user._id},
        *legacy,
    ]
    if assigned:
        clauses.append(
            {
                "org_id": ctx.org_id,
                "linkedin_profile_id": {"$in": sorted(assigned)},
            }
        )
    return {"$or": clauses}


def campaign_has_access(user: User, campaign: Any) -> bool:
    """Return whether the user may read a campaign under org rules."""
    ctx = resolve_org_context(user)
    campaign_org = getattr(campaign, "org_id", None)
    owner_id = getattr(campaign, "user_id", None)
    team_member_ids = getattr(campaign, "team_member_ids", []) or []

    if not ctx.team_enabled:
        return owner_id == user._id or user._id in team_member_ids

    if campaign_org == ctx.org_id:
        if ctx.can_view_all_profiles:
            return True
        if owner_id == user._id or user._id in team_member_ids:
            return True
        assigned = assigned_profile_ids(user, ctx.org_id)
        return getattr(campaign, "linkedin_profile_id", None) in assigned

    # Legacy personal row without an organization id.
    return not campaign_org and owner_id == user._id


def campaign_manage_allowed(user: User, campaign: Any) -> bool:
    """Owner/admin may manage all org campaigns; members manage their own."""
    ctx = resolve_org_context(user)
    campaign_org = getattr(campaign, "org_id", None)
    if ctx.team_enabled and campaign_org == ctx.org_id:
        if ctx.can_view_all_profiles:
            return True
        return getattr(campaign, "user_id", None) == user._id
    if ctx.team_enabled and campaign_org:
        return False
    return getattr(campaign, "user_id", None) == user._id


def user_can_access_campaign(user_id: str, campaign: Any) -> bool:
    """Org-aware campaign access for routers that still hold only a user id."""
    user = User.get(user_id)
    if user is None:
        # Legacy/test path without a user row; fall back to the campaign's own
        # owner/member list rather than granting broader access.
        return campaign.has_access(user_id)
    return campaign_has_access(user, campaign)


def require_org_admin(user: User, org: Organization) -> OrganizationMember:
    member = get_membership(org._id, user._id)
    if member is None:
        if org.owner_user_id == user._id:
            return OrganizationMember(
                org_id=org._id,
                user_id=user._id,
                email=user.email,
                role=ROLE_OWNER,
                status=STATUS_ACTIVE,
            )
        raise PermissionError("Organization access denied")
    if not is_admin_or_owner(member.role):
        raise PermissionError("Organization administrator access required")
    return member
