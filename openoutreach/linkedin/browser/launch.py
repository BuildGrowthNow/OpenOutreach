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
        from django.utils import timezone

        profile = session.linkedin_profile
        cred = getattr(profile, "credentials", None)
        if cred is None:
            try:
                from openoutreach.crm.models import LinkedInCredentials
                cred = LinkedInCredentials.objects.filter(linkedin_profile=profile).first()
            except Exception:
                return

        if cred is None:
            return

        update_fields = []
        cred.last_verified = timezone.now()
        update_fields.append("last_verified")

        if cred.status != "active":
            cred.status = "active"
            update_fields.append("status")

        cred.save(update_fields=update_fields)

        try:
            from openoutreach.crm.models import LinkedInCredentialLog
            LinkedInCredentialLog.objects.create(
                credentials=cred,
                action=LinkedInCredentialLog.ACTION_VERIFIED,
                details={"verified_by": "daemon", "method": "cookie_session"},
            )
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

    session.linkedin_profile.refresh_from_db(fields=["cookie_data_encrypted"])
    cookie_data = session.linkedin_profile.cookie_data

    storage_state = cookie_data if cookie_data else None
    if storage_state:
        logger.info("Loading saved session for %s", session)

    session.page, session.context, session.browser, session.playwright = launch_browser(
        storage_state=storage_state
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
