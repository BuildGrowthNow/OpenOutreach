"""Phase 4 Cloud Duo shared-IP WhatsApp tests."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet

from openoutreach.mongodb.crypto import safe_encrypt
from openoutreach.proxies.models import Proxy
from openoutreach.core.daemon import _cloud_wa_ready
from openoutreach.whatsapp import cloud as wa_cloud
from openoutreach.whatsapp.browser.launch import _whatsapp_proxy_config
from openoutreach.whatsapp.models.profile import WhatsAppProfile
from tests.fake_mongo import FakeMongo


@pytest.fixture(autouse=True)
def encryption_key(monkeypatch):
    monkeypatch.setenv("COOKIE_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.delenv("SECRET_KEY", raising=False)


@pytest.fixture
def fake(monkeypatch):
    mongo = FakeMongo()
    monkeypatch.setattr(
        "openoutreach.whatsapp.cloud.get_mongodb_collection",
        mongo.get_mongodb_collection,
    )
    monkeypatch.setattr(
        "openoutreach.proxies.models.get_mongodb_collection",
        mongo.get_mongodb_collection,
    )
    return mongo


def _seed_duo(fake: FakeMongo, *, active: bool = True, massive_status: str = "active"):
    fake.collection("linkedin_profiles").insert_one(
        {
            "_id": "li1",
            "user_id": "u1",
            "org_id": "org1",
            "execution_mode": "cloud",
            "proxy_id": "px1",
            "identity_id": "id1",
            "active": active,
            "is_active": active,
        }
    )
    fake.collection("linkedin_credentials").insert_one(
        {
            "_id": "cred1",
            "linkedin_profile_id": "li1",
            "user_id": "u1",
        }
    )
    fake.collection("proxies").insert_one(
        {
            "_id": "px1",
            "provider": "massive_residential",
            "protocol": "http",
            "host": "proxy.example.com",
            "port": 8080,
            "username": "parent_sub",
            "password_encrypted": safe_encrypt("secret"),
            "country": "US",
            "status": "assigned",
            "linkedin_profile_id": "li1",
            "assigned_user_id": "u1",
            "assigned_org_id": "org1",
            "identity_id": "id1",
            "massive_status": massive_status,
        }
    )


def test_resolve_duo_share_returns_the_linkedin_proxy(fake, monkeypatch):
    _seed_duo(fake)
    monkeypatch.setattr(
        "openoutreach.whatsapp.cloud.can_access_channel_doc",
        lambda user, doc: True,
    )
    profile, proxy, identity = wa_cloud.resolve_duo_share(
        SimpleNamespace(_id="u1"), "org1", "li1"
    )
    assert profile["_id"] == "li1"
    assert proxy._id == "px1"
    assert identity == "id1"


def test_resolve_duo_share_rejects_a_second_whatsapp_on_the_same_proxy(
    fake, monkeypatch
):
    _seed_duo(fake)
    fake.collection("whatsapp_profiles").insert_one(
        {"_id": "wa1", "proxy_id": "px1", "execution_mode": "cloud"}
    )
    monkeypatch.setattr(
        "openoutreach.whatsapp.cloud.can_access_channel_doc",
        lambda user, doc: True,
    )
    with pytest.raises(wa_cloud.WhatsAppCloudError, match="already has a WhatsApp"):
        wa_cloud.resolve_duo_share(SimpleNamespace(_id="u1"), "org1", "li1")


def test_resolve_duo_share_rejects_a_paused_linkedin_seat(fake, monkeypatch):
    _seed_duo(fake, active=False)
    monkeypatch.setattr(
        "openoutreach.whatsapp.cloud.can_access_channel_doc",
        lambda user, doc: True,
    )
    with pytest.raises(wa_cloud.WhatsAppCloudError, match="paused"):
        wa_cloud.resolve_duo_share(SimpleNamespace(_id="u1"), "org1", "li1")


def test_resolve_duo_share_rejects_paused_or_disabled_proxy(fake, monkeypatch):
    _seed_duo(fake, massive_status="disabled")
    monkeypatch.setattr(
        "openoutreach.whatsapp.cloud.can_access_channel_doc",
        lambda user, doc: True,
    )
    with pytest.raises(wa_cloud.WhatsAppCloudError, match="not active"):
        wa_cloud.resolve_duo_share(SimpleNamespace(_id="u1"), "org1", "li1")


def test_cloud_wa_ready_requires_an_active_linkedin_seat_and_proxy(fake, monkeypatch):
    _seed_duo(fake)
    monkeypatch.setattr(
        "openoutreach.mongodb.connection.get_mongodb_collection",
        fake.get_mongodb_collection,
    )
    profile = WhatsAppProfile(
        _id="wa1",
        execution_mode="cloud",
        proxy_id="px1",
        org_id="org1",
        identity_id="id1",
    )
    assert _cloud_wa_ready(profile) is True

    fake.collection("linkedin_profiles").update_one(
        {"_id": "li1"}, {"$set": {"active": False, "is_active": False}}
    )
    assert _cloud_wa_ready(profile) is False

    fake.collection("linkedin_profiles").update_one(
        {"_id": "li1"}, {"$set": {"active": True, "is_active": True}}
    )
    fake.collection("proxies").update_one(
        {"_id": "px1"}, {"$set": {"massive_status": "disabled"}}
    )
    assert _cloud_wa_ready(profile) is False


def test_whatsapp_proxy_config_is_desktop_free_and_cloud_guarded(monkeypatch):
    desktop = WhatsAppProfile(execution_mode="desktop")
    assert _whatsapp_proxy_config(desktop) is None

    cloud = WhatsAppProfile(execution_mode="cloud", proxy_id="px1", identity_id="id1")
    monkeypatch.setattr(
        "openoutreach.whatsapp.browser.launch.settings.WHATSAPP_CLOUD_PROXY_ENABLED",
        False,
    )
    with pytest.raises(wa_cloud.WhatsAppCloudProxyError, match="not enabled"):
        _whatsapp_proxy_config(cloud)

    monkeypatch.setattr(
        "openoutreach.whatsapp.browser.launch.settings.WHATSAPP_CLOUD_PROXY_ENABLED",
        True,
    )
    proxy = Proxy(
        _id="px1",
        host="proxy.example.com",
        port=8080,
        username="parent_sub",
        password_encrypted=safe_encrypt("secret"),
        status="assigned",
        linkedin_profile_id="li1",
        assigned_org_id="org1",
        identity_id="id1",
        massive_status="active",
    )
    monkeypatch.setattr(
        "openoutreach.whatsapp.browser.launch.Proxy.get",
        staticmethod(lambda proxy_id: proxy if proxy_id == "px1" else None),
    )
    config = _whatsapp_proxy_config(cloud)
    assert config == {
        "server": "http://proxy.example.com:8080",
        "username": "parent_sub",
        "password": "secret",
    }
