"""Launch and manage a WhatsApp Web Playwright browser session."""
from __future__ import annotations

import base64
import logging
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from openoutreach.whatsapp.browser.qr import capture_qr_png, extract_phone_and_name, is_authenticated
from openoutreach.whatsapp.models.profile import STATUS_CONNECTED, STATUS_DISCONNECTED, WhatsAppProfile

if TYPE_CHECKING:
    from openoutreach.whatsapp.browser.session import WASession

logger = logging.getLogger(__name__)

_WA_URL = "https://web.whatsapp.com/"
_QR_POLL_INTERVAL_S = 2
_QR_TIMEOUT_S = 120


def _save_session(wa_session: "WASession") -> None:
    """Persist Playwright storage state to WhatsAppProfile.session_data."""
    if not wa_session.context:
        return
    state = wa_session.context.storage_state()
    wa_session.wa_profile.session_data = state
    wa_session.wa_profile.save(update_fields=["session_data_encrypted"])
    logger.debug("WA session saved for %s", wa_session.wa_profile)


def _write_qr_to_db(profile: WhatsAppProfile, png_bytes: bytes) -> None:
    """Store QR PNG as base64 in profile so the API endpoint can serve it."""
    profile.qr_png_b64 = base64.b64encode(png_bytes).decode()
    profile.qr_generated_at = datetime.now(timezone.utc)
    profile.save(update_fields=["qr_png_b64", "qr_generated_at"])


def _clear_qr_from_db(profile: WhatsAppProfile) -> None:
    profile.qr_png_b64 = None
    profile.qr_generated_at = None
    profile.save(update_fields=["qr_png_b64", "qr_generated_at"])


def start_whatsapp_session(wa_session: "WASession") -> None:
    """Launch Chromium, load stored session, authenticate via QR if needed.

    Runs on the Playwright thread - all sync Playwright calls are safe here.
    Updates wa_session.page / context / browser / playwright in-place.
    """
    from playwright.sync_api import sync_playwright

    profile = wa_session.wa_profile
    pw = sync_playwright().start()
    wa_session.playwright = pw

    # Prefer the user's installed Chrome/Edge so the frozen desktop exe doesn't
    # need Playwright's bundled chromium_headless_shell (not included in the build).
    try:
        from openoutreach.core.browser_detect import get_preferred_browser
        _detected = get_preferred_browser()
        _channel = _detected.channel if _detected else None
    except Exception:
        _channel = None

    if _channel:
        browser = pw.chromium.launch(channel=_channel, headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
    else:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
    wa_session.browser = browser

    stored: Any = profile.session_data
    context = browser.new_context(storage_state=stored if stored else None)
    wa_session.context = context

    page = context.new_page()
    wa_session.page = page

    page.goto(_WA_URL)
    page.wait_for_load_state("domcontentloaded")

    if is_authenticated(page):
        logger.info("WA session loaded from storage for %s", profile)
        _post_auth_update(wa_session)
        return

    logger.info("WA not authenticated, waiting for QR scan for %s", profile)
    deadline = time.monotonic() + _QR_TIMEOUT_S
    last_qr_bytes: bytes | None = None

    try:
        while time.monotonic() < deadline:
            if is_authenticated(page):
                break

            png = capture_qr_png(page)
            if png and png != last_qr_bytes:
                _write_qr_to_db(profile, png)
                last_qr_bytes = png
                logger.info("QR code written to DB for %s - ready to scan", profile)

            time.sleep(_QR_POLL_INTERVAL_S)
        else:
            logger.warning("QR scan timed out for %s", profile)
            _clear_qr_from_db(profile)
            # pw.stop() was never called on this path — close everything now so the
            # next reconnect attempt starts with a clean Playwright context (leaving
            # it open keeps the internal event loop "running" and causes
            # "Playwright Sync API inside asyncio loop" on the second call).
            close_whatsapp_session(wa_session)
            return
    except Exception:
        _clear_qr_from_db(profile)
        close_whatsapp_session(wa_session)
        raise

    _clear_qr_from_db(profile)
    _save_session(wa_session)
    _post_auth_update(wa_session)
    logger.info("WA authenticated for %s", profile)


def _post_auth_update(wa_session: "WASession") -> None:
    """Extract phone/name and mark profile connected after successful auth."""
    profile = wa_session.wa_profile
    try:
        phone, name = extract_phone_and_name(wa_session.page)
        update_fields = ["status", "last_seen"]
        if phone and not profile.phone_number:
            profile.phone_number = phone
            update_fields.append("phone_number")
        if name and not profile.display_name:
            profile.display_name = name
            update_fields.append("display_name")
        profile.status = STATUS_CONNECTED
        profile.last_seen = datetime.now(timezone.utc)
        profile.save(update_fields=update_fields)
    except Exception as e:
        logger.warning("Could not update WA profile after auth: %s", type(e).__name__)


def close_whatsapp_session(wa_session: "WASession", mark_disconnected: bool = True) -> None:
    """Close browser and optionally mark profile disconnected.

    An intentional daemon stop preserves ``connected`` because the encrypted
    storage state is still valid. Unexpected expiry/error paths keep the default
    and surface ``disconnected`` to the user.
    """
    try:
        if wa_session.context:
            _save_session(wa_session)
    except Exception as e:
        logger.debug("Could not save session on close: %s", type(e).__name__)
    try:
        if wa_session.browser:
            wa_session.browser.close()
    except Exception as e:
        logger.debug("Browser close error: %s", type(e).__name__)
    try:
        if wa_session.playwright:
            wa_session.playwright.stop()
    except Exception as e:
        logger.debug("Playwright stop error: %s", type(e).__name__)

    wa_session.page = None
    wa_session.context = None
    wa_session.browser = None
    wa_session.playwright = None

    if mark_disconnected:
        try:
            wa_session.wa_profile.status = STATUS_DISCONNECTED
            wa_session.wa_profile.save(update_fields=["status"])
        except Exception as e:
            logger.debug("Profile status update error: %s", type(e).__name__)
