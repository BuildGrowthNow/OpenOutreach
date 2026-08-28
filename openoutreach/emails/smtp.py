# openoutreach/emails/smtp.py
"""Auth-only SMTP check, run when a mailbox is imported.

No test send - boxes are mid-warmup; we only confirm the credentials log in.
"""

from __future__ import annotations

import smtplib
import imaplib


def verify_auth(host: str, port: int, username: str, password: str) -> tuple[bool, str]:
    """Connect, log in, quit. Return ``(ok, message)``.

    Port 465 uses implicit SSL (SMTP_SSL); all other ports use STARTTLS.
    Mirrors the branch used by sender.py._deliver so import and send use
    the same transport logic.

    A Google Workspace box rejects its login password with 534/535 - the message
    surfaces the "use the app password" hint for that case.
    """
    try:
        if port == 465:
            ctx: smtplib.SMTP = smtplib.SMTP_SSL(host, port, timeout=20)
        else:
            ctx = smtplib.SMTP(host, port, timeout=20)
        with ctx as smtp:
            if port != 465:
                smtp.starttls()
            smtp.login(username, password)
        return True, "ok"
    except smtplib.SMTPAuthenticationError as e:
        hint = (
            " - paste the Google app password, not the mailbox login password"
            if e.smtp_code in (534, 535)
            else ""
        )
        return False, f"auth rejected ({e.smtp_code}){hint}"
    except (smtplib.SMTPException, OSError) as e:
        return False, f"connection failed: {e}"


def verify_imap_auth(host: str, port: int, username: str, password: str) -> tuple[bool, str]:
    """Connect and authenticate to IMAP without changing mailbox state."""
    try:
        with imaplib.IMAP4_SSL(host, port, timeout=20) as imap:
            status, _ = imap.login(username, password)
            if status != "OK":
                return False, "IMAP authentication rejected"
        return True, "ok"
    except (imaplib.IMAP4.error, OSError) as e:
        return False, f"IMAP connection/authentication failed: {e}"
