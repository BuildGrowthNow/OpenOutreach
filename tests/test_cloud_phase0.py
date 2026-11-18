"""Phase 0 cloud seat, webhook, proxy, and launch-guard tests."""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from starlette.requests import Request

from openoutreach.api_v2.routers import admin as admin_router
from openoutreach.api_v2.routers import linkedin_credentials as credentials_router
from openoutreach.api_v2.routers import linkedin_profiles as profiles_router
from openoutreach.api_v2.routers.billing import CheckoutSessionRequest, create_checkout
from openoutreach.api_v2.routers.daemon import bootstrap_daemon, get_profile_details
from openoutreach.api_v2.routers.daemon_v2 import _snapshot
from openoutreach.api_v2.schemas.linkedin import LinkedInCredentialUpdate
from openoutreach.billing import seats as seat_accounting
from openoutreach.billing import stripe_service, webhooks
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
from openoutreach.linkedin.models import LinkedInProfile
from openoutreach.mongodb.models import LinkedInCredentials
from openoutreach.mongodb.models_user import User
from openoutreach.proxies.models import ProxyReuseError, ProxyUnavailableError
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
    assert effective_cloud_seat_limit("pro", 3) == 0


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

    with (
        patch(
            "openoutreach.billing.downgrade_handler.get_mongodb_collection",
            return_value=collection,
        ),
        patch(
            "openoutreach.billing.downgrade_handler.credentialed_profile_ids",
            return_value=None,
        ),
    ):
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
        result = import_proxies("8.8.8.8:8080:user:super-secret:US")

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


def test_cloud_verification_excludes_the_profile_itself():
    user = User(
        _id="u1",
        email="user@example.com",
        plan="cloud",
        cloud_profiles=0,
        subscription_status="active",
    )

    with patch("openoutreach.billing.enforcement.get_mongodb_collection") as get_collection:
        collection = MagicMock()
        collection.count_documents.return_value = 0
        get_collection.return_value = collection

        allowed, error = PlanEnforcer.can_use_cloud_execution(
            user,
            exclude_profile_id="profile-1",
        )

    assert allowed is True
    assert error is None
    query = collection.count_documents.call_args.args[0]
    assert query["_id"] == {"$ne": "profile-1"}


def test_seat_reduction_pauses_cloud_profiles_before_desktop():
    profiles = [
        {"_id": "cloud-old", "execution_mode": "cloud", "linkedin_username": "one"},
        {"_id": "desktop", "execution_mode": "desktop", "linkedin_username": "two"},
        {"_id": "cloud-new", "execution_mode": "cloud", "linkedin_username": "three"},
    ]
    collection = MagicMock()
    collection.find.return_value = profiles
    collection.update_many.return_value.modified_count = 2

    with (
        patch(
            "openoutreach.billing.downgrade_handler.get_mongodb_collection",
            return_value=collection,
        ),
        patch(
            "openoutreach.billing.downgrade_handler.credentialed_profile_ids",
            return_value=None,
        ),
    ):
        result = pause_excess_linkedin_profiles(
            "u1",
            1,
            prefer_execution_mode="cloud",
        )

    assert result == {"deactivated": 2, "error": False}
    paused_ids = collection.update_many.call_args.args[0]["_id"]["$in"]
    assert paused_ids == ["cloud-old", "cloud-new"]


def test_seat_reduction_ignores_orphan_profiles():
    profiles = [
        {"_id": "orphan", "execution_mode": "cloud", "linkedin_username": "orphan"},
        {"_id": "account-1", "execution_mode": "cloud", "linkedin_username": "one"},
        {"_id": "account-2", "execution_mode": "cloud", "linkedin_username": "two"},
    ]
    collection = MagicMock()
    collection.find.return_value = profiles
    collection.update_many.return_value.modified_count = 1

    with (
        patch(
            "openoutreach.billing.downgrade_handler.get_mongodb_collection",
            return_value=collection,
        ),
        patch(
            "openoutreach.billing.downgrade_handler.credentialed_profile_ids",
            return_value={"account-1", "account-2"},
        ),
    ):
        result = pause_excess_linkedin_profiles("u1", 1)

    assert result == {"deactivated": 1, "error": False}
    paused_ids = collection.update_many.call_args.args[0]["_id"]["$in"]
    assert paused_ids == ["account-2"]


