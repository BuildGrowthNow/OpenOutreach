"""Local-only WhatsApp Web session used by the untrusted desktop.

This module intentionally has no imports from MongoDB, the API server, or
provider credential models.  WhatsApp authentication remains human-driven in
the local browser; only bounded observations and action results cross the
daemon gateway.
"""

from __future__ import annotations

import time
import urllib.parse
from pathlib import Path
from typing import Any

_WA_URL = "https://web.whatsapp.com/"
_CHAT_READY = "[data-testid='conversation-panel-wrapper'], [aria-label='Chat list']"
_CHAT_PANEL = "[data-testid='conversation-panel-wrapper']"
_SEND_BUTTON = "[data-testid='send'], [data-testid='compose-btn-send']"
_QR_SELECTOR = "[data-testid='qrcode'], canvas"
_MESSAGE_EXTRACT_JS = """() => Array.from(document.querySelectorAll(
    '[data-testid="msg-container"], .message-in, .message-out'
)).map(el => {
    const body = el.querySelector('[data-testid="msg-text"], .copyable-text, span.selectable-text');
    const dbl = el.querySelector('[data-testid="msg-dblcheck"]');
    const out = el.classList.contains('message-out') || !!el.querySelector('[data-testid="msg-check"], [data-testid="msg-dblcheck"]');
    const label = dbl?.getAttribute('aria-label')?.toLowerCase() || '';
    return {content: body?.innerText || '', is_outgoing: out,
            delivery_status: out ? (label.includes('read') ? 'read' : dbl ? 'delivered' : 'sent') : '',
            ts_text: el.querySelector('[data-testid="msg-meta"]')?.getAttribute('data-pre-plain-text') || ''};
}).filter(item => item.content)"""


class LocalWhatsAppSession:
    """Bounded Playwright wrapper with browser-profile-local session state."""

    def __init__(self, profile_id: str, profile_dir: Path | None = None) -> None:
        if not profile_id or len(profile_id) > 128:
            raise ValueError("invalid WhatsApp profile id")
        self.profile_id = profile_id
        self.profile_dir = profile_dir or (Path.home() / ".lengrowth" / "whatsapp_profiles" / profile_id)
        self.page: Any = None
        self.context: Any = None
        self.playwright: Any = None

    def start(self, *, qr_timeout_seconds: int = 120) -> str:
        """Open WhatsApp Web and wait for human QR authentication if needed."""
        if self.page is not None:
            return self.state()
        if not 1 <= qr_timeout_seconds <= 300:
            raise ValueError("QR timeout must be between 1 and 300 seconds")
        from playwright.sync_api import sync_playwright

        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.playwright = sync_playwright().start()
        try:
            self.context = self.playwright.chromium.launch_persistent_context(
                str(self.profile_dir), headless=False,
            )
            self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
            self.page.goto(_WA_URL, wait_until="domcontentloaded")
            if self.is_alive():
                return "connected"
            deadline = time.monotonic() + qr_timeout_seconds
            while time.monotonic() < deadline:
                if self.detect_ban():
                    return "banned"
                if self.is_alive():
                    return "connected"
                # QR bytes never leave this process; the visible local browser
                # is the only supported human authentication surface.
                time.sleep(1)
            return "qr"
        except Exception:
            self.close()
            raise

    def reconnect(self) -> bool:
        """Perform one bounded reconnect attempt using the local profile."""
        self.close()
        return self.start(qr_timeout_seconds=30) == "connected"

    def state(self) -> str:
        if self.detect_ban():
            return "banned"
        if self.is_alive():
            return "connected"
        if self.page is not None and self._has_qr():
            return "qr"
        return "disconnected"

    def send_message(self, phone: str, message: str) -> str:
        if not self.page:
            raise RuntimeError("WhatsApp session is not started")
        if not phone or not message:
            raise ValueError("phone and message are required")
        if not self.is_alive():
            return "logged_out"
        query = urllib.parse.urlencode({"phone": phone.lstrip("+"), "text": message})
        self.page.goto(f"{_WA_URL}send?{query}", wait_until="domcontentloaded")
        try:
            self.page.wait_for_selector(_CHAT_PANEL, timeout=15_000)
            button = self.page.wait_for_selector(_SEND_BUTTON, timeout=8_000)
            if not button:
                return "rejected"
            button.click()
            return "sent"
        except Exception as exc:
            name = type(exc).__name__.lower()
            if "timeout" in name:
                return "timeout"
            raise

    def sync(self, *, cursor: str = "", limit: int = 100, phone: str = "") -> dict[str, Any]:
        del cursor
        if not self.page:
            raise RuntimeError("WhatsApp session is not started")
        bounded = max(1, min(int(limit), 100))
        if phone:
            query = urllib.parse.urlencode({"phone": phone.lstrip("+")})
            self.page.goto(f"{_WA_URL}send?{query}", wait_until="domcontentloaded")
            self.page.wait_for_selector(_CHAT_PANEL, timeout=15_000)
            rows = self.page.evaluate(_MESSAGE_EXTRACT_JS)
        else:
            rows = self.page.evaluate("""(limit) => Array.from(
                document.querySelectorAll('[data-testid="cell-frame-container"]')
            ).slice(0, limit).map(row => ({
                name: row.querySelector('[data-testid="cell-frame-title"]')?.textContent || '',
                last_message: row.querySelector('[data-testid="last-msg"]')?.textContent || '',
                timestamp: row.querySelector('[data-testid="cell-frame-secondary"]')?.textContent || ''
            }))""", bounded)
        messages = []
        for row in rows if isinstance(rows, list) else []:
            if isinstance(row, dict):
                messages.append({str(k)[:64]: str(v)[:2000] for k, v in row.items()})
        return {"cursor": "", "messages": messages[:100]}

    def is_alive(self) -> bool:
        if not self.page:
            return False
        try:
            self.page.wait_for_selector(_CHAT_READY, timeout=1_000)
            return True
        except Exception:
            return False

    def detect_ban(self) -> bool:
        if not self.page:
            return False
        try:
            return bool(self.page.evaluate("""() => {
                const text = document.body?.innerText?.toLowerCase() || '';
                return text.includes('not allowed to use whatsapp')
                    || text.includes('account has been suspended');
            }"""))
        except Exception:
            return False

    def _has_qr(self) -> bool:
        try:
            return self.page.query_selector(_QR_SELECTOR) is not None
        except Exception:
            return False

    def close(self) -> None:
        for resource in (self.context, self.playwright):
            try:
                if resource is not None:
                    resource.close() if resource is self.context else resource.stop()
            except Exception:
                pass
        self.page = None
        self.context = None
        self.playwright = None
