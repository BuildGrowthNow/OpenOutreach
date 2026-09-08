# openoutreach/whatsapp/tasks/send_message.py
"""WhatsApp initial outreach handler."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from openoutreach.mongodb.connection import get_mongodb_collection

logger = logging.getLogger(__name__)

MAX_WA_MESSAGE_ATTEMPTS = 3


def _handle_send_failure(deal, *, banned: bool) -> None:
    if banned:
        return
    from openoutreach.mongodb.models import Deal
    deal.connect_attempts += 1
    if deal.connect_attempts >= MAX_WA_MESSAGE_ATTEMPTS:
        deal.state = Deal.DealState.FAILED
        deal.reason = f"WA send failed after {deal.connect_attempts} attempts"
    deal.save()


def _substitute_template(template: str, lead) -> str:
    """Replace {name}, {first_name}, {last_name}, {company} placeholders."""
    full_name = (getattr(lead, "full_name", "") or "").strip()
    parts = full_name.split(None, 1)
    first = parts[0] if parts else ""
    last = parts[1] if len(parts) > 1 else ""
    company = getattr(lead, "company", "") or ""
    return (
        template
        .replace("{name}", full_name or first or "there")
        .replace("{first_name}", first or "there")
        .replace("{last_name}", last)
        .replace("{company}", company)
    )


def _generate_node_message(prompt: str, lead, campaign, user_id: str) -> str:
    """Generate a WhatsApp message from a sequence-node instruction."""
    from pydantic import BaseModel, Field
    from pydantic_ai import Agent
    from openoutreach.core.llm import get_llm_model, run_agent_sync

    class MessageOutput(BaseModel):
        message: str = Field(min_length=1, max_length=4000)

    context = (
        f"Lead: {getattr(lead, 'full_name', '') or 'there'}\n"
        f"Company: {getattr(lead, 'company', '') or 'unknown'}\n"
        f"Offer: {campaign.product_pitch or ''}\n"
        f"Campaign objective: {campaign.campaign_objective or ''}\n\n"
        f"Node instruction: {prompt}\n"
        "Write one concise WhatsApp message. Return only the message."
    )
    agent = Agent(get_llm_model(user_id=user_id), output_type=MessageOutput, model_settings={"temperature": 0.7, "timeout": 60})
    result = run_agent_sync(agent.run(context)).output
    if result is None or not result.message.strip():
        raise RuntimeError("LLM returned an empty WhatsApp message")
    return result.message.strip()


def _lead_active_in_other_campaign(lead_id: str, current_campaign_id: str) -> bool:
    """Return True if the lead has a PENDING/CONNECTED WA deal in any other campaign."""
    deals_col = get_mongodb_collection("deals")
    if deals_col is None:
        return False
    from openoutreach.mongodb.models import Deal
    return deals_col.count_documents({
        "lead_id": lead_id,
        "campaign_id": {"$ne": current_campaign_id},
        "active_channel": "whatsapp",
        "state": {"$in": [Deal.DealState.PENDING, Deal.DealState.CONNECTED]},
    }, limit=1) > 0


def _message_action_log_query(campaign_id: str, deal_id: str, step_id: str | None) -> dict:
    """Build an idempotency query for legacy and sequence WhatsApp sends."""
    query = {
        "campaign_id": campaign_id,
        "action_type": "whatsapp_message",
        "details.deal_id": deal_id,
    }
    # A sequence can deliberately contain several WhatsApp nodes.  Scope the
    # dedupe marker to its node, while preserving the old one-message-per-deal
    # behavior for legacy tasks that do not carry a step id.
    if step_id:
        query["details.step_id"] = step_id
    return query


def handle_whatsapp_message(task, wa_session, qualifiers):  # noqa: ARG001
    """Send initial WhatsApp outreach to one eligible QUALIFIED lead.

    task.payload = {"campaign_id": <id>}
    Picks the oldest QUALIFIED deal where active_channel=="whatsapp",
    lead.phone is set, and no whatsapp_message ActionLog exists yet.
    """
    from openoutreach.mongodb.models import Campaign, Deal, Lead, SiteConfig
    from openoutreach.linkedin.models import ActionLog
    from openoutreach.whatsapp.tasks.follow_up import _wa_is_active_now

    wa_profile = wa_session.wa_profile
    config = SiteConfig.load(user_id=wa_profile.user_id)
    if not _wa_is_active_now(config):
        logger.debug("WA send_message: outside WA active hours - skipping")
        return

    campaign_id = task.payload["campaign_id"]
    campaign = Campaign.get(campaign_id)
    if not campaign:
        logger.warning("WA send_message: campaign %s not found", campaign_id)
        return

    deals_col = get_mongodb_collection("deals")
    if deals_col is None:
        return

    # Find QUALIFIED WA deals oldest-first
    target_deal_id = (getattr(task, "payload", None) or {}).get("deal_id")
    eligibility = {
        "campaign_id": campaign_id,
        "state": Deal.DealState.QUALIFIED,
        "active_channel": "whatsapp",
    }
    if target_deal_id:
        # Sequence tasks must address the deal they were created for.
        eligibility["_id"] = str(target_deal_id)
        eligibility.pop("active_channel", None)
        # A sequence may switch into WhatsApp after another channel has
        # already moved the deal out of QUALIFIED.
        eligibility["state"] = {"$in": [
            Deal.DealState.QUALIFIED,
            Deal.DealState.PENDING,
            Deal.DealState.CONNECTED,
            Deal.DealState.EMAIL_SENT,
            Deal.DealState.EMAIL_OPENED,
        ]}
    deal_docs = list(deals_col.find(
        eligibility,
        sort=[("creation_date", 1)],
        limit=50,
    ))

    if not deal_docs:
        logger.info("WA send_message [%s]: no eligible QUALIFIED WA deals", campaign)
        return

    action_logs_col = get_mongodb_collection("action_logs")

    for deal_doc in deal_docs:
        deal = Deal.from_dict(deal_doc)
        target_step_id = (getattr(task, "payload", None) or {}).get("step_id")
        if target_step_id and deal_doc.get("sequence_last_step_id") == target_step_id:
            logger.info("WA send_message: sequence step %s already sent for deal %s", target_step_id, deal._id)
            continue
        lead = Lead.get(deal.lead_id)
        if not lead or not lead.phone:
            continue

        # Skip if already messaged on WhatsApp
        target_step_id = (getattr(task, "payload", None) or {}).get("step_id")
        if action_logs_col is not None:
            already_sent = action_logs_col.count_documents(
                _message_action_log_query(campaign_id, str(deal._id), target_step_id),
                limit=1,
            )
            if already_sent:
                continue

        # Cross-campaign dedup: skip if this lead is already being worked in another WA campaign.
        if _lead_active_in_other_campaign(str(lead._id), campaign_id):
            logger.debug(
                "WA send_message [%s]: lead %s active in another WA campaign - skipping",
                campaign, lead._id,
            )
            continue

        # Safety net: validate.py runs pre-flight before reconcile so this branch
        # is rarely hit, but catches any that slipped through (e.g. first 5-min window).
        if lead.phone_on_whatsapp is False:
            deal.state = Deal.DealState.FAILED
            deal.reason = "phone_not_on_whatsapp"
            deal.save(update_fields=["state", "reason"])
            logger.info("WA send_message [%s]: lead not on WA - skipping", campaign)
            continue

        target_step = next(
            (step for step in (campaign.sequence_steps or []) if step.get("id") == target_step_id),
            None,
        )
        from openoutreach.core.sequence_message import fallback_config, message_config
        payload_message = (getattr(task, "payload", None) or {}).get("message")
        node_message = message_config({"data": payload_message}) if isinstance(payload_message, dict) else message_config(target_step)
        # The task payload is the immutable contract for an in-flight lead.
        # Do not require the node to still exist in the editable campaign
        # graph: an old graph snapshot may legitimately reference it.
        is_sequence_node = bool(target_step_id)
        try:
            if is_sequence_node and node_message.get("content_mode") == "static":
                message_template = str(node_message.get("body") or "").strip()
            elif is_sequence_node and str(node_message.get("prompt") or "").strip():
                message_template = _generate_node_message(str(node_message["prompt"]), lead, campaign, wa_profile.user_id)
            else:
                message_template = (
                    campaign.channel_settings.get("whatsapp", {}).get("message_template", "")
                    if campaign.channel_settings else ""
                )
            if not message_template:
                raise ValueError("WhatsApp message is empty")
        except Exception as exc:
            mode, fallback_body = fallback_config(node_message, exc) if is_sequence_node else ("continue", "")
            if is_sequence_node and mode == "static" and fallback_body:
                message_template = fallback_body
            elif is_sequence_node and mode == "skip":
                deal.sequence_last_step_id = target_step_id
                deal.sequence_last_action_skipped_at = datetime.now(timezone.utc)
                deal.save(update_fields=["sequence_last_step_id", "sequence_last_action_skipped_at"])
                logger.warning("WA send_message: skipping node %s after generation failure", target_step_id)
                return
            elif is_sequence_node and mode == "continue":
                message_template = (campaign.channel_settings or {}).get("whatsapp", {}).get("message_template", "")
                if not message_template:
                    logger.warning("WA send_message [%s]: no fallback WhatsApp template", campaign)
                    return
            else:
                logger.warning("WA send_message [%s]: no message configured", campaign)
                return

        message = _substitute_template(message_template, lead)
        from openoutreach.emails.tracking import render_link_placeholders
        message = render_link_placeholders(
            message,
            deal_id=str(deal._id),
            campaign_id=str(campaign_id),
            lead_id=str(deal.lead_id),
            step_id=str(target_step_id or ""),
            channel="whatsapp",
        )
        success = wa_session.send_message(lead.phone, message)
        if not success:
            logger.warning(
                "WA send_message [%s]: send failed for lead %s", campaign, lead.phone
            )
            banned = wa_session.detect_ban()
            if banned:
                from openoutreach.whatsapp.models.profile import STATUS_BANNED
                wa_session.wa_profile.status = STATUS_BANNED
                wa_session.wa_profile.save(update_fields=["status"])
                logger.error(
                    "WA send_message: profile %s appears BANNED - marking and halting",
                    wa_session.wa_profile,
                )
                return
            _handle_send_failure(deal, banned=False)
            if deal.state == Deal.DealState.FAILED:
                logger.warning(
                    "WA send_message [%s]: deal %s exhausted after %d attempts - marking FAILED",
                    campaign, deal._id, deal.connect_attempts,
                )
            return

        now = datetime.now(timezone.utc)

        # Advance deal to PENDING
        deal.state = Deal.DealState.PENDING
        deal.last_outgoing_at = now
        if target_step_id:
            deal.sequence_last_step_id = target_step_id
            deal.sequence_last_message_at = now
            deal.sequence_stop_on_reply = bool(
                node_message.get("stop_on_reply", True)
                or (getattr(campaign, "safety_defaults", {}) or {}).get("stop_on_reply", False)
            )
            deal.save(update_fields=["state", "last_outgoing_at", "sequence_last_step_id", "sequence_last_message_at", "sequence_stop_on_reply"])
        else:
            deal.save(update_fields=["state", "last_outgoing_at"])

        # Save ChatMessage
        from openoutreach.mongodb.models_extended import ChatMessage
        ChatMessage(
            deal_id=str(deal._id),
            content=message,
            is_outgoing=True,
            creation_date=now,
            user_id=deal.user_id,
            channel="whatsapp",
            wa_msg_hash=ChatMessage.compute_wa_hash(str(deal._id), True, message),
        ).save()

        # Create ActionLog
        ActionLog(
            linkedin_profile_id=wa_session.wa_profile._id,
            campaign_id=campaign_id,
            action_type="whatsapp_message",
            user_id=deal.user_id,
            details={
                "deal_id": str(deal._id),
                "lead_id": str(lead._id),
                "phone": lead.phone,
                "message_preview": message[:100],
                "wa_profile_id": wa_session.wa_profile._id,
                "step_id": str(target_step_id or ""),
            },
        ).save()

        logger.info("WA send_message [%s]: message sent", campaign)
        return

    logger.info("WA send_message [%s]: all eligible leads already messaged", campaign)
