"""WhatsApp lead discovery via public wa.me deep links.

Strategy: search DuckDuckGo for `wa.me/+<country_code>` patterns on business
websites. Each `wa.me/<phone>` link is a direct contact link published by a
business — higher-intent than classified listings because the business itself
placed it on their site.

Also visits top SERP result pages to harvest additional wa.me / tel links
and build a richer lead set without requiring a WhatsApp session.

Entry point: create_leads_from_wa_links(...)
"""
from __future__ import annotations

import logging
import re
import urllib.parse
from typing import List, Optional

from openoutreach.whatsapp.pipeline.upsert import BusinessListing, upsert_listings_as_leads

logger = logging.getLogger(__name__)

_MAX_SEARCH_RESULTS = 60
_MAX_DETAIL_PAGES = 30
_WA_ME_RE = re.compile(r"wa\.me/(\+?[\d]{7,15})")


def _normalize_phone(raw: str, country_code: str) -> Optional[str]:
    try:
        import phonenumbers

        parsed = phonenumbers.parse(raw, country_code.upper())
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.E164
            )
    except Exception:
        pass
    return None


def _phone_from_wa_me(raw: str, country_code: str) -> Optional[str]:
    digits = raw.replace("+", "").replace(" ", "")
    return _normalize_phone(f"+{digits}", country_code)


def _ddg_search_wa_links(page, query: str, country_code: str) -> List[str]:
    search_query = f"{query} wa.me site:*.com OR site:*.net OR site:*.org"
    url = f"https://duckduckgo.com/?q={urllib.parse.quote(search_query)}&ia=web"
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    try:
        page.wait_for_selector(".result, [data-testid='result']", timeout=15000)
    except Exception:
        logger.warning("wa_groups: DDG returned no results for %r", query)
        return []

    for _ in range(3):
        try:
            page.evaluate("window.scrollBy(0, window.innerHeight)")
            page.wait_for_timeout(800)
        except Exception:
            break

    try:
        html = page.content()
    except Exception:
        html = ""

    phones: List[str] = []
    seen: set = set()
    for raw in _WA_ME_RE.findall(html):
        phone = _phone_from_wa_me(raw, country_code)
        if phone and phone not in seen:
            seen.add(phone)
            phones.append(phone)
        if len(phones) >= _MAX_SEARCH_RESULTS:
            break

    return phones


def _ddg_result_urls(page, query: str) -> List[str]:
    url = f"https://duckduckgo.com/?q={urllib.parse.quote(query)}&ia=web"
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    try:
        page.wait_for_selector(
            ".result__url, [data-testid='result-extras-url-link']", timeout=15000
        )
    except Exception:
        return []

    urls: List[str] = []
    seen: set = set()
    for el in page.query_selector_all(
        ".result__a[href], [data-testid='result-title-a'][href]"
    ):
        href = (el.get_attribute("href") or "").split("?")[0]
        if href.startswith("http") and href not in seen:
            seen.add(href)
            urls.append(href)
        if len(urls) >= _MAX_DETAIL_PAGES:
            break
    return urls


def _phones_from_site_page(page, site_url: str, country_code: str) -> List[str]:
    try:
        page.goto(site_url, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(700)
        html = page.content()
    except Exception:
        return []

    phones: List[str] = []
    seen: set = set()

    for raw in _WA_ME_RE.findall(html):
        phone = _phone_from_wa_me(raw, country_code)
        if phone and phone not in seen:
            seen.add(phone)
            phones.append(phone)

    for el in page.query_selector_all("a[href^='tel:']"):
        raw = (el.get_attribute("href") or "").replace("tel:", "").strip()
        phone = _normalize_phone(raw, country_code)
        if phone and phone not in seen:
            seen.add(phone)
            phones.append(phone)

    return phones


def _scrape_wa_links(page, query: str, country_code: str) -> List[BusinessListing]:
    direct_phones = _ddg_search_wa_links(page, query, country_code)
    logger.info("wa_groups: %d phones from DDG SERP for %r", len(direct_phones), query)

    site_urls = _ddg_result_urls(page, f"{query} whatsapp contact phone")
    extra_phones: List[str] = []
    seen_extra: set = set(direct_phones)
    for url in site_urls[:_MAX_DETAIL_PAGES]:
        for phone in _phones_from_site_page(page, url, country_code):
            if phone not in seen_extra:
                seen_extra.add(phone)
                extra_phones.append(phone)

    all_phones = direct_phones + extra_phones
    logger.info("wa_groups: %d total unique phones for %r", len(all_phones), query)

    listings: List[BusinessListing] = []
    seen_listings: set = set()
    for phone in all_phones:
        if phone not in seen_listings:
            seen_listings.add(phone)
            listings.append(
                BusinessListing(
                    name=phone,
                    phone=phone,
                    source="wa_groups",
                    category=query,
                )
            )

    return listings


def create_leads_from_wa_links(
    query: str,
    country_code: str,
    campaign_id: str,
    user_id: str,
) -> int:
    """Discover WhatsApp leads via public wa.me links on business websites.

    Returns count of new leads created.
    """
    from playwright.sync_api import sync_playwright

    all_listings: List[BusinessListing] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"})
            listings = _scrape_wa_links(page, query, country_code)
            all_listings.extend(listings)
        finally:
            browser.close()

    return upsert_listings_as_leads(all_listings, campaign_id, user_id)
