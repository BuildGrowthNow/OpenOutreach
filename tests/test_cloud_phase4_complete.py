"""Phase 4 completion tests: unified seats, channel-aware proxies, WhatsApp-only,
separate-IP Duo, per-channel usage, and email BYO slots.

The tests use the in-memory Mongo fake and a fake Massive provisioning path.
No live provider or database is contacted.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet

from openoutreach.billing import cloud_seats
from openoutreach.billing.cloud_seats import (
    allowed_cloud_seat_units,
    cloud_seat_count_for_org,
    cloud_seat_key_for_profile,
    cloud_seat_summary_for_org,
    cloud_seat_units_for_org,
    linkedin_profile_shares_seat_with_whatsapp,
    reconcile_cloud_seat_usage,
    release_cloud_seat,
    reserve_cloud_seat,
    whatsapp_consumes_cloud_seat,
)
from openoutreach.billing.email_slots import email_slot_limit, email_slot_usage
from openoutreach.mongodb.crypto import safe_encrypt
from openoutreach.organizations.enforcement import EffectivePlan
from openoutreach.organizations.service import (
    assign_seat,
    get_org,
    remove_member,
    unassign_seat,
)
from openoutreach.proxies import provisioning
from openoutreach.proxies.massive_client import (
    build_massive_subuser,
    build_massive_username,
    provision_massive_fallback,
)
from openoutreach.proxies.provisioning import sync_massive_reporting
from openoutreach.proxies.models import Proxy
from openoutreach.proxies.service import (
    assign_proxy_to_whatsapp,
    attach_shared_proxy_to_whatsapp,
    get_usage_summary,
    record_usage_snapshot,
    retire_proxy_for_profile,
    retire_proxy_for_whatsapp_profile,
    unassign_proxy,
)
from openoutreach.whatsapp.models.profile import WhatsAppProfile
from tests.fake_mongo import FakeMongo

PATCH_TARGETS = [
    "openoutreach.billing.cloud_seats.get_mongodb_collection",
    "openoutreach.billing.seats.get_mongodb_collection",
    "openoutreach.organizations.models.get_mongodb_collection",
    "openoutreach.organizations.service.get_mongodb_collection",
    "openoutreach.organizations.access.get_mongodb_collection",
    "openoutreach.organizations.audit.get_mongodb_collection",
    "openoutreach.mongodb.models_user.get_mongodb_collection",
    "openoutreach.proxies.models.get_mongodb_collection",
    "openoutreach.proxies.service.get_mongodb_collection",
    "openoutreach.proxies.provisioning.get_mongodb_collection",
    "openoutreach.whatsapp.models.profile.get_mongodb_collection",
    "openoutreach.whatsapp.cloud.get_mongodb_collection",
    "openoutreach.whatsapp.api.router.get_mongodb_collection",
    "openoutreach.api_v2.routers.mailboxes.get_mongodb_collection",
    "openoutreach.emails.models.get_mongodb_collection",
    "openoutreach.mongodb.connection.get_mongodb_collection",
]


@pytest.fixture(autouse=True)
def encryption_key(monkeypatch):
    monkeypatch.setenv("COOKIE_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.delenv("SECRET_KEY", raising=False)


@pytest.fixture
def fake(monkeypatch):
    mongo = FakeMongo()
    for target in PATCH_TARGETS:
        monkeypatch.setattr(target, mongo.get_mongodb_collection)
    from openoutreach.config import settings

    monkeypatch.setattr(settings, "TEAM_WORKSPACES_ENABLED", True)
    monkeypatch.setattr(settings, "CLOUD_SEATS_ENABLED", True)
    monkeypatch.setattr(settings, "MANAGED_PROXIES_ENABLED", True)
    monkeypatch.setattr(settings, "WHATSAPP_CLOUD_PROXY_ENABLED", True)
    monkeypatch.setattr(settings, "DAEMON_V2_WHATSAPP_ENABLED", True)
    # Assignment tests use a documentation host that must not resolve.
    monkeypatch.setattr(
        "openoutreach.proxies.service.validate_proxy_host", lambda host: None
    )
    monkeypatch.setattr(
        "openoutreach.proxies.models.validate_proxy_host",
        lambda host: None,
        raising=False,
    )

    async def _fake_test_proxy(proxy_id: str):
        return {"success": True, "ip": "203.0.113.10", "country": "US"}

    monkeypatch.setattr(
        "openoutreach.proxies.service.test_proxy", _fake_test_proxy
    )
    return mongo


def seed_owner(fake: FakeMongo, owner_id: str = "owner", *, plan: str = "cloud", cloud_profiles: int = 0):
    fake.collection("users").insert_one(
        {
            "_id": owner_id,
            "email": f"{owner_id}@example.com",
            "plan": plan,
            "cloud_profiles": cloud_profiles,
            "subscription_status": "active",
            "org_id": f"org-{owner_id}",
        }
    )
    fake.collection("organizations").insert_one(
        {
            "_id": f"org-{owner_id}",
            "name": "Workspace",
            "owner_user_id": owner_id,
            "plan": plan,
            "cloud_seats": cloud_profiles,
            "is_personal": True,
            "status": "active",
        }
    )
    return f"org-{owner_id}"


def add_linkedin(
    fake: FakeMongo,
    profile_id: str,
    owner_id: str,
    org_id: str,
    *,
    identity_id: str | None = None,
    active: bool = True,
    proxy_id: str | None = None,
    credentialed: bool = True,
):
    fake.collection("linkedin_profiles").insert_one(
        {
            "_id": profile_id,
            "user_id": owner_id,
            "org_id": org_id,
            "assigned_user_id": owner_id,
            "execution_mode": "cloud",
            "identity_id": identity_id or owner_id,
            "active": active,
            "is_active": active,
            "proxy_id": proxy_id,
            "created_at": datetime.now(timezone.utc),
        }
    )
    if credentialed:
        fake.collection("linkedin_credentials").insert_one(
            {
                "_id": f"cred-{profile_id}",
                "linkedin_profile_id": profile_id,
                "user_id": owner_id,
            }
        )


def add_whatsapp(
    fake: FakeMongo,
    profile_id: str,
    owner_id: str,
    org_id: str,
    *,
    identity_id: str,
    cloud_mode: str = "whatsapp_only",
    proxy_id: str | None = None,
    active: bool = True,
):
    profile = WhatsAppProfile(
        _id=profile_id,
        user_id=owner_id,
        org_id=org_id,
        assigned_user_id=owner_id,
        identity_id=identity_id,
        execution_mode="cloud",
        cloud_mode=cloud_mode,
        proxy_id=proxy_id,
        proxy_mode="managed" if proxy_id else "none",
        active=active,
        is_active=active,
    )
    profile.save()
    return profile


def add_proxy(
    fake: FakeMongo,
    proxy_id: str,
    *,
    channel: str = "linkedin",
    linkedin_profile_id: str | None = None,
    whatsapp_profile_id: str | None = None,
    identity_id: str | None = None,
    org_id: str | None = "org-owner",
    owner_id: str | None = "owner",
    status: str = "assigned",
    massive_status: str = "active",
):
    fake.collection("proxies").insert_one(
        {
            "_id": proxy_id,
            "provider": "massive_residential",
            "protocol": "http",
            "host": "proxy.example.com",
            "port": 8080,
            "username": f"parent_{proxy_id}",
            "password_encrypted": safe_encrypt("secret"),
            "country": "US",
            "status": status,
            "channel": channel,
            "linkedin_profile_id": linkedin_profile_id,
            "whatsapp_profile_id": whatsapp_profile_id,
            "identity_id": identity_id,
            "assigned_user_id": owner_id,
            "assigned_org_id": org_id,
            "ever_assigned": True,
            "massive_status": massive_status,
        }
    )


def add_member(fake: FakeMongo, org_id: str, member_id: str = "member"):
    fake.collection("users").insert_one(
        {
            "_id": member_id,
            "email": f"{member_id}@example.com",
            "plan": "starter",
            "org_id": org_id,
            "subscription_status": "active",
        }
    )
    fake.collection("organization_members").insert_one(
        {
            "_id": f"membership-{member_id}",
            "org_id": org_id,
            "user_id": member_id,
            "email": f"{member_id}@example.com",
            "role": "member",
            "status": "active",
        }
    )
    return member_id


# ── Unified seat accounting ──────────────────────────────────────────────


def test_cloud_duo_shared_ip_is_one_seat(fake):
    org_id = seed_owner(fake, cloud_profiles=1)
    add_linkedin(fake, "li1", "owner", org_id, identity_id="id1", proxy_id="px-li")
    add_proxy(fake, "px-li", channel="duo", linkedin_profile_id="li1", whatsapp_profile_id="wa1", identity_id="id1")
    add_whatsapp(fake, "wa1", "owner", org_id, identity_id="id1", cloud_mode="duo_shared", proxy_id="px-li")

    units = cloud_seat_units_for_org(org_id, "owner")

    assert len(units) == 1
    assert units[0]["channel"] == "duo"
    assert units[0]["profile_id"] == "li1"
    assert units[0]["whatsapp_profile_id"] == "wa1"
    assert cloud_seat_summary_for_org(org_id, "owner", limit=2)["duo"] == 1


def test_cloud_duo_separate_ip_is_one_seat_with_two_proxies(fake):
    org_id = seed_owner(fake, cloud_profiles=1)
    add_linkedin(fake, "li1", "owner", org_id, identity_id="id1", proxy_id="px-li")
    add_proxy(fake, "px-li", channel="linkedin", linkedin_profile_id="li1", identity_id="id1")
    add_proxy(fake, "px-wa", channel="whatsapp", whatsapp_profile_id="wa1", identity_id="id1")
    add_whatsapp(fake, "wa1", "owner", org_id, identity_id="id1", cloud_mode="duo_separate", proxy_id="px-wa")

    units = cloud_seat_units_for_org(org_id, "owner")

    assert len(units) == 1
    assert units[0]["channel"] == "duo"
    assert cloud_seat_key_for_profile("wa1", "whatsapp", org_id=org_id, owner_user_id="owner") == "li:li1"


def test_whatsapp_only_cloud_is_one_seat(fake):
    org_id = seed_owner(fake, cloud_profiles=1)
    add_whatsapp(fake, "wa1", "owner", org_id, identity_id="wa:id1", proxy_id="px-wa")
    add_proxy(fake, "px-wa", channel="whatsapp", whatsapp_profile_id="wa1", identity_id="wa:id1")

    units = cloud_seat_units_for_org(org_id, "owner")

    assert len(units) == 1
    assert units[0]["channel"] == "whatsapp"
    assert units[0]["key"] == "wa:wa1"


def test_paused_accounts_still_consume_a_seat(fake):
    org_id = seed_owner(fake, cloud_profiles=0)
    add_linkedin(fake, "li1", "owner", org_id, active=False)
    add_whatsapp(fake, "wa1", "owner", org_id, identity_id="wa:id1", active=False)

    assert cloud_seat_count_for_org(org_id, "owner") == 2


def test_reservation_is_atomic_and_org_scoped(fake):
    org_id = seed_owner(fake, cloud_profiles=0)
    fake.collection("users").insert_one(
        {
            "_id": "member",
            "email": "member@example.com",
            "plan": "starter",
            "org_id": org_id,
            "subscription_status": "active",
        }
    )
    fake.collection("organization_members").insert_one(
        {
            "_id": "m1",
            "org_id": org_id,
            "user_id": "member",
            "email": "member@example.com",
            "role": "member",
            "status": "active",
        }
    )

    first, error = reserve_cloud_seat("member", 1)
    second, second_error = reserve_cloud_seat("owner", 1)

    assert first is True and error is None
    assert second is False
    assert "1/1" in second_error
    # The member's reservation landed on the owner's counter.
    assert fake.collection("cloud_seat_usage").find_one({"_id": "owner"})["count"] == 1


def test_release_only_on_delete_and_reconcile_heals(fake):
    org_id = seed_owner(fake, cloud_profiles=1)
    add_linkedin(fake, "li1", "owner", org_id)
    # One existing account plus one reservation for a new account.
    assert reserve_cloud_seat("owner", 2) == (True, None)
    assert fake.collection("cloud_seat_usage").find_one({"_id": "owner"})["count"] == 2

    # The reserved account is created.
    add_linkedin(fake, "li2", "owner", org_id)

    # Pausing does not release.
    fake.collection("linkedin_profiles").update_many(
        {}, {"$set": {"active": False, "is_active": False}}
    )
    assert reconcile_cloud_seat_usage("owner") == 2

    # Deleting one credential/profile releases exactly one seat.
    fake.collection("linkedin_credentials").delete_many({"linkedin_profile_id": "li1"})
    fake.collection("linkedin_profiles").delete_one({"_id": "li1"})
    release_cloud_seat("owner")
    assert fake.collection("cloud_seat_usage").find_one({"_id": "owner"})["count"] == 1


def test_deleting_linkedin_keeps_duo_whatsapp_seat(fake):
    org_id = seed_owner(fake, cloud_profiles=1)
    add_linkedin(fake, "li1", "owner", org_id, identity_id="id1", proxy_id="px1")
    add_proxy(fake, "px1", channel="duo", linkedin_profile_id="li1", whatsapp_profile_id="wa1", identity_id="id1")
    add_whatsapp(fake, "wa1", "owner", org_id, identity_id="id1", cloud_mode="duo_shared", proxy_id="px1")

    assert linkedin_profile_shares_seat_with_whatsapp(
        "li1", org_id=org_id, owner_user_id="owner"
    )
    assert whatsapp_consumes_cloud_seat("wa1", org_id=org_id, owner_user_id="owner") is False


def test_allowed_units_cap_the_daemon_at_the_seat_limit(fake):
    org_id = seed_owner(fake, cloud_profiles=0)
    add_linkedin(fake, "li1", "owner", org_id)
    add_whatsapp(fake, "wa1", "owner", org_id, identity_id="wa:id1")
    add_whatsapp(fake, "wa2", "owner", org_id, identity_id="wa:id2")

    allowed = allowed_cloud_seat_units("owner", 2)

    assert len(allowed) == 2
    assert "li:li1" in allowed
    assert "wa:wa1" in allowed
    assert "wa:wa2" not in allowed


def test_team_linkedin_seat_syncs_shared_duo_and_retains_proxy(fake):
    org_id = seed_owner(fake, cloud_profiles=0)
    add_member(fake, org_id)
    add_linkedin(fake, "li1", "owner", org_id, identity_id="id1", proxy_id="px1")
    add_proxy(fake, "px1", channel="duo", linkedin_profile_id="li1", whatsapp_profile_id="wa1", identity_id="id1")
    add_whatsapp(fake, "wa1", "owner", org_id, identity_id="id1", cloud_mode="duo_shared", proxy_id="px1")
    org = get_org(org_id)

    assign_seat(org, "owner", "li1", "member")
    stored_wa = fake.collection("whatsapp_profiles").find_one({"_id": "wa1"})
    assert stored_wa["assigned_user_id"] == "member"
    assert stored_wa["active"] is True

    unassign_seat(org, "owner", "li1")
    paused_wa = fake.collection("whatsapp_profiles").find_one({"_id": "wa1"})
    assert paused_wa["assigned_user_id"] is None
    assert paused_wa["active"] is False
    proxy = fake.collection("proxies").find_one({"_id": "px1"})
    assert proxy["status"] == "assigned"
    assert proxy["whatsapp_profile_id"] == "wa1"


def test_team_whatsapp_only_seat_pauses_and_keeps_proxy(fake):
    org_id = seed_owner(fake, cloud_profiles=1)
    add_member(fake, org_id)
    add_whatsapp(fake, "wa1", "owner", org_id, identity_id="wa:id1", proxy_id="px-wa")
    add_proxy(fake, "px-wa", channel="whatsapp", whatsapp_profile_id="wa1", identity_id="wa:id1")
    org = get_org(org_id)

    assign_seat(org, "owner", "wa1", "member", channel="whatsapp")
    assert fake.collection("whatsapp_profiles").find_one({"_id": "wa1"})["active"] is True

    unassign_seat(org, "owner", "wa1", channel="whatsapp")
    stored = fake.collection("whatsapp_profiles").find_one({"_id": "wa1"})
    assert stored["active"] is False
    assert stored["proxy_id"] == "px-wa"
    assert fake.collection("proxies").find_one({"_id": "px-wa"})["status"] == "assigned"
    assert cloud_seat_count_for_org(org_id, "owner") == 1


def test_separate_duo_pauses_with_the_linkedin_seat(fake):
    org_id = seed_owner(fake, cloud_profiles=0)
    add_member(fake, org_id)
    add_linkedin(fake, "li1", "owner", org_id, identity_id="id1", proxy_id="px-li")
    add_proxy(fake, "px-li", channel="linkedin", linkedin_profile_id="li1", identity_id="id1")
    add_proxy(fake, "px-wa", channel="whatsapp", whatsapp_profile_id="wa1", identity_id="id1")
    add_whatsapp(fake, "wa1", "owner", org_id, identity_id="id1", cloud_mode="duo_separate", proxy_id="px-wa")
    org = get_org(org_id)

    assign_seat(org, "owner", "li1", "member")
    assert fake.collection("whatsapp_profiles").find_one({"_id": "wa1"})["active"] is True

    unassign_seat(org, "owner", "li1")
    stored = fake.collection("whatsapp_profiles").find_one({"_id": "wa1"})
    assert stored["active"] is False
    assert stored["proxy_id"] == "px-wa"


def test_remove_member_pauses_whatsapp_cloud_and_keeps_proxy(fake):
    org_id = seed_owner(fake, cloud_profiles=1)
    add_member(fake, org_id)
    add_whatsapp(fake, "wa1", "owner", org_id, identity_id="wa:id1", proxy_id="px-wa")
    add_proxy(fake, "px-wa", channel="whatsapp", whatsapp_profile_id="wa1", identity_id="wa:id1")
    fake.collection("whatsapp_profiles").update_one(
        {"_id": "wa1"}, {"$set": {"assigned_user_id": "member"}}
    )
    org = get_org(org_id)

    remove_member(org, "owner", "member")

    stored = fake.collection("whatsapp_profiles").find_one({"_id": "wa1"})
    assert stored["assigned_user_id"] is None
    assert stored["active"] is False
    assert stored["proxy_id"] == "px-wa"
    assert fake.collection("proxies").find_one({"_id": "px-wa"})["status"] == "assigned"


# ── Channel-aware provisioning ───────────────────────────────────────────


def test_reseller_and_fallback_usernames_are_channel_aware():
    assert provisioning.build_reseller_username("org1", "p1", "linkedin") == "outreach.org1.li.p1"
    assert provisioning.build_reseller_username("org1", "p1", "whatsapp") == "outreach.org1.wa.p1"
    assert (
        build_massive_username("parent", "p1", "US", channel="linkedin")
        .startswith("parent-subaccount-li-p1-country-US")
    )
    assert (
        build_massive_username("parent", "p1", "US", channel="whatsapp")
        .startswith("parent-subaccount-wa-p1-country-US")
    )
    assert build_massive_subuser("p1", "linkedin") == "subaccount-li-p1"
    assert build_massive_subuser("p1", "whatsapp") == "subaccount-wa-p1"


def test_whatsapp_fallback_proxy_is_stored_on_the_whatsapp_profile(fake, monkeypatch):
    from openoutreach.config import settings
    from openoutreach.proxies.service import validate_proxy_host

    monkeypatch.setattr(settings, "MASSIVE_PARENT_USERNAME", "parent")
    monkeypatch.setattr(settings, "MASSIVE_PROXY_PASSWORD", "account-key")
    monkeypatch.setattr(settings, "MASSIVE_PROXY_HOST", "proxy.example.com")
    monkeypatch.setattr(settings, "MASSIVE_PROXY_PORT", 8080)
    monkeypatch.setattr(provisioning, "validate_proxy_host", lambda host: None)
    monkeypatch.setattr(
        "openoutreach.proxies.models.validate_proxy_host",
        lambda host: None,
        raising=False,
    )
    monkeypatch.setattr(
        "openoutreach.proxies.service.validate_proxy_host",
        lambda host: None,
    )

    org_id = seed_owner(fake, cloud_profiles=1)
    add_whatsapp(fake, "wa1", "owner", org_id, identity_id="wa:id1")
    proxy = provision_massive_fallback(
        "wa1", "US", channel="whatsapp", created_by="owner"
    )
    assigned = assign_proxy_to_whatsapp(proxy._id, "wa1", "owner")

    assert proxy.channel == "whatsapp"
    assert proxy.username.startswith("parent-subaccount-wa-wa1-country-US")
    assert assigned.whatsapp_profile_id == "wa1"
    stored = fake.collection("whatsapp_profiles").find_one({"_id": "wa1"})
    assert stored["proxy_id"] == assigned._id


def test_whatsapp_fallback_reporting_matches_without_a_reseller_account(fake, monkeypatch):
    from openoutreach.config import settings
    from openoutreach.proxies.massive_reseller import MassiveResellerClient

    monkeypatch.setattr(settings, "MASSIVE_RESELLER_ENABLED", True)
    monkeypatch.setattr(settings, "MASSIVE_PARENT_USERNAME", "parent")
    monkeypatch.setattr(settings, "MASSIVE_PROXY_PASSWORD", "account-key")
    monkeypatch.setattr(
        MassiveResellerClient,
        "reporting_usage",
        lambda self, **kwargs: [
            {
                "subaccount": "subaccount-wa-p1",
                "bytes": 512,
                "period_start": "2026-11-01",
                "period_end": "2026-11-30",
            }
        ],
    )
    org_id = seed_owner(fake, cloud_profiles=1)
    add_whatsapp(fake, "wa1", "owner", org_id, identity_id="wa:id1", proxy_id="px-wa")
    add_proxy(
        fake,
        "px-wa",
        channel="whatsapp",
        whatsapp_profile_id="wa1",
        identity_id="wa:id1",
    )
    fake.collection("proxies").update_one(
        {"_id": "px-wa"},
        {
            "$set": {
                "massive_subuser": "subaccount-wa-p1",
                "massive_account_id": None,
            }
        },
    )

    result = sync_massive_reporting("2026-11-01", "2026-11-30")

    assert result["matched"] == 1
    snapshots = list(fake.collection("proxy_usage_snapshots").find({}))
    assert len(snapshots) == 1
    assert snapshots[0]["channel"] == "whatsapp"
    assert snapshots[0]["bytes"] == 512


def test_one_whatsapp_per_proxy_and_cross_identity_denied(fake):
    org_id = seed_owner(fake, cloud_profiles=1)
    add_whatsapp(fake, "wa1", "owner", org_id, identity_id="id1")
    add_whatsapp(fake, "wa2", "owner", org_id, identity_id="id2")
    add_proxy(fake, "px-wa", channel="whatsapp", identity_id="id1", status="available", owner_id=None, org_id=None)

    assign_proxy_to_whatsapp("px-wa", "wa1", "owner")

    with pytest.raises(Exception, match="another WhatsApp"):
        assign_proxy_to_whatsapp("px-wa", "wa2", "owner")


def test_whatsapp_proxy_assignment_denies_cross_tenant(fake):
    org_id = seed_owner(fake, cloud_profiles=1)
    add_whatsapp(fake, "wa1", "owner", org_id, identity_id="wa:id1")
    add_proxy(
        fake,
        "px-other",
        channel="whatsapp",
        identity_id="wa:id1",
        status="available",
        owner_id="other-owner",
        org_id="other-org",
    )

    with pytest.raises(Exception, match="another"):
        assign_proxy_to_whatsapp("px-other", "wa1", "owner")


def test_shared_duo_attach_requires_same_identity(fake):
    org_id = seed_owner(fake, cloud_profiles=1)
    add_linkedin(fake, "li1", "owner", org_id, identity_id="id1", proxy_id="px1")
    add_proxy(fake, "px1", channel="linkedin", linkedin_profile_id="li1", identity_id="id1")
    add_whatsapp(fake, "wa1", "owner", org_id, identity_id="id1", cloud_mode="duo_shared")
    add_whatsapp(fake, "wa2", "owner", org_id, identity_id="id2", cloud_mode="duo_shared")

    attach_shared_proxy_to_whatsapp(
        "px1", "wa1", "owner", identity_id="id1", org_id=org_id, assigned_by="owner"
    )
    with pytest.raises(Exception, match="identity"):
        attach_shared_proxy_to_whatsapp(
            "px1", "wa2", "owner", identity_id="id2", org_id=org_id, assigned_by="owner"
        )


def test_profile_deletion_retires_only_its_own_proxy(fake):
    org_id = seed_owner(fake, cloud_profiles=1)
    add_linkedin(fake, "li1", "owner", org_id, identity_id="id1", proxy_id="px1")
    add_proxy(fake, "px1", channel="duo", linkedin_profile_id="li1", whatsapp_profile_id="wa1", identity_id="id1")
    add_whatsapp(fake, "wa1", "owner", org_id, identity_id="id1", cloud_mode="duo_shared", proxy_id="px1")

    retire_proxy_for_profile("li1")
    shared = fake.collection("proxies").find_one({"_id": "px1"})
    assert shared["status"] == "assigned"
    assert shared["linkedin_profile_id"] is None
    assert shared["whatsapp_profile_id"] == "wa1"

    retire_proxy_for_whatsapp_profile("wa1")
    retired = fake.collection("proxies").find_one({"_id": "px1"})
    assert retired["status"] == "retired"


def test_unassign_keeps_the_subaccount_reserved_for_the_same_profile(fake):
    org_id = seed_owner(fake, cloud_profiles=1)
    add_whatsapp(fake, "wa1", "owner", org_id, identity_id="wa:id1", proxy_id="px-wa")
    add_proxy(fake, "px-wa", channel="whatsapp", whatsapp_profile_id="wa1", identity_id="wa:id1")

    unassign_proxy("px-wa", reason="seat_removed", actor="admin")

    proxy = fake.collection("proxies").find_one({"_id": "px-wa"})
    assert proxy["status"] == "disabled"
    assert proxy["whatsapp_profile_id"] is None
    assert proxy["last_assigned_whatsapp_profile_id"] == "wa1"
    stored = fake.collection("whatsapp_profiles").find_one({"_id": "wa1"})
    assert stored["proxy_id"] is None
    assert stored["active"] is False


# ── WhatsApp-only / separate-IP creation ─────────────────────────────────


def _patch_router_context(monkeypatch, *, plan: str = "cloud", cloud_profiles: int = 1):
    from openoutreach.api_v2.routers import mailboxes as mailbox_router
    from openoutreach.whatsapp.api import router as wa_router

    ctx = SimpleNamespace(
        org_id="org-owner",
        accounting_owner_id="owner",
        team_enabled=True,
        is_shared=False,
        role="owner",
    )
    effective = EffectivePlan(
        plan=plan,
        cloud_profiles=cloud_profiles,
        linkedin_account_limit=1 + cloud_profiles,
        whatsapp_account_limit=1,
        campaign_limit=None,
        subscription_status="active",
        trial_ends_at=None,
        billing_owner_id="owner",
        billing_owner_email="owner@example.com",
        org_id="org-owner",
        role="owner",
        is_billing_owner=True,
        cloud_seat_limit=1 + cloud_profiles,
    )
    monkeypatch.setattr(wa_router, "resolve_org_context", lambda user: ctx)
    monkeypatch.setattr(wa_router, "resolve_effective_plan", lambda user: effective)
    monkeypatch.setattr(wa_router, "whatsapp_cloud_enabled", lambda: True)
    monkeypatch.setattr(mailbox_router, "resolve_org_context", lambda user: ctx)
    monkeypatch.setattr(mailbox_router, "resolve_effective_plan", lambda user: effective)
    return ctx, effective


def test_whatsapp_only_creation_reserves_one_seat_and_assigns_a_proxy(fake, monkeypatch):
    import asyncio
    from openoutreach.api_v2.routers import mailboxes as mailbox_router  # noqa: F401
    from openoutreach.whatsapp.api.router import WhatsAppProfileCreate, create_profile

    org_id = seed_owner(fake, cloud_profiles=1)
    _patch_router_context(monkeypatch)
    fake.collection("users").update_one(
        {"_id": "owner"}, {"$set": {"org_id": org_id}}
    )

    def fake_provision(profile_id, user_id, org_id_value, country, subdivision=None, city=None, *, created_by=None, channel="linkedin"):
        assert channel == "whatsapp"
        proxy = provision_massive_fallback(
            profile_id,
            country,
            subdivision,
            city,
            channel="whatsapp",
            created_by=created_by,
        )
        return assign_proxy_to_whatsapp(proxy._id, profile_id, user_id)

    from openoutreach.config import settings

    monkeypatch.setattr(settings, "MASSIVE_PARENT_USERNAME", "parent")
    monkeypatch.setattr(settings, "MASSIVE_PROXY_PASSWORD", "account-key")
    monkeypatch.setattr(settings, "MASSIVE_PROXY_HOST", "proxy.example.com")
    monkeypatch.setattr(settings, "MASSIVE_PROXY_PORT", 8080)
    monkeypatch.setattr(provisioning, "validate_proxy_host", lambda host: None)
    monkeypatch.setattr(
        "openoutreach.proxies.models.validate_proxy_host",
        lambda host: None,
        raising=False,
    )
    monkeypatch.setattr(
        "openoutreach.proxies.service.validate_proxy_host",
        lambda host: None,
    )
    monkeypatch.setattr(
        "openoutreach.proxies.provisioning.provision_managed_proxy",
        fake_provision,
    )

    result = asyncio.run(
        create_profile(
            WhatsAppProfileCreate(
                display_name="Owner WhatsApp",
                execution_mode="cloud",
                cloud_mode="whatsapp_only",
                proxy_region_country="US",
            ),
            user_id="owner",
        )
    )

    assert result["executionMode"] == "cloud"
    assert result["cloudMode"] == "whatsapp_only"
    assert result["proxyId"]
    assert cloud_seat_count_for_org(org_id, "owner") == 1
    assert fake.collection("cloud_seat_usage").find_one({"_id": "owner"})["count"] == 1


def test_duo_shared_creation_uses_one_seat_and_one_proxy(fake, monkeypatch):
    import asyncio
    from openoutreach.whatsapp.api.router import WhatsAppProfileCreate, create_profile

    org_id = seed_owner(fake, cloud_profiles=1)
    add_linkedin(fake, "li1", "owner", org_id, identity_id="id1", proxy_id="px1")
    add_proxy(fake, "px1", channel="linkedin", linkedin_profile_id="li1", identity_id="id1")
    _patch_router_context(monkeypatch)
    fake.collection("users").update_one({"_id": "owner"}, {"$set": {"org_id": org_id}})
    monkeypatch.setattr(
        "openoutreach.whatsapp.cloud.can_access_channel_doc",
        lambda user, doc: True,
    )

    result = asyncio.run(
        create_profile(
            WhatsAppProfileCreate(
                execution_mode="cloud",
                cloud_mode="duo_shared",
                duo_linkedin_profile_id="li1",
            ),
            user_id="owner",
        )
    )

    assert result["cloudMode"] == "duo_shared"
    assert result["proxyId"] == "px1"
    assert cloud_seat_count_for_org(org_id, "owner") == 1
    proxy = fake.collection("proxies").find_one({"_id": "px1"})
    assert proxy["whatsapp_profile_id"] == result["id"]
    assert proxy["channel"] == "duo"


def test_duo_separate_creation_gets_a_second_proxy_but_one_seat(fake, monkeypatch):
    import asyncio
    from openoutreach.whatsapp.api.router import WhatsAppProfileCreate, create_profile

    org_id = seed_owner(fake, cloud_profiles=1)
    add_linkedin(fake, "li1", "owner", org_id, identity_id="id1", proxy_id="px1")
    add_proxy(fake, "px1", channel="linkedin", linkedin_profile_id="li1", identity_id="id1")
    _patch_router_context(monkeypatch)
    fake.collection("users").update_one({"_id": "owner"}, {"$set": {"org_id": org_id}})
    monkeypatch.setattr(
        "openoutreach.whatsapp.cloud.can_access_channel_doc",
        lambda user, doc: True,
    )

    def fake_provision(profile_id, user_id, org_id_value, country, subdivision=None, city=None, *, created_by=None, channel="linkedin"):
        assert channel == "whatsapp"
        proxy = provision_massive_fallback(
            profile_id, country, subdivision, city, channel="whatsapp", created_by=created_by
        )
        return assign_proxy_to_whatsapp(proxy._id, profile_id, user_id)

    from openoutreach.config import settings

    monkeypatch.setattr(settings, "MASSIVE_PARENT_USERNAME", "parent")
    monkeypatch.setattr(settings, "MASSIVE_PROXY_PASSWORD", "account-key")
    monkeypatch.setattr(settings, "MASSIVE_PROXY_HOST", "proxy.example.com")
    monkeypatch.setattr(settings, "MASSIVE_PROXY_PORT", 8080)
    monkeypatch.setattr(provisioning, "validate_proxy_host", lambda host: None)
    monkeypatch.setattr(
        "openoutreach.proxies.models.validate_proxy_host",
        lambda host: None,
        raising=False,
    )
    monkeypatch.setattr(
        "openoutreach.proxies.service.validate_proxy_host",
        lambda host: None,
    )
    monkeypatch.setattr(
        "openoutreach.proxies.provisioning.provision_managed_proxy",
        fake_provision,
    )

    result = asyncio.run(
        create_profile(
            WhatsAppProfileCreate(
                execution_mode="cloud",
                cloud_mode="duo_separate",
                duo_linkedin_profile_id="li1",
                proxy_region_country="US",
            ),
            user_id="owner",
        )
    )

    assert result["proxyId"] and result["proxyId"] != "px1"
    assert cloud_seat_count_for_org(org_id, "owner") == 1
    counter = fake.collection("cloud_seat_usage").find_one({"_id": "owner"})
    assert counter is None or counter["count"] == 0


# ── Launch guard and daemon filtering ────────────────────────────────────


def test_whatsapp_only_launch_guard_requires_its_own_proxy(fake, monkeypatch):
    from openoutreach.whatsapp.browser.launch import _whatsapp_proxy_config

    org_id = seed_owner(fake, cloud_profiles=1)
    profile = add_whatsapp(fake, "wa1", "owner", org_id, identity_id="wa:id1", proxy_id="px-wa")
    add_proxy(fake, "px-wa", channel="whatsapp", whatsapp_profile_id="wa1", identity_id="wa:id1")

    config = _whatsapp_proxy_config(profile)
    assert config is not None
    assert config["username"] == "parent_px-wa"

    fake.collection("proxies").update_one({"_id": "px-wa"}, {"$set": {"massive_status": "disabled"}})
    with pytest.raises(Exception, match="not active"):
        _whatsapp_proxy_config(profile)


def test_cloud_wa_ready_supports_whatsapp_only_and_duo_shared(fake, monkeypatch):
    from openoutreach.core.daemon import _cloud_wa_ready

    org_id = seed_owner(fake, cloud_profiles=1)
    wa_only = add_whatsapp(fake, "wa1", "owner", org_id, identity_id="wa:id1", proxy_id="px-wa")
    add_proxy(fake, "px-wa", channel="whatsapp", whatsapp_profile_id="wa1", identity_id="wa:id1")
    assert _cloud_wa_ready(wa_only) is True

    add_linkedin(fake, "li1", "owner", org_id, identity_id="id1", proxy_id="px1")
    add_proxy(fake, "px1", channel="duo", linkedin_profile_id="li1", whatsapp_profile_id="wa2", identity_id="id1")
    duo = add_whatsapp(fake, "wa2", "owner", org_id, identity_id="id1", cloud_mode="duo_shared", proxy_id="px1")
    assert _cloud_wa_ready(duo) is True

    fake.collection("linkedin_profiles").update_one(
        {"_id": "li1"}, {"$set": {"active": False, "is_active": False}}
    )
    assert _cloud_wa_ready(duo) is False


# ── Per-channel usage ────────────────────────────────────────────────────


def test_separate_ip_duo_usage_is_split_by_channel(fake):
    org_id = seed_owner(fake, cloud_profiles=1)
    add_linkedin(fake, "li1", "owner", org_id, identity_id="id1", proxy_id="px-li")
    add_proxy(fake, "px-li", channel="linkedin", linkedin_profile_id="li1", identity_id="id1")
    add_proxy(fake, "px-wa", channel="whatsapp", whatsapp_profile_id="wa1", identity_id="id1")
    add_whatsapp(fake, "wa1", "owner", org_id, identity_id="id1", cloud_mode="duo_separate", proxy_id="px-wa")

    li_proxy = Proxy.get("px-li")
    wa_proxy = Proxy.get("px-wa")
    record_usage_snapshot(
        proxy=li_proxy, subuser="li", bytes_used=100, period_start="2026-11-01", period_end="2026-11-30", channel="linkedin"
    )
    record_usage_snapshot(
        proxy=wa_proxy, subuser="wa", bytes_used=200, period_start="2026-11-01", period_end="2026-11-30", channel="whatsapp"
    )

    summary = get_usage_summary(period_start="2026-11-01", period_end="2026-11-30")
    assert summary["per_channel"][0]["channel"] == "whatsapp"
    assert summary["per_channel"][0]["bytes"] == 200
    assert summary["per_channel"][1]["channel"] == "linkedin"
    assert summary["per_channel"][1]["bytes"] == 100
    assert summary["per_workspace_channel"]


def test_shared_ip_duo_usage_is_combined_not_split(fake):
    org_id = seed_owner(fake, cloud_profiles=1)
    add_linkedin(fake, "li1", "owner", org_id, identity_id="id1", proxy_id="px1")
    add_proxy(fake, "px1", channel="duo", linkedin_profile_id="li1", whatsapp_profile_id="wa1", identity_id="id1")
    add_whatsapp(fake, "wa1", "owner", org_id, identity_id="id1", cloud_mode="duo_shared", proxy_id="px1")

    record_usage_snapshot(
        proxy=Proxy.get("px1"), subuser="duo", bytes_used=350, period_start="2026-11-01", period_end="2026-11-30", channel="duo"
    )

    summary = get_usage_summary(period_start="2026-11-01", period_end="2026-11-30")
    assert [entry["channel"] for entry in summary["per_channel"]] == ["duo"]
    assert summary["per_channel"][0]["bytes"] == 350


# ── Email BYO slot ───────────────────────────────────────────────────────


def _effective(plan: str, *, linkedin: int, whatsapp: int, cloud: int) -> EffectivePlan:
    return EffectivePlan(
        plan=plan,
        cloud_profiles=0,
        linkedin_account_limit=linkedin,
        whatsapp_account_limit=whatsapp,
        campaign_limit=None,
        subscription_status="active",
        trial_ends_at=None,
        billing_owner_id="owner",
        billing_owner_email="owner@example.com",
        org_id="org-owner",
        role="owner",
        is_billing_owner=True,
        cloud_seat_limit=cloud,
    )


def test_email_slot_limit_is_one_per_seat():
    assert email_slot_limit(_effective("starter", linkedin=1, whatsapp=1, cloud=0)) == 1
    assert email_slot_limit(_effective("business", linkedin=3, whatsapp=3, cloud=0)) == 3
    assert email_slot_limit(_effective("cloud", linkedin=3, whatsapp=1, cloud=3)) == 3
    assert email_slot_usage(_effective("starter", linkedin=1, whatsapp=1, cloud=0), 1)["at_limit"] is True


def test_email_slot_enforced_and_byo_has_no_proxy(fake, monkeypatch):
    import asyncio
    from openoutreach.api_v2.routers import mailboxes as mailbox_router

    org_id = seed_owner(fake, cloud_profiles=0, plan="starter")
    _patch_router_context(monkeypatch, plan="starter", cloud_profiles=0)
    fake.collection("users").update_one({"_id": "owner"}, {"$set": {"org_id": org_id}})
    monkeypatch.setattr(mailbox_router, "verify_auth", lambda *args: (True, "ok"))
    monkeypatch.setattr(mailbox_router, "verify_imap_auth", lambda *args: (True, "ok"))

    first = asyncio.run(
        mailbox_router.create_mailbox(
            mailbox_router.MailboxCreate(
                username="owner@example.com",
                password="secret",
                host="smtp.example.com",
            ),
            user_id="owner",
        )
    )
    assert first.seat_id
    assert first.managed is False
    stored = fake.collection("mailboxes").find_one({"_id": first.id})
    assert "proxy" not in stored
    assert "proxy_id" not in stored

    with pytest.raises(Exception) as exc:
        asyncio.run(
            mailbox_router.create_mailbox(
                mailbox_router.MailboxCreate(
                    username="second@example.com",
                    password="secret",
                    host="smtp.example.com",
                ),
                user_id="owner",
            )
        )
    assert "Email slot limit" in str(exc.value)


def test_deleting_a_desktop_profile_does_not_release_a_cloud_seat(fake, monkeypatch):
    import asyncio
    from types import SimpleNamespace

    from openoutreach.api_v2.routers import linkedin_profiles as profiles_router

    org_id = seed_owner(fake, cloud_profiles=1)
    fake.collection("linkedin_profiles").insert_one(
        {
            "_id": "desktop-p",
            "user_id": "owner",
            "org_id": org_id,
            "execution_mode": "desktop",
            "active": True,
            "is_active": True,
        }
    )
    fake.collection("linkedin_credentials").insert_one(
        {"_id": "cred-desktop", "linkedin_profile_id": "desktop-p", "user_id": "owner"}
    )
    fake.collection("cloud_seat_usage").insert_one({"_id": "owner", "count": 1})
    released = {"linkedin": 0, "cloud": 0}

    monkeypatch.setattr(
        profiles_router, "get_mongodb_collection", fake.get_mongodb_collection
    )
    monkeypatch.setattr(profiles_router, "_profile_query", lambda user_id: {})
    monkeypatch.setattr(
        profiles_router,
        "User",
        SimpleNamespace(get=lambda user_id: SimpleNamespace(_id=user_id)),
    )
    monkeypatch.setattr(
        profiles_router, "can_delete_profile", lambda user, doc: True
    )
    monkeypatch.setattr(
        profiles_router,
        "release_linkedin_seat",
        lambda user_id: released.__setitem__("linkedin", released["linkedin"] + 1),
    )
    monkeypatch.setattr(
        "openoutreach.billing.cloud_seats.release_cloud_seat",
        lambda user_id: released.__setitem__("cloud", released["cloud"] + 1),
    )

    asyncio.run(profiles_router.delete_profile("desktop-p", user_id="owner"))

    assert released["linkedin"] == 1
    assert released["cloud"] == 0
    assert fake.collection("cloud_seat_usage").find_one({"_id": "owner"})["count"] == 1


# ── Security ─────────────────────────────────────────────────────────────


def test_proxy_public_dict_never_contains_credentials():
    proxy = Proxy(
        _id="px1",
        host="proxy.example.com",
        port=8080,
        username="parent_sub",
        password_encrypted=safe_encrypt("super-secret"),
    )
    payload = proxy.public_dict()
    assert "super-secret" not in str(payload)
    assert "password_encrypted" not in payload
    assert payload["has_password"] is True


def test_whatsapp_serialization_never_contains_proxy_credentials(fake):
    from openoutreach.whatsapp.api.router import _serialize

    org_id = seed_owner(fake, cloud_profiles=1)
    profile = add_whatsapp(fake, "wa1", "owner", org_id, identity_id="wa:id1", proxy_id="px-wa")
    add_proxy(fake, "px-wa", channel="whatsapp", whatsapp_profile_id="wa1", identity_id="wa:id1")

    payload = _serialize(profile)
    assert "secret" not in str(payload)
    assert "password" not in str(payload).lower()
    assert payload["proxyId"] == "px-wa"
