"""Phase 1 managed-proxy operations tests."""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException

from openoutreach.api_v2.routers import admin_proxies as admin_proxies_router
from openoutreach.proxies import service as proxy_service
from openoutreach.proxies.massive_client import (
    build_massive_subuser,
    build_massive_username,
    massive_status,
)
from openoutreach.proxies.models import (
    Proxy,
    ProxyError,
    ProxyReuseError,
)
from openoutreach.proxies.parser import parse_bulk_proxies
from openoutreach.proxies.rate_limit import AdminActionRateLimiter


@pytest.fixture(autouse=True)
def encryption_key(monkeypatch):
    monkeypatch.setenv("COOKIE_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.delenv("SECRET_KEY", raising=False)


class _Cursor:
    def __init__(self, docs):
        self.docs = list(docs)

    def sort(self, *args, **kwargs):
        return self

    def skip(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def __iter__(self):
        return iter(self.docs)


class _ListCollection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])
        self.query = None

    def find(self, query=None, projection=None):
        self.query = query
        return _Cursor(self.docs)

    def count_documents(self, query):
        self.query = query
        return len(self.docs)

    def find_one(self, query, projection=None):
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in query.items() if key != "_id"):
                return doc
        return None

    def update_one(self, query, update, upsert=False):
        return SimpleNamespace(modified_count=1)

    def insert_one(self, doc):
        self.docs.append(doc)
        return SimpleNamespace(inserted_id="1")

    def update_many(self, query, update):
        return SimpleNamespace(modified_count=1)


def test_proxy_list_filters_are_combined():
    collection = _ListCollection()

    with patch.object(proxy_service, "get_mongodb_collection", return_value=collection):
        proxies, total = proxy_service.list_proxies(
            status="assigned",
            country="us",
            provider="manual",
            assignment="assigned",
            identity_id="identity-1",
            org_id="org-1",
            search="8.8.8.8",
        )

    assert proxies == []
    assert total == 0
    assert collection.query is not None
    conditions = collection.query["$and"]
    assert {"status": "assigned"} in conditions
    assert {"country": "US"} in conditions
    assert {"provider": "manual"} in conditions
    assert {"identity_id": "identity-1"} in conditions
    assert any("assigned_org_id" in item.get("$or", [{}])[0] for item in conditions)


def test_csv_export_masks_credentials_and_has_no_password_column():
    proxy = Proxy(
        _id="proxy-1",
        host="8.8.8.8",
        port=8080,
        username="massive-parent-subaccount",
        password_encrypted="encrypted-secret",
        country="US",
        status="available",
    )

    with patch.object(
        proxy_service,
        "list_proxies",
        return_value=([proxy], 1),
    ):
        csv_text = proxy_service.export_proxies_csv()

    assert "encrypted-secret" not in csv_text
    assert "massive-parent-subaccount" not in csv_text
    assert "password" not in csv_text.lower()
    assert "***" in csv_text


def test_import_preview_never_contains_passwords_or_raw_usernames():
    collection = _ListCollection()

    with patch.object(proxy_service, "get_mongodb_collection", return_value=collection):
        preview = proxy_service.preview_proxies(
            "8.8.8.8:8080:super-user:super-secret:US"
        )

    assert preview["valid"] == 1
    assert preview["preview"][0]["username_masked"] == "***"
    assert preview["preview"][0]["has_password"] is True
    assert "super-secret" not in str(preview)
    assert "super-user" not in str(preview)


def test_import_preview_uses_modal_defaults_for_plain_lines():
    collection = _ListCollection()

    with patch.object(proxy_service, "get_mongodb_collection", return_value=collection):
        preview = proxy_service.preview_proxies(
            "8.8.8.8:8080:user:secret:US",
            provider="massive_residential",
            kind="isp",
        )

    assert preview["preview"][0]["provider"] == "massive_residential"
    assert preview["preview"][0]["kind"] == "isp"


