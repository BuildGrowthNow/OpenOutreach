"""Tests for the email tracking webhook contract."""

import pytest
from pydantic import ValidationError
from starlette.requests import Request
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from openoutreach.api_v2.routers.email_tracking import TrackingEvent, tracking_event


@pytest.mark.parametrize("event", ["open", "click", "unsub"])
def test_tracking_event_accepts_supported_events(event):
    parsed = TrackingEvent(deal_id="deal-1", event=event)

    assert parsed.event == event


def test_tracking_event_rejects_unknown_event():
    with pytest.raises(ValidationError):
        TrackingEvent(deal_id="deal-1", event="delete")


@pytest.mark.parametrize("deal_id", ["", "x" * 129])
def test_tracking_event_bounds_deal_id(deal_id):
    with pytest.raises(ValidationError):
        TrackingEvent(deal_id=deal_id, event="open")


@pytest.mark.parametrize("timestamp", [-1, 4_102_444_801])
def test_tracking_event_bounds_timestamp(timestamp):
    with pytest.raises(ValidationError):
        TrackingEvent(deal_id="deal-1", event="click", ts=timestamp)


@pytest.mark.asyncio
async def test_tracking_event_returns_retryable_error_when_database_unavailable(monkeypatch):
    monkeypatch.setenv("WORKER_WEBHOOK_SECRET", "webhook-secret")

    def no_database(_name):
        return None

    monkeypatch.setattr("openoutreach.mongodb.connection.get_mongodb_collection", no_database)
    request = Request({
        "type": "http",
        "headers": [(b"x-webhook-secret", b"webhook-secret")],
    })

    with pytest.raises(HTTPException) as error:
        await tracking_event(request, TrackingEvent(deal_id="deal-1", event="open"))

    assert error.value.status_code == 503


@pytest.mark.asyncio
async def test_click_retries_are_idempotent_but_separate_clicks_count(monkeypatch):
    class Result:
        modified_count = 1

    class Collection:
        def __init__(self, docs=None):
            self.docs = docs or []

        def find_one(self, query, projection=None):
            for doc in self.docs:
                if all(doc.get(key) == value for key, value in query.items() if not isinstance(value, dict)):
                    return dict(doc)
            return None

        def insert_one(self, doc):
            if any(existing.get("_id") == doc.get("_id") or existing.get("idempotency_key") == doc.get("idempotency_key") for existing in self.docs):
                raise DuplicateKeyError("duplicate")
            self.docs.append(dict(doc))

        def count_documents(self, query):
            return sum(1 for doc in self.docs if all(doc.get(key) == value for key, value in query.items()))

        def update_one(self, query, update, **kwargs):
            doc = self.find_one(query)
            if doc is None:
                return Result()
            target = next(item for item in self.docs if item.get("_id") == doc.get("_id"))
            for key, value in update.get("$set", {}).items():
                target[key] = value
            for key, value in update.get("$inc", {}).items():
                target[key] = target.get(key, 0) + value
            return Result()

    deals = Collection([{"_id": "deal-1", "campaign_id": "campaign-1", "lead_id": "lead-1"}])
    leads = Collection([{"_id": "lead-1"}])
    events = Collection()
    markers = Collection()
    links = Collection([{"_id": "link-1", "campaign_id": "campaign-1", "total_clicks": 0, "unique_clicks": 0}])
    collections = {
        "deals": deals, "leads": leads, "tracking_events": events,
        "tracking_click_uniques": markers, "tracked_links": links,
        "sequence_events": None,
    }
    monkeypatch.setenv("WORKER_WEBHOOK_SECRET", "webhook-secret")
    monkeypatch.setattr("openoutreach.mongodb.connection.get_mongodb_collection", lambda name: collections.get(name))
    request = Request({"type": "http", "headers": [(b"x-webhook-secret", b"webhook-secret")]})

    first = TrackingEvent(deal_id="deal-1", event="click", event_id="click-1", tracked_link_id="link-1", ts=1)
    second = TrackingEvent(deal_id="deal-1", event="click", event_id="click-2", tracked_link_id="link-1", ts=2)
    await tracking_event(request, first)
    await tracking_event(request, first)
    await tracking_event(request, second)

    assert len(events.docs) == 2
    assert links.docs[0]["total_clicks"] == 2
    assert links.docs[0]["unique_clicks"] == 1
    assert events.docs[0]["is_unique"] is True
    assert events.docs[1]["is_unique"] is False
