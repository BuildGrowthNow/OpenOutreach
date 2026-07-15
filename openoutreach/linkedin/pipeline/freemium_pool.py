# openoutreach/linkedin/pipeline/freemium_pool.py
"""Freemium candidate selection — seed profiles (QUALIFIED Deals) first, then undiscovered."""

from __future__ import annotations

import logging

from openoutreach.crm.models import DealState

logger = logging.getLogger(__name__)


def find_freemium_candidate(session, qualifier) -> dict | None:
    """Return the top-ranked embedded lead eligible for connection.

    Priority: seed profiles with QUALIFIED Deals are returned first (ranked by
    the kit model).  Once all seeds are exhausted (connected / failed), falls
    back to embedded leads without any Deal in this campaign.
    """
    from openoutreach.mongodb.models import Deal, Lead
    from openoutreach.mongodb.connection import get_mongodb_collection

    campaign = session.campaign

    # All embedded lead IDs (leads with embedding field present)
    leads_collection = get_mongodb_collection("leads")
    if leads_collection is None:
        return None

    embedded_pks = set(
        str(doc["_id"]) for doc in leads_collection.find(
            {"embedding": {"$ne": None}}, {"_id": 1}
        )
    )

    # Seed profiles: QUALIFIED Deals in this campaign (ready to connect)
    deals_collection = get_mongodb_collection("deals")
    if deals_collection is None:
        return None

    seed_pks = set(
        str(doc["lead_id"]) for doc in deals_collection.find(
            {"campaign_id": campaign.pk, "state": DealState.QUALIFIED.value},
            {"lead_id": 1}
        )
    )
    seed_pks &= embedded_pks  # must have embeddings

    # Leads with any Deal in this campaign (all states)
    all_dealt_pks = set(
        str(doc["lead_id"]) for doc in deals_collection.find(
            {"campaign_id": campaign.pk}, {"lead_id": 1}
        )
    )

    # Undiscovered: embedded leads with no Deal at all in this campaign
    undiscovered_pks = embedded_pks - all_dealt_pks

    # Try seeds first, then undiscovered
    for candidate_pks in (seed_pks, undiscovered_pks):
        if not candidate_pks:
            continue
        result = _pick_best(sorted(candidate_pks), qualifier, session)
        if result:
            return result

    return None


def _pick_best(lead_pks: list[str], qualifier, session) -> dict | None:
    """Rank leads by qualifier and return the top-1 profile dict."""
    from openoutreach.mongodb.models import Lead

    # Fetch leads from MongoDB
    leads = [Lead.get(pk) for pk in lead_pks]
    leads = [lead for lead in leads if lead and not lead.disqualified]
    profiles = [lead.to_profile_dict() for lead in leads]

    if not profiles:
        return None

    ranked = qualifier.rank_profiles(profiles, session=session)
    return ranked[0] if ranked else None
