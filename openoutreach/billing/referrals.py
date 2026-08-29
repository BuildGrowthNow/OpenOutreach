"""
Referral program management for user growth.

Tracks referral relationships, generates unique referral codes,
and manages credit rewards for successful referrals.
"""
import logging
import secrets
import string
from datetime import datetime, timezone as tz
from typing import Any, Dict, Optional

from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.mongodb.models_user import User

logger = logging.getLogger(__name__)

REFERRAL_CREDIT_CENTS = 1900  # $19 credit for referrer


class ReferralCode:
    """Unique referral code for each user."""

    def __init__(
        self,
        _id: Optional[str] = None,
        user_id: str = "",
        code: str = "",
        created_at: Optional[datetime] = None,
        used_count: int = 0,
        credits_earned_cents: int = 0,
    ):
        self._id = _id or _generate_id()
        self.user_id = user_id
        self.code = code or _generate_code()
        self.created_at = created_at or datetime.now(tz.utc)
        self.used_count = used_count
        self.credits_earned_cents = credits_earned_cents

    def to_dict(self) -> Dict[str, Any]:
        """Convert to MongoDB document."""
        return {
            "_id": self._id,
            "user_id": self.user_id,
            "code": self.code,
            "created_at": self.created_at,
            "used_count": self.used_count,
            "credits_earned_cents": self.credits_earned_cents,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReferralCode":
        """Create from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            user_id=data.get("user_id", ""),
            code=data.get("code", ""),
            created_at=data.get("created_at"),
            used_count=data.get("used_count", 0),
            credits_earned_cents=data.get("credits_earned_cents", 0),
        )

    def save(self) -> str:
        """Save to MongoDB."""
        collection = get_mongodb_collection("referral_codes")
        if collection is None:
            raise RuntimeError("MongoDB collection 'referral_codes' not available")

        doc = self.to_dict()
        collection.update_one(
            {"_id": self._id},
            {"$set": doc},
            upsert=True
        )
        logger.info(f"Saved referral code: {self.code}")
        return self._id

    @classmethod
    def get_by_user_id(cls, user_id: str) -> Optional["ReferralCode"]:
        """Get referral code for a user (create if not exists)."""
        collection = get_mongodb_collection("referral_codes")
        if collection is None:
            return None

        existing = collection.find_one({"user_id": user_id})
        if existing:
            return cls.from_dict(existing)

        code = cls(user_id=user_id)
        code.save()
        return code

    @classmethod
    def get_by_code(cls, code: str) -> Optional["ReferralCode"]:
        """Get referral code by code string."""
        collection = get_mongodb_collection("referral_codes")
        if collection is None:
            return None

        data = collection.find_one({"code": code})
        return cls.from_dict(data) if data else None

    @classmethod
    def increment_usage(cls, code: str, credit_value_cents: int = REFERRAL_CREDIT_CENTS) -> bool:
        """Mark code as used and add credits."""
        collection = get_mongodb_collection("referral_codes")
        if collection is None:
            return False

        result = collection.update_one(
            {"code": code},
            {
                "$inc": {
                    "used_count": 1,
                    "credits_earned_cents": credit_value_cents
                }
            }
        )
        return result.modified_count > 0


def _generate_code() -> str:
    """Generate a unique referral code (uppercase alphanumeric, 8 chars)."""
    chars = string.ascii_uppercase + string.digits
    collection = get_mongodb_collection("referral_codes")

    if collection is None:
        logger.error("Cannot generate referral code: collection not available")
        raise RuntimeError("Database unavailable for referral code generation")

    for _ in range(20):
        code = "".join(secrets.choice(chars) for _ in range(8))
        if not collection.find_one({"code": code}):
            return code
    raise RuntimeError("Failed to generate unique referral code after 20 attempts")


def _generate_id() -> str:
    """Generate a unique ID."""
    return secrets.token_hex(12)


def create_referral_for_user(user: User) -> ReferralCode:
    """Create or retrieve referral code for a user."""
    code = ReferralCode.get_by_user_id(user._id)
    if code:
        return code

    code = ReferralCode(user_id=user._id)
    code.save()

    user.referral_code = code.code
    user.save()

    return code


def apply_referral_code(referred_user: User, referral_code: str) -> Optional[User]:
    """
    Apply a referral code to a referred user.
    Returns the referrer user if successful, None if code invalid or self-referral.
    """
    ref_code = ReferralCode.get_by_code(referral_code)
    if not ref_code:
        logger.warning(f"Invalid referral code: {referral_code}")
        return None

    referrer = User.get(ref_code.user_id)
    if not referrer:
        logger.warning(f"Referrer user not found: {ref_code.user_id}")
        return None

    # Prevent self-referral
    if referrer._id == referred_user._id:
        logger.warning("User attempted to apply their own referral code")
        return None

    referred_user.referrer_id = referrer._id
    referred_user.save()

    logger.info("Applied referral code")
    return referrer


def get_referral_dashboard(user: User) -> Dict[str, Any]:
    """Get referral dashboard data for a user."""
    code = ReferralCode.get_by_user_id(user._id)
    if not code:
        code = create_referral_for_user(user)

    credit_dollars = code.credits_earned_cents / 100.0

    return {
        "referral_code": code.code,
        "referral_link": f"https://openoutreach.app/signup?ref={code.code}",
        "referrals_count": code.used_count,
        "credits_earned": f"${credit_dollars:.2f}",
        "credits_earned_cents": code.credits_earned_cents,
    }
