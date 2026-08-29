"""Regression tests for desktop bootstrap containment and token separation."""

from datetime import datetime, timedelta, timezone
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
from openoutreach.api_v2.routers import daemon_v2
from openoutreach.api_v2.routers.daemon_v2 import (
    ClaimRequest, CompleteRequest, DaemonEvent, EventBatchRequest,
    FailRequest, LeaseMutation,
)
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


@pytest.mark.parametrize("channel", ["linkedin", "whatsapp", "email"])
def test_task_binding_rejects_unbound_profile_for_every_channel(channel):
    context = TenantContext(
        "tenant-a", actor_type="daemon", device_id="device-a",
        profile_ids=frozenset({"profile-a", "profile-b"}),
        scopes=frozenset({"linkedin", "whatsapp", "email"}),
        channel_profile_ids={channel: frozenset({"profile-a"})},
    )
    document = {
        "_id": "task-b", "user_id": "tenant-a", "channel": channel,
        "task_type": "email_send" if channel == "email" else "whatsapp_message" if channel == "whatsapp" else "connect",
        "linkedin_profile_id": "profile-b",
    }
    with pytest.raises(HTTPException) as exc_info:
        daemon_v2._require_task_binding(context, document)
    assert exc_info.value.status_code == 404


def test_event_batch_preflights_all_profiles_before_writing(monkeypatch):
    collection = MagicMock()
    monkeypatch.setattr(daemon_v2, "get_mongodb_collection", lambda name: collection)
    context = TenantContext(
        "tenant-a", actor_type="daemon", device_id="device-a",
        profile_ids=frozenset({"profile-a", "profile-b"}),
        scopes=frozenset({"linkedin"}),
        channel_profile_ids={"linkedin": frozenset({"profile-a"})},
    )
    event = DaemonEvent(
        event_id="event-00000000000001", event_type="linkedin_state",
        profile_id="profile-b", channel="linkedin", payload={},
    )
    with pytest.raises(HTTPException) as exc_info:
        # Call the route function directly so the test exercises the same
        # server-side preflight used by FastAPI after dependency resolution.
        import asyncio
        asyncio.run(daemon_v2.ingest_events_v2(EventBatchRequest(events=[event]), context))
    assert exc_info.value.status_code == 404
    collection.insert_one.assert_not_called()


@pytest.mark.asyncio
async def test_all_lease_mutations_are_tenant_scoped(monkeypatch):
    class Result:
        matched_count = 0

    class Collection:
        def __init__(self):
            self.documents = [{
                "_id": "task-b", "user_id": "tenant-b", "channel": "linkedin",
                "linkedin_profile_id": "profile-b", "status": "running",
                "leased_by_device_id": "device-b", "lease_id": "b" * 16,
                "lease_expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
            }]
            self.writes = []

        def find_one(self, query, *args, **kwargs):
            for document in self.documents:
                if all(document.get(key) == value for key, value in query.items() if not isinstance(value, dict)):
                    return document
            return None

        def update_one(self, query, update, *args, **kwargs):
            self.writes.append((query, update))
            return Result()

        def find_one_and_update(self, query, update, *args, **kwargs):
            return None

        def insert_one(self, document):
            self.writes.append((document,))

    collection = Collection()
    monkeypatch.setattr(daemon_v2, "get_mongodb_collection", lambda name: collection)
    monkeypatch.setattr(daemon_v2.settings, "DAEMON_TASK_CLAIM_ENABLED", True)
    monkeypatch.setattr(daemon_v2.settings, "DAEMON_V2_LINKEDIN_ENABLED", True)
    context = TenantContext(
        "tenant-a", actor_type="daemon", device_id="device-a",
        profile_ids=frozenset({"profile-a"}), scopes=frozenset({"linkedin"}),
        channel_profile_ids={"linkedin": frozenset({"profile-a"})},
    )
    lease_id = "a" * 16
    with pytest.raises(HTTPException) as renew_error:
        await daemon_v2.renew_task_v2("task-b", LeaseMutation(lease_id=lease_id), context)
    with pytest.raises(HTTPException) as complete_error:
        await daemon_v2.complete_task_v2(
            "task-b", CompleteRequest(lease_id=lease_id, idempotency_key="i" * 16, result={}), context,
        )
    with pytest.raises(HTTPException) as fail_error:
        await daemon_v2.fail_task_v2(
            "task-b", FailRequest(lease_id=lease_id, category="retryable"), context,
        )
    with pytest.raises(HTTPException) as cancel_error:
        await daemon_v2.cancel_ack_task_v2("task-b", LeaseMutation(lease_id=lease_id), context)
    assert renew_error.value.status_code == 410
    assert complete_error.value.status_code == 410
    assert fail_error.value.status_code == 410
    assert cancel_error.value.status_code == 404
    assert collection.writes == []

    claim = await daemon_v2.claim_task_v2(
        ClaimRequest(profile_id="profile-a", channel="linkedin"), context,
    )
    assert claim is None
    assert collection.writes == []


@pytest.mark.asyncio
async def test_email_claim_accepts_canonical_mailbox_task_fields(monkeypatch):
    collection = MagicMock()
    collection.find_one_and_update.return_value = None
    monkeypatch.setattr(daemon_v2, "get_mongodb_collection", lambda name: collection)
    monkeypatch.setattr(daemon_v2.settings, "DAEMON_TASK_CLAIM_ENABLED", True)
    monkeypatch.setattr(daemon_v2.settings, "DAEMON_V2_EMAIL_ENABLED", True)
    context = TenantContext(
        "tenant-a", actor_type="daemon", device_id="device-a",
        profile_ids=frozenset({"mailbox-a"}), scopes=frozenset({"email"}),
        channel_profile_ids={"email": frozenset({"mailbox-a"})},
    )
    assert await daemon_v2.claim_task_v2(
        ClaimRequest(profile_id="mailbox-a", channel="email"), context,
    ) is None
    query = collection.find_one_and_update.call_args.args[0]
    assert {"mailbox_id": "mailbox-a"} in query["$or"]
    assert query["user_id"] == "tenant-a"


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
