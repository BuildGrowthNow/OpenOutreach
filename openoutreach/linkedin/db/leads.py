import logging
import random
import time
from typing import Dict, Any, Optional

from linkedin_cli.url_utils import url_to_public_id, public_id_to_url
from openoutreach.crm.models import DealState

logger = logging.getLogger(__name__)


def lead_exists(url: str) -> bool:
    """Check if Lead already exists for this LinkedIn URL."""
    from openoutreach.mongodb.models import Lead

    pid = url_to_public_id(url)
    if not pid:
        return False
    return Lead.get_by_public_id(pid) is not None


def create_enriched_lead(session, url: str, profile: Dict[str, Any]) -> Optional[str]:
    """Create Lead with full profile data and embedding, and link to campaign.

    Returns lead PK or None if exists.
    Creates a Deal to link the lead to the campaign immediately upon discovery.
    """
    from openoutreach.mongodb.models import Lead, Deal

    # Use canonical public_identifier from Voyager response when available.
    canonical_pid = profile.get("public_identifier")
    public_id = canonical_pid or url_to_public_id(url)
    if not public_id:
        return None
    clean_url = public_id_to_url(public_id)

    urn = profile.get("urn") or None

    # Check if lead exists for this campaign
    existing_lead = Lead.get_by_public_id(public_id)
    if existing_lead:
        # Lead exists - check if already linked to this campaign
        if Deal.get_by_lead_and_campaign(existing_lead.pk, session.campaign.pk) is not None:
            return None  # Already discovered by this campaign
        # Lead exists but not in this campaign - create deal to link them
        deal = Deal(
            lead_id=existing_lead.pk,
            campaign_id=session.campaign.pk,
            state=DealState.DISCOVERED,
            reason="Discovered via search"
        )
        deal.save()
        logger.debug("Linked existing lead %s to campaign %s", public_id, session.campaign)
        return existing_lead.pk

    if urn and Lead.get_by_urn(urn) is not None:
        logger.info(
            "Lead with URN %s already exists — skipping duplicate %s",
            urn,
            public_id,
        )
        return None

    # Create new lead with cached profile data
    degree = profile.get("connection_degree")
    lead = Lead(
        linkedin_url=clean_url,
        public_identifier=public_id,
        cached_profile=profile,
        connection_degree=degree,
    )
    lead.save()
    _cache_urn_from_profile(lead, profile)

    # Create Deal to link lead to campaign immediately
    deal = Deal(
        lead_id=lead.pk,
        campaign_id=session.campaign.pk,
        state=DealState.DISCOVERED,
        reason="Discovered via search"
    )
    deal.save()

    lead.embed_from_profile(profile)

    logger.debug("Created enriched lead for %s (pk=%s)", public_id, lead.pk)

    # Log discovery to activity feed
    from openoutreach.mongodb.models_extended import ActionLog
    _first = profile.get("first_name", "") or profile.get("profile", {}).get("firstName", "")
    _last = profile.get("last_name", "") or profile.get("profile", {}).get("lastName", "")
    _headline = profile.get("headline", "") or profile.get("profile", {}).get("headline", "")
    action_log = ActionLog(
        linkedin_profile_id=session.linkedin_profile.pk,
        campaign_id=session.campaign.pk,
        action_type="lead_discovered",
        status="completed",
        details={
            "lead_name": f"{_first} {_last}".strip() or public_id,
            "lead_url": clean_url,
            "public_identifier": public_id,
            "headline": _headline,
        },
    )
    action_log.save()

    return lead.pk


def promote_lead_to_deal(session, public_id: str, reason: str = ""):
    """Update or create a QUALIFIED Deal for a Lead after LLM approval.

    If a Deal already exists from discovery, it's promoted to QUALIFIED with the reason.
    Returns the Deal.
    """
    from openoutreach.mongodb.models import Lead, Deal

    lead = Lead.get_by_public_id(public_id)
    if not lead:
        raise ValueError(f"No Lead for {public_id}")

    # Check if deal already exists from discovery
    deal = Deal.get_by_lead_and_campaign(lead.pk, session.campaign.pk)
    if deal:
        # Promote existing deal to QUALIFIED with qualification reason
        deal.state = DealState.QUALIFIED
        deal.reason = reason
        deal.save()
    else:
        # Create new deal (shouldn't happen if discovery creates them, but keep as fallback)
        deal = Deal(
            lead_id=lead.pk,
            campaign_id=session.campaign.pk,
            state=DealState.QUALIFIED,
            reason=reason,
        )
        deal.save()

    from termcolor import colored

    logger.info("%s %s", public_id, colored("QUALIFIED", "green", attrs=["bold"]))
    return deal


