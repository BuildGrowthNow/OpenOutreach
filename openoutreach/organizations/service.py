"""Organization lifecycle, invites, roles, and seat assignment (Phase 3A).

The service is deliberately independent of FastAPI so the same rules are used
by the API, daemon, migrations, and tests. Every mutation is org-scoped and
audited. A seat is released only when a credentialed profile is deleted.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import timedelta
from typing import Any, Optional

from openoutreach.billing.plans import (
    effective_cloud_seat_limit,
    effective_linkedin_account_limit,
)
from openoutreach.billing.seats import credentialed_profile_ids_for_org
from openoutreach.config import settings
from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.mongodb.models_user import User
from openoutreach.organizations import audit
from openoutreach.organizations.models import (
    INVITES_COLLECTION,
    MEMBERS_COLLECTION,
    ORGANIZATIONS_COLLECTION,
    ORG_STATUS_ACTIVE,
    ROLE_ADMIN,
    ROLE_MEMBER,
    ROLE_OWNER,
    STATUS_ACTIVE,
    STATUS_REMOVED,
    Organization,
    OrganizationInvite,
    OrganizationMember,
    utc_now,
)
from openoutreach.organizations.permissions import (
    can_assign_role,
    can_assign_seats,
    can_manage_member,
)

logger = logging.getLogger(__name__)

_PROFILES_COLLECTION = "linkedin_profiles"
_CAMPAIGNS_COLLECTION = "campaigns"


class OrganizationError(Exception):
    """Base class for organization errors."""


class OrganizationPermissionError(OrganizationError):
    """The caller is not allowed to perform this organization action."""


class InviteInvalidError(OrganizationError):
    """The invite token is unknown, expired, revoked, or already used."""


class InviteEmailMismatchError(OrganizationError):
    """The signed-in user does not match the invited email address."""


class MemberAlreadyExistsError(OrganizationError):
    """An active member with that email already exists in the organization."""


class MemberNotFoundError(OrganizationError):
    """The requested member is not part of the organization."""


class SeatAssignmentError(OrganizationError):
    """The seat assignment is not allowed."""


class SeatLimitError(SeatAssignmentError):
    """The organization's cloud seat pool is exhausted."""


def team_workspaces_enabled() -> bool:
    return bool(getattr(settings, "TEAM_WORKSPACES_ENABLED", False))


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def personal_org_name(user: User) -> str:
    name = (user.full_name or "").strip()
    if not name:
        name = (user.email or "Personal").split("@")[0]
    return f"{name}'s workspace"


def get_org(org_id: str) -> Optional[Organization]:
    return Organization.get(org_id)


def get_membership(org_id: str, user_id: str) -> Optional[OrganizationMember]:
    collection = get_mongodb_collection(MEMBERS_COLLECTION)
    if collection is None:
        return None
    doc = collection.find_one(
        {"org_id": org_id, "user_id": user_id, "status": STATUS_ACTIVE}
    )
    return OrganizationMember.from_dict(doc) if doc else None


def list_active_members(org_id: str) -> list[OrganizationMember]:
    collection = get_mongodb_collection(MEMBERS_COLLECTION)
    if collection is None:
        return []
    return [
        OrganizationMember.from_dict(doc)
        for doc in collection.find({"org_id": org_id, "status": STATUS_ACTIVE})
    ]


def list_pending_invites(org_id: str) -> list[OrganizationInvite]:
    collection = get_mongodb_collection(INVITES_COLLECTION)
    if collection is None:
        return []
    now = utc_now()
    return [
        OrganizationInvite.from_dict(doc)
        for doc in collection.find(
            {
                "org_id": org_id,
                "accepted_at": None,
                "revoked_at": None,
                "expires_at": {"$gt": now},
            }
        )
    ]


def _active_org_for_user(user_id: str, org_id: Optional[str]) -> bool:
    """Return whether ``org_id`` is a valid active organization for the user."""
    if not org_id:
        return False
    org = Organization.get(org_id)
    if not org or org.status != ORG_STATUS_ACTIVE:
        return False
    if org.owner_user_id == user_id:
        return True
    return get_membership(org._id, user_id) is not None


