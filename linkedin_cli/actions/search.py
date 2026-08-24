import json
import logging
from typing import TYPE_CHECKING, Dict, Any
from urllib.parse import urlencode

from linkedin_cli.browser.nav import goto_page, extract_in_urls

if TYPE_CHECKING:
    from linkedin_cli.session import LinkedInSession

# LinkedIn connection-degree filter codes for People search (`network` facet).
NETWORK_CODES = {"first": "F", "second": "S", "third": "O"}

logger = logging.getLogger(__name__)

SELECTORS = {
    "search_bar": "//input[contains(@placeholder, 'Search')]",
    "profile_links": 'a[href*="/in/"]',
}


def _go_to_profile(session: "LinkedInSession", url: str, public_identifier: str):
    if f"/in/{public_identifier}" in session.page.url:
        return
    logger.debug("Direct navigation → %s", public_identifier)
    try:
        goto_page(
            session,
            action=lambda: session.page.goto(url, wait_until="domcontentloaded"),
            expected_url_pattern=f"/in/{public_identifier}",
            error_message="Failed to navigate to the target profile"
        )
    except RuntimeError:
        # Redirect to a different /in/ slug is tolerated; reconciling the
        # lead's stored slug is the caller's job (this layer holds no DB).
        if not _detect_profile_redirect(session, public_identifier):
            raise


def _detect_profile_redirect(session, old_public_id: str) -> str | None:
    """Return the new public_id if LinkedIn redirected to a different /in/ slug."""
    from urllib.parse import unquote
    from linkedin_cli.url_utils import url_to_public_id

    new_id = url_to_public_id(unquote(session.page.url))
    if new_id and new_id != old_public_id:
        logger.info("Profile redirect: %s → %s", old_public_id, new_id)
        return new_id
    return None


def visit_profile(session: "LinkedInSession", profile: Dict[str, Any]):
    public_identifier: str = profile.get("public_identifier") or ""

    # Ensure browser is alive before doing anything
    session.ensure_browser()

    already_there = f"/in/{public_identifier}" in session.page.url

    if already_there:
        return

    url: str = profile.get("url") or ""
    _go_to_profile(session, url, public_identifier)

    # Emit the /in/ profile URLs visible on the page; enrichment is caller-side.
    return extract_in_urls(session.page)


def _search_url(keyword: str, page: int = 1, network=None) -> str:
    """Build a People-search results URL, optionally filtered by connection degree.

    *network* is an optional list of degree codes - ``F`` (1st), ``S`` (2nd),
    ``O`` (3rd+) - passed to LinkedIn's ``network`` facet as a JSON array.
    """
    params = {"keywords": keyword, "origin": "FACETED_SEARCH"}
    if network:
        params["network"] = json.dumps(list(network))
    if page > 1:
        params["page"] = str(page)
    return "https://www.linkedin.com/search/results/people/?" + urlencode(params)



def search_people(session: "LinkedInSession", keyword: str, page: int = 1, network=None) -> dict:
    """Search LinkedIn People; return the result page as a structured envelope.

    *network* optionally filters by connection degree (a list of `F`/`S`/`O`
    codes). Results carry only ``{public_identifier, url}`` - no `urn`; a
    follow-up `profile` scrape per url resolves the rest. Returns::

        {"query": ..., "page": ..., "network": [...]|None,
         "profiles": [{"public_identifier": ..., "url": ...}, ...]}
    """
    from linkedin_cli.url_utils import url_to_public_id

    session.ensure_browser()
    goto_page(
        session,
        action=lambda: session.page.goto(_search_url(keyword, page, network)),
        expected_url_pattern="/search/results/people/",
        error_message="Failed to reach People search results",
    )

    profiles, seen = [], set()
    for url in extract_in_urls(session.page):
        public_id = url_to_public_id(url)
        if public_id and public_id not in seen:
            seen.add(public_id)
            profiles.append({"public_identifier": public_id, "url": url})

    return {"query": keyword, "page": page,
            "network": list(network) if network else None, "profiles": profiles}


