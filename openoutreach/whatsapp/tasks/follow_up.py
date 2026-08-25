# openoutreach/whatsapp/tasks/follow_up.py
"""WhatsApp follow-up handler - reuses the LLM follow-up agent."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

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
        logger.warning("_wa_is_active_now: unknown timezone %r - defaulting to UTC", tz_name)
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


# Minimum days between consecutive unanswered follow-ups (mirrors LinkedIn's MIN_DAYS_PER_UNANSWERED)
_WA_MIN_DAYS_PER_NUDGE = 2
_WA_STALE_CONVERSATION_DAYS = 30


def _next_wa_followup_deal(campaign_id: str, deals_col):
    """Find the next WA deal (CONNECTED or PENDING with first message sent) past its nudge cooldown.

    CONNECTED deals: lead replied - respond or continue conversation.
    PENDING deals where last_outgoing_at is set: first message sent, no reply yet -
      apply nudge sequence (new angle, yes/no, close-loop) before giving up.

    Mirrors LinkedIn's _next_followup_deal + _too_soon_to_nudge logic:
    - Skip if last_outgoing_at is within (nudge_count * _WA_MIN_DAYS_PER_NUDGE) days
    - Skip if conversation is stale (>30 days since any message)
    - Allow immediate follow-up if last message is inbound (lead replied)
    """
    from openoutreach.mongodb.models import Deal
    from openoutreach.mongodb.connection import get_mongodb_collection

    messages_col = get_mongodb_collection("chat_messages")

    deal_docs = list(deals_col.find(
        {
            "campaign_id": campaign_id,
            "active_channel": "whatsapp",
            "outcome": {"$in": ["", None]},
            "$or": [
                {"state": Deal.DealState.CONNECTED},
                # PENDING with first message already sent (last_outgoing_at set)
                {"state": Deal.DealState.PENDING, "last_outgoing_at": {"$ne": None}},
            ],
        },
        sort=[("last_outgoing_at", 1), ("follow_up_cycled_at", 1)],
        limit=50,
    ))

    now = datetime.now(timezone.utc)

    for deal_doc in deal_docs:
        deal_id = str(deal_doc["_id"])
        last_out = deal_doc.get("last_outgoing_at")
        if last_out and last_out.tzinfo is None:
            last_out = last_out.replace(tzinfo=timezone.utc)

        # Respect LLM-requested timing
        nfa = deal_doc.get("next_follow_up_at")
        if nfa is not None:
            if nfa.tzinfo is None:
                nfa = nfa.replace(tzinfo=timezone.utc)
            if nfa > now:
                continue

        if messages_col is None:
            if last_out and (now - last_out).days < _WA_MIN_DAYS_PER_NUDGE:
                continue
            return deal_doc

        last_msg = messages_col.find_one(
            {"deal_id": deal_id, "channel": "whatsapp"},
            sort=[("creation_date", -1)],
        )

        if not last_msg:
            if last_out and (now - last_out).total_seconds() < 86400 * _WA_MIN_DAYS_PER_NUDGE:
                continue
            return deal_doc

        last_date = last_msg.get("creation_date")
        if last_date and last_date.tzinfo is None:
            last_date = last_date.replace(tzinfo=timezone.utc)

        if last_date:
            age_days = (now - last_date).days
            if age_days >= _WA_STALE_CONVERSATION_DAYS:
                continue

        if not last_msg.get("is_outgoing", False):
            return deal_doc

        # Last message is outgoing - count unanswered nudges since last inbound reply
        last_inbound = messages_col.find_one(
            {"deal_id": deal_id, "channel": "whatsapp", "is_outgoing": False},
            sort=[("creation_date", -1)],
        )
        since_filter = last_inbound["creation_date"] if last_inbound else datetime.min.replace(tzinfo=timezone.utc)
        nudge_count = messages_col.count_documents({
            "deal_id": deal_id,
            "channel": "whatsapp",
            "is_outgoing": True,
            "creation_date": {"$gt": since_filter},
        })
        nudge_count = max(1, nudge_count)
        required_days = nudge_count * _WA_MIN_DAYS_PER_NUDGE

        if last_out and (now - last_out).days < required_days:
            continue

        return deal_doc

    return None


def _notify_wa_unmessaged(deal_doc, user_id: str) -> None:
    """Create a notification if a WA deal has been CONNECTED 48h+ with no outgoing message."""
    try:
        from openoutreach.mongodb.models_extended import Notification
        from openoutreach.mongodb.connection import get_mongodb_collection

        creation = deal_doc.get("creation_date")
        if not creation:
            return
        if creation.tzinfo is None:
            creation = creation.replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - creation).total_seconds() / 3600
        if age_hours < 48:
            return

        messages_col = get_mongodb_collection("chat_messages")
        if messages_col is None:
            return
        has_outgoing = messages_col.count_documents({
            "deal_id": str(deal_doc["_id"]),
            "channel": "whatsapp",
            "is_outgoing": True,
        }, limit=1)
        if has_outgoing:
            return

        notif_col = get_mongodb_collection("notifications")
        dedup_key = f"wa_unmessaged_48h_{deal_doc['_id']}"
        if notif_col is None or notif_col.count_documents({"data.dedup_key": dedup_key}, limit=1):
            return

        Notification(
            recipient_id=user_id,
            notification_type="campaign_warning",
            title="WhatsApp lead not yet messaged",
            message=f"A WhatsApp lead has been connected for {int(age_hours)}h without receiving a message.",
            data={"dedup_key": dedup_key, "deal_id": str(deal_doc["_id"])},
        ).save()
    except Exception as e:
        logger.debug("Could not create WA unmessaged notification: %s", e)


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
        logger.debug("WA follow_up: outside WA active hours - skipping")
        return

    campaign_id = task.payload["campaign_id"]
    campaign = Campaign.get(campaign_id)
    if not campaign:
        logger.warning("WA follow_up: campaign %s not found", campaign_id)
        return

    deals_col = get_mongodb_collection("deals")
    if deals_col is None:
        return

    deal_doc = _next_wa_followup_deal(campaign_id, deals_col)
    if not deal_doc:
        # Check for unmessaged deals and notify
        for d in deals_col.find(
            {"campaign_id": campaign_id, "state": Deal.DealState.CONNECTED, "active_channel": "whatsapp"},
            {"_id": 1, "creation_date": 1, "user_id": 1},
            limit=10,
        ):
            _notify_wa_unmessaged(d, d.get("user_id", wa_session.wa_profile.user_id))
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
        if decision.explicit_follow_up_date:
            try:
                target = datetime.strptime(decision.explicit_follow_up_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                deal.next_follow_up_at = target
            except ValueError:
                deal.next_follow_up_at = now + timedelta(hours=decision.to_hours())
        else:
            deal.next_follow_up_at = now + timedelta(hours=decision.to_hours())
        deal.save(update_fields=["last_outgoing_at", "follow_up_cycled_at", "next_follow_up_at"])

        success = wa_session.send_message(lead.phone, message)
        if not success:
            logger.warning("WA follow_up: send failed for %s", lead.phone)
            banned = wa_session.detect_ban()
            if banned:
                from openoutreach.whatsapp.models.profile import STATUS_BANNED
                wa_session.wa_profile.status = STATUS_BANNED
                wa_session.wa_profile.save(update_fields=["status"])
                logger.error(
                    "WA follow_up: profile %s appears BANNED - marking and halting",
                    wa_session.wa_profile,
                )
                return
            deal.last_outgoing_at = None
            deal.next_follow_up_at = None
            deal.save(update_fields=["last_outgoing_at", "next_follow_up_at"])
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
                "wa_profile_id": wa_profile._id,
            },
        ).save()

    elif decision.action == "mark_completed":
        from openoutreach.mongodb.models import Deal
        outcome = decision.outcome or ""
        deal.state = Deal.DealState.COMPLETED
        deal.outcome = outcome
        deal.save()
        logger.info("WA follow_up [%s]: completed deal %s outcome=%s", campaign, deal._id, outcome)

    elif decision.action == "flag_human":
        deal.follow_up_cycled_at = datetime.now(timezone.utc)
        deal.save(update_fields=["follow_up_cycled_at"])
        try:
            from openoutreach.mongodb.models_extended import Notification
            Notification(
                recipient_id=str(deal.user_id),
                notification_type="action_required",
                title="WhatsApp lead needs your attention",
                message=(
                    f"{lead.phone} sent something that needs a human response "
                    f"in campaign \"{campaign}\". Check the conversation."
                ),
                data={"deal_id": str(deal._id), "phone": lead.phone, "campaign_id": str(campaign_id)},
            ).save()
        except Exception as exc:
            logger.debug("Could not create flag_human notification: %s", exc)
        logger.info("WA follow_up [%s]: flag_human for deal %s", campaign, deal._id)

    elif decision.action == "wait":
        deal.follow_up_cycled_at = datetime.now(timezone.utc)
        deal.save(update_fields=["follow_up_cycled_at"])
