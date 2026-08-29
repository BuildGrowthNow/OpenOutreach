"""Tests for the email tracking webhook contract."""

import pytest
from pydantic import ValidationError
from starlette.requests import Request
from fastapi import HTTPException

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