def get_leads_for_qualification(session) -> list:
    """Leads eligible for qualification in the current campaign.

    Returns profile dicts for leads that:
    - Are not permanently disqualified
    - Have a Deal in this campaign (created at discovery)
    - But haven't been evaluated yet (reason is still "Discovered via search")
    """
    from openoutreach.mongodb.models import Lead, Deal

    # Get Deals that were discovered but not yet qualified by LLM
    unevaluated_deals = Deal.find_unevaluated(session.campaign.pk)

    # Get the leads from those deals, filtering out disqualified ones
    leads = []
    for deal in unevaluated_deals:
        lead = Lead.get(deal.lead_id)
        if lead and not lead.disqualified:
            leads.append(lead)

    return [lead.to_profile_dict() for lead in leads]


def update_lead_slug(old_public_id: str, new_public_id: str):
    """Update a Lead after LinkedIn redirected its vanity URL."""
    from openoutreach.mongodb.models import Lead

    new_url = public_id_to_url(new_public_id)
    lead = Lead.get_by_public_id(old_public_id)
    if lead:
        lead.public_identifier = new_public_id
        lead.linkedin_url = new_url
        lead.save()
        logger.info("Lead slug updated: %s → %s", old_public_id, new_public_id)
        return True
    return False


def disqualify_lead(public_id: str):
    """Set Lead.disqualified = True (account-level, permanent, cross-campaign)."""
    from openoutreach.mongodb.models import Lead

    lead = Lead.get_by_public_id(public_id)
    if not lead:
        logger.warning("disqualify_lead: no Lead for %s", public_id)
        return
    lead.disqualified = True
    lead.save()


def discover_and_enrich(session, urls):
    """For each new URL, call Voyager API, create enriched Lead (with embedding).

    Skips URLs that already have a Lead, caps at enrich_max_per_page (DOM
    order — LinkedIn's own relevance), and pauses a human-ish
    [enrich_min_delay_seconds, enrich_max_delay_seconds] between scrapes.
    """
    from linkedin_cli.api.client import PlaywrightLinkedinAPI
    from openoutreach.core.conf import CAMPAIGN_CONFIG

    new_urls = [u for u in urls if not lead_exists(u)]
    if not new_urls:
        return

    max_per_page = CAMPAIGN_CONFIG["enrich_max_per_page"]
    if len(new_urls) > max_per_page:
        new_urls = new_urls[:max_per_page]

    logger.info(
        "Discovered %d new profiles (%d total on page)", len(new_urls), len(urls)
    )

    min_delay = CAMPAIGN_CONFIG["enrich_min_delay_seconds"]
    max_delay = CAMPAIGN_CONFIG["enrich_max_delay_seconds"]
    session.ensure_browser()
    api = PlaywrightLinkedinAPI(session=session)
    enriched = 0

    for url in new_urls:
        public_id = url_to_public_id(url)
        if not public_id:
            continue

        try:
            profile, _raw = api.get_profile(profile_url=url)
        except Exception:
            logger.warning("Voyager API failed for %s — skipping", url)
            continue

        if not profile:
            logger.warning("Empty profile for %s — skipping", url)
            continue

        if create_enriched_lead(session, url, profile) is not None:
            enriched += 1

        time.sleep(random.uniform(min_delay, max_delay))

    logger.info("Enriched %d/%d new profiles", enriched, len(new_urls))


def _cache_urn_from_profile(lead, profile: Dict[str, Any]):
    """Promote ``profile['urn']`` onto the Lead row if not already cached.

    The only durable field we extract from a fresh scrape — everything
    else lives in memory for the lifetime of the caller's dict.
    """
    urn = profile.get("urn") or None
    if urn and lead.urn != urn:
        lead.urn = urn
        lead.save()


def register_self_lead(session, profile: Dict[str, Any]):
    """Persist the logged-in member's own profile as a disqualified Lead.

    The CRM-side layer over ``linkedin_cli``'s self-discovery primitive: marks
    the real profile disqualified (so auto-discovery never targets it) and links
    it as ``linkedin_profile.self_lead``. Idempotent per profile.
    """
    from openoutreach.mongodb.models import Lead

    public_id = profile["public_identifier"]
    lead = Lead.get_by_public_id(public_id)
    if not lead:
        lead = Lead(
            public_identifier=public_id,
            linkedin_url=public_id_to_url(public_id),
            disqualified=True
        )
        lead.save()
    else:
        lead.linkedin_url = public_id_to_url(public_id)
        lead.disqualified = True
        lead.save()

    _cache_urn_from_profile(lead, profile)

    session.linkedin_profile.self_lead_id = lead.pk
    session.linkedin_profile.save()
    logger.info("Registered self-profile as disqualified Lead: %s", public_id)
