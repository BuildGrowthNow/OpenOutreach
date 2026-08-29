"""WASession - thin Playwright wrapper for a WhatsApp Web session."""
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
            logger.warning("Chat panel did not load")
            return False

        try:
            send_btn = self.page.wait_for_selector(_SEND_BTN_SELECTOR, timeout=8000)
            if send_btn:
                send_btn.click()
                logger.info("WA message sent")
                return True
        except Exception as e:
            logger.warning("Send button not found for %s: %s", phone, type(e).__name__)

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
            logger.warning("check_inbox failed: %s", type(e).__name__)
            return []

    def sync(self, cursor: str = "", limit: int = 100) -> list[dict[str, str]]:
        """Return a bounded inbox snapshot for the API receipt path.

        WhatsApp Web does not expose a stable public message API. The local
        browser adapter therefore uses the currently rendered inbox metadata
        as the safe sync surface; full durable reconciliation remains server
        owned and is keyed by the returned bounded observation batch.
        """
        del cursor
        bounded = max(1, min(int(limit), 100))
        rows = self.check_inbox()[:bounded]
        return [
            {str(key): str(value or "")[:2000] for key, value in row.items()
             if str(key) in {"name", "last_message", "timestamp"}}
            for row in rows if isinstance(row, dict)
        ]

    def is_alive(self) -> bool:
        """Return True if the WA Web session is still authenticated.

        Must be called from the Playwright thread.
        """
        if not self.page:
            return False
        from openoutreach.whatsapp.browser.qr import is_authenticated
        try:
            return is_authenticated(self.page)
        except Exception:
            return False

    def is_registered(self, phone: str) -> bool:
        """Return True if the phone number has a WhatsApp account.

        Navigates to the WA Web send URL and waits for either the chat panel
        (registered) or the "not on WhatsApp" popup (unregistered). Returns
        True on any timeout or unexpected DOM state to avoid false negatives —
        the send handler will then attempt the send and handle the failure.
        """
        if not self.page:
            raise RuntimeError("WASession not started")

        url = _SEND_URL.format(phone=phone.lstrip("+"), text="")
        self.page.goto(url)
        try:
            self.page.wait_for_selector(
                f"{_CHAT_LOAD_SELECTOR}, [data-testid='popup-contents']",
                timeout=12000,
            )
        except Exception:
            # Can't determine - assume registered to avoid losing real leads
            logger.warning("is_registered: timed out - assuming registered")
            return True

        try:
            result = self.page.evaluate("""() => {
                const popup = document.querySelector('[data-testid="popup-contents"]');
                if (!popup) return false;
                const text = (popup.innerText || '').toLowerCase();
                return text.includes('not on whatsapp')
                    || text.includes('phone number shared via url is invalid')
                    || text.includes('invalid phone number');
            }""")
            if result:
                logger.info("is_registered: number is NOT on WhatsApp")
                return False
        except Exception as e:
            logger.warning("is_registered: evaluation failed: %s - assuming registered", type(e).__name__)

        return True

    def detect_ban(self) -> bool:
        """Return True if WA Web shows a ban / account-suspended message.

        Must be called from the Playwright thread.
        """
        if not self.page:
            return False
        try:
            result = self.page.evaluate("""() => {
                const text = document.body ? document.body.innerText : '';
                return text.includes('not allowed to use WhatsApp')
                    || text.includes('account has been suspended');
            }""")
            return bool(result)
        except Exception:
            return False

    def close(self, mark_disconnected: bool = True) -> None:
        """Close browser and clean up.

        ``mark_disconnected`` is false for an intentional daemon shutdown: the
        persisted session remains authenticated and can be resumed on restart.
        QR expiry, crashes, and health-check recovery use the default true.
        Safe to call from the Playwright thread.
        """
        from openoutreach.whatsapp.browser.launch import close_whatsapp_session
        close_whatsapp_session(self, mark_disconnected=mark_disconnected)
