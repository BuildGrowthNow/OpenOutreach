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

from openoutreach.whatsapp.pipeline.icp_filter import apply_icp_filter as _apply_icp_filter
from openoutreach.whatsapp.pipeline.upsert import BusinessListing, upsert_listings_as_leads
from openoutreach.whatsapp.pipeline.utils import (
    apply_resource_block as _apply_resource_block,
    normalize_phone as _normalize_phone,
    random_user_agent as _random_user_agent,
    scrape_retry as _scrape_retry,
)

logger = logging.getLogger(__name__)

_DEFAULT_BACKENDS = ["google_maps", "bing_maps"]
_MAX_LISTINGS = 100        # feed cards to collect (cheap, no detail page)
_MAX_PLACE_VISITS = 25     # Google Maps detail pages per run — caps CAPTCHA exposure
_SCROLL_PAUSE_MS = 1200
_MAX_SCROLL_ROUNDS = 20


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

    def _is_captcha_url(url: str) -> bool:
        return "/sorry" in url or "recaptcha" in url.lower()

    listings: List[BusinessListing] = []
    for place_url in place_urls[:_MAX_PLACE_VISITS]:
        try:
            page.goto(place_url, wait_until="domcontentloaded", timeout=20000)

            # CAPTCHA check: Google redirects blocked requests to /sorry or reCAPTCHA
            if _is_captcha_url(page.url):
                logger.warning("google_maps: CAPTCHA detected — waiting 45s then retrying")
                page.wait_for_timeout(random.randint(40000, 50000))
                page.goto(place_url, wait_until="domcontentloaded", timeout=20000)
                if _is_captcha_url(page.url):
                    logger.warning(
                        "google_maps: CAPTCHA persists after retry — returning %d listings collected so far",
                        len(listings),
                    )
                    break

            # Slower human-like pause — key CAPTCHA-avoidance lever
            page.wait_for_timeout(random.randint(3000, 8000))

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


# ---------------------------------------------------------------------------
# Yellow Pages  (US / CA / AU — phones in search result cards, no detail pages)
# ---------------------------------------------------------------------------

_YP_BASES = {
    "US": ("https://www.yellowpages.com", "search?search_terms={q}&geo_location_terms=United+States"),
    "CA": ("https://www.yellowpages.ca", "search?what={q}&where=Canada"),
    "AU": ("https://www.yellowpages.com.au", "search?name={q}"),
    "GB": ("https://www.yell.com", "find/{q}/in/uk"),
}


def _scrape_yellow_pages(page, query: str, country_code: str) -> List[BusinessListing]:
    entry = _YP_BASES.get(country_code.upper())
    if not entry:
        logger.debug("yellow_pages: no coverage for country=%s — skipping", country_code)
        return []

    base, path_tmpl = entry
    encoded = urllib.parse.quote(query)
    url = f"{base}/{path_tmpl.replace('{q}', encoded)}"
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    try:
        page.wait_for_selector(
            ".result, .OrganicResult, .listing, .v-card, .business-card, li[class*='result']",
            timeout=15000,
        )
    except Exception:
        logger.warning("yellow_pages: no results for %r (%s)", query, country_code)
        return []

    for _ in range(3):
        page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
        page.wait_for_timeout(600)

    cards = page.query_selector_all(
        ".result, .OrganicResult, .listing, .v-card, .business-card, li[class*='result']"
    )
    listings: List[BusinessListing] = []

    for card in cards[:_MAX_LISTINGS]:
        try:
            name_el = card.query_selector(
                ".business-name, .n, h2 a, h3 a, .listing-name, [class*='businessName']"
            )
            name = name_el.inner_text().strip() if name_el else ""
            if not name:
                continue

            raw_phone = ""
            phone_el = card.query_selector(".phones, .phone, [class*='phone']")
            if phone_el:
                raw_phone = phone_el.inner_text().strip()
            if not raw_phone:
                tel_el = card.query_selector("a[href^='tel:']")
                if tel_el:
                    raw_phone = (tel_el.get_attribute("href") or "").replace("tel:", "").strip()
            if not raw_phone:
                continue

            normalized = _normalize_phone(raw_phone, country_code)
            if not normalized:
                continue

            addr_el = card.query_selector(".adr, .address, [class*='address']")
            address = addr_el.inner_text().strip() if addr_el else None

            website_el = card.query_selector(
                "a.track-visit-website, a[class*='website'], a[data-analytics*='website']"
            )
            website = website_el.get_attribute("href") if website_el else None

            cat_el = card.query_selector(".categories a, .category a, [class*='category'] a")
            category = cat_el.inner_text().strip() if cat_el else None

            listings.append(
                BusinessListing(
                    name=name,
                    source="yellow_pages",
                    phone=normalized,
                    website=website,
                    address=address,
                    category=category,
                )
            )
        except Exception as exc:
            logger.debug("yellow_pages: card parse error: %s", exc)

    return listings


