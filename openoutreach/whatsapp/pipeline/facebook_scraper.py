"""Facebook Business pages scraper.

Searches DuckDuckGo for Facebook business page URLs (site:facebook.com/pages),
then visits each page's About section concurrently via isolated browser processes.

IMPORTANT: Facebook increasingly requires authentication to view business data.
This scraper targets publicly-accessible pages only. Expect variable yield —
pages behind login walls are silently skipped. If you need consistent results,
use google_maps or wa_groups sources instead.

Entry point: create_leads_from_facebook(...)
"""
from __future__ import annotations

import logging
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Tuple

from openoutreach.whatsapp.pipeline.upsert import BusinessListing, upsert_listings_as_leads
from openoutreach.whatsapp.pipeline.utils import (
    decode_ddg_href as _decode_ddg_href,
    phone_from_page as _phone_from_page,
    random_user_agent as _random_user_agent,
    scrape_retry as _scrape_retry,
)

logger = logging.getLogger(__name__)

_MAX_PAGES = 20
_MAX_DETAIL_WORKERS = 6

# Facebook path prefixes to skip when filtering search results
_FB_SKIP_PREFIXES = (
    "search", "login", "groups", "events", "watch",
    "marketplace", "gaming", "help", "policies",
)


def _is_fb_business_page(url: str) -> bool:
    """Return True if url looks like a navigable Facebook business page."""
    if "facebook.com/" not in url:
        return False
    try:
        path = url.split("facebook.com/", 1)[1].rstrip("/")
    except IndexError:
        return False
    if not path:
        return False
    first_segment = path.split("/")[0].split("?")[0].lower()
    return first_segment not in _FB_SKIP_PREFIXES


def _search_ddg_for_fb_urls(
    page, query: str
) -> List[Tuple[str, str]]:
    """Search DDG for Facebook business pages; return [(fb_url, ddg_title), ...]."""
    search_query = f"site:facebook.com/pages {query}"
    url = f"https://duckduckgo.com/?q={urllib.parse.quote(search_query)}&ia=web"
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    try:
        page.wait_for_selector(
            ".result__a, [data-testid='result-title-a'], article a",
            timeout=15000,
        )
    except Exception:
        logger.warning("facebook: DDG found no results for %r", query)
        return []

    fb_urls: List[Tuple[str, str]] = []
    seen: set = set()
    for el in page.query_selector_all(
        "[data-testid='result-title-a'][href], "
        "[data-testid='result-title'][href], "
        ".result__a[href], "
        "article a[href]"
    ):
        raw_href = el.get_attribute("href") or ""
        href = _decode_ddg_href(raw_href).split("?")[0].rstrip("/")
        ddg_title = el.inner_text().strip()
        if href not in seen and _is_fb_business_page(href):
            seen.add(href)
            fb_urls.append((href, ddg_title))
        if len(fb_urls) >= _MAX_PAGES * 2:
            break

    return fb_urls


def _extract_from_fb_page(
    page, fb_url: str, ddg_title: str, country_code: str
) -> Optional[BusinessListing]:
    """Visit one Facebook /about page and extract business data. Returns None on login wall or no phone."""
    about_url = fb_url + "/about"
    page.goto(about_url, wait_until="domcontentloaded", timeout=20000)
    page.wait_for_timeout(1200)

    current = page.url
    if "/login" in current or "checkpoint" in current or "login_form" in current:
        logger.debug("facebook: login wall on %s - skipping", fb_url)
        return None

    name_el = page.query_selector("h1, [data-testid='profile-name']")
    name = (name_el.inner_text().strip() if name_el else "") or ddg_title

    phone = _phone_from_page(page, country_code)
    if not phone:
        return None

    category_el = page.query_selector(
        "[data-testid='page-category'], .cxmmr5t8"
    )
    category = None
    if category_el:
        cat_text = category_el.inner_text().strip()
        if cat_text and len(cat_text) < 60:
            category = cat_text

    website_el = page.query_selector(
        "a[href^='http']:not([href*='facebook'])"
    )
    website = website_el.get_attribute("href") if website_el else None

    return BusinessListing(
        name=name or "Facebook Page",
        source="facebook_pages",
        phone=phone,
        website=website,
        category=category,
    )