def ensure_personal_org(user: User, *, persist: bool = True) -> Organization:
    """Return the user's personal organization, creating it when missing."""
    collection = get_mongodb_collection(ORGANIZATIONS_COLLECTION)
    if collection is None:
        raise OrganizationError("Organization storage is unavailable")

    doc = collection.find_one({"owner_user_id": user._id, "is_personal": True})
    if doc:
        org = Organization.from_dict(doc)
    else:
        org = Organization(
            name=personal_org_name(user),
            owner_user_id=user._id,
            plan=user.plan or "starter",
            cloud_seats=user.cloud_profiles or 0,
            desktop_seats=0,
            linkedin_account_limit=effective_linkedin_account_limit(
                user.plan or "starter",
                user.cloud_profiles or 0,
                user.linkedin_account_limit,
            ),
            whatsapp_account_limit=user.whatsapp_account_limit or 1,
            stripe_customer_id=user.stripe_customer_id,
            stripe_subscription_id=user.stripe_subscription_id,
            is_personal=True,
        )
        org.save()

    members = get_mongodb_collection(MEMBERS_COLLECTION)
    if members is not None:
        existing = members.find_one({"org_id": org._id, "user_id": user._id})
        if not existing:
            OrganizationMember(
                org_id=org._id,
                user_id=user._id,
                email=user.email,
                role=ROLE_OWNER,
                status=STATUS_ACTIVE,
                joined_at=utc_now(),
            ).save()

    if persist and not _active_org_for_user(user._id, user.org_id):
        user.org_id = org._id
        user.save()
    return org


def get_active_org(user: User) -> Organization:
    """Return the user's active organization.

    With team workspaces disabled every user falls back to the personal
    organization for billing and access. Team data is left untouched.
    """
    if not team_workspaces_enabled():
        return ensure_personal_org(user)

    if user.org_id:
        org = Organization.get(user.org_id)
        if org and org.status == ORG_STATUS_ACTIVE:
            if org.owner_user_id == user._id or get_membership(org._id, user._id):
                return org
    return ensure_personal_org(user)


def list_user_orgs(user: User) -> list[Organization]:
    """Return organizations the user can switch to (personal + memberships)."""
    personal = ensure_personal_org(user)
    orgs: dict[str, Organization] = {personal._id: personal}
    members = get_mongodb_collection(MEMBERS_COLLECTION)
    if members is not None:
        for doc in members.find({"user_id": user._id, "status": STATUS_ACTIVE}):
            org = Organization.get(str(doc.get("org_id")))
            if org and org.status == ORG_STATUS_ACTIVE:
                orgs[org._id] = org
    return sorted(orgs.values(), key=lambda org: (not org.is_personal, org.name.lower()))


def activate_org(user: User, org_id: str) -> Organization:
    org = Organization.get(org_id)
    if not org or org.status != ORG_STATUS_ACTIVE:
        raise OrganizationError("Organization not found")
    if org.owner_user_id != user._id and not get_membership(org._id, user._id):
        raise OrganizationPermissionError("You are not a member of this organization")
    user.org_id = org._id
    user.save()
    audit.record_org_audit(
        audit.EVENT_ORG_ACTIVATE,
        org_id=org._id,
        actor_user_id=user._id,
        target_user_id=user._id,
    )
    return org


def _require_actor(org: Organization, actor_user_id: str) -> OrganizationMember:
    member = get_membership(org._id, actor_user_id)
    if member:
        return member
    if org.owner_user_id == actor_user_id:
        # Heal a missing owner membership created before the backfill ran.
        owner = User.get(actor_user_id)
        member = OrganizationMember(
            org_id=org._id,
            user_id=actor_user_id,
            email=owner.email if owner else "",
            role=ROLE_OWNER,
            status=STATUS_ACTIVE,
            joined_at=utc_now(),
        )
        member.save()
        return member
    raise OrganizationPermissionError("You are not a member of this organization")


def _find_active_member_by_email(
    org_id: str, email: str
) -> Optional[OrganizationMember]:
    collection = get_mongodb_collection(MEMBERS_COLLECTION)
    if collection is None:
        return None
    doc = collection.find_one(
        {"org_id": org_id, "email": email.lower().strip(), "status": STATUS_ACTIVE}
    )
    return OrganizationMember.from_dict(doc) if doc else None


