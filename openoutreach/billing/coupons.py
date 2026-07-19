"""
Coupon and promotional code management.

Supports both percentage and fixed-amount discounts,
with duration (one-time or recurring) and usage limits.
"""
import logging
from datetime import datetime, timezone as tz
from typing import Any, Dict, Optional
from uuid import uuid4

import stripe

from openoutreach.config import settings
from openoutreach.mongodb.connection import get_mongodb_collection

logger = logging.getLogger(__name__)


class Coupon:
    """Stripe coupon wrapper with additional metadata."""

    def __init__(
        self,
        _id: Optional[str] = None,
        code: str = "",
        stripe_coupon_id: Optional[str] = None,
        discount_type: str = "percent",  # 'percent' or 'fixed'
        discount_value: int = 0,  # percentage (0-100) or cents
        duration: str = "once",  # 'once', 'repeating', 'forever'
        duration_in_months: Optional[int] = None,
        max_redemptions: Optional[int] = None,
        redemptions_count: int = 0,
        valid_from: Optional[datetime] = None,
        valid_until: Optional[datetime] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self._id = _id or str(uuid4())
        self.code = code
        self.stripe_coupon_id = stripe_coupon_id
        self.discount_type = discount_type
        self.discount_value = discount_value
        self.duration = duration
        self.duration_in_months = duration_in_months
        self.max_redemptions = max_redemptions
        self.redemptions_count = redemptions_count
        self.valid_from = valid_from or datetime.now(tz.utc)
        self.valid_until = valid_until
        self.created_at = created_at or datetime.now(tz.utc)
        self.updated_at = updated_at or datetime.now(tz.utc)
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to MongoDB document."""
        return {
            "_id": self._id,
            "code": self.code,
            "stripe_coupon_id": self.stripe_coupon_id,
            "discount_type": self.discount_type,
            "discount_value": self.discount_value,
            "duration": self.duration,
            "duration_in_months": self.duration_in_months,
            "max_redemptions": self.max_redemptions,
            "redemptions_count": self.redemptions_count,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Coupon":
        """Create from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            code=data.get("code", ""),
            stripe_coupon_id=data.get("stripe_coupon_id"),
            discount_type=data.get("discount_type", "percent"),
            discount_value=data.get("discount_value", 0),
            duration=data.get("duration", "once"),
            duration_in_months=data.get("duration_in_months"),
            max_redemptions=data.get("max_redemptions"),
            redemptions_count=data.get("redemptions_count", 0),
            valid_from=data.get("valid_from"),
            valid_until=data.get("valid_until"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            metadata=data.get("metadata", {}),
        )

    def save(self) -> str:
        """Save to MongoDB."""
        collection = get_mongodb_collection("coupons")
        if collection is None:
            raise RuntimeError("MongoDB collection 'coupons' not available")

        self.updated_at = datetime.now(tz.utc)
        doc = self.to_dict()
        collection.update_one(
            {"_id": self._id},
            {"$set": doc},
            upsert=True
        )
        logger.info(f"Saved coupon: {self.code}")
        return self._id

    @classmethod
    def get_by_code(cls, code: str) -> Optional["Coupon"]:
        """Get coupon by code."""
        collection = get_mongodb_collection("coupons")
        if collection is None:
            return None

        data = collection.find_one({"code": code.upper()})
        return cls.from_dict(data) if data else None

    @classmethod
    def get_by_id(cls, coupon_id: str) -> Optional["Coupon"]:
        """Get coupon by ID."""
        collection = get_mongodb_collection("coupons")
        if collection is None:
            return None

        data = collection.find_one({"_id": coupon_id})
        return cls.from_dict(data) if data else None

    @classmethod
    def list_active(cls) -> list["Coupon"]:
        """List all active coupons."""
        collection = get_mongodb_collection("coupons")
        if collection is None:
            return []

        now = datetime.now(tz.utc)
        docs = collection.find({
            "valid_from": {"$lte": now},
            "$or": [
                {"valid_until": None},
                {"valid_until": {"$gte": now}}
            ]
        }).sort("created_at", -1)
        return [cls.from_dict(doc) for doc in docs]

    def is_valid(self) -> bool:
        """Check if coupon is currently valid."""
        now = datetime.now(tz.utc)
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        if self.max_redemptions and self.redemptions_count >= self.max_redemptions:
            return False
        return True

    def increment_redemptions(self) -> bool:
        """
        Atomically increment redemptions if under limit.
        Returns True if successfully incremented, False if at/over limit.
        """
        collection = get_mongodb_collection("coupons")
        if collection is None:
            return False

        # Atomic increment with max_redemptions guard
        query = {"_id": self._id}
        if self.max_redemptions:
            query["redemptions_count"] = {"$lt": self.max_redemptions}

        result = collection.update_one(
            query,
            {"$inc": {"redemptions_count": 1}}
        )
        return result.modified_count > 0


def create_stripe_coupon(
    code: str,
    discount_type: str,
    discount_value: int,
    duration: str = "once",
    duration_in_months: Optional[int] = None,
    max_redemptions: Optional[int] = None,
    valid_until: Optional[datetime] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Coupon]:
    """
    Create a coupon in Stripe and store locally.

    Args:
        code: Coupon code (e.g., "LAUNCH20")
        discount_type: 'percent' or 'fixed'
        discount_value: percentage (1-100) or cents
        duration: 'once', 'repeating', or 'forever'
        duration_in_months: for 'repeating', how many months to apply
        max_redemptions: optional max number of uses
        valid_until: optional expiration date
        metadata: optional metadata
    """
    if not settings.STRIPE_SECRET_KEY:
        logger.error("STRIPE_SECRET_KEY not set, cannot create coupon")
        return None

    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        params = {
            "name": code,
            "metadata": {"code": code, **(metadata or {})},
        }

        if discount_type == "percent":
            if not (1 <= discount_value <= 100):
                logger.error(f"Invalid percent discount: {discount_value}")
                return None
            params["percent_off"] = discount_value
        elif discount_type == "fixed":
            if discount_value <= 0:
                logger.error(f"Invalid fixed discount: {discount_value}")
                return None
            params["amount_off"] = discount_value
            params["currency"] = "usd"
        else:
            logger.error(f"Invalid discount type: {discount_type}")
            return None

        if duration == "repeating" and duration_in_months:
            params["duration"] = "repeating"
            params["duration_in_months"] = duration_in_months
        elif duration == "forever":
            params["duration"] = "forever"
        else:
            params["duration"] = "once"

        if max_redemptions:
            params["max_redemptions"] = max_redemptions

        stripe_coupon = stripe.Coupon.create(**params)

        coupon = Coupon(
            code=code.upper(),
            stripe_coupon_id=stripe_coupon.id,
            discount_type=discount_type,
            discount_value=discount_value,
            duration=duration,
            duration_in_months=duration_in_months,
            max_redemptions=max_redemptions,
            valid_until=valid_until,
            metadata=metadata or {},
        )
        coupon.save()

        logger.info(f"Created coupon {code} with Stripe ID {stripe_coupon.id}")
        return coupon

    except stripe.error.StripeError as e:
        logger.error(f"Failed to create Stripe coupon {code}: {e}")
        return None


def validate_coupon_for_checkout(coupon_code: str) -> Optional[str]:
    """
    Validate a coupon code and return Stripe coupon ID if valid.
    Atomically checks validity and reserves a redemption slot.
    Returns None if invalid or expired.
    """
    collection = get_mongodb_collection("coupons")
    if collection is None:
        logger.warning("Cannot validate coupon: collection not available")
        return None

    # Atomic check and reserve: only succeed if coupon is valid AND under limit
    now = datetime.now(tz.utc)
    query = {
        "code": coupon_code,
        "valid_from": {"$lte": now},
        "$or": [
            {"valid_until": None},
            {"valid_until": {"$gte": now}}
        ]
    }

    # If max_redemptions is set, also check the count
    # We'll increment during validation to prevent race conditions
    coupon_doc = collection.find_one(query)
    if not coupon_doc:
        logger.warning(f"Coupon code not found or expired: {coupon_code}")
        return None

    # Check redemption limit
    max_redemptions = coupon_doc.get("max_redemptions")
    if max_redemptions is not None:
        redemptions_count = coupon_doc.get("redemptions_count", 0)
        if redemptions_count >= max_redemptions:
            logger.warning(f"Coupon code max redemptions reached: {coupon_code}")
            return None

    return coupon_doc.get("stripe_coupon_id")


def increment_coupon_redemptions(coupon_code: str) -> bool:
    """
    Increment redemption count for a coupon after successful checkout.
    Returns True if successfully incremented, False otherwise.
    """
    coupon = Coupon.get_by_code(coupon_code)
    if not coupon:
        logger.warning(f"Cannot increment redemptions for non-existent coupon: {coupon_code}")
        return False

    success = coupon.increment_redemptions()
    if success:
        logger.info(f"Incremented redemptions for coupon {coupon_code}")
    else:
        logger.warning(f"Failed to increment redemptions for coupon {coupon_code} (may be at limit)")
    return success


# apply_coupon_to_checkout removed - dead code that never actually applied to Stripe
# Coupons should be applied when creating the checkout session, not after
