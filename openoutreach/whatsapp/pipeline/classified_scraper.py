"""Classified ads scraper - Craigslist, OLX, MercadoLibre, Gumtree.

Each backend searches the site for `query`, opens listing detail pages, and
extracts phone numbers from tel: links or visible body text.

Entry point: create_leads_from_classified(...)
"""
from __future__ import annotations

import logging
import re
import urllib.parse
from typing import List, Optional

from openoutreach.whatsapp.pipeline.upsert import BusinessListing, upsert_listings_as_leads

logger = logging.getLogger(__name__)

_MAX_LISTINGS = 40      # cards to collect from search page
_MAX_DETAIL_PAGES = 20  # listing detail pages to visit per backend
_PHONE_RE = re.compile(r"(\+?[\d][\d\s\-\.\(\)]{5,18}[\d])")
_DEFAULT_SITES = ["craigslist", "olx", "mercadolibre"]


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


def _phone_from_page(page) -> str:
    """Best-effort phone extraction from the current Playwright page."""
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


# ---------------------------------------------------------------------------
# Craigslist
# ---------------------------------------------------------------------------

def _scrape_craigslist(page, query: str, country_code: str) -> List[BusinessListing]:
    url = f"https://www.craigslist.org/search/sss?query={urllib.parse.quote(query)}&sort=date"
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    try:
        page.wait_for_selector(".cl-search-result, .result-row", timeout=15000)
    except Exception:
        logger.warning("craigslist: no results for %r", query)
        return []

    links = []
    seen: set = set()
    for el in page.query_selector_all("a.cl-app-anchor, a.result-title"):
        href = el.get_attribute("href") or ""
        if "/d/" in href and href not in seen:
            seen.add(href)
            links.append(href)
        if len(links) >= _MAX_LISTINGS:
            break

    listings: List[BusinessListing] = []
    for link in links[:_MAX_DETAIL_PAGES]:
        try:
            page.goto(link, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(700)

            title_el = page.query_selector("#titletextonly, .postingtitletext h1, h1")
            title = title_el.inner_text().strip() if title_el else ""

            raw_phone = _phone_from_page(page)
            if not raw_phone:
                continue
            phone = _normalize_phone(raw_phone, country_code)
            if not phone:
                continue

            addr_el = page.query_selector(".mapaddress")
            address = addr_el.inner_text().strip() if addr_el else None

            listings.append(BusinessListing(
                name=title or "Craigslist Listing",
                phone=phone,
                source="craigslist",
                address=address,
            ))
        except Exception as exc:
            logger.debug("craigslist: error on %s: %s", link, exc)

    return listings


# ---------------------------------------------------------------------------
# OLX  (country-specific subdomain)
# ---------------------------------------------------------------------------

_OLX_BASES = {
    "BR": "https://www.olx.com.br",
    "PL": "https://www.olx.pl",
    "UA": "https://www.olx.ua",
    "IN": "https://www.olx.in",
    "ZA": "https://www.olx.co.za",
    "PT": "https://www.olx.pt",
    "RO": "https://www.olx.ro",
    "AR": "https://www.olx.com.ar",
    "CO": "https://www.olx.com.co",
    "PE": "https://www.olx.com.pe",
    "MX": "https://www.olx.com.mx",
}


def _scrape_olx(page, query: str, country_code: str) -> List[BusinessListing]:
    base = _OLX_BASES.get(country_code.upper(), "https://www.olx.com")
    url = f"{base}/?q={urllib.parse.quote(query)}"
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    try:
        page.wait_for_selector(
            "[data-cy='l-card'], .offer-wrapper, li[data-testid]", timeout=15000
        )
    except Exception:
        logger.warning("olx: no results for %r on %s", query, base)
        return []

    links = []
    seen: set = set()
    for el in page.query_selector_all(
        "a[href*='/d/anuncio/'], a[href*='/oferta/'], [data-cy='l-card'] a"
    ):
        href = el.get_attribute("href") or ""
        if not href.startswith("http"):
            href = base + href
        if href not in seen:
            seen.add(href)
            links.append(href)
        if len(links) >= _MAX_LISTINGS:
            break

    listings: List[BusinessListing] = []
    for link in links[:_MAX_DETAIL_PAGES]:
        try:
            page.goto(link, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(900)

            title_el = page.query_selector(
                "h1[data-cy='ad_title'], h1.css-1soizd2, h1"
            )
            title = title_el.inner_text().strip() if title_el else ""

            # Try "Mostrar número / Show number" button first
            raw_phone = ""
            try:
                show_btn = page.query_selector(
                    "button:has-text('Mostrar'), button:has-text('Ver número'), "
                    "button:has-text('Show'), button:has-text('Ligar')"
                )
                if show_btn:
                    show_btn.click()
                    page.wait_for_timeout(1200)
                    phone_el = page.query_selector(
                        "[data-testid='phone-number'], .css-zgx1rl, "
                        "span[aria-label*='+']"
                    )
                    if phone_el:
                        raw_phone = phone_el.inner_text().strip()
            except Exception:
                pass

            if not raw_phone:
                raw_phone = _phone_from_page(page)
            if not raw_phone:
                continue
            phone = _normalize_phone(raw_phone, country_code)
            if not phone:
                continue

            addr_el = page.query_selector(
                "[data-testid='ad-contact-location'], .css-bshv44-Text"
            )
            address = addr_el.inner_text().strip() if addr_el else None

            listings.append(BusinessListing(
                name=title or "OLX Listing",
                phone=phone,
                source="olx",
                address=address,
            ))
        except Exception as exc:
            logger.debug("olx: error on %s: %s", link, exc)

    return listings


# ---------------------------------------------------------------------------
# MercadoLibre / MercadoLivre
# ---------------------------------------------------------------------------

_ML_BASES = {
    "AR": "https://listado.mercadolibre.com.ar",
    "BR": "https://lista.mercadolivre.com.br",
    "MX": "https://listado.mercadolibre.com.mx",
    "CO": "https://listado.mercadolibre.com.co",
    "CL": "https://listado.mercadolibre.cl",
    "PE": "https://listado.mercadolibre.com.pe",
    "UY": "https://listado.mercadolibre.com.uy",
    "VE": "https://listado.mercadolibre.com.ve",
    "EC": "https://listado.mercadolibre.com.ec",
}


def _scrape_mercadolibre(page, query: str, country_code: str) -> List[BusinessListing]:
    base = _ML_BASES.get(country_code.upper(), "https://listado.mercadolibre.com.ar")
    url = f"{base}/{urllib.parse.quote(query.replace(' ', '-'))}"
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    try:
        page.wait_for_selector(
            ".ui-search-result__wrapper, .andes-card", timeout=15000
        )
    except Exception:
        logger.warning("mercadolibre: no results for %r", query)
        return []

    links = []
    seen: set = set()
    for el in page.query_selector_all(
        "a.ui-search-item__group__element, a.ui-search-link"
    ):
        href = (el.get_attribute("href") or "").split("?")[0]
        if href and "mercadolibre" in href and href not in seen:
            seen.add(href)
            links.append(href)
        if len(links) >= _MAX_LISTINGS:
            break

    listings: List[BusinessListing] = []
    for link in links[:_MAX_DETAIL_PAGES]:
        try:
            page.goto(link, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(700)

            title_el = page.query_selector("h1.ui-pdp-title, h1")
            title = title_el.inner_text().strip() if title_el else ""

            raw_phone = _phone_from_page(page)
            if not raw_phone:
                continue
            phone = _normalize_phone(raw_phone, country_code)
            if not phone:
                continue

            seller_el = page.query_selector(".ui-box-component-pdp__visible-title")
            seller_name = seller_el.inner_text().strip() if seller_el else title

            listings.append(BusinessListing(
                name=seller_name or "MercadoLibre Seller",
                phone=phone,
                source="mercadolibre",
            ))
        except Exception as exc:
            logger.debug("mercadolibre: error on %s: %s", link, exc)

    return listings


# ---------------------------------------------------------------------------
# Gumtree  (UK / AU)
# ---------------------------------------------------------------------------

def _scrape_gumtree(page, query: str, country_code: str) -> List[BusinessListing]:
    base = (
        "https://www.gumtree.com.au"
        if country_code.upper() == "AU"
        else "https://www.gumtree.com"
    )
    url = f"{base}/search?search_category=all&q={urllib.parse.quote(query)}"
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    try:
        page.wait_for_selector(".listing-link, .natural", timeout=15000)
    except Exception:
        logger.warning("gumtree: no results for %r", query)
        return []

    links = []
    seen: set = set()
    for el in page.query_selector_all("a.listing-link"):
        href = el.get_attribute("href") or ""
        if not href.startswith("http"):
            href = base + href
        if href not in seen:
            seen.add(href)
            links.append(href)
        if len(links) >= _MAX_LISTINGS:
            break

    listings: List[BusinessListing] = []
    for link in links[:_MAX_DETAIL_PAGES]:
        try:
            page.goto(link, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(700)

            title_el = page.query_selector("h1.listing-title, h1")
            title = title_el.inner_text().strip() if title_el else ""

            raw_phone = _phone_from_page(page)
            if not raw_phone:
                continue
            phone = _normalize_phone(raw_phone, country_code)
            if not phone:
                continue

            listings.append(BusinessListing(
                name=title or "Gumtree Listing",
                phone=phone,
                source="gumtree",
            ))
        except Exception as exc:
            logger.debug("gumtree: error on %s: %s", link, exc)

    return listings


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_BACKEND_FN = {
    "craigslist": _scrape_craigslist,
    "olx": _scrape_olx,
    "mercadolibre": _scrape_mercadolibre,
    "gumtree": _scrape_gumtree,
}


def create_leads_from_classified(
    query: str,
    country_code: str,
    campaign_id: str,
    user_id: str,
    sites: Optional[List[str]] = None,
) -> int:
    """Scrape classified sites, dedup by phone, upsert leads + deals.

    Returns count of new leads created.
    """
    from playwright.sync_api import sync_playwright

    active_sites = [s for s in (sites or _DEFAULT_SITES) if s in _BACKEND_FN]
    if not active_sites:
        logger.warning("classified: no valid sites in %s", sites)
        return 0

    all_listings: List[BusinessListing] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"})
            for site in active_sites:
                try:
                    results = _BACKEND_FN[site](page, query, country_code)
                    logger.info(
                        "classified: %s returned %d listings", site, len(results)
                    )
                    all_listings.extend(results)
                except Exception as exc:
                    logger.warning("classified: site %s failed: %s", site, exc)
        finally:
            browser.close()

    return upsert_listings_as_leads(all_listings, campaign_id, user_id)
