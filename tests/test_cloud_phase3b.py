"""Phase 3B org-owned channels, desktop enrollment, and device scope tests."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from openoutreach.api_v2.routers import daemon_v2, mailboxes as mailboxes_router
from openoutreach.emails.models import Mailbox
from openoutreach.mongodb.models_user import User
from openoutreach.organizations.access import (
    can_access_channel_doc,
    channel_access_query,
    profile_authorized_for_tenant,
    resolve_org_context,
)
from openoutreach.organizations.models import (
    MEMBERS_COLLECTION,
    ROLE_ADMIN,
    ROLE_MEMBER,
    STATUS_ACTIVE,
    OrganizationMember,
)
from openoutreach.organizations.service import ensure_personal_org
from openoutreach.whatsapp.api import router as whatsapp_router
from openoutreach.whatsapp.models.profile import WhatsAppProfile
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
    "openoutreach.emails.models.get_mongodb_collection",
    "openoutreach.whatsapp.models.profile.get_mongodb_collection",
    "openoutreach.whatsapp.api.router.get_mongodb_collection",
    "openoutreach.api_v2.routers.mailboxes.get_mongodb_collection",
    "openoutreach.api_v2.routers.daemon_v2.get_mongodb_collection",
]


@pytest.fixture(autouse=True)
def encryption_key(monkeypatch):
    from cryptography.fernet import Fernet

    monkeypatch.setenv("COOKIE_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.delenv("SECRET_KEY", raising=False)


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
    org_id=None,
) -> User:
    user = User(
        _id=user_id,
        email=email,
        full_name=user_id,
        plan=plan,
        cloud_profiles=cloud_profiles,
        linkedin_account_limit=1 + cloud_profiles if plan == "cloud" else 1,
        subscription_status="active",
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


def test_channel_query_and_access_for_owner_and_member(fake, team_enabled):
    owner = make_user(fake, "owner", "owner@example.com")
    org = ensure_personal_org(owner)
    member = make_user(
        fake, "member", "member@example.com", plan="starter", cloud_profiles=0, org_id=org._id
    )
    add_member(fake, org._id, member, ROLE_MEMBER)

    assigned = {
        "_id": "wa-assigned",
        "user_id": "owner",
        "org_id": org._id,
        "assigned_user_id": "member",
    }
    other = {
        "_id": "wa-other",
        "user_id": "owner",
        "org_id": org._id,
        "assigned_user_id": "owner",
    }
    fake.collection("whatsapp_profiles").insert_one(assigned)
    fake.collection("whatsapp_profiles").insert_one(other)
    assert can_access_channel_doc(owner, assigned) is True
    assert can_access_channel_doc(member, assigned) is True
    assert can_access_channel_doc(member, other) is False

    member_query = channel_access_query(member)
    assert fake.collection("whatsapp_profiles").find_one({"_id": "wa-assigned", **member_query})
    assert fake.collection("whatsapp_profiles").find_one({"_id": "wa-other", **member_query}) is None


def test_whatsapp_router_owner_sees_member_profile(fake, team_enabled):
    owner = make_user(fake, "owner", "owner@example.com")
    org = ensure_personal_org(owner)
    member = make_user(
        fake, "member", "member@example.com", plan="starter", cloud_profiles=0, org_id=org._id
    )
    add_member(fake, org._id, member, ROLE_MEMBER)
    profile = WhatsAppProfile(
        user_id="member",
        org_id=org._id,
        assigned_user_id="member",
        display_name="Member WA",
        status="disconnected",
    )
    profile.save()

    owner_profiles = asyncio.run(whatsapp_router.list_profiles(user_id="owner"))
    assert [item["id"] for item in owner_profiles] == [profile._id]
    member_profiles = asyncio.run(whatsapp_router.list_profiles(user_id="member"))
    assert [item["id"] for item in member_profiles] == [profile._id]

    other = make_user(fake, "other", "other@example.com")
    other_org = ensure_personal_org(other)
    other_profile = WhatsAppProfile(
        user_id="other", org_id=other_org._id, assigned_user_id="other"
    )
    other_profile.save()
    member_visible = asyncio.run(whatsapp_router.list_profiles(user_id="member"))
    assert [item["id"] for item in member_visible] == [profile._id]
    with pytest.raises(Exception):
        asyncio.run(whatsapp_router.get_profile(other_profile._id, user_id="member"))


def test_mailbox_org_access(fake, team_enabled):
    owner = make_user(fake, "owner", "owner@example.com")
    org = ensure_personal_org(owner)
    member = make_user(
        fake, "member", "member@example.com", plan="starter", cloud_profiles=0, org_id=org._id
    )
    add_member(fake, org._id, member, ROLE_MEMBER)
    box = Mailbox(
        host="smtp.example.com",
        username="member@example.com",
        password="secret",
        user_id="member",
        org_id=org._id,
        assigned_user_id="member",
    )
    box.save()

    owner_boxes = asyncio.run(mailboxes_router.list_mailboxes(user_id="owner"))
    assert [item.id for item in owner_boxes] == [box._id]
    member_boxes = asyncio.run(mailboxes_router.list_mailboxes(user_id="member"))
    assert [item.id for item in member_boxes] == [box._id]

    other = make_user(fake, "other", "other@example.com")
    with pytest.raises(Exception):
        asyncio.run(mailboxes_router.update_mailbox(box._id, mailboxes_router.MailboxUpdate(from_name="x"), user_id="other"))


def test_owner_assigns_desktop_profile_without_consuming_cloud_seat(fake, team_enabled):
    from openoutreach.organizations.service import assign_desktop_profile

    owner = make_user(fake, "owner", "owner@example.com")
    org = ensure_personal_org(owner)
    member = make_user(
        fake, "member", "member@example.com", plan="starter", cloud_profiles=0, org_id=org._id
    )
    add_member(fake, org._id, member, ROLE_MEMBER)
    fake.collection("linkedin_profiles").insert_one(
        {
            "_id": "desktop-p",
            "user_id": "owner",
            "org_id": org._id,
            "execution_mode": "desktop",
            "assigned_user_id": "owner",
            "active": True,
        }
    )
    profile = assign_desktop_profile(org, "owner", "desktop-p", "member")
    assert profile["assigned_user_id"] == "member"
    stored = fake.collection("linkedin_profiles").find_one({"_id": "desktop-p"})
    assert stored["assigned_user_id"] == "member"
    assert stored["execution_mode"] == "desktop"
    # Desktop assignment does not change the cloud seat counter.
    assert fake.collection("linkedin_seat_usage").count_documents({}) == 0


def test_removing_member_revokes_devices_and_clears_channel_assignment(
    fake, team_enabled
):
    from openoutreach.organizations.service import remove_member

    owner = make_user(fake, "owner", "owner@example.com")
    org = ensure_personal_org(owner)
    member = make_user(
        fake, "member", "member@example.com", plan="starter", cloud_profiles=0, org_id=org._id
    )
    add_member(fake, org._id, member, ROLE_MEMBER)
    fake.collection("daemon_devices").insert_one(
        {"_id": "d1", "user_id": "member", "org_id": org._id, "revoked": False}
    )
    fake.collection("daemon_refresh_families").insert_one(
        {"_id": "f1", "device_id": "d1", "user_id": "member", "revoked": False}
    )
    fake.collection("whatsapp_profiles").insert_one(
        {
            "_id": "wa1",
            "user_id": "owner",
            "org_id": org._id,
            "assigned_user_id": "member",
        }
    )
    fake.collection("mailboxes").insert_one(
        {
            "_id": "m1",
            "user_id": "owner",
            "org_id": org._id,
            "assigned_user_id": "member",
        }
    )

    remove_member(org, owner._id, member._id)

    assert fake.collection("daemon_devices").find_one({"_id": "d1"})["revoked"] is True
    assert fake.collection("daemon_refresh_families").find_one({"_id": "f1"})[
        "revoked"
    ] is True
    assert fake.collection("whatsapp_profiles").find_one({"_id": "wa1"})[
        "assigned_user_id"
    ] is None
    assert fake.collection("mailboxes").find_one({"_id": "m1"})[
        "assigned_user_id"
    ] is None


def test_desktop_enrollment_rejects_cloud_and_other_member(fake, team_enabled):
    owner = make_user(fake, "owner", "owner@example.com")
    org = ensure_personal_org(owner)
    member = make_user(
        fake, "member", "member@example.com", plan="starter", cloud_profiles=0, org_id=org._id
    )
    other_member = make_user(
        fake, "other", "other@example.com", plan="starter", cloud_profiles=0, org_id=org._id
    )
    add_member(fake, org._id, member, ROLE_MEMBER)
    add_member(fake, org._id, other_member, ROLE_MEMBER)

    fake.collection("linkedin_profiles").insert_one(
        {
            "_id": "cloud-p",
            "user_id": "owner",
            "org_id": org._id,
            "execution_mode": "cloud",
            "assigned_user_id": "member",
        }
    )
    fake.collection("linkedin_profiles").insert_one(
        {
            "_id": "desktop-p",
            "user_id": "owner",
            "org_id": org._id,
            "execution_mode": "desktop",
            "assigned_user_id": "member",
        }
    )
    fake.collection("linkedin_profiles").insert_one(
        {
            "_id": "other-p",
            "user_id": "owner",
            "org_id": org._id,
            "execution_mode": "desktop",
            "assigned_user_id": "other",
        }
    )

    assert profile_authorized_for_tenant("member", "desktop-p", "linkedin") is True
    assert profile_authorized_for_tenant("member", "cloud-p", "linkedin") is False
    assert profile_authorized_for_tenant("member", "other-p", "linkedin") is False
    assert profile_authorized_for_tenant("owner", "desktop-p", "linkedin") is True


def test_device_scope_is_org_aware(fake, team_enabled):
    owner = make_user(fake, "owner", "owner@example.com")
    org = ensure_personal_org(owner)
    member = make_user(
        fake, "member", "member@example.com", plan="starter", cloud_profiles=0, org_id=org._id
    )
    add_member(fake, org._id, member, ROLE_MEMBER)
    admin = make_user(
        fake, "admin", "admin@example.com", plan="starter", cloud_profiles=0, org_id=org._id
    )
    add_member(fake, org._id, admin, ROLE_ADMIN)

    fake.collection("daemon_devices").insert_one(
        {"_id": "d1", "user_id": "member", "org_id": org._id, "revoked": False}
    )
    fake.collection("daemon_devices").insert_one(
        {"_id": "d2", "user_id": "owner", "org_id": org._id, "revoked": False}
    )

    owner_query, owner_org = daemon_v2._device_scope("owner")
    assert owner_org == org._id
    assert len(list(fake.collection("daemon_devices").find(owner_query))) == 2
    member_query, _ = daemon_v2._device_scope("member")
    assert len(list(fake.collection("daemon_devices").find(member_query))) == 1
    admin_query, _ = daemon_v2._device_scope("admin")
    assert len(list(fake.collection("daemon_devices").find(admin_query))) == 2


def test_task_owner_scope_is_strict_for_personal_and_owner(fake, team_enabled, monkeypatch):
    owner = make_user(fake, "owner", "owner@example.com")
    org = ensure_personal_org(owner)
    member = make_user(
        fake, "member", "member@example.com", plan="starter", cloud_profiles=0, org_id=org._id
    )
    add_member(fake, org._id, member, ROLE_MEMBER)

    from openoutreach.api_v2.tenant_security import TenantContext

    member_scope = daemon_v2._task_owner_scope(
        TenantContext(tenant_id="member", device_id="d1")
    )
    assert member_scope == {}
    owner_scope = daemon_v2._task_owner_scope(
        TenantContext(tenant_id="owner", device_id="d2")
    )
    assert owner_scope == {"user_id": "owner"}

    from openoutreach.config import settings

    monkeypatch.setattr(settings, "TEAM_WORKSPACES_ENABLED", False)
    personal_scope = daemon_v2._task_owner_scope(
        TenantContext(tenant_id="member", device_id="d1")
    )
    assert personal_scope == {"user_id": "member"}
