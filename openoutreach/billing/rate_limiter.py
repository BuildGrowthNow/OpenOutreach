"""
Rate limiting and anti-abuse protection for signup and account creation.
IP-based tracking of account creation attempts.
"""
import logging
from datetime import datetime, timedelta, timezone as tz

from openoutreach.mongodb.connection import get_mongodb_collection

logger = logging.getLogger(__name__)


class SignupRateLimiter:
    """IP-based rate limiter for account creation (3 accounts per IP per day)."""

    MAX_ACCOUNTS_PER_IP_PER_DAY = 3
    WINDOW_HOURS = 24

    @staticmethod
    def check_ip_limit(ip_address: str) -> tuple[bool, str | None]:
        """
        Check if IP can create another account.
        Returns (allowed, error_message).
        """
        collection = get_mongodb_collection("ip_signup_attempts")
        if collection is None:
            logger.warning("Could not check IP rate limit: collection not available")
            return True, None

        cutoff = datetime.now(tz.utc) - timedelta(hours=SignupRateLimiter.WINDOW_HOURS)

        count = collection.count_documents({
            "ip_address": ip_address,
            "created_at": {"$gte": cutoff},
        })

        if count >= SignupRateLimiter.MAX_ACCOUNTS_PER_IP_PER_DAY:
            return False, f"Too many signup attempts from this IP. Maximum {SignupRateLimiter.MAX_ACCOUNTS_PER_IP_PER_DAY} per day."

        return True, None

    @staticmethod
    def record_signup_attempt(ip_address: str, user_id: str, email: str) -> None:
        """Record a signup attempt from an IP."""
        collection = get_mongodb_collection("ip_signup_attempts")
        if collection is None:
            logger.warning("Could not record signup attempt: collection not available")
            return

        try:
            collection.insert_one({
                "ip_address": ip_address,
                "user_id": user_id,
                "email": email,
                "created_at": datetime.now(tz.utc),
            })
        except Exception as e:
            logger.error(f"Failed to record signup attempt for IP {ip_address}: {e}")


class LinkedInCredentialValidator:
    """Validates LinkedIn credentials and enforces uniqueness."""

    @staticmethod
    def validate_username_unique(linkedin_username: str, exclude_user_id: str | None = None) -> tuple[bool, str | None]:
        """
        Check if LinkedIn username is globally unique.
        Returns (is_unique, error_message).
        """
        if not linkedin_username or not linkedin_username.strip():
            return False, "LinkedIn username cannot be empty"

        collection = get_mongodb_collection("linkedin_profiles")
        if collection is None:
            return False, "Database error"

        query: dict = {"linkedin_username": linkedin_username.strip()}
        if exclude_user_id:
            query["user_id"] = {"$ne": exclude_user_id}

        existing = collection.find_one(query)
        if existing:
            return False, "This LinkedIn account is already connected to another OpenOutreach account"

        return True, None

    @staticmethod
    def validate_credentials_format(email: str, password: str) -> tuple[bool, str | None]:
        """
        Validate LinkedIn credential format.
        Returns (is_valid, error_message).
        """
        if not email or not email.strip():
            return False, "LinkedIn email cannot be empty"

        if "@" not in email:
            return False, "Invalid email format"

        if not password or len(password) < 6:
            return False, "LinkedIn password must be at least 6 characters"

        return True, None
