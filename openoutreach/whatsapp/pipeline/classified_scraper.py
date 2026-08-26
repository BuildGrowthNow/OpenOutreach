"""Classified ads scraper - OLX, MercadoLibre, Gumtree.

Each backend searches the site for `query`, opens listing detail pages, and
extracts phone numbers from tel: links or contextual body text.

Entry point: create_leads_from_classified(...)
"""
from __future__ import annotations

import logging
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

from openoutreach.whatsapp.pipeline.icp_filter import apply_icp_filter as _apply_icp_filter
from openoutreach.whatsapp.pipeline.upsert import BusinessListing, upsert_listings_as_leads
from openoutreach.whatsapp.pipeline.utils import (
    apply_resource_block as _apply_resource_block,
    normalize_phone as _normalize_phone,
    phone_from_page as _phone_from_page,
    random_user_agent as _random_user_agent,
    scrape_retry as _scrape_retry,
)

logger = logging.getLogger(__name__)

_MAX_LISTINGS = 40      # cards to collect from search page
_MAX_DETAIL_PAGES = 20  # listing detail pages to visit per backend
_DEFAULT_SITES = ["olx", "mercadolibre"]


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

            if raw_phone:
                phone = _normalize_phone(raw_phone, country_code)
            else:
                phone = _phone_from_page(page, country_code) or None

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

            phone = _phone_from_page(page, country_code) or None
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

            phone = _phone_from_page(page, country_code) or None
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
    "olx": _scrape_olx,
    "mercadolibre": _scrape_mercadolibre,
    "gumtree": _scrape_gumtree,
}


def _run_classified_in_isolation(
    site_name: str, query: str, country_code: str
) -> List[BusinessListing]:
    """Launch a dedicated browser for one classified site; safe to call from a thread."""
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
                return _BACKEND_FN[site_name](page, query, country_code)
            finally:
                browser.close()

    return _scrape_retry(_attempt, max_attempts=2, base_delay=3.0, label=f"classified:{site_name}")


def create_leads_from_classified(
    query: str,
    country_code: str,
    campaign_id: str,
    user_id: str,
    sites: Optional[List[str]] = None,
) -> int:
    """Scrape classified sites with concurrent isolated browsers, dedup by phone, upsert leads + deals.

    Each site runs in its own browser process so a hang on one site never
    blocks the others. Applies ICP filter before upsert when campaign has criteria.
    Returns count of new leads created.
    """
    active_sites = [s for s in (sites or _DEFAULT_SITES) if s in _BACKEND_FN]
    if not active_sites:
        logger.warning("classified: no valid sites in %s", sites)
        return 0

    all_listings: List[BusinessListing] = []

    with ThreadPoolExecutor(max_workers=len(active_sites)) as pool:
        futures = {
            pool.submit(_run_classified_in_isolation, site, query, country_code): site
            for site in active_sites
        }
        for future in as_completed(futures):
            site = futures[future]
            try:
                results = future.result()
                logger.info("classified: %s returned %d listings", site, len(results))
                all_listings.extend(results)
            except Exception as exc:
                logger.warning("classified: site %s failed: %s", site, exc)

    if not all_listings:
        from openoutreach.whatsapp.pipeline.alerts import fire_scrape_zero_results
        fire_scrape_zero_results(campaign_id, user_id, "classified", query)
        return 0

    all_listings = _apply_icp_filter(all_listings, campaign_id, user_id, label="classified")
    return upsert_listings_as_leads(all_listings, campaign_id, user_id)
