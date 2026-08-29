# openoutreach/emails/enrichment/web_search.py
"""Find a confirmed work email via public web sources.

Two sources, tried in order:
  1. DuckDuckGo HTML — searches for "{first} {last}" "@{domain}".
     Conference pages, team bios, press releases, PDFs all surface here.
  2. GitHub — searches public user profiles whose public email matches domain.
     Best hit rate for engineering roles.

Returns the first extracted email passing validity + generic-address filters.
Never raises — returns None on any failure.
"""

from __future__ import annotations

import logging
import re
import urllib.parse

logger = logging.getLogger(__name__)

_GENERIC_LOCALS = frozenset({
    "info", "hello", "contact", "support", "sales", "admin", "noreply",
    "no-reply", "team", "help", "office", "mail", "hr", "billing",
    "legal", "pr", "media", "press", "careers", "jobs", "newsletter",
    "subscribe", "unsubscribe", "bounce", "postmaster", "abuse",
})

_EMAIL_RE = re.compile(r'\b([a-zA-Z0-9._%+\-]+)@([a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})\b')

_DDG_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}


def search(first_name: str, last_name: str, domain: str) -> str | None:
    """Return a confirmed email at domain for this person, or None."""
    email = _duckduckgo(first_name, last_name, domain)
    if email:
        return email
    return _github(first_name, last_name, domain)


def _duckduckgo(first: str, last: str, domain: str) -> str | None:
    try:
        import httpx

        query = f'"{first} {last}" "@{domain}"'
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"

        resp = httpx.get(url, headers=_DDG_HEADERS, follow_redirects=True, timeout=15)
        if resp.status_code != 200:
            return None

        return _extract_email(resp.text, domain)

    except Exception as exc:
        logger.debug("duckduckgo search failed (%s %s @%s): %s", first, last, domain, type(exc).__name__)
        return None


def _github(first: str, last: str, domain: str) -> str | None:
    """Search GitHub public profiles for matching name + email domain."""
    try:
        import httpx

        query = f"{first} {last} {domain} in:email"
        resp = httpx.get(
            "https://api.github.com/search/users",
            params={"q": query, "per_page": 5},
            headers={
                "User-Agent": "OpenOutreach-EmailFinder/1.0",
                "Accept": "application/vnd.github.v3+json",
            },
            timeout=15,
        )
        if resp.status_code not in (200, 422):
            return None

        for item in (resp.json().get("items") or []):
            login = item.get("login") or ""
            if not login:
                continue

            profile_resp = httpx.get(
                f"https://api.github.com/users/{login}",
                headers={"User-Agent": "OpenOutreach-EmailFinder/1.0"},
                timeout=10,
            )
            if profile_resp.status_code != 200:
                continue

            email = (profile_resp.json().get("email") or "").lower()
            if email.endswith(f"@{domain}") and _is_personal(email):
                return email

    except Exception as exc:
        logger.debug("github search failed (%s %s @%s): %s", first, last, domain, type(exc).__name__)

    return None


def _extract_email(html: str, domain: str) -> str | None:
    seen: set[str] = set()
    for m in _EMAIL_RE.finditer(html):
        local, addr_domain = m.group(1).lower(), m.group(2).lower()
        if addr_domain != domain:
            continue
        email = f"{local}@{addr_domain}"
        if email in seen:
            continue
        seen.add(email)
        if _is_personal(email):
            return email
    return None


def _is_personal(email: str) -> bool:
    return email.split("@")[0].lower() not in _GENERIC_LOCALS
