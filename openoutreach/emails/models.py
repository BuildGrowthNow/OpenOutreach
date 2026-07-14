# openoutreach/emails/models.py
"""Mailbox: one SMTP sending inbox, imported from the provider's creds export."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pymongo.collection import Collection

from openoutreach.core.conf import DEFAULT_EMAIL_DAILY_LIMIT
from openoutreach.mongodb.connection import get_mongodb_collection

logger = logging.getLogger(__name__)


class MailboxManager:
    """Pool-level send pacing — the daily-cap accounting the task and planner share."""

    def __init__(self):
        self.collection = None

    def _get_collection(self) -> Optional[Collection]:
        if self.collection is None:
            self.collection = get_mongodb_collection("mailboxes")
        return self.collection

    def all(self) -> List["Mailbox"]:
        """Get all mailboxes."""
        collection = self._get_collection()
        if collection is None:
            return []

        try:
            mailboxes = []
            for data in collection.find():
                mailboxes.append(Mailbox.from_dict(data))
            return mailboxes
        except Exception as e:
            logger.error(f"Failed to get all mailboxes: {e}")
            return []

    def remaining_today(self) -> int:
        """Total sends left across the pool today (Σ per-box headroom).

        0 when no boxes exist or every box is at its cap.
        """
        return sum(box.headroom_today() for box in self.all())

    def least_loaded_under_cap(self) -> Optional["Mailbox"]:
        """The under-cap box with the most headroom today, or None if all are capped."""
        ranked = [
            (box, sent)
            for box in self.all()
            if (sent := box.sent_today()) < box.daily_limit
        ]
        if not ranked:
            return None
        return min(ranked, key=lambda pair: pair[1])[0]

    def exists(self) -> bool:
        """Check if any mailboxes exist."""
        collection = self._get_collection()
        if collection is None:
            return False
        try:
            return collection.count_documents({}) > 0
        except Exception as e:
            logger.error(f"Failed to check mailbox existence: {e}")
            return False

    def update_or_create(
        self, defaults: Optional[Dict[str, Any]] = None, **kwargs
    ) -> tuple["Mailbox", bool]:
        """Get existing mailbox or create new one based on filter criteria.

        Args:
            defaults: Fields to set on the mailbox if creating or updating
            **kwargs: Filter criteria to find existing mailbox

        Returns:
            Tuple of (mailbox, created) where created is True if newly created
        """
        collection = self._get_collection()
        if collection is None:
            raise RuntimeError("MongoDB collection 'mailboxes' not available")

        try:
            # Try to find existing mailbox
            existing_data = collection.find_one(kwargs)

            if existing_data:
                # Update existing
                mailbox = Mailbox.from_dict(existing_data)
                if defaults:
                    # Apply defaults to mailbox
                    for key, value in defaults.items():
                        if hasattr(mailbox, key):
                            setattr(mailbox, key, value)
                    mailbox.save()
                return mailbox, False
            else:
                # Create new
                data = kwargs.copy()
                if defaults:
                    data.update(defaults)
                mailbox = Mailbox(**data)
                mailbox.save()
                return mailbox, True
        except Exception as e:
            logger.error(f"Failed to update_or_create mailbox: {e}")
            raise


class Mailbox:
    """One SMTP inbox. host/port default to IceMail's Google Workspace boxes.

    A row exists only once its credentials pass the import auth-check — the
    provider has no health API, so the import is the gate. Send-time failures
    are not swallowed: a bad send fails its task and is retried, the box is
    left untouched (re-import with fixed credentials to repair it).
    """

    def __init__(
        self,
        _id: Optional[str] = None,
        host: str = "smtp.gmail.com",
        port: int = 587,
        username: str = "",
        password: str = "",
        from_address: str = "",
        daily_limit: int = DEFAULT_EMAIL_DAILY_LIMIT,
        created_at: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_address = from_address
        self.daily_limit = daily_limit
        self.created_at = created_at or datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary for MongoDB storage."""
        return {
            "_id": self._id,
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "password": self.password,
            "from_address": self.from_address,
            "daily_limit": self.daily_limit,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Mailbox":
        """Create Mailbox instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            host=data.get("host", "smtp.gmail.com"),
            port=data.get("port", 587),
            username=data.get("username", ""),
            password=data.get("password", ""),
            from_address=data.get("from_address", ""),
            daily_limit=data.get("daily_limit", DEFAULT_EMAIL_DAILY_LIMIT),
            created_at=data.get("created_at"),
        )

    def save(self) -> str:
        """Save the mailbox to MongoDB."""
        collection = get_mongodb_collection("mailboxes")
        if collection is None:
            raise RuntimeError("MongoDB collection 'mailboxes' not available")

        doc = self.to_dict()
        result = collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
        return str(result.upserted_id or self._id)

    @classmethod
    def get(cls, mailbox_id: str) -> Optional["Mailbox"]:
        """Get a mailbox by ID."""
        collection = get_mongodb_collection("mailboxes")
        if collection is None:
            return None

        try:
            data = collection.find_one({"_id": mailbox_id})
            if data:
                return cls.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get mailbox '{mailbox_id}': {e}")
            return None

    @classmethod
    def find_by_username(cls, username: str) -> Optional["Mailbox"]:
        """Find a mailbox by username (unique)."""
        collection = get_mongodb_collection("mailboxes")
        if collection is None:
            return None

        try:
            data = collection.find_one({"username": username})
            if data:
                return cls.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to find mailbox by username '{username}': {e}")
            return None

    @classmethod
    def delete(cls, mailbox_id: str) -> bool:
        """Delete a mailbox by ID."""
        collection = get_mongodb_collection("mailboxes")
        if collection is None:
            return False

        try:
            result = collection.delete_one({"_id": mailbox_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete mailbox '{mailbox_id}': {e}")
            return False

    def __str__(self):
        return self.from_address or self.username

    @property
    def pk(self):
        """Get the primary key."""
        return self._id

    @pk.setter
    def pk(self, value):
        """Set the primary key."""
        self._id = value

    @classmethod
    def objects(cls) -> MailboxManager:
        """Get the MailboxManager for querying mailboxes."""
        return MailboxManager()

    def sent_today(self) -> int:
        """Emails this box has sent since local midnight (the per-box cap ledger).

        Keyed on ``email_sent_at`` (write-once at send, never cleared), so a deal
        dispositioned past EMAILED later the same day still counts against the cap.
        """
        midnight = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        deals_collection = get_mongodb_collection("deals")
        if deals_collection is None:
            return 0

        try:
            count = deals_collection.count_documents(
                {"mailbox_id": self._id, "email_sent_at": {"$gte": midnight}}
            )
            return count
        except Exception as e:
            logger.error(f"Failed to count sent emails for mailbox '{self._id}': {e}")
            return 0

    def headroom_today(self) -> int:
        """Sends this box has left today before hitting ``daily_limit``."""
        return max(0, self.daily_limit - self.sent_today())


def has_mailbox() -> bool:
    """True when ≥1 mailbox is configured — i.e. email is a viable channel to
    send from. Gates email enrichment: with no mailbox there's nothing to send,
    so resolving an address is pointless and the deal should take the connect leg."""
    return Mailbox.objects().exists()
