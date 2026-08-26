# openoutreach/emails/enrichment/website_scraper.py
"""Scrape the target company website for the person's email address.

Strategy:
  1. Try /sitemap.xml to discover contact/team/about/leadership URLs
  2. Fall back to hardcoded common paths
  3. Extract all @{domain} email addresses from HTML
  4. Return the best match by first/last name scoring

Works for all business types — agencies, consultancies, clinics, SaaS, etc.
Reuses the HTTP/sitemap pattern from openoutreach.whatsapp.pipeline.contact_spider.
"""
from __future__ import annotations

import logging
import re
import unicodedata
import xml.etree.ElementTree as ET
from typing import Optional
from urllib.parse import urlparse

import httpx

from openoutreach.whatsapp.pipeline.utils import random_user_agent

logger = logging.getLogger(__name__)

_TIMEOUT_S = 8
_MAX_PAGES = 8

_SCRAPE_PATHS = [
    "/team",
    "/our-team",
    "/about",
    "/about-us",
    "/people",
    "/leadership",
    "/staff",
    "/employees",
    "/meet-the-team",
    "/contact",
    "/contact-us",
    "/who-we-are",
    "/our-people",
    "/en/team",
    "/en/about",
    "/en/contact",
    "",
]

_SITEMAP_RE = re.compile(
    r"team|about|people|staff|leadership|contact|sobre|kontakt",
    re.IGNORECASE,
)

# Generic addresses that are never a specific person's email
_GENERIC_LOCAL_RE = re.compile(
    r"^(info|contact|hello|hi|support|admin|office|mail|email|sales|"
    r"marketing|hr|jobs|careers|legal|privacy|press|media|news|billing|"
    r"accounts?|noreply|no-reply|webmaster|postmaster|help|service|"
    r"enquir[yi]es?|enquiries?|reception|general|team)$",
    re.IGNORECASE,
)


def _normalize(name: str) -> str:
    name = name.strip().lower()
    name = unicodedata.normalize("NFD", name)
    name = "".join(c for c in name if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", name)


def _name_score(local: str, first: str, last: str) -> int:
    """Score how well the email local part matches the target person's name."""
    if not first and not last:
        return 0
    local = local.lower()
    first_n = _normalize(first)
    last_n = _normalize(last)
    score = 0
    if first_n and first_n in local:
        score += 2
    if last_n and last_n in local:
        score += 2
    if first_n and local.startswith(first_n[0]):
        score += 1
    return score


def _extract_name_emails(html: str, domain: str, first: str, last: str) -> list[tuple[str, int]]:
    """Return (email, score) pairs from HTML for @domain addresses matching the person's name."""
    email_re = re.compile(
        r"[a-zA-Z0-9._%+\-]+@" + re.escape(domain),
        re.IGNORECASE,
    )
    obfuscated_re = re.compile(
        r"([a-zA-Z0-9._%+\-]+)\s*(?:\[at\]|\(at\)|\sat\s)\s*" + re.escape(domain),
        re.IGNORECASE,
    )

    found: dict[str, int] = {}
    for m in email_re.finditer(html):
        email = m.group(0).lower()
        local = email.split("@")[0]
        if _GENERIC_LOCAL_RE.match(local):
            continue
        score = _name_score(local, first, last)
        if score > 0:
            found[email] = max(found.get(email, 0), score)
    for m in obfuscated_re.finditer(html):
        email = f"{m.group(1).lower()}@{domain}"
        local = m.group(1).lower()
        if _GENERIC_LOCAL_RE.match(local):
            continue
        score = _name_score(local, first, last)
        if score > 0:
            found[email] = max(found.get(email, 0), score)

    return sorted(found.items(), key=lambda x: -x[1])


def _make_client() -> httpx.Client:
    return httpx.Client(
        headers={
            "User-Agent": random_user_agent(),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,*/*",
        },
        follow_redirects=True,
        timeout=_TIMEOUT_S,
    )


def _fetch_sitemap_urls(base: str, client: httpx.Client) -> list[str]:
    try:
        resp = client.get(f"{base}/sitemap.xml")
        if resp.status_code != 200:
            return []
        root = ET.fromstring(resp.text)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls: list[str] = []
        for loc in root.findall(".//sm:loc", ns):
            if loc.text and _SITEMAP_RE.search(loc.text):
                urls.append(loc.text)
                if len(urls) >= 5:
                    break
        return urls
    except Exception:
        return []


def scrape_company_email(
    domain: str,
    first_name: str,
    last_name: str,
) -> Optional[str]:
    """Crawl the company website and return an email matching the target person, or None."""
    parsed = urlparse(f"https://{domain}" if "://" not in domain else domain)
    base = f"{parsed.scheme}://{parsed.netloc or parsed.path.rstrip('/')}"

    client = _make_client()
    tried: set[str] = set()
    pages_checked = 0

    # Sitemap pass — often finds team/leadership pages directly
    for url in _fetch_sitemap_urls(base, client):
        if pages_checked >= _MAX_PAGES:
            break
        tried.add(url)
        pages_checked += 1
        try:
            resp = client.get(url)
            if resp.status_code == 200:
                hits = _extract_name_emails(resp.text, domain, first_name, last_name)
                if hits:
                    email = hits[0][0]
                    logger.info("website_scraper: found %s at %s", email, url)
                    return email
        except Exception:
            continue

    # Hardcoded paths
    for path in _SCRAPE_PATHS:
        if pages_checked >= _MAX_PAGES:
            break
        url = base + path
        if url in tried:
            continue
        tried.add(url)
        pages_checked += 1
        try:
            resp = client.get(url)
            if resp.status_code == 200:
                hits = _extract_name_emails(resp.text, domain, first_name, last_name)
                if hits:
                    email = hits[0][0]
                    logger.info("website_scraper: found %s at %s", email, url)
                    return email
        except Exception:
            continue

    return None
