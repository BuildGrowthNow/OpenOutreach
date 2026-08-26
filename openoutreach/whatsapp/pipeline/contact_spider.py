"""Contact-page phone spider.

Finds leads in a campaign that have a website but no phone, fetches their
contact/about pages, extracts E.164 numbers via tel: links or regex, and
writes them back to Lead.phone.  No Playwright needed - pure HTTP.
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional
from urllib.parse import urlparse

import requests

from openoutreach.whatsapp.pipeline.utils import (
    normalize_phone as _normalize_phone,
    random_user_agent as _random_user_agent,
)

logger = logging.getLogger(__name__)

_CONTACT_PATHS = [
    "",
    "/contact",
    "/contact-us",
    "/contacto",
    "/contato",
    "/about",
    "/about-us",
    "/sobre",
    "/sobre-nos",
    "/kontakt",
    "/en/contact",
    "/en/about",
]
_TIMEOUT_S = 8
_SITEMAP_CONTACT_RE = re.compile(
    r"contact|about|sobre|contato|kontakt|kontakti",
    re.IGNORECASE,
)

# Contextual regex: only match phone patterns that appear near phone-related words.
# Prevents false positives from order numbers, zip codes, and other digit sequences.
_PHONE_CONTEXT_RE = re.compile(
    r"(?:phones?|tel(?:efon[eo]?)?|fone|call|whatsapp|cell|mobile"
    r"|celular|m[oó]vil|handy|contact|hotline|helpline)"
    r"[\s\S]{0,80}"
    r"(\+?[\d][\d\s\-\.\(\)]{5,18}[\d])",
    re.IGNORECASE,
)


def _make_session() -> requests.Session:
    """Create a requests session with a randomised user-agent."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": _random_user_agent(),
        "Accept-Language": "en-US,en;q=0.9",
    })
    return session


def _extract_from_html(html: str, country_code: str) -> Optional[str]:
    # tel: links are the most reliable signal
    for raw in re.findall(r'tel:([\+\d\s\-\(\)\.]{7,20})', html):
        phone = _normalize_phone(raw.strip(), country_code)
        if phone:
            return phone
    # Contextual body scan: only match numbers near phone-related keywords
    clean = re.sub(r"<[^>]+>", " ", html)
    for m in _PHONE_CONTEXT_RE.finditer(clean):
        candidate = m.group(1).strip()
        if sum(c.isdigit() for c in candidate) >= 7:
            phone = _normalize_phone(candidate, country_code)
            if phone:
                return phone
    return None


def _fetch_sitemap_contact_urls(base: str, session: requests.Session) -> List[str]:
    """Fetch /sitemap.xml and return URLs matching contact/about patterns (up to 5)."""
    try:
        resp = session.get(f"{base}/sitemap.xml", timeout=_TIMEOUT_S)
        if resp.status_code != 200:
            return []
        root = ET.fromstring(resp.text)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls: List[str] = []
        for loc in root.findall(".//sm:loc", ns):
            if loc.text and _SITEMAP_CONTACT_RE.search(loc.text):
                urls.append(loc.text)
                if len(urls) >= 5:
                    break
        return urls
    except Exception:
        return []


def extract_phone_from_domain(domain_url: str, country_code: str) -> Optional[str]:
    """Try sitemap-discovered contact pages then common paths; return first valid E.164 number."""
    parsed = urlparse(domain_url)
    scheme = parsed.scheme or "https"
    host = parsed.netloc or parsed.path.rstrip("/")
    base = f"{scheme}://{host}"

    session = _make_session()
    tried_urls: set = set()

    # Sitemap pass: often finds contact pages faster than blindly trying all hardcoded paths
    sitemap_urls = _fetch_sitemap_contact_urls(base, session)
    for url in sitemap_urls:
        tried_urls.add(url)
        try:
            resp = session.get(url, timeout=_TIMEOUT_S, allow_redirects=True)
            if resp.status_code == 200:
                phone = _extract_from_html(resp.text, country_code)
                if phone:
                    return phone
        except Exception:
            continue

    # Fallback: hardcoded contact/about paths — skip any already visited via sitemap
    for path in _CONTACT_PATHS:
        url = base + path
        if url in tried_urls:
            continue
        tried_urls.add(url)
        try:
            resp = session.get(url, timeout=_TIMEOUT_S, allow_redirects=True)
            if resp.status_code == 200:
                phone = _extract_from_html(resp.text, country_code)
                if phone:
                    return phone
        except Exception:
            continue

    return None


def enrich_leads_with_contact_phones(
    campaign_id: str,
    user_id: str,
    country_code: str = "US",
    limit: int = 50,
    max_workers: int = 8,
) -> int:
    """Find leads in campaign with website but no phone; spider contact pages in parallel.

    Returns count of leads enriched with a phone number.
    """
    from openoutreach.mongodb.connection import get_mongodb_collection

    leads_col = get_mongodb_collection("leads")
    deals_col = get_mongodb_collection("deals")
    if leads_col is None or deals_col is None:
        return 0

    deal_docs = list(deals_col.find({"campaign_id": campaign_id}, {"lead_id": 1}))
    lead_ids = [d["lead_id"] for d in deal_docs]
    if not lead_ids:
        return 0

    candidates = list(
        leads_col.find(
            {
                "_id": {"$in": lead_ids},
                "user_id": user_id,
                "website": {"$ne": None, "$exists": True},
                "$or": [{"phone": None}, {"phone": {"$exists": False}}],
            },
            {"_id": 1, "website": 1},
        ).limit(limit)
    )

    if not candidates:
        return 0

    def _enrich_one(doc: dict) -> Optional[tuple]:
        website = doc.get("website")
        if not website:
            return None
        phone = extract_phone_from_domain(website, country_code)
        if not phone:
            logger.debug("contact_spider: no phone at %s", website)
            return None
        return (doc["_id"], phone)

    enriched = 0
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_enrich_one, doc): doc for doc in candidates}
        for future in as_completed(futures):
            result = future.result()
            if result is None:
                continue
            lead_id, phone = result
            leads_col.update_one(
                {"_id": lead_id},
                {"$set": {"phone": phone, "phone_source": "contact_spider"}},
            )
            enriched += 1
            logger.info("contact_spider: enriched lead %s → %s", lead_id, phone)

    logger.info(
        "contact_spider: enriched %d/%d leads for campaign %s",
        enriched,
        len(candidates),
        campaign_id,
    )
    return enriched
