# openoutreach/whatsapp/tasks/sync.py
"""WhatsApp inbox sync handler."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from openoutreach.mongodb.connection import get_mongodb_collection

logger = logging.getLogger(__name__)

# JS snippet to extract messages from an open WA Web conversation panel.
# Each selector list is tried in order so the scrape survives WA Web redesigns
# that rename data-testid attributes without changing DOM structure.
_EXTRACT_MESSAGES_JS = """() => {
    function qs(el, selectors) {
        for (const s of selectors) {
            const found = el.querySelector(s);
            if (found) return found;
        }
        return null;
    }
    const containerSelectors = [
        '[data-testid="msg-container"]',
        '.message-in',
        '.message-out',
        '[class*="message-"]'
    ];
    let msgs = [];
    for (const s of containerSelectors) {
        const found = Array.from(document.querySelectorAll(s));
        if (found.length > 0) { msgs = found; break; }
    }
    return msgs.map(el => {
        const out = !!(
            el.querySelector('[data-testid="msg-dblcheck"], [data-testid="msg-check"]') ||
            el.classList.contains('message-out')
        );
        const body = qs(el, [
            '[data-testid="msg-text"]',
            '.copyable-text',
            'span.selectable-text',
            'span[dir="ltr"]',
            'span[dir="rtl"]'
        ]);
        const ts = el.querySelector('[data-testid="msg-meta"]');
        return {
            content: body ? body.innerText : null,
            is_outgoing: out,
            ts_text: ts ? ts.getAttribute('data-pre-plain-text') : null
        };
    }).filter(m => m.content);
}"""

# Per-deal consecutive empty-scrape counter — surfaces selector drift early
_empty_scrape_count: dict[str, int] = {}
_EMPTY_SCRAPE_WARN_THRESHOLD = 3


def _navigate_to_chat(wa_session, phone: str) -> bool:
    """Navigate to a WA Web direct chat by phone number. Returns True on load."""
    url = f"https://web.whatsapp.com/send?phone={phone.lstrip('+')}"
    try:
        wa_session.page.goto(url)
        wa_session.page.wait_for_selector(
            "[data-testid='conversation-panel-wrapper']", timeout=15000
        )
        return True
    except Exception as e:
        logger.warning("WA sync: failed to load chat for %s: %s", phone, e)
        return False


def handle_whatsapp_sync(task, wa_session, qualifiers):  # noqa: ARG001
    """Sync incoming WhatsApp messages for all open WA deals in this campaign.

    task.payload = {"campaign_id": <id>}
    - Iterates PENDING + CONNECTED deals where active_channel=="whatsapp"
    - Navigates to each lead's WA chat, extracts messages via JS
    - Saves new inbound messages as ChatMessage(channel="whatsapp")
    - Transitions PENDING → CONNECTED when a reply is found
    - Updates deal.chat_summary via update_chat_summary()
    """
    from openoutreach.mongodb.models import Campaign, Deal, Lead
    from openoutreach.mongodb.models_extended import ChatMessage
    from openoutreach.core.db.summaries import update_chat_summary

    campaign_id = task.payload["campaign_id"]
    campaign = Campaign.get(campaign_id)
    if not campaign:
        logger.warning("WA sync: campaign %s not found", campaign_id)
        return

    deals_col = get_mongodb_collection("deals")
    messages_col = get_mongodb_collection("chat_messages")
    if deals_col is None or messages_col is None:
        return

    deal_docs = list(deals_col.find({
        "campaign_id": campaign_id,
        "state": {"$in": [Deal.DealState.PENDING, Deal.DealState.CONNECTED]},
        "active_channel": "whatsapp",
    }))

    if not deal_docs:
        logger.debug("WA sync [%s]: no open WA deals", campaign)
        return

    logger.info("WA sync [%s]: syncing %d deal(s)", campaign, len(deal_docs))

    for deal_doc in deal_docs:
        deal = Deal.from_dict(deal_doc)
        lead = Lead.get(deal.lead_id)
        if not lead or not lead.phone:
            continue

        if not _navigate_to_chat(wa_session, lead.phone):
            continue

        try:
            raw_msgs = wa_session.page.evaluate(_EXTRACT_MESSAGES_JS)
        except Exception as e:
            logger.warning("WA sync: JS extraction failed for %s: %s", lead.phone, e)
            continue

        if not raw_msgs:
            deal_key = str(deal._id)
            _empty_scrape_count[deal_key] = _empty_scrape_count.get(deal_key, 0) + 1
            count = _empty_scrape_count[deal_key]
            if count >= _EMPTY_SCRAPE_WARN_THRESHOLD:
                logger.warning(
                    "WA sync [%s]: deal %s returned 0 messages for %d consecutive scrapes "
                    "— WA Web selectors may have changed",
                    campaign, deal._id, count,
                )
            continue
        _empty_scrape_count.pop(str(deal._id), None)  # reset on successful scrape

        # Determine cutoff: only process messages newer than latest saved WA message
        last_saved = messages_col.find_one(
            {"deal_id": str(deal._id), "channel": "whatsapp"},
            sort=[("creation_date", -1)],
        )
        last_saved_content = last_saved.get("content", "") if last_saved else ""

        new_messages = []
        seen_cutoff = not bool(last_saved_content)
        for raw in raw_msgs:
            content = (raw.get("content") or "").strip()
            if not content:
                continue
            if not seen_cutoff:
                if content == last_saved_content:
                    seen_cutoff = True
                continue

            is_outgoing = bool(raw.get("is_outgoing", False))
            now = datetime.now(timezone.utc)
            msg = ChatMessage(
                deal_id=str(deal._id),
                content=content,
                is_outgoing=is_outgoing,
                creation_date=now,
                user_id=deal.user_id,
                channel="whatsapp",
            )
            msg.save()
            new_messages.append(msg)

        if not new_messages:
            continue

        has_inbound = any(not m.is_outgoing for m in new_messages)

        if has_inbound and deal.state == Deal.DealState.PENDING:
            deal.state = Deal.DealState.CONNECTED
            deal.save()
            logger.info("WA sync [%s]: deal %s → CONNECTED (reply received)", campaign, deal._id)

        inbound_only = [m for m in new_messages if not m.is_outgoing]
        if inbound_only:
            wa_profile = wa_session.wa_profile
            seller_name = wa_profile.display_name or wa_profile.phone_number or ""
            try:
                update_chat_summary(
                    deal,
                    inbound_only,
                    seller_name=seller_name,
                    user_id=deal.user_id,
                )
            except Exception as e:
                logger.warning("WA sync: chat_summary update failed for deal %s: %s", deal._id, e)

    logger.info("WA sync [%s]: done", campaign)
