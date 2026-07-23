# openoutreach/linkedin/models/__init__.py
# Main models for the LinkedIn app

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import ClassVar, Optional
from uuid import uuid4

from openoutreach.core.models import Campaign
from openoutreach.mongodb.connection import get_mongodb_collection

# Health monitoring models
try:
    from .health import CampaignHealthMetric, HealthAlert, RecoveryAction
except ImportError:
    # Health models not yet migrated
    CampaignHealthMetric = None
    HealthAlert = None
    RecoveryAction = None

# Rate limiting models (MongoDB)
from .rate_limits import (
    EngagementLevel,
    LinkedInDetectability,
    RateLimitWarning,
    SmartRateLimitContext,
)

# State machine models (MongoDB)
from .state_machine import (
    CampaignExecutionLog,
    CampaignState,
    CampaignStateGraph,
    StateNode,
    StateTransition,
)

logger = logging.getLogger(__name__)

# action_type → daily_limit_field
_RATE_LIMIT_FIELDS = {
    "connect": "connect_daily_limit",
    "follow_up": "follow_up_daily_limit",
}


class LinkedInProfile:
    """MongoDB-based LinkedIn profile model."""

    objects: ClassVar[LinkedInProfileManager]

    def __init__(
        self,
        _id: Optional[str] = None,
        user_id: Optional[str] = None,
        self_lead_id: Optional[str] = None,
        linkedin_username: Optional[str] = None,
        linkedin_password: Optional[str] = None,
        subscribe_newsletter: bool = True,
        active: bool = True,
        is_active: bool = True,
        connect_daily_limit: int = 20,
        follow_up_daily_limit: int = 25,
        legal_accepted: bool = False,
        cookie_data_encrypted: Optional[str] = None,
        newsletter_processed: bool = False,
        campaign_id: Optional[str] = None,
        # Daemon tracking
        daemon_last_seen: Optional[datetime] = None,
        daemon_version: Optional[str] = None,
        daemon_platform: Optional[str] = None,
        daemon_browser: Optional[str] = None,
        # Session state (reported by daemon)
        is_logged_in: bool = False,
        requires_verification: bool = False,
        verification_type: Optional[str] = None,
        session_updated_at: Optional[datetime] = None,
        cookies_updated_at: Optional[datetime] = None,
        # Proxy configuration (per-profile)
        proxy_server: Optional[str] = None,
        proxy_username: Optional[str] = None,
        proxy_password: Optional[str] = None,
        # Execution mode
        execution_mode: str = "desktop",
        last_heartbeat: Optional[datetime] = None,
        daemon_status: str = "unknown",
        daemon_ip: Optional[str] = None,
    ):
        self._id = _id or str(uuid4())
        self.user_id = user_id
        self.self_lead_id = self_lead_id
        self.linkedin_username = linkedin_username
        self.linkedin_password = linkedin_password
        self.subscribe_newsletter = subscribe_newsletter
        self.active = active
        self.is_active = is_active
        self.connect_daily_limit = connect_daily_limit
        self.follow_up_daily_limit = follow_up_daily_limit
        self.legal_accepted = legal_accepted
        self.cookie_data_encrypted = cookie_data_encrypted
        self.newsletter_processed = newsletter_processed
        self.campaign_id = campaign_id
        # Daemon tracking
        self.daemon_last_seen = daemon_last_seen
        self.daemon_version = daemon_version
        self.daemon_platform = daemon_platform
        self.daemon_browser = daemon_browser
        # Session state
        self.is_logged_in = is_logged_in
        self.requires_verification = requires_verification
        self.verification_type = verification_type
        self.session_updated_at = session_updated_at
        self.cookies_updated_at = cookies_updated_at
        # Proxy configuration
        self.proxy_server = proxy_server
        self.proxy_username = proxy_username
        self.proxy_password = proxy_password
        # Execution mode
        self.execution_mode = execution_mode
        self.last_heartbeat = last_heartbeat
        self.daemon_status = daemon_status
        self.daemon_ip = daemon_ip
        self._exhausted: dict[str, date] = {}
        self._user_cache = None  # Cache for lazy-loaded user

    @property
    def cookie_data(self) -> dict | None:
        """Transparent getter for cookie data. Decrypts the stored blob and returns a dict.

        Returns None when no cookie is stored.
        """
        if not self.cookie_data_encrypted:
            return None
        try:
            import json

            from openoutreach.core.crypto import decrypt_text

            decrypted = decrypt_text(self.cookie_data_encrypted)
            return json.loads(decrypted)
        except Exception:
            # If decryption fails, surface None instead of raising to avoid breaking callers
            return None

    @cookie_data.setter
    def cookie_data(self, value: dict | None) -> None:
        """Encrypt and store cookie JSON. Setting to None clears the stored value."""
        if value is None:
            self.cookie_data_encrypted = None
            return
        try:
            import json

            from openoutreach.core.crypto import encrypt_text

            text = json.dumps(value)
            self.cookie_data_encrypted = encrypt_text(text)
        except Exception:
            # Fall back to clearing the field on error
            self.cookie_data_encrypted = None

    @property
    def user(self):
        """Get the User object for this profile (lazy load)."""
        if not self.user_id:
            return None
        if self._user_cache is None:
            from openoutreach.mongodb.models_user import User
            self._user_cache = User.get(self.user_id)
        return self._user_cache

    @property
    def pk(self):
        """Get the primary key."""
        return self._id

    @pk.setter
    def pk(self, value):
        """Set the primary key."""
        self._id = value

    @property
    def id(self):
        """Alias for pk to maintain Django compatibility."""
        return self._id

    def to_dict(self):
        """Convert model instance to dictionary for MongoDB storage."""
        return {
            "_id": self._id,
            "user_id": self.user_id,
            "self_lead_id": self.self_lead_id,
            "linkedin_username": self.linkedin_username,
            "linkedin_password": self.linkedin_password,
            "subscribe_newsletter": self.subscribe_newsletter,
            "active": self.active,
            "is_active": self.is_active,
            "connect_daily_limit": self.connect_daily_limit,
            "follow_up_daily_limit": self.follow_up_daily_limit,
            "legal_accepted": self.legal_accepted,
            "cookie_data_encrypted": self.cookie_data_encrypted,
            "newsletter_processed": self.newsletter_processed,
            "campaign_id": self.campaign_id,
            # Daemon tracking
            "daemon_last_seen": self.daemon_last_seen,
            "daemon_version": self.daemon_version,
            "daemon_platform": self.daemon_platform,
            "daemon_browser": self.daemon_browser,
            # Session state
            "is_logged_in": self.is_logged_in,
            "requires_verification": self.requires_verification,
            "verification_type": self.verification_type,
            "session_updated_at": self.session_updated_at,
            "cookies_updated_at": self.cookies_updated_at,
            # Proxy configuration
            "proxy_server": self.proxy_server,
            "proxy_username": self.proxy_username,
            "proxy_password": self.proxy_password,
            # Execution mode
            "execution_mode": self.execution_mode,
            "last_heartbeat": self.last_heartbeat,
            "daemon_status": self.daemon_status,
            "daemon_ip": self.daemon_ip,
        }

    @classmethod
    def from_dict(cls, data: dict):
        """Create LinkedInProfile instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            user_id=data.get("user_id"),
            self_lead_id=data.get("self_lead_id"),
            linkedin_username=data.get("linkedin_username") or None,
            linkedin_password=data.get("linkedin_password") or None,
            subscribe_newsletter=data.get("subscribe_newsletter", True),
            active=data.get("active", True),
            is_active=data.get("is_active", True),
            connect_daily_limit=data.get("connect_daily_limit", 20),
            follow_up_daily_limit=data.get("follow_up_daily_limit", 25),
            legal_accepted=data.get("legal_accepted", False),
            cookie_data_encrypted=data.get("cookie_data_encrypted"),
            newsletter_processed=data.get("newsletter_processed", False),
            campaign_id=data.get("campaign_id"),
            # Daemon tracking
            daemon_last_seen=data.get("daemon_last_seen"),
            daemon_version=data.get("daemon_version"),
            daemon_platform=data.get("daemon_platform"),
            daemon_browser=data.get("daemon_browser"),
            # Session state
            is_logged_in=data.get("is_logged_in", False),
            requires_verification=data.get("requires_verification", False),
            verification_type=data.get("verification_type"),
            session_updated_at=data.get("session_updated_at"),
            cookies_updated_at=data.get("cookies_updated_at"),
            # Proxy configuration
            proxy_server=data.get("proxy_server"),
            proxy_username=data.get("proxy_username"),
            proxy_password=data.get("proxy_password"),
            # Execution mode
            execution_mode=data.get("execution_mode", "desktop"),
            last_heartbeat=data.get("last_heartbeat"),
            daemon_status=data.get("daemon_status", "unknown"),
            daemon_ip=data.get("daemon_ip"),
        )

    def save(self, update_fields: Optional[list] = None) -> str:
        """Save the profile to MongoDB. If update_fields given, partial update only."""
        collection = get_mongodb_collection("linkedin_profiles")
        if collection is None:
            raise RuntimeError("MongoDB collection 'linkedin_profiles' not available")

        if update_fields:
            field_map = self.to_dict()
            update_doc = {f: field_map[f] for f in update_fields if f in field_map}
            collection.update_one({"_id": self._id}, {"$set": update_doc}, upsert=True)
        else:
            doc = self.to_dict()
            collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
        return self._id

    @classmethod
    def get(cls, profile_id: str) -> Optional["LinkedInProfile"]:
        """Get a LinkedIn profile by ID."""
        collection = get_mongodb_collection("linkedin_profiles")
        if collection is None:
            return None

        data = collection.find_one({"_id": profile_id})
        if data:
            return cls.from_dict(data)
        return None

    @classmethod
    def find_by_user_id(cls, user_id: str) -> list["LinkedInProfile"]:
        """Get all LinkedIn profiles for a user."""
        collection = get_mongodb_collection("linkedin_profiles")
        if collection is None:
            return []
        return [cls.from_dict(d) for d in collection.find({"user_id": user_id})]

    def refresh_from_db(self, fields=None):
        """Refresh the instance from the database."""
        collection = get_mongodb_collection("linkedin_profiles")
        if collection is None:
            return

        data = collection.find_one({"_id": self._id})
        if data:
            if fields:
                for field in fields:
                    if field in data:
                        setattr(self, field, data[field])
            else:
                # Refresh all fields
                for key, value in data.items():
                    if hasattr(self, key):
                        setattr(self, key, value)

    def can_execute(self, action_type: str) -> bool:
        """Check if the action is allowed under the daily rate limit."""
        # Reset exhaustion flag on a new day
        exhausted_date = self._exhausted.get(action_type)
        if exhausted_date is not None and exhausted_date != date.today():
            del self._exhausted[action_type]
        if action_type in self._exhausted:
            return False

        daily_field = _RATE_LIMIT_FIELDS[action_type]
        self.refresh_from_db(fields=[daily_field])

        daily_limit = getattr(self, daily_field)
        if daily_limit is not None and self._daily_count(action_type) >= daily_limit:
            return False

        return True

    def record_action(self, action_type: str, campaign: Campaign, details: dict | None = None) -> None:
        """Persist a rate-limited action with optional descriptive details."""
        action_log = ActionLog(
            linkedin_profile_id=self._id,
            campaign_id=campaign.pk if campaign else "",
            action_type=action_type,
            details=details or {},
        )
        action_log.save()

    def mark_exhausted(self, action_type: str) -> None:
        """Mark the action type as externally exhausted for today."""
        self._exhausted[action_type] = date.today()
        logger.warning("Rate limit: %s externally exhausted for today", action_type)

    def _daily_count(self, action_type: str) -> int:
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        collection = get_mongodb_collection("action_logs")
        if collection is None:
            return 0

        return collection.count_documents({
            "linkedin_profile_id": self._id,
            "action_type": action_type,
            "created_at": {"$gte": today_start},
        })

    def __str__(self):
        return f"LinkedInProfile({self.linkedin_username})"


class SearchKeyword:
    """MongoDB-based search keyword model."""

    objects: ClassVar[SearchKeywordManager]

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

    @property
    def pk(self):
        """Get the primary key."""
        return self._id

    @pk.setter
    def pk(self, value):
        """Set the primary key."""
        self._id = value

    @property
    def id(self):
        """Alias for pk to maintain Django compatibility."""
        return self._id

    def to_dict(self):
        """Convert model instance to dictionary for MongoDB storage."""
        return {
            "_id": self._id,
            "campaign_id": self.campaign_id,
            "keyword": self.keyword,
            "used": self.used,
            "used_at": self.used_at,
        }

    @classmethod
    def from_dict(cls, data: dict):
        """Create SearchKeyword instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            campaign_id=data.get("campaign_id", ""),
            keyword=data.get("keyword", ""),
            used=data.get("used", False),
            used_at=data.get("used_at"),
        )

    def save(self) -> str:
        """Save the keyword to MongoDB."""
        collection = get_mongodb_collection("search_keywords")
        if collection is None:
            raise RuntimeError("MongoDB collection 'search_keywords' not available")

        doc = self.to_dict()
        result = collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
        return str(result.upserted_id or self._id)

    @classmethod
    def exists_unused(cls, campaign_id: str) -> bool:
        """Check if there are unused keywords for a campaign."""
        collection = get_mongodb_collection("search_keywords")
        if collection is None:
            return False
        return collection.count_documents({"campaign_id": campaign_id, "used": False}) > 0

    @classmethod
    def get_used_keywords(cls, campaign_id: str) -> list[str]:
        """Get list of used keywords for a campaign."""
        collection = get_mongodb_collection("search_keywords")
        if collection is None:
            return []
        docs = collection.find({"campaign_id": campaign_id, "used": True})
        return [doc.get("keyword", "") for doc in docs]

    @classmethod
    def get_next_unused(cls, campaign_id: str) -> Optional["SearchKeyword"]:
        """Get the next unused keyword for a campaign."""
        collection = get_mongodb_collection("search_keywords")
        if collection is None:
            return None
        data = collection.find_one({"campaign_id": campaign_id, "used": False})
        return cls.from_dict(data) if data else None

    def __str__(self):
        return self.keyword


