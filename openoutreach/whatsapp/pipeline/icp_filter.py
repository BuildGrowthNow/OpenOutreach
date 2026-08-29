"""ICP pre-insertion filter for WA lead scrapers.

Batches BusinessListings through an LLM to remove obviously irrelevant
businesses before they enter the DISCOVERED queue. When the campaign has no ICP
criteria (no product_pitch, campaign_objective, or icp_titles), skips filtering
and returns all listings unchanged — avoids an LLM call with nothing to compare against.

Failure mode is always safe: any exception (LLM unavailable, API timeout, etc.)
logs a warning and returns all listings, so scraping is never silently broken.
"""
from __future__ import annotations

import logging
from typing import List, TYPE_CHECKING
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from openoutreach.whatsapp.pipeline.upsert import BusinessListing

if TYPE_CHECKING:
    from openoutreach.mongodb.models import Campaign

logger = logging.getLogger(__name__)


def _domain(url: str) -> str:
    """Extract bare hostname from a URL for ICP prompt readability."""
    try:
        return urlparse(url).netloc or url
    except Exception:
        return url

_BATCH_SIZE = 15
_CLASSIFIED_SOURCES = frozenset({"olx", "mercadolibre", "gumtree"})


class _IcpDecision(BaseModel):
    relevant_indices: List[int] = Field(
        description=(
            "0-based indices of businesses in the list that are plausible B2B sales targets "
            "for this campaign. Include any business that could plausibly be a customer. "
            "Exclude only clear mismatches. When uncertain, include."
        )
    )


def filter_by_icp(
    listings: List[BusinessListing],
    campaign: "Campaign",
    user_id: str,
) -> List[BusinessListing]:
    """Filter listings through LLM ICP check before upsert.

    Returns only listings that plausibly match the campaign's target customer.
    Returns all listings unchanged if:
    - No ICP criteria defined on the campaign
    - LLM is unavailable or raises an exception
    """
    if not listings:
        return listings

    product_pitch: str = getattr(campaign, "product_pitch", "") or ""
    campaign_objective: str = getattr(campaign, "campaign_objective", "") or ""
    icp_titles: list = getattr(campaign, "icp_titles", []) or []

    if not product_pitch and not campaign_objective and not icp_titles:
        logger.debug("icp_filter: no ICP criteria on campaign - skipping filter")
        return listings

    try:
        from pydantic_ai import Agent
        from openoutreach.core.llm import get_llm_model, run_agent_sync
    except ImportError as exc:
        logger.warning("icp_filter: pydantic_ai unavailable (%s) - skipping filter", type(exc).__name__)
        return listings

    agent = Agent(
        get_llm_model(user_id=user_id),
        output_type=_IcpDecision,
        model_settings={"temperature": 0.1, "timeout": 45},
    )

    kept: List[BusinessListing] = []
    total_in = len(listings)

    for batch_start in range(0, total_in, _BATCH_SIZE):
        batch = listings[batch_start: batch_start + _BATCH_SIZE]

        lines = "\n".join(
            "{i}. {name}{cat}{site}{src}".format(
                i=i,
                name=lst.name or "(unnamed business)",
                cat=f" [{lst.category}]" if lst.category else "",
                site=f" ({_domain(lst.website)})" if lst.website else "",
                src=" [classified listing — may be individual seller]"
                if lst.source in _CLASSIFIED_SOURCES
                else "",
            )
            for i, lst in enumerate(batch)
        )

        icp_hint = ""
        if icp_titles:
            icp_hint = f"\nIdeal customer types / verticals: {', '.join(icp_titles)}"

        prompt = (
            f"We sell: {product_pitch}\n"
            f"Campaign goal: {campaign_objective}"
            f"{icp_hint}\n\n"
            f"Below is a list of businesses found by a lead scraper. "
            f"Which ones are plausible B2B sales targets for us? "
            f"Be INCLUSIVE - only exclude businesses that are clearly irrelevant "
            f"(e.g. personal accounts, direct competitors, or completely unrelated industries). "
            f"When the business type is ambiguous or matches even loosely, INCLUDE it.\n\n"
            f"Businesses:\n{lines}\n\n"
            f"Return the 0-based indices of the relevant businesses."
        )

        try:
            result = run_agent_sync(agent.run(prompt)).output
            relevant_set = set(result.relevant_indices)
            for i, lst in enumerate(batch):
                if i in relevant_set:
                    kept.append(lst)
            logger.debug(
                "icp_filter: batch %d-%d: %d/%d passed",
                batch_start,
                batch_start + len(batch),
                sum(1 for i in range(len(batch)) if i in relevant_set),
                len(batch),
            )
        except Exception as exc:
            logger.warning(
                "icp_filter: LLM call failed for batch %d-%d: %s - keeping all",
                batch_start,
                batch_start + len(batch),
                type(exc).__name__,
            )
            kept.extend(batch)

    logger.info(
        "icp_filter: %d/%d listings passed ICP filter for campaign %s",
        len(kept),
        total_in,
        getattr(campaign, "_id", "?"),
    )
    return kept


def apply_icp_filter(
    listings: List[BusinessListing],
    campaign_id: str,
    user_id: str,
    label: str = "",
) -> List[BusinessListing]:
    """Load campaign and run ICP filter. Returns listings unchanged on any error.

    Shared wrapper used by all WA pipeline scrapers — avoids copy-pasting this
    try/except boilerplate in each scraper module.
    """
    try:
        from openoutreach.mongodb.models import Campaign
        campaign = Campaign.get(campaign_id)
        if campaign:
            return filter_by_icp(listings, campaign, user_id)
    except Exception as exc:
        logger.warning(
            "icp_filter%s: error: %s - keeping all listings",
            f"[{label}]" if label else "",
            type(exc).__name__,
        )
    return listings
