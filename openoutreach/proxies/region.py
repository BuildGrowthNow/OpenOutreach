"""Proxy region validation shared by account creation and the admin API."""
from __future__ import annotations

import re
from typing import Optional

_ISO2_RE = re.compile(r"^[A-Za-z]{2}$")


class RegionError(ValueError):
    """Raised when a proxy region cannot be normalized."""


def normalize_country(country: Optional[str]) -> str:
    """Return an uppercase ISO-3166 alpha-2 country code."""
    value = (country or "").strip().upper()
    if not _ISO2_RE.match(value):
        raise RegionError("A 2-letter country code is required (for example US)")
    return value


def normalize_region(
    country: Optional[str],
    subdivision: Optional[str] = None,
    city: Optional[str] = None,
) -> tuple[str, Optional[str], Optional[str]]:
    """Normalize a country/subdivision/city triple.

    Country is mandatory. Subdivision and city are optional; empty strings are
    stored as ``None`` so proxy matching stays predictable.
    """
    normalized_country = normalize_country(country)
    normalized_subdivision = (subdivision or "").strip().upper() or None
    normalized_city = (city or "").strip() or None
    if normalized_subdivision and len(normalized_subdivision) > 16:
        raise RegionError("Subdivision is too long")
    if normalized_city and len(normalized_city) > 120:
        raise RegionError("City is too long")
    return normalized_country, normalized_subdivision, normalized_city
