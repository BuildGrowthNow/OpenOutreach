from openoutreach.desktop.email_adapter import EmailAdapter, UnsupportedEmailAction
from openoutreach.desktop.whatsapp_browser_adapter import WhatsAppBrowserAdapter


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
        "mailbox_grant": {"task_id": "task-1", "mailbox_id": "box-1"},
    }})
    assert result["outcome"] == "applied"
