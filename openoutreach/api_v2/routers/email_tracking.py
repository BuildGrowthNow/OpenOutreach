# openoutreach/api_v2/routers/email_tracking.py
"""Webhook endpoint called by the Cloudflare email-tracking Worker.

The Worker posts here after every open, click, or unsubscribe event.
Authentication: WORKER_WEBHOOK_SECRET env var checked via X-Webhook-Secret header.
"""

from __future__ import annotations

import hmac
import logging
import os
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/email-tracking", tags=["email-tracking"])


class TrackingEvent(BaseModel):
    deal_id: str = Field(min_length=1, max_length=128)
    campaign_id: str = Field(default="", max_length=128)
    event: Literal["open", "click", "unsub"]
    # Keep timestamps within the range supported by datetime on all
    # deployment platforms. ``0`` retains the worker's optional fallback to
    # server time for older callers.
    ts: int = Field(default=0, ge=0, le=4_102_444_800)


@router.post("/event", status_code=204, response_model=None)
async def tracking_event(request: Request, body: TrackingEvent) -> None:
    """Handle an open/click/unsub event from the Cloudflare Worker."""
    _verify_webhook_secret(request)

    from openoutreach.mongodb.connection import get_mongodb_collection

    deals_col = get_mongodb_collection("deals")
    leads_col = get_mongodb_collection("leads")

    if deals_col is None or leads_col is None:
        logger.warning("email_tracking webhook: MongoDB not available")
        # Do not acknowledge the event: the Worker retries 5xx responses and
        # would otherwise discard the event while persistence is unavailable.
        raise HTTPException(status_code=503, detail="Database unavailable")

    if body.event == "open":
        _handle_open(body, deals_col)
    elif body.event == "click":
        _handle_click(body, deals_col)
    elif body.event == "unsub":
        _handle_unsub(body, deals_col, leads_col)
    else:
        logger.warning("email_tracking webhook: unknown event %r", body.event)


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
        {"_id": body.deal_id, "state": "email_sent"},
        {"$set": {"state": "email_opened"}},
    )
    if result.modified_count:
        logger.info("email_tracking: deal %s promoted to EMAIL_OPENED", body.deal_id)


def _handle_click(body: TrackingEvent, deals_col) -> None:
    if not body.deal_id:
        logger.warning("email_tracking: missing deal_id in click event")
        return

    from datetime import datetime, timezone

    clicked_at = datetime.fromtimestamp(body.ts, tz=timezone.utc) if body.ts else datetime.now(timezone.utc)
    deals_col.update_one(
        {"_id": body.deal_id},
        {"$set": {"email_clicked_at": clicked_at}},
    )
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
