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
        org_id: Optional[str] = None,
        assigned_user_id: Optional[str] = None,
        identity_id: Optional[str] = None,
        execution_mode: str = "desktop",
        cloud_mode: str = "desktop",
        proxy_id: Optional[str] = None,
        proxy_mode: str = "none",
        proxy_region_country: Optional[str] = None,
        proxy_region_subdivision: Optional[str] = None,
        proxy_region_city: Optional[str] = None,
        active: bool = True,
        is_active: bool = True,
        phone_number: Optional[str] = None,
        display_name: Optional[str] = None,
        session_data_encrypted: Optional[str] = None,
        status: str = STATUS_DISCONNECTED,
        last_seen: Optional[datetime] = None,
        created_at: Optional[datetime] = None,
        qr_png_b64: Optional[str] = None,
        qr_generated_at: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.user_id = user_id
        self.org_id = org_id
        self.assigned_user_id = assigned_user_id or user_id
        self.identity_id = identity_id
        self.execution_mode = execution_mode if execution_mode in {"desktop", "cloud"} else "desktop"
        allowed_cloud_modes = {"desktop", "duo_shared", "duo_separate", "whatsapp_only"}
        resolved_cloud_mode = cloud_mode if cloud_mode in allowed_cloud_modes else "desktop"
        if self.execution_mode == "cloud" and resolved_cloud_mode == "desktop":
            # Pre-Phase-4-completion cloud rows were the shared-IP Duo slice.
            resolved_cloud_mode = "duo_shared"
        if self.execution_mode == "desktop":
            resolved_cloud_mode = "desktop"
        self.cloud_mode = resolved_cloud_mode
        self.proxy_id = proxy_id
        self.proxy_mode = proxy_mode
        self.proxy_region_country = proxy_region_country
        self.proxy_region_subdivision = proxy_region_subdivision
        self.proxy_region_city = proxy_region_city
        self.active = bool(active)
        self.is_active = bool(is_active)
        self.phone_number = phone_number
        self.display_name = display_name
        self.session_data_encrypted = session_data_encrypted
        self.status = status
        self.last_seen = last_seen
        self.created_at = created_at or datetime.now(timezone.utc)
        self.qr_png_b64 = qr_png_b64
        self.qr_generated_at = qr_generated_at

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
            "org_id": self.org_id,
            "assigned_user_id": self.assigned_user_id,
            "identity_id": self.identity_id,
            "execution_mode": self.execution_mode,
            "cloud_mode": self.cloud_mode,
            "proxy_id": self.proxy_id,
            "proxy_mode": self.proxy_mode,
            "proxy_region_country": self.proxy_region_country,
            "proxy_region_subdivision": self.proxy_region_subdivision,
            "proxy_region_city": self.proxy_region_city,
            "active": self.active,
            "is_active": self.is_active,
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
        if self.qr_png_b64 is not None:
            data["qr_png_b64"] = self.qr_png_b64
        if self.qr_generated_at is not None:
            data["qr_generated_at"] = self.qr_generated_at
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "WhatsAppProfile":
        return cls(
            _id=str(data.get("_id")),
            user_id=data.get("user_id", ""),
            org_id=data.get("org_id"),
            assigned_user_id=data.get("assigned_user_id"),
            identity_id=data.get("identity_id"),
            execution_mode=data.get("execution_mode", "desktop"),
            cloud_mode=data.get("cloud_mode", "desktop"),
            proxy_id=data.get("proxy_id"),
            proxy_mode=data.get("proxy_mode", "none"),
            proxy_region_country=data.get("proxy_region_country"),
            proxy_region_subdivision=data.get("proxy_region_subdivision"),
            proxy_region_city=data.get("proxy_region_city"),
            active=bool(data.get("active", True)),
            is_active=bool(data.get("is_active", True)),
            phone_number=data.get("phone_number"),
            display_name=data.get("display_name"),
            session_data_encrypted=data.get("session_data_encrypted"),
            status=data.get("status", STATUS_DISCONNECTED),
            last_seen=data.get("last_seen"),
            created_at=data.get("created_at"),
            qr_png_b64=data.get("qr_png_b64"),
            qr_generated_at=data.get("qr_generated_at"),
        )

    def save(self, update_fields: Optional[List[str]] = None) -> str:
        collection = get_mongodb_collection("whatsapp_profiles")
        if collection is None:
            raise RuntimeError("MongoDB collection 'whatsapp_profiles' not available")
        if update_fields:
            full = self.to_dict()
            doc = {}
            for f in update_fields:
                if f in full:
                    doc[f] = full[f]
                elif hasattr(self, f):
                    doc[f] = getattr(self, f)  # include None values (e.g. clearing qr_png_b64)
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
    def find_for_user(cls, user) -> List["WhatsAppProfile"]:
        """Return org-scoped profiles visible to one authenticated user."""
        from openoutreach.organizations.access import channel_access_query

        collection = get_mongodb_collection("whatsapp_profiles")
        if collection is None:
            return []
        return [
            cls.from_dict(d)
            for d in collection.find(channel_access_query(user))
        ]

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
            logger.error("Failed to get all WhatsApp profiles; exception_type=%s", type(e).__name__)
            return []

    def filter(self, **kwargs) -> List[WhatsAppProfile]:
        collection = self._get_collection()
        if collection is None:
            return []
        try:
            return [WhatsAppProfile.from_dict(d) for d in collection.find(kwargs)]
        except Exception as e:
            logger.error("Failed to filter WhatsApp profiles; exception_type=%s", type(e).__name__)
            return []

    def get(self, **kwargs) -> Optional[WhatsAppProfile]:
        collection = self._get_collection()
        if collection is None:
            return None
        try:
            data = collection.find_one(kwargs)
            return WhatsAppProfile.from_dict(data) if data else None
        except Exception as e:
            logger.error("Failed to get WhatsApp profile; exception_type=%s", type(e).__name__)
            return None


WhatsAppProfile.objects = WhatsAppProfileManager()
