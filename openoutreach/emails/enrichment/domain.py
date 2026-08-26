# openoutreach/emails/enrichment/domain.py
"""Extract a company's sending domain from a lead's profile data.

Strategy (stops at first hit):
  1. Cached profile → company website field (various Voyager path variants)
  2. MongoDB cache: company_name → domain (TTL 30 days)
  3. DuckDuckGo HTML search: "{company} official website" → first result domain
  4. Return None (caller falls back to next enrichment layer)
"""

from __future__ import annotations

import logging
import re
import urllib.parse

logger = logging.getLogger(__name__)

_SKIP_DOMAINS = frozenset({
    "gmail.com", "outlook.com", "hotmail.com", "yahoo.com",
    "linkedin.com", "facebook.com", "twitter.com", "instagram.com",
    "google.com", "microsoft.com", "apple.com", "amazon.com",
    "cloudflare.com", "github.com", "youtube.com", "wordpress.com",
})

_DOMAIN_RE = re.compile(r"(?:https?://)?(?:www\.)?([a-zA-Z0-9-]{2,63}\.[a-zA-Z]{2,10})(?:[/?\s]|$)")
_CACHE_TTL_DAYS = 30


def extract_domain(company: str, cached_profile: dict | None) -> str | None:
    """Return the company's email-sending domain, or None on failure."""
    domain = _from_profile(cached_profile)
    if domain:
        return domain

    if not company:
        return None

    domain = _from_cache(company)
    if domain:
        return domain

    domain = _from_duckduckgo(company)
    if domain:
        _save_cache(company, domain)
        return domain

    return None


def _from_profile(profile: dict | None) -> str | None:
    if not profile:
        return None

    candidates: list[str] = []

    for key in ("website", "websiteUrl", "company_website"):
        if val := profile.get(key):
            candidates.append(str(val))

    experience = profile.get("experience") or []
    if experience and isinstance(experience[0], dict):
        company_obj = experience[0].get("company") or {}
        if isinstance(company_obj, dict):
            for key in ("website", "websiteUrl"):
                if val := company_obj.get(key):
                    candidates.append(str(val))

    for raw in candidates:
        domain = _clean_domain(raw)
        if domain and domain not in _SKIP_DOMAINS:
            return domain

    return None


def _from_cache(company: str) -> str | None:
    try:
        from openoutreach.mongodb.connection import get_mongodb_collection
        from datetime import datetime, timezone, timedelta

        col = get_mongodb_collection("email_domain_patterns")
        if col is None:
            return None

        cutoff = datetime.now(timezone.utc) - timedelta(days=_CACHE_TTL_DAYS)
        doc = col.find_one(
            {
                "company_name": company,
                "domain": {"$exists": True, "$nin": [None, ""]},
                "updated_at": {"$gte": cutoff},
            },
            {"domain": 1},
        )
        return doc["domain"] if doc and doc.get("domain") else None
    except Exception as exc:
        logger.debug("domain cache lookup failed: %s", exc)
        return None


def _save_cache(company: str, domain: str) -> None:
    try:
        from openoutreach.mongodb.connection import get_mongodb_collection
        from datetime import datetime, timezone

        col = get_mongodb_collection("email_domain_patterns")
        if col is None:
            return
        col.update_one(
            {"_id": domain},
            {"$set": {"company_name": company, "domain": domain, "updated_at": datetime.now(timezone.utc)}},
            upsert=True,
        )
    except Exception as exc:
        logger.debug("domain cache save failed: %s", exc)


def _from_duckduckgo(company: str) -> str | None:
    try:
        import httpx

        query = f'"{company}" official website'
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html",
        }

        resp = httpx.get(url, headers=headers, follow_redirects=True, timeout=15)
        if resp.status_code != 200:
            return None

        href_re = re.compile(r'href="(https?://(?!.*duckduckgo\.com)[^"]+)"')
        for match in href_re.finditer(resp.text):
            domain = _clean_domain(match.group(1))
            if domain and domain not in _SKIP_DOMAINS:
                return domain

    except Exception as exc:
        logger.debug("duckduckgo domain search failed for %r: %s", company, exc)

    return None


def _clean_domain(raw: str) -> str | None:
    raw = raw.strip().lower()
    m = _DOMAIN_RE.match(raw) or _DOMAIN_RE.match(f"https://{raw}")
    if not m:
        return None
    domain = m.group(1)
    if domain.startswith("www."):
        domain = domain[4:]
    if "." in domain and "/" not in domain:
        return domain
    return None
