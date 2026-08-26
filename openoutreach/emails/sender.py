# openoutreach/emails/sender.py
"""Send one outbound email through a Mailbox's SMTP credentials.

No error handling by design: a failed send raises and the EMAIL task is marked
FAILED by the daemon, then retried on the next cycle.

When deal_id is supplied the email gains:
- multipart/alternative with text/plain + text/html parts
- 1x1 tracking pixel in the HTML part
- Click-tracking link rewriting in the HTML part
- List-Unsubscribe / List-Unsubscribe-Post headers (Gmail/Yahoo bulk requirement)
"""

from __future__ import annotations

import html
import re
import smtplib
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, make_msgid

SMTP_TIMEOUT_SECONDS = 30

# Match URLs in the raw (un-escaped) plain-text body before html.escape mangles `&`.
_URL_RE = re.compile(r"https://[^\s\"'<>]+")


def send_email(
    mailbox,
    to_address: str,
    subject: str,
    body: str,
    *,
    in_reply_to: str | None = None,
    references: str | None = None,
    deal_id: str = "",
    campaign_id: str = "",
) -> str:
    """Send *body* from *mailbox* to *to_address*; return the Message-ID.

    When deal_id is provided the message is multipart/alternative with tracking.
    Without deal_id it falls back to the original plaintext-only path.
    """
    if deal_id:
        message = _build_tracked_message(
            mailbox, to_address, subject, body,
            in_reply_to, references, deal_id, campaign_id,
        )
    else:
        message = _build_plain_message(mailbox, to_address, subject, body, in_reply_to, references)
    _deliver(mailbox, message)
    return message["Message-ID"]


# ── Plain message (no tracking) ───────────────────────────────────


def _build_plain_message(
    mailbox, to_address, subject, body, in_reply_to, references
) -> EmailMessage:
    message = EmailMessage()
    message["Message-ID"] = _mint_message_id(mailbox.from_address)
    message["From"] = _from_header(mailbox)
    message["To"] = to_address
    message["Subject"] = subject
    if in_reply_to:
        message["In-Reply-To"] = in_reply_to
        message["References"] = references or in_reply_to
    message.set_content(body)
    return message


# ── Tracked multipart message ─────────────────────────────────────


def _build_tracked_message(
    mailbox, to_address, subject, body,
    in_reply_to, references, deal_id, campaign_id,
) -> MIMEMultipart:
    from openoutreach.emails.tracking import open_pixel_url, click_redirect_url, unsubscribe_url

    msg_id = _mint_message_id(mailbox.from_address)
    unsub_link = unsubscribe_url(deal_id, campaign_id)

    message = MIMEMultipart("alternative")
    message["Message-ID"] = msg_id
    message["From"] = _from_header(mailbox)
    message["To"] = to_address
    message["Subject"] = subject
    message["List-Unsubscribe"] = f"<{unsub_link}>"
    message["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    if in_reply_to:
        message["In-Reply-To"] = in_reply_to
        message["References"] = references or in_reply_to

    message.attach(MIMEText(body, "plain", "utf-8"))
    html_body = _build_html(body, deal_id, campaign_id, open_pixel_url, click_redirect_url)
    message.attach(MIMEText(html_body, "html", "utf-8"))

    return message


def _build_html(
    body: str,
    deal_id: str,
    campaign_id: str,
    open_pixel_url_fn,
    click_redirect_url_fn,
) -> str:
    # Rewrite URLs BEFORE html.escape so that `&` in query params is still matchable.
    # We collect (start, end, replacement) tuples, then rebuild the string with the
    # surrounding plain text escaped and the rewritten links inserted verbatim.
    segments: list[str] = []
    last = 0
    for m in _URL_RE.finditer(body):
        # Escape the plain text between the previous match and this one
        segments.append(html.escape(body[last:m.start()]))
        orig_url = m.group(0)
        tracking_url = click_redirect_url_fn(deal_id, orig_url, campaign_id)
        segments.append(
            f'<a href="{html.escape(tracking_url)}">{html.escape(orig_url)}</a>'
        )
        last = m.end()
    # Escape any trailing plain text after the last URL
    segments.append(html.escape(body[last:]))

    linked = "".join(segments)
    pixel = open_pixel_url_fn(deal_id, campaign_id)
    return (
        f'<html><body><pre style="font-family:inherit;white-space:pre-wrap">'
        f"{linked}"
        f"</pre>"
        f'<img src="{html.escape(pixel)}" width="1" height="1" style="display:none" alt="" />'
        f"</body></html>"
    )


# ── From header ───────────────────────────────────────────────────


def _from_header(mailbox) -> str:
    """Return a properly formatted From header, including display name if set."""
    name = (mailbox.from_name or "").strip()
    address = mailbox.from_address or mailbox.username
    return formataddr((name, address)) if name else address


# ── Message-ID ────────────────────────────────────────────────────


def _mint_message_id(from_address: str) -> str:
    domain = from_address.rsplit("@", 1)[-1]
    return make_msgid(domain=domain)


# ── Transport ─────────────────────────────────────────────────────


def _deliver(mailbox, message) -> None:
    # Port 465 uses implicit SSL (SMTP_SSL); all other ports use STARTTLS.
    if mailbox.port == 465:
        with smtplib.SMTP_SSL(mailbox.host, mailbox.port, timeout=SMTP_TIMEOUT_SECONDS) as smtp:
            smtp.login(mailbox.username, mailbox.password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(mailbox.host, mailbox.port, timeout=SMTP_TIMEOUT_SECONDS) as smtp:
            smtp.starttls()
            smtp.login(mailbox.username, mailbox.password)
            smtp.send_message(message)
