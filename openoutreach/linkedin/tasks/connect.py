# openoutreach/linkedin/tasks/connect.py
"""Connect task - resolves one candidate from the campaign pool and acts.

Lazy: the task payload carries only ``campaign_id``. The handler picks
its candidate at execution time via the campaign's ``ConnectStrategy``.
No self-rescheduling - pacing is owned by ``tasks/scheduler.py``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from openoutreach.core.db.deals import increment_connect_attempts, set_profile_state
from openoutreach.crm.models import DealState
from openoutreach.linkedin.db.leads import disqualify_lead
from openoutreach.linkedin.models import ActionLog
from openoutreach.linkedin.services.smart_rate_limits import (
    smart_can_execute,
    smart_record_action,
    smart_get_remaining,
)
from openoutreach.mongodb.models import Deal, Lead

from linkedin_cli.exceptions import (
    ProfileInaccessibleError,
    ReachedConnectionLimit,
    SkipProfile,
)

logger = logging.getLogger(__name__)

MAX_CONNECT_ATTEMPTS = 3


@dataclass
class ConnectStrategy:
    find_candidate: Callable
    pre_connect: Callable | None
    qualifier: Any


def strategy_for(campaign, qualifiers):
    """Build the right ConnectStrategy based on campaign type."""
    qualifier = qualifiers.get(campaign.pk)

    if qualifier is None:
        logger.error(
            "No qualifier found for campaign %s (pk=%s). Available qualifiers: %s",
            campaign,
            campaign.pk,
            list(qualifiers.keys()),
        )
        raise ValueError(f"No qualifier found for campaign {campaign.pk}")

    from openoutreach.linkedin.pipeline.pools import find_candidate

    # Capture find_candidate in closure
    def find_candidate_wrapper(s):
        return find_candidate(s, qualifier)

    return ConnectStrategy(
        find_candidate=find_candidate_wrapper,
        pre_connect=None,
        qualifier=qualifier,
    )


def handle_connect(task, session, qualifiers):
    from linkedin_cli.actions.connect import send_connection_request
    from linkedin_cli.actions.status import get_connection_status

    campaign = session.campaign
    strategy = strategy_for(campaign, qualifiers)

    # Note: Ghost mode is a disabled feature, skipping check

    # Smart rate limiting check
    if not smart_can_execute(
        session.linkedin_profile, ActionLog.ActionType.CONNECT, campaign
    ):
        remaining = smart_get_remaining(
            session.linkedin_profile, ActionLog.ActionType.CONNECT, campaign
        )
        logger.info(
            "[%s] connect: smart rate limit reached (remaining: %d) - slot skipped",
            campaign,
            remaining,
        )
        return

    target_deal_id = (getattr(task, "payload", None) or {}).get("deal_id")
    if target_deal_id:
        # Sequence tasks are bound to one deal.  Resolve that lead directly;
        # the legacy pool picker is intentionally not used here.
        target_deal = Deal.get(str(target_deal_id))
        if not target_deal or str(target_deal.campaign_id) != str(campaign.pk):
            logger.info("[%s] connect: target deal %s not found", campaign, target_deal_id)
            return
        lead = Lead.get(target_deal.lead_id)
        if not lead or not lead.public_identifier:
            logger.info("[%s] connect: target deal %s has no LinkedIn identifier", campaign, target_deal_id)
            return
        profile = dict(lead.cached_profile or {})
        profile.setdefault("public_identifier", lead.public_identifier)
        candidate = {"public_identifier": lead.public_identifier, "profile": profile}
    else:
        try:
            candidate = strategy.find_candidate(session)
        except Exception as e:
            if "Failed to fetch" in str(e) or "Page.evaluate" in str(e):
                logger.warning("[%s] connect: Voyager API unavailable during candidate search - slot skipped (%s)", campaign, type(e).__name__)
                return
            raise
    if candidate is None:
        logger.info("[%s] connect: no candidate available - slot skipped", campaign)
        return

    public_id = candidate["public_identifier"]
    profile = candidate.get("profile") or candidate

    # Freemium campaigns need a Deal before set_profile_state
    if strategy.pre_connect:
        strategy.pre_connect(session, public_id)

    # Find the deal using MongoDB query
    lead = Lead.find_by_public_identifier(public_id)
    deal = None
    if lead:
        deal = Deal.get_by_lead_and_campaign(lead._id, session.campaign._id if hasattr(session.campaign, '_id') else str(session.campaign))

    # Check target_degrees filter - skip leads whose degree doesn't match
    target_degrees = getattr(campaign, "target_degrees", None) or [1, 2, 3]
    if lead and lead.connection_degree is not None:
        if lead.connection_degree not in target_degrees:
            degree_val = lead.connection_degree
            logger.info(
                "[%s] connect: %s degree %d not in target_degrees %s - skipped",
                campaign, public_id, degree_val, target_degrees,
            )
            from openoutreach.mongodb.models_extended import ActionLog as ActionLogExt
            ActionLogExt(
                linkedin_profile_id=session.linkedin_profile.pk,
                campaign_id=campaign.pk if campaign else "",
                action_type="connect_skipped",
                status="skipped",
                details={
                    "public_identifier": public_id,
                    "reason": f"{degree_val}° not in target degrees {target_degrees}",
                },
            ).save()
            return

    reason = deal.reason if deal else ""
    stats = ""
    if strategy.qualifier and not target_deal_id:
        stats = strategy.qualifier.explain(candidate, session)
    logger.info("[%s] connect", campaign)
    logger.info("[%s] %s (%s) - %s", campaign, public_id, stats, reason or "")

    try:
        # The library observes a UI state and returns it as a str; lift it into
        # our funnel enum at the boundary.
        status = DealState(get_connection_status(session, profile).value)

        # Update lead's connection_degree from the fresh API check
        degree = profile.get("connection_degree")
        if degree is not None and lead:
            lead.connection_degree = degree
            lead.save(update_fields=["connection_degree"])

        # Re-check degree filter after fresh API call
        if degree is not None and degree not in target_degrees:
            logger.info(
                "[%s] connect: %s fresh degree %d not in target_degrees %s - skipped",
                campaign, public_id, degree, target_degrees,
            )
            from openoutreach.mongodb.models_extended import ActionLog as ActionLogExt
            ActionLogExt(
                linkedin_profile_id=session.linkedin_profile.pk,
                campaign_id=campaign.pk if campaign else "",
                action_type="connect_skipped",
                status="skipped",
                details={
                    "public_identifier": public_id,
                    "reason": f"{degree}° not in target degrees {target_degrees}",
                },
            ).save()
            return

        # 1st-degree leads: skip connect, transition directly to CONNECTED
        if degree == 1 or status == DealState.CONNECTED:
            set_profile_state(session, public_id, DealState.CONNECTED.value)
            if degree == 1:
                logger.info("[%s] %s already 1st-degree - auto-CONNECTED", campaign, public_id)
            return

        if status == DealState.PENDING:
            set_profile_state(session, public_id, status.value)
            return

        # get_connection_status already navigated to the profile page
        new_state = DealState(
            send_connection_request(session=session, profile=profile).value
        )

        if new_state == DealState.QUALIFIED:
            # No Connect button found - track attempt, disqualify after MAX_CONNECT_ATTEMPTS
            attempts = increment_connect_attempts(session, public_id)
            if attempts >= MAX_CONNECT_ATTEMPTS:
                reason = f"Unreachable: no Connect button after {attempts} attempts"
                disqualify_lead(public_id)
                set_profile_state(
                    session, public_id, DealState.FAILED.value, reason=reason
                )
                logger.warning("Disqualified %s - %s", public_id, reason)
            else:
                set_profile_state(session, public_id, new_state.value)
                logger.debug(
                    "%s: connect attempt %d/%d - no button found",
                    public_id,
                    attempts,
                    MAX_CONNECT_ATTEMPTS,
                )
        else:
            set_profile_state(session, public_id, new_state.value)
            # Record action with smart rate limiter
            smart_record_action(
                session.linkedin_profile, ActionLog.ActionType.CONNECT, campaign
            )
            # Also record in ActionLog with details
            lead_name = ""
            if lead and lead.cached_profile and isinstance(lead.cached_profile, dict):
                first = lead.cached_profile.get("first_name", "")
                last = lead.cached_profile.get("last_name", "")
                lead_name = f"{first} {last}".strip()
            if not lead_name:
                nested = profile.get("profile", {})
                first = nested.get("firstName", "") or nested.get("first_name", "")
                last = nested.get("lastName", "") or nested.get("last_name", "")
                lead_name = f"{first} {last}".strip() or public_id

            session.linkedin_profile.record_action(
                ActionLog.ActionType.CONNECT,
                session.campaign,
                details={
                    "lead_name": lead_name,
                    "public_identifier": public_id,
                    "state": new_state.value,
                },
            )

    except ReachedConnectionLimit as e:
        logger.warning("Rate limited: %s", type(e).__name__)
        session.linkedin_profile.mark_exhausted(ActionLog.ActionType.CONNECT)
    except ProfileInaccessibleError as e:
        logger.warning("Profile inaccessible - marking FAILED: %s", type(e).__name__)
        set_profile_state(
            session,
            public_id,
            DealState.FAILED.value,
            reason=f"Profile inaccessible: {e}",
        )
    except SkipProfile as e:
        logger.warning("Skipping %s: %s", public_id, type(e).__name__)
        set_profile_state(session, public_id, DealState.FAILED.value)
    except Exception as e:
        if "Failed to fetch" in str(e) or "Page.evaluate" in str(e):
            logger.warning("[%s] connect: Voyager API unavailable during connect attempt - slot skipped (%s)", campaign, type(e).__name__)
            return
        raise