def test_webhook_seat_reduction_pauses_when_plan_is_unchanged():
    user = User(
        _id="u1",
        email="user@example.com",
        plan="cloud",
        cloud_profiles=1,
        subscription_status="active",
    )
    subscription = {
        "customer": "cus_1",
        "status": "active",
        "items": {
            "data": [
                _item("cloud_monthly"),
                _item("cloud_addon", quantity=0),
            ]
        },
    }

    with (
        patch.object(webhooks, "_get_user_by_stripe_customer", return_value=user),
        patch.object(webhooks, "_enforce_linkedin_account_limit") as enforce,
        patch.object(User, "save", lambda self: None),
    ):
        webhooks.handle_customer_subscription_updated(
            {"data": {"object": subscription}}
        )

    enforce.assert_called_once()
    assert enforce.call_args.args == ("u1", 1)
    assert enforce.call_args.kwargs["prefer_execution_mode"] == "cloud"


def test_webhook_syncs_addon_item_before_base_plan():
    user = User(_id="u1", email="user@example.com", plan="starter")

    _sync_subscription_items(
        user,
        _subscription([
            _item("cloud_addon", quantity=2),
            _item("cloud_monthly"),
        ]),
    )

    assert user.plan == "cloud"
    assert user.cloud_profiles == 2
    assert user.linkedin_account_limit == 3


def test_proxy_parser_keeps_two_letter_password():
    entries, errors = parse_bulk_proxies(
        "proxy.example.com:8080:user:ab",
        default_country="US",
    )

    assert errors == []
    assert entries[0]["password"] == "ab"
    assert entries[0]["country"] == "US"


def test_proxy_assignment_records_actual_proxy_region():
    class _ProxyCollection:
        def find_one(self, query, projection=None):
            if query == {"_id": "proxy-1"}:
                return {
                    "_id": "proxy-1",
                    "status": "available",
                    "linkedin_profile_id": None,
                    "protocol": "http",
                    "host": "8.8.8.8",
                    "port": 8080,
                    "password_encrypted": "encrypted",
                    "country": "US",
                    "subdivision": "NY",
                    "city": "Buffalo",
                }
            return None

        def find_one_and_update(self, query, update, return_document=True):
            return {**self.find_one({"_id": "proxy-1"}), **update["$set"]}

        def update_one(self, query, update):
            return None

    class _Profiles:
        def __init__(self):
            self.profile_update = None

        def find_one(self, query, projection=None):
            return {
                "_id": "profile-1",
                "user_id": "user-1",
                "proxy_id": None,
                "proxy_server": None,
            }

        def update_one(self, query, update):
            self.profile_update = update
            return SimpleNamespace(modified_count=1)

    proxies = _ProxyCollection()
    profiles = _Profiles()

    def _collection(name):
        return proxies if name == "proxies" else profiles

    with patch(
        "openoutreach.proxies.service.get_mongodb_collection",
        side_effect=_collection,
    ):
        assign_proxy_to_profile("proxy-1", "profile-1", "user-1")

    assert profiles.profile_update is not None
    assert profiles.profile_update["$set"]["proxy_region_country"] == "US"
    assert profiles.profile_update["$set"]["proxy_region_subdivision"] == "NY"
    assert profiles.profile_update["$set"]["proxy_region_city"] == "Buffalo"


def test_proxy_parser_csv_keeps_valid_rows_and_reports_bad_row():
    text = "\n".join([
        "host,port,username,password,country",
        "proxy.example.com,8080,user,secret,US",
        "bad.example.com,not-a-port,user,secret,US",
    ])

    entries, errors = parse_bulk_proxies(text)

    assert len(entries) == 1
    assert entries[0]["host"] == "proxy.example.com"
    assert errors == [{"line": 3, "error": "Port must be a number"}]
    assert "secret" not in str(errors)


