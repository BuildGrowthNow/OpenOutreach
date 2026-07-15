# openoutreach/core/models.py
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional, Dict, Any, List
from uuid import uuid4

if TYPE_CHECKING:
    from openoutreach.crm.models import Deal
    from openoutreach.linkedin.models import CampaignStateGraph, SearchKeyword


class SiteConfig:
    """Singleton model for global site configuration (LLM keys, etc.)."""

    class LLMProvider:
        OPENAI = "openai"
        ANTHROPIC = "anthropic"
        GOOGLE = "google"
        GROQ = "groq"
        MISTRAL = "mistral"
        COHERE = "cohere"
        OPENAI_COMPATIBLE = "openai_compatible"

    class AggressivenessPreset:
        VERY_SLOW = "very_slow"
        SLOW = "slow"
        AVERAGE = "average"
        AGGRESSIVE = "aggressive"
        VERY_AGGRESSIVE = "very_aggressive"

    def __init__(
        self,
        _id: str = "1",
        llm_provider: str = LLMProvider.OPENAI,
        llm_api_key: str = "",
        ai_model: str = "",
        llm_api_base: str = "",
        ai_writing_style: str = "",
        ai_say_rules: str = "",
        ai_avoid_rules: str = "",
        finder_api_key: str = "",
        linkedin_username: str = "",
        linkedin_campaign: str = "",
        enable_smart_rate_limiting: bool = False,
        aggressiveness_preset: str = AggressivenessPreset.AVERAGE,
        daily_connection_limit: int = 20,
        daily_follow_up_limit: int = 25,
        velocity: int = 20,
        bettercontact_api_key: str = "",
        contacts_api_token: str = "",
        contacts_api_url: str = "",
        enable_active_hours: bool = True,
        active_start_hour: int = 9,
        active_end_hour: int = 19,
        active_timezone: str = "UTC",
        active_days: str = "1,2,3,4,5",
    ):
        self._id = _id
        self.llm_provider = llm_provider
        self.llm_api_key = llm_api_key
        self.ai_model = ai_model
        self.llm_api_base = llm_api_base
        self.ai_writing_style = ai_writing_style
        self.ai_say_rules = ai_say_rules
        self.ai_avoid_rules = ai_avoid_rules
        self.finder_api_key = finder_api_key
        self.linkedin_username = linkedin_username
        self.linkedin_campaign = linkedin_campaign
        self.enable_smart_rate_limiting = enable_smart_rate_limiting
        self.aggressiveness_preset = aggressiveness_preset
        self.daily_connection_limit = daily_connection_limit
        self.daily_follow_up_limit = daily_follow_up_limit
        self.velocity = velocity
        self.bettercontact_api_key = bettercontact_api_key
        self.contacts_api_token = contacts_api_token
        self.contacts_api_url = contacts_api_url
        self.enable_active_hours = enable_active_hours
        self.active_start_hour = active_start_hour
        self.active_end_hour = active_end_hour
        self.active_timezone = active_timezone
        self.active_days = active_days

    def __str__(self):
        return "Site Configuration"

    @property
    def pk(self):
        return self._id

    @pk.setter
    def pk(self, value):
        self._id = value

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary for MongoDB storage."""
        return {
            "_id": self._id,
            "llm_provider": self.llm_provider,
            "llm_api_key": self.llm_api_key,
            "ai_model": self.ai_model,
            "llm_api_base": self.llm_api_base,
            "ai_writing_style": self.ai_writing_style,
            "ai_say_rules": self.ai_say_rules,
            "ai_avoid_rules": self.ai_avoid_rules,
            "finder_api_key": self.finder_api_key,
            "linkedin_username": self.linkedin_username,
            "linkedin_campaign": self.linkedin_campaign,
            "enable_smart_rate_limiting": self.enable_smart_rate_limiting,
            "aggressiveness_preset": self.aggressiveness_preset,
            "daily_connection_limit": self.daily_connection_limit,
            "daily_follow_up_limit": self.daily_follow_up_limit,
            "velocity": self.velocity,
            "bettercontact_api_key": self.bettercontact_api_key,
            "contacts_api_token": self.contacts_api_token,
            "contacts_api_url": self.contacts_api_url,
            "enable_active_hours": self.enable_active_hours,
            "active_start_hour": self.active_start_hour,
            "active_end_hour": self.active_end_hour,
            "active_timezone": self.active_timezone,
            "active_days": self.active_days,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SiteConfig":
        """Create SiteConfig instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id", "1")),
            llm_provider=data.get("llm_provider", cls.LLMProvider.OPENAI),
            llm_api_key=data.get("llm_api_key", ""),
            ai_model=data.get("ai_model", ""),
            llm_api_base=data.get("llm_api_base", ""),
            ai_writing_style=data.get("ai_writing_style", ""),
            ai_say_rules=data.get("ai_say_rules", ""),
            ai_avoid_rules=data.get("ai_avoid_rules", ""),
            finder_api_key=data.get("finder_api_key", ""),
            linkedin_username=data.get("linkedin_username", ""),
            linkedin_campaign=data.get("linkedin_campaign", ""),
            enable_smart_rate_limiting=data.get("enable_smart_rate_limiting", False),
            aggressiveness_preset=data.get("aggressiveness_preset", cls.AggressivenessPreset.AVERAGE),
            daily_connection_limit=data.get("daily_connection_limit", 20),
            daily_follow_up_limit=data.get("daily_follow_up_limit", 25),
            velocity=data.get("velocity", 20),
            bettercontact_api_key=data.get("bettercontact_api_key", ""),
            contacts_api_token=data.get("contacts_api_token", ""),
            contacts_api_url=data.get("contacts_api_url", ""),
            enable_active_hours=data.get("enable_active_hours", True),
            active_start_hour=data.get("active_start_hour", 9),
            active_end_hour=data.get("active_end_hour", 19),
            active_timezone=data.get("active_timezone", "UTC"),
            active_days=data.get("active_days", "1,2,3,4,5"),
        )

    def save(self) -> str:
        """Save the site config to MongoDB."""
        from openoutreach.mongodb.connection import get_mongodb_collection

        collection = get_mongodb_collection("site_config")
        if collection is None:
            raise RuntimeError("MongoDB collection 'site_config' not available")

        # Singleton pattern: always use _id="1"
        self._id = "1"
        doc = self.to_dict()
        result = collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
        return str(result.upserted_id or self._id)

    @classmethod
    def load(cls) -> "SiteConfig":
        """Load the singleton site config from MongoDB."""
        from openoutreach.mongodb.connection import get_mongodb_collection

        collection = get_mongodb_collection("site_config")
        if collection is None:
            # Return default instance if MongoDB not available
            return cls()

        data = collection.find_one({"_id": "1"})
        if data:
            return cls.from_dict(data)

        # Create and save default instance
        config = cls()
        config.save()
        return config

    @classmethod
    def objects(cls):
        """Provide basic objects interface for compatibility."""
        return SiteConfigManager()


