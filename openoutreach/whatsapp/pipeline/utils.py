"""Shared utilities for WA lead-source scrapers."""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def normalize_phone(raw: str, country_code: str) -> Optional[str]:
    """Parse raw phone string and return E.164 format, or None if invalid."""
    try:
        import phonenumbers
    except ImportError:
        logger.warning("phonenumbers package not installed — phone normalization disabled")
        return None
    try:
        parsed = phonenumbers.parse(raw, country_code.upper())
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.E164
            )
    except Exception:
        pass
    return None
