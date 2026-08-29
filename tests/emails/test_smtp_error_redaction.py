import imaplib
import smtplib

from openoutreach.emails.smtp import verify_auth, verify_imap_auth


def test_smtp_connection_error_does_not_echo_provider_exception(monkeypatch):
    class FailingSMTP:
        def __init__(self, *args, **kwargs):
            raise OSError("password=super-secret host=internal.example")

    monkeypatch.setattr(smtplib, "SMTP", FailingSMTP)
    ok, message = verify_auth("smtp.example", 587, "user@example", "super-secret")

    assert not ok
    assert message == "connection failed"
    assert "super-secret" not in message
    assert "internal.example" not in message


def test_imap_connection_error_does_not_echo_provider_exception(monkeypatch):
    class FailingIMAP:
        def __init__(self, *args, **kwargs):
            raise imaplib.IMAP4.error("AUTHENTICATIONFAILED password=super-secret")

    monkeypatch.setattr(imaplib, "IMAP4_SSL", FailingIMAP)
    ok, message = verify_imap_auth("imap.example", 993, "user@example", "super-secret")

    assert not ok
    assert message == "IMAP connection/authentication failed"
    assert "super-secret" not in message
