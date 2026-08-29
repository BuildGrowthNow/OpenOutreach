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

    # Step 1: collect lead_id→deal_id from QUALIFIED WA deals (projection only,
    # larger window so the phone filter in step 2 can fill _MAX_PER_RUN slots
    # even when many leads already have phone_on_whatsapp set).
    deal_docs = list(deals_col.find(
        {
            "campaign_id": {"$in": campaign_ids},
            "state": Deal.DealState.QUALIFIED,
            "active_channel": "whatsapp",
        },
        {"_id": 1, "lead_id": 1},
        sort=[("creation_date", 1)],
        limit=200,
    ))
    if not deal_docs:
        return 0

    lead_to_deal: dict[str, str] = {d["lead_id"]: str(d["_id"]) for d in deal_docs}

    # Step 2: find leads where phone_on_whatsapp is unknown.
    # MongoDB: {field: None} matches both null-valued and absent fields.
    unknown_lead_docs = list(leads_col.find(
        {
            "_id": {"$in": list(lead_to_deal.keys())},
            "phone": {"$exists": True, "$ne": None},
            "phone_on_whatsapp": None,
        },
        limit=_MAX_PER_RUN,
    ))

    if not unknown_lead_docs:
        return 0

    validated = 0
    for lead_doc in unknown_lead_docs:
        lead = Lead.from_dict(lead_doc)
        deal_id = lead_to_deal.get(str(lead._id))
        if not deal_id:
            continue

        deal_doc = deals_col.find_one({"_id": deal_id})
        if not deal_doc:
            continue
        deal = Deal.from_dict(deal_doc)

        try:
            registered = wa_session.is_registered(lead.phone)
        except Exception as e:
            logger.warning("validate_wa_phones: is_registered failed: %s", type(e).__name__)
            continue

        lead.phone_on_whatsapp = registered
        lead.save(update_fields=["phone_on_whatsapp"])
        validated += 1

        if not registered:
            deal.state = Deal.DealState.FAILED
            deal.reason = "phone_not_on_whatsapp"
            deal.save(update_fields=["state", "reason"])
            logger.info(
                "validate_wa_phones: %s not on WhatsApp - deal %s FAILED",
                lead.phone, deal._id,
            )

    if validated:
        logger.info(
            "validate_wa_phones: %d phones validated for wa_profile %s",
            validated, wa_profile_id,
        )
    return validated
