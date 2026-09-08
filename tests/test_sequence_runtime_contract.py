"""Regression tests for node runtime policy and timed condition semantics."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from starlette.requests import Request

from openoutreach.core import sequence_executor
from openoutreach.api_v2.routers.email_tracking import resolve_tracking_click
from openoutreach.core.sequence_message import fallback_config, message_config
from openoutreach.core.sequence_schema import SequenceEdge, SequenceNode
from openoutreach.emails.tracking import click_redirect_url_for_recipient
from openoutreach.mongodb.models import Campaign, Deal
from openoutreach.whatsapp.tasks.send_message import _message_action_log_query


class _Collection:
    def __init__(self, docs=None):
        self.docs = docs or []

    def count_documents(self, query):
        return sum(1 for doc in self.docs if all(doc.get(key) == value for key, value in query.items() if not isinstance(value, dict)))

    def find_one(self, *args, **kwargs):
        return None


def test_timed_negative_condition_waits_before_no(monkeypatch):
    sent_at = datetime.now(timezone.utc) - timedelta(hours=1)
    deal = Deal(sequence_last_message_at=sent_at, sequence_last_step_at=datetime.now(timezone.utc))
    monkeypatch.setattr(sequence_executor, "get_mongodb_collection", lambda name: _Collection())

    result = sequence_executor._check_condition(
        deal,
        {"data": {"condition": "email_not_opened", "observation_window_hours": 2}},
        {},
    )
    assert result == "waiting"


def test_click_after_send_is_included_in_condition_window(monkeypatch):
    sent_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    click_at = sent_at + timedelta(minutes=2)
    deal = Deal(
        _id="deal-1",
        campaign_id="campaign-1",
        sequence_last_message_at=sent_at,
        sequence_last_step_at=datetime.now(timezone.utc),
    )

    class Events(_Collection):
        def count_documents(self, query):
            return 1 if query.get("event") == "click" and query["created_at"]["$gte"] <= click_at else 0

    monkeypatch.setattr(sequence_executor, "get_mongodb_collection", lambda name: Events() if name == "tracking_events" else _Collection())
    assert sequence_executor._check_condition(
        deal,
        {"data": {"condition": "link_clicked", "link_key": "demo", "observation_window_hours": 2}},
        {},
    ) == "yes"


def test_message_config_normalizes_legacy_and_nested_shapes():
    assert message_config({"data": {"message": {"content_mode": "static", "body": "hello"}}})["body"] == "hello"
    legacy = message_config({"data": {"body": "legacy"}})
    assert legacy["body"] == "legacy"
    assert legacy["content_mode"] == "static"


def test_fallback_modes_are_explicit_and_static_requires_body():
    assert fallback_config({"fallback_mode": "continue", "fallback_body": ""}) == ("continue", "")
    assert fallback_config({"fallback_mode": "skip", "fallback_body": "unused"}) == ("skip", "unused")
    assert fallback_config({"fallback_mode": "static", "fallback_body": "Use this"}) == ("static", "Use this")


def test_safety_default_is_materialized_into_the_task_policy():
    campaign = Campaign(
        _id="campaign-1",
        safety_defaults={"stop_on_reply": True},
        sequence_steps=[{"id": "email", "type": "action", "data": {"message": {"stop_on_reply": False}}}],
    )
    assert sequence_executor._effective_stop_on_reply(campaign, "email") is True


def test_previous_message_policy_controls_the_next_action_until_it_sends():
    previous_message_at = datetime.now(timezone.utc)
    deal = Deal(sequence_stop_on_reply=False, sequence_last_message_at=previous_message_at)
    assert sequence_executor._stop_on_reply_for_step(deal, "action", {"stop_on_reply": True}, {}) is False
    no_previous_message = Deal(sequence_stop_on_reply=False)
    assert sequence_executor._stop_on_reply_for_step(no_previous_message, "action", {"stop_on_reply": True}, {}) is True


def test_sequence_skip_fallback_counts_as_a_completed_action(monkeypatch):
    class Deals:
        def find_one(self, query):
            return {"_id": query["_id"], "sequence_last_action_skipped_at": datetime.now(timezone.utc)}

    from openoutreach.core import daemon
    monkeypatch.setattr("openoutreach.mongodb.connection.get_mongodb_collection", lambda name: Deals())
    task = SimpleNamespace(payload={"deal_id": "deal-1", "step_id": "email", "message": {"fallback_mode": "skip"}}, task_type="email_follow_up")
    before = {"sequence_last_action_skipped_at": None}
    assert daemon._sequence_task_succeeded(task, before) is True


def test_short_link_uses_opaque_server_side_token_when_store_is_available(monkeypatch):
    class Tokens:
        def __init__(self):
            self.docs = []

        def insert_one(self, doc):
            self.docs.append(doc)

    tokens = Tokens()
    import openoutreach.emails.tracking as tracking
    monkeypatch.setattr(tracking, "TRACKING_BASE_URL", "https://track.example")
    import openoutreach.mongodb.connection as connection
    monkeypatch.setattr(connection, "get_mongodb_collection", lambda name: tokens if name == "tracking_link_tokens" else None)
    url = click_redirect_url_for_recipient(
        "deal-1", "https://example.com/demo?x=1", campaign_id="campaign-1", tracked_link_id="link-1", short_code="abc123"
    )
    assert len(url) < 100
    assert url.startswith("https://track.example/click/abc123/")
    assert len(tokens.docs) == 1
    assert tokens.docs[0]["destination_url"] == "https://example.com/demo?x=1"


@pytest.mark.asyncio
async def test_compact_click_resolver_returns_server_side_attribution(monkeypatch):
    class Tokens:
        def find_one(self, query):
            assert query["_id"] == "opaque-1"
            return {
                "_id": "opaque-1", "event": "click", "short_code": "abc123",
                "destination_url": "https://example.com/demo?utm_source=linkedin",
                "deal_id": "deal-1", "campaign_id": "campaign-1", "tracked_link_id": "link-1",
                "lead_id": "lead-1", "step_id": "node-1", "channel": "linkedin",
            }

    monkeypatch.setenv("WORKER_WEBHOOK_SECRET", "resolver-secret")
    monkeypatch.setattr("openoutreach.mongodb.connection.get_mongodb_collection", lambda name: Tokens())
    request = Request({"type": "http", "headers": [(b"x-tracking-resolver-secret", b"resolver-secret")]})
    result = await resolve_tracking_click("opaque-1", request)
    assert result["short_code"] == "abc123"
    assert result["deal_id"] == "deal-1"
    assert result["destination_url"].startswith("https://example.com/")


def test_sequence_contract_rejects_unknown_node_and_edge_fields():
    node = {"id": "a", "type": "end", "data": {}, "unexpected": True}
    edge = {"id": "a-b", "source": "a", "target": "b", "unexpected": True}
    with pytest.raises(ValueError):
        SequenceNode.model_validate(node)
    with pytest.raises(ValueError):
        SequenceEdge.model_validate(edge)
    with pytest.raises(ValueError):
        SequenceEdge.model_validate({"id": "a-b", "source": "a", "target": "b", "data": {"label": "ignored"}})


def test_whatsapp_sequence_deduplication_is_scoped_to_the_node():
    first = _message_action_log_query("campaign-1", "deal-1", "wa-first")
    second = _message_action_log_query("campaign-1", "deal-1", "wa-second")
    assert first != second
    assert first["details.step_id"] == "wa-first"
    assert second["details.step_id"] == "wa-second"