class SiteConfigManager:
    """Manager for SiteConfig singleton."""

    def get_or_create(self, pk=None, **kwargs):
        """Get or create the singleton config."""
        config = SiteConfig.load()
        return config, False


class CampaignTemplate:
    """Template for creating campaigns with predefined settings."""

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
        created_by_id: Optional[str] = None,  # User ID reference
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
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    @property
    def id(self):
        return self._id

    @property
    def pk(self):
        return self._id

    @pk.setter
    def pk(self, value):
        self._id = value

    def __str__(self) -> str:
        return self.name

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary for MongoDB storage."""
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
        """Create CampaignTemplate instance from MongoDB document."""
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
            created_by_id=data.get("created_by_id"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    def save(self) -> str:
        """Save the campaign template to MongoDB."""
        from openoutreach.mongodb.connection import get_mongodb_collection

        collection = get_mongodb_collection("campaign_templates")
        if collection is None:
            raise RuntimeError("MongoDB collection 'campaign_templates' not available")

        self.updated_at = datetime.utcnow()
        doc = self.to_dict()
        result = collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
        return str(result.upserted_id or self._id)

    @classmethod
    def objects(cls):
        """Provide basic objects interface for compatibility."""
        return CampaignTemplateManager()


class CampaignTemplateManager:
    """Manager for CampaignTemplate queries."""

    def __init__(self):
        self.collection = None

    def _get_collection(self):
        from openoutreach.mongodb.connection import get_mongodb_collection

        if self.collection is None:
            self.collection = get_mongodb_collection("campaign_templates")
        return self.collection

    def all(self) -> List[CampaignTemplate]:
        """Get all campaign templates."""
        collection = self._get_collection()
        if collection is None:
            return []

        templates = []
        for data in collection.find().sort("created_at", -1):
            templates.append(CampaignTemplate.from_dict(data))
        return templates

    def filter(self, **kwargs) -> List[CampaignTemplate]:
        """Filter campaign templates by criteria."""
        collection = self._get_collection()
        if collection is None:
            return []

        templates = []
        for data in collection.find(kwargs).sort("created_at", -1):
            templates.append(CampaignTemplate.from_dict(data))
        return templates

    def get(self, **kwargs) -> Optional[CampaignTemplate]:
        """Get a single campaign template."""
        collection = self._get_collection()
        if collection is None:
            return None

        data = collection.find_one(kwargs)
        if data:
            return CampaignTemplate.from_dict(data)
        return None


# Campaign and CampaignManager are now in mongodb.models
# Import them for backward compatibility
from openoutreach.mongodb.models import Campaign, CampaignManager


# NOTE: TrackedLink is now in openoutreach.mongodb.models


class Task:
    """Task model for MongoDB."""

    class TaskType:
        CONNECT = "connect"
        CHECK_PENDING = "check_pending"
        FOLLOW_UP = "follow_up"
        SEND_MANUAL_MESSAGE = "send_manual_message"

    class Status:
        PENDING = "pending"
        RUNNING = "running"
        COMPLETED = "completed"
        FAILED = "failed"

    def __init__(
        self,
        _id: Optional[str] = None,
        task_type: str = TaskType.CONNECT,
        status: str = Status.PENDING,
        scheduled_at: Optional[datetime] = None,
        payload: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.task_type = task_type
        self.status = status
        self.scheduled_at = scheduled_at or datetime.utcnow()
        self.payload = payload or {}
        self.created_at = created_at or datetime.utcnow()
        self.started_at = started_at
        self.completed_at = completed_at

    @property
    def id(self):
        return self._id

    @property
    def pk(self):
        return self._id

    @pk.setter
    def pk(self, value):
        self._id = value

    def __str__(self) -> str:
        return f"{self.task_type} [{self.status}] scheduled={self.scheduled_at}"

    def get_error_message(self) -> str | None:
        """Get the last error message from payload if available."""
        return (self.payload or {}).get("last_error")

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary for MongoDB storage."""
        return {
            "_id": self._id,
            "task_type": self.task_type,
            "status": self.status,
            "scheduled_at": self.scheduled_at,
            "payload": self.payload,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Create Task instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            task_type=data.get("task_type", cls.TaskType.CONNECT),
            status=data.get("status", cls.Status.PENDING),
            scheduled_at=data.get("scheduled_at"),
            payload=data.get("payload", {}),
            created_at=data.get("created_at"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
        )

    def save(self, update_fields: Optional[List[str]] = None) -> str:
        """Save the task to MongoDB."""
        from openoutreach.mongodb.connection import get_mongodb_collection

        collection = get_mongodb_collection("tasks")
        if collection is None:
            raise RuntimeError("MongoDB collection 'tasks' not available")

        doc = self.to_dict()

        # If update_fields specified, only update those fields
        if update_fields:
            update_doc = {field: doc[field] for field in update_fields if field in doc}
            result = collection.update_one({"_id": self._id}, {"$set": update_doc})
        else:
            result = collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)

        return str(result.upserted_id or self._id)

    def mark_running(self):
        """Mark task as running."""
        self.status = self.Status.RUNNING
        self.started_at = datetime.utcnow()
        self.save(update_fields=["status", "started_at"])

    def mark_completed(self):
        """Mark task as completed."""
        self.status = self.Status.COMPLETED
        self.completed_at = datetime.utcnow()
        self.save(update_fields=["status", "completed_at"])

    def mark_failed(self, error_message: str | None = None):
        """Mark the task as failed. This is a terminal state.

        Args:
            error_message: Optional error message to store in payload for debugging.
                          Message will be stored in payload['error'].
        """
        self.status = self.Status.FAILED
        # Store error details in payload for debugging
        if error_message:
            updated_payload = dict(self.payload or {})
            updated_payload["last_error"] = error_message[:500]  # Truncate to avoid huge payloads
            self.payload = updated_payload
        self.save(update_fields=["status", "payload"])

    @classmethod
    def objects(cls):
        """Provide basic objects interface for compatibility."""
        return TaskManager()


