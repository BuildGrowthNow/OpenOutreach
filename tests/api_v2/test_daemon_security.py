"""Regression tests for desktop bootstrap containment and token separation."""

from datetime import datetime, timedelta, timezone
import json
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from starlette.requests import Request

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
    ClaimRequest, CompleteRequest, ConfigurationResponse,
    DaemonEvent, EventBatchRequest,
    FailRequest, LeaseMutation,
)
from openoutreach.api_v2.daemon_channel_contracts import LinkedInActionReceipt
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


def test_typed_event_payload_rejects_secret_material():
    with pytest.raises(ValidationError):
        DaemonEvent(event_id="event-0000000001", event_type="linkedin_state",
                    profile_id="profile-a", channel="linkedin",
                    payload={"cookie_data": "redacted"})
    with pytest.raises(ValidationError):
        DaemonEvent(event_id="event-0000000002", event_type="linkedin_state",
                    profile_id="profile-a", channel="linkedin",
                    payload={"nested": {"provider_token": "redacted"}})


def test_daemon_configuration_contract_is_bounded_and_strict():
    base = {
        "profile_id": "profile-a",
        "active_hours": {"enabled": False, "start_hour": 9, "end_hour": 18,
                          "timezone": "UTC", "days": [1, 2, 3, 4, 5]},
        "rate_limits": {"velocity": 20, "daily_connect_limit": 20,
                         "daily_message_limit": 40, "cooldown_minutes": 0},
        "channel_policy": {"linkedin": True, "whatsapp": False, "email": False},
        "task_capabilities": ["connect"],
    }
    response = ConfigurationResponse.model_validate(base)
    assert response.task_capabilities == ["connect"]
    with pytest.raises(ValidationError):
        ConfigurationResponse.model_validate({**base, "unexpected": True})
    with pytest.raises(ValidationError):
        ConfigurationResponse.model_validate({**base, "task_capabilities": [str(i) for i in range(21)]})


def test_completion_requires_channel_typed_receipt_and_matching_effect():
    task = {"channel": "linkedin", "task_type": "send_manual_message"}
    valid = {"receipt": LinkedInActionReceipt(
        action="manual_send", target_key="person-1", effect_key="effect-1",
        outcome="applied", observed_at=datetime.now(timezone.utc),
    ).model_dump(mode="json")}
    daemon_v2._validate_completion_result(task, valid, "effect-1")
    with pytest.raises(HTTPException) as missing:
        daemon_v2._validate_completion_result(task, {}, "effect-1")
    assert missing.value.status_code == 422
    with pytest.raises(HTTPException) as wrong_effect:
        daemon_v2._validate_completion_result(task, valid, "effect-2")
    assert wrong_effect.value.status_code == 422


def test_claim_request_bounds_profile_and_task_type_inputs():
    with pytest.raises(ValidationError):
        ClaimRequest(profile_id="", channel="linkedin")
    with pytest.raises(ValidationError):
        ClaimRequest(profile_id="p", channel="linkedin", supported_task_types=["x" * 65])


@pytest.mark.asyncio
async def test_failure_idempotency_key_is_checked_against_task_effect(monkeypatch):
    effect_key = "e" * 16
    task = {"_id": "task-1", "channel": "linkedin", "task_type": "connect",
            "linkedin_profile_id": "profile-a", "idempotency_key": effect_key,
            "failure_idempotency_key": effect_key, "status": "failed",
            "leased_by_device_id": "device-a"}
    context = TenantContext("tenant-a", actor_type="daemon", device_id="device-a",
                            profile_ids=frozenset({"profile-a"}), scopes=frozenset({"linkedin"}),
                            channel_profile_ids={"linkedin": frozenset({"profile-a"})})
    collection = MagicMock()
    collection.find_one.return_value = task
    monkeypatch.setattr(daemon_v2, "get_mongodb_collection", lambda _name: collection)
    with pytest.raises(HTTPException) as exc_info:
        await daemon_v2.fail_task_v2(
            "task-1", FailRequest(lease_id="l" * 16, category="retryable",
                                   idempotency_key="w" * 16), context)
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_daemon_configuration_advertises_linkedin_observation(monkeypatch):
    collection = MagicMock()
    collection.find_one.return_value = {}
    monkeypatch.setattr(daemon_v2, "get_mongodb_collection", lambda _name: collection)
    monkeypatch.setattr(daemon_v2.settings, "DAEMON_V2_LINKEDIN_ENABLED", True)
    context = TenantContext(
        "tenant-a", actor_type="daemon", device_id="device-a",
        profile_ids=frozenset({"profile-a"}), scopes=frozenset({"linkedin"}),
        channel_profile_ids={"linkedin": frozenset({"profile-a"})},
    )
    request = Request({"type": "http", "method": "GET", "path": "/",
                       "query_string": b"channel=linkedin", "headers": []})
    response = await daemon_v2.configuration(request, "profile-a", context)
    body = json.loads(response.body)
    assert "observe" in body["task_capabilities"]


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


