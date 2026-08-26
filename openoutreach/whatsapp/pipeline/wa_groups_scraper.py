"""WhatsApp lead discovery via public wa.me deep links.

Strategy: search DuckDuckGo for `wa.me/+<country_code>` patterns on business
websites. Each `wa.me/<phone>` link is a direct contact link published by a
business - higher-intent than classified listings because the business itself
placed it on their site.

Phase 1: One DDG request - collect direct wa.me phones from SERP + result URLs.
Phase 2: Visit result pages concurrently via isolated browsers to harvest
additional wa.me / tel links and build a richer name-enriched lead set.

Entry point: create_leads_from_wa_links(...)
"""
from __future__ import annotations

import logging
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Tuple

from openoutreach.whatsapp.pipeline.icp_filter import apply_icp_filter as _apply_icp_filter
from openoutreach.whatsapp.pipeline.upsert import BusinessListing, upsert_listings_as_leads
from openoutreach.whatsapp.pipeline.utils import (
    apply_resource_block as _apply_resource_block,
    decode_ddg_href as _decode_ddg_href,
    normalize_phone as _normalize_phone,
    random_user_agent as _random_user_agent,
    scrape_retry as _scrape_retry,
)

logger = logging.getLogger(__name__)

_MAX_SEARCH_RESULTS = 100
_MAX_DETAIL_PAGES = 50
_MAX_DETAIL_WORKERS = 6
_DDG_PAGE2_THRESHOLD = 20
_WA_ME_RE = re.compile(r"wa\.me/(\+?[\d]{7,15})")

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


def _collect_from_ddg_page(
    page,
    country_code: str,
    seen_phones: set,
    seen_urls: set,
    max_phones: int,
    scroll_passes: int = 6,
) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
    """Extract wa.me phones and result URLs from the currently loaded DDG SERP page.

    Mutates seen_phones and seen_urls so callers share dedup state across page loads.
    """
    for _ in range(scroll_passes):
        try:
            page.evaluate("window.scrollBy(0, window.innerHeight)")
            page.wait_for_timeout(700)
        except Exception:
            break

    phones: List[Tuple[str, str]] = []
    urls: List[Tuple[str, str]] = []

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
        for title_sel in _DDG_TITLE_SELS:
            try:
                title_el = el.query_selector(title_sel)
                if title_el:
                    raw_href = title_el.get_attribute("href") or ""
                    href = _decode_ddg_href(raw_href).split("?")[0]
                    title = _clean_title(title_el.inner_text().strip())
                    if href.startswith("http") and href not in seen_urls:
                        seen_urls.add(href)
                        urls.append((href, title))
                    break
            except Exception:
                continue

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
                phones.append((phone, name))

        if len(phones) >= max_phones:
            break

    # Fallback: full-page HTML scan for phones the DOM pass may have missed
    if len(phones) < max_phones:
        try:
            full_html = page.content()
        except Exception:
            full_html = ""
        for source in (full_html, urllib.parse.unquote(full_html)):
            for raw in _WA_ME_RE.findall(source):
                phone = _phone_from_wa_me(raw, country_code)
                if phone and phone not in seen_phones:
                    seen_phones.add(phone)
                    phones.append((phone, ""))
            if len(phones) >= max_phones:
                break

    return phones, urls


def _ddg_search_and_collect(
    page, query: str, country_code: str
) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
    """DDG search for wa.me links. Tries page 2 (s=30 offset) when page 1 is sparse.

    Returns:
        phones_with_names: [(phone_e164, name), ...] — wa.me phones found in SERP
        result_urls:       [(url, title), ...] — result page URLs to visit for more phones
    """
    search_query = f'{query} "wa.me/"'
    url = f"https://duckduckgo.com/?q={urllib.parse.quote(search_query)}&ia=web"
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    try:
        page.wait_for_selector(", ".join(_DDG_RESULT_SELS), timeout=15000)
    except Exception:
        logger.warning("wa_groups: DDG returned no results for %r", query)
        return [], []

    seen_phones: set = set()
    seen_urls: set = set()

    phones, urls = _collect_from_ddg_page(
        page, country_code, seen_phones, seen_urls, _MAX_SEARCH_RESULTS
    )
    logger.info("wa_groups: %d phones from DDG page 1 for %r", len(phones), query)

    # Page 2 via s=30 offset when first pass is sparse
    if len(phones) < _DDG_PAGE2_THRESHOLD:
        url_p2 = f"https://duckduckgo.com/?q={urllib.parse.quote(search_query)}&ia=web&s=30"
        try:
            page.goto(url_p2, wait_until="domcontentloaded", timeout=25000)
            page.wait_for_selector(", ".join(_DDG_RESULT_SELS), timeout=10000)
            extra_phones, extra_urls = _collect_from_ddg_page(
                page, country_code, seen_phones, seen_urls,
                _MAX_SEARCH_RESULTS - len(phones), scroll_passes=4,
            )
            phones.extend(extra_phones)
            urls.extend(extra_urls)
            if extra_phones:
                logger.info(
                    "wa_groups: DDG page 2 added %d phones for %r", len(extra_phones), query
                )
        except Exception as exc:
            logger.debug("wa_groups: DDG page 2 failed for %r: %s", query, exc)

    return phones[:_MAX_SEARCH_RESULTS], urls


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


