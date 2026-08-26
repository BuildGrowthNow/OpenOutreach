# openoutreach/emails/enrichment/smtp_probe.py
"""Verify email existence via SMTP RCPT TO without sending any message.

Connects to the domain's MX server, issues EHLO + MAIL FROM + RCPT TO, then
QUITs immediately. No email is ever sent.

Return values:
  True  — server accepted the address (definite hit)
  False — server rejected with a permanent 5xx code (definite miss)
  None  — indeterminate: catch-all domain, connection refused, timeout,
           or port-25 blocked (e.g. EC2). Caller treats as unknown.

Notes:
  - Many large providers (Google Workspace, M365) respond 250 to everything
    to prevent enumeration. Detect with is_catch_all() first.
  - EC2 and most cloud providers block outbound port 25. The probe returns
    None on connection failure, so the waterfall transparently falls through
    to the web-search layer.
  - Desktop daemon (residential IP) gets ~60% hit rate on B2B domains.
"""

from __future__ import annotations

import logging
import smtplib
import socket
import uuid

logger = logging.getLogger(__name__)

_PROBE_TIMEOUT_S = 10
_PROBE_FROM = "probe@openoutreach.internal"
_PROBE_HELO = "mail.openoutreach.internal"

# SMTP 5xx codes that definitively mean "address does not exist"
_REJECT_CODES = frozenset({550, 551, 553, 554})

# In-process cache for catch-all results (resets per daemon run — intentional)
_catchall_cache: dict[str, bool] = {}


def is_catch_all(domain: str) -> bool:
    """True if the domain accepts all RCPT TO (enumeration is useless there)."""
    if domain in _catchall_cache:
        return _catchall_cache[domain]

    fake = f"definitely-not-real-{uuid.uuid4().hex[:8]}@{domain}"
    result = _probe_raw(fake, domain)
    catch_all = result is True
    _catchall_cache[domain] = catch_all
    return catch_all


def probe(email: str) -> bool | None:
    """Probe a single address. Returns True/False/None (see module docstring)."""
    domain = email.split("@", 1)[1]
    return _probe_raw(email, domain)


def _probe_raw(email: str, domain: str) -> bool | None:
    mx = _get_mx(domain)
    if mx is None:
        return None

    try:
        with smtplib.SMTP(timeout=_PROBE_TIMEOUT_S) as smtp:
            smtp.connect(mx, 25)
            smtp.helo(_PROBE_HELO)
            smtp.mail(_PROBE_FROM)
            code, _ = smtp.rcpt(email)
            smtp.quit()
        return code == 250
    except smtplib.SMTPRecipientsRefused as exc:
        code = _first_code(exc)
        if code in _REJECT_CODES:
            return False
        return None
    except smtplib.SMTPConnectError:
        logger.debug("smtp_probe: connect refused for %s — port 25 may be blocked", domain)
        return None
    except (smtplib.SMTPException, OSError, socket.timeout, TimeoutError) as exc:
        logger.debug("smtp_probe: %s for %s: %s", type(exc).__name__, email, exc)
        return None


def _get_mx(domain: str) -> str | None:
    """Look up the lowest-preference MX host via Google DNS-over-HTTPS."""
    try:
        import httpx

        resp = httpx.get(
            "https://dns.google/resolve",
            params={"name": domain, "type": "MX"},
            timeout=8,
        )
        if resp.status_code != 200:
            return None

        answers = resp.json().get("Answer") or []
        records: list[tuple[int, str]] = []
        for a in answers:
            parts = str(a.get("data", "")).split()
            if len(parts) == 2:
                try:
                    records.append((int(parts[0]), parts[1].rstrip(".")))
                except ValueError:
                    pass

        return min(records, key=lambda r: r[0])[1] if records else None

    except Exception as exc:
        logger.debug("smtp_probe: MX lookup failed for %s: %s", domain, exc)
        return None


def _first_code(exc: smtplib.SMTPRecipientsRefused) -> int:
    for item in exc.recipients.values():
        return item[0]
    return 0
