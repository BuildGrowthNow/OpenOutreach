"""
Pydantic schemas for Campaign API endpoints.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class CampaignCreate(BaseModel):
    """Schema for creating a campaign."""
    name: str = Field(..., description="Campaign name", min_length=1, max_length=255)
    product_pitch: str = Field(..., description="Product/service pitch")
    campaign_objective: str = Field(..., description="Campaign objective/goal")
    booking_link: Optional[str] = Field(None, description="Calendar booking link")
    velocity: int = Field(default=20, ge=1, le=100, description="Actions per hour")
    cooldown_minutes: int = Field(default=0, ge=0, description="Cooldown between actions")
    icp_titles: Optional[List[str]] = Field(None, description="Ideal customer profile job titles")
    follow_up_strategy: Optional[str] = Field(None, description="Follow-up strategy")
    linkedin_profile_id: Optional[str] = Field(None, description="LinkedIn profile to use")
    target_degrees: Optional[List[int]] = Field(None, description="Target connection degrees (1, 2, 3)")


class CampaignUpdate(BaseModel):
    """Schema for updating a campaign (all fields optional)."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    product_pitch: Optional[str] = None
    campaign_objective: Optional[str] = None
    booking_link: Optional[str] = None
    is_paused: Optional[bool] = None
    velocity: Optional[int] = Field(None, ge=1, le=100)
    cooldown_minutes: Optional[int] = Field(None, ge=0)
    icp_titles: Optional[List[str]] = None
    follow_up_strategy: Optional[str] = None
    target_degrees: Optional[List[int]] = None


class CampaignResponse(BaseModel):
    """Schema for campaign responses."""
    id: str = Field(alias="_id", description="Campaign ID")
    name: str
    product_pitch: str
    campaign_objective: str
    booking_link: Optional[str] = None
    is_paused: bool
    velocity: int
    cooldown_minutes: int
    status: str = Field(default="draft", description="Campaign status")
    user_id: str = Field(..., description="Owner user ID")
    linkedin_profile_id: Optional[str] = None
    icp_titles: Optional[List[str]] = None
    follow_up_strategy: Optional[str] = None
    target_degrees: List[int] = Field(default_factory=lambda: [1, 2, 3])
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(populate_by_name=True)


class CampaignStats(BaseModel):
    """Schema for campaign statistics."""
    connections_sent: int = Field(default=0, description="Total connection requests sent")
    connections_accepted: int = Field(default=0, description="Total connections accepted")
    connection_accept_rate: float = Field(default=0.0, ge=0, le=1, description="Connection acceptance rate")
    messages_sent: int = Field(default=0, description="Total messages sent")
    messages_replied: int = Field(default=0, description="Total messages replied to")
    response_rate: float = Field(default=0.0, ge=0, le=1, description="Message response rate")
    deals_created: int = Field(default=0, description="Total deals created")
    deals_qualified: int = Field(default=0, description="Total deals qualified")
    deals_connected: int = Field(default=0, description="Total deals connected")
    deals_completed: int = Field(default=0, description="Total deals completed")


class CampaignWithStats(CampaignResponse):
    """Schema for campaign with embedded statistics."""
    stats: CampaignStats = Field(default_factory=CampaignStats)


class CampaignLeadUploadResponse(BaseModel):
    """Schema for CSV lead upload response."""
    added: int = Field(..., description="Number of leads added")
    campaign_id: str = Field(..., description="Campaign ID")
    errors: Optional[List[str]] = Field(None, description="Any errors during upload")


class CampaignAnalyticsResponse(BaseModel):
    """Schema for campaign analytics response."""
    campaign_id: str
    period: str = Field(..., description="Time period (7d, 30d, all)")
    connections_sent: int
    connections_accepted: int
    connection_accept_rate: float
    messages_sent: int
    messages_replied: int
    response_rate: float
    deals_by_state: Dict[str, int] = Field(..., description="Deal counts by state")
    recent_replies: List[Dict[str, Any]] = Field(default_factory=list, description="Recent message replies")
