import logging

from termcolor import colored

from openoutreach.crm.models import DealState

logger = logging.getLogger(__name__)

_STATE_LOG_STYLE = {
    DealState.QUALIFIED: ("QUALIFIED", "green", []),
    DealState.READY_TO_CONNECT: ("READY_TO_CONNECT", "yellow", ["bold"]),
    DealState.PENDING: ("PENDING", "cyan", []),
    DealState.CONNECTED: ("CONNECTED", "green", ["bold"]),
    DealState.COMPLETED: ("COMPLETED", "green", ["bold"]),
    DealState.FAILED: ("FAILED", "red", ["bold"]),
    DealState.NO_EMAIL: ("NO_EMAIL", "yellow", []),
}


def increment_connect_attempts(session, public_id: str) -> int:
    """Increment connect_attempts on the Deal and return the new count."""
    from openoutreach.mongodb.models import Deal

    deal = Deal.get_by_lead_and_campaign(public_id, session.campaign.pk)
    if not deal:
        return 1

    deal.connect_attempts += 1
    deal.save()
    return deal.connect_attempts


def _deal_to_profile_dict(deal) -> dict:
    """Convert a Deal (with select_related lead) to a profile dict for lanes."""
    from openoutreach.mongodb.models import Lead

    # Load lead if not already attached
    if not hasattr(deal, 'lead') or deal.lead is None:
        deal.lead = Lead.get(deal.lead_id)

    if not deal.lead:
        # Fallback to minimal dict if lead is missing
        return {
            "lead_id": deal.lead_id,
            "public_identifier": "unknown",
            "url": "",
            "meta": {
                "connect_attempts": deal.connect_attempts,
                "backoff_hours": deal.backoff_hours,
                "reason": deal.reason,
            }
        }

    base = deal.lead.to_profile_dict()
    base["meta"] = {
        "connect_attempts": deal.connect_attempts,
        "backoff_hours": deal.backoff_hours,
        "reason": deal.reason,
    }
    return base


def _deals_at_state(session, state: DealState) -> list:
    """Return profile dicts for all Deals at the given state in this campaign."""
    from openoutreach.mongodb.models import Deal

    deals = Deal.find_by_state_and_campaign(state, session.campaign.pk)
    return [_deal_to_profile_dict(d) for d in deals]


def _existing_deal_or_lead(public_id: str, campaign):
    """Check for an existing Deal in campaign; if none, look up the Lead.

    Returns (lead, existing_deal) — exactly one will be non-None,
    or both None if no Lead exists at all.
    """
    from openoutreach.mongodb.models import Deal, Lead

    existing = Deal.get_by_lead_and_campaign(public_id, campaign.pk)
    if existing:
        return None, existing
    lead = Lead.get_by_public_id(public_id)
    return lead, None


# ── State transitions ──


def _capture_contact_info(lead, session) -> None:
    """Best-effort LinkedIn contact-info capture when a lead first connects.

    Fired on the CONNECTED transition — the moment LinkedIn exposes a 1st-degree
    connection's email/phone. A failure here must never roll back the transition
    or fail the task, so expected scrape/network errors are swallowed with a log;
    ``AuthenticationError`` still propagates (the daemon's reauth handler owns it,
    and capture is moot on a dead session).
    """
    from linkedin_cli.exceptions import ProfileInaccessibleError

    try:
        lead.capture_contact_info(session)
    except (ProfileInaccessibleError, IOError) as exc:
        logger.warning(
            "contact-info capture failed for %s: %s", lead.public_identifier, exc
        )


def set_profile_state(
    session, public_identifier: str, new_state: str, reason: str = "", outcome: str = ""
):
    """Move the Deal to the corresponding state and enqueue the implied next task.

    Campaign-scoped: only finds Deals in the current campaign.
    Raises ValueError if no Deal exists.

    Task creation for state-driven transitions (CONNECTED → follow_up,
    PENDING → check_pending) happens here via the scheduler hook — callers
    do not enqueue directly.
    """
    from openoutreach.mongodb.models import Deal, Lead
    from openoutreach.core.scheduler import on_deal_state_entered

    deal = Deal.get_by_lead_and_campaign(public_identifier, session.campaign.pk)
    if not deal:
        raise ValueError(
            f"No Deal for {public_identifier} — cannot set state {new_state}"
        )

    # Load lead if not already loaded
    if not hasattr(deal, 'lead') or deal.lead is None:
        deal.lead = Lead.get_by_public_id(public_identifier)

    ps = DealState(new_state)
    state_changed = deal.state != ps

    deal.state = ps

    if reason:
        deal.reason = reason
    if outcome:
        deal.outcome = outcome

    deal.save()

    label, color, attrs = _STATE_LOG_STYLE.get(ps, ("ERROR", "red", ["bold"]))
    suffix = f" ({reason})" if reason else ""
    if state_changed:
        logger.info(
            "%s %s%s", public_identifier, colored(label, color, attrs=attrs), suffix
        )
    else:
        logger.debug("%s %s (unchanged)%s", public_identifier, label, suffix)

    on_deal_state_entered(deal)

    if state_changed and ps == DealState.CONNECTED:
        if deal.lead:
            _capture_contact_info(deal.lead, session)


# ── State queries ──


def get_qualified_profiles(session) -> list:
    return _deals_at_state(session, DealState.QUALIFIED)


def get_ready_to_connect_profiles(session) -> list:
    return _deals_at_state(session, DealState.READY_TO_CONNECT)


def get_profile_dict_for_public_id(session, public_id: str) -> dict | None:
    """Load profile dict for a single public_id from Deal + Lead (campaign-scoped)."""
    from openoutreach.mongodb.models import Deal, Lead

    deal = Deal.get_by_lead_and_campaign(public_id, session.campaign.pk)
    if not deal:
        return None

    # Load lead if not already loaded
    if not hasattr(deal, 'lead') or deal.lead is None:
        deal.lead = Lead.get_by_public_id(public_id)

    return _deal_to_profile_dict(deal)


# ── Deal creation ──


def create_disqualified_deal(session, public_id: str, reason: str = ""):
    """Create a FAILED Deal with 'Disqualified' closing reason for an LLM-rejected lead.

    LLM qualification rejections are tracked as FAILED Deals (campaign-scoped),
    NOT as Lead.disqualified (which is for permanent account-level exclusion).
    """
    from openoutreach.crm.models import Outcome

    campaign = session.campaign
    lead, existing = _existing_deal_or_lead(public_id, campaign)
    if existing:
        return existing
    if not lead:
        logger.warning("create_disqualified_deal: no Lead for %s", public_id)
        return None

    deal = _create_deal(
        lead=lead,
        state=DealState.FAILED,
        session=session,
        outcome=Outcome.WRONG_FIT,
        reason=reason,
    )

    suffix = f" ({reason})" if reason else ""
    logger.info(
        "%s %s%s", public_id, colored("DISQUALIFIED", "red", attrs=["bold"]), suffix
    )
    return deal



def _create_deal(
    *,
    lead,
    state,
    session,
    outcome="",
    reason="",
):
    """Shared Deal creation with common defaults."""
    from openoutreach.mongodb.models import Deal

    deal = Deal(
        lead_id=lead.pk,
        campaign_id=session.campaign.pk,
        state=state,
        outcome=outcome,
        reason=reason,
    )
    deal.save()
    deal.lead = lead  # Attach for immediate access
    return deal
