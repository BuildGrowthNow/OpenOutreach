"""Smart Rate Limiting models with context awareness - MongoDB version."""

from __future__ import annotations

from datetime import datetime, timezone as tz
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import uuid4

from openoutreach.mongodb.connection import get_mongodb_collection


class EngagementLevel(Enum):
    """Lead engagement level for rate limiting decisions."""
    COLD = "cold"
    HOT = "hot"
    VERIFIED_WARM = "verified_warm"
    ACTIVELY_ENGAGED = "actively_engaged"


class LinkedInDetectability(Enum):
    """LinkedIn detection risk level."""
    NORMAL = "normal"
    SUSPICIOUS = "suspicious"
    WARNING = "warning"
    CRITICAL = "critical"


class SmartRateLimitContext:
    """
    MongoDB model for contextual rate limiting data.
    One per LinkedInProfile. Stores dynamic limits based on:
    - Time of day/week patterns
    - Detectability score (0-100, higher = more suspicious)
    - Action patterns and streaks
    - Per-campaign context
    """

    def __init__(
        self,
        _id: Optional[str] = None,
        linkedin_profile_id: str = "",
        time_of_day_limit_multiplier: float = 1.0,
        day_of_week_limit_multiplier: float = 1.0,
        detectability_score: int = 50,
        last_detectability_update: Optional[datetime] = None,
        last_action_type: str = "",
        last_action_at: Optional[datetime] = None,
        consecutive_actions: int = 0,
        action_streak_reset_at: Optional[datetime] = None,
        campaign_context: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.linkedin_profile_id = linkedin_profile_id
        self.time_of_day_limit_multiplier = time_of_day_limit_multiplier
        self.day_of_week_limit_multiplier = day_of_week_limit_multiplier
        self.detectability_score = max(0, min(100, detectability_score))
        self.last_detectability_update = last_detectability_update or datetime.now(tz.utc)
        self.last_action_type = last_action_type
        self.last_action_at = last_action_at
        self.consecutive_actions = consecutive_actions
        self.action_streak_reset_at = action_streak_reset_at
        self.campaign_context = campaign_context or {}
        self.created_at = created_at or datetime.now(tz.utc)
        self.updated_at = updated_at or datetime.now(tz.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to MongoDB document."""
        return {
            "_id": self._id,
            "linkedin_profile_id": self.linkedin_profile_id,
            "time_of_day_limit_multiplier": self.time_of_day_limit_multiplier,
            "day_of_week_limit_multiplier": self.day_of_week_limit_multiplier,
            "detectability_score": self.detectability_score,
            "last_detectability_update": self.last_detectability_update,
            "last_action_type": self.last_action_type,
            "last_action_at": self.last_action_at,
            "consecutive_actions": self.consecutive_actions,
            "action_streak_reset_at": self.action_streak_reset_at,
            "campaign_context": self.campaign_context,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SmartRateLimitContext":
        """Create instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            linkedin_profile_id=data.get("linkedin_profile_id", ""),
            time_of_day_limit_multiplier=data.get("time_of_day_limit_multiplier", 1.0),
            day_of_week_limit_multiplier=data.get("day_of_week_limit_multiplier", 1.0),
            detectability_score=data.get("detectability_score", 50),
            last_detectability_update=data.get("last_detectability_update"),
            last_action_type=data.get("last_action_type", ""),
            last_action_at=data.get("last_action_at"),
            consecutive_actions=data.get("consecutive_actions", 0),
            action_streak_reset_at=data.get("action_streak_reset_at"),
            campaign_context=data.get("campaign_context", {}),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    def save(self) -> str:
        """Save to MongoDB."""
        collection = get_mongodb_collection("smart_rate_limit_contexts")
        if collection is None:
            raise RuntimeError("MongoDB collection not available")

        self.updated_at = datetime.now(tz.utc)
        doc = self.to_dict()
        collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
        return self._id

    @classmethod
    def get_by_profile(cls, linkedin_profile_id: str) -> Optional["SmartRateLimitContext"]:
        """Get context for a LinkedIn profile."""
        collection = get_mongodb_collection("smart_rate_limit_contexts")
        if collection is None:
            return None

        data = collection.find_one({"linkedin_profile_id": linkedin_profile_id})
        return cls.from_dict(data) if data else None

    @classmethod
    def get_or_create(cls, linkedin_profile_id: str) -> "SmartRateLimitContext":
        """Get or create context for a LinkedIn profile."""
        existing = cls.get_by_profile(linkedin_profile_id)
        if existing:
            return existing

        context = cls(linkedin_profile_id=linkedin_profile_id)
        context.save()
        return context

    def get_effective_limit(self, action_type: str, campaign=None) -> int:
        """Calculate effective rate limit based on all context factors."""
        base_limit = self._get_base_limit(action_type)

        # Apply multipliers
        multipliers = [
            self.time_of_day_limit_multiplier,
            self.day_of_week_limit_multiplier,
            self._detectability_multiplier(),
        ]

        effective = base_limit
        for m in multipliers:
            effective = int(effective * m)

        # Reduce if campaign-specific limits are lower
        if campaign and str(campaign.id) in self.campaign_context:
            campaign_limit = self.campaign_context[str(campaign.id)].get("limit", float("inf"))
            effective = min(effective, int(campaign_limit))

        return max(1, effective)  # At least 1 action allowed

    def _get_base_limit(self, action_type: str) -> int:
        """Get base limit for action type."""
        base_limits = {
            "connect": 30,
            "follow_up": 40,
            "message": 50,
            "view_profile": 60,
        }
        return base_limits.get(action_type, 30)

    def _detectability_multiplier(self) -> float:
        """Calculate multiplier based on detectability score (0-100)."""
        if self.detectability_score >= 80:
            return 0.3  # Very suspicious - slow way down
        elif self.detectability_score >= 60:
            return 0.6  # Suspicious - reduce activity
        elif self.detectability_score >= 40:
            return 0.8  # Slightly elevated - be cautious
        else:
            return 1.0  # Normal - full speed

    def record_action(self, action_type: str):
        """Record an action and update context."""
        now = datetime.now(tz.utc)

        # Update time-based multipliers
        self._update_time_context(now)

        # Track consecutive actions
        if self.last_action_type == action_type:
            self.consecutive_actions += 1

            # Rapid consecutive same-type actions = suspicious
            if self.consecutive_actions >= 5:
                self.detectability_score = min(100, self.detectability_score + 10)
            elif self.consecutive_actions >= 10:
                # Too many consecutive same-type actions = very suspicious
                self.detectability_score = min(100, self.detectability_score + 15)
        else:
            self.consecutive_actions = 1

        # Decay detectability slowly over time
        self.detectability_score = max(0, self.detectability_score - 1)

        self.last_action_type = action_type
        self.last_action_at = now
        self.save()

    def _update_time_context(self, now: datetime):
        """Update multipliers based on time of day and day of week."""
        hour = now.hour
        day_of_week = now.weekday()  # Monday = 0, Sunday = 6

        # Time of day multiplier
        if 9 <= hour <= 17:  # Business hours
            self.time_of_day_limit_multiplier = 1.0
        elif 7 <= hour <= 9 or 17 <= hour <= 20:  # Early/late
            self.time_of_day_limit_multiplier = 0.8
        elif 20 <= hour or hour <= 6:  # Night
            self.time_of_day_limit_multiplier = 0.3

        # Day of week multiplier
        if day_of_week >= 5:  # Weekend
            self.day_of_week_limit_multiplier = 0.5
        elif day_of_week == 6:  # Sunday
            self.day_of_week_limit_multiplier = 0.2
        else:  # Weekday
            self.day_of_week_limit_multiplier = 1.0

        # Friday effect (people wrap up week)
        if day_of_week == 4:  # Friday
            self.day_of_week_limit_multiplier = 0.8

    def update_detectability(self, score_delta: int):
        """Adjust detectability score (positive = more suspicious)."""
        self.detectability_score = max(0, min(100, self.detectability_score + score_delta))
        self.last_detectability_update = datetime.now(tz.utc)
        self.save()

    def get_engagement_level(self, lead) -> EngagementLevel:
        """Determine engagement level for a specific lead."""
        from openoutreach.mongodb.models import Deal

        # Find deal for this lead
        deal = Deal.get_by_lead(lead._id)
        if not deal:
            return EngagementLevel.COLD

        # Check engagement signals
        if deal.outcome == "converted":
            return EngagementLevel.VERIFIED_WARM

        # Days since first connection
        if deal.creation_date:
            days_since = (datetime.now(tz.utc) - deal.creation_date).days
            if days_since < 3:
                return EngagementLevel.HOT

        # Response history
        if deal.outcome in ["not_interested", "wrong_fit"]:
            return EngagementLevel.COLD

        # Connection accepted, no response yet
        if deal.state == "CONNECTED":
            if deal.creation_date:
                hours_since = (datetime.now(tz.utc) - deal.creation_date).total_seconds() / 3600
                if hours_since < 24:
                    return EngagementLevel.ACTIVELY_ENGAGED

        return EngagementLevel.VERIFIED_WARM

    def get_detectability_level(self) -> LinkedInDetectability:
        """Get current detectability risk level."""
        if self.detectability_score >= 80:
            return LinkedInDetectability.CRITICAL
        elif self.detectability_score >= 60:
            return LinkedInDetectability.WARNING
        elif self.detectability_score >= 40:
            return LinkedInDetectability.SUSPICIOUS
        else:
            return LinkedInDetectability.NORMAL


class RateLimitWarning:
    """Warning log for rate limit violations."""

    def __init__(
        self,
        _id: Optional[str] = None,
        linkedin_profile_id: str = "",
        action_type: str = "",
        limit_type: str = "",
        limit_exceeded: int = 0,
        actual_count: int = 0,
        warning_level: str = "low",
        at_time: Optional[datetime] = None,
        resolved: bool = False,
    ):
        self._id = _id or str(uuid4())
        self.linkedin_profile_id = linkedin_profile_id
        self.action_type = action_type
        self.limit_type = limit_type
        self.limit_exceeded = limit_exceeded
        self.actual_count = actual_count
        self.warning_level = warning_level  # low, medium, high
        self.at_time = at_time or datetime.now(tz.utc)
        self.resolved = resolved

    def to_dict(self) -> Dict[str, Any]:
        """Convert to MongoDB document."""
        return {
            "_id": self._id,
            "linkedin_profile_id": self.linkedin_profile_id,
            "action_type": self.action_type,
            "limit_type": self.limit_type,
            "limit_exceeded": self.limit_exceeded,
            "actual_count": self.actual_count,
            "warning_level": self.warning_level,
            "at_time": self.at_time,
            "resolved": self.resolved,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RateLimitWarning":
        """Create instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            linkedin_profile_id=data.get("linkedin_profile_id", ""),
            action_type=data.get("action_type", ""),
            limit_type=data.get("limit_type", ""),
            limit_exceeded=data.get("limit_exceeded", 0),
            actual_count=data.get("actual_count", 0),
            warning_level=data.get("warning_level", "low"),
            at_time=data.get("at_time"),
            resolved=data.get("resolved", False),
        )

    def save(self) -> str:
        """Save to MongoDB."""
        collection = get_mongodb_collection("rate_limit_warnings")
        if collection is None:
            raise RuntimeError("MongoDB collection not available")

        doc = self.to_dict()
        collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
        return self._id

    @classmethod
    def get_recent(cls, linkedin_profile_id: str, limit: int = 10) -> List["RateLimitWarning"]:
        """Get recent warnings for a profile."""
        collection = get_mongodb_collection("rate_limit_warnings")
        if collection is None:
            return []

        warnings = []
        for data in collection.find(
            {"linkedin_profile_id": linkedin_profile_id}
        ).sort("at_time", -1).limit(limit):
            warnings.append(cls.from_dict(data))
        return warnings