def test_import_reports_per_line_duplicate_without_secrets():
    collection = _ListCollection()

    with patch.object(proxy_service, "get_mongodb_collection", return_value=collection), patch(
        "openoutreach.proxies.models.get_mongodb_collection",
        return_value=collection,
    ):
        result = proxy_service.import_proxies(
            "8.8.8.8:8080:user:secret:US\n8.8.8.8:8080:user:secret:US"
        )

    assert result["created"] == 1
    assert result["failed"] == 1
    assert result["errors"] == [{"line": 2, "error": "Duplicate proxy"}]
    assert "secret" not in str(result["errors"])


def test_csv_import_supports_label_type_and_provider():
    text = (
        "label,host,port,username,password,country,subdivision,city,type,provider\n"
        "Office,8.8.8.8,8080,user,secret,US,NY,New York,isp,manual"
    )

    entries, errors = parse_bulk_proxies(text)

    assert errors == []
    assert entries[0]["label"] == "Office"
    assert entries[0]["kind"] == "isp"
    assert entries[0]["provider"] == "manual"
    assert entries[0]["city"] == "New York"


class _AssignmentProxyCollection:
    def __init__(self, doc):
        self.doc = doc
        self.claim_query = None
        self.release_update = None

    def find_one(self, query, projection=None):
        if query.get("_id") == self.doc["_id"]:
            return dict(self.doc)
        return None

    def find_one_and_update(self, query, update, return_document=True):
        self.claim_query = query
        if not self._matches(query):
            return None
        self.doc.update(update["$set"])
        return dict(self.doc)

    def _matches(self, query):
        if query.get("_id") != self.doc["_id"]:
            return False

        def _clause_matches(clause):
            for key, expected in clause.items():
                if key == "_id":
                    continue
                actual = self.doc.get(key)
                if isinstance(expected, dict):
                    if "$in" in expected and actual not in expected["$in"]:
                        return False
                    if "$ne" in expected and actual == expected["$ne"]:
                        return False
                elif actual != expected:
                    return False
            return True

        return any(_clause_matches(clause) for clause in query.get("$or", []))

    def update_one(self, query, update):
        self.release_update = (query, update)
        return SimpleNamespace(modified_count=1)


class _AssignmentProfileCollection:
    def __init__(self, doc):
        self.doc = doc
        self.update = None

    def find_one(self, query, projection=None):
        if query.get("_id") == self.doc["_id"]:
            return dict(self.doc)
        return None

    def update_one(self, query, update):
        self.update = update
        return SimpleNamespace(modified_count=1)


def _assign_fixture(proxy_doc, profile_doc):
    proxies = _AssignmentProxyCollection(proxy_doc)
    profiles = _AssignmentProfileCollection(profile_doc)

    def _collection(name):
        if name == "proxies":
            return proxies
        if name == "linkedin_profiles":
            return profiles
        return None

    return proxies, profiles, _collection


def test_used_proxy_cannot_be_assigned_to_a_different_profile():
    proxies, profiles, collection = _assign_fixture(
        {
            "_id": "proxy-1",
            "status": "disabled",
            "linkedin_profile_id": None,
            "last_assigned_profile_id": "profile-1",
            "last_assigned_user_id": "user-1",
            "ever_assigned": True,
            "host": "8.8.8.8",
            "port": 8080,
            "protocol": "http",
            "country": "US",
            "password_encrypted": "encrypted",
        },
        {
            "_id": "profile-2",
            "user_id": "user-1",
            "proxy_id": None,
            "proxy_server": None,
        },
    )

    with patch.object(proxy_service, "get_mongodb_collection", side_effect=collection):
        with pytest.raises(ProxyReuseError):
            proxy_service.assign_proxy_to_profile("proxy-1", "profile-2", "user-1")

    assert proxies.claim_query is None
    assert profiles.update is None


