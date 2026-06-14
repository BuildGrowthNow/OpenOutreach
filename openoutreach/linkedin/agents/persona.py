"""
Lead Persona Generation Agent

Generates detailed lead personas using LLM analysis based on profile data and company context.
This persona lives alongside the Deal and is consumed by the follow-up agent for
hyper-personalized outreach.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from openoutreach.core.conf import PROMPTS_DIR
from openoutreach.core.llm import get_llm_model, run_agent_sync

if TYPE_CHECKING:
    from openoutreach.crm.models import Deal

logger = logging.getLogger(__name__)


class LeadPersonaOutput(BaseModel):
    """Structured output for lead persona generation."""

    pain_points: list[str] = Field(
        description="Top 5 predicted pain points for this lead based on their profile"
    )
    goals: list[str] = Field(
        description="Top 5 professional goals inferred from their career trajectory"
    )
    messaging_preferences: dict = Field(
        description="Messaging approach that would resonate with this lead. "
                    "Keys: tone (data-driven, visionary, practical, conversational), "
                    "formality (casual, professional, formal), "
                    "topics (list of resonant topics), "
                    "style (concise, detailed, storytelling)"
    )
    buy_signals: list[dict] = Field(
        description="Signals indicating readiness to buy. "
                    "Each signal has: signal_type, strength (low/medium/high), "
                    "source (profile, company, engagement), description"
    )
    confidence_score: float = Field(
        description="LLM confidence in this persona (0.0-1.0)"
    )
    recommendations: list[str] = Field(
        description="Specific outreach suggestions for this lead"
    )


def generate_lead_persona(session, deal: "Deal") -> LeadPersonaOutput | None:
    """
    Generate a detailed persona for a lead using LLM analysis.
    
    Context includes:
    - Full LinkedIn profile
    - Company information
    - Industry context
    - Campaign objective
    
    Args:
        session: The current LinkedIn session with API access
        deal: The Deal containing lead and campaign information
        
    Returns:
        LeadPersonaOutput with the generated persona or None if generation fails
    """
    from openoutreach.crm.models import Lead
    import jinja2
    
    # Fetch full profile from LinkedIn
    profile = deal.lead.get_profile(session)
    
    if not profile:
        logger.warning(f"Could not fetch profile for {deal.lead.public_identifier}")
        return None
    
    campaign = deal.campaign
    
    # Build context from profile data
    context = {
        "profile": profile,
        "product_docs": campaign.product_docs,
        "campaign_objective": campaign.campaign_objective,
    }
    
    # Render prompt from template
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(PROMPTS_DIR)))
    template = env.get_template("generate_persona.j2")
    prompt = template.render(**context)
    
    # Call LLM
    agent = Agent(
        get_llm_model(),
        output_type=LeadPersonaOutput,
        model_settings={"temperature": 0.7, "timeout": 60},
    )
    
    result = run_agent_sync(agent.run(prompt))
    
    if result.output is None:
        logger.error(f"LLM returned unparseable persona for {deal.lead.public_identifier}")
        return None
    
    return result.output


def save_persona(deal: "Deal", persona_output: LeadPersonaOutput) -> None:
    """Save persona to database.
    
    Args:
        deal: The Deal to associate the persona with
        persona_output: The generated persona data from LLM
    """
    from openoutreach.crm.models import LeadPersona
    
    persona, created = LeadPersona.objects.get_or_create(
        lead=deal.lead,
        campaign=deal.campaign,
        defaults={
            "pain_points": persona_output.pain_points,
            "goals": persona_output.goals,
            "messaging_preferences": persona_output.messaging_preferences,
            "buy_signals": persona_output.buy_signals,
            "confidence_score": persona_output.confidence_score,
            "recommendations": persona_output.recommendations,
            "version": 1,
        }
    )
    
    if not created:
        # Update existing persona (increment version)
        persona.pain_points = persona_output.pain_points
        persona.goals = persona_output.goals
        persona.messaging_preferences = persona_output.messaging_preferences
        persona.buy_signals = persona_output.buy_signals
        persona.confidence_score = persona_output.confidence_score
        persona.recommendations = persona_output.recommendations
        persona.version += 1
        persona.save(update_fields=[
            "pain_points", "goals", "messaging_preferences",
            "buy_signals", "confidence_score", "recommendations", "version"
        ])
    
    logger.info(
        f"Persona v{persona.version} saved for {deal.lead.public_identifier} "
        f"(confidence: {persona_output.confidence_score:.2f}, "
        f"pain_points: {len(persona_output.pain_points)}, "
        f"buy_signals: {len(persona_output.buy_signals)})"
    )


def get_lead_persona(deal: "Deal") -> LeadPersona | None:
    """Get the most recent persona for a deal.
    
    Args:
        deal: The Deal to get persona for
        
    Returns:
        The LeadPersona instance with highest version, or None if not generated
    """
    try:
        from openoutreach.crm.models import LeadPersona
        
        return LeadPersona.objects.filter(
            lead=deal.lead,
            campaign=deal.campaign
        ).latest('version')
    except LeadPersona.DoesNotExist:
        return None


def get_persona_text(deal: "Deal") -> str:
    """Format persona data for inclusion in agent prompts.
    
    Args:
        deal: The Deal to get persona for
        
    Returns:
        Formatted string representation of the persona
    """
    persona = get_lead_persona(deal)
    
    if not persona:
        return "(no persona generated yet)"
    
    lines = ["### LEAD PERSONA", ""]
    
    lines.append("**Pain Points:**")
    for point in persona.get_formatted_pain_points(3):
        lines.append(f"- {point}")
    lines.append("")
    
    lines.append("**Goals:**")
    for goal in persona.get_formatted_goals(3):
        lines.append(f"- {goal}")
    lines.append("")
    
    if persona.messaging_preferences:
        lines.append("**Messaging Preferences:**")
        for pref, value in persona.messaging_preferences.items():
            lines.append(f"- {pref}: {value}")
        lines.append("")
    
    if persona.buy_signals:
        lines.append("**Buy Signals:**")
        for signal_desc in persona.get_formatted_buy_signals(3):
            lines.append(f"- {signal_desc}")
        lines.append("")
    
    lines.append(f"**Persona Confidence:** {persona.confidence_score:.2f}")
    
    return "\n".join(lines)