def invite_member(
    org: Organization,
    actor_user_id: str,
    email: str,
    role: str = ROLE_MEMBER,
) -> tuple[OrganizationInvite, str]:
    """Create a single-use invite and return ``(invite, raw_token)``.

    Only the SHA-256 hash is stored. The raw token is returned so the caller
    can put it in the invitation email; it must never be logged or persisted.
    """
    actor = _require_actor(org, actor_user_id)
    if not (actor.role == ROLE_OWNER or (actor.role == ROLE_ADMIN and role == ROLE_MEMBER)):
        raise OrganizationPermissionError("Only owners and admins can invite members")
    if role not in (ROLE_ADMIN, ROLE_MEMBER):
        raise OrganizationPermissionError("Invites cannot grant the owner role")
    if actor.role == ROLE_ADMIN and role != ROLE_MEMBER:
        raise OrganizationPermissionError("Admins can only invite members")

    normalized_email = (email or "").lower().strip()
    if not normalized_email or "@" not in normalized_email:
        raise OrganizationError("A valid email address is required")
    if _find_active_member_by_email(org._id, normalized_email):
        raise MemberAlreadyExistsError("That email is already a member of this workspace")

    collection = get_mongodb_collection(INVITES_COLLECTION)
    if collection is None:
        raise OrganizationError("Invite storage is unavailable")

    now = utc_now()
    # One active invite per email/org: revoke older pending invites.
    collection.update_many(
        {
            "org_id": org._id,
            "email": normalized_email,
            "accepted_at": None,
            "revoked_at": None,
        },
        {"$set": {"revoked_at": now}},
    )

    token = secrets.token_urlsafe(32)
    expiry_days = int(getattr(settings, "ORGANIZATION_INVITE_EXPIRY_DAYS", 7) or 7)
    invite = OrganizationInvite(
        org_id=org._id,
        email=normalized_email,
        role=role,
        token_hash=_sha256(token),
        expires_at=now + timedelta(days=expiry_days),
        created_by=actor_user_id,
        created_at=now,
    )
    invite.save()
    audit.record_org_audit(
        audit.EVENT_ORG_INVITE,
        org_id=org._id,
        actor_user_id=actor_user_id,
        target_email=normalized_email,
        metadata={"role": role, "invite_id": invite._id},
    )
    return invite, token


def get_invite_by_token(token: str) -> OrganizationInvite:
    collection = get_mongodb_collection(INVITES_COLLECTION)
    if collection is None:
        raise OrganizationError("Invite storage is unavailable")
    doc = collection.find_one({"token_hash": _sha256(token)})
    if not doc:
        raise InviteInvalidError("Invite is invalid or has expired")
    invite = OrganizationInvite.from_dict(doc)
    if not invite.is_pending():
        raise InviteInvalidError("Invite is invalid or has expired")
    return invite


def accept_invite(token: str, user: User) -> tuple[Organization, OrganizationMember]:
    invite = get_invite_by_token(token)
    return _accept_invite(invite, user)


def accept_invite_by_hash(token_hash: str, user: User) -> tuple[Organization, OrganizationMember]:
    collection = get_mongodb_collection(INVITES_COLLECTION)
    if collection is None:
        raise OrganizationError("Invite storage is unavailable")
    doc = collection.find_one({"token_hash": token_hash})
    if not doc:
        raise InviteInvalidError("Invite is invalid or has expired")
    invite = OrganizationInvite.from_dict(doc)
    if not invite.is_pending():
        raise InviteInvalidError("Invite is invalid or has expired")
    return _accept_invite(invite, user)


def _accept_invite(
    invite: OrganizationInvite, user: User
) -> tuple[Organization, OrganizationMember]:
    if invite.email != (user.email or "").lower().strip():
        raise InviteEmailMismatchError(
            "This invitation was sent to a different email address"
        )
    org = Organization.get(invite.org_id)
    if not org or org.status != ORG_STATUS_ACTIVE:
        raise InviteInvalidError("The workspace is no longer available")

    # Consume the token atomically so two concurrent accepts cannot both win.
    collection = get_mongodb_collection(INVITES_COLLECTION)
    if collection is None:
        raise OrganizationError("Invite storage is unavailable")
    now = utc_now()
    consumed = collection.find_one_and_update(
        {
            "_id": invite._id,
            "accepted_at": None,
            "revoked_at": None,
            "expires_at": {"$gt": now},
        },
        {"$set": {"accepted_at": now}},
        return_document=True,
    )
    if not consumed:
        raise InviteInvalidError("Invite is invalid or has expired")

    members = get_mongodb_collection(MEMBERS_COLLECTION)
    if members is None:
        raise OrganizationError("Member storage is unavailable")
    existing = members.find_one({"org_id": org._id, "user_id": user._id})
    if existing:
        members.update_one(
            {"_id": existing["_id"]},
            {
                "$set": {
                    "email": user.email,
                    "role": invite.role,
                    "status": STATUS_ACTIVE,
                    "joined_at": existing.get("joined_at") or now,
                }
            },
        )
        member = OrganizationMember.from_dict(
            members.find_one({"_id": existing["_id"]}) or {}
        )
    else:
        member = OrganizationMember(
            org_id=org._id,
            user_id=user._id,
            email=user.email,
            role=invite.role,
            status=STATUS_ACTIVE,
            invited_by=invite.created_by,
            invited_at=invite.created_at,
            joined_at=now,
        )
        member.save()

    user.org_id = org._id
    user.save()
    audit.record_org_audit(
        audit.EVENT_ORG_ACCEPT,
        org_id=org._id,
        actor_user_id=user._id,
        target_user_id=user._id,
        target_email=user.email,
        metadata={"role": member.role, "invite_id": invite._id},
    )
    return org, member


