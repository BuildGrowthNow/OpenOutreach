from unittest.mock import Mock
from openoutreach.desktop.notifications import notify_icon, truncate_notification_text


def test_notification_text_is_capped_for_windows_pystray() -> None:
    text = truncate_notification_text("x" * 80)

    assert len(text) == 64
    assert text.endswith("...")


def test_notify_truncates_and_does_not_propagate_tray_errors() -> None:
    icon = Mock()
    icon.notify.side_effect = ValueError("notification failed")

    notify_icon(icon, "title", "message " + "x" * 100)

    title, message = icon.notify.call_args.args
    assert len(title) <= 64
    assert len(message) <= 64
