"""
Extended MongoDB Models for OpenOutreach - Missing Models

This module contains all the missing MongoDB models needed to complete Phase 1.
These models follow the same pattern as the existing models in models.py.
"""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pymongo.collection import Collection

from .connection import get_mongodb_collection

logger = logging.getLogger(__name__)


class ChatMessage:
    """
    MongoDB ChatMessage model - LinkedIn conversation messages.
    """

    def __init__(
        self,
        _id: Optional[str] = None,
        deal_id: str = "",
        content: str = "",
        owner_id: Optional[str] = None,
        linkedin_urn: str = "",
        is_outgoing: bool = True,
        creation_date: Optional[datetime] = None,
        user_id: Optional[str] = None,
        channel: str = "linkedin",
        wa_msg_hash: Optional[str] = None,
        wa_delivery_status: Optional[str] = None,
        reply_intent: Optional[str] = None,
    ):
        self._id = _id or str(uuid4())
        self.deal_id = deal_id
        self.content = content
        self.owner_id = owner_id
        self.linkedin_urn = linkedin_urn
        self.is_outgoing = is_outgoing
        self.creation_date = creation_date or datetime.now(timezone.utc)
        self.user_id = user_id
        self.channel = channel
        self.wa_msg_hash = wa_msg_hash
        self.wa_delivery_status = wa_delivery_status  # "sent" | "delivered" | "read" | None
        self.reply_intent = reply_intent  # "interested" | "objection" | "wrong_person" | "not_now" | None

    @staticmethod
    def compute_wa_hash(
        deal_id: str, is_outgoing: bool, content: str, message_key: str = ""
    ) -> str:
        """Hash a WA message, retaining distinct repeated inbound messages.

        Older callers omit ``message_key`` for backwards compatibility.  The
        syncer supplies the DOM timestamp for inbound messages so two replies
        with identical text are not collapsed into one record.
        """
        raw = f"{deal_id}|{is_outgoing}|{content.strip()}|{message_key}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "_id": self._id,
            "deal_id": self.deal_id,
            "content": self.content,
            "owner_id": self.owner_id,
            "linkedin_urn": self.linkedin_urn,
            "is_outgoing": self.is_outgoing,
            "creation_date": self.creation_date,
            "user_id": self.user_id,
            "channel": self.channel,
        }
        if self.wa_msg_hash is not None:
            d["wa_msg_hash"] = self.wa_msg_hash
        if self.wa_delivery_status is not None:
            d["wa_delivery_status"] = self.wa_delivery_status
        if self.reply_intent is not None:
            d["reply_intent"] = self.reply_intent
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatMessage":
        return cls(
            _id=str(data.get("_id")),
            deal_id=data.get("deal_id", ""),
            content=data.get("content", ""),
            owner_id=data.get("owner_id"),
            linkedin_urn=data.get("linkedin_urn", ""),
            is_outgoing=data.get("is_outgoing", True),
            creation_date=data.get("creation_date"),
            user_id=data.get("user_id"),
            channel=data.get("channel", "linkedin"),
            wa_msg_hash=data.get("wa_msg_hash"),
            wa_delivery_status=data.get("wa_delivery_status"),
            reply_intent=data.get("reply_intent"),
        )

    def save(self) -> str:
        from pymongo.errors import DuplicateKeyError

        collection = get_mongodb_collection("chat_messages")
        if collection is None:
            raise RuntimeError("MongoDB collection 'chat_messages' not available")
        doc = self.to_dict()
        try:
            result = collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
        except DuplicateKeyError:
            existing = collection.find_one({"deal_id": self.deal_id, "linkedin_urn": self.linkedin_urn})
            if existing:
                self._id = str(existing["_id"])
            return self._id
        return str(result.upserted_id or self._id)

    @classmethod
    def get(cls, message_id: str) -> Optional["ChatMessage"]:
        collection = get_mongodb_collection("chat_messages")
        if collection is None:
            return None
        try:
            data = collection.find_one({"_id": message_id})
            return cls.from_dict(data) if data else None
        except Exception as e:
            logger.error(f"Failed to get chat message '{message_id}': {e}")
            return None

    @classmethod
    def delete(cls, message_id: str) -> bool:
        collection = get_mongodb_collection("chat_messages")
        if collection is None:
            return False
        try:
            result = collection.delete_one({"_id": message_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete chat message '{message_id}': {e}")
            return False

    def __str__(self) -> str:
        return f"ChatMessage#{self._id[:8]}"

    @property
    def pk(self):
        return self._id

    @pk.setter
    def pk(self, value):
        self._id = value

    @classmethod
    def get_by_deal_and_urn(cls, deal_id: str, linkedin_urn: str) -> Optional["ChatMessage"]:
        """Find a single message by deal and LinkedIn URN."""
        collection = get_mongodb_collection("chat_messages")
        if collection is None:
            return None
        try:
            data = collection.find_one({"deal_id": deal_id, "linkedin_urn": linkedin_urn})
            return cls.from_dict(data) if data else None
        except Exception as e:
            logger.error(f"Failed to get message by deal/urn: {e}")
            return None

    @classmethod
    def find_by_deal(cls, deal_id: str, limit: int = 0) -> List["ChatMessage"]:
        """Find messages for a deal, most recent first."""
        collection = get_mongodb_collection("chat_messages")
        if collection is None:
            return []
        try:
            cursor = collection.find({"deal_id": deal_id}).sort("creation_date", -1)
            if limit:
                cursor = cursor.limit(limit)
            return [cls.from_dict(data) for data in cursor]
        except Exception as e:
            logger.error(f"Failed to find messages for deal '{deal_id}': {e}")
            return []

    @classmethod
    def objects(cls):
        return ChatMessageManager()


class ChatMessageManager:
    def __init__(self):
        self.collection = None

    def _get_collection(self) -> Optional[Collection]:
        if self.collection is None:
            self.collection = get_mongodb_collection("chat_messages")
        return self.collection

    def all(self) -> List[ChatMessage]:
        collection = self._get_collection()
        if collection is None:
            return []
        try:
            return [ChatMessage.from_dict(data) for data in collection.find()]
        except Exception as e:
            logger.error(f"Failed to get all chat messages: {e}")
            return []

    def filter(self, **kwargs) -> List[ChatMessage]:
        collection = self._get_collection()
        if collection is None:
            return []
        try:
            return [ChatMessage.from_dict(data) for data in collection.find(kwargs)]
        except Exception as e:
            logger.error(f"Failed to filter chat messages: {e}")
            return []

    def count(self) -> int:
        collection = self._get_collection()
        if collection is None:
            return 0
        try:
            return collection.count_documents({})
        except Exception as e:
            logger.error(f"Failed to count chat messages: {e}")
            return 0

    def get(self, **kwargs) -> Optional[ChatMessage]:
        collection = self._get_collection()
        if collection is None:
            return None
        try:
            data = collection.find_one(kwargs)
            return ChatMessage.from_dict(data) if data else None
        except Exception as e:
            logger.error(f"Failed to get chat message: {e}")
            return None


class ActionLog:
    """
    MongoDB ActionLog model - LinkedIn action tracking + activity feed + error tracking.
    """

    # Action types
    ACTION_CONNECT = "connect"
    ACTION_CHECK_PENDING = "check_pending"
    ACTION_FOLLOW_UP = "follow_up"
    ACTION_SEND_MANUAL_MESSAGE = "send_manual_message"
    ACTION_CAMPAIGN_PAUSED = "campaign_paused"
    ACTION_CAMPAIGN_STARTED = "campaign_started"
    ACTION_LEAD_DISCOVERED = "lead_discovered"
    ACTION_LEAD_QUALIFIED = "lead_qualified"
    ACTION_LEAD_DISQUALIFIED = "lead_disqualified"

    def __init__(
        self,
        _id: Optional[str] = None,
        linkedin_profile_id: Optional[str] = None,
        campaign_id: str = "",
        action_type: str = "",
        created_at: Optional[datetime] = None,
        details: Optional[Dict[str, Any]] = None,
        status: str = "",
        error_message: str = "",
        duration_ms: Optional[int] = None,
        user_id: Optional[str] = None,
    ):
        self._id = _id or str(uuid4())
        self.linkedin_profile_id = linkedin_profile_id
        self.campaign_id = campaign_id
        self.action_type = action_type
        self.created_at = created_at or datetime.now(timezone.utc)
        self.details = details or {}
        self.status = status
        self.error_message = error_message
        self.duration_ms = duration_ms
        self.user_id = user_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "_id": self._id,
            "linkedin_profile_id": self.linkedin_profile_id,
            "campaign_id": self.campaign_id,
            "action_type": self.action_type,
            "created_at": self.created_at,
            "details": self.details,
            "status": self.status,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
            "user_id": self.user_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActionLog":
        return cls(
            _id=str(data.get("_id")),
            linkedin_profile_id=data.get("linkedin_profile_id"),
            campaign_id=data.get("campaign_id", ""),
            action_type=data.get("action_type", ""),
            created_at=data.get("created_at"),
            details=data.get("details", {}),
            status=data.get("status", ""),
            error_message=data.get("error_message", ""),
            duration_ms=data.get("duration_ms"),
            user_id=data.get("user_id"),
        )

    def save(self) -> str:
        collection = get_mongodb_collection("action_logs")
        if collection is None:
            raise RuntimeError("MongoDB collection 'action_logs' not available")
        doc = self.to_dict()
        result = collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
        return str(result.upserted_id or self._id)

    @classmethod
    def get(cls, log_id: str) -> Optional["ActionLog"]:
        collection = get_mongodb_collection("action_logs")
        if collection is None:
            return None
        try:
            data = collection.find_one({"_id": log_id})
            return cls.from_dict(data) if data else None
        except Exception as e:
            logger.error(f"Failed to get action log '{log_id}': {e}")
            return None

    @classmethod
    def delete(cls, log_id: str) -> bool:
        collection = get_mongodb_collection("action_logs")
        if collection is None:
            return False
        try:
            result = collection.delete_one({"_id": log_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete action log '{log_id}': {e}")
            return False

    def __str__(self) -> str:
        return f"ActionLog#{self._id[:8]} - {self.action_type}"

    @property
    def pk(self):
        return self._id

    @pk.setter
    def pk(self, value):
        self._id = value

    @classmethod
    def objects(cls):
        return ActionLogManager()


class ActionLogManager:
    def __init__(self):
        self.collection = None

    def _get_collection(self) -> Optional[Collection]:
        if self.collection is None:
            self.collection = get_mongodb_collection("action_logs")
        return self.collection

    def all(self) -> List[ActionLog]:
        collection = self._get_collection()
        if collection is None:
            return []
        try:
            return [ActionLog.from_dict(data) for data in collection.find()]
        except Exception as e:
            logger.error(f"Failed to get all action logs: {e}")
            return []

    def filter(self, **kwargs) -> List[ActionLog]:
        collection = self._get_collection()
        if collection is None:
            return []
        try:
            return [ActionLog.from_dict(data) for data in collection.find(kwargs)]
        except Exception as e:
            logger.error(f"Failed to filter action logs: {e}")
            return []

    def count(self) -> int:
        collection = self._get_collection()
        if collection is None:
            return 0
        try:
            return collection.count_documents({})
        except Exception as e:
            logger.error(f"Failed to count action logs: {e}")
            return 0


class Notification:
    """
    MongoDB Notification model - 7 notification types.
    """

    TYPE_CAMPAIGN_STARTED = "campaign_started"
    TYPE_CAMPAIGN_PAUSED = "campaign_paused"
    TYPE_CAMPAIGN_COMPLETED = "campaign_completed"
    TYPE_RATE_LIMIT_WARNING = "rate_limit_warning"
    TYPE_NEW_MESSAGE = "new_message"
    TYPE_CAMPAIGN_ERROR = "campaign_error"
    TYPE_SYSTEM_ANNOUNCEMENT = "system_announcement"

    def __init__(
        self,
        _id: Optional[str] = None,
        recipient_id: str = "",
        notification_type: str = "",
        title: str = "",
        message: str = "",
        campaign_id: Optional[str] = None,
        deal_id: Optional[str] = None,
        is_read: bool = False,
        read_at: Optional[datetime] = None,
        data: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.recipient_id = recipient_id
        self.notification_type = notification_type
        self.title = title
        self.message = message
        self.campaign_id = campaign_id
        self.deal_id = deal_id
        self.is_read = is_read
        self.read_at = read_at
        self.data = data or {}
        self.created_at = created_at or datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "_id": self._id,
            "recipient_id": self.recipient_id,
            "notification_type": self.notification_type,
            "title": self.title,
            "message": self.message,
            "campaign_id": self.campaign_id,
            "deal_id": self.deal_id,
            "is_read": self.is_read,
            "read_at": self.read_at,
            "data": self.data,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Notification":
        return cls(
            _id=str(data.get("_id")),
            recipient_id=data.get("recipient_id", ""),
            notification_type=data.get("notification_type", ""),
            title=data.get("title", ""),
            message=data.get("message", ""),
            campaign_id=data.get("campaign_id"),
            deal_id=data.get("deal_id"),
            is_read=data.get("is_read", False),
            read_at=data.get("read_at"),
            data=data.get("data", {}),
            created_at=data.get("created_at"),
        )

    def save(self) -> str:
        collection = get_mongodb_collection("notifications")
        if collection is None:
            raise RuntimeError("MongoDB collection 'notifications' not available")
        doc = self.to_dict()
        result = collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
        return str(result.upserted_id or self._id)

    def mark_as_read(self):
        self.is_read = True
        self.read_at = datetime.now(timezone.utc)
        self.save()

    @classmethod
    def get(cls, notification_id: str) -> Optional["Notification"]:
        collection = get_mongodb_collection("notifications")
        if collection is None:
            return None
        try:
            data = collection.find_one({"_id": notification_id})
            return cls.from_dict(data) if data else None
        except Exception as e:
            logger.error(f"Failed to get notification '{notification_id}': {e}")
            return None

    @classmethod
    def get_unread_count(cls, user_id: str) -> int:
        collection = get_mongodb_collection("notifications")
        if collection is None:
            return 0
        try:
            return collection.count_documents({"recipient_id": user_id, "is_read": False})
        except Exception as e:
            logger.error(f"Failed to count unread notifications: {e}")
            return 0

    @classmethod
    def delete(cls, notification_id: str) -> bool:
        collection = get_mongodb_collection("notifications")
        if collection is None:
            return False
        try:
            result = collection.delete_one({"_id": notification_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete notification '{notification_id}': {e}")
            return False

    def __str__(self) -> str:
        return f"Notification#{self._id[:8]} - {self.notification_type}"

    @property
    def pk(self):
        return self._id

    @pk.setter
    def pk(self, value):
        self._id = value

    @classmethod
    def objects(cls):
        return NotificationManager()


class NotificationManager:
    def __init__(self):
        self.collection = None

    def _get_collection(self) -> Optional[Collection]:
        if self.collection is None:
            self.collection = get_mongodb_collection("notifications")
        return self.collection

    def all(self) -> List[Notification]:
        collection = self._get_collection()
        if collection is None:
            return []
        try:
            return [Notification.from_dict(data) for data in collection.find()]
        except Exception as e:
            logger.error(f"Failed to get all notifications: {e}")
            return []

    def filter(self, **kwargs) -> List[Notification]:
        collection = self._get_collection()
        if collection is None:
            return []
        try:
            return [Notification.from_dict(data) for data in collection.find(kwargs)]
        except Exception as e:
            logger.error(f"Failed to filter notifications: {e}")
            return []

    def count(self) -> int:
        collection = self._get_collection()
        if collection is None:
            return 0
        try:
            return collection.count_documents({})
        except Exception as e:
            logger.error(f"Failed to count notifications: {e}")
            return 0


class SearchKeyword:
    """
    MongoDB SearchKeyword model - campaign search keywords.
    """

    def __init__(
        self,
        _id: Optional[str] = None,
        campaign_id: str = "",
        keyword: str = "",
        used: bool = False,
        used_at: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.campaign_id = campaign_id
        self.keyword = keyword
        self.used = used
        self.used_at = used_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "_id": self._id,
            "campaign_id": self.campaign_id,
            "keyword": self.keyword,
            "used": self.used,
            "used_at": self.used_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SearchKeyword":
        return cls(
            _id=str(data.get("_id")),
            campaign_id=data.get("campaign_id", ""),
            keyword=data.get("keyword", ""),
            used=data.get("used", False),
            used_at=data.get("used_at"),
        )

    def save(self) -> str:
        from pymongo.errors import DuplicateKeyError

        collection = get_mongodb_collection("search_keywords")
        if collection is None:
            raise RuntimeError("MongoDB collection 'search_keywords' not available")
        doc = self.to_dict()
        try:
            result = collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
        except DuplicateKeyError:
            existing = collection.find_one({"campaign_id": self.campaign_id, "keyword": self.keyword})
            if existing:
                self._id = str(existing["_id"])
            return self._id
        return str(result.upserted_id or self._id)

    @classmethod
    def get(cls, keyword_id: str) -> Optional["SearchKeyword"]:
        collection = get_mongodb_collection("search_keywords")
        if collection is None:
            return None
        try:
            data = collection.find_one({"_id": keyword_id})
            return cls.from_dict(data) if data else None
        except Exception as e:
            logger.error(f"Failed to get search keyword '{keyword_id}': {e}")
            return None

    @classmethod
    def delete(cls, keyword_id: str) -> bool:
        collection = get_mongodb_collection("search_keywords")
        if collection is None:
            return False
        try:
            result = collection.delete_one({"_id": keyword_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete search keyword '{keyword_id}': {e}")
            return False

    def __str__(self) -> str:
        return f"SearchKeyword#{self._id[:8]} - {self.keyword}"

    @property
    def pk(self):
        return self._id

    @pk.setter
    def pk(self, value):
        self._id = value

    @classmethod
    def objects(cls):
        return SearchKeywordManager()


class SearchKeywordManager:
    def __init__(self):
        self.collection = None

    def _get_collection(self) -> Optional[Collection]:
        if self.collection is None:
            self.collection = get_mongodb_collection("search_keywords")
        return self.collection

    def all(self) -> List[SearchKeyword]:
        collection = self._get_collection()
        if collection is None:
            return []
        try:
            return [SearchKeyword.from_dict(data) for data in collection.find()]
        except Exception as e:
            logger.error(f"Failed to get all search keywords: {e}")
            return []

    def filter(self, **kwargs) -> List[SearchKeyword]:
        collection = self._get_collection()
        if collection is None:
            return []
        try:
            return [SearchKeyword.from_dict(data) for data in collection.find(kwargs)]
        except Exception as e:
            logger.error(f"Failed to filter search keywords: {e}")
            return []

    def count(self) -> int:
        collection = self._get_collection()
        if collection is None:
            return 0
        try:
            return collection.count_documents({})
        except Exception as e:
            logger.error(f"Failed to count search keywords: {e}")
            return 0


class Mailbox:
    """
    MongoDB Mailbox model - SMTP mailbox with daily send pacing.
    """

    def __init__(
        self,
        _id: Optional[str] = None,
        host: str = "smtp.gmail.com",
        port: int = 587,
        username: str = "",
        password: str = "",
        from_address: str = "",
        daily_limit: int = 50,
        user_id: str = "",
    ):
        self._id = _id or str(uuid4())
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_address = from_address
        self.daily_limit = daily_limit
        self.user_id = user_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "_id": self._id,
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "password": self.password,
            "from_address": self.from_address,
            "daily_limit": self.daily_limit,
            "user_id": self.user_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Mailbox":
        return cls(
            _id=str(data.get("_id")),
            host=data.get("host", "smtp.gmail.com"),
            port=data.get("port", 587),
            username=data.get("username", ""),
            password=data.get("password", ""),
            from_address=data.get("from_address", ""),
            daily_limit=data.get("daily_limit", 50),
            user_id=data.get("user_id", ""),
        )

    def save(self) -> str:
        collection = get_mongodb_collection("mailboxes")
        if collection is None:
            raise RuntimeError("MongoDB collection 'mailboxes' not available")
        doc = self.to_dict()
        result = collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
        return str(result.upserted_id or self._id)

    def sent_today(self) -> int:
        """Count emails sent today by this mailbox."""
        collection = get_mongodb_collection("deals")
        if collection is None:
            return 0
        midnight = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        try:
            return collection.count_documents({
                "mailbox_id": self._id,
                "email_sent_at": {"$gte": midnight}
            })
        except Exception as e:
            logger.error(f"Failed to count sent emails: {e}")
            return 0

    def headroom_today(self) -> int:
        return max(0, self.daily_limit - self.sent_today())

    @classmethod
    def get(cls, mailbox_id: str) -> Optional["Mailbox"]:
        collection = get_mongodb_collection("mailboxes")
        if collection is None:
            return None
        try:
            data = collection.find_one({"_id": mailbox_id})
            return cls.from_dict(data) if data else None
        except Exception as e:
            logger.error(f"Failed to get mailbox '{mailbox_id}': {e}")
            return None

    @classmethod
    def delete(cls, mailbox_id: str) -> bool:
        collection = get_mongodb_collection("mailboxes")
        if collection is None:
            return False
        try:
            result = collection.delete_one({"_id": mailbox_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete mailbox '{mailbox_id}': {e}")
            return False

    def __str__(self) -> str:
        return f"Mailbox#{self._id[:8]} - {self.from_address}"

    @property
    def pk(self):
        return self._id

    @pk.setter
    def pk(self, value):
        self._id = value

    @classmethod
    def objects(cls):
        return MailboxManager()


class MailboxManager:
    def __init__(self):
        self.collection = None

    def _get_collection(self) -> Optional[Collection]:
        if self.collection is None:
            self.collection = get_mongodb_collection("mailboxes")
        return self.collection

    def all(self) -> List[Mailbox]:
        collection = self._get_collection()
        if collection is None:
            return []
        try:
            return [Mailbox.from_dict(data) for data in collection.find()]
        except Exception as e:
            logger.error(f"Failed to get all mailboxes: {e}")
            return []

    def filter(self, **kwargs) -> List[Mailbox]:
        collection = self._get_collection()
        if collection is None:
            return []
        try:
            return [Mailbox.from_dict(data) for data in collection.find(kwargs)]
        except Exception as e:
            logger.error(f"Failed to filter mailboxes: {e}")
            return []

    def count(self) -> int:
        collection = self._get_collection()
        if collection is None:
            return 0
        try:
            return collection.count_documents({})
        except Exception as e:
            logger.error(f"Failed to count mailboxes: {e}")
            return 0


class CampaignTemplate:
    """
    MongoDB CampaignTemplate model - predefined campaign settings.
    """

    def __init__(
        self,
        _id: Optional[str] = None,
        name: str = "",
        description: str = "",
        product_pitch: str = "",
        campaign_objective: str = "",
        booking_link: str = "",
        icp_titles: Optional[List[str]] = None,
        follow_up_strategy: str = "",
        ghost_mode_enabled: bool = False,
        is_public: bool = False,
        created_by_id: str = "",
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.name = name
        self.description = description
        self.product_pitch = product_pitch
        self.campaign_objective = campaign_objective
        self.booking_link = booking_link
        self.icp_titles = icp_titles or []
        self.follow_up_strategy = follow_up_strategy
        self.ghost_mode_enabled = ghost_mode_enabled
        self.is_public = is_public
        self.created_by_id = created_by_id
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "_id": self._id,
            "name": self.name,
            "description": self.description,
            "product_pitch": self.product_pitch,
            "campaign_objective": self.campaign_objective,
            "booking_link": self.booking_link,
            "icp_titles": self.icp_titles,
            "follow_up_strategy": self.follow_up_strategy,
            "ghost_mode_enabled": self.ghost_mode_enabled,
            "is_public": self.is_public,
            "created_by_id": self.created_by_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CampaignTemplate":
        return cls(
            _id=str(data.get("_id")),
            name=data.get("name", ""),
            description=data.get("description", ""),
            product_pitch=data.get("product_pitch", ""),
            campaign_objective=data.get("campaign_objective", ""),
            booking_link=data.get("booking_link", ""),
            icp_titles=data.get("icp_titles", []),
            follow_up_strategy=data.get("follow_up_strategy", ""),
            ghost_mode_enabled=data.get("ghost_mode_enabled", False),
            is_public=data.get("is_public", False),
            created_by_id=data.get("created_by_id", ""),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    def save(self) -> str:
        collection = get_mongodb_collection("campaign_templates")
        if collection is None:
            raise RuntimeError("MongoDB collection 'campaign_templates' not available")
        self.updated_at = datetime.now(timezone.utc)
        doc = self.to_dict()
        result = collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
        return str(result.upserted_id or self._id)

    @classmethod
    def get(cls, template_id: str) -> Optional["CampaignTemplate"]:
        collection = get_mongodb_collection("campaign_templates")
        if collection is None:
            return None
        try:
            data = collection.find_one({"_id": template_id})
            return cls.from_dict(data) if data else None
        except Exception as e:
            logger.error(f"Failed to get campaign template '{template_id}': {e}")
            return None

    @classmethod
    def delete(cls, template_id: str) -> bool:
        collection = get_mongodb_collection("campaign_templates")
        if collection is None:
            return False
        try:
            result = collection.delete_one({"_id": template_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete campaign template '{template_id}': {e}")
            return False

    def __str__(self) -> str:
        return f"CampaignTemplate#{self._id[:8]} - {self.name}"

    @property
    def pk(self):
        return self._id

    @pk.setter
    def pk(self, value):
        self._id = value

    @classmethod
    def objects(cls):
        return CampaignTemplateManager()


class CampaignTemplateManager:
    def __init__(self):
        self.collection = None

    def _get_collection(self) -> Optional[Collection]:
        if self.collection is None:
            self.collection = get_mongodb_collection("campaign_templates")
        return self.collection

    def all(self) -> List[CampaignTemplate]:
        collection = self._get_collection()
        if collection is None:
            return []
        try:
            return [CampaignTemplate.from_dict(data) for data in collection.find()]
        except Exception as e:
            logger.error(f"Failed to get all campaign templates: {e}")
            return []

    def filter(self, **kwargs) -> List[CampaignTemplate]:
        collection = self._get_collection()
        if collection is None:
            return []
        try:
            return [CampaignTemplate.from_dict(data) for data in collection.find(kwargs)]
        except Exception as e:
            logger.error(f"Failed to filter campaign templates: {e}")
            return []

    def count(self) -> int:
        collection = self._get_collection()
        if collection is None:
            return 0
        try:
            return collection.count_documents({})
        except Exception as e:
            logger.error(f"Failed to count campaign templates: {e}")
            return 0


# Export all models
__all__ = [
    "ChatMessage",
    "ChatMessageManager",
    "ActionLog",
    "ActionLogManager",
    "Notification",
    "NotificationManager",
    "SearchKeyword",
    "SearchKeywordManager",
    "Mailbox",
    "MailboxManager",
    "CampaignTemplate",
    "CampaignTemplateManager",
]
