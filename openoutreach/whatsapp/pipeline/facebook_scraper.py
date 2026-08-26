"""Facebook Business pages scraper.

Searches DuckDuckGo for Facebook business page URLs (site:facebook.com), then
visits each page's About section directly. This bypasses Facebook's login wall
on the FB search endpoint while still reaching publicly-accessible business pages.

Entry point: create_leads_from_facebook(...)
"""
from __future__ import annotations

import logging
import re
import urllib.parse
from typing import List, Tuple

from openoutreach.whatsapp.pipeline.upsert import BusinessListing, upsert_listings_as_leads
from openoutreach.whatsapp.pipeline.utils import (
    normalize_phone as _normalize_phone,
    random_user_agent as _random_user_agent,
)

logger = logging.getLogger(__name__)

_MAX_PAGES = 20
_PHONE_RE = re.compile(r"(\+?[\d][\d\s\-\.\(\)]{5,18}[\d])")

# DDG redirect marker — same pattern as wa_groups_scraper
_DDG_REDIRECT_MARKER = "/l/?uddg="

# Facebook path prefixes to skip when filtering search results
_FB_SKIP_PREFIXES = (
    "search", "login", "groups", "events", "watch",
    "marketplace", "gaming", "help", "policies",
)


def _decode_ddg_href(href: str) -> str:
    """Unwrap DDG redirect URL (/l/?uddg=...) if present."""
    if _DDG_REDIRECT_MARKER in href:
        try:
            return urllib.parse.unquote(href.split("uddg=")[-1].split("&")[0])
        except Exception:
            pass
    return href


def _phone_from_page(page) -> str:
    """Best-effort phone extraction: tel: link first, then body text regex."""
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


def _scrape_facebook_pages(
    page, query: str, country_code: str
) -> List[BusinessListing]:
    """Find Facebook business pages via DDG, then visit each /about page directly.

    Facebook's own /search/pages endpoint requires login; DDG site:facebook.com
    queries surface public business pages without touching the login wall.
    """
    # site:facebook.com/pages narrows to dedicated business page URLs
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

    fb_urls: List[Tuple[str, str]] = []  # (url, ddg_title)
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

    if not fb_urls:
        logger.warning("facebook: no usable FB page URLs from DDG for %r", query)
        return []

    listings: List[BusinessListing] = []
    for fb_url, ddg_title in fb_urls[:_MAX_PAGES]:
        try:
            about_url = fb_url + "/about"
            page.goto(about_url, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(1200)

            # Skip if Facebook redirected to login or checkpoint
            current = page.url
            if "/login" in current or "checkpoint" in current or "login_form" in current:
                logger.debug("facebook: login wall on %s — skipping", fb_url)
                continue

            name_el = page.query_selector("h1, [data-testid='profile-name']")
            name = (name_el.inner_text().strip() if name_el else "") or ddg_title

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
                    source="facebook_pages",
                    phone=phone,
                    website=website,
                    category=category,
                )
            )
        except Exception as exc:
            logger.debug("facebook: error on %s: %s", fb_url, exc)

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
        from playwright_stealth import Stealth
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
            listings = _scrape_facebook_pages(page, query, country_code)
            logger.info("facebook: returned %d listings", len(listings))
            all_listings.extend(listings)
        finally:
            browser.close()

    return upsert_listings_as_leads(all_listings, campaign_id, user_id)
