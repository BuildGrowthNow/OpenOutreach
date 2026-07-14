"""
User Model for Multi-Tenant MongoDB Auth

Production-ready User model with local auth + Supabase support.
Replaces SupabaseUser with proper multi-tenant User model.
"""

import logging
from datetime import datetime, timezone as tz
from typing import Any, Dict, Optional
from uuid import uuid4

from passlib.context import CryptContext

from .connection import get_mongodb_collection

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


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
    ):
        self._id = _id or str(uuid4())
        self.email = email.lower().strip()  # Normalize email
        self.hashed_password = hashed_password
        self.full_name = full_name
        self.is_active = is_active
        self.is_superuser = is_superuser
        self.supabase_user_id = supabase_user_id
        self.org_id = org_id
        self.created_at = created_at or datetime.now(tz.utc)
        self.updated_at = updated_at or datetime.now(tz.utc)
        self.last_login = last_login

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
        )

    def save(self) -> str:
        """Save user to MongoDB."""
        collection = get_mongodb_collection("users")
        if not collection:
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
        if not collection:
            return None

        data = collection.find_one({"_id": user_id})
        return cls.from_dict(data) if data else None

    @classmethod
    def get_by_email(cls, email: str) -> Optional["User"]:
        """Get user by email (case-insensitive)."""
        collection = get_mongodb_collection("users")
        if not collection:
            return None

        data = collection.find_one({"email": email.lower().strip()})
        return cls.from_dict(data) if data else None

    @classmethod
    def get_by_supabase_id(cls, supabase_id: str) -> Optional["User"]:
        """Get user by Supabase user ID."""
        collection = get_mongodb_collection("users")
        if not collection:
            return None

        data = collection.find_one({"supabase_user_id": supabase_id})
        return cls.from_dict(data) if data else None

    def verify_password(self, password: str) -> bool:
        """Verify password against hash."""
        if not self.hashed_password:
            return False
        return pwd_context.verify(password, self.hashed_password)

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password."""
        return pwd_context.hash(password)

    def set_password(self, password: str):
        """Set password (hashes automatically)."""
        self.hashed_password = self.hash_password(password)

    def update_last_login(self):
        """Update last login timestamp."""
        collection = get_mongodb_collection("users")
        if collection:
            self.last_login = datetime.now(tz.utc)
            collection.update_one(
                {"_id": self._id},
                {"$set": {"last_login": self.last_login}}
            )