class ActionLog:
    """MongoDB-based action log model."""

    objects: ClassVar[ActionLogManager]

    class ActionType:
        CONNECT = "connect"
        CHECK_PENDING = "check_pending"
        FOLLOW_UP = "follow_up"
        SEND_MANUAL_MESSAGE = "send_manual_message"
        CAMPAIGN_PAUSED = "campaign_paused"
        CAMPAIGN_STARTED = "campaign_started"
        LEAD_DISCOVERED = "lead_discovered"
        LEAD_QUALIFIED = "lead_qualified"
        LEAD_DISQUALIFIED = "lead_disqualified"

    def __init__(
        self,
        _id: Optional[str] = None,
        linkedin_profile_id: Optional[str] = None,
        campaign_id: str = "",
        action_type: str = "",
        created_at: Optional[datetime] = None,
        details: Optional[dict] = None,
        status: str = "",
        error_message: str = "",
        duration_ms: Optional[float] = None,
    ):
        self._id = _id or str(uuid4())
        self.linkedin_profile_id = linkedin_profile_id
        self.campaign_id = campaign_id
        self.action_type = action_type
        self.created_at = created_at or datetime.utcnow()
        self.details = details or {}
        self.status = status
        self.error_message = error_message
        self.duration_ms = duration_ms

    @property
    def pk(self):
        """Get the primary key."""
        return self._id

    @pk.setter
    def pk(self, value):
        """Set the primary key."""
        self._id = value

    @property
    def id(self):
        """Alias for pk to maintain Django compatibility."""
        return self._id

    def to_dict(self):
        """Convert model instance to dictionary for MongoDB storage."""
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
        }

    @classmethod
    def from_dict(cls, data: dict):
        """Create ActionLog instance from MongoDB document."""
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
        )

    def save(self) -> str:
        """Save the action log to MongoDB."""
        collection = get_mongodb_collection("action_logs")
        if collection is None:
            raise RuntimeError("MongoDB collection 'action_logs' not available")

        doc = self.to_dict()
        result = collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
        return str(result.upserted_id or self._id)

    def __str__(self):
        return f"{self.action_type} at {self.created_at}"



