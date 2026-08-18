"""QR capture and auth detection for WhatsApp Web."""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_QR_PARENT_SELECTOR = "[data-testid='qrcode']"
_APP_READY_SELECTOR = "[data-testid='conversation-panel-wrapper'], [aria-label='Chat list']"


def is_authenticated(page) -> bool:
    """Return True if WA Web shows the main app UI (not QR/landing screen)."""
    try:
        page.wait_for_selector(_APP_READY_SELECTOR, timeout=3000)
        return True
    except Exception:
        pass
    try:
        result = page.evaluate(
            "() => !!document.querySelector('[data-testid=\"conversation-panel-wrapper\"]')"
            " || !!document.querySelector('[aria-label=\"Chat list\"]')"
        )
        return bool(result)
    except Exception:
        return False


def capture_qr_png(page) -> Optional[bytes]:
    """Capture the QR code element as PNG bytes. Returns None if not visible."""
    try:
        page.wait_for_selector(_QR_PARENT_SELECTOR, timeout=5000)
        element = page.query_selector(_QR_PARENT_SELECTOR)
        if element:
            return element.screenshot(type="png")
    except Exception:
        pass
    # Fallback: screenshot the canvas
    try:
        canvas = page.query_selector("canvas")
        if canvas:
            return canvas.screenshot(type="png")
    except Exception:
        pass
    logger.debug("No QR element found on page")
    return None


def extract_phone_and_name(page) -> tuple[Optional[str], Optional[str]]:
    """Extract phone number and display name from authenticated WA Web."""
    phone: Optional[str] = None
    name: Optional[str] = None
    try:
        result = page.evaluate("""() => {
            try {
                const store = window.Store;
                if (store && store.Me && store.Me.get) {
                    const me = store.Me.get();
                    if (me) {
                        return {
                            phone: me.id ? me.id._serialized : null,
                            name: me.pushname || me.name || null
                        };
                    }
                }
            } catch(e) {}
            const nameEl = document.querySelector('[data-testid="profile-details-name"]');
            return { phone: null, name: nameEl ? nameEl.textContent : null };
        }""")
        if isinstance(result, dict):
            raw_phone = result.get("phone")
            if raw_phone and "@" in str(raw_phone):
                phone = "+" + str(raw_phone).split("@")[0]
            name = result.get("name")
    except Exception as e:
        logger.debug("Could not extract phone/name: %s", e)
    return phone, name
