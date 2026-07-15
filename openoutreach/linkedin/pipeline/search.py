# openoutreach/linkedin/pipeline/search.py
"""Search keyword management and LinkedIn People search."""

from __future__ import annotations

import logging
from datetime import datetime, timezone as tz

from termcolor import colored

logger = logging.getLogger(__name__)


def run_search(session) -> str | None:
    """Use the next search keyword to discover new profiles. Returns keyword or None."""
    from linkedin_cli.actions.search import search_people
    from openoutreach.linkedin.db.leads import discover_and_enrich
    from openoutreach.linkedin.pipeline.search_keywords import generate_search_keywords
    from openoutreach.linkedin.models import SearchKeyword

    campaign = session.campaign

    if not SearchKeyword.exists_unused(campaign.pk):
        used = SearchKeyword.get_used_keywords(campaign.pk)
        fresh = generate_search_keywords(
            product_pitch=campaign.product_pitch,
            campaign_objective=campaign.campaign_objective,
            icp_titles=campaign.icp_titles or None,
            exclude_keywords=used if used else None,
        )

        if not fresh:
            return None

        for keyword in fresh:
            sk = SearchKeyword(campaign_id=campaign.pk, keyword=keyword, used=False)
            sk.save()

    kw = SearchKeyword.get_next_unused(campaign.pk)
    if not kw:
        return None

    kw.used = True
    kw.used_at = datetime.now(tz.utc)
    kw.save()

    logger.info(
        colored("\u25b6 search", "magenta", attrs=["bold"]) + " keyword=%r", kw.keyword
    )
    urls = [p["url"] for p in search_people(session, kw.keyword)["profiles"]]
    discover_and_enrich(session, urls)
    return kw.keyword
