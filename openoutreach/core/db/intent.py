# openoutreach/core/db/intent.py
"""LLM-based reply intent classification.

Labels each incoming message as one of:
  "interested"   - lead wants to learn more / buy / schedule a call
  "objection"    - pushback on price, timing, fit, but still engaging
  "wrong_person" - forwarded to wrong contact, or not the decision-maker
  "not_now"      - polite deferral (busy, on holiday, check back later)

Returns None when the LLM is unavailable or the content is too short to classify.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_INTENT_SYSTEM = """\
You are a sales-conversation classifier. Given one incoming reply from a prospect, \
classify their intent as exactly one of:
  interested   - positive signal, wants more info, ready to talk, asks questions
  objection    - raises a concern or pushback but still engaging
  wrong_person - message was forwarded or addressed to someone else
  not_now      - polite deferral, asks to reconnect later

Reply with ONLY the single label, no punctuation, no explanation."""

_INTENTS = {"interested", "objection", "wrong_person", "not_now"}


def classify_reply_intent(content: str, user_id: Optional[str] = None) -> Optional[str]:
    """Return intent label for an incoming message, or None on failure."""
    if not content or len(content.strip()) < 5:
        return None

    try:
        from pydantic_ai import Agent
        from openoutreach.core.llm import get_llm_model, run_agent_sync

        model = get_llm_model(user_id=user_id)
        agent: Agent[None, str] = Agent(
            model,
            output_type=str,
            model_settings={"temperature": 0.0, "timeout": 30},
            system_prompt=_INTENT_SYSTEM,
        )
        label = (run_agent_sync(agent.run(content.strip())).output or "").strip().lower().replace("-", "_")
        if label not in _INTENTS:
            logger.debug("Intent classifier returned unexpected label %r - discarding", label)
            return None
        return label
    except Exception as exc:
        logger.debug("Intent classification failed: %s", type(exc).__name__)
        return None
