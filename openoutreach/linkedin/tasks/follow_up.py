# openoutreach/linkedin/tasks/follow_up.py
"""Follow-up task — runs the agentic follow-up for one eligible CONNECTED deal."""
from __future__ import annotations
  
import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Dict, Optional
  
from django.utils import timezone
from termcolor import colored
  
from openoutreach.crm.models import DealState
from openoutreach.linkedin.models import ActionLog
from openoutreach.linkedin.services.ghost_mode import GhostModeInterceptor
from openoutreach.linkedin.services.smart_rate_limits import smart_can_execute, smart_record_action, smart_get_remaining
  
logger = logging.getLogger(__name__)
 
if TYPE_CHECKING:
    from openoutreach.core.db.lead import Lead
    from openoutreach.core.db.deal import Deal
    from openoutreach.linkedin.browser.session import AccountSession
 
# Required silence between nudges scales with unanswered count:
# 1 unanswered → 3d, 2 → 6d, 3 → 9d. Skips the LLM call while open.
MIN_DAYS_PER_UNANSWERED = 3
 
 
def _build_send_profile(deal) -> dict:
    """Minimal profile dict for ``send_raw_message`` and its fallbacks."""
    lead = deal.lead
    return {
        "public_identifier": lead.public_identifier,
        "urn": lead.urn or "",
    }
 
 
def _too_soon_to_nudge(deal) -> bool:
    """Wait ``unanswered_count * MIN_DAYS_PER_UNANSWERED`` days between nudges."""
    from openoutreach.chat.models import ChatMessage
 
    messages = ChatMessage.objects.filter(deal=deal)
 
    last = messages.order_by("-creation_date").first()
    if last is None or not last.is_outgoing:
        return False
 
    last_reply = messages.filter(is_outgoing=False).order_by("-creation_date").first()
    nudges = messages.filter(is_outgoing=True)
    if last_reply:
        nudges = nudges.filter(creation_date__gt=last_reply.creation_date)
 
    required = timedelta(days=nudges.count() * MIN_DAYS_PER_UNANSWERED)
    return timezone.now() - last.creation_date < required
 
 
def _connected_deals(campaign):
    """Open, non-disqualified CONNECTED deals in *campaign*, oldest first."""
    from openoutreach.crm.models import Deal
 
    return (
        Deal.objects.filter(
            campaign=campaign,
            state=DealState.CONNECTED,
            outcome="",
            lead__disqualified=False,
        )
        .select_related("lead", "campaign")
        .order_by("update_date")
    )
 
 
def _next_followup_deal(campaign):
    """Oldest CONNECTED deal in *campaign* not on a nudge cooldown."""
    for deal in _connected_deals(campaign):
        if not _too_soon_to_nudge(deal):
            return deal
    return None
 
 
