"""
User Model for Multi-Tenant MongoDB Auth
"""

import logging
from datetime import datetime, timedelta, timezone as tz
from typing import Any, Dict, Optional
from uuid import uuid4

import bcrypt

from .connection import get_mongodb_collection

logger = logging.getLogger(__name__)


class User:
    """
    Production MongoDB User model.

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
        whatsapp_account_limit: int = 1,
        campaign_limit: Optional[int] = None,
        cloud_profiles: int = 0,
        admin_notes: Optional[str] = None,
        is_deleted: bool = False,
        deleted_at: Optional[datetime] = None,
        deletion_scheduled_at: Optional[datetime] = None,
        referral_code: Optional[str] = None,
        referrer_id: Optional[str] = None,
        referral_credits_earned: int = 0,
        referral_credit_applied: bool = False,
        email_verified: bool = False,
        email_verification_token: Optional[str] = None,
        email_verification_expires: Optional[datetime] = None,
        password_reset_token: Optional[str] = None,
        password_reset_expires: Optional[datetime] = None,
        last_login_ip: Optional[str] = None,
        signup_ip: Optional[str] = None,
        trial_warning_sent_at: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.email = email.lower().strip()
        self.hashed_password = hashed_password
        self.full_name = full_name
        self.is_active = is_active
        self.is_superuser = is_superuser
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
        self.whatsapp_account_limit = whatsapp_account_limit
        self.campaign_limit = campaign_limit
        self.cloud_profiles = cloud_profiles
        self.admin_notes = admin_notes
        self.is_deleted = is_deleted
        self.deleted_at = deleted_at
        self.deletion_scheduled_at = deletion_scheduled_at
        self.referral_code = referral_code
        self.referrer_id = referrer_id
        self.referral_credits_earned = referral_credits_earned
        self.referral_credit_applied = referral_credit_applied
        self.email_verified = email_verified
        self.email_verification_token = email_verification_token
        self.email_verification_expires = email_verification_expires
        self.password_reset_token = password_reset_token
        self.password_reset_expires = password_reset_expires
        self.last_login_ip = last_login_ip
        self.signup_ip = signup_ip
        self.trial_warning_sent_at = trial_warning_sent_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert to MongoDB document."""
        doc: Dict[str, Any] = {
            "_id": self._id,
            "email": self.email,
            "hashed_password": self.hashed_password,
            "full_name": self.full_name,
            "is_active": self.is_active,
            "is_superuser": self.is_superuser,
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
            "whatsapp_account_limit": self.whatsapp_account_limit,
            "campaign_limit": self.campaign_limit,
            "cloud_profiles": self.cloud_profiles,
            "admin_notes": self.admin_notes,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at,
            "deletion_scheduled_at": self.deletion_scheduled_at,
            "referral_code": self.referral_code,
            "referrer_id": self.referrer_id,
            "referral_credits_earned": self.referral_credits_earned,
            "referral_credit_applied": self.referral_credit_applied,
            "email_verified": self.email_verified,
            "email_verification_token": self.email_verification_token,
            "email_verification_expires": self.email_verification_expires,
            "password_reset_token": self.password_reset_token,
            "password_reset_expires": self.password_reset_expires,
            "last_login_ip": self.last_login_ip,
            "signup_ip": self.signup_ip,
            "trial_warning_sent_at": self.trial_warning_sent_at,
        }
        return doc

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
            whatsapp_account_limit=data.get("whatsapp_account_limit", 1),
            campaign_limit=data.get("campaign_limit"),
            cloud_profiles=data.get("cloud_profiles", 0),
            admin_notes=data.get("admin_notes"),
            is_deleted=data.get("is_deleted", False),
            deleted_at=data.get("deleted_at"),
            deletion_scheduled_at=data.get("deletion_scheduled_at"),
            referral_code=data.get("referral_code"),
            referrer_id=data.get("referrer_id"),
            referral_credits_earned=data.get("referral_credits_earned", 0),
            referral_credit_applied=data.get("referral_credit_applied", False),
            email_verified=data.get("email_verified", False),
            email_verification_token=data.get("email_verification_token"),
            email_verification_expires=data.get("email_verification_expires"),
            password_reset_token=data.get("password_reset_token"),
            password_reset_expires=data.get("password_reset_expires"),
            last_login_ip=data.get("last_login_ip"),
            signup_ip=data.get("signup_ip"),
            trial_warning_sent_at=data.get("trial_warning_sent_at"),
        )

    def save(self) -> str:
        """Save user to MongoDB."""
        collection = get_mongodb_collection("users")
        if collection is None:
            raise RuntimeError("MongoDB collection 'users' not available")

        self.updated_at = datetime.now(tz.utc)
        doc = self.to_dict()
        update: Dict[str, Any] = {"$set": doc, "$unset": {"supabase_user_id": ""}}
        collection.update_one({"_id": self._id}, update, upsert=True)
        logger.info("Saved user")
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

    def update_last_login(self, ip: Optional[str] = None):
        """Update last login timestamp and optionally the login IP."""
        collection = get_mongodb_collection("users")
        if collection is not None:
            self.last_login = datetime.now(tz.utc)
            fields: Dict[str, Any] = {"last_login": self.last_login}
            if ip:
                self.last_login_ip = ip
                fields["last_login_ip"] = ip
            collection.update_one({"_id": self._id}, {"$set": fields})

    def schedule_deletion(self) -> datetime:
        """Schedule account for deletion (30-day soft delete window)."""
        self.deletion_scheduled_at = datetime.now(tz.utc)
        self.is_deleted = True
        self.save()
        logger.info("Account deletion scheduled")
        return self.deletion_scheduled_at

    def cancel_deletion(self):
        """Cancel scheduled deletion (user reactivates during grace period)."""
        self.deletion_scheduled_at = None
        self.is_deleted = False
        self.deleted_at = None
        self.save()
        logger.info("Account deletion canceled")

    def is_deletion_grace_period_expired(self) -> bool:
        """Check if 30-day deletion grace period has expired."""
        if not self.deletion_scheduled_at:
            return False
        grace_period_end = self.deletion_scheduled_at + timedelta(days=30)
        return datetime.now(tz.utc) >= grace_period_end

    def permanently_delete(self):
        """Permanently delete all user data."""
        collection = get_mongodb_collection("users")
        if collection is not None:
            collection.delete_one({"_id": self._id})
            logger.info("User permanently deleted")

    def soft_delete(self):
        """Soft delete - mark as deleted but retain data for 30 days."""
        self.is_deleted = True
        self.deleted_at = datetime.now(tz.utc)
        self.save()
        logger.info("User soft deleted")