def revoke_invite(org: Organization, actor_user_id: str, invite_id: str) -> None:
    actor = _require_actor(org, actor_user_id)
    if actor.role not in (ROLE_OWNER, ROLE_ADMIN):
        raise OrganizationPermissionError("Only owners and admins can revoke invites")
    collection = get_mongodb_collection(INVITES_COLLECTION)
    if collection is None:
        raise OrganizationError("Invite storage is unavailable")
    result = collection.update_one(
        {
            "_id": invite_id,
            "org_id": org._id,
            "accepted_at": None,
            "revoked_at": None,
        },
        {"$set": {"revoked_at": utc_now()}},
    )
    if getattr(result, "matched_count", 0) == 0:
        raise InviteInvalidError("Invite not found")
    audit.record_org_audit(
        "org.invite_revoke",
        org_id=org._id,
        actor_user_id=actor_user_id,
        metadata={"invite_id": invite_id},
    )


def change_member_role(
    org: Organization,
    actor_user_id: str,
    target_user_id: str,
    role: str,
) -> OrganizationMember:
    actor = _require_actor(org, actor_user_id)
    target = get_membership(org._id, target_user_id)
    if not target:
        raise MemberNotFoundError("Member not found")
    if not can_manage_member(actor.role, target.role):
        raise OrganizationPermissionError("You cannot change that member's role")
    if not can_assign_role(actor.role, role):
        raise OrganizationPermissionError("Only the owner can change roles")
    if role == target.role:
        return target
    collection = get_mongodb_collection(MEMBERS_COLLECTION)
    if collection is None:
        raise OrganizationError("Member storage is unavailable")
    collection.update_one(
        {"_id": target._id, "org_id": org._id},
        {"$set": {"role": role}},
    )
    target.role = role
    audit.record_org_audit(
        audit.EVENT_ORG_ROLE_CHANGE,
        org_id=org._id,
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        target_email=target.email,
        metadata={"role": role},
    )
    return target


def _pause_profile_for_seat_removal(profile_id: str) -> bool:
    """Pause a profile and clear its assignee while retaining its proxy."""
    collection = get_mongodb_collection(_PROFILES_COLLECTION)
    if collection is None:
        return False
    result = collection.update_one(
        {"_id": profile_id},
        {
            "$set": {
                "assigned_user_id": None,
                "active": False,
                "is_active": False,
                "daemon_status": "seat_removed",
                "updated_at": utc_now(),
            }
        },
    )
    if getattr(result, "modified_count", 0):
        # Phase 2: disable the Massive sub-account but keep it bound to this
        # profile so the same identity can resume later.
        from openoutreach.proxies.provisioning import disable_massive_for_profile

        disable_massive_for_profile(profile_id, reason="member_removed")
    return bool(getattr(result, "modified_count", 0))


def remove_member(
    org: Organization, actor_user_id: str, target_user_id: str
) -> int:
    actor = _require_actor(org, actor_user_id)
    target = get_membership(org._id, target_user_id)
    if not target:
        raise MemberNotFoundError("Member not found")
    if target.role == ROLE_OWNER:
        raise OrganizationPermissionError("The workspace owner cannot be removed")
    if not can_manage_member(actor.role, target.role):
        raise OrganizationPermissionError("You cannot remove that member")

    collection = get_mongodb_collection(MEMBERS_COLLECTION)
    if collection is None:
        raise OrganizationError("Member storage is unavailable")
    collection.update_one(
        {"_id": target._id, "org_id": org._id},
        {"$set": {"status": STATUS_REMOVED}},
    )

    profiles = get_mongodb_collection(_PROFILES_COLLECTION)
    paused = 0
    if profiles is not None:
        assigned = list(
            profiles.find(
                {
                    "$or": [
                        {"org_id": org._id, "assigned_user_id": target_user_id},
                        {
                            "user_id": target_user_id,
                            "assigned_user_id": target_user_id,
                            "$or": [
                                {"org_id": {"$exists": False}},
                                {"org_id": None},
                            ],
                        },
                    ]
                },
                {"_id": 1, "linkedin_username": 1, "proxy_id": 1, "proxy_mode": 1},
            )
        )
        for profile in assigned:
            profile_id = str(profile.get("_id"))
            if _pause_profile_for_seat_removal(profile_id):
                paused += 1
                audit.record_org_audit(
                    audit.EVENT_SEAT_REMOVE,
                    org_id=org._id,
                    actor_user_id=actor_user_id,
                    target_user_id=target_user_id,
                    target_email=target.email,
                    metadata={
                        "profile_id": profile_id,
                        "reason": "member_removed",
                        "proxy_retained": bool(
                            profile.get("proxy_id") or profile.get("proxy_mode")
                        ),
                    },
                )

    # Revoke the member's desktop devices and clear channel assignments. The
    # data stays in the workspace for owner/admin reassignment; the removed
    # member falls back to their personal workspace.
    devices = get_mongodb_collection("daemon_devices")
    families = get_mongodb_collection("daemon_refresh_families")
    if devices is not None:
        revoked_devices = list(
            devices.find(
                {"user_id": target_user_id, "org_id": org._id, "revoked": False},
                {"_id": 1},
            )
        )
        device_ids = [str(doc["_id"]) for doc in revoked_devices]
        if device_ids:
            devices.update_many(
                {"_id": {"$in": device_ids}},
                {"$set": {"revoked": True, "revoked_at": utc_now()}},
            )
            if families is not None:
                families.update_many(
                    {"device_id": {"$in": device_ids}},
                    {"$set": {"revoked": True}},
                )
    for collection_name in ("whatsapp_profiles", "mailboxes"):
        channel_collection = get_mongodb_collection(collection_name)
        if channel_collection is not None:
            channel_collection.update_many(
                {"org_id": org._id, "assigned_user_id": target_user_id},
                {"$set": {"assigned_user_id": None}},
            )

    # Move the removed member back to their personal workspace so they keep a
    # valid billing context. Their org data is retained for audit/support.
    target_user = User.get(target_user_id)
    if target_user is not None:
        personal = ensure_personal_org(target_user, persist=False)
        target_user.org_id = personal._id
        target_user.save()

    audit.record_org_audit(
        audit.EVENT_ORG_REMOVE,
        org_id=org._id,
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        target_email=target.email,
        metadata={"paused_profiles": paused},
    )
    return paused


