"""Shared utilities for WA lead-source scrapers."""
from __future__ import annotations

from typing import Optional


def normalize_phone(raw: str, country_code: str) -> Optional[str]:
    """Parse raw phone string and return E.164 format, or None if invalid."""
    try:
        import phonenumbers

        parsed = phonenumbers.parse(raw, country_code.upper())
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.E164
            )
    except Exception:
        pass
    return None
