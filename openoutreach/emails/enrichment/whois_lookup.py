# openoutreach/emails/enrichment/whois_lookup.py
"""RDAP registrant email lookup.

Queries rdap.org (free, no key) for domain registration data and returns
the registrant email when its local part matches the target person's name.

Works best for: founders, owners, solo consultants at small companies where
the domain is registered in the person's name.

GDPR privacy shields (domainsbyproxy.com, withheldforprivacy.com, etc.)
are detected and skipped — returns None in those cases.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT_S = 8

_PRIVACY_DOMAINS = frozenset({
    "domainsbyproxy.com",
    "privacyguardian.org",
    "whoisguard.com",
    "contactprivacy.com",
    "networksolutionsprivateregistration.com",
    "domainprivacygroup.com",
    "privatebyreg.com",
    "anonymize.it",
    "perfect-privacy.com",
    "withheldforprivacy.com",
    "redacted.invalid",
    "privacy.icann.org",
    "1and1-private-registration.com",
})


def _normalize(name: str) -> str:
    name = name.strip().lower()
    name = unicodedata.normalize("NFD", name)
    name = "".join(c for c in name if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", name)


def _is_privacy_email(email: str) -> bool:
    domain = email.split("@")[-1].lower() if "@" in email else ""
    return any(p in domain for p in _PRIVACY_DOMAINS)


def _name_matches(email: str, first: str, last: str) -> bool:
    local = email.split("@")[0].lower() if "@" in email else email.lower()
    first_n = _normalize(first)
    last_n = _normalize(last)
    if first_n and first_n in local:
        return True
    if last_n and last_n in local:
        return True
    return False


def _collect_emails(entity: dict) -> list[str]:
    """Recursively collect email addresses from an RDAP entity and its sub-entities."""
    emails: list[str] = []
    vcard = entity.get("vcardArray")
    if vcard and isinstance(vcard, list) and len(vcard) > 1:
        for prop in vcard[1]:
            if isinstance(prop, (list, tuple)) and len(prop) >= 4:
                if str(prop[0]).lower() == "email":
                    val = str(prop[3])
                    if "@" in val:
                        emails.append(val.lower().strip())
    for sub in entity.get("entities", []):
        emails.extend(_collect_emails(sub))
    return emails


def lookup_registrant_email(
    domain: str,
    first_name: str,
    last_name: str,
) -> Optional[str]:
    """Query RDAP for domain registration; return registrant email if it matches the person."""
    try:
        resp = httpx.get(
            f"https://rdap.org/domain/{domain}",
            timeout=_TIMEOUT_S,
            follow_redirects=True,
            headers={"Accept": "application/rdap+json"},
        )
        if resp.status_code != 200:
            return None

        data = resp.json()
        all_emails = _collect_emails({"entities": data.get("entities", [])})

        for email in all_emails:
            if _is_privacy_email(email):
                continue
            if _name_matches(email, first_name, last_name):
                logger.info("whois_lookup: registrant match %s for %s", email, domain)
                return email

        return None

    except Exception as exc:
        logger.debug("whois_lookup: RDAP failed for %s: %s", domain, exc)
        return None