def handle_follow_up(task, session, qualifiers):
    campaign = session.campaign
 
    # Check if ghost mode is active for this campaign
    ghost_campaign = campaign.ghost_campaigns.filter(is_active=True).first()
    if ghost_campaign:
        interceptor = GhostModeInterceptor(ghost_campaign)
        if not interceptor.can_proceed("follow_up"):
            deal = _next_followup_deal(campaign)
            if deal:
                interceptor.simulate_action(
                    "follow_up",
                    {"days_since_connect": 3, "name": deal.lead.public_identifier},
                    {"campaign": campaign, "session": session},
                )
                logger.info(
                    "[%s] Ghost mode: Would send follow-up to %s (simulated)",
                    campaign,
                    deal.lead.public_identifier,
                )
            return
 
    # Smart rate limiting check
    if not smart_can_execute(session.linkedin_profile, ActionLog.ActionType.FOLLOW_UP, campaign):
        remaining = smart_get_remaining(session.linkedin_profile, ActionLog.ActionType.FOLLOW_UP, campaign)
        logger.info("[%s] follow_up: smart rate limit reached (remaining: %d) — slot skipped", campaign, remaining)
        return
 
    deal = _next_followup_deal(campaign)
    if deal is None:
        connected = _connected_deals(campaign).count()
        if connected:
            logger.info(
                "[%s] follow_up: %d connected lead(s), all within nudge cooldown — nothing due",
                campaign, connected,
            )
        else:
            logger.info("[%s] follow_up: no connected leads yet — nobody to follow up", campaign)
        return
 
    public_id = deal.lead.public_identifier
    logger.info(
        "[%s] %s %s",
        campaign, colored("▶ follow_up", "green", attrs=["bold"]), public_id,
    )
 
    materialize_profile_summary_if_missing(deal, session)
    decision = run_follow_up_agent(session, deal)
 
    profile = _build_send_profile(deal)
 
    if decision.action == "send_message":
        logger.info("[%s] follow_up message for %s: %s", campaign, public_id, decision.message)
        sent = send_raw_message(session, profile, decision.message)
        if not sent:
            set_profile_state(session, public_id, DealState.QUALIFIED.value)
            logger.warning("follow_up for %s: send failed — moving to QUALIFIED for re-connection", public_id)
            return
        # Record action with smart rate limiter
        smart_record_action(session.linkedin_profile, ActionLog.ActionType.FOLLOW_UP, campaign)
        # Also record in ActionLog for backward compatibility
        session.linkedin_profile.record_action(
            ActionLog.ActionType.FOLLOW_UP, session.campaign,
        )
        # Persist the outgoing message locally and bump update_date so the
        # next slot's eligibility query respects the cooldown and moves
        # this deal to the back of the queue.
        from openoutreach.linkedin.db.chat import sync_conversation
        try:
            sync_conversation(session, public_id)
        except Exception:
            logger.exception("post-send sync failed for %s (best-effort)", public_id)
        deal.save()
 
    elif decision.action == "mark_completed":
        set_profile_state(session, public_id, DealState.COMPLETED.value, outcome=decision.outcome)
        logger.info("[%s] follow_up completed for %s: outcome=%s", campaign, public_id, decision.outcome)
 
    elif decision.action == "wait":
        # Bump update_date so the eligibility query cycles to a different deal
        # next time; this deal returns to the front only after others are touched.
        deal.save()
    
    # State Machine Integration - Execute state machine if campaign has one
    _try_execute_state_machine(deal, session)


def _try_execute_state_machine(deal: "Deal", session, last_message: Optional[Dict] = None) -> None:
    """Try to execute the state machine for a deal if it has one configured."""
    from openoutreach.linkedin.models.state_machine import CampaignState, CampaignStateGraph
    from openoutreach.linkedin.services.state_machine import StateMachineEngine
    
    try:
        # Check if campaign has an active state graph
        state_graph = CampaignStateGraph.objects.filter(
            campaign=deal.campaign,
            is_active=True,
        ).first()
        
        if not state_graph:
            return
        
        # Get or create state machine instance for this deal
        state_machine, created = CampaignState.objects.get_or_create(
            deal=deal,
            state_graph=state_graph,
            defaults={
                'current_node': state_graph.nodes.filter(node_type='start').first(),
                'status': CampaignState.STATUS_ACTIVE,
            }
        )
        
        # Check if waiting (cooldown period)
        if state_machine.wait_until and timezone.now() < state_machine.wait_until:
            return  # Still waiting, skip this execution
        
        # Check if already completed or errored
        if state_machine.status in (CampaignState.STATUS_COMPLETED, CampaignState.STATUS_ERROR):
            return
        
        # Execute state machine step
        engine = StateMachineEngine(state_graph)
        success, message = engine.execute_step(state_machine, session)
        
        if not success:
            logger.error(f"State machine execution failed for deal {deal.id}: {message}")
            return
        
        logger.info(f"State machine step completed for deal {deal.id}: {message}")
        
    except Exception as e:
        logger.exception(f"Error executing state machine for deal {deal.id}: {e}")


# Re-imports needed for type hints (local import avoids circular imports)
from openoutreach.core.db.deals import set_profile_state
from openoutreach.core.db.summaries import materialize_profile_summary_if_missing
from linkedin_cli.actions.message import send_raw_message
from openoutreach.core.agents.follow_up import run_follow_up_agent
