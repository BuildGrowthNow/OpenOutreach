"""Maps scraper - multi-backend Playwright scraper for phone leads.

Supported backends: google_maps, bing_maps, duckduckgo_maps.
Entry point: create_leads_from_maps(...)
"""

from __future__ import annotations

import logging
import random
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

from openoutreach.whatsapp.pipeline.upsert import BusinessListing, upsert_listings_as_leads
from openoutreach.whatsapp.pipeline.utils import (
    normalize_phone as _normalize_phone,
    random_user_agent as _random_user_agent,
    scrape_retry as _scrape_retry,
)

logger = logging.getLogger(__name__)

_DEFAULT_BACKENDS = ["google_maps", "bing_maps", "duckduckgo_maps"]
_MAX_LISTINGS = 50
_SCROLL_PAUSE_MS = 1200
_MAX_SCROLL_ROUNDS = 12


def _scroll_until_stable(page, selector: str) -> None:
    """Scroll until two consecutive rounds produce no new children."""
    stale = 0
    prev_count = 0
    for _ in range(_MAX_SCROLL_ROUNDS):
        try:
            current_count = len(page.query_selector_all(f"{selector} > *"))
        except Exception:
            current_count = prev_count
        try:
            el = page.query_selector(selector)
            if el:
                el.evaluate("el => el.scrollBy(0, el.scrollHeight)")
            else:
                page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
        except Exception:
            page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
        page.wait_for_timeout(_SCROLL_PAUSE_MS)
        try:
            new_count = len(page.query_selector_all(f"{selector} > *"))
        except Exception:
            new_count = current_count
        if new_count <= prev_count:
            stale += 1
            if stale >= 2:
                break
        else:
            stale = 0
        prev_count = new_count


def _find_first_present(page, selectors: list) -> Optional[str]:
    """Return first selector that has a matching element on the page."""
    for sel in selectors:
        try:
            if page.query_selector(sel):
                return sel
        except Exception:
            continue
    return None


def _try_selector_all(page, selectors: list):
    """Return elements from first selector that yields non-empty results."""
    for sel in selectors:
        try:
            els = page.query_selector_all(sel)
            if els:
                return els
        except Exception:
            continue
    return []


def _scrape_google_maps(page, query: str, country_code: str) -> List[BusinessListing]:
    import re as _re

    url = f"https://www.google.com/maps/search/{urllib.parse.quote(query)}"
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    try:
        page.wait_for_selector('[role="feed"]', timeout=15000)
    except Exception:
        logger.warning("google_maps: feed not found for query %r", query)
        return []

    _scroll_until_stable(page, '[role="feed"]')

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
            # Random human-like pause — reduces bot-detection fingerprint
            page.wait_for_timeout(random.randint(900, 2800))

            # Name: multiple fallbacks as Google rotates class names
            name = ""
            for name_sel in ["h1.DUwDvf", "h1[data-attrid='title']", "h1"]:
                name_el = page.query_selector(name_sel)
                if name_el:
                    name = name_el.inner_text().strip()
                    if name:
                        break

            if not name:
                continue

            # Extract all fields before deciding how to categorise this listing.

            # Phone: data-item-id prefix has been stable for years
            raw_phone = ""
            phone_el = page.query_selector('[data-item-id^="phone:"]')
            if phone_el:
                raw_phone = (
                    phone_el.get_attribute("aria-label") or phone_el.inner_text() or ""
                ).replace("Phone:", "").replace("Telefone:", "").replace("Teléfono:", "").strip()

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

            if not raw_phone:
                # No phone on Maps — keep as partial when there's a website so the
                # spider pass in create_leads_from_maps can attempt to recover one.
                if website:
                    listings.append(
                        BusinessListing(
                            name=name,
                            source="google_maps",
                            phone=None,
                            website=website,
                            address=address,
                            category=category,
                            rating=rating,
                            review_count=review_count,
                        )
                    )
                continue

            normalized = _normalize_phone(raw_phone, country_code)
            if not normalized:
                continue

            listings.append(
                BusinessListing(
                    name=name,
                    source="google_maps",
                    phone=normalized,
                    website=website,
                    address=address,
                    category=category,
                    rating=rating,
                    review_count=review_count,
                )
            )
        except Exception as exc:
            logger.debug("google_maps: error parsing place %s: %s", place_url, exc)

    return listings


