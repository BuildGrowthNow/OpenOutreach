"""
API v2 Pydantic Schemas

Pydantic models for request/response validation and serialization.
"""

from .auth import (
    LoginRequest,
    TokenResponse,
    UserResponse,
    PasswordResetRequest,
    PasswordResetConfirm,
    PasswordUpdate,
)
from .campaign import (
    CampaignCreate,
    CampaignUpdate,
    CampaignResponse,
    CampaignStats,
    CampaignWithStats,
    CampaignLeadUploadResponse,
    CampaignAnalyticsResponse,
)
from .deal import (
    DealResponse,
    DealUpdate,
    DealStateUpdate,
    DealState,
    DealOutcome,
)
from .lead import (
    LeadCreate,
    LeadUpdate,
    LeadResponse,
    LeadWithDeal,
)
from .link import (
    LinkCreate,
    LinkUpdate,
    LinkResponse,
)
from .linkedin import (
    LinkedInProfileResponse,
    LinkedInCredentialCreate,
    LinkedInCredentialResponse,
)
from .message import (
    MessageResponse,
    MessageCreate,
)
from .notification import (
    NotificationResponse,
    NotificationUpdate,
    NotificationSummaryResponse,
)
from .settings import (
    SiteConfigUpdate,
    SiteConfigResponse,
)

__all__ = [
    # Auth
    "LoginRequest",
    "TokenResponse",
    "UserResponse",
    "PasswordResetRequest",
    "PasswordResetConfirm",
    "PasswordUpdate",
    # Campaign
    "CampaignCreate",
    "CampaignUpdate",
    "CampaignResponse",
    "CampaignStats",
    "CampaignWithStats",
    "CampaignLeadUploadResponse",
    "CampaignAnalyticsResponse",
    # Deal
    "DealResponse",
    "DealUpdate",
    "DealStateUpdate",
    "DealState",
    "DealOutcome",
    # Lead
    "LeadCreate",
    "LeadUpdate",
    "LeadResponse",
    "LeadWithDeal",
    # Link
    "LinkCreate",
    "LinkUpdate",
    "LinkResponse",
    # LinkedIn
    "LinkedInProfileResponse",
    "LinkedInCredentialCreate",
    "LinkedInCredentialResponse",
    # Message
    "MessageResponse",
    "MessageCreate",
    # Notification
    "NotificationResponse",
    "NotificationUpdate",
    "NotificationSummaryResponse",
    # Settings
    "SiteConfigUpdate",
    "SiteConfigResponse",
]
