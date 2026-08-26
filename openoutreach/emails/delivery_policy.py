# openoutreach/emails/delivery_policy.py
"""SMTP delivery outcome classification.

Maps any SMTP (or transport) exception to one of four outcome values so the
task handler can take the right action without a growing if/elif chain.

Outcomes:
  BOUNCE_DEAL   — permanent address rejection; mark deal EMAIL_BOUNCED, suppress lead
  RETRY_LATER   — transient failure; return without raising (scheduler replans next cycle)
  PAUSE_MAILBOX — auth/credentials broken; log at ERROR, return (needs manual fix)
  RAISE         — unexpected error class; caller re-raises for daemon to mark task FAILED

SMTP code reference:
  4xx (soft): 421 service unavailable, 450/451/452 mailbox / system temporarily unavailable
  5xx (hard): 550 mailbox unavailable, 551 user not local, 552/553 address not allowed,
              554 transaction failed / spam, 534/535 auth failed
"""

from __future__ import annotations

import smtplib
from enum import Enum, auto


class SmtpOutcome(Enum):
    BOUNCE_DEAL = auto()
    RETRY_LATER = auto()
    PAUSE_MAILBOX = auto()
    RAISE = auto()


# Permanent address failures — suppress the lead's email permanently.
_HARD_BOUNCE_CODES = frozenset({550, 551, 552, 553, 554})

# Transient server-side failures — safe to retry on the next scheduler cycle.
_TRANSIENT_CODES = frozenset({421, 450, 451, 452})

# Sending-mailbox credential failures — need operator intervention, not retries.
_AUTH_FAIL_CODES = frozenset({534, 535})


def classify(exc: Exception) -> SmtpOutcome:
    """Return the delivery outcome for *exc*.

    Handles the two primary exception hierarchies:
    - smtplib.SMTPAuthenticationError (subclass of SMTPResponseException) — checked first
    - smtplib.SMTPRecipientsRefused — per-recipient code dict
    - smtplib.SMTPResponseException — single smtp_code
    - Network / transport errors (OSError, TimeoutError, SMTPConnectError, etc.)
    """
    # Auth failures first — SMTPAuthenticationError IS a SMTPResponseException,
    # so the subclass must be checked before the parent.
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return SmtpOutcome.PAUSE_MAILBOX

    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        code = _first_recipient_code(exc)
        if code in _HARD_BOUNCE_CODES:
            return SmtpOutcome.BOUNCE_DEAL
        if code in _TRANSIENT_CODES:
            return SmtpOutcome.RETRY_LATER
        return SmtpOutcome.RAISE

    if isinstance(exc, smtplib.SMTPResponseException):
        code = exc.smtp_code
        if code in _HARD_BOUNCE_CODES:
            return SmtpOutcome.BOUNCE_DEAL
        if code in _TRANSIENT_CODES:
            return SmtpOutcome.RETRY_LATER
        if code in _AUTH_FAIL_CODES:
            return SmtpOutcome.PAUSE_MAILBOX
        return SmtpOutcome.RAISE

    # Transport-level failures: connection refused, timeout, server disconnected mid-session.
    if isinstance(exc, (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected,
                        TimeoutError, OSError)):
        return SmtpOutcome.RETRY_LATER

    return SmtpOutcome.RAISE


def _first_recipient_code(exc: smtplib.SMTPRecipientsRefused) -> int:
    for _addr, (code, _msg) in exc.recipients.items():
        return code
    return 0