# Manager classes for MongoDB queries


class LinkedInProfileManager:
    """Manager for LinkedInProfile queries."""

    def __init__(self):
        self.collection = None

    def _get_collection(self):
        if self.collection is None:
            self.collection = get_mongodb_collection("linkedin_profiles")
        return self.collection

    def all(self):
        """Get all LinkedIn profiles."""
        collection = self._get_collection()
        if collection is None:
            return []

        try:
            profiles = []
            for data in collection.find():
                profiles.append(LinkedInProfile.from_dict(data))
            return profiles
        except Exception as e:
            logger.error(f"Failed to get all LinkedIn profiles: {e}")
            return []

    def filter(self, **kwargs):
        """Filter LinkedIn profiles by criteria."""
        collection = self._get_collection()
        if collection is None:
            return []

        try:
            profiles = []
            for data in collection.find(kwargs):
                profiles.append(LinkedInProfile.from_dict(data))
            return profiles
        except Exception as e:
            logger.error(f"Failed to filter LinkedIn profiles: {e}")
            return []

    def get(self, **kwargs):
        """Get a single LinkedIn profile by criteria."""
        collection = self._get_collection()
        if collection is None:
            return None

        try:
            data = collection.find_one(kwargs)
            if data:
                return LinkedInProfile.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get LinkedIn profile: {e}")
            return None

    def create(self, **kwargs):
        """Create a new LinkedIn profile."""
        profile = LinkedInProfile(**kwargs)
        profile.save()
        return profile


