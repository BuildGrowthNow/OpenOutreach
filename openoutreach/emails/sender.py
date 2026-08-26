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
from email.utils import make_msgid

SMTP_TIMEOUT_SECONDS = 30

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
    message["From"] = mailbox.from_address
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
    message["From"] = mailbox.from_address
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
    escaped = html.escape(body)

    def _rewrite(m: re.Match) -> str:
        orig = m.group(0)
        tracking = click_redirect_url_fn(deal_id, orig, campaign_id)
        return f'<a href="{html.escape(tracking)}">{html.escape(orig)}</a>'

    linked = _URL_RE.sub(_rewrite, escaped)
    pixel = open_pixel_url_fn(deal_id, campaign_id)
    return (
        f'<html><body><pre style="font-family:inherit;white-space:pre-wrap">'
        f"{linked}"
        f"</pre>"
        f'<img src="{html.escape(pixel)}" width="1" height="1" style="display:none" alt="" />'
        f"</body></html>"
    )


# ── Message-ID ────────────────────────────────────────────────────


def _mint_message_id(from_address: str) -> str:
    domain = from_address.rsplit("@", 1)[-1]
    return make_msgid(domain=domain)


# ── Transport ─────────────────────────────────────────────────────


def _deliver(mailbox, message) -> None:
    with smtplib.SMTP(mailbox.host, mailbox.port, timeout=SMTP_TIMEOUT_SECONDS) as smtp:
        smtp.starttls()
        smtp.login(mailbox.username, mailbox.password)
        smtp.send_message(message)
