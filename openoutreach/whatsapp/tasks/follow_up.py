# openoutreach/whatsapp/tasks/follow_up.py
"""WhatsApp follow-up handler — reuses the LLM follow-up agent."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from openoutreach.mongodb.connection import get_mongodb_collection

logger = logging.getLogger(__name__)


def _wa_is_active_now(config) -> bool:
    """Return True if current time is within WA-specific active hours (when enabled)."""
    if not getattr(config, "wa_enable_active_hours", False):
        return True
    from datetime import datetime, timezone
    import pytz
    tz_name = getattr(config, "active_timezone", "UTC") or "UTC"
    try:
        tz = pytz.timezone(tz_name)
    except pytz.exceptions.UnknownTimeZoneError:
        logger.warning("_wa_is_active_now: unknown timezone %r — defaulting to UTC", tz_name)
        tz = pytz.utc
    now = datetime.now(timezone.utc).astimezone(tz)
    start = getattr(config, "wa_active_start_hour", 8)
    end = getattr(config, "wa_active_end_hour", 21)
    wa_days = getattr(config, "wa_active_days", None)
    if isinstance(wa_days, list):
        active_days = wa_days
    elif isinstance(wa_days, str):
        active_days = [int(d) for d in wa_days.split(",") if d.strip().isdigit()]
    else:
        active_days = list(range(1, 8))
    isoweekday = now.isoweekday()  # 1=Monday … 7=Sunday
    if active_days and isoweekday not in active_days:
        return False
    return start <= now.hour < end


def handle_whatsapp_follow_up(task, wa_session, qualifiers):  # noqa: ARG001
    """Run AI follow-up for one eligible CONNECTED WhatsApp deal.

    task.payload = {"campaign_id": <id>}
    Reuses core follow-up agent logic but skips LinkedIn sync.
    """
    from openoutreach.mongodb.models import Campaign, Deal, Lead
    from openoutreach.mongodb.models_extended import ChatMessage
    from openoutreach.linkedin.models import ActionLog
    from openoutreach.core.agents.follow_up import (
        _render_system_prompt,
        _load_recent_messages,
        FollowUpDecision,
    )
    from openoutreach.core.llm import get_llm_model, run_agent_sync
    from pydantic_ai import Agent

    from openoutreach.mongodb.models import SiteConfig
    wa_profile = wa_session.wa_profile
    config = SiteConfig.load(user_id=wa_profile.user_id)
    if not _wa_is_active_now(config):
        logger.debug("WA follow_up: outside WA active hours — skipping")
        return

    campaign_id = task.payload["campaign_id"]
    campaign = Campaign.get(campaign_id)
    if not campaign:
        logger.warning("WA follow_up: campaign %s not found", campaign_id)
        return

    deals_col = get_mongodb_collection("deals")
    if deals_col is None:
        return

    deal_doc = deals_col.find_one(
        {
            "campaign_id": campaign_id,
            "state": Deal.DealState.CONNECTED,
            "active_channel": "whatsapp",
            "outcome": {"$in": ["", None]},
        },
        sort=[("last_outgoing_at", 1), ("follow_up_cycled_at", 1)],
    )
    if not deal_doc:
        logger.info("WA follow_up [%s]: no eligible CONNECTED WA deals", campaign)
        return

    deal = Deal.from_dict(deal_doc)
    lead = Lead.get(deal.lead_id)
    if not lead or not lead.phone:
        logger.warning("WA follow_up: lead %s has no phone", deal.lead_id)
        return

    deal.refresh_from_db(fields=["chat_summary", "profile_summary"])

    # Build minimal duck-typed session for _render_system_prompt
    wa_profile = wa_session.wa_profile

    class _MinimalProfile:
        def __init__(self):
            self.user_id = wa_profile.user_id
            self.linkedin_username = wa_profile.phone_number or ""

    class _MinimalSession:
        def __init__(self):
            self.user_id = wa_profile.user_id
            self.linkedin_profile = _MinimalProfile()
            self.self_profile = {
                "first_name": wa_profile.display_name or "",
                "last_name": "",
            }

    session_like = _MinimalSession()
    recent = _load_recent_messages(deal)
    system_prompt = _render_system_prompt(session_like, deal, recent, channel="whatsapp")

    agent = Agent(
        get_llm_model(user_id=session_like.user_id),
        output_type=FollowUpDecision,
        model_settings={"temperature": 0.7, "timeout": 60},
    )
    decision = run_agent_sync(agent.run(system_prompt)).output
    if decision is None:
        logger.warning("WA follow_up: LLM returned None for deal %s", deal._id)
        return

    logger.info("WA follow_up [%s]: decision=%s", campaign, decision.action)

    if decision.action == "send_message":
        message = (decision.message or "").replace("—", "-").replace("–", "-")
        if not message:
            logger.warning("WA follow_up: empty message for deal %s", deal._id)
            return

        now = datetime.now(timezone.utc)
        deal.last_outgoing_at = now
        deal.follow_up_cycled_at = now
        deal.save(update_fields=["last_outgoing_at", "follow_up_cycled_at"])

        success = wa_session.send_message(lead.phone, message)
        if not success:
            logger.warning("WA follow_up: send failed for %s", lead.phone)
            banned = wa_session.detect_ban()
            if banned:
                from openoutreach.whatsapp.models.profile import STATUS_BANNED
                wa_session.wa_profile.status = STATUS_BANNED
                wa_session.wa_profile.save(update_fields=["status"])
                logger.error(
                    "WA follow_up: profile %s appears BANNED — marking and halting",
                    wa_session.wa_profile,
                )
                return
            deal.last_outgoing_at = None
            deal.save(update_fields=["last_outgoing_at"])
            return

        ChatMessage(
            deal_id=str(deal._id),
            content=message,
            is_outgoing=True,
            creation_date=now,
            user_id=deal.user_id,
            channel="whatsapp",
        ).save()

        ActionLog(
            linkedin_profile_id=wa_profile._id,
            campaign_id=campaign_id,
            action_type="whatsapp_follow_up",
            user_id=deal.user_id,
            details={
                "deal_id": str(deal._id),
                "phone": lead.phone,
                "message_preview": message[:100],
            },
        ).save()

    elif decision.action == "mark_completed":
        from openoutreach.crm.models import DealState
        outcome = decision.outcome or ""
        deal.state = DealState.COMPLETED.value
        deal.outcome = outcome
        deal.save()
        logger.info("WA follow_up [%s]: completed deal %s outcome=%s", campaign, deal._id, outcome)

    elif decision.action == "wait":
        deal.follow_up_cycled_at = datetime.now(timezone.utc)
        deal.save(update_fields=["follow_up_cycled_at"])