def org_seat_limit(org: Organization) -> int:
    """Return the cloud seat pool for an organization."""
    owner = User.get(org.owner_user_id)
    if org.seat_override:
        return effective_cloud_seat_limit(org.plan, org.cloud_seats)
    if owner is not None:
        return effective_cloud_seat_limit(owner.plan, owner.cloud_profiles)
    return effective_cloud_seat_limit(org.plan, org.cloud_seats)


def _org_profile(org: Organization, profile_id: str) -> Optional[dict[str, Any]]:
    collection = get_mongodb_collection(_PROFILES_COLLECTION)
    if collection is None:
        raise OrganizationError("LinkedIn profile storage is unavailable")
    doc = collection.find_one({"_id": profile_id, "org_id": org._id})
    if doc:
        return doc
    # Pre-migration profiles may not have org_id yet. Only heal when the
    # profile's owner is an active member of this organization.
    member_ids = [member.user_id for member in list_active_members(org._id)]
    if not member_ids:
        return None
    legacy = collection.find_one({"_id": profile_id, "user_id": {"$in": member_ids}})
    if legacy and not legacy.get("org_id"):
        collection.update_one(
            {
                "_id": profile_id,
                "$or": [
                    {"org_id": {"$exists": False}},
                    {"org_id": None},
                ],
            },
            {"$set": {"org_id": org._id, "updated_at": utc_now()}},
        )
        legacy["org_id"] = org._id
        return legacy
    return None


