"""
Pydantic schemas for Notification endpoints
"""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Dict, Any
from datetime import datetime


class NotificationBase(BaseModel):
    """Base notification schema"""
    notification_type: str = Field(..., description="Type of notification")
    title: str = Field(..., description="Notification title")
    message: str = Field(..., description="Notification message")
    campaign_id: Optional[str] = Field(None, description="Related campaign ID")
    deal_id: Optional[str] = Field(None, description="Related deal ID")
    data: Dict[str, Any] = Field(default_factory=dict, description="Additional data")


class NotificationCreate(NotificationBase):
    """Schema for creating a notification"""
    recipient_id: str = Field(..., description="User ID of recipient")


class NotificationUpdate(BaseModel):
    """Schema for updating a notification"""
    is_read: Optional[bool] = Field(None, description="Read status")


class NotificationResponse(NotificationBase):
    """Schema for notification response"""
    id: str = Field(..., alias="_id", description="Notification ID")
    recipient_id: str = Field(..., description="User ID of recipient")
    is_read: bool = Field(..., description="Read status")
    read_at: Optional[datetime] = Field(None, description="When notification was read")
    created_at: datetime = Field(..., description="When notification was created")

    model_config = ConfigDict(populate_by_name=True)


class NotificationListResponse(BaseModel):
    """Schema for notification list response"""
    notifications: list[NotificationResponse]
    total: int
    unread_count: int


class NotificationSummaryResponse(BaseModel):
    """Schema for notification summary response"""
    unread_count: int
    recent_notifications: list[NotificationResponse]


class MarkAllReadResponse(BaseModel):
    """Schema for mark all read response"""
    marked_count: int
    message: str
