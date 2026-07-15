# openoutreach/linkedin/tasks/follow_up.py
"""Follow-up task — runs the agentic follow-up for one eligible CONNECTED deal."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Dict, Optional

from openoutreach.mongodb import models
from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.linkedin.services.smart_rate_limits import (
    smart_can_execute,
    smart_record_action,
    smart_get_remaining,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from openoutreach.linkedin.browser.session import AccountSession

# Required silence between nudges scales with unanswered count:
# 1 unanswered → 3d, 2 → 6d, 3 → 9d. Skips the LLM call while open.
MIN_DAYS_PER_UNANSWERED = 3


def _build_send_profile(deal) -> dict:
    """Minimal profile dict for ``send_raw_message`` and its fallbacks."""
    from openoutreach.mongodb.models import Lead
    lead = Lead.get(deal.lead_id)
    if not lead:
        return {"public_identifier": "", "urn": ""}
    return {
        "public_identifier": lead.public_identifier,
        "urn": lead.urn or "",
    }


def _replace_placeholders(message: str, deal) -> str:
    """Replace common placeholders in messages with actual lead data.

    Handles cases where the LLM generates placeholders despite being told not to.
    Falls back to public_identifier if profile data is unavailable.
    """
    import json
    import re
    from openoutreach.mongodb.models import Lead

    lead = Lead.get(deal.lead_id)
    if not lead:
        return message

    first_name = ""
    last_name = ""
    company = ""

    # Try to get data from cached_profile
    if lead.cached_profile:
        try:
            # cached_profile is already a dict in MongoDB, not JSON string
            profile = lead.cached_profile if isinstance(lead.cached_profile, dict) else json.loads(lead.cached_profile)
            first_name = profile.get("first_name", "")
            last_name = profile.get("last_name", "")
            # Company could be in various places in the profile
            if "experience" in profile and profile["experience"]:
                company = profile["experience"][0].get("company_name", "")
        except Exception:
            pass

    # Fallback to public_identifier if we don't have a first name
    if not first_name:
        first_name = lead.public_identifier

    # Replace common placeholder patterns (case-insensitive)
    replacements = {
        r'\[First Name\]': first_name,
        r'\[first name\]': first_name,
        r'\[FIRST NAME\]': first_name,
        r'\[Last Name\]': last_name,
        r'\[last name\]': last_name,
        r'\[LAST NAME\]': last_name,
        r'\[Company Name\]': company,
        r'\[company name\]': company,
        r'\[COMPANY NAME\]': company,
    }

    result = message
    for pattern, replacement in replacements.items():
        if replacement:  # Only replace if we have data
            result = re.sub(pattern, replacement, result)

    return result


def _too_soon_to_nudge(deal) -> bool:
    """Wait ``unanswered_count * MIN_DAYS_PER_UNANSWERED`` days between nudges."""
    message_collection = get_mongodb_collection("chat_messages")
    if message_collection is None:
        return False

    # Get all messages for this deal, sorted by creation_date descending
    messages = list(message_collection.find(
        {"deal_id": deal._id},
        sort=[("creation_date", -1)]
    ))

    if not messages:
        return False

    last = messages[0]
    if not last.get("is_outgoing", False):
        return False

    # Find last reply (incoming message)
    last_reply = None
    for msg in messages:
        if not msg.get("is_outgoing", False):
            last_reply = msg
            break

    # Count nudges (outgoing messages after last reply)
    if last_reply:
        last_reply_date = last_reply.get("creation_date")
        nudges = [m for m in messages if m.get("is_outgoing", False) and m.get("creation_date", datetime.min.replace(tzinfo=timezone.utc)) > last_reply_date]
    else:
        nudges = [m for m in messages if m.get("is_outgoing", False)]

    required = timedelta(days=len(nudges) * MIN_DAYS_PER_UNANSWERED)
    now = datetime.now(timezone.utc)
    last_creation_date = last.get("creation_date", now)
    return now - last_creation_date < required


def _connected_deals(campaign):
    """Open, non-disqualified CONNECTED deals in *campaign*, oldest first."""
    deal_collection = get_mongodb_collection("deals")
    lead_collection = get_mongodb_collection("leads")
    if deal_collection is None or lead_collection is None:
        return []

    # Find all CONNECTED deals for this campaign
    campaign_id = campaign._id if hasattr(campaign, '_id') else str(campaign)
    deal_docs = list(deal_collection.find(
        {
            "campaign_id": campaign_id,
            "state": models.Deal.DealState.CONNECTED,
            "outcome": "",
        },
        sort=[("creation_date", 1)]  # Oldest first (use creation_date since update_date doesn't exist yet)
    ))

    # Filter out deals with disqualified leads
    valid_deals = []
    for deal_doc in deal_docs:
        lead_id = deal_doc.get("lead_id")
        if lead_id:
            lead_doc = lead_collection.find_one({"_id": lead_id})
            if lead_doc and not lead_doc.get("disqualified", False):
                valid_deals.append(models.Deal.from_dict(deal_doc))

    return valid_deals


def _next_followup_deal(campaign):
    """Oldest CONNECTED deal in *campaign* not on a nudge cooldown."""
    for deal in _connected_deals(campaign):
        if not _too_soon_to_nudge(deal):
            return deal
    return None


def handle_follow_up(task, session, qualifiers):
    from openoutreach.mongodb.models import Lead
    from openoutreach.linkedin.models import ActionLog

    campaign = session.campaign

    # Check if ghost mode is active for this campaign
    # Note: Ghost mode is disabled, skipping for now
    # ghost_campaign = campaign.ghost_campaigns.filter(is_active=True).first()
    # if ghost_campaign: ...

    # Smart rate limiting check
    if not smart_can_execute(
        session.linkedin_profile, ActionLog.ActionType.FOLLOW_UP, campaign
    ):
        remaining = smart_get_remaining(
            session.linkedin_profile, ActionLog.ActionType.FOLLOW_UP, campaign
        )
        logger.info(
            "[%s] follow_up: smart rate limit reached (remaining: %d) — slot skipped",
            campaign,
            remaining,
        )
        return

    deal = _next_followup_deal(campaign)
    if deal is None:
        connected = len(_connected_deals(campaign))
        if connected:
            logger.info(
                "[%s] follow_up: %d connected lead(s), all within nudge cooldown — nothing due",
                campaign,
                connected,
            )
        else:
            logger.info(
                "[%s] follow_up: no connected leads yet — nobody to follow up", campaign
            )
        return

    lead = Lead.get(deal.lead_id)
    if not lead:
        logger.warning("[%s] follow_up: Lead not found for deal %s — skipped", campaign, deal._id)
        return

    public_id = lead.public_identifier
    logger.info(
        "[%s] follow_up %s",
        campaign,
        public_id,
    )

    materialize_profile_summary_if_missing(deal, session)
    decision = run_follow_up_agent(session, deal)

    profile = _build_send_profile(deal)

    if decision.action == "send_message":
        message = decision.message or ""
        # Replace any placeholders the LLM may have generated
        message = _replace_placeholders(message, deal)
        logger.info("[%s] follow_up message for %s: %s", campaign, public_id, message)
        sent = send_raw_message(session, profile, message)
        if not sent:
            from openoutreach.crm.models import DealState
            set_profile_state(session, public_id, DealState.QUALIFIED)
            logger.warning(
                "follow_up for %s: send failed — moving to QUALIFIED for re-connection",
                public_id,
            )
            return
        # Record action with smart rate limiter
        smart_record_action(
            session.linkedin_profile, ActionLog.ActionType.FOLLOW_UP, campaign
        )
        # Also record in ActionLog with details
        lead_name = ""
        try:
            prof = lead.get_profile(session)
            if prof and "profile" in prof:
                first = prof["profile"].get("firstName", "")
                last = prof["profile"].get("lastName", "")
                lead_name = f"{first} {last}".strip()
        except Exception:
            pass
        if not lead_name:
            lead_name = lead.public_identifier

        session.linkedin_profile.record_action(
            ActionLog.ActionType.FOLLOW_UP,
            session.campaign,
            details={
                "lead_name": lead_name,
                "public_identifier": public_id,
                "message_preview": message[:100] if message else "",
            },
        )
        # Persist the outgoing message locally and bump update_date so the
        # next slot's eligibility query respects the cooldown and moves
        # this deal to the back of the queue.
        from openoutreach.linkedin.db.chat import sync_conversation

        try:
            sync_conversation(session, public_id)
        except Exception:
            logger.exception("post-send sync failed for %s (best-effort)", public_id)
        deal.save()

    elif decision.action == "mark_completed":
        from openoutreach.crm.models import DealState
        outcome = decision.outcome or ""
        set_profile_state(
            session, public_id, DealState.COMPLETED, outcome=outcome
        )
        logger.info(
            "[%s] follow_up completed for %s: outcome=%s", campaign, public_id, outcome
        )

    elif decision.action == "wait":
        # Bump creation_date (used for sorting) so the eligibility query cycles to a different deal
        # next time; this deal returns to the front only after others are touched.
        deal.save()

    # State Machine Integration - Execute state machine if campaign has one
    # Note: State machine is disabled feature, skipping for now
    # _try_execute_state_machine(deal, session)


# Re-imports needed for type hints (local import avoids circular imports)
from openoutreach.core.db.deals import set_profile_state
from openoutreach.core.db.summaries import materialize_profile_summary_if_missing
from linkedin_cli.actions.message import send_raw_message
from openoutreach.core.agents.follow_up import run_follow_up_agent
