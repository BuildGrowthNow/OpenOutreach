"""Phase 0 cloud seat, webhook, proxy, and launch-guard tests."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from starlette.requests import Request

from openoutreach.api_v2.routers.daemon import bootstrap_daemon, get_profile_details
from openoutreach.billing.downgrade_handler import pause_excess_linkedin_profiles
from openoutreach.billing.enforcement import PlanEnforcer
from openoutreach.billing.plans import (
    apply_plan_entitlements,
    effective_cloud_seat_limit,
    effective_linkedin_account_limit,
)
from openoutreach.billing.webhooks import _sync_subscription_items
from openoutreach.linkedin.browser.launch import start_browser_session
from openoutreach.linkedin.exceptions import CloudProxyRequiredError
from openoutreach.mongodb.models_user import User
from openoutreach.proxies.models import ProxyReuseError
from openoutreach.proxies.parser import parse_bulk_proxies
from openoutreach.proxies.region import RegionError, normalize_region
from openoutreach.proxies.service import assign_proxy_to_profile, import_proxies


@pytest.fixture(autouse=True)
def encryption_key(monkeypatch):
    monkeypatch.setenv("COOKIE_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.delenv("SECRET_KEY", raising=False)


def _subscription(items):
    return {"items": {"data": items}}


def _item(price_key, quantity=1, interval="month"):
    return {
        "quantity": quantity,
        "price": {
            "metadata": {"price_key": price_key},
            "recurring": {"interval": interval},
        },
    }


def test_cloud_plan_includes_one_base_seat():
    assert effective_linkedin_account_limit("cloud", 0, 1) == 1
    assert effective_linkedin_account_limit("cloud", 2, 1) == 3
    assert effective_cloud_seat_limit("cloud", 0) == 1
    assert effective_cloud_seat_limit("cloud", 2) == 3


def test_non_cloud_plan_keeps_plan_limit():
    assert effective_linkedin_account_limit("pro", 3, 1) == 1
    assert effective_cloud_seat_limit("pro", 3) == 3


def test_apply_plan_entitlements_raises_cloud_limit():
    user = User(
        _id="u1",
        email="user@example.com",
        plan="cloud",
        cloud_profiles=2,
        linkedin_account_limit=1,
    )

    apply_plan_entitlements(user)

    assert user.linkedin_account_limit == 3
    assert user.whatsapp_account_limit == 1


def test_cloud_execution_respects_purchased_seats():
    user = User(
        _id="u1",
        email="user@example.com",
        plan="cloud",
        cloud_profiles=1,
        subscription_status="active",
    )

    with patch("openoutreach.billing.enforcement.get_mongodb_collection") as get_collection:
        collection = MagicMock()
        collection.count_documents.return_value = 2
        get_collection.return_value = collection

        allowed, error = PlanEnforcer.can_use_cloud_execution(user)

    assert allowed is False
    assert "2/2" in error


def test_webhook_syncs_base_plan_and_all_cloud_seat_items():
    user = User(_id="u1", email="user@example.com", plan="starter")

    _sync_subscription_items(
        user,
        _subscription([
            _item("cloud_monthly"),
            _item("cloud_addon", quantity=2),
        ]),
    )

    assert user.plan == "cloud"
    assert user.cloud_profiles == 2
    assert user.linkedin_account_limit == 3


def test_webhook_never_treats_cloud_addon_as_plan():
    user = User(_id="u1", email="user@example.com", plan="pro", cloud_profiles=0)

    _sync_subscription_items(user, _subscription([_item("cloud_addon", quantity=4)]))

    assert user.plan == "pro"
    assert user.cloud_profiles == 4
    assert user.linkedin_account_limit == 1


def test_seat_reduction_pauses_excess_profiles():
    profiles = [
        {"_id": "p1", "linkedin_username": "one"},
        {"_id": "p2", "linkedin_username": "two"},
        {"_id": "p3", "linkedin_username": "three"},
    ]
    collection = MagicMock()
    collection.find.return_value = profiles
    collection.update_many.return_value.modified_count = 2

    with patch("openoutreach.billing.downgrade_handler.get_mongodb_collection", return_value=collection):
        result = pause_excess_linkedin_profiles("u1", 1)

    assert result == {"deactivated": 2, "error": False}
    update = collection.update_many.call_args
    assert update.args[0] == {"_id": {"$in": ["p2", "p3"]}}
    assert update.args[1]["$set"]["is_active"] is False
    assert update.args[1]["$set"]["active"] is False


def test_proxy_parser_accepts_supported_formats():
    text = "\n".join([
        "proxy.example.com:8080:user:secret:US",
        "socks5://user2:secret2@other.example.com:1080",
        "third.example.com:3128:user3:secret3",
    ])

    entries, errors = parse_bulk_proxies(text, default_country="DE")

    assert errors == []
    assert len(entries) == 3
    assert entries[0]["country"] == "US"
    assert entries[1]["protocol"] == "socks5"
    assert entries[1]["country"] == "DE"
    assert entries[2]["port"] == 3128


def test_proxy_parser_reports_duplicates_without_echoing_secrets():
    text = "proxy.example.com:8080:user:secret:US\nproxy.example.com:8080:user:secret:US"

    entries, errors = parse_bulk_proxies(text)

    assert len(entries) == 1
    assert errors == [{"line": 2, "error": "Duplicate proxy"}]
    assert "secret" not in str(errors)


def test_region_requires_a_country():
    with pytest.raises(RegionError):
        normalize_region("", None, None)

    assert normalize_region("us", "ny", "new york") == ("US", "NY", "new york")


def test_proxy_reuse_is_rejected():
    collection = MagicMock()
    collection.find_one.return_value = {
        "_id": "proxy-1",
        "linkedin_profile_id": "another-profile",
        "status": "available",
    }

    with patch("openoutreach.proxies.service.get_mongodb_collection", return_value=collection):
        with pytest.raises(ProxyReuseError):
            assign_proxy_to_profile("proxy-1", "profile-1", "user-1")


def test_proxy_import_encrypts_password_and_never_returns_it():
    collection = MagicMock()
    collection.find_one.return_value = None

    with patch("openoutreach.proxies.service.get_mongodb_collection", return_value=collection), patch(
        "openoutreach.proxies.models.get_mongodb_collection", return_value=collection
    ):
        result = import_proxies("proxy.example.com:8080:user:super-secret:US")

    assert result["created"] == 1
    stored = collection.update_one.call_args.args[1]["$set"]
    assert stored["password_encrypted"] != "super-secret"
    assert "super-secret" not in str(result)
    assert result["proxies"][0]["username"] == "user…" or result["proxies"][0]["username"] == "***"


class _FakeProfile:
    pk = "profile-1"
    execution_mode = "cloud"
    proxy_server = None
    proxy_username = None
    proxy_password = None
    cookie_data = None

    def refresh_from_db(self, fields=None):
        return None


class _FakeSession:
    linkedin_profile = _FakeProfile()


def test_cloud_profile_without_proxy_never_launches():
    with pytest.raises(CloudProxyRequiredError):
        start_browser_session(_FakeSession())


def test_bootstrap_and_legacy_profile_endpoints_are_gone():
    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/api/daemon/bootstrap",
        "headers": [],
        "client": ("127.0.0.1", 1234),
    })

    with pytest.raises(HTTPException) as bootstrap_error:
        asyncio.run(bootstrap_daemon(request=request, linkedin_profile_id=None))
    assert bootstrap_error.value.status_code == 410

    with pytest.raises(HTTPException) as legacy_error:
        asyncio.run(get_profile_details("profile-1", user_id="user-1"))
    assert legacy_error.value.status_code == 410


def test_intended_plan_roundtrips_on_user():
    user = User(_id="u1", email="user@example.com", intended_plan="cloud")

    restored = User.from_dict(user.to_dict())

    assert restored.intended_plan == "cloud"
