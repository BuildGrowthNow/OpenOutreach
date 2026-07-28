# linkedin/actions/profile.py
import logging

from ..api.client import PlaywrightLinkedinAPI

logger = logging.getLogger(__name__)


def scrape_profile(session, profile: dict):
    url = profile["url"]

    session.ensure_browser()
    session.wait()

    api = PlaywrightLinkedinAPI(session=session)

    logger.info("Enriching profile → %s", url)
    enriched, data = api.get_profile(profile_url=url)

    if enriched:
        logger.info("Profile enriched – %s", enriched.get("public_identifier"))
        profile = enriched

    return profile, data
