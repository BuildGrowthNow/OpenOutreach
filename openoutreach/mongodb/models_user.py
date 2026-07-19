"""
User Model for Multi-Tenant MongoDB Auth

Production-ready User model with local auth + Supabase support.
Replaces SupabaseUser with proper multi-tenant User model.
"""

import logging
from datetime import datetime, timezone as tz
from typing import Any, Dict, Optional
from uuid import uuid4

import bcrypt

from .connection import get_mongodb_collection

logger = logging.getLogger(__name__)


class User:
    """
    Production MongoDB User model.

    Supports both local authentication and Supabase SSO.
    Designed for multi-tenant architecture with proper user isolation.
    """

    def __init__(
        self,
        _id: Optional[str] = None,
        email: str = "",
        hashed_password: Optional[str] = None,
        full_name: str = "",
        is_active: bool = True,
        is_superuser: bool = False,
        supabase_user_id: Optional[str] = None,
        org_id: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        last_login: Optional[datetime] = None,
        is_admin: bool = False,
        admin_role: Optional[str] = None,
        status: str = "active",
        stripe_customer_id: Optional[str] = None,
        stripe_subscription_id: Optional[str] = None,
        plan: str = "starter",
        billing_period: Optional[str] = None,
        subscription_status: str = "none",
        trial_ends_at: Optional[datetime] = None,
        current_period_end: Optional[datetime] = None,
        linkedin_account_limit: int = 1,
        campaign_limit: Optional[int] = None,
        cloud_profiles: int = 0,
    ):
        self._id = _id or str(uuid4())
        self.email = email.lower().strip()
        self.hashed_password = hashed_password
        self.full_name = full_name
        self.is_active = is_active
        self.is_superuser = is_superuser
        self.supabase_user_id = supabase_user_id
        self.org_id = org_id
        self.created_at = created_at or datetime.now(tz.utc)
        self.updated_at = updated_at or datetime.now(tz.utc)
        self.last_login = last_login
        self.is_admin = is_admin
        self.admin_role = admin_role
        self.status = status
        self.stripe_customer_id = stripe_customer_id
        self.stripe_subscription_id = stripe_subscription_id
        self.plan = plan
        self.billing_period = billing_period
        self.subscription_status = subscription_status
        self.trial_ends_at = trial_ends_at
        self.current_period_end = current_period_end
        self.linkedin_account_limit = linkedin_account_limit
        self.campaign_limit = campaign_limit
        self.cloud_profiles = cloud_profiles

    def to_dict(self) -> Dict[str, Any]:
        """Convert to MongoDB document."""
        return {
            "_id": self._id,
            "email": self.email,
            "hashed_password": self.hashed_password,
            "full_name": self.full_name,
            "is_active": self.is_active,
            "is_superuser": self.is_superuser,
            "supabase_user_id": self.supabase_user_id,
            "org_id": self.org_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_login": self.last_login,
            "is_admin": self.is_admin,
            "admin_role": self.admin_role,
            "status": self.status,
            "stripe_customer_id": self.stripe_customer_id,
            "stripe_subscription_id": self.stripe_subscription_id,
            "plan": self.plan,
            "billing_period": self.billing_period,
            "subscription_status": self.subscription_status,
            "trial_ends_at": self.trial_ends_at,
            "current_period_end": self.current_period_end,
            "linkedin_account_limit": self.linkedin_account_limit,
            "campaign_limit": self.campaign_limit,
            "cloud_profiles": self.cloud_profiles,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "User":
        """Create User from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            email=data.get("email", ""),
            hashed_password=data.get("hashed_password"),
            full_name=data.get("full_name", ""),
            is_active=data.get("is_active", True),
            is_superuser=data.get("is_superuser", False),
            supabase_user_id=data.get("supabase_user_id"),
            org_id=data.get("org_id"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            last_login=data.get("last_login"),
            is_admin=data.get("is_admin", False),
            admin_role=data.get("admin_role"),
            status=data.get("status", "active"),
            stripe_customer_id=data.get("stripe_customer_id"),
            stripe_subscription_id=data.get("stripe_subscription_id"),
            plan=data.get("plan", "starter"),
            billing_period=data.get("billing_period"),
            subscription_status=data.get("subscription_status", "none"),
            trial_ends_at=data.get("trial_ends_at"),
            current_period_end=data.get("current_period_end"),
            linkedin_account_limit=data.get("linkedin_account_limit", 1),
            campaign_limit=data.get("campaign_limit"),
            cloud_profiles=data.get("cloud_profiles", 0),
        )

    def save(self) -> str:
        """Save user to MongoDB."""
        collection = get_mongodb_collection("users")
        if collection is None:
            raise RuntimeError("MongoDB collection 'users' not available")

        self.updated_at = datetime.now(tz.utc)
        doc = self.to_dict()
        collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
        logger.info(f"Saved user: {self.email}")
        return self._id

    @classmethod
    def get(cls, user_id: str) -> Optional["User"]:
        """Get user by ID."""
        collection = get_mongodb_collection("users")
        if collection is None:
            return None

        data = collection.find_one({"_id": user_id})
        return cls.from_dict(data) if data else None

    @classmethod
    def get_by_email(cls, email: str) -> Optional["User"]:
        """Get user by email (case-insensitive)."""
        collection = get_mongodb_collection("users")
        if collection is None:
            return None

        data = collection.find_one({"email": email.lower().strip()})
        return cls.from_dict(data) if data else None

    @classmethod
    def get_by_supabase_id(cls, supabase_id: str) -> Optional["User"]:
        """Get user by Supabase user ID."""
        collection = get_mongodb_collection("users")
        if collection is None:
            return None

        data = collection.find_one({"supabase_user_id": supabase_id})
        return cls.from_dict(data) if data else None

    def verify_password(self, password: str) -> bool:
        """Verify password against hash."""
        if not self.hashed_password:
            return False
        return bcrypt.checkpw(password.encode(), self.hashed_password.encode())

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password."""
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    def set_password(self, password: str):
        """Set password (hashes automatically)."""
        self.hashed_password = self.hash_password(password)

    def update_last_login(self):
        """Update last login timestamp."""
        collection = get_mongodb_collection("users")
        if collection is not None:
            self.last_login = datetime.now(tz.utc)
            collection.update_one(
                {"_id": self._id},
                {"$set": {"last_login": self.last_login}}
            )
