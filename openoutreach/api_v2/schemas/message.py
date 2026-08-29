"""
Message Pydantic Schemas

Pydantic models for Message validation, serialization, and API responses.
Corresponds to the MongoDB Message model in openoutreach.mongodb.models.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class MessageResponse(BaseModel):
    """
    Message response schema.

    Returned by GET endpoints for Message retrieval.
    Includes all Message fields from MongoDB.
    """
    id: str = Field(..., description="Message unique identifier")
    deal_id: str = Field(..., description="Associated deal ID")
    content: str = Field(..., description="Message content/body")
    is_outgoing: bool = Field(default=True, description="True if sent by user, False if received from lead")
    user_id: Optional[str] = Field(None, description="Author user ID (creator of the message)")
    created_at: datetime = Field(..., description="Message creation timestamp")

    model_config = ConfigDict(json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "deal_id": "660e8400-e29b-41d4-a716-446655440001",
                "content": "Hi, I'd love to connect and discuss how our solution can help your team.",
                "is_outgoing": True,
                "user_id": "880e8400-e29b-41d4-a716-446655440003",
                "created_at": "2026-07-10T12:00:00Z"
            }
        })


class MessageCreate(BaseModel):
    """
    Message creation schema.

    Used for POST endpoints to create new Message records.
    The id and created_at fields are auto-generated; user_id is typically
    set from authenticated context.
    """
    deal_id: str = Field(..., description="Associated deal ID (required)")
    content: str = Field(..., min_length=1, description="Message content/body (required, non-empty)")
    is_outgoing: bool = Field(default=True, description="True if sent by user, False if received from lead")
    user_id: Optional[str] = Field(None, description="Author user ID (optional, typically set from auth context)")

    model_config = ConfigDict(json_schema_extra={
            "example": {
                "deal_id": "660e8400-e29b-41d4-a716-446655440001",
                "content": "Thank you for your interest! Let's schedule a call.",
                "is_outgoing": True,
                "user_id": "880e8400-e29b-41d4-a716-446655440003"
            }
        })
