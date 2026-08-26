# openoutreach/emails/finder.py
"""Resolve a work email for a qualified lead.

`resolve_email` is the public entry point. Runs the free 6-layer waterfall:
domain → website scrape → WHOIS/RDAP → pattern generation → SMTP probe → web search.

A genuine miss (all layers tried, nothing found) returns None.
The waterfall never raises — errors degrade gracefully per layer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


class FinderUnavailable(Exception):
    """Finder could not run (service unreachable).
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
    status: str  # "smtp_verified" | "site_found" | "whois_found" | "web_found" | "pattern_only"


def resolve_email(query: FinderQuery, user_id: str | None = None) -> FinderResult | None:
    """Resolve one lead's work email via the free enrichment waterfall.

    Returns a FinderResult on hit, None on genuine miss.
    """
    try:
        from openoutreach.emails.enrichment.waterfall import find_free
        return find_free(query, user_id=user_id)
    except Exception as exc:
        logger.warning("email waterfall raised unexpectedly: %s", exc)
        return None
