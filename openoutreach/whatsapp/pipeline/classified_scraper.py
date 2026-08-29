"""Classified ads scraper - Gumtree (UK/AU).

Searches the site for `query`, opens listing detail pages, and extracts phone
numbers from tel: links or contextual body text.

Entry point: create_leads_from_classified(...)
"""
from __future__ import annotations

import logging
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

from openoutreach.whatsapp.pipeline.icp_filter import apply_icp_filter as _apply_icp_filter
from openoutreach.whatsapp.pipeline.upsert import BusinessListing, upsert_listings_as_leads
from openoutreach.whatsapp.pipeline.utils import (
    apply_resource_block as _apply_resource_block,
    is_likely_whatsapp_number as _is_likely_whatsapp_number,
    phone_from_page as _phone_from_page,
    random_user_agent as _random_user_agent,
    scrape_retry as _scrape_retry,
)

logger = logging.getLogger(__name__)

_MAX_LISTINGS = 60      # cards to collect from search page
_MAX_DETAIL_PAGES = 30  # listing detail pages to visit per backend
_DEFAULT_SITES = ["gumtree"]


# ---------------------------------------------------------------------------
# Gumtree  (UK / AU)
# ---------------------------------------------------------------------------

def _scrape_gumtree(page, query: str, country_code: str) -> List[BusinessListing]:
    base = (
        "https://www.gumtree.com.au"
        if country_code.upper() == "AU"
        else "https://www.gumtree.com"
    )
    url = f"{base}/search?search_category=all&q={urllib.parse.quote(query)}"
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    try:
        page.wait_for_selector(".listing-link, .natural", timeout=15000)
    except Exception:
        logger.warning("gumtree: no results for %r", query)
        return []

    links = []
    seen: set = set()
    for el in page.query_selector_all("a.listing-link"):
        href = el.get_attribute("href") or ""
        if not href.startswith("http"):
            href = base + href
        if href not in seen:
            seen.add(href)
            links.append(href)
        if len(links) >= _MAX_LISTINGS:
            break

    listings: List[BusinessListing] = []
    for link in links[:_MAX_DETAIL_PAGES]:
        try:
            page.goto(link, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(700)

            title_el = page.query_selector("h1.listing-title, h1")
            title = title_el.inner_text().strip() if title_el else ""

            phone = _phone_from_page(page, country_code) or None
            if not phone:
                continue

            listings.append(BusinessListing(
                name=title or "Gumtree Listing",
                phone=phone,
                source="gumtree",
            ))
        except Exception as exc:
            logger.debug("gumtree: error on %s: %s", link, type(exc).__name__)

    return listings


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_BACKEND_FN = {
    "gumtree": _scrape_gumtree,
}


def _run_classified_in_isolation(
    site_name: str, query: str, country_code: str
) -> List[BusinessListing]:
    """Launch a dedicated browser for one classified site; safe to call from a thread."""
    from playwright.sync_api import sync_playwright
    from playwright_stealth import Stealth

    def _attempt() -> List[BusinessListing]:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                context = browser.new_context(
                    user_agent=_random_user_agent(),
                    locale="en-US",
                    viewport={"width": 1280, "height": 800},
                )
                Stealth().apply_stealth_sync(context)
                page = context.new_page()
                _apply_resource_block(page)
                page.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"})
                return _BACKEND_FN[site_name](page, query, country_code)
            finally:
                browser.close()

    return _scrape_retry(_attempt, max_attempts=2, base_delay=3.0, label=f"classified:{site_name}")


def create_leads_from_classified(
    query: str,
    country_code: str,
    campaign_id: str,
    user_id: str,
    sites: Optional[List[str]] = None,
) -> int:
    """Scrape classified sites with concurrent isolated browsers, dedup by phone, upsert leads + deals.

    Each site runs in its own browser process so a hang on one site never
    blocks the others. Applies ICP filter before upsert when campaign has criteria.
    Returns count of new leads created.
    """
    active_sites = [s for s in (sites or _DEFAULT_SITES) if s in _BACKEND_FN]
    if not active_sites:
        logger.warning("classified: no valid sites in %s", sites)
        return 0

    all_listings: List[BusinessListing] = []

    with ThreadPoolExecutor(max_workers=len(active_sites)) as pool:
        futures = {
            pool.submit(_run_classified_in_isolation, site, query, country_code): site
            for site in active_sites
        }
        for future in as_completed(futures):
            site = futures[future]
            try:
                results = future.result()
                logger.info("classified: %s returned %d listings", site, len(results))
                all_listings.extend(results)
            except Exception as exc:
                logger.warning("classified: site %s failed: %s", site, type(exc).__name__)

    if not all_listings:
        from openoutreach.whatsapp.pipeline.alerts import fire_scrape_zero_results
        fire_scrape_zero_results(campaign_id, user_id, "classified", query)
        return 0

    # Skip phones already in DB — saves ICP tokens on re-runs
    already_known: frozenset = frozenset()
    try:
        from openoutreach.mongodb.connection import get_mongodb_collection
        leads_col = get_mongodb_collection("leads")
        if leads_col is not None:
            already_known = frozenset(
                d["phone"] for d in leads_col.find(
                    {"user_id": user_id, "phone": {"$ne": None}},
                    {"phone": 1},
                ) if d.get("phone")
            )
    except Exception as exc:
        logger.warning("classified: dedup pre-fetch failed: %s", type(exc).__name__)

    if already_known:
        before = len(all_listings)
        all_listings = [
            lst for lst in all_listings
            if not lst.phone or lst.phone not in already_known
        ]
        skipped = before - len(all_listings)
        if skipped:
            logger.info("classified: dedup removed %d already-known phones", skipped)

    # Drop definitive landlines — they can't receive WhatsApp messages
    before_mobile = len(all_listings)
    all_listings = [
        lst for lst in all_listings
        if not lst.phone or _is_likely_whatsapp_number(lst.phone)
    ]
    dropped_landlines = before_mobile - len(all_listings)
    if dropped_landlines:
        logger.info("classified: filtered %d landline numbers", dropped_landlines)

    all_listings = _apply_icp_filter(all_listings, campaign_id, user_id, label="classified")
    return upsert_listings_as_leads(all_listings, campaign_id, user_id)