class SearchKeywordManager:
    """Manager for SearchKeyword queries."""

    def __init__(self):
        self.collection = None

    def _get_collection(self):
        if self.collection is None:
            self.collection = get_mongodb_collection("search_keywords")
        return self.collection

    def all(self):
        """Get all search keywords."""
        collection = self._get_collection()
        if collection is None:
            return []

        try:
            keywords = []
            for data in collection.find():
                keywords.append(SearchKeyword.from_dict(data))
            return keywords
        except Exception as e:
            logger.error(f"Failed to get all search keywords: {e}")
            return []

    def filter(self, **kwargs):
        """Filter search keywords by criteria."""
        collection = self._get_collection()
        if collection is None:
            return []

        try:
            keywords = []
            for data in collection.find(kwargs):
                keywords.append(SearchKeyword.from_dict(data))
            return keywords
        except Exception as e:
            logger.error(f"Failed to filter search keywords: {e}")
            return []

    def get(self, **kwargs):
        """Get a single search keyword by criteria."""
        collection = self._get_collection()
        if collection is None:
            return None

        try:
            data = collection.find_one(kwargs)
            if data:
                return SearchKeyword.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get search keyword: {e}")
            return None

    def create(self, **kwargs):
        """Create a new search keyword."""
        keyword = SearchKeyword(**kwargs)
        keyword.save()
        return keyword


