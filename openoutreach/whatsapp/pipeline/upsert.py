"""Shared upsert helpers for all WA lead-source scrapers."""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone as tz
from typing import List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class BusinessListing:
    """Normalised business lead from any scraper backend."""

    name: str                        # business / company name → stored as Lead.company
    source: str                      # scraper identifier
    phone: Optional[str] = None      # E.164, e.g. "+15551234567"; None = partial (website spider pending)
    website: Optional[str] = None
    address: Optional[str] = None
    category: Optional[str] = None   # → stored as Lead.headline
    rating: Optional[float] = None
    review_count: Optional[int] = None


def upsert_listings_as_leads(
    listings: List[BusinessListing],
    campaign_id: str,
    user_id: str,
    channel: str = "whatsapp",
) -> int:
    """Dedup by phone, upsert Leads + Deals. Returns count of new leads created."""
    from openoutreach.mongodb.connection import get_mongodb_collection
    from openoutreach.mongodb.models import Deal

    seen_phones: set = set()
    unique: List[BusinessListing] = []
    for lst in listings:
        if not lst.phone:
            continue
        if lst.phone not in seen_phones:
            seen_phones.add(lst.phone)
            unique.append(lst)

    leads_col = get_mongodb_collection("leads")
    deals_col = get_mongodb_collection("deals")
    if leads_col is None or deals_col is None:
        raise RuntimeError("MongoDB leads/deals collection unavailable")

    created = 0
    now = datetime.now(tz.utc)

    for lst in unique:
        lead_id = str(uuid4())
        set_on_insert: dict = {
            "_id": lead_id,
            "phone": lst.phone,
            "phone_source": lst.source,
            "company": lst.name or None,
            "linkedin_url": None,
            "public_identifier": "",
            "user_id": user_id,
            "disqualified": False,
            "creation_date": now,
            "update_date": now,
        }
        if lst.category:
            set_on_insert["headline"] = lst.category
        if lst.website:
            set_on_insert["website"] = lst.website
        if lst.address:
            set_on_insert["address"] = lst.address
        if lst.rating is not None:
            set_on_insert["rating"] = lst.rating
        if lst.review_count is not None:
            set_on_insert["review_count"] = lst.review_count
        if lst.rating is not None and lst.rating > 0:
            # 0-1 score: balances star rating with review volume (log10 curve caps at ~300 reviews)
            count = lst.review_count or 1
            set_on_insert["quality_score"] = round(
                min(1.0, (lst.rating / 5.0) * min(1.0, math.log10(max(1, count)) / 2.5)),
                3,
            )

        result = leads_col.update_one(
            {"phone": lst.phone, "user_id": user_id},
            {"$setOnInsert": set_on_insert},
            upsert=True,
        )

        if result.upserted_id is not None:
            actual_lead_id = str(result.upserted_id)
            created += 1
        else:
            doc = leads_col.find_one({"phone": lst.phone, "user_id": user_id}, {"_id": 1})
            actual_lead_id = str(doc["_id"]) if doc else lead_id
            # fill any fields that are currently null/absent on the existing lead
            fill: dict = {}
            if lst.name:
                fill["company"] = lst.name
            if lst.category:
                fill["headline"] = lst.category
            if lst.website:
                fill["website"] = lst.website
            if lst.address:
                fill["address"] = lst.address
            if lst.rating is not None:
                fill["rating"] = lst.rating
            if lst.review_count is not None:
                fill["review_count"] = lst.review_count
            if fill:
                leads_col.update_one(
                    {"_id": actual_lead_id},
                    [{"$set": {
                        **{k: {"$ifNull": [f"${k}", v]} for k, v in fill.items()},
                        "update_date": now,
                    }}],
                )

        if not deals_col.find_one({"lead_id": actual_lead_id, "campaign_id": campaign_id}):
            deals_col.insert_one({
                "_id": str(uuid4()),
                "lead_id": actual_lead_id,
                "campaign_id": campaign_id,
                "state": Deal.DealState.DISCOVERED,
                "user_id": user_id,
                "creation_date": now,
                "active_channel": channel,
            })

    logger.info("upsert: %d new leads for campaign %s", created, campaign_id)
    return created