def _visit_fb_page_in_isolation(
    fb_url: str, ddg_title: str, country_code: str
) -> Optional[BusinessListing]:
    """Dedicated isolated browser for one FB page; safe to call from a thread."""
    from playwright.sync_api import sync_playwright
    from playwright_stealth import Stealth

    def _attempt() -> Optional[BusinessListing]:
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
                page.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"})
                return _extract_from_fb_page(page, fb_url, ddg_title, country_code)
            finally:
                browser.close()

    try:
        return _attempt()
    except Exception as exc:
        logger.debug("facebook: isolated visit failed for %s: %s", fb_url, exc)
        return None


def _scrape_facebook_pages(
    page, query: str, country_code: str
) -> List[BusinessListing]:
    """Phase 1: DDG search for FB page URLs (serial, one browser).
    Phase 2: Visit each /about page concurrently via isolated browsers.
    """
    fb_urls = _search_ddg_for_fb_urls(page, query)
    if not fb_urls:
        return []

    targets = fb_urls[:_MAX_PAGES]
    logger.info("facebook: visiting %d FB pages concurrently", len(targets))

    listings: List[BusinessListing] = []
    with ThreadPoolExecutor(max_workers=_MAX_DETAIL_WORKERS) as pool:
        futures = {
            pool.submit(_visit_fb_page_in_isolation, fb_url, ddg_title, country_code): fb_url
            for fb_url, ddg_title in targets
        }
        for future in as_completed(futures):
            fb_url = futures[future]
            try:
                result = future.result()
                if result is not None:
                    listings.append(result)
            except Exception as exc:
                logger.debug("facebook: page %s failed: %s", fb_url, exc)

    return listings


def create_leads_from_facebook(
    query: str,
    country_code: str,
    campaign_id: str,
    user_id: str,
) -> int:
    """Scrape Facebook business pages via DDG, dedup by phone, upsert leads + deals.

    Uses concurrent isolated browsers for detail pages. Applies ICP filter before upsert.
    Returns count of new leads created.
    """
    logger.warning(
        "facebook: this source relies on unauthenticated Facebook access. "
        "Pages behind login walls are skipped. Consider google_maps or wa_groups for higher yield."
    )

    from playwright.sync_api import sync_playwright
    from playwright_stealth import Stealth

    all_listings: List[BusinessListing] = []

    def _run_search() -> List[BusinessListing]:
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
                page.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"})
                return _scrape_facebook_pages(page, query, country_code)
            finally:
                browser.close()

    try:
        all_listings = _scrape_retry(_run_search, max_attempts=2, base_delay=4.0, label="facebook:ddg")
    except Exception as exc:
        logger.error("facebook: scrape failed after retries: %s", exc)
        return 0

    logger.info("facebook: returned %d listings", len(all_listings))

    if not all_listings:
        return 0

    all_listings = _apply_icp_filter(all_listings, campaign_id, user_id)
    return upsert_listings_as_leads(all_listings, campaign_id, user_id)


def _apply_icp_filter(
    listings: List[BusinessListing], campaign_id: str, user_id: str
) -> List[BusinessListing]:
    """Load campaign and run ICP filter. Returns listings unchanged on any error."""
    try:
        from openoutreach.mongodb.models import Campaign
        from openoutreach.whatsapp.pipeline.icp_filter import filter_by_icp
        campaign = Campaign.get(campaign_id)
        if campaign:
            return filter_by_icp(listings, campaign, user_id)
    except Exception as exc:
        logger.warning("facebook: icp_filter error: %s - keeping all listings", exc)
    return listings
