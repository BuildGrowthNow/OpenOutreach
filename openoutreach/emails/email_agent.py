# openoutreach/emails/email_agent.py
"""LLM-powered email writer.

Renders email_agent.j2 with deal/campaign context, calls the LLM,
and returns (subject, body) as plain strings.
"""

from __future__ import annotations

import logging

import jinja2

from openoutreach.core.conf import PROMPTS_DIR
from openoutreach.core.llm import get_llm_model, run_agent_sync

logger = logging.getLogger(__name__)


def generate_email(deal, user_id: str, campaign, sequence_step: int) -> tuple[str, str]:
    """Return (subject, body) for the given deal and sequence step.

    Args:
        deal:           Deal model instance
        user_id:        Owner's user_id for LLM config lookup
        campaign:       Campaign model instance
        sequence_step:  0 = cold, 1 = first follow-up, 2 = second follow-up

    Raises:
        RuntimeError: LLM returned unparseable response
    """
    from openoutreach.mongodb.models import SiteConfig, Lead
    from pydantic_ai import Agent
    from pydantic import BaseModel

    class EmailOutput(BaseModel):
        subject: str
        body: str

    config = SiteConfig.load(user_id=user_id)
    lead = Lead.get(deal.lead_id)

    system_prompt = _render_prompt(
        deal=deal,
        campaign=campaign,
        config=config,
        seller_name=_seller_name(user_id),
        sequence_step=sequence_step,
    )

    agent = Agent(
        get_llm_model(user_id=user_id),
        output_type=EmailOutput,
        model_settings={"temperature": 0.7, "timeout": 60},
    )
    result = run_agent_sync(agent.run(system_prompt)).output
    if result is None:
        raise RuntimeError(
            f"LLM returned unparseable email response for deal {deal._id}"
        )

    logger.info(
        "email_agent: generated step=%d subject=%r lead=%s",
        sequence_step,
        result.subject,
        getattr(lead, "public_identifier", deal.lead_id) if lead else deal.lead_id,
    )
    return result.subject, result.body


def _render_prompt(deal, campaign, config, seller_name: str, sequence_step: int) -> str:
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(PROMPTS_DIR)))
    template = env.get_template("email_agent.j2")
    return template.render(
        seller_name=seller_name,
        product_pitch=campaign.product_pitch or "",
        campaign_objective=campaign.campaign_objective or "",
        booking_link=campaign.booking_link or "",
        profile_summary=_format_facts(deal.profile_summary),
        chat_summary=_format_facts(deal.chat_summary),
        sequence_step=sequence_step,
        ai_writing_style=config.ai_writing_style or "",
        ai_say_rules=config.ai_say_rules or "",
        ai_avoid_rules=config.ai_avoid_rules or "",
    )


def _format_facts(summary: dict | None) -> str:
    facts = (summary or {}).get("facts") or []
    if not facts:
        return "(none yet)"
    return "\n".join(f"- {f}" for f in facts)


def _seller_name(user_id: str) -> str:
    try:
        from openoutreach.mongodb.models_user import User
        user = User.get(user_id)
        if user:
            name = f"{getattr(user, 'first_name', '') or ''} {getattr(user, 'last_name', '') or ''}".strip()
            if name:
                return name
            email = getattr(user, "email", "") or ""
            return email.split("@")[0] if "@" in email else email
    except Exception:
        pass
    return "the team"
