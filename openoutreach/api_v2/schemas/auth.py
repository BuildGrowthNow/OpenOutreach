"""
Pydantic schemas for Auth API endpoints.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, EmailStr, field_validator


class RegisterRequest(BaseModel):
    """Schema for user registration."""
    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., min_length=8, description="User password (min 8 characters)")
    full_name: str = Field(..., min_length=1, max_length=100, description="Full name")
    intended_plan: Optional[str] = Field(
        None,
        description="Plan the user picked before signup (for example 'cloud')",
    )
    invite_token: Optional[str] = Field(
        None,
        max_length=256,
        description="Optional organization invite token from an invitation email",
    )

    @field_validator('intended_plan')
    @classmethod
    def validate_intended_plan(cls, v: Optional[str]) -> Optional[str]:
        """Only sellable, non-add-on plans may be stored as intent."""
        if v is None:
            return None
        allowed = {"starter", "pro", "business", "agency", "cloud", "lifetime", "team", "desktop"}
        normalized = v.strip().lower()
        if normalized not in allowed:
            raise ValueError('Unsupported intended plan')
        return normalized

    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Ensure password has minimum complexity."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v


class LoginRequest(BaseModel):
    """Schema for login request."""
    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., min_length=6, description="User password")


class TokenResponse(BaseModel):
    """Schema for JWT token response."""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    refresh_token: Optional[str] = Field(None, description="JWT refresh token")
    expires_in: int = Field(..., description="Token expiration in seconds")


class UserResponse(BaseModel):
    """Schema for user info response."""
    id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    full_name: str = Field(..., description="Full name")
    is_active: bool = Field(..., description="Whether user is active")
    created_at: datetime = Field(..., description="User creation timestamp")
    status: str = Field(default="active", description="User status (active/blocked/inactive)")
    admin_notes: Optional[str] = Field(None, description="Admin notes for the user")
    is_admin: bool = Field(default=False, description="Whether user has admin access")
    admin_role: Optional[str] = Field(None, description="Admin role (support/finance/superadmin)")
    org_id: Optional[str] = Field(None, description="Active organization ID")
    org_name: Optional[str] = Field(None, description="Active organization name")
    org_role: Optional[str] = Field(None, description="Role in the active organization")
    team_workspaces_enabled: bool = Field(
        default=False, description="Whether team workspaces are enabled"
    )

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


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


class DeletionScheduledResponse(BaseModel):
    """Schema for account deletion request response."""
    deletion_scheduled_at: str = Field(..., description="Timestamp when deletion was scheduled")
    grace_period_ends_at: str = Field(..., description="Timestamp when 30-day grace period ends")


class AccountStatusResponse(BaseModel):
    """Schema for account recovery response."""
    status: str = Field(..., description="Account status")
    subscription_status: str = Field(..., description="Subscription status")
    message: str = Field(..., description="Status message")


class EmailVerifyRequest(BaseModel):
    token: str = Field(..., description="Email verification token")