class TaskManager:
    """Manager for Task queries."""

    def __init__(self):
        self.collection = None

    def _get_collection(self):
        from openoutreach.mongodb.connection import get_mongodb_collection

        if self.collection is None:
            self.collection = get_mongodb_collection("tasks")
        return self.collection

    def all(self) -> List[Task]:
        """Get all tasks."""
        collection = self._get_collection()
        if collection is None:
            return []

        tasks = []
        for data in collection.find():
            tasks.append(Task.from_dict(data))
        return tasks

    def filter(self, **kwargs) -> List[Task]:
        """Filter tasks by criteria."""
        collection = self._get_collection()
        if collection is None:
            return []

        tasks = []
        for data in collection.find(kwargs):
            tasks.append(Task.from_dict(data))
        return tasks

    def pending(self) -> List[Task]:
        """Get pending tasks ordered by scheduled_at."""
        collection = self._get_collection()
        if collection is None:
            return []

        tasks = []
        for data in collection.find({"status": Task.Status.PENDING}).sort("scheduled_at", 1):
            tasks.append(Task.from_dict(data))
        return tasks

    def claim_next(self) -> Optional[Task]:
        """Claim the next pending task that's due."""
        collection = self._get_collection()
        if collection is None:
            return None

        now = datetime.utcnow()
        data = collection.find_one(
            {"status": Task.Status.PENDING, "scheduled_at": {"$lte": now}},
            sort=[("scheduled_at", 1)]
        )
        if data:
            return Task.from_dict(data)
        return None

    def seconds_to_next(self) -> float | None:
        """Seconds until the next pending task, or None if queue is empty."""
        collection = self._get_collection()
        if collection is None:
            return None

        data = collection.find_one(
            {"status": Task.Status.PENDING},
            {"scheduled_at": 1},
            sort=[("scheduled_at", 1)]
        )
        if data is None:
            return None

        next_task = Task.from_dict(data)
        now = datetime.utcnow()
        return max((next_task.scheduled_at - now).total_seconds(), 0)

    def get(self, **kwargs) -> Optional[Task]:
        """Get a single task."""
        collection = self._get_collection()
        if collection is None:
            return None

        data = collection.find_one(kwargs)
        if data:
            return Task.from_dict(data)
        return None

    def create(self, **kwargs) -> Task:
        """Create a new task."""
        task = Task(**kwargs)
        task.save()
        return task