class ActionLogManager:
    """Manager for ActionLog queries."""

    def __init__(self):
        self.collection = None

    def _get_collection(self):
        if self.collection is None:
            self.collection = get_mongodb_collection("action_logs")
        return self.collection

    def all(self):
        """Get all action logs."""
        collection = self._get_collection()
        if collection is None:
            return []

        try:
            logs = []
            for data in collection.find():
                logs.append(ActionLog.from_dict(data))
            return logs
        except Exception as e:
            logger.error(f"Failed to get all action logs: {e}")
            return []

    def filter(self, **kwargs):
        """Filter action logs by criteria."""
        collection = self._get_collection()
        if collection is None:
            return []

        try:
            # Handle Django-style lookups
            query = {}
            for key, value in kwargs.items():
                if "__gte" in key:
                    field = key.replace("__gte", "")
                    query[field] = {"$gte": value}
                elif "__lte" in key:
                    field = key.replace("__lte", "")
                    query[field] = {"$lte": value}
                elif "__gt" in key:
                    field = key.replace("__gt", "")
                    query[field] = {"$gt": value}
                elif "__lt" in key:
                    field = key.replace("__lt", "")
                    query[field] = {"$lt": value}
                else:
                    query[key] = value

            logs = []
            for data in collection.find(query):
                logs.append(ActionLog.from_dict(data))
            return logs
        except Exception as e:
            logger.error(f"Failed to filter action logs: {e}")
            return []

    def count(self):
        """Count total action logs."""
        collection = self._get_collection()
        if collection is None:
            return 0

        try:
            return collection.count_documents({})
        except Exception as e:
            logger.error(f"Failed to count action logs: {e}")
            return 0

    def get(self, **kwargs):
        """Get a single action log by criteria."""
        collection = self._get_collection()
        if collection is None:
            return None

        try:
            data = collection.find_one(kwargs)
            if data:
                return ActionLog.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get action log: {e}")
            return None

    def create(self, **kwargs):
        """Create a new action log."""
        log = ActionLog(**kwargs)
        log.save()
        return log


# Assign managers as class attributes
LinkedInProfile.objects = LinkedInProfileManager()
SearchKeyword.objects = SearchKeywordManager()
ActionLog.objects = ActionLogManager()
