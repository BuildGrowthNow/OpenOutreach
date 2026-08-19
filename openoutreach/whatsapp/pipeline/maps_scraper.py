"""Maps scraper — multi-backend Playwright scraper for phone leads.

Supported backends: google_maps, bing_maps, duckduckgo_maps.
Entry point: create_leads_from_maps(...)
"""

from __future__ import annotations

import logging
import urllib.parse
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_BACKENDS = ["google_maps", "bing_maps", "duckduckgo_maps"]
_MAX_LISTINGS = 50
_SCROLL_REPEATS = 3
_SCROLL_PAUSE_MS = 1000


@dataclass
class BusinessListing:
    name: str
    phone: str  # E.164, e.g. "+15551234567"
    website: Optional[str]
    address: Optional[str]
    category: Optional[str]
    source: str  # "google_maps" | "bing_maps" | "duckduckgo_maps"
    rating: Optional[float] = None
    review_count: Optional[int] = None


def _normalize_phone(raw: str, country_code: str) -> Optional[str]:
    """Return E.164 string or None if unparseable."""
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
    url = f"https://www.google.com/maps/search/{urllib.parse.quote(query)}"
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    try:
        page.wait_for_selector('[role="feed"]', timeout=15000)
    except Exception:
        logger.warning("google_maps: feed not found for query %r", query)
        return []

    _scroll_results(page, '[role="feed"]')

    listings: List[BusinessListing] = []
    cards = page.query_selector_all(
        '[role="feed"] > div[data-result-index], [role="feed"] > div[jsaction]'
    )
    if not cards:
        cards = page.query_selector_all('[role="feed"] > div')

    for card in cards[:_MAX_LISTINGS]:
        try:
            card.click()
            page.wait_for_timeout(1500)

            name_el = page.query_selector(
                "h1.DUwDvf, .fontHeadlineLarge, .fontHeadlineSmall"
            )
            name = name_el.inner_text().strip() if name_el else ""
            if not name:
                aria = card.get_attribute("aria-label") or ""
                name = aria.strip()

            phone_el = page.query_selector('[data-item-id^="phone:"]')
            raw_phone = ""
            if phone_el:
                raw_phone = (
                    phone_el.get_attribute("aria-label") or ""
                ).replace("Phone:", "").strip()

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
                website = (
                    website_el.get_attribute("href")
                    or website_el.inner_text().strip()
                    or None
                )

            category_el = page.query_selector(
                'button[jsaction*="category"], .DkEaL, [data-section-id="speciality"] .mgr77e'
            )
            category = category_el.inner_text().strip() if category_el else None

            rating: Optional[float] = None
            review_count: Optional[int] = None
            rating_el = page.query_selector('[data-value="Rating"], .MW4etd')
            if rating_el:
                try:
                    rating = float(rating_el.inner_text().strip())
                except (ValueError, AttributeError):
                    pass
            reviews_el = page.query_selector('.UY7F9, [aria-label*="reviews"]')
            if reviews_el:
                raw_rc = (
                    reviews_el.get_attribute("aria-label")
                    or reviews_el.inner_text()
                    or ""
                )
                import re as _re
                m = _re.search(r"[\d,]+", raw_rc.replace(",", ""))
                if m:
                    try:
                        review_count = int(m.group().replace(",", ""))
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
            logger.debug("google_maps: error parsing card: %s", exc)

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


def scrape(query: str, country_code: str, backend: str) -> List[BusinessListing]:
    """Open headless Chromium, navigate to backend, extract listings with phones."""
    if backend not in _BACKEND_FN:
        raise ValueError(f"Unknown backend: {backend!r}")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"})
            return _BACKEND_FN[backend](page, query, country_code)
        finally:
            browser.close()


def create_leads_from_maps(
    query: str,
    country_code: str,
    campaign_id: str,
    user_id: str,
    backends: Optional[List[str]] = None,
) -> int:
    """Scrape maps backends, dedup by phone, upsert Leads + Deals.

    Returns count of new leads created.
    """
    from datetime import datetime, timezone as tz
    from uuid import uuid4

    from openoutreach.mongodb.connection import get_mongodb_collection
    from openoutreach.mongodb.models import Deal

    active_backends = backends if backends is not None else _DEFAULT_BACKENDS

    all_listings: List[BusinessListing] = []
    for backend in active_backends:
        try:
            results = scrape(query, country_code, backend)
            logger.info(
                "maps_scraper: %s returned %d listings", backend, len(results)
            )
            all_listings.extend(results)
        except Exception as exc:
            logger.warning("maps_scraper: backend %s failed: %s", backend, exc)

    # Dedup by phone across all backends
    seen_phones: set = set()
    unique: List[BusinessListing] = []
    for listing in all_listings:
        if listing.phone not in seen_phones:
            seen_phones.add(listing.phone)
            unique.append(listing)

    leads_col = get_mongodb_collection("leads")
    deals_col = get_mongodb_collection("deals")
    if leads_col is None or deals_col is None:
        raise RuntimeError("MongoDB leads/deals collection unavailable")

    created = 0
    now = datetime.now(tz.utc)

    for listing in unique:
        lead_id = str(uuid4())

        set_on_insert: dict = {
            "_id": lead_id,
            "phone": listing.phone,
            "phone_source": listing.source,
            "company": listing.name,
            "linkedin_url": None,
            "public_identifier": "",
            "user_id": user_id,
            "disqualified": False,
            "created_at": now,
        }
        if listing.category:
            set_on_insert["headline"] = listing.category
        if listing.website:
            set_on_insert["website"] = listing.website
        if listing.address:
            set_on_insert["address"] = listing.address
        if listing.rating is not None:
            set_on_insert["rating"] = listing.rating
        if listing.review_count is not None:
            set_on_insert["review_count"] = listing.review_count

        result = leads_col.update_one(
            {"phone": listing.phone},
            {"$setOnInsert": set_on_insert},
            upsert=True,
        )

        # Resolve the actual lead _id (upserted or existing)
        if result.upserted_id is not None:
            actual_lead_id = str(result.upserted_id)
            created += 1
        else:
            doc = leads_col.find_one({"phone": listing.phone}, {"_id": 1})
            actual_lead_id = str(doc["_id"]) if doc else lead_id

        # Create Deal if none exists for this lead+campaign
        existing_deal = deals_col.find_one(
            {"lead_id": actual_lead_id, "campaign_id": campaign_id}
        )
        if not existing_deal:
            deals_col.insert_one(
                {
                    "_id": str(uuid4()),
                    "lead_id": actual_lead_id,
                    "campaign_id": campaign_id,
                    "state": Deal.DealState.DISCOVERED,
                    "user_id": user_id,
                    "created_at": now,
                }
            )

    logger.info(
        "maps_scraper: created %d new leads for campaign %s", created, campaign_id
    )
    return created
