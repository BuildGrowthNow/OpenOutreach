"""
Billing models for subscription management.
"""
from datetime import datetime, timezone as tz
from typing import Any, Dict, Optional
from uuid import uuid4

from openoutreach.mongodb.connection import get_mongodb_collection

import logging

logger = logging.getLogger(__name__)


class StripePlan:
    """
    Stores Stripe product and price IDs for each plan.
    Single source of truth for plan ↔ Stripe mappings.
    """

    def __init__(
        self,
        _id: Optional[str] = None,
        plan_name: str = "",
        stripe_product_id: str = "",
        monthly_price_id: str = "",
        annual_price_id: str = "",
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.plan_name = plan_name
        self.stripe_product_id = stripe_product_id
        self.monthly_price_id = monthly_price_id
        self.annual_price_id = annual_price_id
        self.created_at = created_at or datetime.now(tz.utc)
        self.updated_at = updated_at or datetime.now(tz.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to MongoDB document."""
        return {
            "_id": self._id,
            "plan_name": self.plan_name,
            "stripe_product_id": self.stripe_product_id,
            "monthly_price_id": self.monthly_price_id,
            "annual_price_id": self.annual_price_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StripePlan":
        """Create from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            plan_name=data.get("plan_name", ""),
            stripe_product_id=data.get("stripe_product_id", ""),
            monthly_price_id=data.get("monthly_price_id", ""),
            annual_price_id=data.get("annual_price_id", ""),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    def save(self) -> str:
        """Save to MongoDB."""
        collection = get_mongodb_collection("stripe_plans")
        if collection is None:
            raise RuntimeError("MongoDB collection 'stripe_plans' not available")

        self.updated_at = datetime.now(tz.utc)
        doc = self.to_dict()
        collection.update_one(
            {"plan_name": self.plan_name},
            {"$set": doc},
            upsert=True
        )
        logger.info(f"Saved Stripe plan mapping: {self.plan_name}")
        return self._id

    @classmethod
    def get_by_plan(cls, plan_name: str) -> Optional["StripePlan"]:
        """Get Stripe plan mapping by plan name."""
        collection = get_mongodb_collection("stripe_plans")
        if collection is None:
            return None

        data = collection.find_one({"plan_name": plan_name})
        return cls.from_dict(data) if data else None

    @classmethod
    def get_all(cls) -> list["StripePlan"]:
        """Get all Stripe plan mappings."""
        collection = get_mongodb_collection("stripe_plans")
        if collection is None:
            return []

        docs = collection.find().sort("plan_name", 1)
        return [cls.from_dict(doc) for doc in docs]


class SiteConfig:
    """
    Global billing and platform configuration.
    Single instance per installation, stored in MongoDB.
    """

    def __init__(
        self,
        _id: str = "site_config",
        trial_duration_days: int = 3,
        lifetime_deal_enabled: bool = True,
        lifetime_deal_ends_at: Optional[datetime] = None,
        referral_program_enabled: bool = True,
        referral_trial_extension_days: int = 4,
        referral_credit_cents: int = 1900,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self._id = _id
        self.trial_duration_days = trial_duration_days
        self.lifetime_deal_enabled = lifetime_deal_enabled
        self.lifetime_deal_ends_at = lifetime_deal_ends_at
        self.referral_program_enabled = referral_program_enabled
        self.referral_trial_extension_days = referral_trial_extension_days
        self.referral_credit_cents = referral_credit_cents
        self.created_at = created_at or datetime.now(tz.utc)
        self.updated_at = updated_at or datetime.now(tz.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to MongoDB document."""
        return {
            "_id": self._id,
            "trial_duration_days": self.trial_duration_days,
            "lifetime_deal_enabled": self.lifetime_deal_enabled,
            "lifetime_deal_ends_at": self.lifetime_deal_ends_at,
            "referral_program_enabled": self.referral_program_enabled,
            "referral_trial_extension_days": self.referral_trial_extension_days,
            "referral_credit_cents": self.referral_credit_cents,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SiteConfig":
        """Create from MongoDB document."""
        return cls(
            _id=data.get("_id", "site_config"),
            trial_duration_days=data.get("trial_duration_days", 3),
            lifetime_deal_enabled=data.get("lifetime_deal_enabled", True),
            lifetime_deal_ends_at=data.get("lifetime_deal_ends_at"),
            referral_program_enabled=data.get("referral_program_enabled", True),
            referral_trial_extension_days=data.get("referral_trial_extension_days", 4),
            referral_credit_cents=data.get("referral_credit_cents", 1900),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    def save(self) -> str:
        """Save to MongoDB."""
        collection = get_mongodb_collection("site_config")
        if collection is None:
            raise RuntimeError("MongoDB collection 'site_config' not available")

        self.updated_at = datetime.now(tz.utc)
        doc = self.to_dict()
        collection.update_one(
            {"_id": self._id},
            {"$set": doc},
            upsert=True
        )
        logger.info("Saved SiteConfig")
        return self._id

    @classmethod
    def load(cls) -> "SiteConfig":
        """Load global config from MongoDB, create if not exists."""
        collection = get_mongodb_collection("site_config")
        if collection is None:
            logger.warning("MongoDB collection 'site_config' not available, using defaults")
            return cls()

        data = collection.find_one({"_id": "site_config"})
        if data:
            return cls.from_dict(data)

        config = cls()
        config.save()
        return config
