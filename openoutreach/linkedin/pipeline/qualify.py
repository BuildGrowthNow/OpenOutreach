# openoutreach/linkedin/pipeline/qualify.py
"""Qualify orchestration for the lazy chain."""

from __future__ import annotations

import logging

import numpy as np
from termcolor import colored

from openoutreach.linkedin.ml.qualifier import BayesianQualifier

logger = logging.getLogger(__name__)


def fetch_qualification_candidates(session):
    """Return Lead rows (with embeddings) for leads awaiting qualification."""
    from openoutreach.mongodb.models import Lead
    from openoutreach.linkedin.db.leads import get_leads_for_qualification

    leads = get_leads_for_qualification(session)
    if not leads:
        return []

    lead_ids = {ld["lead_id"] for ld in leads}

    # Find leads with embeddings for this campaign
    candidates = [Lead.get(lead_id) for lead_id in lead_ids]
    candidates = [c for c in candidates if c and c.embedding is not None]
    if candidates:
        return candidates

    # Robustness fallback: embed any lead that was missed at discovery time
    for ld in leads:
        lead = Lead.get(ld["lead_id"])
        if not lead or lead.embedding is not None:
            continue
        if lead.get_embedding(session) is not None:
            return [lead]

    return []


def run_qualification(session, qualifier: BayesianQualifier) -> str | None:
    """Qualify one unlabelled profile via BALD/auto-decision/LLM. Returns public_id or None."""
    from openoutreach.linkedin.ml.qualifier import qualify_with_llm, format_prediction
    from openoutreach.mongodb.connection import get_mongodb_collection
    from openoutreach.crm.models import DealState

    # Cap the QUALIFIED+READY_TO_CONNECT backlog at 3× the daily connect limit so
    # we don't accumulate thousands of qualified leads that can't be connected in time.
    deals_col = get_mongodb_collection("deals")
    if deals_col is not None:
        backlog = deals_col.count_documents({
            "campaign_id": session.campaign.pk,
            "state": {"$in": [DealState.QUALIFIED.value, DealState.READY_TO_CONNECT.value]},
        })
        daily_limit = getattr(session.linkedin_profile, "connect_daily_limit", 20)
        cap = max(30, daily_limit * 3)
        if backlog >= cap:
            logger.info(
                "[%s] qualify: backlog %d ≥ cap %d — pausing (drain connects first)",
                session.campaign, backlog, cap,
            )
            return None

    candidates = fetch_qualification_candidates(session)
    if not candidates:
        return None

    logger.info(colored("\u25b6 qualify", "blue", attrs=["bold"]))

    # Balance-driven candidate selection
    selection_score = None
    if len(candidates) == 1:
        candidate = candidates[0]
    else:
        embeddings = np.array([c.embedding_array for c in candidates], dtype=np.float32)
        result = qualifier.acquisition_scores(embeddings)

        if result is None:
            candidate = candidates[0]
        else:
            strategy, scores = result
            best_idx = int(np.argmax(scores))
            candidate = candidates[best_idx]
            selection_score = (strategy, float(scores[best_idx]))
            n_neg, n_pos = qualifier.class_counts
            logger.info(
                "Strategy: %s (neg=%d, pos=%d)",
                colored(strategy, "cyan", attrs=["bold"]),
                n_neg,
                n_pos,
            )

    lead_id = candidate.pk
    public_id = candidate.public_identifier
    embedding = candidate.embedding_array
    if embedding is None:
        logger.warning(
            "No embedding for lead %d (%s) — disqualifying", lead_id, public_id
        )
        return None

    # Use a different variable name to avoid type interference from previous assignment
    predicted = qualifier.predict(embedding)

    if predicted is not None:
        # Type: predicted is tuple[float, float, float] when not None
        pred_prob, entropy, std = predicted  # type: ignore
        stats = format_prediction(pred_prob, entropy, std, qualifier.n_obs)
        sel = (
            f", {selection_score[0]}={selection_score[1]:.4f}"
            if selection_score
            else ""
        )
        logger.debug("%s (%s%s) — querying LLM", public_id, stats, sel)
    else:
        logger.debug(
            "%s GP not fitted (%d obs) — querying LLM", public_id, qualifier.n_obs
        )

    profile_text = _fetch_profile_text(session, lead_id, public_id)
    if not profile_text:
        logger.warning("No profile text for lead %d \u2014 disqualifying", lead_id)
        _save_qualification_result(
            session,
            qualifier,
            lead_id,
            public_id,
            embedding,
            0,
            "no profile text available",
        )
        return public_id

    campaign = session.campaign
    label, reason = qualify_with_llm(
        profile_text,
        product_pitch=campaign.product_pitch,
        campaign_objective=campaign.campaign_objective,
        icp_titles=campaign.icp_titles or None,
        user_id=session.user_id,
    )
    _save_qualification_result(
        session, qualifier, lead_id, public_id, embedding, label, reason
    )
    return public_id


