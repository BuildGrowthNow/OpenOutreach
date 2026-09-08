# openoutreach/api_v2/routers/email_tracking.py
"""Webhook endpoint called by the Cloudflare email-tracking Worker.

The Worker posts here after every open, click, or unsubscribe event.
Authentication: WORKER_WEBHOOK_SECRET env var checked via X-Webhook-Secret header.
"""

from __future__ import annotations

import hmac
import logging
import os
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/email-tracking", tags=["email-tracking"])


@router.get("/resolve/{campaign_id}/{short_code}")
async def resolve_tracking_link(campaign_id: str, short_code: str, request: Request, channel: str = "email", step_id: str = "") -> dict:
    """Resolve an opaque short link for the tracking Worker.

    This endpoint is Worker-authenticated and returns only an active link in
    the signed token's campaign.  The destination is expanded server-side so
    recipient-facing URLs never carry the destination or UTM payload.
    """
    expected = os.environ.get("WORKER_WEBHOOK_SECRET", "")
    incoming = request.headers.get("X-Tracking-Resolver-Secret", "")
    if not expected or not hmac.compare_digest(expected, incoming):
        raise HTTPException(status_code=401, detail="Invalid tracking resolver secret")
    from openoutreach.mongodb.connection import get_mongodb_collection
    links = get_mongodb_collection("tracked_links")
    doc = links.find_one({"campaign_id": campaign_id, "short_code": short_code, "is_active": True}) if links is not None else None
    if not doc:
        raise HTTPException(status_code=404, detail="Link not found")
    destination = str(doc.get("destination_url") or doc.get("original_url") or "")
    parsed = urlsplit(destination)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    values = {"channel": channel[:32], "campaign_id": campaign_id, "step_id": step_id[:128]}
    for key, value in (doc.get("default_utm") or {}).items():
        utm_key = key if str(key).startswith("utm_") else f"utm_{key}"
        rendered = str(value)
        for token, replacement in values.items():
            rendered = rendered.replace("{{" + token + "}}", replacement)
        query[utm_key] = rendered
    return {"destination_url": urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))}


@router.get("/resolve-click/{token_id}")
async def resolve_tracking_click(token_id: str, request: Request) -> dict:
    """Resolve a compact opaque click token into server-side attribution."""
    expected = os.environ.get("WORKER_WEBHOOK_SECRET", "")
    incoming = request.headers.get("X-Tracking-Resolver-Secret", "")
    if not expected or not hmac.compare_digest(expected, incoming):
        raise HTTPException(status_code=401, detail="Invalid tracking resolver secret")
    from openoutreach.mongodb.connection import get_mongodb_collection
    tokens = get_mongodb_collection("tracking_link_tokens")
    doc = tokens.find_one({"_id": token_id, "event": "click", "expires_at": {"$gt": datetime.now(timezone.utc)}}) if tokens is not None else None
    if not doc:
        raise HTTPException(status_code=404, detail="Click token not found")
    return {
        "short_code": str(doc.get("short_code") or ""),
        "destination_url": str(doc.get("destination_url") or ""),
        "deal_id": str(doc.get("deal_id") or ""),
        "campaign_id": str(doc.get("campaign_id") or ""),
        "tracked_link_id": str(doc.get("tracked_link_id") or ""),
        "lead_id": str(doc.get("lead_id") or ""),
        "step_id": str(doc.get("step_id") or ""),
        "message_id": str(doc.get("message_id") or ""),
        "channel": str(doc.get("channel") or "email"),
    }


class TrackingEvent(BaseModel):
    deal_id: str = Field(min_length=1, max_length=128)
    campaign_id: str = Field(default="", max_length=128)
    event: Literal["open", "click", "unsub"]
    # Keep timestamps within the range supported by datetime on all
    # deployment platforms. ``0`` retains the worker's optional fallback to
    # server time for older callers.
    ts: int = Field(default=0, ge=0, le=4_102_444_800)
    event_id: str = Field(default="", max_length=256)
    tracked_link_id: str = Field(default="", max_length=128)
    lead_id: str = Field(default="", max_length=128)
    step_id: str = Field(default="", max_length=128)
    message_id: str = Field(default="", max_length=256)
    channel: str = Field(default="email", max_length=32)