def test_proxy_assignment_releases_claim_when_profile_races():
    class _ProxyCollection:
        def __init__(self):
            self.release_update = None

        def find_one(self, query, projection=None):
            if query == {"_id": "proxy-1"}:
                return {
                    "_id": "proxy-1",
                    "status": "available",
                    "linkedin_profile_id": None,
                    "protocol": "http",
                    "host": "8.8.8.8",
                    "port": 8080,
                    "password_encrypted": "encrypted",
                    "country": "US",
                }
            return None

        def find_one_and_update(self, query, update, return_document=True):
            return {**self.find_one({"_id": "proxy-1"}), **update["$set"]}

        def update_one(self, query, update):
            self.release_update = (query, update)

    class _Profiles:
        def find_one(self, query, projection=None):
            return {
                "_id": "profile-1",
                "user_id": "user-1",
                "proxy_id": None,
                "proxy_server": None,
            }

        def update_one(self, query, update):
            return SimpleNamespace(modified_count=0)

    proxies = _ProxyCollection()
    profiles = _Profiles()

    def _collection(name):
        return proxies if name == "proxies" else profiles

    with patch(
        "openoutreach.proxies.service.get_mongodb_collection",
        side_effect=_collection,
    ):
        with pytest.raises(ProxyUnavailableError):
            assign_proxy_to_profile("proxy-1", "profile-1", "user-1")

    assert proxies.release_update is not None
    assert proxies.release_update[1]["$set"]["status"] == "available"


def test_profile_delete_retires_proxy():
    profiles_collection = MagicMock()
    profiles_collection.find_one.return_value = {"_id": "profile-1", "user_id": "u1"}
    profiles_collection.delete_one.return_value.deleted_count = 1
    campaigns_collection = MagicMock()
    campaigns_collection.count_documents.return_value = 0
    rate_collection = MagicMock()

    def _collection(name):
        return {
            "linkedin_profiles": profiles_collection,
            "campaigns": campaigns_collection,
            "smart_rate_limit_contexts": rate_collection,
        }.get(name)

    with (
        patch.object(profiles_router, "get_mongodb_collection", side_effect=_collection),
        patch("openoutreach.proxies.service.retire_proxy_for_profile") as retire,
    ):
        asyncio.run(profiles_router.delete_profile("profile-1", user_id="u1"))

    retire.assert_called_once_with("profile-1")


def test_managed_proxy_update_is_read_only():
    collection = MagicMock()
    collection.find_one.return_value = {
        "_id": "profile-1",
        "user_id": "u1",
        "proxy_id": "proxy-1",
        "proxy_mode": "managed",
        "proxy_server": "http://proxy.example.com:8080",
    }

    with patch.object(profiles_router, "get_mongodb_collection", return_value=collection):
        with pytest.raises(HTTPException) as error:
            asyncio.run(
                profiles_router.update_proxy_config(
                    "profile-1",
                    proxy_server="http://other.example.com:8080",
                    proxy_username=None,
                    proxy_password=None,
                    user_id="u1",
                )
            )

    assert error.value.status_code == 403
    collection.update_one.assert_not_called()


def test_managed_proxy_config_masks_username():
    collection = MagicMock()
    collection.find_one.return_value = {
        "_id": "profile-1",
        "user_id": "u1",
        "proxy_id": "proxy-1",
        "proxy_mode": "managed",
        "proxy_server": "http://proxy.example.com:8080",
        "proxy_username": "massive-parent-subaccount",
        "proxy_password_encrypted": "encrypted",
    }

    with patch.object(profiles_router, "get_mongodb_collection", return_value=collection):
        result = asyncio.run(
            profiles_router.get_proxy_config("profile-1", user_id="u1")
        )

    assert result["proxy_username"] == "***"
    assert result["proxy_password"] == "********"
    assert result["proxy_server"] == "http://proxy.example.com:8080"


