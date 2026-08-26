# openoutreach/emails/enrichment/waterfall.py
"""Free 6-layer email enrichment waterfall.

Layer 1 — Domain extraction  (company profile → DDG search → cache)
Layer 2 — Website scrape     (company team/about/contact pages → direct email hit)
Layer 3 — WHOIS/RDAP         (domain registrant email, for founders/owners)
Layer 4 — Pattern generation (Hunter.io cache → global frequency ranking)
Layer 5 — SMTP probe         (RCPT TO verify without sending; skip catch-all)
Layer 6 — Web search         (DuckDuckGo HTML + GitHub public profiles)

Each layer is attempted in order; first hit returned.  All layers are
best-effort: failure is logged at DEBUG, waterfall continues.  Never raises.

Layers 2 and 3 are direct finders — when they hit, no pattern generation
or SMTP probing is needed at all.

Returned FinderResult statuses:
  "smtp_verified"  — SMTP server explicitly accepted the address
  "site_found"     — email extracted directly from the company website
  "whois_found"    — email from domain RDAP/WHOIS registrant record
  "web_found"      — email extracted from a public web page / GitHub profile
  "pattern_only"   — no verification possible (catch-all / port-25 blocked);
                     caller may choose to accept or discard
"""

from __future__ import annotations

import logging

from openoutreach.emails.finder import FinderQuery, FinderResult

logger = logging.getLogger(__name__)

def _return_unverified(user_id: str | None) -> bool:
    """Read email_accept_unverified from SiteConfig; default False."""
    if not user_id:
        return False
    try:
        from openoutreach.mongodb.models import SiteConfig
        return SiteConfig.load(user_id=user_id).email_accept_unverified
    except Exception:
        return False


def find_free(query: FinderQuery, user_id: str | None = None) -> FinderResult | None:
    """Run the free waterfall; return a FinderResult or None on total miss."""
    from openoutreach.emails.enrichment.domain import extract_domain
    from openoutreach.emails.enrichment.patterns import (
        generate_candidates,
        update_pattern_from_confirmed,
    )
    from openoutreach.emails.enrichment.smtp_probe import is_catch_all, probe
    from openoutreach.emails.enrichment.web_search import search
    from openoutreach.emails.enrichment.website_scraper import scrape_company_email
    from openoutreach.emails.enrichment.whois_lookup import lookup_registrant_email

    # Layer 1: domain
    domain = extract_domain(
        company=query.company,
        cached_profile=query.cached_profile,
    )
    if not domain:
        logger.debug("waterfall: no domain for company=%r", query.company)
        return None

    # Layer 2: company website scrape (direct hit — no SMTP needed)
    site_email = scrape_company_email(domain, query.first_name, query.last_name)
    if site_email:
        logger.info("waterfall: site_found %s", site_email)
        update_pattern_from_confirmed(domain, query.first_name, query.last_name, site_email)
        return FinderResult(email=site_email, status="site_found")

    # Layer 3: WHOIS/RDAP (best for founders/owners of small companies)
    rdap_email = lookup_registrant_email(domain, query.first_name, query.last_name)
    if rdap_email:
        logger.info("waterfall: whois_found %s", rdap_email)
        update_pattern_from_confirmed(domain, query.first_name, query.last_name, rdap_email)
        return FinderResult(email=rdap_email, status="whois_found")

    # Layer 4: pattern candidates
    candidates = generate_candidates(
        first_name=query.first_name,
        last_name=query.last_name,
        domain=domain,
        user_id=user_id,
    )
    if not candidates:
        logger.debug("waterfall: no candidates for %s %s @%s", query.first_name, query.last_name, domain)
        return None

    # Layer 5: SMTP probe (skip when catch-all)
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

    # Layer 6: web search (DuckDuckGo HTML + GitHub)
    found = search(query.first_name, query.last_name, domain)
    if found:
        logger.info("waterfall: web_found %s", found)
        update_pattern_from_confirmed(domain, query.first_name, query.last_name, found)
        return FinderResult(email=found, status="web_found")

    # Fallback: top pattern candidate unverified (opt-in via SiteConfig.email_accept_unverified)
    if _return_unverified(user_id) and candidates:
        logger.debug("waterfall: pattern_only %s", candidates[0])
        return FinderResult(email=candidates[0], status="pattern_only")

    return None