_BING_CONTAINER_SELS = [
    ".listings-container",
    ".b-list",
    "#panelContent",
    "[data-testid='listCard']",
    ".panelEntityCard",
]

_BING_CARD_SELS = [
    ".listings-container .listing",
    ".b-listingCard",
    ".listing-card",
    "[data-testid='listCard']",
    ".panelEntityCard",
    ".b-list li",
]


def _scrape_bing_maps(page, query: str, country_code: str) -> List[BusinessListing]:
    url = f"https://www.bing.com/maps?q={urllib.parse.quote(query)}"
    page.goto(url, wait_until="domcontentloaded", timeout=30000)

    container_sel = None
    try:
        page.wait_for_selector(", ".join(_BING_CONTAINER_SELS), timeout=15000)
        container_sel = _find_first_present(page, _BING_CONTAINER_SELS)
    except Exception:
        pass

    if not container_sel:
        logger.warning("bing_maps: no result container found for query %r", query)
        return []

    _scroll_until_stable(page, container_sel)

    cards = _try_selector_all(page, _BING_CARD_SELS)

    listings: List[BusinessListing] = []
    for card in cards[:_MAX_LISTINGS]:
        try:
            name_el = card.query_selector(
                ".b-title, .listing-title, [class*='title'], h2, h3"
            )
            name = name_el.inner_text().strip() if name_el else ""
            if not name:
                continue

            phone_el = card.query_selector(
                ".b-phone, [data-phone], a[href^='tel:'], [aria-label*='phone'], [aria-label*='Phone']"
            )
            raw_phone = ""
            if phone_el:
                raw_phone = (
                    phone_el.get_attribute("data-phone")
                    or (phone_el.get_attribute("href") or "").replace("tel:", "")
                    or phone_el.inner_text().strip()
                )

            if not raw_phone:
                continue

            normalized = _normalize_phone(raw_phone.strip(), country_code)
            if not normalized:
                continue

            addr_el = card.query_selector(".b-address, .listing-address, [class*='address']")
            address = addr_el.inner_text().strip() if addr_el else None

            website_el = card.query_selector("a.b-website, a[href^='http']:not([href*='bing'])")
            website = website_el.get_attribute("href") if website_el else None

            listings.append(
                BusinessListing(
                    name=name,
                    source="bing_maps",
                    phone=normalized,
                    website=website,
                    address=address,
                )
            )
        except Exception as exc:
            logger.debug("bing_maps: error parsing card: %s", exc)

    return listings


_DDG_CARD_SELS = [
    ".map-result",
    "[class*='mapResult']",
    "[data-testid='mapResult']",
    "[class*='result--map']",
    ".ddg-map-result",
    "li[class*='map']",
]


