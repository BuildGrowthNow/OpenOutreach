# openoutreach/linkedin/browser/launch.py
"""Persist + orchestrate the daemon's LinkedIn browser session.

Cookie persistence (to the Django DB) and the launch/login orchestration are
OpenOutreach concerns, so they live here. The reusable *mechanics* — launching a
stealthed browser, driving the login form, clearing checkpoints — stay in the
Django-free ``linkedin_cli.browser`` library and are called from here.
"""

from __future__ import annotations

import logging
from typing import Any

from linkedin_cli.auth import authenticate
from linkedin_cli.browser.login import dismiss_comply_gate, launch_browser
from linkedin_cli.browser.nav import goto_page
from termcolor import colored

logger = logging.getLogger(__name__)

LINKEDIN_FEED_URL = "https://www.linkedin.com/feed/"


def _mark_credential_verified(session) -> None:
    """Update the linked credential after successful browser session start."""
    try:
        from datetime import datetime, timezone
        from openoutreach.mongodb.connection import get_mongodb_collection

        profile = session.linkedin_profile
        if not profile or not hasattr(profile, '_id'):
            return

        # Find credential by profile ID
        cred_collection = get_mongodb_collection("linkedin_credentials")
        if cred_collection is None:
            return

        cred_doc = cred_collection.find_one({"linkedin_profile_id": profile._id})
        if cred_doc is None:
            return

        # Update credential verification status
        now = datetime.now(timezone.utc)
        update_fields: dict[str, Any] = {
            "last_verified": now,
            "updated_at": now
        }

        if cred_doc.get("status") != "active":
            update_fields["status"] = "active"

        cred_collection.update_one(
            {"_id": cred_doc["_id"]},
            {"$set": update_fields}
        )

        # Create audit log entry
        try:
            log_collection = get_mongodb_collection("linkedin_credential_logs")
            if log_collection is not None:
                log_collection.insert_one({
                    "credentials_id": str(cred_doc["_id"]),
                    "action": "verified",
                    "details": {"verified_by": "daemon", "method": "cookie_session"},
                    "created_at": now
                })
        except Exception:
            pass
    except Exception:
        pass


def _save_cookies(session: Any) -> None:
    """Persist Playwright storage state (cookies) to the DB.

    Called after initial login and after each successful task to keep
    the session warm and reduce re-authentication frequency.
    """
    if not session.context:
        logger.debug("No browser context to save cookies from")
        return
    state = session.context.storage_state()
    session.linkedin_profile.cookie_data = state
    session.linkedin_profile.save(update_fields=["cookie_data_encrypted"])


def start_browser_session(session: Any) -> None:
    logger.debug("Configuring browser for %s", session)

    session.linkedin_profile.refresh_from_db(
        fields=["cookie_data_encrypted", "proxy_server", "proxy_username", "proxy_password"]
    )
    cookie_data = session.linkedin_profile.cookie_data

    storage_state = cookie_data if cookie_data else None
    if storage_state:
        logger.info("Loading saved session for %s", session)

    # Extract proxy configuration from profile
    profile = session.linkedin_profile
    proxy_server = profile.proxy_server
    proxy_username = profile.proxy_username
    proxy_password = profile.proxy_password

    # Get the VNC display for this profile
    display_override = None
    try:
        from openoutreach.core.vnc_manager import get_or_create_vnc_session
        vnc_session = get_or_create_vnc_session(str(profile.pk))
        if vnc_session:
            display_override = vnc_session.display
            logger.debug("Using VNC display %s for profile %s", display_override, profile.pk)
    except Exception as e:
        logger.debug("Could not get VNC display, using default: %s", e)

    session.page, session.context, session.browser, session.playwright = launch_browser(
        storage_state=storage_state,
        proxy_server=proxy_server,
        proxy_username=proxy_username,
        proxy_password=proxy_password,
        display_override=display_override,
    )

    if not storage_state:
        lp = session.linkedin_profile
        authenticate(
            session, username=lp.linkedin_username, password=lp.linkedin_password
        )
        _save_cookies(session)
        logger.info(
            colored("Login successful – session saved", "green", attrs=["bold"])
        )
    else:
        session.page.goto(LINKEDIN_FEED_URL)
        dismiss_comply_gate(session.page)
        goto_page(
            session,
            action=lambda: None,
            expected_url_pattern="/feed",
            error_message="Saved session invalid",
        )

    # "domcontentloaded" — "load" waits for every subresource (analytics
    # beacons, lazy media) and on LinkedIn that event may never fire,
    # hanging the daemon for the duration of the browser timeout.
    session.page.wait_for_load_state("domcontentloaded")
    logger.info(colored("Browser ready", "green", attrs=["bold"]))
    _mark_credential_verified(session)
