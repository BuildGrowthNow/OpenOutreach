"""Organization, membership, and invite models (Phase 3A).

Organizations own billing, seats, members, and the profiles assigned to those
members. A personal organization is created for every user and can later be
shared by inviting members. All timestamps are stored in UTC.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from openoutreach.mongodb.connection import get_mongodb_collection

logger = logging.getLogger(__name__)

ORGANIZATIONS_COLLECTION = "organizations"
MEMBERS_COLLECTION = "organization_members"
INVITES_COLLECTION = "organization_invites"
AUDIT_COLLECTION = "organization_audit_logs"

ROLE_OWNER = "owner"
ROLE_ADMIN = "admin"
ROLE_MEMBER = "member"
ROLES = {ROLE_OWNER, ROLE_ADMIN, ROLE_MEMBER}

STATUS_INVITED = "invited"
STATUS_ACTIVE = "active"
STATUS_REMOVED = "removed"
MEMBER_STATUSES = {STATUS_INVITED, STATUS_ACTIVE, STATUS_REMOVED}

ORG_STATUS_ACTIVE = "active"
ORG_STATUS_INACTIVE = "inactive"


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    """Normalize PyMongo's naive UTC datetimes for safe comparisons."""
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class Organization:
    """A workspace that owns billing, seats, members, and profiles."""

    def __init__(
        self,
        _id: Optional[str] = None,
        name: str = "",
        owner_user_id: str = "",
        plan: str = "starter",
        stripe_customer_id: Optional[str] = None,
        stripe_subscription_id: Optional[str] = None,
        cloud_seats: int = 0,
        desktop_seats: int = 0,
        linkedin_account_limit: int = 1,
        whatsapp_account_limit: int = 1,
        is_personal: bool = False,
        seat_override: bool = False,
        status: str = ORG_STATUS_ACTIVE,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.name = name
        self.owner_user_id = owner_user_id
        self.plan = plan
        self.stripe_customer_id = stripe_customer_id
        self.stripe_subscription_id = stripe_subscription_id
        self.cloud_seats = max(0, int(cloud_seats or 0))
        self.desktop_seats = max(0, int(desktop_seats or 0))
        self.linkedin_account_limit = max(0, int(linkedin_account_limit or 0))
        self.whatsapp_account_limit = max(0, int(whatsapp_account_limit or 0))
        self.is_personal = bool(is_personal)
        self.seat_override = bool(seat_override)
        self.status = status
        self.created_at = created_at or utc_now()
        self.updated_at = updated_at or utc_now()

    @property
    def pk(self) -> str:
        return self._id

    @property
    def id(self) -> str:
        return self._id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "_id": self._id,
            "name": self.name,
            "owner_user_id": self.owner_user_id,
            "plan": self.plan,
            "stripe_customer_id": self.stripe_customer_id,
            "stripe_subscription_id": self.stripe_subscription_id,
            "cloud_seats": self.cloud_seats,
            "desktop_seats": self.desktop_seats,
            "linkedin_account_limit": self.linkedin_account_limit,
            "whatsapp_account_limit": self.whatsapp_account_limit,
            "is_personal": self.is_personal,
            "seat_override": self.seat_override,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Organization":
        return cls(
            _id=str(data.get("_id")),
            name=data.get("name", ""),
            owner_user_id=data.get("owner_user_id", ""),
            plan=data.get("plan", "starter"),
            stripe_customer_id=data.get("stripe_customer_id"),
            stripe_subscription_id=data.get("stripe_subscription_id"),
            cloud_seats=data.get("cloud_seats", 0),
            desktop_seats=data.get("desktop_seats", 0),
            linkedin_account_limit=data.get("linkedin_account_limit", 1),
            whatsapp_account_limit=data.get("whatsapp_account_limit", 1),
            is_personal=data.get("is_personal", False),
            seat_override=data.get("seat_override", False),
            status=data.get("status", ORG_STATUS_ACTIVE),
            created_at=_aware(data.get("created_at")),
            updated_at=_aware(data.get("updated_at")),
        )

    def save(self) -> str:
        collection = get_mongodb_collection(ORGANIZATIONS_COLLECTION)
        if collection is None:
            raise RuntimeError("MongoDB collection 'organizations' not available")
        self.updated_at = utc_now()
        collection.update_one({"_id": self._id}, {"$set": self.to_dict()}, upsert=True)
        return self._id

    @classmethod
    def get(cls, org_id: str) -> Optional["Organization"]:
        collection = get_mongodb_collection(ORGANIZATIONS_COLLECTION)
        if collection is None:
            return None
        data = collection.find_one({"_id": org_id})
        return cls.from_dict(data) if data else None


class OrganizationMember:
    """A user's membership in one organization."""

    def __init__(
        self,
        _id: Optional[str] = None,
        org_id: str = "",
        user_id: str = "",
        email: str = "",
        role: str = ROLE_MEMBER,
        status: str = STATUS_ACTIVE,
        invited_by: Optional[str] = None,
        invited_at: Optional[datetime] = None,
        joined_at: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.org_id = org_id
        self.user_id = user_id
        self.email = (email or "").lower().strip()
        self.role = role if role in ROLES else ROLE_MEMBER
        self.status = status if status in MEMBER_STATUSES else STATUS_ACTIVE
        self.invited_by = invited_by
        self.invited_at = invited_at
        self.joined_at = joined_at

    @property
    def pk(self) -> str:
        return self._id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "_id": self._id,
            "org_id": self.org_id,
            "user_id": self.user_id,
            "email": self.email,
            "role": self.role,
            "status": self.status,
            "invited_by": self.invited_by,
            "invited_at": self.invited_at,
            "joined_at": self.joined_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OrganizationMember":
        return cls(
            _id=str(data.get("_id")),
            org_id=data.get("org_id", ""),
            user_id=data.get("user_id", ""),
            email=data.get("email", ""),
            role=data.get("role", ROLE_MEMBER),
            status=data.get("status", STATUS_ACTIVE),
            invited_by=data.get("invited_by"),
            invited_at=_aware(data.get("invited_at")),
            joined_at=_aware(data.get("joined_at")),
        )

    def save(self) -> str:
        collection = get_mongodb_collection(MEMBERS_COLLECTION)
        if collection is None:
            raise RuntimeError("MongoDB collection 'organization_members' not available")
        collection.update_one({"_id": self._id}, {"$set": self.to_dict()}, upsert=True)
        return self._id


class OrganizationInvite:
    """A single-use, expiring email invitation. Only the token hash is stored."""

    def __init__(
        self,
        _id: Optional[str] = None,
        org_id: str = "",
        email: str = "",
        role: str = ROLE_MEMBER,
        token_hash: str = "",
        expires_at: Optional[datetime] = None,
        accepted_at: Optional[datetime] = None,
        created_by: Optional[str] = None,
        created_at: Optional[datetime] = None,
        revoked_at: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.org_id = org_id
        self.email = (email or "").lower().strip()
        self.role = role if role in (ROLE_ADMIN, ROLE_MEMBER) else ROLE_MEMBER
        self.token_hash = token_hash
        self.expires_at = expires_at or utc_now()
        self.accepted_at = accepted_at
        self.created_by = created_by
        self.created_at = created_at or utc_now()
        self.revoked_at = revoked_at

    @property
    def pk(self) -> str:
        return self._id

    def is_pending(self, now: Optional[datetime] = None) -> bool:
        moment = _aware(now) or utc_now()
        expires_at = _aware(self.expires_at)
        return (
            self.accepted_at is None
            and self.revoked_at is None
            and expires_at is not None
            and expires_at > moment
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "_id": self._id,
            "org_id": self.org_id,
            "email": self.email,
            "role": self.role,
            "token_hash": self.token_hash,
            "expires_at": self.expires_at,
            "accepted_at": self.accepted_at,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "revoked_at": self.revoked_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OrganizationInvite":
        return cls(
            _id=str(data.get("_id")),
            org_id=data.get("org_id", ""),
            email=data.get("email", ""),
            role=data.get("role", ROLE_MEMBER),
            token_hash=data.get("token_hash", ""),
            expires_at=_aware(data.get("expires_at")),
            accepted_at=_aware(data.get("accepted_at")),
            created_by=data.get("created_by"),
            created_at=_aware(data.get("created_at")),
            revoked_at=_aware(data.get("revoked_at")),
        )

    def save(self) -> str:
        collection = get_mongodb_collection(INVITES_COLLECTION)
        if collection is None:
            raise RuntimeError("MongoDB collection 'organization_invites' not available")
        collection.update_one({"_id": self._id}, {"$set": self.to_dict()}, upsert=True)
        return self._id