def test_used_proxy_can_return_only_to_the_same_profile():
    proxy_doc = {
        "_id": "proxy-1",
        "status": "disabled",
        "linkedin_profile_id": None,
        "last_assigned_profile_id": "profile-1",
        "last_assigned_user_id": "user-1",
        "ever_assigned": True,
        "host": "8.8.8.8",
        "port": 8080,
        "protocol": "http",
        "country": "US",
        "password_encrypted": "encrypted",
    }
    profile_doc = {
        "_id": "profile-1",
        "user_id": "user-1",
        "proxy_id": None,
        "proxy_server": None,
        "identity_id": "user-1",
    }
    proxies, profiles, collection = _assign_fixture(proxy_doc, profile_doc)

    with patch.object(proxy_service, "get_mongodb_collection", side_effect=collection):
        assigned = proxy_service.assign_proxy_to_profile(
            "proxy-1",
            "profile-1",
            "user-1",
        )

    assert assigned.status == "assigned"
    assert assigned.last_assigned_profile_id == "profile-1"
    assert profiles.update is not None
    assert profiles.update["$set"]["proxy_id"] == "proxy-1"


def test_cross_tenant_assignment_is_rejected():
    proxies, profiles, collection = _assign_fixture(
        {
            "_id": "proxy-1",
            "status": "available",
            "linkedin_profile_id": None,
            "ever_assigned": False,
            "host": "8.8.8.8",
            "port": 8080,
            "protocol": "http",
            "country": "US",
            "password_encrypted": "encrypted",
        },
        {
            "_id": "profile-1",
            "user_id": "user-2",
            "proxy_id": None,
            "proxy_server": None,
        },
    )

    with patch.object(proxy_service, "get_mongodb_collection", side_effect=collection):
        with pytest.raises(ProxyError):
            proxy_service.assign_proxy_to_profile("proxy-1", "profile-1", "user-1")

    assert proxies.claim_query is None
    assert profiles.update is None


def test_cross_identity_assignment_is_rejected():
    proxies, profiles, collection = _assign_fixture(
        {
            "_id": "proxy-1",
            "status": "available",
            "linkedin_profile_id": None,
            "ever_assigned": False,
            "identity_id": "identity-a",
            "host": "8.8.8.8",
            "port": 8080,
            "protocol": "http",
            "country": "US",
            "password_encrypted": "encrypted",
        },
        {
            "_id": "profile-1",
            "user_id": "user-1",
            "identity_id": "identity-b",
            "proxy_id": None,
            "proxy_server": None,
        },
    )

    with patch.object(proxy_service, "get_mongodb_collection", side_effect=collection):
        with pytest.raises(ProxyError):
            proxy_service.assign_proxy_to_profile("proxy-1", "profile-1", "user-1")

    assert proxies.claim_query is None
    assert profiles.update is None


def test_auto_assignment_excludes_used_proxies():
    collection = MagicMock()
    collection.find_one.return_value = None

    with patch.object(proxy_service, "get_mongodb_collection", return_value=collection):
        assert proxy_service.find_available_proxy("US") is None

    query = collection.find_one.call_args.args[0]
    assert query["ever_assigned"] == {"$ne": True}
    assert query["linkedin_profile_id"] is None


class _UnassignCollection:
    def __init__(self):
        self.doc = {
            "_id": "proxy-1",
            "status": "assigned",
            "linkedin_profile_id": "profile-1",
            "assigned_user_id": "user-1",
            "assigned_org_id": "org-1",
            "last_assigned_profile_id": "profile-1",
            "host": "8.8.8.8",
            "port": 8080,
        }
        self.profile_update = None

    def find_one(self, query, projection=None):
        if query.get("_id") == "proxy-1":
            return dict(self.doc)
        return None

    def find_one_and_update(self, query, update, return_document=True):
        self.doc.update(update["$set"])
        return dict(self.doc)

    def update_one(self, query, update):
        return SimpleNamespace(modified_count=1)


