# openoutreach/emails/enrichment/waterfall.py
"""Free 4-layer email enrichment waterfall.

Layer 1 — Domain extraction  (company profile → DDG search → cache)
Layer 2 — Pattern generation (Hunter.io cache → global frequency ranking)
Layer 3 — SMTP probe         (RCPT TO verify without sending; skip catch-all)
Layer 4 — Web search         (DuckDuckGo HTML + GitHub public profiles)

Each layer is attempted in order; first hit returned.  All layers are
best-effort: failure is logged at DEBUG, waterfall continues.  Never raises.

Returned FinderResult statuses:
  "smtp_verified"  — SMTP server explicitly accepted the address
  "web_found"      — email extracted from a public web page / GitHub profile
  "pattern_only"   — no verification possible (catch-all / port-25 blocked);
                     caller may choose to accept or discard
"""

from __future__ import annotations

import logging

from openoutreach.emails.finder import FinderQuery, FinderResult

logger = logging.getLogger(__name__)

# When SMTP is indeterminate return the top pattern candidate unverified.
# Set False to skip low-confidence hits entirely.
RETURN_UNVERIFIED = True


def find_free(query: FinderQuery, user_id: str | None = None) -> FinderResult | None:
    """Run the free waterfall; return a FinderResult or None on total miss."""
    from openoutreach.emails.enrichment.domain import extract_domain
    from openoutreach.emails.enrichment.patterns import (
        generate_candidates,
        update_pattern_from_confirmed,
    )
    from openoutreach.emails.enrichment.smtp_probe import is_catch_all, probe
    from openoutreach.emails.enrichment.web_search import search

    # Layer 1: domain
    domain = extract_domain(
        company=query.company,
        cached_profile=query.cached_profile,
    )
    if not domain:
        logger.debug("waterfall: no domain for company=%r", query.company)
        return None

    # Layer 2: candidates
    candidates = generate_candidates(
        first_name=query.first_name,
        last_name=query.last_name,
        domain=domain,
        user_id=user_id,
    )
    if not candidates:
        logger.debug("waterfall: no candidates for %s %s @%s", query.first_name, query.last_name, domain)
        return None

    # Layer 3: SMTP probe (skip when catch-all)
    catch_all = is_catch_all(domain)
    if not catch_all:
        for email in candidates:
            result = probe(email)
            if result is True:
                logger.info("waterfall: smtp_verified %s", email)
                update_pattern_from_confirmed(domain, query.first_name, query.last_name, email)
                return FinderResult(email=email, status="smtp_verified")
            elif result is False:
                continue
            # None → indeterminate; try next candidate

    # Layer 4: web search
    found = search(query.first_name, query.last_name, domain)
    if found:
        logger.info("waterfall: web_found %s", found)
        update_pattern_from_confirmed(domain, query.first_name, query.last_name, found)
        return FinderResult(email=found, status="web_found")

    # Fallback: top pattern candidate unverified
    if RETURN_UNVERIFIED and candidates:
        logger.debug("waterfall: pattern_only %s", candidates[0])
        return FinderResult(email=candidates[0], status="pattern_only")

    return None