# ---------------------------------------------------------------------------
# Yelp  (US / CA / GB / AU / IE — detail pages for phones, JSON-LD first)
# ---------------------------------------------------------------------------

_YELP_MAX_BIZ_VISITS = 15


def _scrape_yelp(page, query: str, country_code: str) -> List[BusinessListing]:
    import json as _json

    url = f"https://www.yelp.com/search?find_desc={urllib.parse.quote(query)}&find_loc={country_code}"
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    try:
        page.wait_for_selector("a[href*='/biz/'], h3 a", timeout=15000)
    except Exception:
        logger.warning("yelp: no results for %r", query)
        return []

    biz_links: list = []
    seen: set = set()
    for el in page.query_selector_all("a[href*='/biz/']"):
        href = el.get_attribute("href") or ""
        if "/biz/" not in href:
            continue
        if href.startswith("/"):
            href = "https://www.yelp.com" + href
        href = href.split("?")[0]
        name = el.inner_text().strip()
        if href not in seen and "/biz/" in href:
            seen.add(href)
            biz_links.append((href, name))
        if len(biz_links) >= _YELP_MAX_BIZ_VISITS * 2:
            break

    listings: List[BusinessListing] = []
    for biz_url, fallback_name in biz_links[:_YELP_MAX_BIZ_VISITS]:
        try:
            page.goto(biz_url, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(random.randint(2000, 4000))

            # JSON-LD is the most reliable signal — Yelp embeds it on every biz page
            raw_phone = ""
            for script_el in page.query_selector_all('script[type="application/ld+json"]'):
                try:
                    data = _json.loads(script_el.inner_text() or "{}")
                    if isinstance(data, list):
                        data = data[0] if data else {}
                    raw_phone = data.get("telephone") or data.get("phone") or ""
                    if raw_phone:
                        break
                except Exception:
                    continue

            if not raw_phone:
                tel_el = page.query_selector("a[href^='tel:'], p[class*='phone']")
                if tel_el:
                    raw_phone = (
                        (tel_el.get_attribute("href") or "").replace("tel:", "").strip()
                        or tel_el.inner_text().strip()
                    )

            if not raw_phone:
                continue

            normalized = _normalize_phone(raw_phone, country_code)
            if not normalized:
                continue

            name_el = page.query_selector("h1")
            name = name_el.inner_text().strip() if name_el else fallback_name

            addr_el = page.query_selector("address")
            address = addr_el.inner_text().strip() if addr_el else None

            cat_el = page.query_selector(
                "span[class*='tag--'], a[class*='category'], [class*='categories'] a"
            )
            category = cat_el.inner_text().strip() if cat_el else None

            listings.append(
                BusinessListing(
                    name=name or "Yelp Business",
                    source="yelp",
                    phone=normalized,
                    address=address,
                    category=category,
                )
            )
        except Exception as exc:
            logger.debug("yelp: error on %s: %s", biz_url, exc)

    return listings


_BACKEND_FN = {
    "google_maps": _scrape_google_maps,
    "bing_maps": _scrape_bing_maps,
    "yellow_pages": _scrape_yellow_pages,
    "yelp": _scrape_yelp,
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
                _apply_resource_block(page)
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
        from openoutreach.whatsapp.pipeline.alerts import fire_scrape_zero_results
        fire_scrape_zero_results(campaign_id, user_id, "maps", query)
        return 0

    ready = _apply_icp_filter(ready, campaign_id, user_id, label="maps_scraper")
    return upsert_listings_as_leads(ready, campaign_id, user_id)
