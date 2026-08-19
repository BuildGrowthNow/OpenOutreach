# openoutreach/whatsapp/tasks/validate.py
"""Pre-flight phone validation for WhatsApp leads.

Called by the daemon BEFORE server reconcile so that unregistered leads are
marked FAILED before any WHATSAPP_MESSAGE task is planned for them.
Runs in the WA Playwright thread (same pattern as other WA task handlers).
"""
from __future__ import annotations

import logging

from openoutreach.mongodb.connection import get_mongodb_collection

logger = logging.getLogger(__name__)

# Process at most this many unknown leads per run to keep latency bounded.
# Each check navigates WA Web once (~2-3 s); 30 = ~60-90 s max.
_MAX_PER_RUN = 30


def validate_wa_phones(wa_session) -> int:
    """Validate QUALIFIED WA deals where phone_on_whatsapp is unknown.

    For each matching lead:
    - Calls WASession.is_registered(phone)
    - Sets lead.phone_on_whatsapp = True / False
    - FAILs the deal when phone is not on WhatsApp

    Returns count of leads validated this run.
    """
    from openoutreach.mongodb.models import Deal, Lead

    deals_col = get_mongodb_collection("deals")
    leads_col = get_mongodb_collection("leads")
    campaigns_col = get_mongodb_collection("campaigns")
    if deals_col is None or leads_col is None or campaigns_col is None:
        return 0

    wa_profile_id = wa_session.wa_profile._id

    # Scope to campaigns that use this WA profile.
    campaign_ids = [
        str(c["_id"])
        for c in campaigns_col.find(
            {"whatsapp_profile_id": wa_profile_id},
            {"_id": 1},
        )
    ]
    if not campaign_ids:
        return 0

    # QUALIFIED WA deals where phone registration is unknown, oldest first.
    deal_docs = list(deals_col.find(
        {
            "campaign_id": {"$in": campaign_ids},
            "state": Deal.DealState.QUALIFIED,
            "active_channel": "whatsapp",
        },
        sort=[("creation_date", 1)],
        limit=_MAX_PER_RUN,
    ))

    validated = 0
    for deal_doc in deal_docs:
        deal = Deal.from_dict(deal_doc)
        lead = Lead.get(deal.lead_id)
        if not lead or not lead.phone:
            continue

        if lead.phone_on_whatsapp is not None:
            continue  # already known — skip

        try:
            registered = wa_session.is_registered(lead.phone)
        except Exception as e:
            logger.warning("validate_wa_phones: is_registered failed for %s: %s", lead.phone, e)
            continue

        lead.phone_on_whatsapp = registered
        lead.save(update_fields=["phone_on_whatsapp"])
        validated += 1

        if not registered:
            deal.state = Deal.DealState.FAILED
            deal.reason = "phone_not_on_whatsapp"
            deal.save(update_fields=["state", "reason"])
            logger.info(
                "validate_wa_phones: %s not on WhatsApp — deal %s FAILED",
                lead.phone, deal._id,
            )

    if validated:
        logger.info(
            "validate_wa_phones: %d phones validated for wa_profile %s",
            validated, wa_profile_id,
        )
    return validated
