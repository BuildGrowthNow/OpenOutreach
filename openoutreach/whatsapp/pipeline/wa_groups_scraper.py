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
from openoutreach.whatsapp.pipeline.utils import normalize_phone as _normalize_phone

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


def _ddg_search_wa_links(page, query: str, country_code: str) -> List[Tuple[str, str]]:
    """Return [(phone_e164, name), ...] from DDG SERP results that contain wa.me links.

    Uses DOM-based per-result extraction so each phone is correlated with its
    result title. Falls back to full-page HTML scan for any phones missed by the
    DOM pass (DDG sometimes embeds wa.me in JavaScript-only nodes).
    """
    # Plain query — DDG silently ignores wildcard site: operators (site:*.com) so
    # they add noise without restricting results; omit them entirely.
    search_query = f"{query} wa.me"
    url = f"https://duckduckgo.com/?q={urllib.parse.quote(search_query)}&ia=web"
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    try:
        page.wait_for_selector(
            ", ".join(_DDG_RESULT_SELS),
            timeout=15000,
        )
    except Exception:
        logger.warning("wa_groups: DDG returned no results for %r", query)
        return []

    for _ in range(3):
        try:
            page.evaluate("window.scrollBy(0, window.innerHeight)")
            page.wait_for_timeout(800)
        except Exception:
            break

    results: List[Tuple[str, str]] = []
    seen: set = set()

    # DOM-based pass: correlate each phone with its result article title
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
        try:
            inner_html = el.inner_html() or ""
        except Exception:
            inner_html = ""

        # Scan both raw and URL-decoded HTML — DDG embeds wa.me in /l/?uddg= redirect hrefs
        phones_in_result: List[str] = []
        for source in (inner_html, urllib.parse.unquote(inner_html)):
            for raw in _WA_ME_RE.findall(source):
                phone = _phone_from_wa_me(raw, country_code)
                if phone and phone not in seen:
                    seen.add(phone)
                    phones_in_result.append(phone)

        if not phones_in_result:
            continue

        # Get title from the same result element
        name = ""
        for title_sel in _DDG_TITLE_SELS:
            try:
                title_el = el.query_selector(title_sel)
                if title_el:
                    raw_title = title_el.inner_text().strip()
                    if raw_title:
                        name = _clean_title(raw_title)
                        break
            except Exception:
                continue

        for phone in phones_in_result:
            results.append((phone, name))

        if len(results) >= _MAX_SEARCH_RESULTS:
            break

    # Fallback: full-page HTML scan for phones the DOM pass may have missed
    if len(results) < _MAX_SEARCH_RESULTS:
        try:
            full_html = page.content()
        except Exception:
            full_html = ""
        for source in (full_html, urllib.parse.unquote(full_html)):
            for raw in _WA_ME_RE.findall(source):
                phone = _phone_from_wa_me(raw, country_code)
                if phone and phone not in seen:
                    seen.add(phone)
                    results.append((phone, ""))
            if len(results) >= _MAX_SEARCH_RESULTS:
                break

    return results[:_MAX_SEARCH_RESULTS]


def _ddg_result_urls_with_titles(page, query: str) -> List[Tuple[str, str]]:
    """Return [(url, ddg_title), ...] for DDG web results.

    Decodes DDG redirect hrefs (/l/?uddg=...) so the list contains real target URLs.
    """
    url = f"https://duckduckgo.com/?q={urllib.parse.quote(query)}&ia=web"
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    try:
        page.wait_for_selector(
            ", ".join(_DDG_TITLE_SELS),
            timeout=15000,
        )
    except Exception:
        return []

    results: List[Tuple[str, str]] = []
    seen: set = set()
    for el in page.query_selector_all(
        "[data-testid='result-title-a'][href], "
        "[data-testid='result-title'][href], "
        ".result__a[href], "
        "article a[href], "
        ".result a[href]"
    ):
        raw_href = el.get_attribute("href") or ""
        href = _decode_ddg_href(raw_href).split("?")[0]
        title = el.inner_text().strip()
        if href.startswith("http") and href not in seen:
            seen.add(href)
            results.append((href, title))
        if len(results) >= _MAX_DETAIL_PAGES:
            break
    return results


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
    # Phase 1: scan DDG SERP for wa.me links — each phone paired with its result title
    direct_results = _ddg_search_wa_links(page, query, country_code)
    logger.info("wa_groups: %d phones from DDG SERP for %r", len(direct_results), query)

    # phone → best name known so far (from SERP title)
    phone_name: dict = {phone: name for phone, name in direct_results}
    direct_phones: set = set(phone_name.keys())

    # Phase 2: visit top result pages to discover more phones and upgrade empty names
    site_results = _ddg_result_urls_with_titles(page, f"{query} whatsapp contact phone")
    seen_extra: set = set(direct_phones)

    for site_url, ddg_title in site_results[:_MAX_DETAIL_PAGES]:
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
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
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
