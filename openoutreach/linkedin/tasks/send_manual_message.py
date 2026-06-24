# openoutreach/linkedin/tasks/send_manual_message.py
"""Send manual message task — sends a manual message to a lead via Playwright."""
from __future__ import annotations

import logging
from openoutreach.crm.models import Message, DealState
from openoutreach.core.db.deals import set_profile_state

logger = logging.getLogger(__name__)

def handle_send_manual_message(task, session, qualifiers):
    from linkedin_cli.actions.message import send_raw_message
    from openoutreach.linkedin.db.chat import sync_conversation
    
    campaign = session.campaign
    message_id = task.payload.get("message_id")
    
    try:
        msg = Message.objects.get(pk=message_id)
    except Message.DoesNotExist:
        logger.error("[%s] send_manual_message: Message %s not found — task skipped", campaign, message_id)
        return
        
    deal = msg.deal
    public_id = deal.lead.public_identifier
    logger.info("[%s] Sending manual message to %s", campaign, public_id)
    
    profile: dict[str, str] = {
        "public_identifier": public_id,
        "urn": deal.lead.urn or "",
    }
    
    # Ensure Playwright browser session is running and logged in
    session.ensure_browser()
    
    content_str: str = str(msg.content)
    sent = send_raw_message(session, profile, content_str)
    if not sent:
        raise Exception(f"Playwright send_raw_message failed for {public_id}")
        
    # Mark the deal state as CONNECTED just in case it wasn't
    if deal.state != DealState.CONNECTED:
        set_profile_state(session, public_id, DealState.CONNECTED.value)
        
    # Sync the conversation back to DB to update chat logs and record the outgoing message
    try:
        sync_conversation(session, public_id)
    except Exception:
        logger.exception("post-send manual message sync failed for %s", public_id)
