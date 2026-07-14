"""
Link Pydantic Schemas

Pydantic models for TrackedLink validation, serialization, and API responses.
Corresponds to the MongoDB TrackedLink model in openoutreach.mongodb.models.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class LinkCreate(BaseModel):
    """
    Link creation schema.

    Used for POST endpoints to create new tracked links.
    Accepts all required fields for creating a TrackedLink.
    """
    campaign_id: Optional[str] = Field(None, description="Associated campaign ID")
    user_id: Optional[str] = Field(None, description="Creator user ID")
    original_url: str = Field(..., description="Original destination URL to track")
    short_code: str = Field(..., description="Unique short code for the link")
    is_active: bool = Field(default=True, description="Whether the link is active")
    utm_source: str = Field(default="", description="UTM source parameter")
    utm_medium: str = Field(default="", description="UTM medium parameter")
    utm_campaign: str = Field(default="", description="UTM campaign parameter")
    utm_term: str = Field(default="", description="UTM term parameter")
    utm_content: str = Field(default="", description="UTM content parameter")

    class Config:
        json_schema_extra = {
            "example": {
                "campaign_id": "770e8400-e29b-41d4-a716-446655440002",
                "user_id": "880e8400-e29b-41d4-a716-446655440003",
                "original_url": "https://example.com/landing-page",
                "short_code": "abc123",
                "is_active": True,
                "utm_source": "linkedin",
                "utm_medium": "social",
                "utm_campaign": "q3_outreach",
                "utm_term": "b2b_saas",
                "utm_content": "link1"
            }
        }


class LinkUpdate(BaseModel):
    """
    Link update schema.

    Used for PATCH/PUT endpoints to update TrackedLink fields.
    All fields are optional - only provided fields will be updated.
    """
    campaign_id: Optional[str] = Field(None, description="Update associated campaign ID")
    original_url: Optional[str] = Field(None, description="Update original destination URL")
    short_code: Optional[str] = Field(None, description="Update short code")
    is_active: Optional[bool] = Field(None, description="Update link active status")
    utm_source: Optional[str] = Field(None, description="Update UTM source parameter")
    utm_medium: Optional[str] = Field(None, description="Update UTM medium parameter")
    utm_campaign: Optional[str] = Field(None, description="Update UTM campaign parameter")
    utm_term: Optional[str] = Field(None, description="Update UTM term parameter")
    utm_content: Optional[str] = Field(None, description="Update UTM content parameter")
    total_clicks: Optional[int] = Field(None, ge=0, description="Update total clicks count")
    unique_clicks: Optional[int] = Field(None, ge=0, description="Update unique clicks count")
    last_clicked_at: Optional[datetime] = Field(None, description="Update last click timestamp")
    last_ip: Optional[str] = Field(None, description="Update last click IP address")
    last_user_agent: Optional[str] = Field(None, description="Update last click user agent")

    class Config:
        json_schema_extra = {
            "example": {
                "is_active": False,
                "utm_campaign": "q4_outreach"
            }
        }


class LinkResponse(BaseModel):
    """
    Link response schema.

    Returned by GET endpoints for TrackedLink retrieval.
    Includes all TrackedLink fields from MongoDB.
    """
    id: str = Field(..., description="Link unique identifier")
    campaign_id: Optional[str] = Field(None, description="Associated campaign ID")
    user_id: Optional[str] = Field(None, description="Creator user ID")
    original_url: str = Field(..., description="Original destination URL")
    short_code: str = Field(..., description="Unique short code for the link")
    is_active: bool = Field(default=True, description="Whether the link is active")
    utm_source: str = Field(default="", description="UTM source parameter")
    utm_medium: str = Field(default="", description="UTM medium parameter")
    utm_campaign: str = Field(default="", description="UTM campaign parameter")
    utm_term: str = Field(default="", description="UTM term parameter")
    utm_content: str = Field(default="", description="UTM content parameter")
    total_clicks: int = Field(default=0, ge=0, description="Total number of clicks")
    unique_clicks: int = Field(default=0, ge=0, description="Number of unique clicks")
    created_at: datetime = Field(..., description="Link creation timestamp")
    last_clicked_at: Optional[datetime] = Field(None, description="Last click timestamp")
    last_ip: Optional[str] = Field(None, description="Last click IP address")
    last_user_agent: str = Field(default="", description="Last click user agent string")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "campaign_id": "770e8400-e29b-41d4-a716-446655440002",
                "user_id": "880e8400-e29b-41d4-a716-446655440003",
                "original_url": "https://example.com/landing-page",
                "short_code": "abc123",
                "is_active": True,
                "utm_source": "linkedin",
                "utm_medium": "social",
                "utm_campaign": "q3_outreach",
                "utm_term": "b2b_saas",
                "utm_content": "link1",
                "total_clicks": 42,
                "unique_clicks": 38,
                "created_at": "2026-07-01T10:00:00Z",
                "last_clicked_at": "2026-07-10T14:30:00Z",
                "last_ip": "192.168.1.100",
                "last_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        }
