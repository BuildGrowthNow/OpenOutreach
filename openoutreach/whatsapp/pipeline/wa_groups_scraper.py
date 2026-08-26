"""WhatsApp lead discovery via public wa.me deep links.

Strategy: search DuckDuckGo for `wa.me/+<country_code>` patterns on business
websites. Each `wa.me/<phone>` link is a direct contact link published by a
business - higher-intent than classified listings because the business itself
placed it on their site.

Also visits top SERP result pages to harvest additional wa.me / tel links
and build a richer lead set without requiring a WhatsApp session.

Entry point: create_leads_from_wa_links(...)
"""
from __future__ import annotations

import logging
import re
import urllib.parse
from typing import List, Optional, Tuple

from openoutreach.whatsapp.pipeline.upsert import BusinessListing, upsert_listings_as_leads
from openoutreach.whatsapp.pipeline.utils import (
    normalize_phone as _normalize_phone,
    random_user_agent as _random_user_agent,
)

logger = logging.getLogger(__name__)

_MAX_SEARCH_RESULTS = 60
_MAX_DETAIL_PAGES = 30
_WA_ME_RE = re.compile(r"wa\.me/(\+?[\d]{7,15})")

# DDG wraps some result URLs in redirect hrefs — must decode to get real targets
_DDG_REDIRECT_MARKER = "/l/?uddg="

# Result container selectors — DDG rotates these; first match wins
_DDG_RESULT_SELS = [
    "article",
    "[data-testid='result']",
    ".result",
    "li[data-nr]",
]

# Title link selectors within a result element
_DDG_TITLE_SELS = [
    "[data-testid='result-title-a']",
    "h2 a",
    "h3 a",
    ".result__title a",
    ".result__a",
]


def _decode_ddg_href(href: str) -> str:
    """Unwrap DDG redirect URL (/l/?uddg=...) if present; return href unchanged otherwise."""
    if _DDG_REDIRECT_MARKER in href:
        try:
            return urllib.parse.unquote(href.split("uddg=")[-1].split("&")[0])
        except Exception:
            pass
    return href


def _phone_from_wa_me(raw: str, country_code: str) -> Optional[str]:
    digits = raw.replace("+", "").replace(" ", "")
    return _normalize_phone(f"+{digits}", country_code)


def _clean_title(raw: str) -> str:
    """Strip common domain-suffix noise like ' | Company' or ' - Site'."""
    for sep in [" | ", " - ", " — ", " :: ", " · "]:
        if sep in raw:
            raw = raw.split(sep)[0].strip()
            break
    return raw


def _ddg_search_and_collect(
    page, query: str, country_code: str
) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
    """Single DDG search that returns both SERP phones and result URLs.

    Eliminates the second DDG request that the old split design required.

    Returns:
        phones_with_names: [(phone_e164, name), ...] — wa.me phones found in SERP
        result_urls:       [(url, title), ...] — result page URLs to visit for more phones
    """
    # Plain query — DDG silently ignores wildcard site: operators so omit them
    search_query = f"{query} wa.me"
    url = f"https://duckduckgo.com/?q={urllib.parse.quote(search_query)}&ia=web"
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    try:
        page.wait_for_selector(", ".join(_DDG_RESULT_SELS), timeout=15000)
    except Exception:
        logger.warning("wa_groups: DDG returned no results for %r", query)
        return [], []

    for _ in range(3):
        try:
            page.evaluate("window.scrollBy(0, window.innerHeight)")
            page.wait_for_timeout(800)
        except Exception:
            break

    phones_with_names: List[Tuple[str, str]] = []
    result_urls: List[Tuple[str, str]] = []
    seen_phones: set = set()
    seen_urls: set = set()

    # Collect all result elements from the first selector that yields any
    result_els = []
    for sel in _DDG_RESULT_SELS:
        try:
            els = page.query_selector_all(sel)
            if els:
                result_els = els
                break
        except Exception:
            continue

    for el in result_els:
        # Extract result URL + title
        for title_sel in _DDG_TITLE_SELS:
            try:
                title_el = el.query_selector(title_sel)
                if title_el:
                    raw_href = title_el.get_attribute("href") or ""
                    href = _decode_ddg_href(raw_href).split("?")[0]
                    title = _clean_title(title_el.inner_text().strip())
                    if href.startswith("http") and href not in seen_urls:
                        seen_urls.add(href)
                        result_urls.append((href, title))
                    break
            except Exception:
                continue

        # Extract wa.me phones from this result (raw + URL-decoded HTML)
        try:
            inner_html = el.inner_html() or ""
        except Exception:
            inner_html = ""

        phones_in_result: List[str] = []
        for source in (inner_html, urllib.parse.unquote(inner_html)):
            for raw in _WA_ME_RE.findall(source):
                phone = _phone_from_wa_me(raw, country_code)
                if phone and phone not in seen_phones:
                    seen_phones.add(phone)
                    phones_in_result.append(phone)

        if phones_in_result:
            # Get title for name context
            name = ""
            for title_sel in _DDG_TITLE_SELS:
                try:
                    title_el = el.query_selector(title_sel)
                    if title_el:
                        name = _clean_title(title_el.inner_text().strip())
                        break
                except Exception:
                    continue
            for phone in phones_in_result:
                phones_with_names.append((phone, name))

        if len(phones_with_names) >= _MAX_SEARCH_RESULTS:
            break

    # Fallback: full-page HTML scan for phones the DOM pass may have missed
    if len(phones_with_names) < _MAX_SEARCH_RESULTS:
        try:
            full_html = page.content()
        except Exception:
            full_html = ""
        for source in (full_html, urllib.parse.unquote(full_html)):
            for raw in _WA_ME_RE.findall(source):
                phone = _phone_from_wa_me(raw, country_code)
                if phone and phone not in seen_phones:
                    seen_phones.add(phone)
                    phones_with_names.append((phone, ""))
            if len(phones_with_names) >= _MAX_SEARCH_RESULTS:
                break

    return phones_with_names[:_MAX_SEARCH_RESULTS], result_urls