@router.post("/event", status_code=204, response_model=None)
async def tracking_event(request: Request, body: TrackingEvent) -> None:
    """Handle an open/click/unsub event from the Cloudflare Worker."""
    _verify_webhook_secret(request)

    from openoutreach.mongodb.connection import get_mongodb_collection

    deals_col = get_mongodb_collection("deals")
    leads_col = get_mongodb_collection("leads")
    events_col = get_mongodb_collection("tracking_events")

    if deals_col is None or leads_col is None:
        logger.warning("email_tracking webhook: MongoDB not available")
        # Do not acknowledge the event: the Worker retries 5xx responses and
        # would otherwise discard the event while persistence is unavailable.
        raise HTTPException(status_code=503, detail="Database unavailable")

    deal_doc = deals_col.find_one({"_id": body.deal_id}, {"campaign_id": 1, "lead_id": 1}) or {}
    # Attribution comes from the server-side deal relationship whenever it is
    # available; token/webhook fields are hints, never tenant authorization.
    if deal_doc.get("campaign_id"):
        body.campaign_id = str(deal_doc["campaign_id"])
    if deal_doc.get("lead_id"):
        body.lead_id = str(deal_doc["lead_id"])

    event_id = body.event_id or f"legacy:{body.event}:{body.deal_id}:{body.ts}"
    click_transaction = None
    if body.event == "click" and body.tracked_link_id and events_col is not None:
        click_transaction = _persist_click_transaction(
            body,
            event_id,
            deals_col,
            events_col,
            get_mongodb_collection("tracking_click_uniques"),
            get_mongodb_collection("tracked_links"),
        )
        if click_transaction is False:
            return

    is_unique = False
    event_persisted = click_transaction is True
    if not event_persisted and body.event == "click" and body.tracked_link_id:
        unique_markers = get_mongodb_collection("tracking_click_uniques")
        if unique_markers is not None:
            from pymongo.errors import DuplicateKeyError
            try:
                unique_markers.insert_one({
                    "_id": f"{body.deal_id}:{body.tracked_link_id}",
                    "deal_id": body.deal_id,
                    "tracked_link_id": body.tracked_link_id,
                    "created_at": datetime.now(timezone.utc),
                })
                is_unique = True
            except DuplicateKeyError:
                is_unique = False
        elif events_col is not None:
            # Compatibility path for databases that have not created the
            # marker collection yet. The production index is installed by
            # ensure_all_indexes.
            is_unique = events_col.count_documents({"event": "click", "deal_id": body.deal_id, "tracked_link_id": body.tracked_link_id}) == 0

    if events_col is not None and not event_persisted:
        from pymongo.errors import DuplicateKeyError
        try:
            events_col.insert_one({
                "_id": str(uuid4()), "event_id": event_id, "idempotency_key": event_id,
                "event": body.event, "campaign_id": body.campaign_id, "deal_id": body.deal_id,
                "lead_id": body.lead_id, "step_id": body.step_id, "message_id": body.message_id,
                "channel": body.channel, "tracked_link_id": body.tracked_link_id,
                "is_unique": is_unique,
                "created_at": datetime.fromtimestamp(body.ts, timezone.utc) if body.ts else datetime.now(timezone.utc),
            })
        except DuplicateKeyError:
            return

    if body.campaign_id:
        sequence_events = get_mongodb_collection("sequence_events")
        if sequence_events is not None:
            audit_event = {"click": "link_clicked", "unsub": "unsubscribe"}.get(body.event)
            if audit_event:
                try:
                    sequence_events.insert_one({
                        "campaign_id": body.campaign_id,
                        "deal_id": body.deal_id,
                        "step_id": body.step_id or "unknown",
                        "event": audit_event,
                        "reason": body.channel,
                        "created_at": datetime.fromtimestamp(body.ts, timezone.utc) if body.ts else datetime.now(timezone.utc),
                    })
                except Exception:
                    logger.debug("tracking sequence audit write failed", exc_info=True)

    if body.event == "open":
        _handle_open(body, deals_col)
    elif body.event == "click" and not event_persisted:
        _handle_click(body, deals_col, events_col)
    elif body.event == "unsub":
        _handle_unsub(body, deals_col, leads_col)
    else:
        logger.warning("email_tracking webhook: unknown event %r", body.event)


def _persist_click_transaction(body: TrackingEvent, event_id: str, deals_col, events_col, unique_markers, links_col) -> bool | None:
    """Atomically persist a click, recipient uniqueness, and counters.

    ``None`` means the Mongo client cannot start transactions, so the caller
    falls back to the compatibility path. ``False`` is an idempotent retry.
    """
    database = getattr(events_col, "database", None)
    client = getattr(database, "client", None)
    start_session = getattr(client, "start_session", None)
    if not callable(start_session):
        return None

    clicked_at = datetime.fromtimestamp(body.ts, timezone.utc) if body.ts else datetime.now(timezone.utc)
    event_doc = {
        "_id": str(uuid4()), "event_id": event_id, "idempotency_key": event_id,
        "event": "click", "campaign_id": body.campaign_id, "deal_id": body.deal_id,
        "lead_id": body.lead_id, "step_id": body.step_id, "message_id": body.message_id,
        "channel": body.channel, "tracked_link_id": body.tracked_link_id,
        "is_unique": False, "created_at": clicked_at,
    }

    def callback(session):
        is_unique = False
        if unique_markers is not None:
            marker = unique_markers.find_one_and_update(
                {"_id": f"{body.deal_id}:{body.tracked_link_id}"},
                {"$setOnInsert": {
                    "deal_id": body.deal_id,
                    "tracked_link_id": body.tracked_link_id,
                    "created_at": clicked_at,
                }},
                upsert=True,
                return_document=ReturnDocument.BEFORE,
                session=session,
            )
            is_unique = marker is None
        event_doc["is_unique"] = is_unique
        events_col.insert_one(event_doc, session=session)
        deals_col.update_one({"_id": body.deal_id}, {"$set": {"email_clicked_at": clicked_at}}, session=session)
        if links_col is not None:
            increments = {"total_clicks": 1}
            if is_unique:
                increments["unique_clicks"] = 1
            links_col.update_one(
                {"_id": body.tracked_link_id, "campaign_id": body.campaign_id},
                {"$inc": increments, "$set": {"last_clicked_at": clicked_at, "updated_at": clicked_at}},
                session=session,
            )

    try:
        with start_session() as session:
            session.with_transaction(callback)
        return True
    except DuplicateKeyError:
        return False
    except Exception:
        logger.info("click transaction unavailable; using compatibility persistence path", exc_info=True)
        return None


