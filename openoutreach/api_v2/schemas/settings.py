"""
Settings Pydantic Schemas

Pydantic models for SiteConfig validation, serialization, and API responses.
Corresponds to the MongoDB SiteConfig model in openoutreach.mongodb.models.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


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
    finder_api_key: str = Field(default="", description="Email finder API key (BetterContact)")
    linkedin_username: str = Field(default="", description="LinkedIn username")
    linkedin_campaign: str = Field(default="", description="Default LinkedIn campaign")
    daily_connection_limit: int = Field(default=20, ge=0, description="Daily connection request limit")
    daily_follow_up_limit: int = Field(default=25, ge=0, description="Daily follow-up message limit")
    velocity: int = Field(default=20, ge=0, description="Actions per hour (manual mode)")
    cooldown_minutes: int = Field(default=0, ge=0, description="Cooldown between actions in minutes")
    bettercontact_api_key: str = Field(default="", description="BetterContact API key")
    contacts_api_token: str = Field(default="", description="Contacts API token")
    contacts_api_url: str = Field(default="", description="Contacts API URL")

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
    finder_api_key: Optional[str] = Field(None, description="Update email finder API key")
    linkedin_username: Optional[str] = Field(None, description="Update LinkedIn username")
    linkedin_campaign: Optional[str] = Field(None, description="Update default LinkedIn campaign")
    daily_connection_limit: Optional[int] = Field(None, ge=0, description="Update daily connection request limit")
    daily_follow_up_limit: Optional[int] = Field(None, ge=0, description="Update daily follow-up message limit")
    velocity: Optional[int] = Field(None, ge=0, description="Update actions per hour")
    cooldown_minutes: Optional[int] = Field(None, ge=0, description="Update cooldown in minutes")
    bettercontact_api_key: Optional[str] = Field(None, description="Update BetterContact API key")
    contacts_api_token: Optional[str] = Field(None, description="Update Contacts API token")
    contacts_api_url: Optional[str] = Field(None, description="Update Contacts API URL")

    class Config:
        json_schema_extra = {
            "example": {
                "llm_provider": "anthropic",
                "ai_model": "claude-3-opus-20240229",
                "daily_connection_limit": 30,
                "velocity": 25
            }
        }