def test_unassign_pauses_profile_and_keeps_proxy_reserved():
    proxies = _UnassignCollection()
    profiles = MagicMock()
    profiles.update_one.return_value = SimpleNamespace(modified_count=1)

    def _collection(name):
        if name == "proxies":
            return proxies
        if name == "linkedin_profiles":
            return profiles
        return None

    with patch.object(proxy_service, "get_mongodb_collection", side_effect=_collection):
        result = proxy_service.unassign_proxy(
            "proxy-1",
            reason="admin_request",
            actor="admin-1",
        )

    assert result.status == "disabled"
    assert result.linkedin_profile_id is None
    assert result.last_assigned_profile_id == "profile-1"
    assert result.ever_assigned is True
    update = profiles.update_one.call_args.args[1]["$set"]
    assert update["proxy_id"] is None
    assert update["proxy_server"] is None
    assert update["active"] is False
    assert update["is_active"] is False
    assert update["daemon_status"] == "proxy_unassigned"


def test_retire_requires_unassigned_proxy():
    collection = MagicMock()
    collection.find_one.return_value = {
        "_id": "proxy-1",
        "status": "assigned",
        "linkedin_profile_id": "profile-1",
    }

    with patch.object(proxy_service, "get_mongodb_collection", return_value=collection):
        with pytest.raises(ProxyError):
            proxy_service.retire_proxy("proxy-1")

    collection.update_one.assert_not_called()


def test_rotate_encrypts_password_and_never_returns_it():
    class _RotateCollection:
        def __init__(self):
            self.doc = {
                "_id": "proxy-1",
                "status": "available",
                "provider": "manual",
                "host": "8.8.8.8",
                "port": 8080,
                "username": "user",
                "password_encrypted": "old",
            }

        def find_one(self, query, projection=None):
            return dict(self.doc)

        def update_one(self, query, update):
            self.doc.update(update["$set"])
            return SimpleNamespace(modified_count=1)

    collection = _RotateCollection()

    with (
        patch.object(proxy_service, "get_mongodb_collection", return_value=collection),
        patch(
            "openoutreach.proxies.models.get_mongodb_collection",
            return_value=collection,
        ),
    ):
        proxy = proxy_service.rotate_proxy_password("proxy-1", "new-super-secret")

    assert collection.doc["password_encrypted"] != "new-super-secret"
    assert "new-super-secret" not in str(proxy.public_dict())
    assert proxy.public_dict()["has_password"] is True


def test_rotate_updates_the_assigned_profile_encrypted_password():
    class _RotateProxyCollection:
        def __init__(self):
            self.doc = {
                "_id": "proxy-1",
                "status": "assigned",
                "provider": "manual",
                "host": "8.8.8.8",
                "port": 8080,
                "username": "user",
                "password_encrypted": "old",
                "linkedin_profile_id": "profile-1",
            }

        def find_one(self, query, projection=None):
            return dict(self.doc)

        def update_one(self, query, update):
            self.doc.update(update["$set"])
            return SimpleNamespace(modified_count=1)

    class _Profiles:
        def __init__(self):
            self.update = None

        def update_one(self, query, update):
            self.update = (query, update)
            return SimpleNamespace(modified_count=1)

    proxies = _RotateProxyCollection()
    profiles = _Profiles()

    def _collection(name):
        return proxies if name == "proxies" else profiles

    with (
        patch.object(proxy_service, "get_mongodb_collection", side_effect=_collection),
        patch(
            "openoutreach.proxies.models.get_mongodb_collection",
            return_value=proxies,
        ),
    ):
        proxy_service.rotate_proxy_password("proxy-1", "new-super-secret")

    assert profiles.update is not None
    assert profiles.update[0] == {"_id": "profile-1", "proxy_id": "proxy-1"}
    stored = profiles.update[1]["$set"]["proxy_password_encrypted"]
    assert stored != "new-super-secret"
    assert stored == proxies.doc["password_encrypted"]


