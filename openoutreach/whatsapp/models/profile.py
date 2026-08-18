import logging
from datetime import datetime, timezone
from typing import ClassVar, List, Optional
from uuid import uuid4

from openoutreach.mongodb.connection import get_mongodb_collection

logger = logging.getLogger(__name__)

STATUS_CONNECTED = "connected"
STATUS_DISCONNECTED = "disconnected"
STATUS_BANNED = "banned"


class WhatsAppProfile:
    """MongoDB-based WhatsApp profile model.

    Stores one WA Web session per user. session_data_encrypted holds
    Playwright localStorage + cookies, same crypto as LinkedInProfile.
    """

    objects: ClassVar["WhatsAppProfileManager"]

    def __init__(
        self,
        _id: Optional[str] = None,
        user_id: str = "",
        phone_number: Optional[str] = None,
        display_name: Optional[str] = None,
        session_data_encrypted: Optional[str] = None,
        status: str = STATUS_DISCONNECTED,
        last_seen: Optional[datetime] = None,
        created_at: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.user_id = user_id
        self.phone_number = phone_number
        self.display_name = display_name
        self.session_data_encrypted = session_data_encrypted
        self.status = status
        self.last_seen = last_seen
        self.created_at = created_at or datetime.now(timezone.utc)

    @property
    def pk(self) -> str:
        return self._id

    @pk.setter
    def pk(self, value: str) -> None:
        self._id = value

    @property
    def id(self) -> str:
        return self._id

    @property
    def session_data(self) -> Optional[dict]:
        """Decrypt and return the session dict, or None."""
        if not self.session_data_encrypted:
            return None
        try:
            import json
            from openoutreach.core.crypto import decrypt_text
            return json.loads(decrypt_text(self.session_data_encrypted))
        except Exception:
            return None

    @session_data.setter
    def session_data(self, value: Optional[dict]) -> None:
        """Encrypt and store the session dict."""
        if value is None:
            self.session_data_encrypted = None
            return
        try:
            import json
            from openoutreach.core.crypto import encrypt_text
            self.session_data_encrypted = encrypt_text(json.dumps(value))
        except Exception:
            self.session_data_encrypted = None

    def to_dict(self) -> dict:
        data: dict = {
            "_id": self._id,
            "user_id": self.user_id,
            "status": self.status,
            "created_at": self.created_at,
        }
        if self.phone_number is not None:
            data["phone_number"] = self.phone_number
        if self.display_name is not None:
            data["display_name"] = self.display_name
        if self.session_data_encrypted is not None:
            data["session_data_encrypted"] = self.session_data_encrypted
        if self.last_seen is not None:
            data["last_seen"] = self.last_seen
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "WhatsAppProfile":
        return cls(
            _id=str(data.get("_id")),
            user_id=data.get("user_id", ""),
            phone_number=data.get("phone_number"),
            display_name=data.get("display_name"),
            session_data_encrypted=data.get("session_data_encrypted"),
            status=data.get("status", STATUS_DISCONNECTED),
            last_seen=data.get("last_seen"),
            created_at=data.get("created_at"),
        )

    def save(self, update_fields: Optional[List[str]] = None) -> str:
        collection = get_mongodb_collection("whatsapp_profiles")
        if collection is None:
            raise RuntimeError("MongoDB collection 'whatsapp_profiles' not available")
        if update_fields:
            full = self.to_dict()
            doc = {f: full[f] for f in update_fields if f in full}
        else:
            doc = self.to_dict()
        result = collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
        return str(result.upserted_id or self._id)

    @classmethod
    def get(cls, profile_id: str) -> Optional["WhatsAppProfile"]:
        collection = get_mongodb_collection("whatsapp_profiles")
        if collection is None:
            return None
        data = collection.find_one({"_id": profile_id})
        return cls.from_dict(data) if data else None

    @classmethod
    def find_by_user_id(cls, user_id: str) -> List["WhatsAppProfile"]:
        collection = get_mongodb_collection("whatsapp_profiles")
        if collection is None:
            return []
        return [cls.from_dict(d) for d in collection.find({"user_id": user_id})]

    @classmethod
    def delete(cls, profile_id: str) -> bool:
        collection = get_mongodb_collection("whatsapp_profiles")
        if collection is None:
            return False
        result = collection.delete_one({"_id": profile_id})
        return result.deleted_count > 0

    def __str__(self) -> str:
        label = self.phone_number or self.display_name or f"WAProfile#{self._id[:8]}"
        return f"WhatsAppProfile({label})"


class WhatsAppProfileManager:
    def __init__(self) -> None:
        self.collection = None

    def _get_collection(self):
        if self.collection is None:
            self.collection = get_mongodb_collection("whatsapp_profiles")
        return self.collection

    def all(self) -> List[WhatsAppProfile]:
        collection = self._get_collection()
        if collection is None:
            return []
        try:
            return [WhatsAppProfile.from_dict(d) for d in collection.find()]
        except Exception as e:
            logger.error("Failed to get all WhatsApp profiles: %s", e)
            return []

    def filter(self, **kwargs) -> List[WhatsAppProfile]:
        collection = self._get_collection()
        if collection is None:
            return []
        try:
            return [WhatsAppProfile.from_dict(d) for d in collection.find(kwargs)]
        except Exception as e:
            logger.error("Failed to filter WhatsApp profiles: %s", e)
            return []

    def get(self, **kwargs) -> Optional[WhatsAppProfile]:
        collection = self._get_collection()
        if collection is None:
            return None
        try:
            data = collection.find_one(kwargs)
            return WhatsAppProfile.from_dict(data) if data else None
        except Exception as e:
            logger.error("Failed to get WhatsApp profile: %s", e)
            return None


WhatsAppProfile.objects = WhatsAppProfileManager()
