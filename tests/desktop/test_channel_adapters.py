from datetime import datetime, timedelta, timezone

from openoutreach.desktop.email_adapter import EmailAdapter, RemoteMailboxProvider, UnsupportedEmailAction
from openoutreach.desktop.whatsapp_browser_adapter import WhatsAppBrowserAdapter
from openoutreach.desktop.whatsapp_session import LocalWhatsAppSession


class FakeWhatsApp:
    def send_message(self, phone, message):
        assert (phone, message) == ("+15551212", "hello")
        return True

    def sync(self, *, cursor, limit):
        assert (cursor, limit) == ("c1", 100)
        return [{"id": "m1"}]

    def detect_ban(self):
        return False

    def is_alive(self):
        return True

    def reconnect(self):
        return True


class FakeMail:
    def send(self, grant, recipient, subject, body, effect_key):
        assert grant["task_id"] == "task-1"
        return True

    def scan_replies(self, grant, cursor):
        return [{"id": "r1", "cursor": cursor}]


def test_whatsapp_adapter_returns_bounded_receipts_and_synces():
    adapter = WhatsAppBrowserAdapter("wa-1", FakeWhatsApp())
    result = adapter.execute({"task_type": "whatsapp_message", "snapshot": {
        "profile_id": "wa-1", "target_phone": "+15551212", "message": "hello",
        "effect_key": "effect-1",
    }})
    assert result["outcome"] == "applied"
    assert result["effect_key"] == "effect-1"
    sync = adapter.execute({"task_type": "whatsapp_sync", "snapshot": {
        "profile_id": "wa-1", "cursor": "c1",
    }})
    assert sync["messages"] == [{"id": "m1"}]
    assert adapter.observe_session()["state"] == "connected"


def test_whatsapp_adapter_accepts_provider_cursor_and_reconnects():
    class CursorSession(FakeWhatsApp):
        def sync(self, *, cursor, limit):
            return {"cursor": "c2", "messages": [{"id": "m1"}, {"id": "m1"}]}

    adapter = WhatsAppBrowserAdapter("wa-1", CursorSession())
    sync = adapter.execute({"task_type": "whatsapp_sync", "snapshot": {
        "profile_id": "wa-1", "cursor": "c1",
    }})
    assert sync["cursor"] == "c2"
    assert sync["messages"] == [{"id": "m1"}]
    reconnect = adapter.execute({"task_type": "whatsapp_reconnect", "snapshot": {
        "profile_id": "wa-1",
    }})
    assert reconnect["outcome"] == "applied"


def test_local_whatsapp_session_is_desktop_only():
    from pathlib import Path
    source = Path(__file__).parents[2] / "openoutreach" / "desktop" / "whatsapp_session.py"
    text = source.read_text(encoding="utf-8")
    assert "openoutreach.mongodb" not in text
    assert "openoutreach.whatsapp.models" not in text
    assert LocalWhatsAppSession("wa-1").state() == "disconnected"


def test_email_adapter_requires_task_bound_grant():
    adapter = EmailAdapter(FakeMail())
    task = {"task_type": "email_send", "snapshot": {
        "recipient": "person@example.com", "subject": "Hi", "body": "Hello",
    }}
    try:
        adapter.execute(task)
    except UnsupportedEmailAction:
        pass
    else:
        raise AssertionError("email adapter accepted an unbound mailbox")


def test_email_adapter_sends_only_with_grant():
    result = EmailAdapter(FakeMail()).execute({"task_type": "email_send", "snapshot": {
        "recipient": "person@example.com", "subject": "Hi", "body": "Hello",
        "mailbox_grant": {"task_id": "task-1", "mailbox_id": "box-1",
                           "purpose": "send",
                           "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat()},
    }})
    assert result["outcome"] == "applied"


def test_email_adapter_returns_typed_failure_receipt():
    class FailingMail(FakeMail):
        def send(self, *args):
            raise TimeoutError("provider timeout")

    result = EmailAdapter(FailingMail()).execute({"task_id": "task-1", "task_type": "email_send", "snapshot": {
        "recipient": "person@example.com", "subject": "Hi", "body": "Hello",
        "effect_key": "effect-1",
        "mailbox_grant": {"task_id": "task-1", "mailbox_id": "box-1",
                           "purpose": "send",
                           "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat()},
    }})
    assert result["outcome"] == "timeout"
    assert result["receipt"]["outcome"] == "failed"


def test_remote_mailbox_provider_forwards_task_lease_without_credentials():
    calls = []

    def submit(task, operation, grant, recipient, subject, body, effect_key, cursor=""):
        calls.append((task, operation, grant, recipient, subject, body, effect_key, cursor))
        return {"status": "sent"}

    provider = RemoteMailboxProvider(submit)
    task = {"task_id": "task-1", "lease_id": "lease-1", "task_type": "email_send"}
    adapter = EmailAdapter(provider)
    adapter.execute({**task, "snapshot": {
        "recipient": "person@example.com", "subject": "Hi", "body": "Hello",
        "effect_key": "effect-1",
        "mailbox_grant": {"task_id": "task-1", "mailbox_id": "box-1",
                           "purpose": "send",
                           "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat()},
    }})
    assert calls[0][0]["task_id"] == task["task_id"]
    assert calls[0][0]["lease_id"] == task["lease_id"]
    assert calls[0][1] == "send"
    assert "password" not in repr(calls[0][2]).lower()


def test_email_reply_scan_returns_typed_receipt_and_cursor():
    result = EmailAdapter(FakeMail()).execute({"task_id": "task-1", "task_type": "email_reply_scan", "snapshot": {
        "cursor": "c1",
        "effect_key": "effect-scan-1",
        "mailbox_grant": {"task_id": "task-1", "mailbox_id": "box-1",
                           "purpose": "reply_scan",
                           "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat()},
    }})
    assert result["outcome"] == "observed"
    assert result["effect_key"] == "effect-scan-1"
    assert result["receipt"]["outcome"] == "replied"
