# openoutreach/emails/imap_checker.py
"""IMAP reply detector.

Connects read-only to a Mailbox's IMAP account and searches for inbound
replies to a given Message-ID. Returns the plain-text body of the first reply
found, or None when IMAP is unconfigured, unreachable, or no reply exists.

Never raises — all errors are logged at DEBUG so the caller degrades gracefully.
"""

from __future__ import annotations

import email as email_lib
import imaplib
import logging
from email import policy

logger = logging.getLogger(__name__)


def find_reply(mailbox, original_message_id: str) -> str | None:
    """Return text body of first reply to *original_message_id*, or None.

    Searches the mailbox INBOX for messages whose In-Reply-To header matches
    the given message ID. Returns None when IMAP is not configured on the
    mailbox, when the connection fails, or when no matching reply exists.
    """
    if not mailbox.imap_host or not original_message_id:
        return None

    imap_port = mailbox.imap_port or 993

    try:
        with imaplib.IMAP4_SSL(mailbox.imap_host, imap_port) as imap:
            imap.login(mailbox.username, mailbox.password)
            imap.select("INBOX", readonly=True)

            # Try both with and without angle brackets — servers vary.
            clean_id = original_message_id.strip("<>")
            for candidate in (f"<{clean_id}>", clean_id):
                status, data = imap.search(None, "HEADER", "In-Reply-To", candidate)
                if status == "OK":
                    uids = (data[0] or b"").split()
                    if uids:
                        return _fetch_text(imap, uids[0])

    except Exception as exc:
        logger.debug(
            "imap_checker: could not check replies for %s: %s",
            original_message_id, exc,
        )

    return None


def _fetch_text(imap: imaplib.IMAP4_SSL, uid: bytes) -> str:
    """Fetch the RFC822 body of *uid* and return its text/plain part."""
    try:
        status, msg_data = imap.fetch(uid.decode(), "(RFC822)")
        if status != "OK" or not msg_data or not msg_data[0]:
            return "replied"
        raw = msg_data[0][1]
        if not isinstance(raw, bytes):
            return "replied"
        msg = email_lib.message_from_bytes(raw, policy=policy.default)
        text = _extract_plain(msg)
        return text or "replied"
    except Exception:
        return "replied"


def _extract_plain(msg) -> str:
    """Return the text/plain body from a (possibly multipart) message."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    return str(part.get_content())
                except Exception:
                    pass
    else:
        if msg.get_content_type() == "text/plain":
            try:
                return str(msg.get_content())
            except Exception:
                pass
    return ""