def assign_seat(
    org: Organization,
    actor_user_id: str,
    profile_id: str,
    assigned_user_id: str,
) -> dict[str, Any]:
    actor = _require_actor(org, actor_user_id)
    if not can_assign_seats(actor.role):
        raise OrganizationPermissionError("Only owners and admins can assign seats")
    target = get_membership(org._id, assigned_user_id)
    if not target:
        raise MemberNotFoundError("Assigned member not found in this workspace")

    profile = _org_profile(org, profile_id)
    if not profile:
        raise SeatAssignmentError("LinkedIn profile not found in this workspace")
    if profile.get("execution_mode") != "cloud":
        raise SeatAssignmentError("Only cloud LinkedIn profiles use cloud seats")
    if profile.get("assigned_user_id") == assigned_user_id:
        return profile

    profiles = get_mongodb_collection(_PROFILES_COLLECTION)
    if profiles is None:
        raise OrganizationError("LinkedIn profile storage is unavailable")

    # Count every credentialed cloud account in the org, active or paused.
    credentialed = credentialed_profile_ids_for_org(
        org._id, execution_mode="cloud"
    )
    if credentialed is None:
        raise OrganizationError("Seat accounting is unavailable")
    seat_limit = org_seat_limit(org)
    other_credentialed = {
        pid for pid in credentialed if pid != profile_id
    }
    if len(other_credentialed) >= seat_limit:
        raise SeatLimitError(
            f"Cloud seat limit reached ({len(other_credentialed)}/{seat_limit})"
        )

    updates: dict[str, Any] = {
        "assigned_user_id": assigned_user_id,
        "org_id": org._id,
        "updated_at": utc_now(),
    }
    # Reassigning a seat resumes the account only when it still has its proxy.
    if profile.get("proxy_server") or profile.get("proxy_id"):
        updates["active"] = True
        updates["is_active"] = True
        updates["daemon_status"] = "seat_assigned"
    profiles.update_one({"_id": profile_id, "org_id": org._id}, {"$set": updates})
    profile.update(updates)

    # Phase 2: a re-added seat re-enables only the same profile's disabled
    # sub-account. Budget-disabled accounts stay disabled until the budget
    # review re-enables them.
    from openoutreach.proxies.provisioning import enable_massive_for_profile

    enable_massive_for_profile(profile_id, actor_user_id=actor_user_id)

    # Keep the proxy's assignment metadata aligned with the seat holder. The
    # proxy itself stays attached to this profile and is never recycled.
    proxy_id = profile.get("proxy_id")
    if proxy_id:
        proxies = get_mongodb_collection("proxies")
        if proxies is not None:
            try:
                proxies.update_one(
                    {"_id": proxy_id, "linkedin_profile_id": profile_id},
                    {
                        "$set": {
                            "assigned_user_id": assigned_user_id,
                            "assigned_org_id": org._id,
                            "updated_at": utc_now(),
                        }
                    },
                )
            except Exception as exc:  # pragma: no cover - audit/metadata only
                logger.warning(
                    "proxy_seat_metadata_update_failed profile_id=%s exception_type=%s",
                    profile_id,
                    type(exc).__name__,
                )

    audit.record_org_audit(
        audit.EVENT_SEAT_ASSIGN,
        org_id=org._id,
        actor_user_id=actor_user_id,
        target_user_id=assigned_user_id,
        target_email=target.email,
        metadata={
            "profile_id": profile_id,
            "linkedin_username": profile.get("linkedin_username"),
        },
    )
    return profile


def assign_desktop_profile(
    org: Organization,
    actor_user_id: str,
    profile_id: str,
    assigned_user_id: str,
) -> dict[str, Any]:
    """Assign an org-owned desktop profile to a member.

    Desktop profiles run on the member's device with the local IP. They do not
    consume a cloud seat and never receive a proxy.
    """
    actor = _require_actor(org, actor_user_id)
    if not can_assign_seats(actor.role):
        raise OrganizationPermissionError("Only owners and admins can assign desktop profiles")
    target = get_membership(org._id, assigned_user_id)
    if not target:
        raise MemberNotFoundError("Assigned member not found in this workspace")
    profile = _org_profile(org, profile_id)
    if not profile:
        raise SeatAssignmentError("LinkedIn profile not found in this workspace")
    if profile.get("execution_mode") == "cloud":
        raise SeatAssignmentError("Cloud profiles use cloud seats")
    if profile.get("execution_mode", "desktop") != "desktop":
        raise SeatAssignmentError("Only desktop LinkedIn profiles use desktop assignment")

    profiles = get_mongodb_collection(_PROFILES_COLLECTION)
    if profiles is None:
        raise OrganizationError("LinkedIn profile storage is unavailable")
    profiles.update_one(
        {"_id": profile_id, "org_id": org._id},
        {
            "$set": {
                "assigned_user_id": assigned_user_id,
                "org_id": org._id,
                "updated_at": utc_now(),
            }
        },
    )
    profile["assigned_user_id"] = assigned_user_id
    audit.record_org_audit(
        audit.EVENT_SEAT_ASSIGN,
        org_id=org._id,
        actor_user_id=actor_user_id,
        target_user_id=assigned_user_id,
        target_email=target.email,
        metadata={
            "profile_id": profile_id,
            "linkedin_username": profile.get("linkedin_username"),
            "seat_type": "desktop",
        },
    )
    return profile


def unassign_seat(
    org: Organization,
    actor_user_id: str,
    profile_id: str,
    *,
    event: str = audit.EVENT_SEAT_UNASSIGN,
    reason: str = "seat_unassigned",
) -> dict[str, Any]:
    actor = _require_actor(org, actor_user_id)
    if not can_assign_seats(actor.role):
        raise OrganizationPermissionError("Only owners and admins can unassign seats")
    profile = _org_profile(org, profile_id)
    if not profile:
        raise SeatAssignmentError("LinkedIn profile not found in this workspace")

    profiles = get_mongodb_collection(_PROFILES_COLLECTION)
    if profiles is None:
        raise OrganizationError("LinkedIn profile storage is unavailable")
    previous_assignee = profile.get("assigned_user_id")
    profiles.update_one(
        {"_id": profile_id, "org_id": org._id},
        {
            "$set": {
                "assigned_user_id": None,
                "active": False,
                "is_active": False,
                "daemon_status": "seat_unassigned",
                "updated_at": utc_now(),
            }
        },
    )
    audit.record_org_audit(
        event,
        org_id=org._id,
        actor_user_id=actor_user_id,
        target_user_id=previous_assignee,
        metadata={
            "profile_id": profile_id,
            "reason": reason,
            # The proxy remains assigned by design; only profile deletion
            # retires it.
            "proxy_retained": bool(profile.get("proxy_id") or profile.get("proxy_mode")),
        },
    )
    from openoutreach.proxies.provisioning import disable_massive_for_profile

    disable_massive_for_profile(
        profile_id, actor_user_id=actor_user_id, reason=reason
    )
    profile["assigned_user_id"] = None
    profile["active"] = False
    profile["is_active"] = False
    return profile


