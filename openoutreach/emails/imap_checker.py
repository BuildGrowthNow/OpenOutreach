# openoutreach/emails/imap_checker.py
"""IMAP reply detector.

Connects read-only to a Mailbox's IMAP account and searches for inbound
replies to a given Message-ID. Returns the plain-text body of the first reply
found, or None when IMAP is unconfigured, unreachable, or no reply exists.

Never raises — all errors are logged at DEBUG so the caller degrades gracefully.

`scan_imap_replies(user_id)` is called from the daemon reconcile loop to
proactively advance EMAIL_SENT/EMAIL_OPENED deals to EMAIL_REPLIED without
waiting for the next follow-up task to fire.
"""

from __future__ import annotations

import email as email_lib
import imaplib
import logging
from datetime import datetime, timezone
from email import policy, utils as email_utils

logger = logging.getLogger(__name__)


def find_reply(mailbox, original_message_id: str) -> tuple[str, datetime] | None:
    """Return (text, received_at) of first reply to *original_message_id*, or None.

    Searches the mailbox INBOX for messages whose In-Reply-To header matches
    the given message ID. Returns None when IMAP is not configured on the
    mailbox, when the connection fails, or when no matching reply exists.
    received_at is the email's Date header parsed to UTC; falls back to now().
    """
    if not mailbox.imap_host or not original_message_id:
        return None

    imap_port = mailbox.imap_port or 993

    try:
        with imaplib.IMAP4_SSL(mailbox.imap_host, imap_port) as imap:
            imap.login(mailbox.username, mailbox.password)
            imap.select("INBOX", readonly=True)
            return _search_inbox(imap, original_message_id)

    except Exception as exc:
        logger.debug(
            "imap_checker: could not check replies for %s: %s",
            original_message_id, exc,
        )

    return None


def _fetch_text(imap: imaplib.IMAP4_SSL, uid: bytes) -> tuple[str, datetime]:
    """Fetch the RFC822 body of *uid*; return (text, received_at).

    received_at is parsed from the email's Date header (UTC).
    Falls back to now() when the header is absent or unparseable.
    """
    fallback_dt = datetime.now(timezone.utc)
    try:
        status, msg_data = imap.fetch(uid.decode(), "(RFC822)")
        if status != "OK" or not msg_data or not msg_data[0]:
            return "replied", fallback_dt
        raw = msg_data[0][1]
        if not isinstance(raw, bytes):
            return "replied", fallback_dt
        msg = email_lib.message_from_bytes(raw, policy=policy.default)
        received_at = _parse_date_header(msg) or fallback_dt
        text = _extract_plain(msg)
        return (text or "replied"), received_at
    except Exception:
        return "replied", fallback_dt


def _parse_date_header(msg) -> datetime | None:
    """Parse the Date header into a UTC-aware datetime, or return None."""
    date_str = msg.get("Date", "")
    if not date_str:
        return None
    try:
        ts = email_utils.parsedate_to_datetime(date_str)
        return ts.astimezone(timezone.utc)
    except Exception:
        return None


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


def scan_imap_replies(user_id: str) -> int:
    """Proactively scan IMAP inboxes for replies to outstanding email deals.

    Called from the daemon reconcile loop so operators see EMAIL_REPLIED as
    soon as the next idle cycle fires — not only when the follow-up task runs.

    Returns the number of deals advanced to EMAIL_REPLIED.
    """
    from openoutreach.mongodb.connection import get_mongodb_collection
    from openoutreach.emails.models import Mailbox

    deals_col = get_mongodb_collection("deals")
    if deals_col is None:
        return 0

    # Fetch all EMAIL_SENT/EMAIL_OPENED deals for this user that have a
    # message ID and a mailbox we can check.
    cursor = deals_col.find(
        {
            "user_id": user_id,
            "state": {"$in": ["email_sent", "email_opened"]},
            "email_message_id": {"$exists": True, "$nin": [None, ""]},
            "mailbox_id": {"$exists": True, "$nin": [None, ""]},
        },
        {"_id": 1, "mailbox_id": 1, "email_message_id": 1, "lead_id": 1},
    )

    replied_count = 0
    # Group by mailbox to open each IMAP connection only once.
    mailbox_deal_map: dict[str, list[dict]] = {}
    for doc in cursor:
        mid = doc.get("mailbox_id", "")
        mailbox_deal_map.setdefault(mid, []).append(doc)

    for mailbox_id, deal_docs in mailbox_deal_map.items():
        mailbox = Mailbox.get(mailbox_id)
        if mailbox is None or not mailbox.imap_host:
            continue
        if mailbox.user_id != user_id:
            # Defensive: skip if mailbox ownership doesn't match (data integrity guard).
            continue

        imap_port = mailbox.imap_port or 993
        try:
            with imaplib.IMAP4_SSL(mailbox.imap_host, imap_port) as imap:
                imap.login(mailbox.username, mailbox.password)
                imap.select("INBOX", readonly=True)

                for deal_doc in deal_docs:
                    original_msg_id = deal_doc.get("email_message_id", "")
                    if not original_msg_id:
                        continue

                    result = _search_inbox(imap, original_msg_id)
                    if result is None:
                        continue

                    reply_text, received_at = result
                    deals_col.update_one(
                        {"_id": deal_doc["_id"]},
                        {"$set": {"state": "email_replied"}},
                    )
                    # Write reply as inbound ChatMessage with actual email timestamp.
                    try:
                        from openoutreach.mongodb.models_extended import ChatMessage
                        msg = ChatMessage(
                            deal_id=str(deal_doc["_id"]),
                            content=reply_text,
                            is_outgoing=False,
                            channel="email",
                            user_id=user_id,
                            creation_date=received_at,
                        )
                        msg.save()
                    except Exception as exc:
                        logger.debug("scan_imap_replies: ChatMessage write failed for deal %s: %s", deal_doc["_id"], exc)

                    replied_count += 1
                    logger.info(
                        "scan_imap_replies: EMAIL_REPLIED for deal %s (mailbox %s)",
                        deal_doc["_id"], mailbox.from_address,
                    )

        except Exception as exc:
            logger.debug(
                "scan_imap_replies: IMAP error for mailbox %s: %s",
                mailbox_id, exc,
            )

    return replied_count


def _search_inbox(imap: imaplib.IMAP4_SSL, original_message_id: str) -> tuple[str, datetime] | None:
    """Return (reply_text, received_at) for *original_message_id* using an already-open IMAP connection.

    Searches In-Reply-To then References with/without angle brackets.
    Returns None when no reply is found.
    """
    clean_id = original_message_id.strip("<>")
    search_variants = [
        ("In-Reply-To", f"<{clean_id}>"),
        ("In-Reply-To", clean_id),
        ("References", f"<{clean_id}>"),
        ("References", clean_id),
    ]
    seen_uids: set[bytes] = set()
    for header, candidate in search_variants:
        try:
            status, data = imap.search(None, "HEADER", header, candidate)
        except Exception:
            continue
        if status != "OK":
            continue
        uids = (data[0] or b"").split()
        for uid in uids:
            if uid not in seen_uids:
                seen_uids.add(uid)
                return _fetch_text(imap, uid)
    return None
