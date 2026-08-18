"""WASession — thin Playwright wrapper for a WhatsApp Web session."""
from __future__ import annotations

import logging
import urllib.parse
from typing import Any, Optional

from openoutreach.whatsapp.models.profile import WhatsAppProfile

logger = logging.getLogger(__name__)

_SEND_URL = "https://web.whatsapp.com/send?phone={phone}&text={text}"
_SEND_BTN_SELECTOR = "[data-testid='send'], [data-testid='compose-btn-send']"
_CHAT_LOAD_SELECTOR = "[data-testid='conversation-panel-wrapper']"


class WASession:
    """Holds Playwright objects for one WhatsApp Web session.

    All methods that touch self.page must be called from the Playwright thread.
    """

    def __init__(self, wa_profile: WhatsAppProfile):
        self.wa_profile = wa_profile
        self.page: Optional[Any] = None
        self.context: Optional[Any] = None
        self.browser: Optional[Any] = None
        self.playwright: Optional[Any] = None

    def __str__(self) -> str:
        return f"WASession({self.wa_profile})"

    def send_message(self, phone: str, text: str) -> bool:
        """Navigate to WA Web send URL and click the send button.

        Returns True on apparent success. Raises on unexpected Playwright errors.
        """
        if not self.page:
            raise RuntimeError("WASession not started")

        encoded_text = urllib.parse.quote(text)
        url = _SEND_URL.format(phone=phone.lstrip("+"), text=encoded_text)
        self.page.goto(url)
        try:
            self.page.wait_for_selector(_CHAT_LOAD_SELECTOR, timeout=15000)
        except Exception:
            logger.warning("Chat panel did not load for %s", phone)
            return False

        try:
            send_btn = self.page.wait_for_selector(_SEND_BTN_SELECTOR, timeout=8000)
            if send_btn:
                send_btn.click()
                logger.info("WA message sent to %s", phone)
                return True
        except Exception as e:
            logger.warning("Send button not found for %s: %s", phone, e)

        return False

    def check_inbox(self) -> list[dict]:
        """Return list of recent conversation metadata from WA Web sidebar.

        Each entry: {name, last_message, timestamp}
        Full message sync handled in whatsapp/tasks/sync.py.
        """
        if not self.page:
            raise RuntimeError("WASession not started")

        try:
            result = self.page.evaluate("""() => {
                const rows = Array.from(
                    document.querySelectorAll('[data-testid="cell-frame-container"]')
                );
                return rows.slice(0, 50).map(row => {
                    const title = row.querySelector('[data-testid="cell-frame-title"]');
                    const lastMsg = row.querySelector('[data-testid="last-msg"]');
                    const ts = row.querySelector('[data-testid="cell-frame-secondary"]');
                    return {
                        name: title ? title.textContent : null,
                        last_message: lastMsg ? lastMsg.textContent : null,
                        timestamp: ts ? ts.textContent : null
                    };
                });
            }""")
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.warning("check_inbox failed: %s", e)
            return []

    def close(self) -> None:
        """Close browser and clean up. Safe to call from Playwright thread."""
        from openoutreach.whatsapp.browser.launch import close_whatsapp_session
        close_whatsapp_session(self)