def remove_seat(
    org: Organization, actor_user_id: str, profile_id: str
) -> dict[str, Any]:
    return unassign_seat(
        org,
        actor_user_id,
        profile_id,
        event=audit.EVENT_SEAT_REMOVE,
        reason="seat_removed",
    )


def seat_summary(org: Organization) -> dict[str, Any]:
    profiles = get_mongodb_collection(_PROFILES_COLLECTION)
    org_profiles: list[dict[str, Any]] = []
    if profiles is not None:
        org_profiles = list(
            profiles.find(
                {"org_id": org._id},
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
        )
    credentialed = credentialed_profile_ids_for_org(org._id) or set()
    cloud_profiles = [
        profile
        for profile in org_profiles
        if profile.get("execution_mode") == "cloud"
    ]
    assigned = [p for p in cloud_profiles if p.get("assigned_user_id")]
    unassigned = [p for p in cloud_profiles if not p.get("assigned_user_id")]
    return {
        "cloud_seat_limit": org_seat_limit(org),
        "cloud_profiles": len(cloud_profiles),
        "credentialed_profiles": len(credentialed),
        "assigned_profiles": len(assigned),
        "unassigned_profiles": len(unassigned),
        "members": len(list_active_members(org._id)),
    }


def sync_org_billing_from_user(user: User) -> None:
    """Mirror the owner's billing state onto the organizations they own."""
    collection = get_mongodb_collection(ORGANIZATIONS_COLLECTION)
    if collection is None:
        return
    try:
        now = utc_now()
        for doc in collection.find({"owner_user_id": user._id}):
            org = Organization.from_dict(doc)
            updates: dict[str, Any] = {
                "plan": user.plan,
                "stripe_customer_id": user.stripe_customer_id,
                "stripe_subscription_id": user.stripe_subscription_id,
                "whatsapp_account_limit": user.whatsapp_account_limit,
                "updated_at": now,
            }
            if not org.seat_override:
                updates["cloud_seats"] = user.cloud_profiles or 0
                updates["linkedin_account_limit"] = effective_linkedin_account_limit(
                    user.plan,
                    user.cloud_profiles,
                    user.linkedin_account_limit,
                )
            collection.update_one({"_id": org._id}, {"$set": updates})
    except Exception as exc:  # pragma: no cover - billing must not fail on mirror
        logger.warning(
            "organization_billing_sync_failed user_id=%s exception_type=%s",
            user._id,
            type(exc).__name__,
        )


def apply_seat_override(
    org: Organization,
    admin_user_id: str,
    cloud_seats: int,
    reason: str,
    *,
    plan: Optional[str] = None,
) -> Organization:
    """Admin-only seat/plan override. Audited; does not change Stripe."""
    if cloud_seats < 0:
        raise OrganizationError("Seat count cannot be negative")
    collection = get_mongodb_collection(ORGANIZATIONS_COLLECTION)
    if collection is None:
        raise OrganizationError("Organization storage is unavailable")
    new_plan = plan or org.plan
    from openoutreach.billing.plans import get_plan

    plan_def = get_plan(new_plan)
    fallback_limit = (
        int(plan_def.get("max_linkedin_accounts", org.linkedin_account_limit))
        if plan_def
        else org.linkedin_account_limit
    )
    linkedin_limit = effective_linkedin_account_limit(
        new_plan, cloud_seats, fallback_limit
    )
    collection.update_one(
        {"_id": org._id},
        {
            "$set": {
                "plan": new_plan,
                "cloud_seats": cloud_seats,
                "linkedin_account_limit": linkedin_limit,
                "seat_override": True,
                "updated_at": utc_now(),
            }
        },
    )
    audit.record_org_audit(
        audit.EVENT_SEAT_OVERRIDE,
        org_id=org._id,
        actor_user_id=admin_user_id,
        metadata={
            "cloud_seats": cloud_seats,
            "plan": new_plan,
            "reason": reason[:500],
        },
    )
    org.plan = new_plan
    org.cloud_seats = cloud_seats
    org.linkedin_account_limit = linkedin_limit
    org.seat_override = True
    org.updated_at = utc_now()
    return org


def backfill_personal_orgs(*, dry_run: bool = True) -> dict[str, int]:
    """Create personal orgs and backfill org ownership on existing records.

    Idempotent and additive. ``dry_run`` reports what would change without
    writing anything.
    """
    users_collection = get_mongodb_collection("users")
    orgs_collection = get_mongodb_collection(ORGANIZATIONS_COLLECTION)
    members_collection = get_mongodb_collection(MEMBERS_COLLECTION)
    profiles_collection = get_mongodb_collection(_PROFILES_COLLECTION)
    campaigns_collection = get_mongodb_collection(_CAMPAIGNS_COLLECTION)
    whatsapp_collection = get_mongodb_collection("whatsapp_profiles")
    mailboxes_collection = get_mongodb_collection("mailboxes")
    if users_collection is None or orgs_collection is None or members_collection is None:
        raise OrganizationError("Organization storage is unavailable")

    summary = {
        "users_scanned": 0,
        "orgs_created": 0,
        "users_linked": 0,
        "members_created": 0,
        "profiles_backfilled": 0,
        "campaigns_backfilled": 0,
        "channels_backfilled": 0,
    }

    for user_doc in users_collection.find({}):
        summary["users_scanned"] += 1
        user = User.from_dict(user_doc)
        org_doc = orgs_collection.find_one(
            {"owner_user_id": user._id, "is_personal": True}
        )
        if org_doc:
            org = Organization.from_dict(org_doc)
        else:
            summary["orgs_created"] += 1
            org = Organization(
                name=personal_org_name(user),
                owner_user_id=user._id,
                plan=user.plan or "starter",
                cloud_seats=user.cloud_profiles or 0,
                linkedin_account_limit=effective_linkedin_account_limit(
                    user.plan or "starter",
                    user.cloud_profiles or 0,
                    user.linkedin_account_limit,
                ),
                whatsapp_account_limit=user.whatsapp_account_limit or 1,
                stripe_customer_id=user.stripe_customer_id,
                stripe_subscription_id=user.stripe_subscription_id,
                is_personal=True,
            )
            if not dry_run:
                org.save()

        if not _active_org_for_user(user._id, user.org_id):
            summary["users_linked"] += 1
            if not dry_run:
                users_collection.update_one(
                    {"_id": user._id}, {"$set": {"org_id": org._id}}
                )

        if not members_collection.find_one({"org_id": org._id, "user_id": user._id}):
            summary["members_created"] += 1
            if not dry_run:
                OrganizationMember(
                    org_id=org._id,
                    user_id=user._id,
                    email=user.email,
                    role=ROLE_OWNER,
                    status=STATUS_ACTIVE,
                    joined_at=utc_now(),
                ).save()

        if profiles_collection is not None:
            profile_filter = {
                "user_id": user._id,
                "$or": [
                    {"org_id": {"$exists": False}},
                    {"org_id": None},
                ],
            }
            count = profiles_collection.count_documents(profile_filter)
            summary["profiles_backfilled"] += count
            if count and not dry_run:
                profiles_collection.update_many(
                    profile_filter,
                    {"$set": {"org_id": org._id, "updated_at": utc_now()}},
                )
                profiles_collection.update_many(
                    {
                        "user_id": user._id,
                        "assigned_user_id": {"$exists": False},
                    },
                    {"$set": {"assigned_user_id": user._id}},
                )

        if campaigns_collection is not None:
            campaign_filter = {
                "user_id": user._id,
                "$or": [
                    {"org_id": {"$exists": False}},
                    {"org_id": None},
                ],
            }
            count = campaigns_collection.count_documents(campaign_filter)
            summary["campaigns_backfilled"] += count
            if count and not dry_run:
                campaigns_collection.update_many(
                    campaign_filter,
                    {"$set": {"org_id": org._id}},
                )

        # Org-owned WhatsApp numbers and mailboxes. Keep the row owner as the
        # accounting owner (the workspace owner) while preserving the creator
        # as the assignee so member visibility stays narrow.
        for channel_collection in (whatsapp_collection, mailboxes_collection):
            if channel_collection is None:
                continue
            channel_filter = {
                "user_id": user._id,
                "$or": [
                    {"org_id": {"$exists": False}},
                    {"org_id": None},
                ],
            }
            count = channel_collection.count_documents(channel_filter)
            summary["channels_backfilled"] += count
            if count and not dry_run:
                channel_collection.update_many(
                    channel_filter,
                    {
                        "$set": {
                            "org_id": org._id,
                            "assigned_user_id": user._id,
                            "user_id": org.owner_user_id,
                        }
                    },
                )

    logger.info(
        "organization_backfill dry_run=%s summary=%s",
        dry_run,
        summary,
    )
    return summary
