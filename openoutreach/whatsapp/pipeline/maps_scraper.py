"""Maps scraper - multi-backend Playwright scraper for phone leads.

Supported backends: google_maps, bing_maps, duckduckgo_maps.
Entry point: create_leads_from_maps(...)
"""

from __future__ import annotations

import logging
import urllib.parse
from typing import List, Optional

from openoutreach.whatsapp.pipeline.upsert import BusinessListing, upsert_listings_as_leads
from openoutreach.whatsapp.pipeline.utils import normalize_phone as _normalize_phone

logger = logging.getLogger(__name__)

_DEFAULT_BACKENDS = ["google_maps", "bing_maps", "duckduckgo_maps"]
_MAX_LISTINGS = 50
_SCROLL_REPEATS = 3
_SCROLL_PAUSE_MS = 1000


def _scroll_results(page, selector: str) -> None:
    """Scroll a results container to load more items."""
    for _ in range(_SCROLL_REPEATS):
        try:
            container = page.query_selector(selector)
            if container:
                container.evaluate("el => el.scrollBy(0, el.scrollHeight)")
            else:
                page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
        except Exception:
            page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
        page.wait_for_timeout(_SCROLL_PAUSE_MS)


def _scrape_google_maps(page, query: str, country_code: str) -> List[BusinessListing]:
    import re as _re

    url = f"https://www.google.com/maps/search/{urllib.parse.quote(query)}"
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    try:
        page.wait_for_selector('[role="feed"]', timeout=15000)
    except Exception:
        logger.warning("google_maps: feed not found for query %r", query)
        return []

    _scroll_results(page, '[role="feed"]')

    # Collect place links directly — stable across Google Maps DOM updates
    seen_hrefs: set = set()
    place_urls: list = []
    for el in page.query_selector_all('[role="feed"] a[href*="/maps/place/"]'):
        href = el.get_attribute("href") or ""
        if not href:
            continue
        if href.startswith("/"):
            href = "https://www.google.com" + href
        base_href = href.split("?")[0]
        if base_href not in seen_hrefs:
            seen_hrefs.add(base_href)
            place_urls.append(href)
        if len(place_urls) >= _MAX_LISTINGS:
            break

    if not place_urls:
        logger.warning("google_maps: no place links found for query %r", query)
        return []

    listings: List[BusinessListing] = []
    for place_url in place_urls:
        try:
            page.goto(place_url, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(1200)

            # Name: multiple fallbacks as Google rotates class names
            name = ""
            for name_sel in ["h1.DUwDvf", "h1[data-attrid='title']", "h1"]:
                name_el = page.query_selector(name_sel)
                if name_el:
                    name = name_el.inner_text().strip()
                    if name:
                        break

            # Phone: data-item-id prefix has been stable for years
            raw_phone = ""
            phone_el = page.query_selector('[data-item-id^="phone:"]')
            if phone_el:
                raw_phone = (
                    phone_el.get_attribute("aria-label") or phone_el.inner_text() or ""
                ).replace("Phone:", "").replace("Telefone:", "").replace("Teléfono:", "").strip()

            if not raw_phone:
                continue

            normalized = _normalize_phone(raw_phone, country_code)
            if not normalized:
                continue

            addr_el = page.query_selector('[data-item-id="address"]')
            address = addr_el.inner_text().strip() if addr_el else None

            website_el = page.query_selector('[data-item-id^="authority"]')
            website = None
            if website_el:
                website = website_el.get_attribute("href") or website_el.inner_text().strip() or None

            category_el = page.query_selector('button[jsaction*="category"], .DkEaL')
            category = category_el.inner_text().strip() if category_el else None

            rating: Optional[float] = None
            review_count: Optional[int] = None
            rating_el = page.query_selector(".MW4etd, [data-value='Rating']")
            if rating_el:
                try:
                    rating = float(rating_el.inner_text().strip().replace(",", "."))
                except (ValueError, AttributeError):
                    pass
            reviews_el = page.query_selector(
                '.UY7F9, [aria-label*="reviews"], [aria-label*="avaliações"], [aria-label*="reseñas"]'
            )
            if reviews_el:
                raw_rc = reviews_el.get_attribute("aria-label") or reviews_el.inner_text() or ""
                m = _re.search(r"[\d]+", raw_rc.replace(",", "").replace(".", ""))
                if m:
                    try:
                        review_count = int(m.group())
                    except ValueError:
                        pass

            listings.append(
                BusinessListing(
                    name=name or "Unknown",
                    phone=normalized,
                    website=website,
                    address=address,
                    category=category,
                    source="google_maps",
                    rating=rating,
                    review_count=review_count,
                )
            )
        except Exception as exc:
            logger.debug("google_maps: error parsing place %s: %s", place_url, exc)

    return listings


def _scrape_bing_maps(page, query: str, country_code: str) -> List[BusinessListing]:
    url = f"https://www.bing.com/maps?q={urllib.parse.quote(query)}"
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    try:
        page.wait_for_selector(".listings-container", timeout=15000)
    except Exception:
        logger.warning("bing_maps: listings-container not found for query %r", query)
        return []

    _scroll_results(page, ".listings-container")

    listings: List[BusinessListing] = []
    cards = page.query_selector_all(".listings-container .listing")

    for card in cards[:_MAX_LISTINGS]:
        try:
            name_el = card.query_selector(".b-title, .listing-title")
            name = name_el.inner_text().strip() if name_el else ""

            phone_el = card.query_selector(".b-phone, [data-phone]")
            raw_phone = ""
            if phone_el:
                raw_phone = (
                    phone_el.get_attribute("data-phone")
                    or phone_el.inner_text().strip()
                )

            if not raw_phone:
                continue

            normalized = _normalize_phone(raw_phone, country_code)
            if not normalized:
                continue

            addr_el = card.query_selector(".b-address, .listing-address")
            address = addr_el.inner_text().strip() if addr_el else None

            website_el = card.query_selector("a.b-website, a[href^='http']")
            website = website_el.get_attribute("href") if website_el else None

            listings.append(
                BusinessListing(
                    name=name or "Unknown",
                    phone=normalized,
                    website=website,
                    address=address,
                    category=None,
                    source="bing_maps",
                )
            )
        except Exception as exc:
            logger.debug("bing_maps: error parsing card: %s", exc)

    return listings


def _scrape_duckduckgo_maps(
    page, query: str, country_code: str
) -> List[BusinessListing]:
    url = (
        f"https://duckduckgo.com/?q={urllib.parse.quote(query)}&ia=maps&iaxm=maps"
    )
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    try:
        page.wait_for_selector(".map-result", timeout=15000)
    except Exception:
        logger.warning("duckduckgo_maps: .map-result not found for query %r", query)
        return []

    _scroll_results(page, "body")

    listings: List[BusinessListing] = []
    cards = page.query_selector_all(".map-result")

    for card in cards[:_MAX_LISTINGS]:
        try:
            name_el = card.query_selector(".map-result__title, .result__title")
            name = name_el.inner_text().strip() if name_el else ""

            phone_el = card.query_selector(".map-result__phone")
            raw_phone = phone_el.inner_text().strip() if phone_el else ""

            if not raw_phone:
                continue

            normalized = _normalize_phone(raw_phone, country_code)
            if not normalized:
                continue

            addr_el = card.query_selector(".map-result__address")
            address = addr_el.inner_text().strip() if addr_el else None

            listings.append(
                BusinessListing(
                    name=name or "Unknown",
                    phone=normalized,
                    website=None,
                    address=address,
                    category=None,
                    source="duckduckgo_maps",
                )
            )
        except Exception as exc:
            logger.debug("duckduckgo_maps: error parsing card: %s", exc)

    return listings


_BACKEND_FN = {
    "google_maps": _scrape_google_maps,
    "bing_maps": _scrape_bing_maps,
    "duckduckgo_maps": _scrape_duckduckgo_maps,
}


def create_leads_from_maps(
    query: str,
    country_code: str,
    campaign_id: str,
    user_id: str,
    backends: Optional[List[str]] = None,
    min_rating: Optional[float] = None,
) -> int:
    """Scrape maps backends with a single shared browser, dedup by phone, upsert Leads + Deals.

    min_rating: if set, only listings with rating >= min_rating (or no rating data) are kept.
    Returns count of new leads created.
    """
    from playwright.sync_api import sync_playwright

    active_backends = [b for b in (backends or _DEFAULT_BACKENDS) if b in _BACKEND_FN]
    if not active_backends:
        logger.warning("maps_scraper: no valid backends in %s", backends)
        return 0

    all_listings: List[BusinessListing] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"})
            for backend in active_backends:
                try:
                    results = _BACKEND_FN[backend](page, query, country_code)
                    logger.info("maps_scraper: %s returned %d listings", backend, len(results))
                    all_listings.extend(results)
                except Exception as exc:
                    logger.warning("maps_scraper: backend %s failed: %s", backend, exc)
        finally:
            browser.close()

    if min_rating is not None:
        before = len(all_listings)
        all_listings = [
            lst for lst in all_listings
            if lst.rating is None or lst.rating >= min_rating
        ]
        logger.info(
            "maps_scraper: min_rating=%.1f kept %d/%d listings",
            min_rating, len(all_listings), before,
        )

    return upsert_listings_as_leads(all_listings, campaign_id, user_id)
