"""
Deal Pydantic Schemas

Pydantic models for Deal validation, serialization, and API responses.
Corresponds to the MongoDB Deal model in openoutreach.mongodb.models.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class DealState:
    """Deal state constants matching MongoDB Deal.DealState."""
    QUALIFIED = "Qualified"
    READY_TO_CONNECT = "Ready to Connect"
    PENDING = "Pending"
    CONNECTED = "Connected"
    COMPLETED = "Completed"
    FAILED = "Failed"
    NO_EMAIL = "No Email"


class DealOutcome:
    """Deal outcome constants matching MongoDB Deal.Outcome."""
    CONVERTED = "converted"
    NOT_INTERESTED = "not_interested"
    WRONG_FIT = "wrong_fit"
    NO_BUDGET = "no_budget"
    HAS_SOLUTION = "has_solution"
    BAD_TIMING = "bad_timing"
    UNRESPONSIVE = "unresponsive"
    UNKNOWN = "unknown"


class DealResponse(BaseModel):
    """
    Deal response schema.

    Returned by GET endpoints for Deal retrieval.
    Includes all Deal fields from MongoDB.
    """
    id: str = Field(..., description="Deal unique identifier")
    lead_id: str = Field(..., description="Associated lead ID")
    campaign_id: str = Field(..., description="Associated campaign ID")
    user_id: Optional[str] = Field(None, description="Owner user ID")
    state: str = Field(
        default=DealState.QUALIFIED,
        description="Current deal state (Qualified, Ready to Connect, Pending, Connected, Completed, Failed, No Email)"
    )
    outcome: str = Field(default="", description="Deal outcome (converted, not_interested, wrong_fit, no_budget, has_solution, bad_timing, unresponsive, unknown)")
    reason: str = Field(default="", description="Reason for current state/outcome")
    connect_attempts: int = Field(default=0, ge=0, description="Number of connection attempts")
    backoff_hours: int = Field(default=0, ge=0, description="Backoff period in hours before next attempt")
    next_check_pending_at: Optional[datetime] = Field(None, description="When to check pending connection status")
    profile_summary: Dict[str, Any] = Field(default_factory=dict, description="Lead profile summary (mem0-style facts)")
    chat_summary: Dict[str, Any] = Field(default_factory=dict, description="Chat conversation summary (mem0-style facts)")
    creation_date: datetime = Field(..., description="Deal creation timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "lead_id": "660e8400-e29b-41d4-a716-446655440001",
                "campaign_id": "770e8400-e29b-41d4-a716-446655440002",
                "user_id": "880e8400-e29b-41d4-a716-446655440003",
                "state": "Connected",
                "outcome": "",
                "reason": "",
                "connect_attempts": 1,
                "backoff_hours": 0,
                "next_check_pending_at": None,
                "profile_summary": {"facts": ["Works at Acme Corp", "Director of Engineering"]},
                "chat_summary": {"facts": ["Interested in product demo", "Available next Tuesday"]},
                "creation_date": "2026-07-10T12:00:00Z"
            }
        }


class DealUpdate(BaseModel):
    """
    Deal update schema.

    Used for PATCH/PUT endpoints to update Deal fields.
    All fields are optional - only provided fields will be updated.
    """
    state: Optional[str] = Field(None, description="Update deal state")
    outcome: Optional[str] = Field(None, description="Update deal outcome")
    reason: Optional[str] = Field(None, description="Update reason for state/outcome")
    connect_attempts: Optional[int] = Field(None, ge=0, description="Update connection attempts count")
    backoff_hours: Optional[int] = Field(None, ge=0, description="Update backoff period in hours")
    next_check_pending_at: Optional[datetime] = Field(None, description="Update next pending check timestamp")
    profile_summary: Optional[Dict[str, Any]] = Field(None, description="Update profile summary")
    chat_summary: Optional[Dict[str, Any]] = Field(None, description="Update chat summary")

    class Config:
        json_schema_extra = {
            "example": {
                "state": "Connected",
                "outcome": "converted",
                "reason": "Completed onboarding call"
            }
        }


class DealStateUpdate(BaseModel):
    """
    Deal state transition schema.

    Used for state-specific endpoints (e.g., POST /deals/{id}/qualify).
    Minimal schema for common state transitions with optional reason.
    """
    state: str = Field(..., description="New deal state")
    reason: Optional[str] = Field(None, description="Reason for state transition")

    class Config:
        json_schema_extra = {
            "example": {
                "state": "Qualified",
                "reason": "Matches ICP criteria"
            }
        }
