# openoutreach/linkedin/models/__init__.py
# Main models for the LinkedIn app

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional
from uuid import uuid4

from openoutreach.core.models import Campaign
from openoutreach.mongodb.connection import get_mongodb_collection

from .health import CampaignHealthMetric, HealthAlert, RecoveryAction
from .rate_limits import (
    EngagementLevel,
    LinkedInDetectability,
    RateLimitWarning,
    SmartRateLimitContext,
)
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

    def __init__(
        self,
        _id: Optional[str] = None,
        user_id: Optional[str] = None,
        self_lead_id: Optional[str] = None,
        linkedin_username: str = "",
        linkedin_password: str = "",
        subscribe_newsletter: bool = True,
        active: bool = True,
        connect_daily_limit: int = 20,
        follow_up_daily_limit: int = 25,
        legal_accepted: bool = False,
        cookie_data_encrypted: Optional[str] = None,
        newsletter_processed: bool = False,
        campaign_id: Optional[str] = None,
    ):
        self._id = _id or str(uuid4())
        self.user_id = user_id
        self.self_lead_id = self_lead_id
        self.linkedin_username = linkedin_username
        self.linkedin_password = linkedin_password
        self.subscribe_newsletter = subscribe_newsletter
        self.active = active
        self.connect_daily_limit = connect_daily_limit
        self.follow_up_daily_limit = follow_up_daily_limit
        self.legal_accepted = legal_accepted
        self.cookie_data_encrypted = cookie_data_encrypted
        self.newsletter_processed = newsletter_processed
        self.campaign_id = campaign_id
        self._exhausted: dict[str, date] = {}

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
            "connect_daily_limit": self.connect_daily_limit,
            "follow_up_daily_limit": self.follow_up_daily_limit,
            "legal_accepted": self.legal_accepted,
            "cookie_data_encrypted": self.cookie_data_encrypted,
            "newsletter_processed": self.newsletter_processed,
            "campaign_id": self.campaign_id,
        }

    @classmethod
    def from_dict(cls, data: dict):
        """Create LinkedInProfile instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            user_id=data.get("user_id"),
            self_lead_id=data.get("self_lead_id"),
            linkedin_username=data.get("linkedin_username", ""),
            linkedin_password=data.get("linkedin_password", ""),
            subscribe_newsletter=data.get("subscribe_newsletter", True),
            active=data.get("active", True),
            connect_daily_limit=data.get("connect_daily_limit", 20),
            follow_up_daily_limit=data.get("follow_up_daily_limit", 25),
            legal_accepted=data.get("legal_accepted", False),
            cookie_data_encrypted=data.get("cookie_data_encrypted"),
            newsletter_processed=data.get("newsletter_processed", False),
            campaign_id=data.get("campaign_id"),
        )

    def save(self) -> str:
        """Save the profile to MongoDB."""
        collection = get_mongodb_collection("linkedin_profiles")
        if collection is None:
            raise RuntimeError("MongoDB collection 'linkedin_profiles' not available")

        doc = self.to_dict()
        result = collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
        return str(result.upserted_id or self._id)

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
            campaign_id=campaign.pk if campaign else None,
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

    @classmethod
    def objects(cls):
        """Get the LinkedInProfileManager for querying profiles."""
        return LinkedInProfileManager()


class SearchKeyword:
    """MongoDB-based search keyword model."""

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

    def __str__(self):
        return self.keyword

    @classmethod
    def objects(cls):
        """Get the SearchKeywordManager for querying keywords."""
        return SearchKeywordManager()


class ActionLog:
    """MongoDB-based action log model."""

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

    @classmethod
    def objects(cls):
        """Get the ActionLogManager for querying action logs."""
        return ActionLogManager()


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
