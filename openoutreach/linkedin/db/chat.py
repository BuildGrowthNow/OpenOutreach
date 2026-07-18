import logging

logger = logging.getLogger(__name__)


def _get_lead_and_deal(session, public_identifier: str):
    """Return (lead, deal) for a public identifier in the active campaign.

    The conversation is owned by the Deal (per lead+campaign), so sync needs it.
    Returns (lead, None) when no Deal exists yet — the caller skips the upsert.
    """
    from openoutreach.mongodb.models import Deal, Lead

    lead = Lead.get_by_public_id(public_identifier)
    if not lead:
        return None, None
    deal = Deal.get_by_lead_and_campaign(public_identifier, session.campaign.pk)
    if deal and not hasattr(deal, 'lead'):
        deal.lead = lead
    return lead, deal


def sync_conversation(session, public_identifier: str) -> list[dict]:
    """Fetch messages from Voyager API and upsert into ChatMessage.

    Returns messages as a list of {sender, text, timestamp, is_outgoing} dicts
    from the DB (always the source of truth after sync). Newly-synced messages
    are also folded into the campaign Deal's `chat_summary` (mem0-style facts).
    """
    lead, deal = _get_lead_and_deal(session, public_identifier)
    if deal is None:
        logger.debug(
            "sync: no deal for %s in %s — skipping", public_identifier, session.campaign
        )
        return []

    new_messages = _sync_from_api(session, public_identifier, deal)
    _update_deal_chat_summary(session, deal, new_messages)

    return _read_from_db(deal)


def _update_deal_chat_summary(session, deal, new_messages):
    """Fold newly-synced ChatMessages into the campaign Deal's chat_summary."""
    if not new_messages:
        return
    from openoutreach.core.db.summaries import seller_name_from, update_chat_summary

    update_chat_summary(deal, new_messages, seller_name=seller_name_from(session))


def _sync_from_api(session, public_identifier: str, deal) -> list:
    """Fetch messages from Voyager API and upsert into DB, scoped to `deal`.

    Returns the list of newly-created ``ChatMessage`` rows (in arrival order),
    so callers can incrementally update derived caches like ``chat_summary``.
    """
    from openoutreach.mongodb.models_extended import ChatMessage
    from linkedin_cli.actions.conversations import (
        find_conversation_urn,
        find_conversation_urn_via_navigation,
        parse_message_element,
    )
    from linkedin_cli.api.client import PlaywrightLinkedinAPI
    from linkedin_cli.api.messaging import fetch_messages

    session.ensure_browser()
    api = PlaywrightLinkedinAPI(session=session)

    lead = deal.lead
    target_urn = lead.get_urn(session)
    mailbox_urn = session.self_profile["urn"]

    # Find conversation URN
    conversation_urn = find_conversation_urn(api, target_urn, mailbox_urn)
    if not conversation_urn:
        conversation_urn = find_conversation_urn_via_navigation(session, target_urn)
    if not conversation_urn:
        logger.debug("sync: no conversation found for %s", public_identifier)
        return []

    # Fetch messages
    raw = fetch_messages(api, conversation_urn)
    elements = (
        raw.get("data", {}).get("messengerMessagesBySyncToken", {}).get("elements", [])
    )

    self_urn = session.self_profile["urn"]
    new_messages: list = []

    from openoutreach.mongodb.connection import get_mongodb_collection
    messages_collection = get_mongodb_collection("chat_messages")

    for msg in elements:
        parsed = parse_message_element(msg)
        if not parsed or not parsed["entityUrn"]:
            continue

        is_outgoing = parsed["sender_host_urn"] == self_urn

        # Use upsert to prevent race conditions
        message_data = {
            "content": parsed["text"],
            "is_outgoing": is_outgoing,
            "owner_id": session.linkedin_profile.user_id,
        }
        if parsed["delivered_at"]:
            message_data["creation_date"] = parsed["delivered_at"]

        if messages_collection:
            # Atomic upsert prevents duplicate creation
            result = messages_collection.update_one(
                {
                    "deal_id": deal.pk,
                    "linkedin_urn": parsed["entityUrn"],
                },
                {
                    "$set": message_data,
                    "$setOnInsert": {
                        "deal_id": deal.pk,
                        "linkedin_urn": parsed["entityUrn"],
                    }
                },
                upsert=True
            )

            # Track newly created messages
            if result.upserted_id:
                obj = ChatMessage.get_by_deal_and_urn(deal.pk, parsed["entityUrn"])
                if obj:
                    new_messages.append(obj)
                logger.debug(
                    "sync: new message from %s for %s",
                    parsed["sender_name"],
                    public_identifier,
                )
        else:
            # Fallback to original logic if collection unavailable
            existing = ChatMessage.get_by_deal_and_urn(deal.pk, parsed["entityUrn"])
            if existing:
                existing.content = parsed["text"]
                existing.is_outgoing = is_outgoing
                if parsed["delivered_at"]:
                    existing.creation_date = parsed["delivered_at"]
                existing.save()
            else:
                obj = ChatMessage(
                    deal_id=deal.pk,
                    linkedin_urn=parsed["entityUrn"],
                    content=parsed["text"],
                    is_outgoing=is_outgoing,
                    owner_id=session.linkedin_profile.user_id,
                    creation_date=parsed["delivered_at"] if parsed["delivered_at"] else None,
                )
                obj.save()
                new_messages.append(obj)
                logger.debug(
                    "sync: new message from %s for %s",
                    parsed["sender_name"],
                    public_identifier,
                )

    # Sort new messages chronologically so the LLM sees them in order.
    new_messages.sort(key=lambda m: m.creation_date or m.pk)
    logger.debug(
        "sync: processed %d messages for %s (%d new)",
        len(elements),
        public_identifier,
        len(new_messages),
    )
    return new_messages


def _read_from_db(deal) -> list[dict]:
    """Read all ChatMessages for a deal, sorted chronologically."""
    from openoutreach.mongodb.models_extended import ChatMessage

    lead_name = deal.lead.public_identifier or "them"

    messages = ChatMessage.find_by_deal(deal.pk)

    result = []
    for msg in messages:
        if not msg.content:
            continue
        if msg.is_outgoing:
            sender = "me"
        else:
            sender = lead_name
        result.append(
            {
                "sender": sender or "me",
                "text": msg.content,
                "timestamp": (
                    msg.creation_date.strftime("%Y-%m-%d %H:%M")
                    if msg.creation_date
                    else ""
                ),
                "is_outgoing": msg.is_outgoing,
            }
        )
    return result
