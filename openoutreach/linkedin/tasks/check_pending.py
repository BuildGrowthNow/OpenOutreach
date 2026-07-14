# openoutreach/linkedin/tasks/check_pending.py
"""Check pending task — re-checks one due PENDING deal in the campaign.

Lazy: the slot carries only ``campaign_id``. The handler picks the
oldest-due PENDING deal at execution time. If the recheck leaves the
deal in PENDING, the backoff is doubled and ``next_check_pending_at``
re-stamped via the ``on_deal_state_entered`` hook.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from termcolor import colored

from openoutreach.core.db.deals import set_profile_state
from openoutreach.mongodb import models
from openoutreach.mongodb.connection import get_mongodb_collection
from linkedin_cli.exceptions import SkipProfile

logger = logging.getLogger(__name__)


def _next_due_pending_deal(campaign):
    """Find the next due PENDING deal for a campaign using MongoDB."""
    deal_collection = get_mongodb_collection("deals")
    if deal_collection is None:
        return None

    now = datetime.now(timezone.utc)
    deal_doc = deal_collection.find_one(
        {
            "campaign_id": campaign._id if hasattr(campaign, '_id') else str(campaign),
            "state": models.Deal.DealState.PENDING,
            "next_check_pending_at": {"$lte": now},
        },
        sort=[("next_check_pending_at", 1)]  # Oldest due first
    )

    if deal_doc is None:
        return None

    return models.Deal.from_dict(deal_doc)


def _double_backoff(deal) -> float:
    """Double the backoff hours for a deal using MongoDB."""
    from openoutreach.core.conf import CAMPAIGN_CONFIG

    current = deal.backoff_hours or CAMPAIGN_CONFIG["check_pending_recheck_after_hours"]
    # Fix type issues: current might be Any | object, ensure it's a number
    backoff_value = float(current) if current is not None else 1.0  # type: ignore
    deal.backoff_hours = backoff_value * 2
    deal.save()  # MongoDB save doesn't need update_fields
    return float(deal.backoff_hours)  # type: ignore


def handle_check_pending(task, session, qualifiers):
    from linkedin_cli.actions.status import get_connection_status

    campaign = session.campaign
    deal = _next_due_pending_deal(campaign)
    if deal is None:
        logger.info("[%s] check_pending: no due PENDING deals — slot skipped", campaign)
        return

    public_id = deal.lead.public_identifier
    logger.info(
        "[%s] %s %s",
        campaign,
        colored("▶ check_pending", "magenta", attrs=["bold"]),
        public_id,
    )

    profile = deal.lead.to_profile_dict()
    profile_for_status = profile.get("profile") or profile

    try:
        # The library returns the observed UI state as a str; lift it into our enum.
        status = get_connection_status(session, profile_for_status)
        new_state = status.value  # Keep as string for MongoDB
    except SkipProfile as e:
        logger.warning("Skipping %s: %s", public_id, e)
        set_profile_state(session, public_id, models.Deal.DealState.FAILED)
        return

    if new_state == models.Deal.DealState.PENDING:
        # Still pending — double the backoff before set_profile_state so the
        # state hook re-stamps next_check_pending_at with the doubled value.
        old = deal.backoff_hours or 0
        new = _double_backoff(deal)
        logger.info("%s still pending — backoff %.1fh → %.1fh", public_id, old, new)

    set_profile_state(session, public_id, new_state)