def test_health_check_records_country_mismatch_and_error_type():
    collection = MagicMock()

    proxy = Proxy(
        _id="proxy-1",
        host="8.8.8.8",
        port=8080,
        country="US",
    )

    with patch.object(proxy_service, "get_mongodb_collection", return_value=collection):
        proxy_service.record_health_check(
            proxy,
            {
                "success": False,
                "country": "DE",
                "latency_ms": 120,
                "error": "The proxy rejected the username or password (HTTP 407)",
            },
        )

    doc = collection.insert_one.call_args.args[0]
    assert doc["country_match"] is False
    assert doc["expected_country"] == "US"
    assert doc["egress_country"] == "DE"
    assert doc["error_type"] == "proxy_auth"
    assert "password_encrypted" not in doc
    assert "secret" not in str(doc).lower()


def test_health_error_types_are_classified():
    assert proxy_service._error_type({"success": True}) is None
    assert proxy_service._error_type({"success": False, "error": "HTTP 407"}) == "proxy_auth"
    assert proxy_service._error_type({"success": False, "error": "Request timed out"}) == "timeout"
    assert proxy_service._error_type({"success": False, "error_type": "connection"}) == "connection"


def test_massive_username_contains_region_and_session_parameters():
    username = build_massive_username(
        "parent_user",
        "profile-1",
        "us",
        "ny",
        "New York",
    )

    assert username.startswith("parent_user-subaccount-profile-1-country-US")
    assert "-subdivision-NY" in username
    assert "-city-New%20York" in username
    assert "-session-profile-1" in username
    assert "-sessionttl-1440" in username
    assert "-sessionmode-flex" in username
    assert build_massive_subuser("profile-1") == "subaccount-profile-1"


def test_massive_usage_parser_handles_decimal_units():
    from openoutreach.proxies.massive_client import _usage_bytes

    assert _usage_bytes({"bytes": 123}) == 123
    assert _usage_bytes({"usage": 1.5, "unit": "GB"}) == 1_500_000_000
    assert _usage_bytes({"usage": 42, "unit": "bytes"}) == 42
    assert _usage_bytes({"usage": 42}) is None


def test_massive_status_never_returns_secrets(monkeypatch):
    from openoutreach.config import settings

    monkeypatch.setattr(settings, "MASSIVE_PARENT_USERNAME", "parent-secret")
    monkeypatch.setattr(settings, "MASSIVE_PROXY_PASSWORD", "proxy-secret")
    monkeypatch.setattr(settings, "MASSIVE_REPORTING_API_KEY", "reporting-secret")
    monkeypatch.setattr(settings, "MASSIVE_REPORTING_ENABLED", True)

    status = massive_status()

    assert status["configured"] is True
    assert status["reporting_configured"] is True
    assert "parent-secret" not in str(status)
    assert "proxy-secret" not in str(status)
    assert "reporting-secret" not in str(status)


def test_admin_rate_limiter_blocks_after_limit(monkeypatch):
    from openoutreach.config import settings

    collection = MagicMock()
    collection.count_documents.return_value = 2
    monkeypatch.setattr(settings, "PROXY_IMPORT_RATE_LIMIT", 2)

    with patch(
        "openoutreach.proxies.rate_limit.get_mongodb_collection",
        return_value=collection,
    ):
        allowed, message = AdminActionRateLimiter.check("admin-1", "proxy_import")

    assert allowed is False
    assert "Rate limit" in str(message)


