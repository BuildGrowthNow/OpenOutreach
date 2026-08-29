"""Regression tests for desktop bootstrap containment and token separation."""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from openoutreach.api_v2.daemon_security import (
    assert_safe_response,
    is_secure_version,
    require_secure_daemon,
)
from openoutreach.api_v2.dependencies_v2 import get_current_user
from openoutreach.api_v2.routers.auth import create_access_token, create_refresh_token
from openoutreach.api_v2.routers.daemon import bootstrap_daemon
from openoutreach.api_v2.daemon_v2_auth import require_profile
from openoutreach.api_v2.tenant_security import TenantContext, owned_predicate


def test_secure_version_policy_is_fail_closed_for_legacy_clients():
    assert not is_secure_version(None)
    assert not is_secure_version("1.9.8")
    assert is_secure_version("2.1.0")
    assert not is_secure_version("2.0.0")
    assert not is_secure_version("2.0.0-beta")


def test_legacy_daemon_is_rejected_before_resource_access():
    request = MagicMock()
    request.headers = {}
    request.client = None
    with pytest.raises(HTTPException) as exc_info:
        require_secure_daemon(request)
    assert exc_info.value.status_code == 426


def test_response_secret_denylist_fails_closed():
    with pytest.raises(RuntimeError):
        assert_safe_response({"nested": {"llm_api_key": "secret"}})
    with pytest.raises(RuntimeError):
        assert_safe_response({"message": "mongodb+srv://user:password@example/db"})


def test_tenant_predicate_is_server_derived_and_non_empty():
    context = TenantContext("tenant-a")
    assert owned_predicate(context, resource_id="object-b", profile_id="profile-a") == {
        "user_id": "tenant-a",
        "_id": "object-b",
        "profile_id": "profile-a",
    }
    with pytest.raises(ValueError):
        owned_predicate(context, user_id="tenant-b")
    with pytest.raises(ValueError):
        TenantContext("")


def test_channel_profile_binding_rejects_cross_channel_profile_use():
    context = TenantContext(
        "tenant-a", profile_ids=frozenset({"li-1", "wa-1"}),
        scopes=frozenset({"linkedin", "whatsapp"}),
        channel_profile_ids={"linkedin": frozenset({"li-1"}),
                             "whatsapp": frozenset({"wa-1"})},
    )
    require_profile(context, "li-1", "linkedin")
    with pytest.raises(HTTPException) as exc_info:
        require_profile(context, "li-1", "whatsapp")
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_bootstrap_is_always_gone():
    request = MagicMock()
    with pytest.raises(HTTPException) as exc_info:
        await bootstrap_daemon(request)
    assert exc_info.value.status_code == 410
    assert exc_info.value.headers["Cache-Control"] == "no-store"


@pytest.mark.asyncio
async def test_refresh_token_cannot_authorize_resources():
    token = create_refresh_token("missing-user")
    credentials = MagicMock()
    credentials.credentials = token
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_access_token_still_reaches_user_lookup():
    token = create_access_token("missing-user", "missing@example.com")
    credentials = MagicMock()
    credentials.credentials = token
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials)
    assert exc_info.value.status_code == 401