@pytest.mark.asyncio
async def test_event_batch_preflights_all_profiles_before_writing(monkeypatch):
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
        await daemon_v2.ingest_events_v2(EventBatchRequest(events=[event]), context)
    assert exc_info.value.status_code == 404
    collection.insert_one.assert_not_called()


def test_successful_whatsapp_effect_projects_idempotently(monkeypatch):
    deals = MagicMock()
    deals.find_one.return_value = {"_id": "deal-a", "user_id": "tenant-a", "state": "Qualified"}
    logs = MagicMock()
    messages = MagicMock()
    collections = {"deals": deals, "action_logs": logs, "chat_messages": messages}
    monkeypatch.setattr(daemon_v2, "get_mongodb_collection", lambda name: collections.get(name))
    context = TenantContext(
        "tenant-a", actor_type="daemon", device_id="device-a",
        profile_ids=frozenset({"wa-a"}), scopes=frozenset({"whatsapp"}),
        channel_profile_ids={"whatsapp": frozenset({"wa-a"})},
    )
    daemon_v2._project_channel_effect(
        context,
        {"_id": "task-a", "channel": "whatsapp", "whatsapp_profile_id": "wa-a",
         "task_type": "whatsapp_message",
         "payload": {"deal_id": "deal-a", "campaign_id": "campaign-a", "message": "Hello"}},
        {"outcome": "applied", "receipt": {"action": "send", "target_key": "+15551212"}},
        "effect-a", datetime.now(timezone.utc),
    )
    assert logs.update_one.call_args.kwargs["upsert"] is True
    assert messages.update_one.call_args.kwargs["upsert"] is True
    assert deals.update_one.call_args.args[0]["user_id"] == "tenant-a"
    assert messages.update_one.call_args.args[0]["user_id"] == "tenant-a"
    assert logs.update_one.call_args.args[0]["_id"] == "daemon-effect:effect-a"


def test_whatsapp_sync_projects_delivery_and_opt_out(monkeypatch):
    deals = MagicMock()
    deals.find_one.return_value = {"_id": "deal-a", "user_id": "tenant-a", "lead_id": "lead-a", "state": "Pending"}
    leads = MagicMock()
    messages = MagicMock()
    logs = MagicMock()
    collections = {"deals": deals, "leads": leads, "chat_messages": messages, "action_logs": logs}
    monkeypatch.setattr(daemon_v2, "get_mongodb_collection", lambda name: collections.get(name))
    context = TenantContext(
        "tenant-a", actor_type="daemon", device_id="device-a",
        profile_ids=frozenset({"wa-a"}), scopes=frozenset({"whatsapp"}),
        channel_profile_ids={"whatsapp": frozenset({"wa-a"})},
    )
    daemon_v2._project_channel_effect(
        context,
        {"_id": "task-sync", "channel": "whatsapp", "whatsapp_profile_id": "wa-a",
         "task_type": "whatsapp_sync", "payload": {"deal_id": "deal-a", "campaign_id": "campaign-a"}},
        {"outcome": "observed", "receipt": {"action": "sync", "target_key": "sync"},
         "sync": {"messages": [{"content": "STOP", "is_outgoing": "false", "delivery_status": ""}]}},
        "effect-sync", datetime.now(timezone.utc),
    )
    assert any(call.args[0].get("_id") == "lead-a" for call in leads.update_one.call_args_list)
    assert any(call.args[0].get("_id") == "deal-a" for call in deals.update_one.call_args_list)
    assert messages.update_one.call_args.kwargs["upsert"] is True


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
            "task-b", FailRequest(lease_id=lease_id, category="retryable", idempotency_key="i" * 16), context,
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
