# openoutreach/whatsapp/tasks/send_message.py
"""WhatsApp initial outreach handler."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from openoutreach.mongodb.connection import get_mongodb_collection

logger = logging.getLogger(__name__)


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

        message_template = (
            campaign.channel_settings.get("whatsapp", {}).get("message_template", "")
            if campaign.channel_settings else ""
        )
        if not message_template:
            logger.warning("WA send_message [%s]: no message_template in channel_settings", campaign)
            return

        success = wa_session.send_message(lead.phone, message_template)
        if not success:
            logger.warning(
                "WA send_message [%s]: send failed for lead %s", campaign, lead.phone
            )
            return

        now = datetime.now(timezone.utc)

        # Advance deal to PENDING
        deal.state = Deal.DealState.PENDING
        deal.last_outgoing_at = now
        deal.save()

        # Save ChatMessage
        from openoutreach.mongodb.models_extended import ChatMessage
        ChatMessage(
            deal_id=str(deal._id),
            content=message_template,
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
            details={
                "deal_id": str(deal._id),
                "lead_id": str(lead._id),
                "phone": lead.phone,
                "message_preview": message_template[:100],
            },
        ).save()

        logger.info("WA send_message [%s]: sent to %s", campaign, lead.phone)
        return

    logger.info("WA send_message [%s]: all eligible leads already messaged", campaign)
