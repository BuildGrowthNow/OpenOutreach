# openoutreach/emails/finder.py
"""Resolve a work email for a qualified lead.

`resolve_email` is the public entry point.

Priority:
  1. Free 6-layer waterfall (domain → website scrape → WHOIS → patterns → SMTP → web search) — always tried
  2. BetterContact paid API  — only if SiteConfig.finder_api_key is set AND free missed

`FinderUnavailable` is raised only on BetterContact transport errors (network
down, HTTP error, poll timeout). The free waterfall never raises it.

`Lead.resolve_api_email()` catches FinderUnavailable and returns None (retry
next cycle). A genuine miss (all layers tried, nothing found) returns False.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


class FinderUnavailable(Exception):
    """Finder could not run — no API key or service unreachable.
    Distinct from a genuine miss (finder ran, found no email)."""


@dataclass(frozen=True)
class FinderQuery:
    """A lead to resolve. Provide as much context as available; more = better hits."""

    linkedin_url: str = ""
    first_name: str = ""
    last_name: str = ""
    company: str = ""
    company_domain: str = ""
    cached_profile: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FinderResult:
    email: str
    status: str  # "smtp_verified" | "site_found" | "whois_found" | "web_found" | "pattern_only" | "bettercontact"


def resolve_email(query: FinderQuery, user_id: str | None = None) -> FinderResult | None:
    """Resolve one lead's work email.

    Returns a FinderResult on hit, None on genuine miss. Raises FinderUnavailable
    only when BetterContact transport fails (network / timeout).
    """
    # Always try free waterfall first
    try:
        from openoutreach.emails.enrichment.waterfall import find_free
        result = find_free(query, user_id=user_id)
        if result:
            return result
    except Exception as exc:
        logger.warning("free waterfall raised unexpectedly: %s", exc)

    # BetterContact fallback when key is configured
    try:
        from openoutreach.mongodb.models import SiteConfig  # type: ignore[attr-defined]
        api_key = (SiteConfig.load(user_id=user_id).finder_api_key or "").strip()
    except Exception:
        api_key = ""

    if api_key:
        from openoutreach.emails import bettercontact
        bc_result = bettercontact.find_email(api_key, query)
        if bc_result:
            return FinderResult(email=bc_result.email, status="bettercontact")

    return None