def _scrape_duckduckgo_maps(page, query: str, country_code: str) -> List[BusinessListing]:
    url = f"https://duckduckgo.com/?q={urllib.parse.quote(query)}&ia=maps&iaxm=maps"
    page.goto(url, wait_until="domcontentloaded", timeout=30000)

    container_sel = None
    try:
        page.wait_for_selector(", ".join(_DDG_CARD_SELS), timeout=15000)
        container_sel = _find_first_present(page, _DDG_CARD_SELS)
    except Exception:
        pass

    if not container_sel:
        logger.warning("duckduckgo_maps: no map results found for query %r", query)
        return []

    _scroll_until_stable(page, "body")

    cards = _try_selector_all(page, _DDG_CARD_SELS)

    listings: List[BusinessListing] = []
    for card in cards[:_MAX_LISTINGS]:
        try:
            name_el = card.query_selector(
                ".map-result__title, .result__title, [class*='title']"
            )
            name = name_el.inner_text().strip() if name_el else ""
            if not name:
                continue

            phone_el = card.query_selector(
                ".map-result__phone, [class*='phone'], a[href^='tel:']"
            )
            raw_phone = ""
            if phone_el:
                raw_phone = (
                    (phone_el.get_attribute("href") or "").replace("tel:", "")
                    or phone_el.inner_text().strip()
                )

            if not raw_phone:
                continue

            normalized = _normalize_phone(raw_phone.strip(), country_code)
            if not normalized:
                continue

            addr_el = card.query_selector(".map-result__address, [class*='address']")
            address = addr_el.inner_text().strip() if addr_el else None

            listings.append(
                BusinessListing(
                    name=name,
                    source="duckduckgo_maps",
                    phone=normalized,
                    address=address,
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


def _run_backend_in_isolation(
    backend_name: str, query: str, country_code: str
) -> List[BusinessListing]:
    """Launch a dedicated browser for one backend; safe to call from a thread."""
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
                page.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"})
                return _BACKEND_FN[backend_name](page, query, country_code)
            finally:
                browser.close()

    return _scrape_retry(_attempt, max_attempts=2, base_delay=3.0, label=f"maps:{backend_name}")


def create_leads_from_maps(
    query: str,
    country_code: str,
    campaign_id: str,
    user_id: str,
    backends: Optional[List[str]] = None,
    min_rating: Optional[float] = None,
) -> int:
    """Scrape maps backends with concurrent isolated browsers, dedup by phone, upsert Leads + Deals.

    Google Maps results that have a website but no visible phone number are kept
    as partial listings and fed through a concurrent HTTP spider pass
    (contact_spider.extract_phone_from_domain) to recover additional phone numbers.

    min_rating: if set, only listings with rating >= min_rating (or no rating data) are kept.
    Returns count of new leads created.
    """
    active_backends = [b for b in (backends or _DEFAULT_BACKENDS) if b in _BACKEND_FN]
    if not active_backends:
        logger.warning("maps_scraper: no valid backends in %s", backends)
        return 0

    all_listings: List[BusinessListing] = []

    with ThreadPoolExecutor(max_workers=len(active_backends)) as pool:
        futures = {
            pool.submit(_run_backend_in_isolation, backend, query, country_code): backend
            for backend in active_backends
        }
        for future in as_completed(futures):
            backend = futures[future]
            try:
                results = future.result()
                logger.info("maps_scraper: %s returned %d listings", backend, len(results))
                all_listings.extend(results)
            except Exception as exc:
                logger.warning("maps_scraper: backend %s failed: %s", backend, exc)

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

    # Partition into phone-ready listings and website-only partials
    ready = [lst for lst in all_listings if lst.phone]
    partial = [lst for lst in all_listings if not lst.phone and lst.website]

    if partial:
        logger.info(
            "maps_scraper: spidering %d website-only listings for phones",
            len(partial),
        )
        from openoutreach.whatsapp.pipeline.contact_spider import extract_phone_from_domain

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures_spider = {
                pool.submit(extract_phone_from_domain, lst.website, country_code): lst
                for lst in partial
                if lst.website  # website is Optional[str]; guard satisfies type checker
            }
            for future in as_completed(futures_spider):
                lst = futures_spider[future]
                try:
                    phone = future.result()
                    if phone:
                        ready.append(
                            BusinessListing(
                                name=lst.name,
                                source=f"{lst.source}_spider",
                                phone=phone,
                                website=lst.website,
                                address=lst.address,
                                category=lst.category,
                                rating=lst.rating,
                                review_count=lst.review_count,
                            )
                        )
                except Exception as exc:
                    logger.debug("maps_scraper: spider failed for %s: %s", lst.website, exc)

        recovered = len(ready) - len([lst for lst in all_listings if lst.phone])
        logger.info(
            "maps_scraper: spider recovered %d phones from %d partials",
            recovered,
            len(partial),
        )

    if not ready:
        return 0

    ready = _apply_icp_filter(ready, campaign_id, user_id)
    return upsert_listings_as_leads(ready, campaign_id, user_id)


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
        logger.warning("maps_scraper: icp_filter error: %s - keeping all listings", exc)
    return listings
