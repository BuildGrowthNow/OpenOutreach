"""Safe helpers for desktop tray notifications."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def truncate_notification_text(value: str) -> str:
    """Keep Windows tray notifications within pystray's 64-character limit."""
    value = str(value)
    return value if len(value) <= 64 else value[:61].rstrip() + "..."


def notify_icon(icon: Any, title: str, message: str) -> None:
    """Show a best-effort tray notification without breaking app startup."""
    if not icon:
        return
    safe_title = truncate_notification_text(title)
    safe_message = truncate_notification_text(message)
    try:
        icon.notify(safe_title, safe_message)
    except Exception:
        logger.warning("Tray notification failed; title=%r", safe_title, exc_info=True)
