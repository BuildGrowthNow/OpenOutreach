"""
Pydantic schemas for LinkedIn-related API endpoints.

This module defines request and response models for LinkedIn profile
and credential management operations in the FastAPI v2 API.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field


class LinkedInProfileResponse(BaseModel):
    """
    Response schema for LinkedIn profile information.

    Represents a user's LinkedIn profile configuration including
    authentication credentials, rate limits, and activity status.
    """

    id: str = Field(..., description="Unique profile identifier (MongoDB _id)")
    user_id: str = Field(..., description="Reference to the Django User who owns this profile")
    linkedin_username: str = Field(..., description="LinkedIn account username/email")
    subscribe_newsletter: bool = Field(default=True, description="Newsletter subscription preference")
    active: bool = Field(default=True, description="Whether this profile is active")
    connect_daily_limit: int = Field(default=20, description="Daily connection request limit")
    follow_up_daily_limit: int = Field(default=25, description="Daily follow-up message limit")
    legal_accepted: bool = Field(default=False, description="Whether user accepted legal terms")
    cookie_data_encrypted: Optional[str] = Field(None, description="Encrypted browser cookie storage")
    newsletter_processed: bool = Field(default=False, description="Whether newsletter signup was processed")
    campaign_id: Optional[str] = Field(None, description="Associated campaign identifier")
    self_lead_id: Optional[str] = Field(None, description="Reference to the user's own lead profile")
    created_at: Optional[datetime] = Field(None, description="Profile creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last profile update timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "user_id": "507f1f77bcf86cd799439012",
                "linkedin_username": "user@example.com",
                "subscribe_newsletter": True,
                "active": True,
                "connect_daily_limit": 20,
                "follow_up_daily_limit": 25,
                "legal_accepted": True,
                "cookie_data_encrypted": "encrypted_base64_string...",
                "newsletter_processed": False,
                "campaign_id": "507f1f77bcf86cd799439013",
                "self_lead_id": None,
                "created_at": "2026-07-10T12:00:00Z",
                "updated_at": "2026-07-10T12:00:00Z"
            }
        }


class LinkedInCredentialCreate(BaseModel):
    """
    Request schema for creating LinkedIn credentials.

    Captures the minimum required fields to store encrypted LinkedIn
    login credentials for automated browser sessions.
    """

    email: str = Field(..., description="LinkedIn account email address", min_length=1)
    password: str = Field(..., description="LinkedIn account password", min_length=1)
    username: Optional[str] = Field(None, description="LinkedIn profile username (optional)")
    linkedin_profile_id: Optional[str] = Field(None, description="Associated LinkedIn profile ID")
    campaign_id: Optional[str] = Field(None, description="Associated campaign ID")
    is_primary: bool = Field(default=True, description="Whether this is the primary credential set")
    is_backup: bool = Field(default=False, description="Whether this is a backup credential set")
    backup_of_id: Optional[str] = Field(None, description="ID of the primary credential if this is a backup")
    rotation_required_days: int = Field(default=90, description="Days until credential rotation is required")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "SecurePassword123!",
                "username": "john-doe",
                "linkedin_profile_id": "507f1f77bcf86cd799439011",
                "campaign_id": "507f1f77bcf86cd799439013",
                "is_primary": True,
                "is_backup": False,
                "backup_of_id": None,
                "rotation_required_days": 90
            }
        }


class LinkedInCredentialResponse(BaseModel):
    """
    Response schema for LinkedIn credential information.

    Returns stored credential metadata with encrypted sensitive fields
    and audit tracking information. Password is never returned in responses.
    """

    id: str = Field(..., description="Unique credential identifier (MongoDB _id)")
    linkedin_profile_id: Optional[str] = Field(None, description="Associated LinkedIn profile ID")
    email_encrypted: str = Field(..., description="Encrypted LinkedIn email address")
    username: str = Field("", description="LinkedIn profile username (public identifier)")
    status: str = Field(default="active", description="Credential status (stored/tested/active/invalid/expired/locked/backup)")
    last_verified: Optional[datetime] = Field(None, description="Last successful verification timestamp")
    verification_failed_at: Optional[datetime] = Field(None, description="Last verification failure timestamp")
    verification_failures: int = Field(default=0, description="Number of consecutive verification failures")
    usage_count: int = Field(default=0, description="Number of times this credential has been used")
    last_used: Optional[datetime] = Field(None, description="Last usage timestamp")
    campaign_id: Optional[str] = Field(None, description="Associated campaign ID")
    user_id: Optional[str] = Field(None, description="Reference to the Django User who owns these credentials")
    created_at: datetime = Field(..., description="Credential creation timestamp")
    updated_at: datetime = Field(..., description="Last credential update timestamp")
    expires_at: Optional[datetime] = Field(None, description="Credential expiration timestamp")
    rotated_at: Optional[datetime] = Field(None, description="Last rotation timestamp")
    rotation_required_days: int = Field(default=90, description="Days until credential rotation is required")
    is_primary: bool = Field(default=True, description="Whether this is the primary credential set")
    is_backup: bool = Field(default=False, description="Whether this is a backup credential set")
    backup_of_id: Optional[str] = Field(None, description="ID of the primary credential if this is a backup")
    security_alert_sent_at: Optional[datetime] = Field(None, description="Last security alert notification timestamp")

    # Audit log entries (if included)
    logs: Optional[List[Dict[str, Any]]] = Field(None, description="Recent audit log entries")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439014",
                "linkedin_profile_id": "507f1f77bcf86cd799439011",
                "email_encrypted": "encrypted_base64_string...",
                "username": "john-doe",
                "status": "active",
                "last_verified": "2026-07-10T11:00:00Z",
                "verification_failed_at": None,
                "verification_failures": 0,
                "usage_count": 42,
                "last_used": "2026-07-10T10:30:00Z",
                "campaign_id": "507f1f77bcf86cd799439013",
                "user_id": "507f1f77bcf86cd799439012",
                "created_at": "2026-06-01T09:00:00Z",
                "updated_at": "2026-07-10T11:00:00Z",
                "expires_at": "2026-09-01T09:00:00Z",
                "rotated_at": None,
                "rotation_required_days": 90,
                "is_primary": True,
                "is_backup": False,
                "backup_of_id": None,
                "security_alert_sent_at": None,
                "logs": []
            }
        }


class LinkedInCredentialUpdate(BaseModel):
    """
    Request schema for updating LinkedIn credentials.

    Allows partial updates to credential fields. All fields are optional
    so clients can update only the fields they need to change.
    """

    email: Optional[str] = Field(None, description="New LinkedIn email address")
    password: Optional[str] = Field(None, description="New LinkedIn password")
    username: Optional[str] = Field(None, description="New LinkedIn username")
    status: Optional[str] = Field(None, description="New credential status")
    linkedin_profile_id: Optional[str] = Field(None, description="New LinkedIn profile association")
    campaign_id: Optional[str] = Field(None, description="New campaign association")
    is_primary: Optional[bool] = Field(None, description="Update primary status")
    is_backup: Optional[bool] = Field(None, description="Update backup status")
    rotation_required_days: Optional[int] = Field(None, description="Update rotation requirement")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "newemail@example.com",
                "password": "NewSecurePassword456!",
                "status": "active"
            }
        }


class LinkedInCredentialLogResponse(BaseModel):
    """
    Response schema for LinkedIn credential audit log entries.

    Tracks credential verification, usage, rotation, and security events.
    """

    id: str = Field(..., description="Unique log entry identifier")
    credential_id: str = Field(..., description="Associated credential ID")
    action: str = Field(..., description="Action type (verified/failed/locked/unlocked/rotated/backup/usage)")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional action details")
    ip_address: Optional[str] = Field(None, description="IP address where action occurred")
    user_agent: str = Field("", description="User agent string")
    created_at: datetime = Field(..., description="Log entry timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439015",
                "credential_id": "507f1f77bcf86cd799439014",
                "action": "verified",
                "details": {"status": "success", "method": "browser_login"},
                "ip_address": "192.168.1.100",
                "user_agent": "Mozilla/5.0...",
                "created_at": "2026-07-10T11:00:00Z"
            }
        }


class LinkedInProfileHealthResponse(BaseModel):
    """
    Response schema for LinkedIn profile health status.

    Provides aggregated health metrics and recommendations for
    profile performance and risk assessment.
    """

    profile_id: str = Field(..., description="LinkedIn profile identifier")
    overall_status: str = Field(..., description="Overall health status (healthy/warning/critical)")
    credential_status: str = Field(..., description="Credential verification status")
    last_active: Optional[datetime] = Field(None, description="Last successful activity timestamp")
    connection_rate: float = Field(0.0, description="Connection acceptance rate (0.0-1.0)")
    response_rate: float = Field(0.0, description="Message response rate (0.0-1.0)")
    daily_limit_usage: Dict[str, Dict[str, int]] = Field(
        default_factory=dict,
        description="Usage against daily limits by action type"
    )
    risk_score: float = Field(0.0, description="Detectability risk score (0.0-1.0)")
    recommendations: List[str] = Field(default_factory=list, description="Health improvement recommendations")
    alerts: List[Dict[str, Any]] = Field(default_factory=list, description="Active health alerts")

    class Config:
        json_schema_extra = {
            "example": {
                "profile_id": "507f1f77bcf86cd799439011",
                "overall_status": "healthy",
                "credential_status": "active",
                "last_active": "2026-07-10T10:30:00Z",
                "connection_rate": 0.45,
                "response_rate": 0.32,
                "daily_limit_usage": {
                    "connect": {"used": 8, "limit": 20},
                    "follow_up": {"used": 12, "limit": 25}
                },
                "risk_score": 0.15,
                "recommendations": [
                    "Consider reducing connection velocity during peak hours",
                    "Follow-up response rate is strong, maintain current cadence"
                ],
                "alerts": []
            }
        }