def test_credential_update_rejects_foreign_profile():
    credential = SimpleNamespace(
        _id="credential-1",
        user_id="u1",
        linkedin_profile_id="profile-1",
    )

    with (
        patch.object(LinkedInCredentials, "get", return_value=credential),
        patch.object(
            LinkedInProfile,
            "get",
            return_value=SimpleNamespace(user_id="u2"),
        ),
    ):
        with pytest.raises(HTTPException) as error:
            asyncio.run(
                credentials_router.update_credential(
                    "credential-1",
                    LinkedInCredentialUpdate(linkedin_profile_id="profile-2"),
                    MagicMock(),
                    "u1",
                )
            )

    assert error.value.status_code == 403


def test_cloud_checkout_never_starts_trial_for_cloud_intent():
    user = User(
        _id="u1",
        email="user@example.com",
        subscription_status="none",
        intended_plan="cloud",
        email_verified=True,
    )

    with (
        patch("openoutreach.api_v2.routers.billing.User.get", return_value=user),
        patch("openoutreach.api_v2.routers.billing.create_or_get_customer") as customer,
        patch("openoutreach.api_v2.routers.billing.StripePlan.get_by_plan") as stripe_plan,
        patch("openoutreach.api_v2.routers.billing.get_site_config") as site_config,
        patch("openoutreach.api_v2.routers.billing.create_checkout_session") as checkout,
        patch.object(User, "save", lambda self: None),
    ):
        customer.return_value = SimpleNamespace(id="cus_1")
        stripe_plan.return_value = SimpleNamespace(
            monthly_price_id="price_1",
            annual_price_id=None,
        )
        site_config.return_value = SimpleNamespace(
            trial_duration_days=7,
            referral_trial_extension_days=3,
        )
        checkout.return_value = "https://checkout.example.com"

        asyncio.run(
            create_checkout(
                CheckoutSessionRequest(plan_name="starter", billing_period="monthly"),
                user_id="u1",
            )
        )

    assert checkout.call_args.kwargs["trial_period_days"] is None


def test_stripe_plan_change_keeps_cloud_addon_item():
    addon_item = SimpleNamespace(
        id="addon-item",
        price=SimpleNamespace(metadata={"price_key": "cloud_addon"}),
    )
    base_item = SimpleNamespace(
        id="base-item",
        price=SimpleNamespace(metadata={"price_key": "cloud_monthly"}),
    )
    subscription = SimpleNamespace(
        items=SimpleNamespace(data=[addon_item, base_item]),
    )

    with (
        patch.object(stripe_service.stripe.Subscription, "retrieve", return_value=subscription),
        patch.object(stripe_service.stripe.Subscription, "modify") as modify,
    ):
        modify.return_value = SimpleNamespace(id="sub_1")
        stripe_service.update_subscription_price("sub_1", "price_new")

    items = modify.call_args.kwargs["items"]
    assert items[0]["id"] == "base-item"


def test_admin_plan_change_applies_cloud_seat_limit():
    user = User(
        _id="u1",
        email="user@example.com",
        plan="pro",
        cloud_profiles=2,
        linkedin_account_limit=1,
    )

    with (
        patch.object(admin_router.User, "get", return_value=user),
        patch.object(User, "save", lambda self: None),
    ):
        asyncio.run(
            admin_router.update_user(
                "u1",
                admin_router.UserUpdateRequest(plan="cloud"),
                current_admin="admin-1",
            )
        )

    assert user.plan == "cloud"
    assert user.linkedin_account_limit == 3