def _visit_site_in_isolation(
    site_url: str, country_code: str, fallback_name: str
) -> List[Tuple[str, str]]:
    """Dedicated isolated browser for one detail page; safe to call from a thread."""
    from playwright.sync_api import sync_playwright
    from playwright_stealth import Stealth

    try:
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
                return _listings_from_site_page(page, site_url, country_code, fallback_name)
            finally:
                browser.close()
    except Exception as exc:
        logger.debug("wa_groups: isolated visit failed for %s: %s", site_url, exc)
        return []


def _bing_search_and_collect(
    page, query: str, country_code: str
) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
    """Bing fallback used when DDG yields 0 phones and 0 URLs."""
    search_query = f'{query} "wa.me/"'
    url = f"https://www.bing.com/search?q={urllib.parse.quote(search_query)}"
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    try:
        page.wait_for_selector("#b_results .b_algo, #b_results li", timeout=15000)
    except Exception:
        logger.warning("wa_groups: Bing fallback found no results for %r", query)
        return [], []

    phones_with_names: List[Tuple[str, str]] = []
    result_urls: List[Tuple[str, str]] = []
    seen_phones: set = set()
    seen_urls: set = set()

    for el in page.query_selector_all("#b_results .b_algo h2 a"):
        raw_href = el.get_attribute("href") or ""
        if not raw_href.startswith("http"):
            continue
        href = raw_href.split("?")[0].rstrip("/")
        title = _clean_title(el.inner_text().strip())
        if href not in seen_urls:
            seen_urls.add(href)
            result_urls.append((href, title))

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


def _scrape_wa_links(page, query: str, country_code: str) -> List[BusinessListing]:
    # Phase 1: single DDG request — direct phones + URLs to visit
    direct_results, site_urls = _ddg_search_and_collect(page, query, country_code)
    logger.info("wa_groups: %d phones from DDG SERP for %r", len(direct_results), query)

    # Bing fallback when DDG yields nothing
    if not direct_results and not site_urls:
        logger.info("wa_groups: DDG empty — trying Bing fallback for %r", query)
        direct_results, site_urls = _bing_search_and_collect(page, query, country_code)
        logger.info("wa_groups: Bing returned %d phones for %r", len(direct_results), query)

    phone_name: dict = {phone: name for phone, name in direct_results}
    direct_phones: set = set(phone_name.keys())
    seen_extra: set = set(direct_phones)

    # Phase 2: visit result pages concurrently via isolated browsers
    targets = site_urls[:_MAX_DETAIL_PAGES]
    if targets:
        with ThreadPoolExecutor(max_workers=_MAX_DETAIL_WORKERS) as pool:
            futures = {
                pool.submit(_visit_site_in_isolation, site_url, country_code, ddg_title): (site_url, ddg_title)
                for site_url, ddg_title in targets
            }
            for future in as_completed(futures):
                site_url, _ = futures[future]
                try:
                    results = future.result()
                    for phone, page_name in results:
                        if phone not in seen_extra:
                            seen_extra.add(phone)
                            phone_name[phone] = page_name
                        elif phone in direct_phones and not phone_name.get(phone) and page_name:
                            phone_name[phone] = page_name
                except Exception as exc:
                    logger.debug("wa_groups: detail visit %s failed: %s", site_url, exc)

    all_phones = list(phone_name.keys())
    logger.info("wa_groups: %d total unique phones for %r", len(all_phones), query)

    return [
        BusinessListing(
            name=phone_name.get(phone, ""),
            source="wa_groups",
            phone=phone,
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

    Uses concurrent isolated browsers for detail page visits. Applies ICP filter before upsert.
    Returns count of new leads created.
    """
    from playwright.sync_api import sync_playwright
    from playwright_stealth import Stealth

    def _run_ddg_search() -> List[BusinessListing]:
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
                return _scrape_wa_links(page, query, country_code)
            finally:
                browser.close()

    all_listings: List[BusinessListing] = []
    try:
        all_listings = _scrape_retry(_run_ddg_search, max_attempts=2, base_delay=4.0, label="wa_groups:ddg")
    except Exception as exc:
        logger.error("wa_groups: scrape failed after retries: %s", exc)
        return 0

    if not all_listings:
        from openoutreach.whatsapp.pipeline.alerts import fire_scrape_zero_results
        fire_scrape_zero_results(campaign_id, user_id, "wa_groups", query)
        return 0

    # Skip phones already in DB — saves detail visits + ICP tokens on re-runs
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
        logger.warning("wa_groups: dedup pre-fetch failed: %s", exc)

    if already_known:
        before = len(all_listings)
        all_listings = [
            lst for lst in all_listings
            if not lst.phone or lst.phone not in already_known
        ]
        skipped = before - len(all_listings)
        if skipped:
            logger.info("wa_groups: dedup removed %d already-known phones", skipped)

    all_listings = _apply_icp_filter(all_listings, campaign_id, user_id, label="wa_groups")
    return upsert_listings_as_leads(all_listings, campaign_id, user_id)
