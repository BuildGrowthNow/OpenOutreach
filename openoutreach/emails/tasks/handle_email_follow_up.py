# openoutreach/emails/tasks/handle_email_follow_up.py
"""Email follow-up task handler.

Picks the next EMAIL_QUEUED deal for a campaign, selects a mailbox,
sends the email, and advances Deal state to EMAIL_SENT.

Hard bounces (SMTP 550) permanently suppress the lead's email address
and set Deal state to EMAIL_BOUNCED.
"""

from __future__ import annotations

import logging
import smtplib
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def handle_email_follow_up(task, user_id: str, campaign) -> None:
    """Send one email for the next eligible EMAIL_QUEUED deal in *campaign*.

    Args:
        task:      Task object (has .payload with campaign_id)
        user_id:   Owner's user_id — used to select the right mailbox pool
        campaign:  Campaign model instance (already validated as ACTIVE)
    """
    from openoutreach.mongodb.connection import get_mongodb_collection
    from openoutreach.mongodb.models import Deal, Lead
    from openoutreach.emails.models import Mailbox
    from openoutreach.emails.sender import send_email

    deals_col = get_mongodb_collection("deals")
    leads_col = get_mongodb_collection("leads")
    if deals_col is None or leads_col is None:
        logger.warning("email_follow_up: MongoDB collections not available")
        return

    # Find next EMAIL_QUEUED deal that has an api_email
    deal_doc = deals_col.find_one(
        {
            "campaign_id": campaign.pk,
            "state": "email_queued",
            "active_channel": "email",
        },
        sort=[("creation_date", 1)],
    )
    if deal_doc is None:
        logger.debug("email_follow_up [%s]: no EMAIL_QUEUED deals", campaign.pk)
        return

    deal = Deal.from_dict(deal_doc)
    lead = Lead.get(deal.lead_id)
    if not lead:
        logger.warning("email_follow_up: lead %s not found for deal %s", deal.lead_id, deal._id)
        return

    if not lead.api_email:
        logger.debug("email_follow_up: lead %s has no api_email — skipping", lead._id)
        return

    if lead.email_unsubscribed:
        logger.info("email_follow_up: lead %s is unsubscribed — skipping", lead._id)
        return

    # Pick the least-loaded mailbox that still has daily headroom
    mailbox = Mailbox.objects.least_loaded_under_cap(user_id=user_id)
    if mailbox is None:
        logger.info(
            "email_follow_up [%s]: all mailboxes at daily cap — deferring", campaign.pk
        )
        return

    subject, body = _generate_email_stub(deal, lead, deal.email_sequence_step)

    try:
        message_id = send_email(
            mailbox,
            lead.api_email,
            subject,
            body,
            in_reply_to=deal.email_message_id,
        )
    except smtplib.SMTPRecipientsRefused as exc:
        # Hard bounce (550) — suppress email permanently
        code = _extract_smtp_code(exc)
        if code == 550:
            _mark_bounced(deal, lead, deals_col, leads_col)
            logger.warning(
                "email_follow_up: hard bounce 550 for %s — EMAIL_BOUNCED + unsubscribed",
                lead.api_email,
            )
            return
        raise

    # Success — advance deal state
    now = datetime.now(timezone.utc)
    deals_col.update_one(
        {"_id": deal._id},
        {
            "$set": {
                "state": "email_sent",
                "mailbox_id": mailbox.pk,
                "email_sent_at": now,
                "email_message_id": message_id,
                "email_sequence_step": deal.email_sequence_step + 1,
            }
        },
    )
    logger.info(
        "email_follow_up [%s]: sent step %d to %s via %s",
        campaign.pk, deal.email_sequence_step, lead.api_email, mailbox.from_address,
    )


def _generate_email_stub(deal, lead, step: int) -> tuple[str, str]:
    """Phase 2 placeholder — Phase 3 wires LLM here."""
    name = lead.full_name or lead.public_identifier or "there"
    if step == 0:
        subject = f"Quick question, {name}"
        body = (
            f"Hi {name},\n\n"
            "I came across your profile and wanted to reach out briefly.\n\n"
            "Would you be open to a quick chat?\n\n"
            "Best regards"
        )
    else:
        subject = f"Following up, {name}"
        body = (
            f"Hi {name},\n\n"
            "Just following up on my previous message.\n\n"
            "Happy to connect if you have a moment.\n\n"
            "Best regards"
        )
    return subject, body


def _extract_smtp_code(exc: smtplib.SMTPRecipientsRefused) -> int:
    """Return the SMTP status code from a SMTPRecipientsRefused exception."""
    for _addr, (code, _msg) in exc.recipients.items():
        return code
    return 0


def _mark_bounced(deal, lead, deals_col, leads_col) -> None:
    deals_col.update_one(
        {"_id": deal._id},
        {"$set": {"state": "email_bounced"}},
    )
    leads_col.update_one(
        {"_id": lead._id},
        {"$set": {"email_unsubscribed": True}},
    )