def _save_qualification_result(
    session,
    qualifier: BayesianQualifier,
    lead_id: str,
    public_id: str,
    embedding: np.ndarray,
    label: int,
    reason: str,
):
    # LLM rejections are tracked as FAILED Deals with "Disqualified" closing reason
    # (campaign-scoped), not as Lead.disqualified (permanent account-level exclusion).
    from openoutreach.core.db.deals import create_disqualified_deal
    from openoutreach.linkedin.db.leads import promote_lead_to_deal

    qualifier.update(embedding, label)

    if label == 1:
        try:
            deal = promote_lead_to_deal(session, public_id, reason=reason)
        except ValueError as e:
            logger.warning("Cannot promote %s: %s \u2014 disqualifying", public_id, e)
            create_disqualified_deal(session, public_id, reason=str(e))
            _log_qualification_action(session, lead_id, public_id, False, str(e))
            return
        logger.info(
            "%s %s: %s",
            public_id,
            colored("QUALIFIED", "green", attrs=["bold"]),
            reason,
        )
        _log_qualification_action(session, lead_id, public_id, True, reason)
        # Enrich at the QUALIFIED gate (only qualified leads ever reach here).
        # Tri-state: True = hit (proceed QUALIFIED), False = genuine miss (park
        # in NO_EMAIL, out of the connect pool), None = finder off/unreachable
        # (leave QUALIFIED to retry — a miss is free to re-attempt).
        from openoutreach.mongodb.models import Lead as LeadModel
        lead = LeadModel.get(deal.lead_id)
        if lead and lead.resolve_api_email() is False:
            from openoutreach.core.db.deals import set_profile_state
            from openoutreach.crm.models import DealState

            set_profile_state(
                session,
                public_id,
                DealState.NO_EMAIL.value,
                reason="No email found by finder",
            )
    else:
        create_disqualified_deal(session, public_id, reason=reason)
        _log_qualification_action(session, lead_id, public_id, False, reason)


def _log_qualification_action(session, lead_id: str, public_id: str, qualified: bool, reason: str):
    """Log qualification decision to activity feed."""
    from openoutreach.mongodb.models import Lead
    from openoutreach.linkedin.models import ActionLog

    lead = Lead.get(lead_id)
    lead_name = public_id
    if lead:
        try:
            prof = lead.get_profile(session)
            if prof and "profile" in prof:
                first = prof["profile"].get("firstName", "")
                last = prof["profile"].get("lastName", "")
                lead_name = f"{first} {last}".strip() or public_id
        except Exception:
            pass

    action_log = ActionLog(
        linkedin_profile_id=session.linkedin_profile.pk,
        campaign_id=session.campaign.pk,
        action_type="lead_qualified" if qualified else "lead_disqualified",
        details={
            "lead_name": lead_name,
            "public_identifier": public_id,
            "reason": reason,
        },
    )
    action_log.save()


def _fetch_profile_text(session, lead_id: str, public_id: str) -> str | None:
    from openoutreach.mongodb.models import Lead
    from openoutreach.linkedin.ml.profile_text import build_profile_text

    lead = Lead.get(lead_id)
    if not lead:
        return None
    profile_data = lead.get_profile(session)
    if not profile_data:
        return None
    return build_profile_text({"profile": profile_data})
