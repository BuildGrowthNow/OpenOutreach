"""
LinkedIn Setup Router - Setup guide, cookie instructions, and status

Provides endpoints for onboarding users through LinkedIn credential setup,
returning guide content, cookie extraction instructions, and current setup status.
"""

import logging
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from openoutreach.api_v2.dependencies_v2 import get_current_user
from openoutreach.linkedin.models import LinkedInProfile
from openoutreach.mongodb.models import LinkedInCredentials

logger = logging.getLogger(__name__)
router = APIRouter()


# Response schemas
class SetupGuideResponse(BaseModel):
    """Response schema for setup guide."""
    steps: List[Dict[str, Any]]
    current_step: int
    completed: bool


class CookieInstructionsResponse(BaseModel):
    """Response schema for cookie extraction instructions."""
    method: str
    steps: List[str]
    extensions: List[Dict[str, str]]
    notes: List[str]


class SetupStatusResponse(BaseModel):
    """Response schema for setup status."""
    setup_complete: bool
    setup_progress: float
    linkedin_profile: Optional[Dict[str, Any]]
    linkedin_credentials: Optional[List[Dict[str, Any]]]
    missing_steps: List[str]


# Endpoints

@router.get("/guide", response_model=SetupGuideResponse)
async def get_setup_guide(
    user_id: str = Depends(get_current_user),
):
    """
    Get LinkedIn setup guide with steps.

    Returns structured onboarding steps and tracks current progress.
    """
    # Check current status
    profiles = LinkedInProfile.find_by_user_id(user_id)
    credentials_list = LinkedInCredentials.find_by_user_id(user_id)

    has_profile = len(profiles) > 0
    has_credentials = len(credentials_list) > 0
    has_verified = any(c.status == LinkedInCredentials.STATUS_ACTIVE for c in credentials_list)

    # Define setup steps
    steps = [
        {
            "step": 1,
            "title": "Create LinkedIn Profile",
            "description": "Set up your LinkedIn profile configuration",
            "completed": has_profile,
            "required": True,
        },
        {
            "step": 2,
            "title": "Add Credentials",
            "description": "Provide your LinkedIn email and password",
            "completed": has_credentials,
            "required": True,
        },
        {
            "step": 3,
            "title": "Verify Connection",
            "description": "Test your credentials with LinkedIn",
            "completed": has_verified,
            "required": True,
        },
        {
            "step": 4,
            "title": "Configure Settings",
            "description": "Set rate limits and active hours (optional)",
            "completed": False,
            "required": False,
        },
    ]

    # Determine current step
    current_step = 1
    if has_profile:
        current_step = 2
    if has_credentials:
        current_step = 3
    if has_verified:
        current_step = 4

    # Check if all required steps complete
    completed = has_profile and has_credentials and has_verified

    return SetupGuideResponse(
        steps=steps,
        current_step=current_step,
        completed=completed
    )


@router.get("/cookie-instructions", response_model=CookieInstructionsResponse)
async def get_cookie_instructions():
    """
    Get instructions for extracting LinkedIn cookies.

    Returns step-by-step guide for cookie extraction via browser DevTools.
    """
    return CookieInstructionsResponse(
        method="devtools",
        steps=[
            "1. Log into LinkedIn in your browser",
            "2. Open Developer Tools (F12 or Cmd+Option+I)",
            "3. Go to the 'Application' tab (Chrome) or 'Storage' tab (Firefox)",
            "4. In the left sidebar, expand 'Cookies' and select 'https://www.linkedin.com'",
            "5. Find the cookie named 'li_at' - this is your session token",
            "6. Copy the 'Value' of the 'li_at' cookie (it's a long string starting with 'AQE')",
            "7. Paste it into the session cookie field below",
        ],
        extensions=[
            {
                "name": "EditThisCookie",
                "chrome_url": "https://chrome.google.com/webstore/detail/editthiscookie/fngmhnnpilhplaeedifhccceomclgfbg",
                "firefox_url": "https://addons.mozilla.org/en-US/firefox/addon/editthiscookie/",
                "description": "Browser extension to view and edit cookies easily"
            },
            {
                "name": "Cookie-Editor",
                "chrome_url": "https://chrome.google.com/webstore/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm",
                "firefox_url": "https://addons.mozilla.org/en-US/firefox/addon/cookie-editor/",
                "description": "Another popular cookie management extension"
            }
        ],
        notes=[
            "The 'li_at' cookie is HttpOnly, so it cannot be accessed via JavaScript in the browser console",
            "You must use DevTools (Application/Storage tab) to view HttpOnly cookies",
            "Session cookies are optional - email/password authentication is the primary method",
            "Cookies expire after ~1 year, so you may need to refresh them periodically",
            "Never share your cookies or credentials with anyone"
        ]
    )


@router.get("/status")
async def get_setup_status(
    user_id: str = Depends(get_current_user),
):
    """
    Get current LinkedIn setup status.

    Returns profile, credentials, and completion metrics.
    """
    # Get user's profiles
    profiles = LinkedInProfile.find_by_user_id(user_id)
    credentials_list = LinkedInCredentials.find_by_user_id(user_id)

    # Calculate progress
    has_profile = len(profiles) > 0
    has_credentials = len(credentials_list) > 0
    has_verified = any(c.status == LinkedInCredentials.STATUS_ACTIVE for c in credentials_list)

    completed_steps = sum([has_profile, has_credentials, has_verified])
    total_steps = 3

    # Determine missing steps
    missing_steps = []
    if not has_profile:
        missing_steps.append("Create LinkedIn profile")
    if not has_credentials:
        missing_steps.append("Add LinkedIn credentials")
    if not has_verified:
        missing_steps.append("Verify credentials")

    setup_complete = len(missing_steps) == 0

    return {
        "status": {
            "linkedinProfile": {
                "exists": has_profile,
                "count": len(profiles),
                "requiresAttention": not has_verified and has_profile,
            },
            "linkedinCredentials": {
                "exists": has_credentials,
                "count": len(credentials_list),
                "activeCount": sum(1 for c in credentials_list if c.status == LinkedInCredentials.STATUS_ACTIVE),
                "requiresAttention": has_credentials and not has_verified,
            },
            "setupComplete": setup_complete,
            "setupProgress": {
                "current": completed_steps,
                "total": total_steps,
            },
        },
        "missingSteps": missing_steps,
    }
