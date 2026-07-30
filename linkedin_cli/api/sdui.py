"""Parsers for LinkedIn's server-driven-UI (RSC) responses.

Some flagship-web surfaces — including the profile "Contact info" overlay —
are rendered via server-driven UI: a POST returns an RSC stream (React flight
format) rather than a Voyager JSON blob.  These helpers extract the fields we
care about from that text payload.

RSC stream format
-----------------
The response body is a newline-delimited sequence of "flight rows", each with
an optional single-character tag prefix:

    J:0:{"some":"json"}
    J:1:[ref,{...}]
    <blank line>

Tags used by LinkedIn:
  J   — plain JSON value (string, number, object, array)
  M   — module descriptor (ignored)
  S   — string chunk (ignored)
  E   — error chunk (logged but not fatal)

The ``J`` tag is the most common; some rows carry no tag at all and begin
directly with a JSON-parseable character (``{``, ``[``, ``"``).

We scan every row that looks JSON-parseable, recursively walk the decoded
structure, and collect ``mailto:`` / ``tel:`` URLs wherever they appear as
string values.  A secondary regex scan over the raw text covers anything the
JSON walk might miss (e.g. contact data embedded in a non-JSON row or a
slightly malformed chunk).  Both result sets are merged and de-duplicated.

Regression detection
--------------------
When the payload is non-trivial (> 200 bytes) but both methods find nothing,
a WARNING is logged with a short snippet of the raw text.  This surfaces API
format changes in production logs without crashing the task.  If DUMP_PAGES is
enabled the full payload is also written to the fixtures directory so it can
be inspected offline.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ── Regex fallback patterns ────────────────────────────────────────────────────
#
# Match RFC 6068 ``mailto:`` and ``tel:`` URIs in the raw text.  The stop-set
# ``[^"\\<>\s]`` avoids bleeding into adjacent JSON tokens.

_MAILTO_RE = re.compile(r"mailto:([^\"\\<>\s]+)")
_TEL_RE = re.compile(r"tel:([^\"\\<>\s]+)")

# LinkedIn's newer RSC format (React Flight / Next.js) encodes contact data as
# plain string props inside component trees — no mailto:/tel: URI wrappers.
# These patterns catch bare email addresses and phone numbers in that format.
# Email: standard RFC 5322 local@domain.tld, anchored by JSON string delimiters.
_EMAIL_RE = re.compile(
    r'"([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})"'
)
# Phone: starts with + or digit, 7-20 chars of digits/spaces/dashes/parens,
# anchored by JSON string delimiters.
_PHONE_RE = re.compile(
    r'"(\+?[\d][\d\s\-().]{6,19})"'
)

# Minimum raw-payload size (bytes) before we emit a regression warning when both
# parsers find nothing.  Keeps noise down for truly-empty API responses.
_EMPTY_WARN_THRESHOLD = 200


# ── Helpers ────────────────────────────────────────────────────────────────────

def _unique_ordered(values: list[str]) -> list[str]:
    """De-duplicate while preserving first-seen order."""
    return list(dict.fromkeys(values))


def _collect_contact_urls(obj: Any, emails: list[str], phones: list[str]) -> None:
    """Recursively walk *obj* and collect mailto/tel URL strings in-place."""
    if isinstance(obj, str):
        if obj.startswith("mailto:"):
            addr = obj[len("mailto:"):]
            if addr:
                emails.append(addr)
        elif obj.startswith("tel:"):
            num = obj[len("tel:"):]
            if num:
                phones.append(num)
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect_contact_urls(v, emails, phones)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            _collect_contact_urls(item, emails, phones)
    # Numbers, booleans, None — nothing to extract.


def _try_decode_row(row: str) -> Any:
    """Return a decoded Python object for an RSC flight row, or None on failure.

    Strips the optional tag prefix (``J:N:``, ``M:N:``, etc.) then attempts
    JSON decoding.  Returns None for empty rows, module descriptors (``M``),
    error chunks (``E``), or rows that do not produce a dict/list.
    """
    stripped = row.strip()
    if not stripped:
        return None

    # Detect and handle error chunks explicitly.
    if stripped.startswith("E:"):
        try:
            err = json.loads(stripped[2:].split(":", 1)[-1])
            logger.debug("RSC error chunk in contact-info response: %s", err)
        except Exception:
            logger.debug("RSC error chunk (unparseable): %.120s", stripped)
        return None

    # Skip module descriptor rows ("M:…") — they carry import metadata only.
    if stripped.startswith("M:"):
        return None

    # Strip the tag prefix: one alpha + colon + optional index + colon
    # e.g. "J:0:", "J:42:", "S:1:".  Use a simple heuristic: if the second
    # or third character is ":", advance past the prefix.
    content = stripped
    if len(stripped) >= 2 and stripped[1] == ":":
        # "J:{rest}" — but rest may itself start "N:" (J:0:{...})
        rest = stripped[2:]
        # Check for a second colon that separates the index from the payload.
        colon_pos = rest.find(":")
        if colon_pos != -1 and rest[:colon_pos].isdigit():
            content = rest[colon_pos + 1:]
        else:
            content = rest

    content = content.strip()
    if not content or content[0] not in ("{", "[", '"', "t", "f", "n", "0", "1",
                                          "2", "3", "4", "5", "6", "7", "8", "9",
                                          "-"):
        return None

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return None


# ── Primary RSC parser ─────────────────────────────────────────────────────────

def _parse_rsc_chunks(rsc_text: str) -> tuple[list[str], list[str]]:
    """Walk every JSON-decodeable RSC row and collect mailto/tel values.

    Returns ``(emails, phone_numbers)`` — un-deduplicated, in document order.
    """
    emails: list[str] = []
    phones: list[str] = []

    for row in rsc_text.splitlines():
        decoded = _try_decode_row(row)
        if decoded is None:
            continue
        _collect_contact_urls(decoded, emails, phones)

    return emails, phones


# ── Regex fallback ────────────────────────────────────────────────────────────

def _parse_rsc_regex(rsc_text: str) -> tuple[list[str], list[str]]:
    """Regex scan over the raw text — catches values missed by the JSON walker.

    Three passes in priority order:
    1. ``mailto:`` URIs — classic RSC format.
    2. ``tel:`` URIs — classic RSC format.
    3. Bare email / phone strings — newer React Flight / Next.js RSC format
       where contact data appears as plain JSON string props with no URI prefix.
    """
    emails = _MAILTO_RE.findall(rsc_text) + _EMAIL_RE.findall(rsc_text)
    phones = _TEL_RE.findall(rsc_text) + _PHONE_RE.findall(rsc_text)
    return emails, phones


# ── Regression logging ────────────────────────────────────────────────────────

def _warn_empty_result(rsc_text: str) -> None:
    """Emit a WARNING when a non-trivial payload yields no contact data at all."""
    snippet = rsc_text[:400].replace("\n", " ↵ ")
    logger.warning(
        "parse_contact_info: non-trivial payload (%d bytes) but no mailto/tel "
        "found — LinkedIn may have changed the RSC format.  "
        "Raw snippet: %.400s",
        len(rsc_text),
        snippet,
    )
    # If HTML/page snapshots are enabled, save the full payload for offline analysis.
    try:
        from linkedin_cli.conf import DUMP_PAGES, FIXTURE_PAGES_DIR
        if DUMP_PAGES:
            dest = FIXTURE_PAGES_DIR / "contact_info_rsc"
            dest.mkdir(parents=True, exist_ok=True)
            import time as _time
            ts = int(_time.time())
            (dest / f"payload_{ts}.txt").write_text(rsc_text, encoding="utf-8")
            logger.info("Saved RSC payload → %s/payload_%d.txt", dest, ts)
    except Exception as dump_err:
        logger.debug("Could not save RSC dump: %s", dump_err)


# ── Public API ────────────────────────────────────────────────────────────────

def parse_contact_info(rsc_text: str) -> dict:
    """Extract contact details from a ProfileContactDetailsOverlay RSC payload.

    Runs two complementary extraction passes and merges the results:

    1. **RSC chunk parser** — decodes each flight row as JSON and recursively
       walks the object graph collecting ``mailto:`` / ``tel:`` string values.
       Precise: only extracts real URL-valued fields.

    2. **Regex fallback** — scans the raw text for ``mailto:`` / ``tel:``
       patterns.  Catches values in malformed or non-JSON rows that the
       structured walker cannot reach.

    Both passes run on every call; their results are merged and de-duplicated
    in document order.  When the payload is non-trivial but both passes find
    nothing, a WARNING is logged with a raw snippet to surface format changes.

    Returns ``{email, emails, phone_numbers}``.  ``email`` is the first address
    found (or ``None``).  Only fields the member exposes to your network appear
    — email is typically present only for 1st-degree connections.
    """
    # Pass 1: structured RSC chunk walk.
    chunk_emails, chunk_phones = _parse_rsc_chunks(rsc_text)

    # Pass 2: regex scan over raw text.
    regex_emails, regex_phones = _parse_rsc_regex(rsc_text)

    # Merge: chunk-walker results first (higher precision), regex fills gaps.
    all_emails = _unique_ordered(chunk_emails + regex_emails)
    all_phones = _unique_ordered(chunk_phones + regex_phones)

    if not all_emails and not all_phones and len(rsc_text) > _EMPTY_WARN_THRESHOLD:
        _warn_empty_result(rsc_text)

    return {
        "email": all_emails[0] if all_emails else None,
        "emails": all_emails,
        "phone_numbers": all_phones,
    }
