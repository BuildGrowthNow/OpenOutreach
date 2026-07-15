# openoutreach/linkedin/models/health.py
"""Campaign Health Monitor & Auto-Recovery models."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone as tz
from typing import Any, Dict, List, Optional
from uuid import uuid4

from openoutreach.mongodb.connection import get_mongodb_collection

logger = logging.getLogger(__name__)


class CampaignHealthMetric:
    """Stores hourly metrics for campaign health monitoring."""

    def __init__(
        self,
        _id: Optional[str] = None,
        campaign_id: str = "",
        timestamp: Optional[datetime] = None,
        # Connection metrics
        connections_sent: int = 0,
        connections_accepted: int = 0,
        connection_accept_rate: float = 0.0,
        # Follow-up metrics
        messages_sent: int = 0,
        messages_replied: int = 0,
        response_rate: float = 0.0,
        # Error metrics
        errors_total: int = 0,
        rate_limit_errors: int = 0,
        auth_errors: int = 0,
        network_errors: int = 0,
        # Conversion metrics
        deals_created: int = 0,
        conversions: int = 0,
        # Detection metrics
        detectability_score: int = 50,  # 0-100
        created_at: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.campaign_id = campaign_id
        self.timestamp = timestamp or datetime.now(tz.utc)
        self.connections_sent = connections_sent
        self.connections_accepted = connections_accepted
        self.connection_accept_rate = connection_accept_rate
        self.messages_sent = messages_sent
        self.messages_replied = messages_replied
        self.response_rate = response_rate
        self.errors_total = errors_total
        self.rate_limit_errors = rate_limit_errors
        self.auth_errors = auth_errors
        self.network_errors = network_errors
        self.deals_created = deals_created
        self.conversions = conversions
        self.detectability_score = detectability_score
        self.created_at = created_at or datetime.now(tz.utc)

    @property
    def id(self) -> str:
        """Get the ID."""
        return self._id

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary for MongoDB storage."""
        return {
            "_id": self._id,
            "campaign_id": self.campaign_id,
            "timestamp": self.timestamp,
            "connections_sent": self.connections_sent,
            "connections_accepted": self.connections_accepted,
            "connection_accept_rate": self.connection_accept_rate,
            "messages_sent": self.messages_sent,
            "messages_replied": self.messages_replied,
            "response_rate": self.response_rate,
            "errors_total": self.errors_total,
            "rate_limit_errors": self.rate_limit_errors,
            "auth_errors": self.auth_errors,
            "network_errors": self.network_errors,
            "deals_created": self.deals_created,
            "conversions": self.conversions,
            "detectability_score": self.detectability_score,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CampaignHealthMetric":
        """Create CampaignHealthMetric instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            campaign_id=data.get("campaign_id", ""),
            timestamp=data.get("timestamp"),
            connections_sent=data.get("connections_sent", 0),
            connections_accepted=data.get("connections_accepted", 0),
            connection_accept_rate=data.get("connection_accept_rate", 0.0),
            messages_sent=data.get("messages_sent", 0),
            messages_replied=data.get("messages_replied", 0),
            response_rate=data.get("response_rate", 0.0),
            errors_total=data.get("errors_total", 0),
            rate_limit_errors=data.get("rate_limit_errors", 0),
            auth_errors=data.get("auth_errors", 0),
            network_errors=data.get("network_errors", 0),
            deals_created=data.get("deals_created", 0),
            conversions=data.get("conversions", 0),
            detectability_score=data.get("detectability_score", 50),
            created_at=data.get("created_at"),
        )

    def save(self) -> str:
        """Save the health metric to MongoDB."""
        collection = get_mongodb_collection("campaign_health_metrics")
        if collection is None:
            logger.warning(
                "MongoDB collection 'campaign_health_metrics' not available; skipping CampaignHealthMetric save"
            )
            return self._id

        doc = self.to_dict()
        result = collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
        return str(result.upserted_id or self._id)

    @classmethod
    def create_hourly_snapshot(cls, campaign_id: str) -> "CampaignHealthMetric":
        """Create a hourly snapshot for a campaign."""
        now = datetime.now(tz.utc)
        hour_start = now.replace(minute=0, second=0, microsecond=0)

        # Get metrics for the hour
        since = hour_start - timedelta(hours=1)

        # Get MongoDB collections
        action_log_collection = get_mongodb_collection("action_logs")
        deal_collection = get_mongodb_collection("deals")
        chat_message_collection = get_mongodb_collection("chat_messages")

        connections_sent = 0
        connections_accepted = 0
        messages_sent = 0
        deals_with_responses = 0
        errors = 0

        if action_log_collection is not None:
            # Connection metrics from ActionLog
            connections_sent = action_log_collection.count_documents(
                {
                    "campaign_id": campaign_id,
                    "action_type": "CONNECT",
                    "created_at": {"$gte": since},
                }
            )

            # Follow-up metrics
            messages_sent = action_log_collection.count_documents(
                {
                    "campaign_id": campaign_id,
                    "action_type": "FOLLOW_UP",
                    "created_at": {"$gte": since},
                }
            )

            # Error metrics (basic count)
            errors = action_log_collection.count_documents(
                {
                    "campaign_id": campaign_id,
                    "created_at": {"$gte": since},
                    "error_message": {"$exists": True, "$ne": ""},
                }
            )

        if deal_collection is not None:
            # Count connected deals
            connections_accepted = deal_collection.count_documents(
                {
                    "campaign_id": campaign_id,
                    "state": "CONNECTED",
                    "creation_date": {"$gte": since},
                }
            )

        if chat_message_collection is not None and deal_collection is not None:
            # Get deals with responses (incoming messages)
            pipeline = [
                {
                    "$match": {
                        "campaign_id": campaign_id,
                        "creation_date": {"$gte": since},
                    }
                },
                {
                    "$lookup": {
                        "from": "chat_messages",
                        "localField": "_id",
                        "foreignField": "deal_id",
                        "as": "messages",
                    }
                },
                {
                    "$match": {
                        "messages": {
                            "$elemMatch": {
                                "is_outgoing": False,
                                "creation_date": {"$gte": since},
                            }
                        }
                    }
                },
                {"$count": "count"},
            ]
            result = list(deal_collection.aggregate(pipeline))
            deals_with_responses = result[0]["count"] if result else 0

        connection_accept_rate = (
            connections_accepted / connections_sent if connections_sent > 0 else 0.0
        )
        response_rate = (
            deals_with_responses / connections_sent if connections_sent > 0 else 0.0
        )

        rate_limit_errors = 0  # Rate limit errors tracked elsewhere
        auth_errors = 0  # Auth errors tracked elsewhere
        network_errors = 0  # Network errors tracked elsewhere

        # Detectability score - calculated by smart rate limiter
        detectability_score = 50  # Default

        metric = cls(
            campaign_id=campaign_id,
            timestamp=hour_start,
            connections_sent=connections_sent,
            connections_accepted=connections_accepted,
            connection_accept_rate=connection_accept_rate,
            messages_sent=messages_sent,
            messages_replied=deals_with_responses,
            response_rate=response_rate,
            errors_total=errors,
            rate_limit_errors=rate_limit_errors,
            auth_errors=auth_errors,
            network_errors=network_errors,
            deals_created=connections_sent,
            conversions=0,  # Will be calculated separately
            detectability_score=detectability_score,
        )
        metric.save()
        return metric


class HealthAlert:
    """Alert for campaign health issues."""

    # Severity constants
    SEVERITY_LOW = "low"
    SEVERITY_MEDIUM = "medium"
    SEVERITY_HIGH = "high"
    SEVERITY_CRITICAL = "critical"

    SEVERITY_CHOICES = [
        (SEVERITY_LOW, "Low"),
        (SEVERITY_MEDIUM, "Medium"),
        (SEVERITY_HIGH, "High"),
        (SEVERITY_CRITICAL, "Critical"),
    ]

    # Type constants
    TYPE_CONNECTION_RATE = "connection_rate"
    TYPE_RESPONSE_RATE = "response_rate"
    TYPE_RATE_LIMIT = "rate_limit"
    TYPE_AUTH_ERROR = "auth_error"
    TYPE_DETECTION = "detection"
    TYPE_ERROR_SPIKE = "error_spike"

    TYPE_CHOICES = [
        (TYPE_CONNECTION_RATE, "Connection accept rate too low"),
        (TYPE_RESPONSE_RATE, "Response rate too low"),
        (TYPE_RATE_LIMIT, "Rate limit warnings"),
        (TYPE_AUTH_ERROR, "Authentication errors"),
        (TYPE_DETECTION, "LinkedIn detectability high"),
        (TYPE_ERROR_SPIKE, "Error rate spike"),
    ]

    def __init__(
        self,
        _id: Optional[str] = None,
        campaign_id: str = "",
        alert_type: str = "",
        severity: str = SEVERITY_LOW,
        message: str = "",
        details: Optional[Dict[str, Any]] = None,
        # Resolution
        is_resolved: bool = False,
        resolved_at: Optional[datetime] = None,
        resolution_notes: str = "",
        # Auto-remediation
        auto_remediation_applied: bool = False,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.campaign_id = campaign_id
        self.alert_type = alert_type
        self.severity = severity
        self.message = message
        self.details = details or {}
        self.is_resolved = is_resolved
        self.resolved_at = resolved_at
        self.resolution_notes = resolution_notes
        self.auto_remediation_applied = auto_remediation_applied
        self.created_at = created_at or datetime.now(tz.utc)
        self.updated_at = updated_at or datetime.now(tz.utc)

    @property
    def id(self) -> str:
        """Get the ID."""
        return self._id

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary for MongoDB storage."""
        return {
            "_id": self._id,
            "campaign_id": self.campaign_id,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "message": self.message,
            "details": self.details,
            "is_resolved": self.is_resolved,
            "resolved_at": self.resolved_at,
            "resolution_notes": self.resolution_notes,
            "auto_remediation_applied": self.auto_remediation_applied,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HealthAlert":
        """Create HealthAlert instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            campaign_id=data.get("campaign_id", ""),
            alert_type=data.get("alert_type", ""),
            severity=data.get("severity", cls.SEVERITY_LOW),
            message=data.get("message", ""),
            details=data.get("details", {}),
            is_resolved=data.get("is_resolved", False),
            resolved_at=data.get("resolved_at"),
            resolution_notes=data.get("resolution_notes", ""),
            auto_remediation_applied=data.get("auto_remediation_applied", False),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    def save(self) -> str:
        """Save the health alert to MongoDB."""
        collection = get_mongodb_collection("health_alerts")
        if collection is None:
            logger.warning(
                "MongoDB collection 'health_alerts' not available; skipping HealthAlert save"
            )
            return self._id

        self.updated_at = datetime.now(tz.utc)
        doc = self.to_dict()
        result = collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
        return str(result.upserted_id or self._id)

    def resolve(self, notes: str = "") -> None:
        """Mark the alert as resolved."""
        self.is_resolved = True
        self.resolved_at = datetime.now(tz.utc)
        self.resolution_notes = notes
        self.save()


class RecoveryAction:
    """Track recovery actions taken for campaigns."""

    # Action type constants
    ACTION_REDUCE_VELOCITY = "reduce_velocity"
    ACTION_ADD_COOLDOWN = "add_cooldown"
    ACTION_SWITCH_MESSAGE = "switch_message"
    ACTION_PAUSE = "pause"
    ACTION_SWITCH_ACCOUNT = "switch_account"

    ACTION_CHOICES = [
        (ACTION_REDUCE_VELOCITY, "Reduce velocity"),
        (ACTION_ADD_COOLDOWN, "Add cooldown period"),
        (ACTION_SWITCH_MESSAGE, "Switch message variant"),
        (ACTION_PAUSE, "Pause campaign"),
        (ACTION_SWITCH_ACCOUNT, "Switch LinkedIn account"),
    ]

    def __init__(
        self,
        _id: Optional[str] = None,
        campaign_id: str = "",
        action_type: str = "",
        before_state: Optional[Dict[str, Any]] = None,
        after_state: Optional[Dict[str, Any]] = None,
        reason: str = "",
        executed_at: Optional[datetime] = None,
        execution_result: str = "",
    ):
        self._id = _id or str(uuid4())
        self.campaign_id = campaign_id
        self.action_type = action_type
        self.before_state = before_state or {}
        self.after_state = after_state or {}
        self.reason = reason
        self.executed_at = executed_at or datetime.now(tz.utc)
        self.execution_result = execution_result

    @property
    def id(self) -> str:
        """Get the ID."""
        return self._id

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary for MongoDB storage."""
        return {
            "_id": self._id,
            "campaign_id": self.campaign_id,
            "action_type": self.action_type,
            "before_state": self.before_state,
            "after_state": self.after_state,
            "reason": self.reason,
            "executed_at": self.executed_at,
            "execution_result": self.execution_result,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecoveryAction":
        """Create RecoveryAction instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            campaign_id=data.get("campaign_id", ""),
            action_type=data.get("action_type", ""),
            before_state=data.get("before_state", {}),
            after_state=data.get("after_state", {}),
            reason=data.get("reason", ""),
            executed_at=data.get("executed_at"),
            execution_result=data.get("execution_result", ""),
        )

    def save(self) -> str:
        """Save the recovery action to MongoDB."""
        collection = get_mongodb_collection("recovery_actions")
        if collection is None:
            logger.warning(
                "MongoDB collection 'recovery_actions' not available; skipping RecoveryAction save"
            )
            return self._id

        doc = self.to_dict()
        result = collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
        return str(result.upserted_id or self._id)
