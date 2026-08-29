# openoutreach/emails/enrichment/patterns.py
"""Generate ranked email address candidates for a (name, domain) pair.

If a Hunter.io API key is set in SiteConfig.hunter_api_key, the confirmed
domain pattern is fetched and cached in email_domain_patterns. Without a key
all 8 patterns are generated and ranked by global B2B frequency.

Pattern syntax uses {first}, {last}, {f} (first initial), {l} (last initial).
"""

from __future__ import annotations

import logging
import re
import unicodedata

logger = logging.getLogger(__name__)

# Ranked by observed B2B frequency (source: Hunter.io aggregate data)
_PATTERN_RANK: list[str] = [
    "{first}.{last}",    # ~38%
    "{first}",           # ~17%
    "{f}{last}",         # ~14%
    "{first}{last}",     # ~12%
    "{f}.{last}",        # ~8%
    "{last}",            # ~4%
    "{last}.{first}",    # ~3%
    "{first}_{last}",    # ~2%
    "{first}-{last}",    # ~1%
    "{f}{l}",            # rare
]

_HUNTER_PATTERN_MAP = {
    "first.last":  "{first}.{last}",
    "first":       "{first}",
    "flast":       "{f}{last}",
    "firstlast":   "{first}{last}",
    "f.last":      "{f}.{last}",
    "last":        "{last}",
    "last.first":  "{last}.{first}",
    "first_last":  "{first}_{last}",
    "first-last":  "{first}-{last}",
}

_CACHE_TTL_DAYS = 30
_EMAIL_LOCAL_RE = re.compile(r"^[a-zA-Z0-9.\-]+$")


def generate_candidates(
    first_name: str,
    last_name: str,
    domain: str,
    user_id: str | None = None,
) -> list[str]:
    """Return a de-duped ordered list of email candidates, most likely first."""
    first = _normalize(first_name)
    last = _normalize(last_name)
    if not first or not last:
        return []

    f = first[0]
    l = last[0]  # noqa: E741

    pattern = _get_pattern(domain, user_id)
    ordered_patterns = ([pattern] + [p for p in _PATTERN_RANK if p != pattern]) if pattern else _PATTERN_RANK

    candidates: list[str] = []
    for tmpl in ordered_patterns:
        local = _render(tmpl, first=first, last=last, f=f, l=l)
        if local and _EMAIL_LOCAL_RE.match(local):
            email = f"{local}@{domain}"
            if email not in candidates:
                candidates.append(email)

    return candidates


def _get_pattern(domain: str, user_id: str | None) -> str | None:
    cached = _from_cache(domain)
    if cached:
        return cached
    pattern = _from_hunter(domain, user_id)
    if pattern:
        _save_pattern_cache(domain, pattern, source="hunter")
    return pattern


def _render(tmpl: str, *, first: str, last: str, f: str, l: str) -> str:  # noqa: E741
    return (
        tmpl
        .replace("{first}", first)
        .replace("{last}", last)
        .replace("{f}", f)
        .replace("{l}", l)
    )


def _normalize(name: str) -> str:
    """Lowercase, strip accents, keep only alphanum."""
    name = name.strip().lower()
    name = unicodedata.normalize("NFD", name)
    name = "".join(c for c in name if unicodedata.category(c) != "Mn")
    name = re.sub(r"[\s.]", "", name)
    name = re.sub(r"[^a-z0-9]", "", name)
    return name


def _from_cache(domain: str) -> str | None:
    try:
        from openoutreach.mongodb.connection import get_mongodb_collection
        from datetime import datetime, timezone, timedelta

        col = get_mongodb_collection("email_domain_patterns")
        if col is None:
            return None

        cutoff = datetime.now(timezone.utc) - timedelta(days=_CACHE_TTL_DAYS)
        doc = col.find_one(
            {"_id": domain, "pattern": {"$exists": True, "$nin": [None, ""]}, "updated_at": {"$gte": cutoff}},
            {"pattern": 1},
        )
        return doc["pattern"] if doc and doc.get("pattern") else None
    except Exception as exc:
        logger.debug("pattern cache lookup failed for %s: %s", domain, type(exc).__name__)
        return None


def _save_pattern_cache(domain: str, pattern: str, source: str) -> None:
    try:
        from openoutreach.mongodb.connection import get_mongodb_collection
        from datetime import datetime, timezone

        col = get_mongodb_collection("email_domain_patterns")
        if col is None:
            return
        col.update_one(
            {"_id": domain},
            {"$set": {"pattern": pattern, "source": source, "updated_at": datetime.now(timezone.utc)}},
            upsert=True,
        )
    except Exception as exc:
        logger.debug("pattern cache save failed for %s: %s", domain, type(exc).__name__)


def update_pattern_from_confirmed(domain: str, first: str, last: str, email: str) -> None:
    """When a confirmed email is found, back-infer and cache its pattern."""
    first_n = _normalize(first)
    last_n = _normalize(last)
    if not first_n or not last_n:
        return

    local = email.split("@")[0].lower()
    f = first_n[0]
    l = last_n[0]  # noqa: E741

    for tmpl in _PATTERN_RANK:
        rendered = _render(tmpl, first=first_n, last=last_n, f=f, l=l)
        if rendered == local:
            _save_pattern_cache(domain, tmpl, source="verified")
            logger.debug("Inferred pattern %r for %s from confirmed email", tmpl, domain)
            return


def _from_hunter(domain: str, user_id: str | None) -> str | None:
    try:
        from openoutreach.mongodb.models import SiteConfig  # type: ignore[attr-defined]

        config = SiteConfig.load(user_id=user_id)
        api_key = getattr(config, "hunter_api_key", "") or ""
        if not api_key:
            return None

        import httpx

        resp = httpx.get(
            "https://api.hunter.io/v2/domain-search",
            params={"domain": domain, "limit": 1, "api_key": api_key},
            timeout=15,
        )
        if resp.status_code != 200:
            return None

        raw_pattern = ((resp.json().get("data") or {}).get("pattern") or "")
        return _HUNTER_PATTERN_MAP.get(raw_pattern)

    except Exception as exc:
        logger.debug("hunter pattern lookup failed for %s: %s", domain, type(exc).__name__)
        return None