def test_usage_summary_groups_per_proxy_profile_and_workspace():
    usage = _ListCollection([
        {
            "proxy_id": "proxy-1",
            "profile_id": "profile-1",
            "user_id": "user-1",
            "org_id": None,
            "bytes": 100,
            "period_start": "2026-11-17",
            "period_end": "2026-11-18",
        },
        {
            "proxy_id": "proxy-1",
            "profile_id": "profile-1",
            "user_id": "user-1",
            "org_id": None,
            "bytes": 50,
            "period_start": "2026-11-16",
            "period_end": "2026-11-17",
        },
    ])
    proxies = _ListCollection([
        {
            "_id": "proxy-1",
            "label": "P1",
            "status": "assigned",
            "provider": "manual",
        }
    ])
    profiles = _ListCollection([
        {"_id": "profile-1", "linkedin_username": "alice"}
    ])
    users = _ListCollection([
        {"_id": "user-1", "email": "alice@example.com"}
    ])

    def _collection(name):
        return {
            "proxy_usage_snapshots": usage,
            "proxies": proxies,
            "linkedin_profiles": profiles,
            "users": users,
        }.get(name)

    with patch.object(proxy_service, "get_mongodb_collection", side_effect=_collection):
        summary = proxy_service.get_usage_summary()

    assert summary["total_bytes"] == 150
    assert summary["per_proxy"][0]["bytes"] == 150
    assert summary["per_profile"][0]["label"] == "alice"
    assert summary["per_workspace"][0]["label"] == "alice@example.com"
    assert summary["per_channel"][0]["channel"] == "linkedin"
    assert summary["per_channel"][0]["bytes"] == 150


def test_import_endpoint_rate_limit_returns_429():
    body = admin_proxies_router.ProxyImportRequest(
        text="8.8.8.8:8080:user:secret:US"
    )

    with patch.object(
        admin_proxies_router.AdminActionRateLimiter,
        "check",
        return_value=(False, "Rate limit reached"),
    ):
        with pytest.raises(HTTPException) as error:
            asyncio.run(
                admin_proxies_router.import_proxy_inventory(
                    body,
                    current_admin="admin-1",
                )
            )

    assert error.value.status_code == 429


def test_assign_endpoint_rejects_desktop_profiles():
    profiles = MagicMock()
    profiles.find_one.return_value = {
        "_id": "profile-1",
        "user_id": "user-1",
        "execution_mode": "desktop",
    }

    with patch.object(
        admin_proxies_router,
        "get_mongodb_collection",
        return_value=profiles,
    ):
        with pytest.raises(HTTPException) as error:
            asyncio.run(
                admin_proxies_router.assign_proxy_inventory(
                    "proxy-1",
                    admin_proxies_router.ProxyAssignRequest(profile_id="profile-1"),
                    current_admin="admin-1",
                )
            )

    assert error.value.status_code == 400


def test_rotate_endpoint_rejects_short_password_without_echoing_it():
    body = admin_proxies_router.ProxyRotateRequest(password="short")

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            admin_proxies_router.rotate_proxy_credentials(
                "proxy-1",
                body,
                current_admin="admin-1",
            )
        )

    assert error.value.status_code == 400
    assert "short" not in str(error.value.detail)


def test_massive_config_repr_hides_secrets(monkeypatch):
    from openoutreach.config import settings
    from openoutreach.proxies.massive_client import MassiveConfig

    monkeypatch.setattr(settings, "MASSIVE_PARENT_USERNAME", "parent-secret")
    monkeypatch.setattr(settings, "MASSIVE_PROXY_PASSWORD", "proxy-secret")
    monkeypatch.setattr(settings, "MASSIVE_REPORTING_API_KEY", "reporting-secret")
    monkeypatch.setattr(settings, "MASSIVE_REPORTING_ENABLED", True)

    config = MassiveConfig.from_settings()

    assert config is not None
    assert "parent-secret" not in repr(config)
    assert "proxy-secret" not in repr(config)
    assert "reporting-secret" not in repr(config)


def test_massive_reporting_reuses_proxy_password_when_no_reporting_key(monkeypatch):
    from openoutreach.config import settings
    from openoutreach.proxies.massive_client import MassiveConfig

    monkeypatch.setattr(settings, "MASSIVE_PARENT_USERNAME", "parent")
    monkeypatch.setattr(settings, "MASSIVE_PROXY_PASSWORD", "proxy-secret")
    monkeypatch.setattr(settings, "MASSIVE_REPORTING_API_KEY", None)
    monkeypatch.setattr(settings, "MASSIVE_REPORTING_ENABLED", True)

    config = MassiveConfig.from_settings()

    assert config is not None
    assert config.reporting_ready is True
    assert config.reporting_api_key == "proxy-secret"
