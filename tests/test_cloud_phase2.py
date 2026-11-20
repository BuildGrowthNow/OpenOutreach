"""Phase 2 Massive Reseller, Pool Stats, provisioning, and budget tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet

from openoutreach.proxies import provisioning
from openoutreach.proxies.massive_reseller import (
    MassivePoolStatsClient,
    MassiveResellerClient,
    MassiveResellerConfig,
    MassiveResellerError,
    generate_subaccount_password,
    pool_stats_status,
    reseller_status,
)
from openoutreach.proxies.models import Proxy
from tests.fake_mongo import FakeMongo


PATCH_TARGETS = [
    "openoutreach.proxies.models.get_mongodb_collection",
    "openoutreach.proxies.service.get_mongodb_collection",
    "openoutreach.proxies.provisioning.get_mongodb_collection",
    "openoutreach.organizations.audit.get_mongodb_collection",
]


@pytest.fixture(autouse=True)
def encryption_key(monkeypatch):
    from openoutreach.proxies import massive_reseller

    massive_reseller._POOL_STATS_CACHE.clear()
    monkeypatch.setenv("COOKIE_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.delenv("SECRET_KEY", raising=False)


@pytest.fixture
def fake(monkeypatch):
    mongo = FakeMongo()
    for target in PATCH_TARGETS:
        monkeypatch.setattr(target, mongo.get_mongodb_collection)
    return mongo


@pytest.fixture
def reseller_settings(monkeypatch):
    from openoutreach.config import settings

    monkeypatch.setattr(settings, "MASSIVE_RESELLER_ENABLED", True)
    monkeypatch.setattr(settings, "MASSIVE_PARENT_USERNAME", "parent")
    monkeypatch.setattr(settings, "MASSIVE_PROXY_PASSWORD", "account-key")
    monkeypatch.setattr(settings, "MASSIVE_PROXY_HOST", "proxy.example.com")
    monkeypatch.setattr(settings, "MASSIVE_PROXY_PORT", 8080)
    monkeypatch.setattr(settings, "MASSIVE_RESELLER_DEFAULT_LIMIT_BYTES", 5_000_000_000)
    monkeypatch.setattr(settings, "MASSIVE_MONTHLY_SOFT_LIMIT_BYTES", 25_000_000_000)
    monkeypatch.setattr(settings, "MASSIVE_MONTHLY_HARD_LIMIT_BYTES", 40_000_000_000)
    monkeypatch.setattr(settings, "MASSIVE_POOL_STATS_ENABLED", True)
    monkeypatch.setattr(settings, "MASSIVE_POOL_STATS_MIN_NODES", 1000)
    monkeypatch.setattr(settings, "MASSIVE_REPORTING_BASE_URL", "https://reporting.example.com")
    return settings


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class _FakeHTTPClient:
    calls: list[dict] = []
    responses: list[_FakeResponse] = []

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def request(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        return self.responses.pop(0)

    def get(self, url, **kwargs):
        self.calls.append({"method": "GET", "url": url, **kwargs})
        return self.responses.pop(0)


@pytest.fixture
def fake_http(monkeypatch):
    _FakeHTTPClient.calls = []
    _FakeHTTPClient.responses = []
    monkeypatch.setattr(
        "openoutreach.proxies.massive_reseller.httpx.Client", _FakeHTTPClient
    )
    return _FakeHTTPClient


def test_reseller_status_never_returns_secret(reseller_settings):
    status = reseller_status()
    assert status["enabled"] is True
    assert status["configured"] is True
    assert status["parent_username_set"] is True
    assert status["api_key_set"] is True
    assert "account-key" not in str(status)


def test_pool_stats_status_never_returns_secret(reseller_settings):
    status = pool_stats_status()
    assert status["configured"] is True
    assert "account-key" not in str(status)


def test_reseller_config_repr_hides_secret(reseller_settings):
    config = MassiveResellerConfig.from_settings()
    assert config is not None
    assert "account-key" not in repr(config)


def test_reseller_create_sends_expected_payload_and_strips_password(
    reseller_settings, fake_http
):
    fake_http.responses = [
        _FakeResponse(
            {
                "data": {
                    "id": "acct-1",
                    "username": "outreach-org-li-profile",
                    "password": "sub-secret",
                    "limit": 5_000_000_000,
                    "status": "active",
                }
            }
        )
    ]
    client = MassiveResellerClient()
    account = client.create_account("outreach-org-li-profile", "sub-secret", 5_000_000_000)

    call = fake_http.calls[0]
    assert call["method"] == "POST"
    assert call["url"].endswith("/accounts")
    assert call["json"]["username"] == "outreach-org-li-profile"
    assert call["json"]["password"] == "sub-secret"
    assert call["json"]["limit"] == 5_000_000_000
    assert call["json"]["sync_with_parent"] is True
    assert "sub-secret" not in str(account)
    assert account["account_id"] == "acct-1"


def test_reseller_409_maps_to_already_exists(reseller_settings, fake_http):
    fake_http.responses = [_FakeResponse({"error": "exists"}, status_code=409)]
    client = MassiveResellerClient()
    with pytest.raises(MassiveResellerError) as exc_info:
        client.create_account("outreach-org-li-profile", "secret", 1)
    assert exc_info.value.code == "already_exists"
    assert "secret" not in str(exc_info.value)


def test_enable_and_disable_use_documented_action_endpoints(
    reseller_settings, fake_http
):
    fake_http.responses = [
        _FakeResponse({"id": "acct-1"}),
        _FakeResponse({"id": "acct-1"}),
    ]
    client = MassiveResellerClient()

    client.disable_account("acct-1")
    client.enable_account("acct-1")

    disable_call, enable_call = fake_http.calls
    assert disable_call["method"] == "POST"
    assert disable_call["url"].endswith("/accounts/acct-1/disable")
    assert enable_call["method"] == "POST"
    assert enable_call["url"].endswith("/accounts/acct-1/enable")


def test_allocate_traffic_sends_limit_field(reseller_settings, fake_http):
    fake_http.responses = [_FakeResponse({"created_at": 1, "limit": 1_000_000_000})]
    client = MassiveResellerClient()

    client.allocate_traffic("acct-1", 1_000_000_000)

    call = fake_http.calls[0]
    assert call["method"] == "POST"
    assert call["url"].endswith("/accounts/acct-1/allocations")
    assert call["json"] == {"limit": 1_000_000_000}


def test_session_limits_use_documented_path_and_fields(reseller_settings, fake_http):
    fake_http.responses = [_FakeResponse({"id": "acct-1"})]
    client = MassiveResellerClient()

    client.set_session_limits(
        "acct-1",
        session_traffic_limit="100mb",
        session_duration_limit="15m",
    )

    call = fake_http.calls[0]
    assert call["method"] == "PUT"
    assert call["url"].endswith("/accounts/acct-1/session-limit")
    assert call["json"] == {
        "session_traffic_limit": "100mb",
        "session_duration_limit": "15m",
    }


def test_reseller_list_accounts_strips_passwords(reseller_settings, fake_http):
    fake_http.responses = [
        _FakeResponse(
            {
                "accounts": [
                    {
                        "id": "acct-1",
                        "username": "outreach-org-li-profile",
                        "password": "must-not-leak",
                        "used_bytes": 10,
                        "limit": 100,
                        "limit_reached": False,
                        "proxy_access": True,
                        "status": "active",
                    }
                ]
            }
        )
    ]
    accounts = MassiveResellerClient().list_accounts()
    assert accounts[0]["used_bytes"] == 10
    assert "must-not-leak" not in str(accounts)


def test_pool_stats_requests_gzip_and_caches(reseller_settings, fake_http):
    fake_http.responses = [
        _FakeResponse({"data": [{"country": "US", "count": 5000}]}),
    ]
    client = MassivePoolStatsClient()
    assert client.country_counts() == {"US": 5000}
    call = fake_http.calls[0]
    assert call["headers"]["Accept-Encoding"] == "gzip"
    # Cached: no second HTTP call.
    assert client.country_counts() == {"US": 5000}
    assert len(fake_http.calls) == 1


def test_pool_stats_warns_below_threshold(reseller_settings, fake_http):
    fake_http.responses = [_FakeResponse({"data": [{"country": "US", "count": 50}]})]
    client = MassivePoolStatsClient()
    warnings = client.warnings("US")
    assert warnings and "below the recommended" in warnings[0]
    assert client.is_country_safe("US") is False


def test_build_reseller_username_uses_reseller_safe_characters():
    username = provisioning.build_reseller_username("org_1", "profile_1")
    assert username == "outreach.org.1.li.profile.1"
    assert "_" not in username
    assert "-" not in username
    assert all(char.isalnum() or char in ".@" for char in username)


def test_full_massive_username_allows_parent_underscore():
    assert (
        provisioning.full_massive_username("parent_account", "outreach.org.li.p1")
        == "parent_account_outreach.org.li.p1"
    )


def test_reseller_proxy_username_contains_region_and_session():
    username = provisioning.build_reseller_proxy_username(
        "parent", "outreach.org.li.p1", "US", "NY", "New York", session_id="p1"
    )
    assert username.startswith("parent_outreach.org.li.p1-country-US-subdivision-NY")
    assert "-city-New%20York" in username
    assert "-session-p1" in username
    assert "-sessionttl-1440" in username
    assert "-sessionmode-flex" in username


class _FakeResellerClient:
    instances: list["_FakeResellerClient"] = []

    def __init__(self, config=None):
        self.created: list[dict] = []
        self.disabled: list[str] = []
        self.enabled: list[str] = []
        self.rotated: list[dict] = []
        _FakeResellerClient.instances.append(self)

    def create_account(self, username, password, limit_bytes, sync_with_parent=True):
        self.created.append(
            {
                "username": username,
                "password": password,
                "limit_bytes": limit_bytes,
            }
        )
        return {
            "account_id": "acct-1",
            "username": username,
            "limit_bytes": limit_bytes,
            "used_bytes": 0,
            "limit_reached": False,
            "proxy_access": True,
            "status": "active",
        }

    def find_account_by_username(self, username, include_password=False):
        return None

    def disable_account(self, account_id):
        self.disabled.append(account_id)
        return {"account_id": account_id, "status": "disabled"}

    def enable_account(self, account_id):
        self.enabled.append(account_id)
        return {"account_id": account_id, "status": "active"}

    def update_account(self, account_id, **fields):
        self.rotated.append({"account_id": account_id, **fields})
        return {"account_id": account_id}

    def list_accounts(self):
        return []

    def parent_usage(self):
        return {"accounts": 0}


@pytest.fixture
def fake_reseller(monkeypatch):
    from openoutreach.proxies import massive_reseller

    _FakeResellerClient.instances = []
    massive_reseller._POOL_STATS_CACHE.clear()
    monkeypatch.setattr(provisioning, "MassiveResellerClient", _FakeResellerClient)
    monkeypatch.setattr(provisioning, "validate_proxy_host", lambda host: None)
    monkeypatch.setattr(
        "openoutreach.proxies.service.validate_proxy_host", lambda host: None
    )
    return _FakeResellerClient


def _add_cloud_profile(fake: FakeMongo, profile_id="p1", user_id="u1", org_id="org1"):
    fake.collection("linkedin_profiles").insert_one(
        {
            "_id": profile_id,
            "user_id": user_id,
            "org_id": org_id,
            "execution_mode": "cloud",
            "proxy_region_country": "US",
        }
    )


def test_provision_reseller_proxy_encrypts_and_assigns(
    fake, reseller_settings, fake_reseller
):
    _add_cloud_profile(fake)
    proxy = provisioning.provision_reseller_proxy(
        "p1", "u1", "org1", "US", created_by="admin"
    )
    created = fake_reseller.instances[0].created[0]
    plaintext = created["password"]
    stored = fake.collection("proxies").find_one({"_id": proxy._id})
    profile = fake.collection("linkedin_profiles").find_one({"_id": "p1"})

    assert stored["massive_account_id"] == "acct-1"
    assert stored["massive_subuser"] == "outreach.org1.li.p1"
    assert stored["username"].startswith("parent_outreach.org1.li.p1-country-US")
    assert "-session-p1" in stored["username"]
    assert stored["massive_status"] == "active"
    assert stored["password_encrypted"] and plaintext not in stored["password_encrypted"]
    assert profile["proxy_id"] == proxy._id
    assert profile["proxy_mode"] == "managed"
    assert "password" not in stored


def test_provision_reseller_is_idempotent_for_an_assigned_profile(
    fake, reseller_settings, fake_reseller
):
    _add_cloud_profile(fake)
    first = provisioning.provision_reseller_proxy("p1", "u1", "org1", "US")
    second = provisioning.provision_reseller_proxy("p1", "u1", "org1", "US")
    assert second._id == first._id
    assert fake.collection("proxies").count_documents({}) == 1
    assert len(fake_reseller.instances[0].created) == 1


def test_provision_reseller_409_adopts_existing_account(
    fake, reseller_settings, fake_reseller, monkeypatch
):
    _add_cloud_profile(fake)

    def raise_exists(self, username, password, limit_bytes, sync_with_parent=True):
        raise MassiveResellerError("exists", status_code=409, code="already_exists")

    def find_existing(self, username, include_password=False):
        return {
            "account_id": "acct-existing",
            "username": username,
            "password": "existing-secret" if include_password else None,
            "limit_bytes": 10,
            "status": "active",
        }

    monkeypatch.setattr(_FakeResellerClient, "create_account", raise_exists)
    monkeypatch.setattr(_FakeResellerClient, "find_account_by_username", find_existing)

    proxy = provisioning.provision_reseller_proxy("p1", "u1", "org1", "US")
    stored = fake.collection("proxies").find_one({"_id": proxy._id})
    assert stored["massive_account_id"] == "acct-existing"
    assert "existing-secret" not in str(stored)


def test_disable_and_retire_keep_the_same_profile_link(
    fake, reseller_settings, fake_reseller
):
    _add_cloud_profile(fake)
    proxy = provisioning.provision_reseller_proxy("p1", "u1", "org1", "US")

    assert provisioning.disable_massive_for_profile("p1", reason="seat_cancelled")
    stored = fake.collection("proxies").find_one({"_id": proxy._id})
    assert stored["massive_status"] == "disabled"
    assert stored["linkedin_profile_id"] == "p1"

    assert provisioning.retire_massive_for_profile("p1")
    stored = fake.collection("proxies").find_one({"_id": proxy._id})
    assert stored["massive_status"] == "retired"
    assert stored["linkedin_profile_id"] == "p1"


def test_sync_massive_accounts_updates_usage_and_snapshots(
    fake, reseller_settings, fake_reseller, monkeypatch
):
    _add_cloud_profile(fake)
    proxy = provisioning.provision_reseller_proxy("p1", "u1", "org1", "US")
    monkeypatch.setattr(
        _FakeResellerClient,
        "list_accounts",
        lambda self: [
            {
                "account_id": "acct-1",
                "username": "outreach-org1-li-p1",
                "used_bytes": 1234,
                "limit_bytes": 5_000_000_000,
                "limit_reached": True,
                "proxy_access": False,
                "status": "active",
            }
        ],
    )
    monkeypatch.setattr(
        _FakeResellerClient,
        "parent_usage",
        lambda self: {"accounts": 1, "used_bytes": 1234},
    )

    result = provisioning.sync_massive_accounts(actor_user_id="admin")
    stored = fake.collection("proxies").find_one({"_id": proxy._id})
    assert result["matched"] == 1
    assert stored["massive_used_bytes"] == 1234
    assert stored["massive_limit_reached"] is True
    assert stored["massive_proxy_access"] is False
    snapshots = list(fake.collection("massive_usage_snapshots").find({}))
    assert len(snapshots) == 1
    assert "password" not in str(snapshots[0])


def test_budget_hard_limit_disables_and_new_month_reenables(
    fake, reseller_settings, fake_reseller
):
    _add_cloud_profile(fake)
    proxy = provisioning.provision_reseller_proxy("p1", "u1", "org1", "US")
    # Over the hard monthly threshold.
    fake.collection("proxy_usage_snapshots").insert_one(
        {
            "proxy_id": proxy._id,
            "bytes": 41_000_000_000,
            "period_start": datetime.now(timezone.utc).date().isoformat(),
        }
    )
    result = provisioning.enforce_massive_budgets()
    stored = fake.collection("proxies").find_one({"_id": proxy._id})
    assert result["disabled"] == 1
    assert stored["massive_status"] == "budget_disabled"
    assert stored["massive_budget_disabled_at"] is not None

    # Simulate last month's budget disable and a new month with low usage.
    fake.collection("proxies").update_one(
        {"_id": proxy._id},
        {
            "$set": {
                "massive_status": "budget_disabled",
                "massive_budget_disabled_at": datetime.now(timezone.utc)
                - timedelta(days=40),
            }
        },
    )
    fake.collection("proxy_usage_snapshots").delete_many({"proxy_id": proxy._id})
    fake.collection("proxy_usage_snapshots").insert_one(
        {
            "proxy_id": proxy._id,
            "bytes": 1_000_000,
            "period_start": datetime.now(timezone.utc).date().isoformat(),
        }
    )
    result = provisioning.enforce_massive_budgets()
    stored = fake.collection("proxies").find_one({"_id": proxy._id})
    assert result["re_enabled"] == 1
    assert stored["massive_status"] == "active"


def test_rotate_massive_password_updates_proxy_and_profile(
    fake, reseller_settings, fake_reseller
):
    _add_cloud_profile(fake)
    proxy = provisioning.provision_reseller_proxy("p1", "u1", "org1", "US")
    old_encrypted = fake.collection("proxies").find_one({"_id": proxy._id})[
        "password_encrypted"
    ]
    rotated = provisioning.rotate_massive_password(proxy, actor_user_id="admin")
    stored = fake.collection("proxies").find_one({"_id": rotated._id})
    profile = fake.collection("linkedin_profiles").find_one({"_id": "p1"})
    assert stored["password_encrypted"] != old_encrypted
    assert profile["proxy_password_encrypted"] == stored["password_encrypted"]
    assert fake_reseller.instances[-1].rotated[0]["account_id"] == "acct-1"
    assert "password" not in stored
    assert "password" not in rotated.public_dict()


def test_list_massive_subaccounts_never_returns_secrets(
    fake, reseller_settings, fake_reseller
):
    _add_cloud_profile(fake)
    provisioning.provision_reseller_proxy("p1", "u1", "org1", "US")
    rows = provisioning.list_massive_subaccounts()
    assert len(rows) == 1
    assert rows[0]["profile_id"] == "p1"
    assert "password" not in str(rows)


def test_sync_does_not_reactivate_a_seat_disabled_subaccount(
    fake, reseller_settings, fake_reseller, monkeypatch
):
    _add_cloud_profile(fake)
    proxy = provisioning.provision_reseller_proxy("p1", "u1", "org1", "US")
    provisioning.disable_massive_for_profile("p1", reason="seat_cancelled")
    monkeypatch.setattr(
        _FakeResellerClient,
        "list_accounts",
        lambda self: [
            {
                "account_id": "acct-1",
                "username": "outreach-org1-li-p1",
                "used_bytes": 10,
                "limit_bytes": 100,
                "status": "active",
            }
        ],
    )
    monkeypatch.setattr(_FakeResellerClient, "parent_usage", lambda self: {})
    provisioning.sync_massive_accounts()
    stored = fake.collection("proxies").find_one({"_id": proxy._id})
    assert stored["massive_status"] == "disabled"
    assert stored["massive_used_bytes"] == 10


def test_massive_alerts_include_operational_reasons(
    fake, reseller_settings, fake_reseller
):
    _add_cloud_profile(fake)
    proxy = provisioning.provision_reseller_proxy("p1", "u1", "org1", "US")
    fake.collection("proxies").update_one(
        {"_id": proxy._id},
        {
            "$set": {
                "massive_limit_reached": True,
                "massive_proxy_access": False,
                "last_test_country": "CA",
                "country": "US",
            }
        },
    )
    alerts = provisioning.massive_alerts()
    assert alerts
    assert "limit_reached" in alerts[0]["reasons"]
    assert "proxy_access_revoked" in alerts[0]["reasons"]
    assert "country_mismatch" in alerts[0]["reasons"]
    assert "password" not in str(alerts)


def test_provision_managed_proxy_falls_back_when_reseller_fails(
    monkeypatch, reseller_settings
):
    def fail_reseller(*args, **kwargs):
        raise MassiveResellerError("down", status_code=503)

    fallback = Proxy(
        _id="fallback-proxy",
        host="proxy.example.com",
        port=8080,
        country="US",
    )
    monkeypatch.setattr(provisioning, "provision_reseller_proxy", fail_reseller)
    monkeypatch.setattr(
        provisioning, "assign_proxy_for_new_profile", lambda *args, **kwargs: fallback
    )
    result = provisioning.provision_managed_proxy("p1", "u1", "org1", "US")
    assert result._id == "fallback-proxy"


def test_city_targeting_is_blocked_when_pool_is_too_small(monkeypatch):
    class _Stats:
        def is_city_safe(self, country, city):
            return False

    monkeypatch.setattr(provisioning, "pool_stats_client", lambda: _Stats())
    from openoutreach.proxies.models import ProxyError

    with pytest.raises(ProxyError):
        provisioning.validate_city_pool("US", "New York")
    # Country-level is always allowed.
    provisioning.validate_city_pool("US", None)


def test_generated_password_is_long_enough():
    assert len(generate_subaccount_password()) >= 32
