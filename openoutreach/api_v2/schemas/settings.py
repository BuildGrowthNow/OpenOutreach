"""
Settings Pydantic Schemas

Pydantic models for SiteConfig validation, serialization, and API responses.
Corresponds to the MongoDB SiteConfig model in openoutreach.mongodb.models.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field, model_validator


class SiteConfigResponse(BaseModel):
    """
    Site configuration response schema.

    Returned by GET endpoints for SiteConfig retrieval.
    Includes all SiteConfig fields from MongoDB.
    """
    id: str = Field(..., description="SiteConfig unique identifier")
    llm_provider: str = Field(default="", description="LLM provider (openai, anthropic, google, groq, mistral, cohere, openai_compatible)")
    llm_api_key: str = Field(default="", description="LLM API key (encrypted)")
    ai_model: str = Field(default="", description="AI model identifier")
    llm_api_base: str = Field(default="", description="LLM API base URL (for openai_compatible provider)")
    ai_writing_style: str = Field(default="", description="AI writing style guidelines")
    ai_say_rules: str = Field(default="", description="Phrases the AI should emphasize")
    ai_avoid_rules: str = Field(default="", description="Phrases/promises the AI should avoid")
    finder_api_key: str = Field(default="", description="Email finder API key (BetterContact)")
    linkedin_username: str = Field(default="", description="LinkedIn username")
    linkedin_campaign: str = Field(default="", description="Default LinkedIn campaign")
    enable_smart_rate_limiting: bool = Field(default=False, description="Enable smart rate limiting")
    aggressiveness_preset: str = Field(default="average", description="Rate limiting aggressiveness preset (very_slow, slow, average, aggressive, very_aggressive)")
    daily_connection_limit: int = Field(default=20, ge=0, description="Daily connection request limit")
    daily_follow_up_limit: int = Field(default=40, ge=0, description="Daily follow-up message limit")
    velocity: int = Field(default=20, ge=0, description="Actions per hour (manual mode)")
    cooldown_minutes: int = Field(default=0, ge=0, description="Cooldown between actions in minutes")
    enable_active_hours: bool = Field(default=False, description="Enable active hours restriction")
    active_start_hour: int = Field(default=9, ge=0, le=23, description="Active hours start (0-23)")
    active_end_hour: int = Field(default=18, ge=0, le=23, description="Active hours end (0-23)")
    active_timezone: str = Field(default="UTC", description="Timezone for active hours")
    active_days: str = Field(default="1,2,3,4,5", description="Comma-separated day numbers (1=Monday, 7=Sunday)")
    bettercontact_api_key: str = Field(default="", description="BetterContact API key")
    contacts_api_token: str = Field(default="", description="Contacts API token")
    contacts_api_url: str = Field(default="", description="Contacts API URL")
    wa_daily_limit: int = Field(default=20, ge=0, description="WhatsApp daily message limit")
    wa_enable_active_hours: bool = Field(default=False, description="Enable WhatsApp-specific active hours")
    wa_active_start_hour: int = Field(default=8, ge=0, le=23, description="WhatsApp active hours start (0-23)")
    wa_active_end_hour: int = Field(default=21, ge=0, le=23, description="WhatsApp active hours end (0-23)")
    wa_active_days: str = Field(default="1,2,3,4,5,6,7", description="Comma-separated active days for WhatsApp (1=Monday, 7=Sunday)")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "llm_provider": "openai",
                "llm_api_key": "sk-***",
                "ai_model": "gpt-4",
                "llm_api_base": "",
                "finder_api_key": "finder-***",
                "linkedin_username": "john.doe",
                "linkedin_campaign": "outreach_2026",
                "daily_connection_limit": 20,
                "daily_follow_up_limit": 25,
                "velocity": 20,
                "cooldown_minutes": 0,
                "bettercontact_api_key": "bc-***",
                "contacts_api_token": "ct-***",
                "contacts_api_url": "https://contacts.api.example.com"
            }
        }


class SiteConfigUpdate(BaseModel):
    """
    Site configuration update schema.

    Used for PATCH/PUT endpoints to update SiteConfig fields.
    All fields are optional - only provided fields will be updated.
    """
    llm_provider: Optional[str] = Field(None, description="Update LLM provider")
    llm_api_key: Optional[str] = Field(None, description="Update LLM API key")
    ai_model: Optional[str] = Field(None, description="Update AI model identifier")
    llm_api_base: Optional[str] = Field(None, description="Update LLM API base URL")
    ai_writing_style: Optional[str] = Field(None, description="Update AI writing style guidelines")
    ai_say_rules: Optional[str] = Field(None, description="Update phrases the AI should emphasize")
    ai_avoid_rules: Optional[str] = Field(None, description="Update phrases/promises the AI should avoid")
    finder_api_key: Optional[str] = Field(None, description="Update email finder API key")
    linkedin_username: Optional[str] = Field(None, description="Update LinkedIn username")
    linkedin_campaign: Optional[str] = Field(None, description="Update default LinkedIn campaign")
    enable_smart_rate_limiting: Optional[bool] = Field(None, description="Update smart rate limiting toggle")
    aggressiveness_preset: Optional[str] = Field(None, description="Update rate limiting aggressiveness preset")
    daily_connection_limit: Optional[int] = Field(None, ge=0, description="Update daily connection request limit")
    daily_follow_up_limit: Optional[int] = Field(None, ge=0, description="Update daily follow-up message limit")
    velocity: Optional[int] = Field(None, ge=0, description="Update actions per hour")
    cooldown_minutes: Optional[int] = Field(None, ge=0, description="Update cooldown in minutes")
    enable_active_hours: Optional[bool] = Field(None, description="Update active hours toggle")
    active_start_hour: Optional[int] = Field(None, ge=0, le=23, description="Update active hours start")
    active_end_hour: Optional[int] = Field(None, ge=0, le=23, description="Update active hours end")
    active_timezone: Optional[str] = Field(None, description="Update timezone for active hours")
    active_days: Optional[str] = Field(None, description="Update comma-separated day numbers")
    bettercontact_api_key: Optional[str] = Field(None, description="Update BetterContact API key")
    contacts_api_token: Optional[str] = Field(None, description="Update Contacts API token")
    contacts_api_url: Optional[str] = Field(None, description="Update Contacts API URL")
    wa_daily_limit: Optional[int] = Field(None, ge=0, description="Update WhatsApp daily message limit")
    wa_enable_active_hours: Optional[bool] = Field(None, description="Update WhatsApp active hours toggle")
    wa_active_start_hour: Optional[int] = Field(None, ge=0, le=23, description="Update WhatsApp active hours start")
    wa_active_end_hour: Optional[int] = Field(None, ge=0, le=23, description="Update WhatsApp active hours end")
    wa_active_days: Optional[str] = Field(None, description="Update WhatsApp active days (comma-separated)")

    @model_validator(mode="before")
    @classmethod
    def _flatten_nested(cls, data: Any) -> Any:
        """Accept the nested camelCase body the frontend sends and flatten it.

        Frontend sends: { llm: { provider, model, apiKey, apiBase, ... },
                          rateLimits: { ... }, activeHours: { ... } }
        Schema expects: flat snake_case fields.
        """
        if not isinstance(data, dict):
            return data

        # llm sub-object
        llm = data.pop("llm", None) or {}
        if llm.get("provider") is not None:
            data.setdefault("llm_provider", llm["provider"])
        if llm.get("apiKey") is not None:
            data.setdefault("llm_api_key", llm["apiKey"])
        if llm.get("model") is not None:
            data.setdefault("ai_model", llm["model"])
        if llm.get("apiBase") is not None:
            data.setdefault("llm_api_base", llm["apiBase"])
        if llm.get("writingStyle") is not None:
            data.setdefault("ai_writing_style", llm["writingStyle"])
        if llm.get("sayRules") is not None:
            data.setdefault("ai_say_rules", llm["sayRules"])
        if llm.get("avoidRules") is not None:
            data.setdefault("ai_avoid_rules", llm["avoidRules"])

        # rateLimits sub-object
        rl = data.pop("rateLimits", None) or {}
        if rl.get("enableSmartRateLimiting") is not None:
            data.setdefault("enable_smart_rate_limiting", rl["enableSmartRateLimiting"])
        if rl.get("aggressivenessPreset") is not None:
            data.setdefault("aggressiveness_preset", rl["aggressivenessPreset"])
        if rl.get("dailyConnectionLimit") is not None:
            data.setdefault("daily_connection_limit", rl["dailyConnectionLimit"])
        if rl.get("dailyFollowUpLimit") is not None:
            data.setdefault("daily_follow_up_limit", rl["dailyFollowUpLimit"])
        if rl.get("velocity") is not None:
            data.setdefault("velocity", rl["velocity"])
        if rl.get("cooldownMinutes") is not None:
            data.setdefault("cooldown_minutes", rl["cooldownMinutes"])

        # activeHours sub-object
        ah = data.pop("activeHours", None) or {}
        if ah.get("enableActiveHours") is not None:
            data.setdefault("enable_active_hours", ah["enableActiveHours"])
        if ah.get("activeStartHour") is not None:
            data.setdefault("active_start_hour", ah["activeStartHour"])
        if ah.get("activeEndHour") is not None:
            data.setdefault("active_end_hour", ah["activeEndHour"])
        if ah.get("activeTimezone") is not None:
            data.setdefault("active_timezone", ah["activeTimezone"])
        if ah.get("activeDays") is not None:
            data.setdefault("active_days", ah["activeDays"])

        # linkedinProfile sub-object
        lp = data.pop("linkedinProfile", None) or {}
        if lp.get("username") is not None:
            data.setdefault("linkedin_username", lp["username"])
        if lp.get("campaign") is not None:
            data.setdefault("linkedin_campaign", lp["campaign"])

        # whatsapp sub-object
        wa = data.pop("whatsapp", None) or {}
        if wa.get("dailyLimit") is not None:
            data.setdefault("wa_daily_limit", wa["dailyLimit"])
        if wa.get("enableActiveHours") is not None:
            data.setdefault("wa_enable_active_hours", wa["enableActiveHours"])
        if wa.get("activeStartHour") is not None:
            data.setdefault("wa_active_start_hour", wa["activeStartHour"])
        if wa.get("activeEndHour") is not None:
            data.setdefault("wa_active_end_hour", wa["activeEndHour"])
        if wa.get("activeDays") is not None:
            data.setdefault("wa_active_days", wa["activeDays"])

        return data

    class Config:
        json_schema_extra = {
            "example": {
                "llm_provider": "anthropic",
                "ai_model": "claude-3-opus-20240229",
                "daily_connection_limit": 30,
                "velocity": 25
            }
        }