class _SeatCollection:
    def __init__(self):
        self.document = None

    def _matches(self, query):
        if self.document is None:
            return False
        for key, condition in query.items():
            if key == "_id":
                continue
            value = self.document.get(key)
            if isinstance(condition, dict):
                if "$lt" in condition and not value < condition["$lt"]:
                    return False
                if "$gt" in condition and not value > condition["$gt"]:
                    return False
            elif value != condition:
                return False
        return True

    def update_one(self, query, update, upsert=False):
        if self.document is None and upsert:
            self.document = {
                "_id": query["_id"],
                "count": update.get("$setOnInsert", {}).get("count", 0),
            }
            return
        if not self._matches(query):
            return
        if "count" in update.get("$set", {}):
            self.document["count"] = update["$set"]["count"]
        if "count" in update.get("$inc", {}):
            self.document["count"] += update["$inc"]["count"]

    def find_one_and_update(self, query, update, return_document=True):
        if not self._matches(query):
            return None
        self.document["count"] += update.get("$inc", {}).get("count", 0)
        return dict(self.document)


def test_seat_reservation_is_atomic_at_the_limit():
    collection = _SeatCollection()

    with (
        patch.object(
            seat_accounting,
            "get_mongodb_collection",
            return_value=collection,
        ),
        patch.object(seat_accounting, "count_credentialed_profiles", return_value=0),
    ):
        first, first_error = seat_accounting.reserve_linkedin_seat("u1", 1)
        second, second_error = seat_accounting.reserve_linkedin_seat("u1", 1)

    assert first is True
    assert first_error is None
    assert second is False
    assert second_error is not None
    assert collection.document["count"] == 1


def test_seat_release_returns_a_slot():
    collection = _SeatCollection()

    with (
        patch.object(
            seat_accounting,
            "get_mongodb_collection",
            return_value=collection,
        ),
        patch.object(seat_accounting, "count_credentialed_profiles", return_value=0),
    ):
        assert seat_accounting.reserve_linkedin_seat("u1", 1)[0] is True
        seat_accounting.release_linkedin_seat("u1")

    assert collection.document["count"] == 0


def test_credentialed_profile_count_includes_paused_profiles():
    profiles = MagicMock()
    profiles.find.return_value = [{"_id": "p1"}, {"_id": "p2"}]
    credentials = MagicMock()
    credentials.find.return_value = [
        {"linkedin_profile_id": "p1"},
        {"linkedin_profile_id": "p1"},
        {"linkedin_profile_id": "p2"},
    ]

    def _collection(name):
        return profiles if name == "linkedin_profiles" else credentials

    with patch.object(
        seat_accounting,
        "get_mongodb_collection",
        side_effect=_collection,
    ):
        count = seat_accounting.count_credentialed_profiles("u1")

    assert count == 2
    profiles.find.assert_called_once_with({"user_id": "u1"}, {"_id": 1})


def test_profile_delete_releases_seat_when_credentials_exist():
    profiles_collection = MagicMock()
    profiles_collection.find_one.return_value = {"_id": "profile-1", "user_id": "u1"}
    profiles_collection.delete_one.return_value.deleted_count = 1
    campaigns_collection = MagicMock()
    campaigns_collection.count_documents.return_value = 0
    credentials_collection = MagicMock()
    credentials_collection.count_documents.return_value = 1
    rate_collection = MagicMock()

    def _collection(name):
        return {
            "linkedin_profiles": profiles_collection,
            "linkedin_credentials": credentials_collection,
            "campaigns": campaigns_collection,
            "smart_rate_limit_contexts": rate_collection,
        }.get(name)

    with (
        patch.object(profiles_router, "get_mongodb_collection", side_effect=_collection),
        patch.object(profiles_router, "release_linkedin_seat") as release,
        patch("openoutreach.proxies.service.retire_proxy_for_profile"),
    ):
        asyncio.run(profiles_router.delete_profile("profile-1", user_id="u1"))

    release.assert_called_once_with("u1")


def test_v2_snapshot_never_contains_proxy_fields():
    snapshot = _snapshot({
        "user_id": "u1",
        "linkedin_profile_id": "profile-1",
        "channel": "linkedin",
        "payload": {
            "message": "hello",
            "proxy_server": "http://proxy.example.com:8080",
            "proxy_username": "massive-parent",
            "proxy_password": "super-secret",
            "proxy_password_encrypted": "encrypted",
        },
    })

    assert snapshot["message"] == "hello"
    assert not any(key.startswith("proxy_") for key in snapshot)
