"""
Pydantic schemas for Auth API endpoints.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr


class LoginRequest(BaseModel):
    """Schema for login request."""
    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., min_length=6, description="User password")


class TokenResponse(BaseModel):
    """Schema for JWT token response."""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    refresh_token: Optional[str] = Field(None, description="JWT refresh token")
    expires_in: Optional[int] = Field(None, description="Token expiration in seconds")


class UserResponse(BaseModel):
    """Schema for user info response."""
    id: str = Field(alias="_id", description="User ID")
    email: str = Field(..., description="User email")
    full_name: str = Field(..., description="Full name")
    is_active: bool = Field(..., description="Whether user is active")
    supabase_user_id: Optional[str] = Field(None, description="Supabase user ID if linked")
    created_at: datetime = Field(..., description="User creation timestamp")

    class Config:
        populate_by_name = True


class PasswordResetRequest(BaseModel):
    """Schema for password reset request."""
    email: EmailStr = Field(..., description="User email for password reset")


class PasswordResetConfirm(BaseModel):
    """Schema for password reset confirmation."""
    token: str = Field(..., description="Password reset token")
    new_password: str = Field(..., min_length=6, description="New password")


class PasswordUpdate(BaseModel):
    """Schema for password update."""
    old_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=6, description="New password")


class SupabaseUserLink(BaseModel):
    """Schema for linking Supabase user."""
    supabase_user_id: str = Field(..., description="Supabase user ID")
    email: EmailStr = Field(..., description="User email")
    full_name: Optional[str] = Field(None, description="Full name")
