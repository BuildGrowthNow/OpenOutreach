"""
LinkedIn credential validation - ensures account uniqueness and billing compliance.
Prevents multi-account abuse by enforcing global LinkedIn account uniqueness.
"""

import logging
from typing import Optional

from openoutreach.mongodb.connection import get_mongodb_collection

logger = logging.getLogger(__name__)


class LinkedInCredentialValidator:
    """Validates LinkedIn credentials against billing rules."""

    @staticmethod
    def is_linkedin_account_available(
        linkedin_username: str,
        exclude_user_id: Optional[str] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if a LinkedIn account is available (not connected to another user).

        Args:
            linkedin_username: The LinkedIn username/public identifier
            exclude_user_id: User ID to exclude (for update operations)

        Returns:
            (is_available, error_message)
        """
        collection = get_mongodb_collection("linkedin_profiles")
        if collection is None:
            logger.error("LinkedIn profiles collection not available")
            return False, "Service unavailable"

        if exclude_user_id:
            query = {
                "linkedin_username": linkedin_username,
                "user_id": {"$ne": exclude_user_id},
            }
        else:
            query = {"linkedin_username": linkedin_username}

        existing = collection.find_one(query)
        if existing:
            return False, (
                "This LinkedIn account is already connected to another OpenOutreach account. "
                "Each LinkedIn account can only be used once."
            )

        return True, None

    @staticmethod
    def validate_credential_for_user(
        user_id: str,
        linkedin_username: str,
    ) -> tuple[bool, Optional[str]]:
        """
        Validate credential creation/update for a user.

        Args:
            user_id: The user ID
            linkedin_username: The LinkedIn username

        Returns:
            (is_valid, error_message)
        """
        if not linkedin_username or not linkedin_username.strip():
            return False, "LinkedIn username is required"

        is_available, error = LinkedInCredentialValidator.is_linkedin_account_available(
            linkedin_username,
            exclude_user_id=user_id,
        )

        if not is_available:
            return False, error

        return True, None
