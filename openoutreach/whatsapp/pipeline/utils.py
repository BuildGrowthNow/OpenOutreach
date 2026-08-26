"""Shared utilities for WA lead-source scrapers."""
from __future__ import annotations

import logging
import random
import re
import time
from typing import Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

_T = TypeVar("_T")

# Desktop UA pool - rotated per browser context. Updated to current Chrome/Firefox versions.
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.6; rv:131.0) Gecko/20100101 Firefox/131.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
]


def random_user_agent() -> str:
    """Return a random desktop user-agent string from the pool."""
    return random.choice(_USER_AGENTS)


# DDG redirect wrapper — same pattern across wa_groups and facebook scrapers.
_DDG_REDIRECT_MARKER = "/l/?uddg="


def decode_ddg_href(href: str) -> str:
    """Unwrap DDG redirect URL (/l/?uddg=...) if present; return href unchanged otherwise."""
    if _DDG_REDIRECT_MARKER in href:
        try:
            import urllib.parse
            return urllib.parse.unquote(href.split("uddg=")[-1].split("&")[0])
        except Exception:
            pass
    return href


# Contextual phone regex: only match numbers that appear near phone-related keywords.
# Prevents false positives from order numbers, zip codes, and other digit sequences.
_PHONE_CONTEXT_RE = re.compile(
    r"(?:phones?|tel(?:efon[eo]?)?|fone|call|whatsapp|cell|mobile"
    r"|celular|m[oó]vil|handy|contact|hotline|helpline|ligar|liame)"
    r"[\s\S]{0,80}"
    r"(\+?[\d][\d\s\-\.\(\)]{5,18}[\d])",
    re.IGNORECASE,
)


def phone_from_html_text(text: str, country_code: str) -> Optional[str]:
    """Extract first valid E.164 phone from plain text using contextual proximity scan."""
    for m in _PHONE_CONTEXT_RE.finditer(text):
        candidate = m.group(1).strip()
        if sum(c.isdigit() for c in candidate) >= 7:
            phone = normalize_phone(candidate, country_code)
            if phone:
                return phone
    return None


def phone_from_page(page, country_code: str) -> str:
    """Best-effort phone extraction from a Playwright page.

    Priority:
    1. tel: links (business placed it intentionally, most reliable)
    2. Contextual body-text scan near phone-related keywords
    Returns empty string when no valid phone found.
    """
    tel_el = page.query_selector("a[href^='tel:']")
    if tel_el:
        raw = (tel_el.get_attribute("href") or "").replace("tel:", "").strip()
        if raw:
            phone = normalize_phone(raw, country_code)
            if phone:
                return phone
    try:
        body = page.inner_text("body")
    except Exception:
        body = ""
    return phone_from_html_text(body, country_code) or ""


def is_likely_whatsapp_number(phone_e164: str) -> bool:
    """Return True if the E.164 number is likely capable of receiving WhatsApp messages.

    Rejects definitive landlines, toll-free, VOIP, pager, and UAN numbers.
    Accepts MOBILE, FIXED_LINE_OR_MOBILE (common in LatAm), PERSONAL_NUMBER, and UNKNOWN
    (don't reject what we can't determine).
    """
    try:
        import phonenumbers
        parsed = phonenumbers.parse(phone_e164)
        number_type = phonenumbers.number_type(parsed)
        PhoneNumberType = phonenumbers.PhoneNumberType
        _REJECT = {
            PhoneNumberType.FIXED_LINE,
            PhoneNumberType.TOLL_FREE,
            PhoneNumberType.PREMIUM_RATE,
            PhoneNumberType.SHARED_COST,
            PhoneNumberType.VOIP,
            PhoneNumberType.PAGER,
            PhoneNumberType.UAN,
        }
        return number_type not in _REJECT
    except Exception:
        return True  # parse failed — don't reject


def normalize_phone(raw: str, country_code: str) -> Optional[str]:
    """Parse raw phone string and return E.164 format, or None if invalid."""
    try:
        import phonenumbers
    except ImportError:
        logger.warning("phonenumbers package not installed - phone normalization disabled")
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


def scrape_retry(
    fn: Callable[[], _T],
    max_attempts: int = 3,
    base_delay: float = 2.0,
    label: str = "",
) -> _T:
    """Call fn() up to max_attempts times with exponential backoff on any exception.

    Re-raises the last exception if all attempts are exhausted.
    """
    last_exc: BaseException = RuntimeError("scrape_retry: no attempts made")
    for attempt in range(max_attempts):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if attempt < max_attempts - 1:
                delay = base_delay * (2 ** attempt) + random.uniform(0.0, 1.0)
                logger.warning(
                    "scrape_retry[%s]: attempt %d/%d failed (%s) - retrying in %.1fs",
                    label or getattr(fn, "__name__", "?"),
                    attempt + 1,
                    max_attempts,
                    exc,
                    delay,
                )
                time.sleep(delay)
    raise last_exc
