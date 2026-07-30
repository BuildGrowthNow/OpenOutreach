# openoutreach/linkedin/tasks/follow_up.py
"""Follow-up task — runs the agentic follow-up for one eligible CONNECTED deal."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from openoutreach.mongodb import models
from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.linkedin.services.smart_rate_limits import (
    smart_can_execute,
    smart_record_action,
    smart_get_remaining,
)
from openoutreach.core.db.deals import set_profile_state
from openoutreach.core.db.summaries import materialize_profile_summary_if_missing
from linkedin_cli.actions.message import send_raw_message
from openoutreach.core.agents.follow_up import run_follow_up_agent

logger = logging.getLogger(__name__)

# Required silence between nudges scales with unanswered count:
# 1 unanswered → 3d, 2 → 6d, 3 → 9d. Skips the LLM call while open.
MIN_DAYS_PER_UNANSWERED = 3

# In-memory post-send guard: maps deal_id → sent_at. Prevents a second queued
# follow_up task from firing before LinkedIn's API propagates the just-sent
# message (DB sync has a propagation delay of ~10-30s).
_last_send_times: dict[str, datetime] = {}
_IN_MEMORY_LOCK_SECONDS = 300  # 5 minutes

# If the most recent message (in either direction) is older than this and
# no outgoing message has ever been sent, the conversation is treated as
# stale — skip it rather than cold-replying to an ancient inbound message.
STALE_CONVERSATION_DAYS = 30


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
    """Return True if we should skip this deal now.

    Guards:
    1. Persistent post-send lock (deal.last_outgoing_at): after a successful
       send this field is stamped immediately — before sync_conversation —
       so it survives LinkedIn API propagation delay and daemon restarts.
       Required minimum cooldown = unanswered_count * MIN_DAYS_PER_UNANSWERED,
       with a hard floor of _IN_MEMORY_LOCK_SECONDS to prevent same-minute
       double-sends when the nudge count is 0.
    2. In-memory post-send lock: belt-and-suspenders for the first 5 minutes.
    3. Stale conversation: last message (either direction) older than
       STALE_CONVERSATION_DAYS with no known outgoing record.
    4. DB nudge cooldown: count outgoing messages since last reply and enforce
       MIN_DAYS_PER_UNANSWERED * nudge_count days of silence.
    """
    def _aware(dt):
        if dt is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    deal_id = str(deal._id)

    # Guard 1: persistent field — survives restarts, set before sync_conversation
    last_out = _aware(deal.last_outgoing_at) if deal.last_outgoing_at else None
    if last_out is not None and last_out > datetime.min.replace(tzinfo=timezone.utc):
        seconds_since = (now - last_out).total_seconds()
        if seconds_since < _IN_MEMORY_LOCK_SECONDS:
            logger.debug(
                "deal %s: persistent post-send lock (%ds ago) — skip",
                deal_id, int(seconds_since),
            )
            return True

    # Guard 2: in-memory lock (belt-and-suspenders)
    sent_at = _last_send_times.get(deal_id)
    if sent_at is not None:
        seconds_since = (now - sent_at).total_seconds()
        if seconds_since < _IN_MEMORY_LOCK_SECONDS:
            logger.debug(
                "deal %s: in-memory post-send lock (%ds ago) — skip",
                deal_id, int(seconds_since),
            )
            return True
        del _last_send_times[deal_id]

    message_collection = get_mongodb_collection("chat_messages")
    if message_collection is None:
        return False

    # Load messages sorted newest-first
    messages = list(message_collection.find(
        {"deal_id": deal._id},
        sort=[("creation_date", -1)]
    ))

    if not messages:
        # No synced messages yet; fall back to persistent field for cooldown check
        if last_out is not None:
            required = timedelta(days=MIN_DAYS_PER_UNANSWERED)
            return (now - last_out) < required
        return False

    last = messages[0]
    last_date = _aware(last.get("creation_date"))

    # Guard 3: stale conversation
    age_days = (now - last_date).days
    if age_days >= STALE_CONVERSATION_DAYS:
        logger.info(
            "deal %s: stale conversation (%dd since last message) — skip",
            deal._id, age_days,
        )
        return True

    # If the last message is incoming, no nudge cooldown applies
    if not last.get("is_outgoing", False):
        return False

    # Guard 4: post-send DB lock (<60s) — guards against racing tasks before API propagation
    seconds_since_last_outgoing = (now - last_date).total_seconds()
    if seconds_since_last_outgoing < 60:
        logger.debug(
            "deal %s: post-send lock (last outgoing %ds ago) — skip",
            deal._id, int(seconds_since_last_outgoing),
        )
        return True

    # Count nudges (outgoing messages since last incoming reply)
    last_reply = next((m for m in messages if not m.get("is_outgoing", False)), None)
    if last_reply:
        last_reply_date = _aware(last_reply.get("creation_date"))
        nudges = [
            m for m in messages
            if m.get("is_outgoing", False)
            and _aware(m.get("creation_date")) > last_reply_date
        ]
    else:
        nudges = [m for m in messages if m.get("is_outgoing", False)]

    required = timedelta(days=max(1, len(nudges)) * MIN_DAYS_PER_UNANSWERED)
    return now - last_date < required


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
        # Strip em-dashes — the LLM occasionally ignores the hard constraint
        message = message.replace("—", "-").replace("–", "-")
        logger.info("[%s] follow_up message for %s: %s", campaign, public_id, message)
        sent = send_raw_message(session, profile, message)
        if not sent:
            logger.warning(
                "follow_up for %s: send failed — keeping CONNECTED, will retry next cycle",
                public_id,
            )
            return
        now = datetime.now(timezone.utc)
        # Stamp in-memory lock so back-to-back queued tasks skip this deal
        # before LinkedIn's API propagates the just-sent message to the DB.
        _last_send_times[str(deal._id)] = now
        # Persist last_outgoing_at immediately — before any post-send logging
        # or sync that could throw, so the guard survives exceptions and restarts.
        deal.last_outgoing_at = now
        deal.creation_date = now
        deal.save(update_fields=["last_outgoing_at", "creation_date"])
        # Record action with smart rate limiter
        smart_record_action(
            session.linkedin_profile, ActionLog.ActionType.FOLLOW_UP, campaign
        )
        # Also record in ActionLog with details
        lead_name = ""
        if lead.cached_profile and isinstance(lead.cached_profile, dict):
            first = lead.cached_profile.get("first_name", "")
            last = lead.cached_profile.get("last_name", "")
            lead_name = f"{first} {last}".strip()
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
        from openoutreach.linkedin.db.chat import sync_conversation

        try:
            sync_conversation(session, public_id)
        except Exception:
            logger.exception("post-send sync failed for %s (best-effort)", public_id)

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
        # Bump creation_date so the eligibility query cycles to a different deal next time.
        deal.creation_date = datetime.now(timezone.utc)
        deal.save(update_fields=["creation_date"])

    # State Machine Integration - Execute state machine if campaign has one
    # Note: State machine is disabled feature, skipping for now
    # _try_execute_state_machine(deal, session)


