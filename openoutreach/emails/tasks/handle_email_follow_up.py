# openoutreach/emails/tasks/handle_email_follow_up.py
"""Email follow-up task handler.

Handles all three sequence steps (0=cold, 1=follow-up 1, 2=follow-up 2) in
a single task type. Step timing is enforced here:
  - Step 0: any EMAIL_QUEUED deal with api_email set
  - Step 1: EMAIL_SENT/EMAIL_OPENED, sequence_step==1, sent_at + day1 days ago
  - Step 2: EMAIL_SENT/EMAIL_OPENED, sequence_step==2, sent_at + day2 days ago

Stops sending when deal enters EMAIL_REPLIED, EMAIL_BOUNCED, or sequence_step >= 3.
SMTP failure handling is policy-driven via delivery_policy.classify():
  - Hard bounce (550-554) → EMAIL_BOUNCED + suppress lead email permanently
  - Transient (4xx, connection, timeout) → return silently; scheduler replans
  - Auth failure (534/535) → log ERROR; return silently (needs operator fix)
  - Unexpected → re-raise for daemon to mark task FAILED
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from openoutreach.emails.delivery_policy import SmtpOutcome, classify

logger = logging.getLogger(__name__)

MAX_SEQUENCE_STEPS = 3


def _write_chat_message(deal, user_id: str, subject: str, body: str, sent_at: datetime) -> None:
    """Persist the sent email as a ChatMessage so it appears in the Messages view."""
    try:
        from openoutreach.mongodb.models_extended import ChatMessage

        content = f"Subject: {subject}\n\n{body}" if subject else body
        msg = ChatMessage(
            deal_id=str(deal._id),
            content=content,
            is_outgoing=True,
            channel="email",
            user_id=user_id,
            creation_date=sent_at,
        )
        msg.save()
    except Exception as exc:
        logger.warning("email_follow_up: failed to write ChatMessage for deal %s: %s", deal._id, exc)


def handle_email_follow_up(task, user_id: str, campaign) -> None:
    """Send one email for the next eligible deal in *campaign*.

    Args:
        task:      Task object (has .payload with campaign_id)
        user_id:   Owner's user_id — used to select the right mailbox pool
        campaign:  Campaign model instance (already validated as ACTIVE)
    """
    from openoutreach.mongodb.connection import get_mongodb_collection
    from openoutreach.mongodb.models import Deal, Lead, SiteConfig
    from openoutreach.emails.models import Mailbox
    from openoutreach.emails.sender import send_email

    deals_col = get_mongodb_collection("deals")
    leads_col = get_mongodb_collection("leads")
    if deals_col is None or leads_col is None:
        logger.warning("email_follow_up: MongoDB collections not available")
        return

    config = SiteConfig.load(user_id=user_id)
    now = datetime.now(timezone.utc)
    day1_cutoff = now - timedelta(days=config.email_followup_day1)
    day2_cutoff = now - timedelta(days=config.email_followup_day2)

    # Find the earliest-created eligible deal across all steps
    deal_doc = deals_col.find_one(
        {
            "campaign_id": campaign.pk,
            "$or": [
                {"state": "email_queued", "active_channel": "email"},
                {
                    "state": {"$in": ["email_sent", "email_opened"]},
                    "email_sequence_step": 1,
                    "email_sent_at": {"$lte": day1_cutoff},
                },
                {
                    "state": {"$in": ["email_sent", "email_opened"]},
                    "email_sequence_step": 2,
                    "email_sent_at": {"$lte": day2_cutoff},
                },
            ],
        },
        sort=[("creation_date", 1)],
    )
    if deal_doc is None:
        logger.debug("email_follow_up [%s]: no eligible deals", campaign.pk)
        return

    deal = Deal.from_dict(deal_doc)

    # Skip silently if deal advanced past expected state since task was created
    if deal.email_sequence_step >= MAX_SEQUENCE_STEPS:
        logger.debug(
            "email_follow_up: deal %s already at step %d — skipping",
            deal._id, deal.email_sequence_step,
        )
        return

    if deal.state in ("email_replied", "email_bounced"):
        logger.info(
            "email_follow_up: deal %s in terminal email state %r — skipping",
            deal._id, deal.state,
        )
        return

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

    mailbox = Mailbox.objects.least_loaded_under_cap(user_id=user_id)
    if mailbox is None:
        logger.info(
            "email_follow_up [%s]: all mailboxes at daily cap — deferring", campaign.pk
        )
        return

    from openoutreach.emails.email_agent import generate_email
    subject, body = generate_email(deal, user_id, campaign, deal.email_sequence_step)

    try:
        message_id = send_email(
            mailbox,
            lead.api_email,
            subject,
            body,
            in_reply_to=deal.email_message_id,
            deal_id=str(deal._id),
            campaign_id=str(campaign.pk),
        )
    except Exception as exc:
        outcome = classify(exc)

        if outcome == SmtpOutcome.BOUNCE_DEAL:
            _mark_bounced(deal, lead, deals_col, leads_col)
            logger.warning(
                "email_follow_up: hard bounce for %s (%s) — EMAIL_BOUNCED + suppressed",
                lead.api_email, exc,
            )
            return

        if outcome == SmtpOutcome.RETRY_LATER:
            logger.info(
                "email_follow_up: transient failure for %s (%s) — will retry next cycle",
                lead.api_email, exc,
            )
            return

        if outcome == SmtpOutcome.PAUSE_MAILBOX:
            logger.error(
                "email_follow_up: auth/credentials failure on mailbox %s (%s) — "
                "check SMTP password; no further sends attempted until fixed",
                mailbox.from_address, exc,
            )
            return

        raise  # SmtpOutcome.RAISE — daemon marks task FAILED

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

    _write_chat_message(deal, user_id, subject, body, now)

    logger.info(
        "email_follow_up [%s]: sent step %d to %s via %s",
        campaign.pk, deal.email_sequence_step, lead.api_email, mailbox.from_address,
    )


def _mark_bounced(deal, lead, deals_col, leads_col) -> None:
    deals_col.update_one(
        {"_id": deal._id},
        {"$set": {"state": "email_bounced"}},
    )
    leads_col.update_one(
        {"_id": lead._id},
        {"$set": {"email_unsubscribed": True}},
    )
