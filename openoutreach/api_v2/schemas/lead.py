"""
Pydantic schemas for Lead API endpoints.

These schemas define the request/response models for lead-related operations
in the FastAPI v2 API, mapping to MongoDB Lead model fields.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class ChannelAvailability(BaseModel):
    """Per-lead channel availability flags."""
    linkedin: bool
    email: bool
    whatsapp: bool


class LeadCreate(BaseModel):
    """
    Schema for creating a new lead.

    A lead is a discovered person from LinkedIn with profile information.
    Required fields are linkedin_url and public_identifier for initial creation.
    """

    linkedin_url: str = Field(
        ...,
        description="LinkedIn profile URL of the lead",
        examples=["https://www.linkedin.com/in/johndoe/"]
    )
    public_identifier: str = Field(
        ...,
        description="LinkedIn public identifier (username) of the lead",
        examples=["johndoe"]
    )
    urn: Optional[str] = Field(
        None,
        description="LinkedIn URN identifier for the lead"
    )
    contact_info: Optional[Dict[str, Any]] = Field(
        None,
        description="Raw LinkedIn contact information (email, phone) from overlay"
    )
    api_email: Optional[str] = Field(
        None,
        description="Work email resolved via email enrichment waterfall"
    )
    disqualified: bool = Field(
        False,
        description="Permanent exclusion flag - disqualified leads never appear in any campaign"
    )
    user_id: Optional[str] = Field(
        None,
        description="ID of the User who created/owns this lead"
    )


class LeadUpdate(BaseModel):
    """
    Schema for updating an existing lead.

    All fields are optional - only provided fields will be updated.
    """

    linkedin_url: Optional[str] = Field(
        None,
        description="LinkedIn profile URL of the lead"
    )
    public_identifier: Optional[str] = Field(
        None,
        description="LinkedIn public identifier (username) of the lead"
    )
    urn: Optional[str] = Field(
        None,
        description="LinkedIn URN identifier for the lead"
    )
    contact_info: Optional[Dict[str, Any]] = Field(
        None,
        description="Raw LinkedIn contact information (email, phone) from overlay"
    )
    api_email: Optional[str] = Field(
        None,
        description="Work email resolved via enrichment API"
    )
    disqualified: Optional[bool] = Field(
        None,
        description="Permanent exclusion flag"
    )


class LeadResponse(BaseModel):
    """
    Schema for lead API responses.

    Returns all lead fields including system-managed fields like ID and timestamps.
    """

    id: str = Field(
        ...,
        alias="_id",
        description="Unique MongoDB identifier for the lead"
    )
    linkedin_url: str = Field(
        ...,
        description="LinkedIn profile URL of the lead"
    )
    public_identifier: str = Field(
        ...,
        description="LinkedIn public identifier (username) of the lead"
    )
    urn: Optional[str] = Field(
        None,
        description="LinkedIn URN identifier for the lead"
    )
    embedding: Optional[bytes] = Field(
        None,
        description="384-dim embedding vector (lazily computed from profile)"
    )
    contact_info: Optional[Dict[str, Any]] = Field(
        None,
        description="Raw LinkedIn contact information (email, phone) from overlay"
    )
    api_email: Optional[str] = Field(
        None,
        description="Work email resolved via enrichment API"
    )
    disqualified: bool = Field(
        False,
        description="Permanent exclusion flag - disqualified leads never appear in any campaign"
    )
    user_id: Optional[str] = Field(
        None,
        description="ID of the User who created/owns this lead"
    )
    phone: str = Field(
        "",
        description="Phone number of the lead"
    )
    channel_availability: Optional[ChannelAvailability] = Field(
        None,
        description="Per-channel availability flags based on lead data"
    )
    creation_date: datetime = Field(
        ...,
        description="Timestamp when the lead was first discovered/created"
    )

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "_id": "550e8400-e29b-41d4-a716-446655440000",
                "linkedin_url": "https://www.linkedin.com/in/johndoe/",
                "public_identifier": "johndoe",
                "urn": "urn:li:fs_miniProfile:ACoAABhCDEFGHIJKLMNOPQ",
                "embedding": None,
                "contact_info": {
                    "email": "john.doe@example.com",
                    "phone": "+1-555-123-4567"
                },
                "api_email": "john.doe@company.com",
                "disqualified": False,
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "creation_date": "2026-07-10T12:34:56.789Z"
            }
        },
    )


class LeadWithDeal(LeadResponse):
    """
    Schema for lead with associated deal information.

    Extends LeadResponse to include the lead's deal relationship with a campaign.
    Used in endpoints that need to show both lead and deal state together.
    """

    deal_id: Optional[str] = Field(
        None,
        description="ID of the associated Deal linking this lead to a campaign"
    )
    deal_state: Optional[str] = Field(
        None,
        description="Current state of the deal (DISCOVERED, QUALIFIED, PENDING, etc.)"
    )
    deal_outcome: Optional[str] = Field(
        None,
        description="Outcome of the deal (converted, not_interested, wrong_fit, etc.)"
    )
    campaign_id: Optional[str] = Field(
        None,
        description="ID of the campaign this lead-deal relationship belongs to"
    )

    model_config = ConfigDict(json_schema_extra={
            "example": {
                "_id": "550e8400-e29b-41d4-a716-446655440000",
                "linkedin_url": "https://www.linkedin.com/in/johndoe/",
                "public_identifier": "johndoe",
                "urn": "urn:li:fs_miniProfile:ACoAABhCDEFGHIJKLMNOPQ",
                "contact_info": {
                    "email": "john.doe@example.com"
                },
                "api_email": "john.doe@company.com",
                "disqualified": False,
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "creation_date": "2026-07-10T12:34:56.789Z",
                "deal_id": "660e8400-e29b-41d4-a716-446655440001",
                "deal_state": "QUALIFIED",
                "deal_outcome": "",
                "campaign_id": "770e8400-e29b-41d4-a716-446655440002"
            }
        })
