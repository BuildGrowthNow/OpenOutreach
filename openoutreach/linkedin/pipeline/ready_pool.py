# openoutreach/linkedin/pipeline/ready_pool.py
"""Ready-to-connect pool: GP confidence gate between QUALIFIED and READY_TO_CONNECT."""

from __future__ import annotations

import logging

import numpy as np

from openoutreach.core.db.deals import (
    get_qualified_profiles,
    get_ready_to_connect_profiles,
    set_profile_state,
)
from openoutreach.linkedin.ml.qualifier import BayesianQualifier
from openoutreach.crm.models import DealState

logger = logging.getLogger(__name__)


def promote_to_ready(session, qualifier: BayesianQualifier, threshold: float) -> int:
    """Promote QUALIFIED profiles above GP confidence threshold to READY_TO_CONNECT.

    When the GP model is not yet fitted (cold start — no labelled examples),
    all QUALIFIED leads are promoted directly so the campaign can start sending
    connections immediately rather than stalling forever waiting for training data.

    Returns the number of profiles promoted.
    """
    from openoutreach.mongodb.models import Lead

    profiles = get_qualified_profiles(session)
    if not profiles:
        return 0

    # Degree-1 leads are already connected — skip READY_TO_CONNECT entirely so
    # they don't burn a connect slot and go straight to the follow-up queue.
    first_degree = [p for p in profiles if p.get("connection_degree") == 1]
    for p in first_degree:
        pid = p.get("public_identifier", "?")
        logger.info("%s already 1st-degree — CONNECTED (no connect slot needed)", pid)
        set_profile_state(session, pid, DealState.CONNECTED.value)
    profiles = [p for p in profiles if p.get("connection_degree") != 1]

    if not profiles:
        return len(first_degree)

    # Cold-start: model has no labels yet — promote everything so connections start
    if not qualifier.is_fitted:
        promoted = len(first_degree)
        for p in profiles:
            pid = p.get("public_identifier", "?")
            logger.info("%s READY_TO_CONNECT (cold-start bypass)", pid)
            set_profile_state(
                session, pid, DealState.READY_TO_CONNECT.value
            )
            promoted += 1
        return promoted

    embeddings = []
    valid = []
    for p in profiles:
        lead = Lead.get(p.get("lead_id"))
        emb = lead.get_embedding(session) if lead else None
        if emb is not None:
            embeddings.append(emb)
            valid.append(p)

    if not valid:
        return len(first_degree)

    X = np.array(embeddings, dtype=np.float64)
    probs = qualifier.predict_probs(X)
    if probs is None:
        # predict_probs can still return None if fit failed — fall back to promote all
        promoted = len(first_degree)
        for p in profiles:
            pid = p.get("public_identifier", "?")
            logger.info("%s READY_TO_CONNECT (GP unavailable, promoting all)", pid)
            set_profile_state(
                session, pid, DealState.READY_TO_CONNECT.value
            )
            promoted += 1
        return promoted

    promoted = len(first_degree)
    for prob, p in zip(probs, valid):
        if prob > threshold:
            pid = p.get("public_identifier", "?")
            logger.info("%s READY_TO_CONNECT (P(f>0.5)=%.3f)", pid, prob)
            set_profile_state(
                session, p["public_identifier"], DealState.READY_TO_CONNECT.value
            )
            promoted += 1

    return promoted


def find_ready_candidate(session, qualifier: BayesianQualifier) -> dict | None:
    """Return the top-ranked READY_TO_CONNECT profile, or None."""
    profiles = get_ready_to_connect_profiles(session)
    if not profiles:
        return None

    ranked = qualifier.rank_profiles(profiles, session=session)
    return ranked[0] if ranked else None