def _verify_webhook_secret(request: Request) -> None:
    expected = os.environ.get("WORKER_WEBHOOK_SECRET", "")
    if not expected:
        logger.error("WORKER_WEBHOOK_SECRET not set — rejecting tracking webhook")
        raise HTTPException(status_code=401, detail="Webhook secret not configured")
    incoming = request.headers.get("X-Webhook-Secret", "")
    if not hmac.compare_digest(expected, incoming):
        raise HTTPException(status_code=401, detail="Invalid webhook secret")


def _handle_open(body: TrackingEvent, deals_col) -> None:
    if not body.deal_id:
        logger.warning("email_tracking: missing deal_id in open event")
        return

    result = deals_col.update_one(
        {"_id": body.deal_id},
        {"$set": {"email_opened_at": datetime.fromtimestamp(body.ts, timezone.utc) if body.ts else datetime.now(timezone.utc)}, "$setOnInsert": {}},
    )
    # Preserve the existing funnel transition while making the timestamp the
    # canonical signal consumed by sequence conditions.
    deals_col.update_one({"_id": body.deal_id, "state": "email_sent"}, {"$set": {"state": "email_opened"}})
    if result.modified_count:
        logger.info("email_tracking: deal %s promoted to EMAIL_OPENED", body.deal_id)


def _handle_click(body: TrackingEvent, deals_col, events_col=None) -> None:
    if not body.deal_id:
        logger.warning("email_tracking: missing deal_id in click event")
        return

    from datetime import datetime, timezone
    from openoutreach.mongodb.connection import get_mongodb_collection

    clicked_at = datetime.fromtimestamp(body.ts, tz=timezone.utc) if body.ts else datetime.now(timezone.utc)
    deals_col.update_one(
        {"_id": body.deal_id},
        {"$set": {"email_clicked_at": clicked_at}},
    )
    if events_col is not None and body.tracked_link_id:
        # Counters are derived from immutable events and updated atomically.
        links = get_mongodb_collection("tracked_links")
        if links is not None:
            increments = {"total_clicks": 1}
            if body.event_id or body.ts:
                event = events_col.find_one({"idempotency_key": body.event_id or f"legacy:{body.event}:{body.deal_id}:{body.ts}"}, {"is_unique": 1})
                if event and event.get("is_unique"):
                    increments["unique_clicks"] = 1
            links.update_one({"_id": body.tracked_link_id, "campaign_id": body.campaign_id}, {"$inc": increments, "$set": {"last_clicked_at": clicked_at, "updated_at": clicked_at}})
    logger.info("email_tracking: deal %s click recorded at %s", body.deal_id, clicked_at)


def _handle_unsub(body: TrackingEvent, deals_col, leads_col) -> None:
    if not body.deal_id:
        logger.warning("email_tracking: missing deal_id in unsub event")
        return

    deal_doc = deals_col.find_one({"_id": body.deal_id}, {"lead_id": 1})
    if not deal_doc:
        return

    lead_id = deal_doc.get("lead_id")
    if lead_id:
        leads_col.update_one(
            {"_id": lead_id},
            {"$set": {"email_unsubscribed": True}},
        )
        deals_col.update_one(
            {"_id": body.deal_id},
            {"$set": {"sequence_done": True, "sequence_terminal_reason": "unsubscribe"}},
        )

    from openoutreach.mongodb.connection import get_mongodb_collection as _get
    tasks_col = _get("tasks")
    if tasks_col is not None and lead_id:
        tasks_col.update_many(
            {
                "lead_id": lead_id,
                "task_type": "email_follow_up",
                "status": {"$in": ["pending", "running"]},
            },
            {"$set": {"status": "cancelled"}},
        )

    logger.info("email_tracking: lead %s unsubscribed via deal %s", lead_id, body.deal_id)
