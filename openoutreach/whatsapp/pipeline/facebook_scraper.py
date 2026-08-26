"""Facebook Business pages scraper.

Searches Facebook for business pages matching `query`, opens each page's
About section, and extracts phone numbers via tel: links or body text regex.

Note: Facebook heavily throttles unauthenticated browsing. This scraper runs
      in headed mode and gracefully skips pages that require login.

Entry point: create_leads_from_facebook(...)
"""
from __future__ import annotations

import logging
import re
import urllib.parse
from typing import List

from openoutreach.whatsapp.pipeline.upsert import BusinessListing, upsert_listings_as_leads
from openoutreach.whatsapp.pipeline.utils import normalize_phone as _normalize_phone

logger = logging.getLogger(__name__)

_MAX_PAGES = 20
_PHONE_RE = re.compile(r"(\+?[\d][\d\s\-\.\(\)]{5,18}[\d])")


def _phone_from_page(page) -> str:
    tel_el = page.query_selector("a[href^='tel:']")
    if tel_el:
        raw = (tel_el.get_attribute("href") or "").replace("tel:", "").strip()
        if raw:
            return raw
    try:
        body = page.inner_text("body")
    except Exception:
        body = ""
    for raw in _PHONE_RE.findall(body):
        candidate = raw.strip()
        if sum(c.isdigit() for c in candidate) >= 7:
            return candidate
    return ""


def _scrape_facebook_pages(
    page, query: str, country_code: str
) -> List[BusinessListing]:
    search_url = (
        f"https://www.facebook.com/search/pages/?q={urllib.parse.quote(query)}"
    )
    page.goto(search_url, wait_until="domcontentloaded", timeout=30000)

    # Dismiss cookie banner if present
    try:
        page.wait_for_selector(
            "[data-testid='cookie-policy-dialog-accept-button'], "
            "button[title='Allow all cookies'], "
            "button:has-text('Accept all')",
            timeout=5000,
        )
        page.click(
            "[data-testid='cookie-policy-dialog-accept-button'], "
            "button[title='Allow all cookies'], "
            "button:has-text('Accept all')",
            timeout=3000,
        )
    except Exception:
        pass

    # Redirect to login wall → abort
    if "/login" in page.url or "login_form" in page.url:
        logger.warning("facebook: login wall hit - skipping")
        return []

    try:
        page.wait_for_selector(
            "[data-testid='search-result'], div[role='article'], a[href*='/pages/']",
            timeout=15000,
        )
    except Exception:
        logger.warning("facebook: no page results for %r", query)
        return []

    # Collect page profile URLs from search results
    page_links: List[str] = []
    seen: set = set()
    for el in page.query_selector_all(
        "a[href*='/pages/'], a[href*='facebook.com/'], [data-testid='search-result'] a"
    ):
        href = (el.get_attribute("href") or "").split("?")[0]
        if (
            "facebook.com/" in href
            and "/search" not in href
            and "/events" not in href
            and "/groups" not in href
            and href not in seen
        ):
            seen.add(href)
            page_links.append(href)
        if len(page_links) >= _MAX_PAGES * 2:
            break

    listings: List[BusinessListing] = []
    for link in page_links[:_MAX_PAGES]:
        try:
            about_url = link.rstrip("/") + "/about"
            page.goto(about_url, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(1200)

            if "/login" in page.url:
                continue

            name_el = page.query_selector("h1, [data-testid='profile-name']")
            name = name_el.inner_text().strip() if name_el else ""

            raw_phone = _phone_from_page(page)
            if not raw_phone:
                continue
            phone = _normalize_phone(raw_phone, country_code)
            if not phone:
                continue

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

            listings.append(
                BusinessListing(
                    name=name or "Facebook Page",
                    phone=phone,
                    source="facebook_pages",
                    website=website,
                    category=category,
                )
            )
        except Exception as exc:
            logger.debug("facebook: error on %s: %s", link, exc)

    return listings


def create_leads_from_facebook(
    query: str,
    country_code: str,
    campaign_id: str,
    user_id: str,
) -> int:
    """Scrape Facebook business pages, dedup by phone, upsert leads + deals.

    Returns count of new leads created.
    """
    from playwright.sync_api import sync_playwright

    all_listings: List[BusinessListing] = []

    with sync_playwright() as pw:
        # Non-headless reduces bot-detection rate; no --no-sandbox flag needed
        browser = pw.chromium.launch(headless=False)
        try:
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()
            page.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"})
            listings = _scrape_facebook_pages(page, query, country_code)
            logger.info("facebook: returned %d listings", len(listings))
            all_listings.extend(listings)
        finally:
            browser.close()

    return upsert_listings_as_leads(all_listings, campaign_id, user_id)