def _listings_from_site_page(
    page, site_url: str, country_code: str, fallback_name: str = ""
) -> List[Tuple[str, str]]:
    """Return [(phone, name), ...] extracted from a business website page.

    Name priority: og:site_name > og:title > <title> > fallback_name.
    """
    try:
        page.goto(site_url, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(700)
        html = page.content()
    except Exception:
        return []

    name = ""
    for meta_sel, attr in [
        ('meta[property="og:site_name"]', "content"),
        ('meta[property="og:title"]', "content"),
        ('meta[name="title"]', "content"),
    ]:
        try:
            el = page.query_selector(meta_sel)
            if el:
                val = el.get_attribute(attr) or ""
                if val.strip():
                    name = _clean_title(val.strip())
                    break
        except Exception:
            pass
    if not name:
        try:
            title_el = page.query_selector("title")
            if title_el:
                name = _clean_title(title_el.inner_text().strip())
        except Exception:
            pass
    if not name:
        name = _clean_title(fallback_name)

    page_results: List[Tuple[str, str]] = []
    seen: set = set()

    for raw in _WA_ME_RE.findall(html):
        phone = _phone_from_wa_me(raw, country_code)
        if phone and phone not in seen:
            seen.add(phone)
            page_results.append((phone, name))

    for el in page.query_selector_all("a[href^='tel:']"):
        raw = (el.get_attribute("href") or "").replace("tel:", "").strip()
        phone = _normalize_phone(raw, country_code)
        if phone and phone not in seen:
            seen.add(phone)
            page_results.append((phone, name))

    return page_results


def _scrape_wa_links(page, query: str, country_code: str) -> List[BusinessListing]:
    # Single DDG request: extract both SERP phones and result URLs to visit
    direct_results, site_urls = _ddg_search_and_collect(page, query, country_code)
    logger.info("wa_groups: %d phones from DDG SERP for %r", len(direct_results), query)

    # phone → best name known so far (from SERP title)
    phone_name: dict = {phone: name for phone, name in direct_results}
    direct_phones: set = set(phone_name.keys())
    seen_extra: set = set(direct_phones)

    # Phase 2: visit the same result pages for more phones + better name data
    for site_url, ddg_title in site_urls[:_MAX_DETAIL_PAGES]:
        for phone, page_name in _listings_from_site_page(
            page, site_url, country_code, fallback_name=ddg_title
        ):
            if phone not in seen_extra:
                seen_extra.add(phone)
                phone_name[phone] = page_name
            elif phone in direct_phones and not phone_name.get(phone) and page_name:
                # Upgrade: replace empty SERP name with a real page-visit name
                phone_name[phone] = page_name

    all_phones = list(phone_name.keys())
    logger.info("wa_groups: %d total unique phones for %r", len(all_phones), query)

    return [
        BusinessListing(
            name=phone_name.get(phone, ""),
            source="wa_groups",
            phone=phone,
            category=query,
        )
        for phone in all_phones
    ]


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
            listings = _scrape_wa_links(page, query, country_code)
            all_listings.extend(listings)
        finally:
            browser.close()

    return upsert_listings_as_leads(all_listings, campaign_id, user_id)
