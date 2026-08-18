# openoutreach/whatsapp/tasks/follow_up.py
"""WhatsApp follow-up handler — reuses the LLM follow-up agent."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from openoutreach.mongodb.connection import get_mongodb_collection

logger = logging.getLogger(__name__)


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
            "outcome": "",
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
    system_prompt = _render_system_prompt(session_like, deal, recent)

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
