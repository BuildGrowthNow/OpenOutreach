"""Phase 3A organization, invite, role, and seat tests.

These tests use an in-memory Mongo fake so they exercise the real service
predicates (org scope, atomic counter updates, invite single-use) without
requiring a live database.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from openoutreach.api_v2.routers import organizations as organizations_router
from openoutreach.billing import seats as seat_accounting
from openoutreach.billing.enforcement import PlanEnforcer
from openoutreach.mongodb.models_user import User
from openoutreach.organizations import audit
from openoutreach.organizations.access import (
    can_access_profile_doc,
    campaign_access_query,
    campaign_has_access,
    profile_access_query,
    resolve_org_context,
)
from openoutreach.organizations.enforcement import resolve_effective_plan
from openoutreach.organizations.models import (
    INVITES_COLLECTION,
    MEMBERS_COLLECTION,
    ORGANIZATIONS_COLLECTION,
    ROLE_ADMIN,
    ROLE_MEMBER,
    ROLE_OWNER,
    STATUS_ACTIVE,
    OrganizationMember,
)
from openoutreach.organizations.permissions import (
    can_assign_seats,
    can_change_roles,
    can_manage_billing,
    can_manage_member,
    can_manage_proxies,
    can_view_billing,
)
from openoutreach.organizations.service import (
    InviteEmailMismatchError,
    InviteInvalidError,
    MemberAlreadyExistsError,
    OrganizationPermissionError,
    accept_invite,
    apply_seat_override,
    assign_seat,
    backfill_personal_orgs,
    ensure_personal_org,
    get_invite_by_token,
    invite_member,
    list_active_members,
    remove_member,
    remove_seat,
    revoke_invite,
    seat_summary,
    sync_org_billing_from_user,
    unassign_seat,
)
from tests.fake_mongo import FakeMongo

PATCH_TARGETS = [
    "openoutreach.organizations.models.get_mongodb_collection",
    "openoutreach.organizations.service.get_mongodb_collection",
    "openoutreach.organizations.access.get_mongodb_collection",
    "openoutreach.organizations.audit.get_mongodb_collection",
    "openoutreach.organizations.rate_limit.get_mongodb_collection",
    "openoutreach.billing.seats.get_mongodb_collection",
    "openoutreach.billing.enforcement.get_mongodb_collection",
    "openoutreach.mongodb.models_user.get_mongodb_collection",
    "openoutreach.api_v2.routers.organizations.get_mongodb_collection",
]


@pytest.fixture
def fake(monkeypatch):
    mongo = FakeMongo()
    for target in PATCH_TARGETS:
        monkeypatch.setattr(target, mongo.get_mongodb_collection)
    return mongo


@pytest.fixture
def team_enabled(monkeypatch):
    from openoutreach.config import settings

    monkeypatch.setattr(settings, "TEAM_WORKSPACES_ENABLED", True)


def make_user(
    fake: FakeMongo,
    user_id: str,
    email: str,
    *,
    plan: str = "cloud",
    cloud_profiles: int = 1,
    subscription_status: str = "active",
    org_id=None,
) -> User:
    user = User(
        _id=user_id,
        email=email,
        full_name=user_id,
        plan=plan,
        cloud_profiles=cloud_profiles,
        linkedin_account_limit=1 + cloud_profiles if plan == "cloud" else 1,
        subscription_status=subscription_status,
        org_id=org_id,
        email_verified=True,
    )
    fake.collection("users").insert_one(user.to_dict())
    return user


def add_member(fake: FakeMongo, org_id: str, user: User, role: str) -> OrganizationMember:
    member = OrganizationMember(
        org_id=org_id,
        user_id=user._id,
        email=user.email,
        role=role,
        status=STATUS_ACTIVE,
        joined_at=datetime.now(timezone.utc),
    )
    member.save()
    return member


def add_profile(
    fake: FakeMongo,
    profile_id: str,
    user_id: str,
    org_id: str,
    *,
    execution_mode: str = "cloud",
    assigned_user_id=None,
    active: bool = True,
    proxy: bool = False,
    credentialed: bool = True,
) -> dict:
    doc = {
        "_id": profile_id,
        "user_id": user_id,
        "org_id": org_id,
        "assigned_user_id": assigned_user_id or user_id,
        "linkedin_username": f"{profile_id}@example.com",
        "execution_mode": execution_mode,
        "active": active,
        "is_active": active,
        "proxy_id": f"proxy-{profile_id}" if proxy else None,
        "proxy_server": "http://proxy.example.com:8080" if proxy else None,
        "proxy_mode": "managed" if proxy else "none",
        "created_at": datetime.now(timezone.utc),
    }
    fake.collection("linkedin_profiles").insert_one(doc)
    if credentialed:
        fake.collection("linkedin_credentials").insert_one(
            {
                "_id": f"cred-{profile_id}",
                "linkedin_profile_id": profile_id,
                "user_id": user_id,
                "status": "active",
            }
        )
    return doc


def test_personal_org_backfill_dry_run_writes_nothing(fake):
    make_user(fake, "u1", "owner@example.com", plan="starter", cloud_profiles=0)
    fake.collection("linkedin_profiles").insert_one(
        {"_id": "p1", "user_id": "u1", "linkedin_username": "legacy"}
    )

    summary = backfill_personal_orgs(dry_run=True)

    assert summary["orgs_created"] == 1
    assert summary["profiles_backfilled"] == 1
    assert fake.collection(ORGANIZATIONS_COLLECTION).count_documents({}) == 0
    assert fake.collection(MEMBERS_COLLECTION).count_documents({}) == 0
    assert fake.collection("users").find_one({"_id": "u1"}).get("org_id") is None
    assert fake.collection("linkedin_profiles").find_one({"_id": "p1"}).get("org_id") is None


def test_personal_org_backfill_is_idempotent(fake):
    user = make_user(fake, "u1", "owner@example.com", plan="starter", cloud_profiles=0)
    fake.collection("linkedin_profiles").insert_one(
        {
            "_id": "p1",
            "user_id": "u1",
            "linkedin_username": "legacy",
            "execution_mode": "desktop",
        }
    )
    fake.collection("campaigns").insert_one({"_id": "c1", "user_id": "u1", "name": "legacy"})

    first = backfill_personal_orgs(dry_run=False)
    second = backfill_personal_orgs(dry_run=False)

    assert first["orgs_created"] == 1
    assert first["users_linked"] == 1
    assert first["members_created"] == 1
    assert first["profiles_backfilled"] == 1
    assert first["campaigns_backfilled"] == 1
    assert second["orgs_created"] == 0
    assert second["users_linked"] == 0
    assert second["members_created"] == 0

    org = fake.collection(ORGANIZATIONS_COLLECTION).find_one({"owner_user_id": "u1"})
    assert org is not None and org["is_personal"] is True
    assert fake.collection("users").find_one({"_id": "u1"})["org_id"] == org["_id"]
    assert fake.collection(MEMBERS_COLLECTION).find_one(
        {"org_id": org["_id"], "user_id": "u1"}
    )["role"] == ROLE_OWNER
    assert fake.collection("linkedin_profiles").find_one({"_id": "p1"})["org_id"] == org["_id"]
    assert fake.collection("linkedin_profiles").find_one({"_id": "p1"})[
        "assigned_user_id"
    ] == "u1"
    assert fake.collection("campaigns").find_one({"_id": "c1"})["org_id"] == org["_id"]


def test_invite_lifecycle_hashes_token_and_is_single_use(fake, team_enabled):
    owner = make_user(fake, "owner", "owner@example.com")
    org = ensure_personal_org(owner)
    invite, token = invite_member(org, owner._id, "member@example.com", ROLE_MEMBER)

    stored = fake.collection(INVITES_COLLECTION).find_one({"_id": invite._id})
    assert stored["token_hash"] == hashlib.sha256(token.encode()).hexdigest()
    assert stored["token_hash"] != token
    assert len(stored["token_hash"]) == 64
    assert stored["accepted_at"] is None

    member = make_user(
        fake, "member", "member@example.com", plan="starter", cloud_profiles=0,
        subscription_status="none",
    )
    accepted_org, membership = accept_invite(token, member)

    assert accepted_org._id == org._id
    assert membership.role == ROLE_MEMBER
    assert membership.status == STATUS_ACTIVE
    assert fake.collection("users").find_one({"_id": "member"})["org_id"] == org._id
    assert fake.collection(INVITES_COLLECTION).find_one({"_id": invite._id})[
        "accepted_at"
    ] is not None

    with pytest.raises(InviteInvalidError):
        accept_invite(token, member)

    events = {doc["event"] for doc in fake.collection(audit.AUDIT_COLLECTION).find({})}
    assert "org.invite" in events
    assert "org.accept" in events


def test_one_active_invite_per_email(fake, team_enabled):
    owner = make_user(fake, "owner", "owner@example.com")
    org = ensure_personal_org(owner)
    first, _ = invite_member(org, owner._id, "member@example.com", ROLE_MEMBER)
    second, _ = invite_member(org, owner._id, "member@example.com", ROLE_ADMIN)

    first_doc = fake.collection(INVITES_COLLECTION).find_one({"_id": first._id})
    assert first_doc["revoked_at"] is not None
    assert fake.collection(INVITES_COLLECTION).find_one({"_id": second._id})[
        "revoked_at"
    ] is None

    with pytest.raises(MemberAlreadyExistsError):
        member = make_user(fake, "member", "member@example.com")
        add_member(fake, org._id, member, ROLE_MEMBER)
        invite_member(org, owner._id, "member@example.com", ROLE_MEMBER)


def test_role_permissions_matrix():
    assert can_view_billing(ROLE_OWNER) and can_view_billing(ROLE_ADMIN)
    assert not can_view_billing(ROLE_MEMBER)
    assert can_manage_billing(ROLE_OWNER)
    assert not can_manage_billing(ROLE_ADMIN)
    assert can_change_roles(ROLE_OWNER)
    assert not can_change_roles(ROLE_ADMIN)
    assert can_assign_seats(ROLE_OWNER) and can_assign_seats(ROLE_ADMIN)
    assert not can_assign_seats(ROLE_MEMBER)
    assert can_manage_proxies(ROLE_ADMIN) and not can_manage_proxies(ROLE_MEMBER)
    assert can_manage_member(ROLE_OWNER, ROLE_ADMIN)
    assert can_manage_member(ROLE_ADMIN, ROLE_MEMBER)
    assert not can_manage_member(ROLE_ADMIN, ROLE_ADMIN)
    assert not can_manage_member(ROLE_OWNER, ROLE_OWNER)


def test_member_inherits_owner_plan_and_seat_pool(fake, team_enabled):
    owner = make_user(
        fake, "owner", "owner@example.com", plan="cloud", cloud_profiles=2
    )
    org = ensure_personal_org(owner)
    member = make_user(
        fake, "member", "member@example.com", plan="starter", cloud_profiles=0,
        subscription_status="none", org_id=org._id,
    )
    add_member(fake, org._id, member, ROLE_MEMBER)

    effective = resolve_effective_plan(member)
    assert effective.plan == "cloud"
    assert effective.cloud_profiles == 2
    assert effective.linkedin_account_limit == 3
    assert effective.cloud_seat_limit == 3
    assert effective.billing_owner_id == "owner"
    assert effective.is_billing_owner is False
    assert effective.is_active is True

    assert PlanEnforcer.can_create_linkedin_account(member)[0] is True


def test_ensure_personal_org_does_not_steal_active_team_org(fake, team_enabled):
    owner = make_user(fake, "owner", "owner@example.com")
    org = ensure_personal_org(owner)
    member = make_user(
        fake, "member", "member@example.com", plan="starter", cloud_profiles=0,
        org_id=org._id,
    )
    add_member(fake, org._id, member, ROLE_MEMBER)

    personal = ensure_personal_org(member)
    assert personal._id != org._id
    assert fake.collection("users").find_one({"_id": "member"})["org_id"] == org._id
    assert resolve_org_context(member).org_id == org._id


def test_invite_acceptance_by_hash_after_email_verification(fake, team_enabled):
    owner = make_user(fake, "owner", "owner@example.com")
    org = ensure_personal_org(owner)
    invite, token = invite_member(org, owner._id, "new@example.com", ROLE_MEMBER)
    new_user = make_user(
        fake, "new", "new@example.com", plan="starter", cloud_profiles=0,
        subscription_status="none",
    )
    new_user.pending_org_invite_hash = hashlib.sha256(token.encode()).hexdigest()

    from openoutreach.organizations.service import accept_invite_by_hash

    accepted_org, member = accept_invite_by_hash(new_user.pending_org_invite_hash, new_user)
    assert accepted_org._id == org._id
    assert member.role == ROLE_MEMBER
    assert fake.collection("users").find_one({"_id": "new"})["org_id"] == org._id


def test_feature_flag_rollback_uses_personal_billing(fake, team_enabled, monkeypatch):
    owner = make_user(
        fake, "owner", "owner@example.com", plan="cloud", cloud_profiles=1
    )
    org = ensure_personal_org(owner)
    member = make_user(
        fake, "member", "member@example.com", plan="starter", cloud_profiles=0,
        subscription_status="trialing", org_id=org._id,
    )
    member.trial_ends_at = datetime.now(timezone.utc) + timedelta(days=3)
    fake.collection("users").update_one(
        {"_id": "member"}, {"$set": {"trial_ends_at": member.trial_ends_at}}
    )
    add_member(fake, org._id, member, ROLE_MEMBER)

    assert resolve_effective_plan(member).plan == "cloud"

    from openoutreach.config import settings

    monkeypatch.setattr(settings, "TEAM_WORKSPACES_ENABLED", False)
    effective = resolve_effective_plan(member)
    assert effective.plan == "starter"
    assert effective.billing_owner_id == "member"
    assert effective.is_billing_owner is True
    assert resolve_org_context(member).org.is_personal is True
    # Rollback keeps all organization data.
    assert fake.collection(MEMBERS_COLLECTION).find_one(
        {"org_id": org._id, "user_id": "member"}
    ) is not None


def test_org_seat_accounting_counts_paused_and_is_org_scoped(fake, team_enabled):
    owner = make_user(
        fake, "owner", "owner@example.com", plan="cloud", cloud_profiles=1
    )
    org = ensure_personal_org(owner)
    member = make_user(
        fake, "member", "member@example.com", plan="starter", cloud_profiles=0,
        org_id=org._id,
    )
    add_member(fake, org._id, member, ROLE_MEMBER)

    add_profile(fake, "p1", "member", org._id, assigned_user_id="member", active=True)
    add_profile(fake, "p2", "owner", org._id, assigned_user_id="owner", active=False)

    assert seat_accounting.count_credentialed_profiles("member") == 2
    assert seat_accounting.count_credentialed_profiles("owner") == 2
    assert seat_accounting.reserve_linkedin_seat("member", 2) == (
        False,
        "LinkedIn account limit reached (2/2)",
    )
    assert seat_accounting.reserve_linkedin_seat("owner", 2)[0] is False

    # Deleting the account releases exactly one seat.
    fake.collection("linkedin_profiles").delete_one({"_id": "p1"})
    fake.collection("linkedin_credentials").delete_one({"linkedin_profile_id": "p1"})
    seat_accounting.release_linkedin_seat("member")
    assert seat_accounting.reserve_linkedin_seat("member", 2)[0] is True

    # The counter is keyed by the accounting owner, never the member.
    counter_ids = {doc["_id"] for doc in fake.collection("linkedin_seat_usage").find({})}
    assert counter_ids == {"owner"}


def test_cross_tenant_profile_and_campaign_access_denied(fake, team_enabled):
    owner_a = make_user(fake, "owner-a", "a@example.com")
    org_a = ensure_personal_org(owner_a)
    member_a = make_user(
        fake, "member-a", "member-a@example.com", plan="starter", cloud_profiles=0,
        org_id=org_a._id,
    )
    add_member(fake, org_a._id, member_a, ROLE_MEMBER)

    owner_b = make_user(fake, "owner-b", "b@example.com")
    org_b = ensure_personal_org(owner_b)
    profile_b = add_profile(fake, "profile-b", "owner-b", org_b._id)

    assert can_access_profile_doc(member_a, profile_b) is False
    assert can_access_profile_doc(owner_b, profile_b) is True

    query = profile_access_query(member_a)
    assert fake.collection("linkedin_profiles").find_one({"_id": "profile-b", **query}) is None

    campaign_b = type(
        "Campaign",
        (),
        {
            "user_id": "owner-b",
            "org_id": org_b._id,
            "team_member_ids": [],
            "linkedin_profile_id": "profile-b",
        },
    )()
    assert campaign_has_access(member_a, campaign_b) is False


def test_seat_removal_pauses_profile_and_retains_proxy(fake, team_enabled):
    owner = make_user(fake, "owner", "owner@example.com")
    org = ensure_personal_org(owner)
    member = make_user(
        fake, "member", "member@example.com", plan="starter", cloud_profiles=0,
        org_id=org._id,
    )
    add_member(fake, org._id, member, ROLE_MEMBER)
    add_profile(
        fake, "p1", "owner", org._id, assigned_user_id="member", proxy=True
    )

    unassign_seat(org, owner._id, "p1")

    profile = fake.collection("linkedin_profiles").find_one({"_id": "p1"})
    assert profile["assigned_user_id"] is None
    assert profile["active"] is False
    assert profile["is_active"] is False
    assert profile["proxy_id"] == "proxy-p1"
    assert profile["proxy_server"] == "http://proxy.example.com:8080"
    assert profile["proxy_mode"] == "managed"

    remove_seat(org, owner._id, "p1")
    events = [doc["event"] for doc in fake.collection(audit.AUDIT_COLLECTION).find({})]
    assert "seat.unassign" in events
    assert "seat.remove" in events


def test_owner_invites_assigns_and_member_sees_only_assigned(fake, team_enabled):
    owner = make_user(
        fake, "owner", "owner@example.com", plan="cloud", cloud_profiles=2
    )
    org = ensure_personal_org(owner)
    member = make_user(
        fake, "member", "member@example.com", plan="starter", cloud_profiles=0,
        subscription_status="none",
    )

    invite, token = invite_member(org, owner._id, member.email, ROLE_MEMBER)
    accept_invite(token, member)

    add_profile(fake, "p-member", "owner", org._id, assigned_user_id="owner", proxy=True)
    add_profile(fake, "p-owner", "owner", org._id, assigned_user_id="owner", proxy=True)

    assign_seat(org, owner._id, "p-member", member._id)

    member_query = profile_access_query(member)
    visible = list(fake.collection("linkedin_profiles").find(member_query))
    assert [doc["_id"] for doc in visible] == ["p-member"]
    assert can_access_profile_doc(member, fake.collection("linkedin_profiles").find_one({"_id": "p-owner"})) is False

    summary = seat_summary(org)
    assert summary["assigned_profiles"] == 2
    assert summary["cloud_seat_limit"] == 3

    # Removing the member pauses their assigned profile and keeps the proxy.
    paused = remove_member(org, owner._id, member._id)
    assert paused == 1
    profile = fake.collection("linkedin_profiles").find_one({"_id": "p-member"})
    assert profile["active"] is False
    assert profile["proxy_id"] == "proxy-p-member"
    assert fake.collection("linkedin_profiles").find_one(
        {"_id": "p-owner"}
    )["active"] is True
    membership = fake.collection(MEMBERS_COLLECTION).find_one(
        {"org_id": org._id, "user_id": member._id}
    )
    assert membership["status"] == "removed"
    events = [doc["event"] for doc in fake.collection(audit.AUDIT_COLLECTION).find({})]
    assert "seat.remove" in events
    assert "org.remove" in events


def test_invite_preview_returns_workspace_without_consuming_token(fake, team_enabled):
    owner = make_user(fake, "owner", "owner@example.com")
    org = ensure_personal_org(owner)
    invite, token = invite_member(org, owner._id, "member@example.com", ROLE_MEMBER)

    import asyncio

    from starlette.requests import Request

    request = Request(
        {"type": "http", "method": "GET", "path": "/", "headers": [], "client": ("127.0.0.1", 1234)}
    )
    preview = asyncio.run(organizations_router.preview_invite(token, request))
    assert preview.org_id == org._id
    assert preview.org_name == org.name
    assert preview.email == "member@example.com"
    assert preview.role == ROLE_MEMBER
    # Preview is read-only.
    assert fake.collection(INVITES_COLLECTION).find_one({"_id": invite._id})[
        "accepted_at"
    ] is None


def test_invite_expiry_rejects_preview_and_acceptance(fake, team_enabled):
    owner = make_user(fake, "owner", "owner@example.com")
    org = ensure_personal_org(owner)
    invite, token = invite_member(org, owner._id, "member@example.com", ROLE_MEMBER)
    fake.collection(INVITES_COLLECTION).update_one(
        {"_id": invite._id},
        {"$set": {"expires_at": datetime.now(timezone.utc) - timedelta(minutes=1)}},
    )

    with pytest.raises(InviteInvalidError):
        get_invite_by_token(token)

    member = make_user(
        fake, "member", "member@example.com", plan="starter", cloud_profiles=0
    )
    with pytest.raises(InviteInvalidError):
        accept_invite(token, member)
    assert fake.collection(INVITES_COLLECTION).find_one({"_id": invite._id})[
        "accepted_at"
    ] is None


def test_invite_email_mismatch_does_not_consume_token(fake, team_enabled):
    owner = make_user(fake, "owner", "owner@example.com")
    org = ensure_personal_org(owner)
    invite, token = invite_member(org, owner._id, "member@example.com", ROLE_MEMBER)
    other = make_user(fake, "other", "other@example.com", plan="starter", cloud_profiles=0)

    with pytest.raises(InviteEmailMismatchError):
        accept_invite(token, other)

    assert fake.collection(INVITES_COLLECTION).find_one({"_id": invite._id})[
        "accepted_at"
    ] is None
    assert fake.collection(MEMBERS_COLLECTION).find_one(
        {"org_id": org._id, "user_id": "other"}
    ) is None

    member = make_user(
        fake, "member", "member@example.com", plan="starter", cloud_profiles=0
    )
    accepted_org, _ = accept_invite(token, member)
    assert accepted_org._id == org._id


def test_revoked_invite_cannot_be_accepted(fake, team_enabled):
    owner = make_user(fake, "owner", "owner@example.com")
    org = ensure_personal_org(owner)
    invite, token = invite_member(org, owner._id, "member@example.com", ROLE_MEMBER)

    revoke_invite(org, owner._id, invite._id)
    assert fake.collection(INVITES_COLLECTION).find_one({"_id": invite._id})[
        "revoked_at"
    ] is not None

    member = make_user(
        fake, "member", "member@example.com", plan="starter", cloud_profiles=0
    )
    with pytest.raises(InviteInvalidError):
        accept_invite(token, member)


def test_admin_cannot_invite_admin_or_owner(fake, team_enabled):
    owner = make_user(fake, "owner", "owner@example.com")
    org = ensure_personal_org(owner)
    admin = make_user(fake, "admin", "admin@example.com", plan="starter", cloud_profiles=0)
    add_member(fake, org._id, admin, ROLE_ADMIN)

    with pytest.raises(OrganizationPermissionError):
        invite_member(org, admin._id, "second-admin@example.com", ROLE_ADMIN)
    with pytest.raises(OrganizationPermissionError):
        invite_member(org, admin._id, "owner2@example.com", ROLE_OWNER)
    invite, _ = invite_member(org, admin._id, "member@example.com", ROLE_MEMBER)
    assert invite.role == ROLE_MEMBER


def test_router_member_only_lists_assigned_profiles(fake, team_enabled):
    owner = make_user(
        fake, "owner", "owner@example.com", plan="cloud", cloud_profiles=2
    )
    org = ensure_personal_org(owner)
    member = make_user(
        fake, "member", "member@example.com", plan="starter", cloud_profiles=0,
        org_id=org._id,
    )
    add_member(fake, org._id, member, ROLE_MEMBER)
    add_profile(fake, "p-member", "owner", org._id, assigned_user_id="member")
    add_profile(fake, "p-owner", "owner", org._id, assigned_user_id="owner")

    import asyncio

    profiles = asyncio.run(
        organizations_router.list_org_profiles(org._id, user_id="member")
    )
    assert [profile.profile_id for profile in profiles] == ["p-member"]

    seats = asyncio.run(
        organizations_router.get_seats(org._id, user_id="member")
    )
    assert seats.cloud_seat_limit is None
    assert seats.credentialed_profiles == 0


def test_removed_member_loses_former_team_campaign_access(fake, team_enabled):
    owner = make_user(fake, "owner", "owner@example.com", plan="cloud", cloud_profiles=2)
    org = ensure_personal_org(owner)
    member = make_user(
        fake, "member", "member@example.com", plan="starter", cloud_profiles=0,
        org_id=org._id,
    )
    add_member(fake, org._id, member, ROLE_MEMBER)

    campaign = type(
        "Campaign",
        (),
        {
            "user_id": "member",
            "org_id": org._id,
            "team_member_ids": [],
            "linkedin_profile_id": None,
        },
    )()

    assert campaign_has_access(User.get("member"), campaign) is True

    remove_member(org, owner._id, member._id)
    member_after = User.get("member")

    assert campaign_has_access(member_after, campaign) is False
    query = campaign_access_query(member_after)
    clauses = query["$or"]
    # The removed member's personal org is active. Every clause must be
    # org-scoped (including legacy org_id-missing rows); a bare user_id clause
    # would keep the former team campaign visible.
    assert all("org_id" in clause for clause in clauses)


def test_seat_summary_counts_cloud_credentials_only(fake, team_enabled):
    owner = make_user(fake, "owner", "owner@example.com", plan="cloud", cloud_profiles=1)
    org = ensure_personal_org(owner)
    add_profile(fake, "p-cloud", "owner", org._id, execution_mode="cloud")
    add_profile(fake, "p-desktop", "owner", org._id, execution_mode="desktop")

    summary = seat_summary(org)

    assert summary["cloud_profiles"] == 1
    assert summary["credentialed_profiles"] == 1
    assert summary["desktop_credentialed_profiles"] == 1


def test_admin_seat_override_survives_billing_mirror(fake, team_enabled):
    owner = make_user(fake, "owner", "owner@example.com", plan="starter", cloud_profiles=0)
    org = ensure_personal_org(owner)

    apply_seat_override(org, "admin", 3, "support exception", plan="cloud")
    sync_org_billing_from_user(owner)

    updated = fake.collection(ORGANIZATIONS_COLLECTION).find_one({"_id": org._id})
    assert updated["plan"] == "cloud"
    assert updated["cloud_seats"] == 3
    assert updated["seat_override"] is True
