"""Shared utilities for WA lead-source scrapers."""
from __future__ import annotations

import logging
import random
from typing import Optional

logger = logging.getLogger(__name__)

# Realistic desktop UA pool — rotated per browser context to avoid a single
# static UA being a trivial bot fingerprint.
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
]


def random_user_agent() -> str:
    """Return a random desktop user-agent string from the pool."""
    return random.choice(_USER_AGENTS)


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
