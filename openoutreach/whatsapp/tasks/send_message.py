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


def handle_whatsapp_message(task, wa_session, qualifiers):  # noqa: ARG001
    """Send initial WhatsApp outreach to one eligible QUALIFIED lead.

    task.payload = {"campaign_id": <id>}
    Picks the oldest QUALIFIED deal where active_channel=="whatsapp",
    lead.phone is set, and no whatsapp_message ActionLog exists yet.
    """
    from openoutreach.mongodb.models import Campaign, Deal, Lead
    from openoutreach.linkedin.models import ActionLog

    campaign_id = task.payload["campaign_id"]
    campaign = Campaign.get(campaign_id)
    if not campaign:
        logger.warning("WA send_message: campaign %s not found", campaign_id)
        return

    deals_col = get_mongodb_collection("deals")
    if deals_col is None:
        return

    # Find QUALIFIED WA deals oldest-first
    deal_docs = list(deals_col.find(
        {
            "campaign_id": campaign_id,
            "state": Deal.DealState.QUALIFIED,
            "active_channel": "whatsapp",
        },
        sort=[("creation_date", 1)],
        limit=50,
    ))

    if not deal_docs:
        logger.info("WA send_message [%s]: no eligible QUALIFIED WA deals", campaign)
        return

    action_logs_col = get_mongodb_collection("action_logs")

    for deal_doc in deal_docs:
        deal = Deal.from_dict(deal_doc)
        lead = Lead.get(deal.lead_id)
        if not lead or not lead.phone:
            continue

        # Skip if already messaged on WhatsApp
        if action_logs_col is not None:
            already_sent = action_logs_col.count_documents({
                "campaign_id": campaign_id,
                "action_type": "whatsapp_message",
                "details.deal_id": str(deal._id),
            }, limit=1)
            if already_sent:
                continue

        # Safety net: validate.py runs pre-flight before reconcile so this branch
        # is rarely hit, but catches any that slipped through (e.g. first 5-min window).
        if lead.phone_on_whatsapp is False:
            deal.state = Deal.DealState.FAILED
            deal.reason = "phone_not_on_whatsapp"
            deal.save(update_fields=["state", "reason"])
            logger.info("WA send_message [%s]: %s not on WA — skipping", campaign, lead.phone)
            continue

        message_template = (
            campaign.channel_settings.get("whatsapp", {}).get("message_template", "")
            if campaign.channel_settings else ""
        )
        if not message_template:
            logger.warning("WA send_message [%s]: no message_template in channel_settings", campaign)
            return

        message = _substitute_template(message_template, lead)
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
                    "WA send_message: profile %s appears BANNED — marking and halting",
                    wa_session.wa_profile,
                )
                return
            _handle_send_failure(deal, banned=False)
            if deal.state == Deal.DealState.FAILED:
                logger.warning(
                    "WA send_message [%s]: deal %s exhausted after %d attempts — marking FAILED",
                    campaign, deal._id, deal.connect_attempts,
                )
            return

        now = datetime.now(timezone.utc)

        # Advance deal to PENDING
        deal.state = Deal.DealState.PENDING
        deal.last_outgoing_at = now
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
            },
        ).save()

        logger.info("WA send_message [%s]: sent to %s", campaign, lead.phone)
        return

    logger.info("WA send_message [%s]: all eligible leads already messaged", campaign)
