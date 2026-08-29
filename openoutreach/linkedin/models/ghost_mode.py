# openoutreach/linkedin/models/ghost_mode.py
"""Ghost Mode campaign models for safe testing without sending real actions."""

from __future__ import annotations

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from openoutreach.mongodb.connection import get_mongodb_collection

logger = logging.getLogger(__name__)


class ModeType(str, Enum):
    """Ghost campaign mode types."""
    SIMULATION = "simulation"
    VALIDATION = "validation"
    DRY_RUN = "dry_run"


class GhostCampaign:
    """
    MongoDB GhostCampaign model.

    A campaign running in ghost mode for safe testing.
    Uses pymongo directly for data operations.
    """

    def __init__(
        self,
        _id: Optional[str] = None,
        campaign_id: str = "",
        name: str = "",
        description: str = "",
        is_active: bool = True,
        mode_type: str = ModeType.SIMULATION.value,
        test_seed_leads: str = "",
        test_keywords: str = "",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        leads_processed: int = 0,
        connections_simulated: int = 0,
        messages_simulated: int = 0,
        conversions_simulated: int = 0,
        avg_rating: float = 0.0,
        avg_score: float = 0.0,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.campaign_id = campaign_id
        self.name = name
        self.description = description
        self.is_active = is_active
        self.mode_type = mode_type
        self.test_seed_leads = test_seed_leads
        self.test_keywords = test_keywords
        self.start_time = start_time or datetime.utcnow()
        self.end_time = end_time
        self.leads_processed = leads_processed
        self.connections_simulated = connections_simulated
        self.messages_simulated = messages_simulated
        self.conversions_simulated = conversions_simulated
        self.avg_rating = avg_rating
        self.avg_score = avg_score
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary for MongoDB storage."""
        return {
            "_id": self._id,
            "campaign_id": self.campaign_id,
            "name": self.name,
            "description": self.description,
            "is_active": self.is_active,
            "mode_type": self.mode_type,
            "test_seed_leads": self.test_seed_leads,
            "test_keywords": self.test_keywords,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "leads_processed": self.leads_processed,
            "connections_simulated": self.connections_simulated,
            "messages_simulated": self.messages_simulated,
            "conversions_simulated": self.conversions_simulated,
            "avg_rating": self.avg_rating,
            "avg_score": self.avg_score,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GhostCampaign":
        """Create GhostCampaign instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            campaign_id=data.get("campaign_id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            is_active=data.get("is_active", True),
            mode_type=data.get("mode_type", ModeType.SIMULATION.value),
            test_seed_leads=data.get("test_seed_leads", ""),
            test_keywords=data.get("test_keywords", ""),
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
            leads_processed=data.get("leads_processed", 0),
            connections_simulated=data.get("connections_simulated", 0),
            messages_simulated=data.get("messages_simulated", 0),
            conversions_simulated=data.get("conversions_simulated", 0),
            avg_rating=data.get("avg_rating", 0.0),
            avg_score=data.get("avg_score", 0.0),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    def save(self) -> str:
        """Save the ghost campaign to MongoDB."""
        collection = get_mongodb_collection("ghost_campaigns")
        if collection is None:
            logger.warning(
                "MongoDB collection 'ghost_campaigns' not available; skipping GhostCampaign save"
            )
            return self._id

        self.updated_at = datetime.utcnow()
        doc = self.to_dict()
        collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
        return self._id

    @classmethod
    def get(cls, ghost_campaign_id: str) -> Optional["GhostCampaign"]:
        """Get a ghost campaign by ID."""
        collection = get_mongodb_collection("ghost_campaigns")
        if collection is None:
            return None

        try:
            data = collection.find_one({"_id": ghost_campaign_id})
            if data:
                return cls.from_dict(data)
            return None
        except Exception as e:
            logger.error("Failed to get ghost campaign '%s': %s", ghost_campaign_id, type(e).__name__)
            return None

    @classmethod
    def get_by_campaign_id(cls, campaign_id: str) -> List["GhostCampaign"]:
        """Get all ghost campaigns for a campaign."""
        collection = get_mongodb_collection("ghost_campaigns")
        if collection is None:
            return []

        try:
            results = []
            for data in collection.find({"campaign_id": campaign_id}).sort("created_at", -1):
                results.append(cls.from_dict(data))
            return results
        except Exception as e:
            logger.error("Failed to get ghost campaigns for campaign '%s': %s", campaign_id, type(e).__name__)
            return []

    @classmethod
    def delete(cls, ghost_campaign_id: str) -> bool:
        """Delete a ghost campaign by ID."""
        collection = get_mongodb_collection("ghost_campaigns")
        if collection is None:
            return False

        try:
            result = collection.delete_one({"_id": ghost_campaign_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error("Failed to delete ghost campaign '%s': %s", ghost_campaign_id, type(e).__name__)
            return False

    def __str__(self):
        return f"{self.name} (Ghost Mode)"

    @property
    def pk(self):
        """Get the primary key."""
        return self._id

    @pk.setter
    def pk(self, value):
        """Set the primary key."""
        self._id = value


class ActionType(str, Enum):
    """Ghost simulation action types."""
    SEARCH = "search"
    QUALIFY = "qualify"
    CONNECT = "connect"
    MESSAGE = "message"
    FOLLOW_UP = "follow_up"
    CONVERSION = "conversion"


class GhostSimulationLog:
    """
    MongoDB GhostSimulationLog model.

    Logs a ghost mode simulation run.
    Uses pymongo directly for data operations.
    """

    def __init__(
        self,
        _id: Optional[str] = None,
        ghost_campaign_id: str = "",
        action_type: str = ActionType.SEARCH.value,
        target_url: str = "",
        target_name: str = "",
        result_data: Optional[Dict[str, Any]] = None,
        rating: Optional[float] = None,
        score: Optional[float] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        simulated_action: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.ghost_campaign_id = ghost_campaign_id
        self.action_type = action_type
        self.target_url = target_url
        self.target_name = target_name
        self.result_data = result_data or {}
        self.rating = rating
        self.score = score
        self.started_at = started_at or datetime.utcnow()
        self.completed_at = completed_at or datetime.utcnow()
        self.simulated_action = simulated_action or {}
        self.created_at = created_at or datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary for MongoDB storage."""
        return {
            "_id": self._id,
            "ghost_campaign_id": self.ghost_campaign_id,
            "action_type": self.action_type,
            "target_url": self.target_url,
            "target_name": self.target_name,
            "result_data": self.result_data,
            "rating": self.rating,
            "score": self.score,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "simulated_action": self.simulated_action,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GhostSimulationLog":
        """Create GhostSimulationLog instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            ghost_campaign_id=data.get("ghost_campaign_id", ""),
            action_type=data.get("action_type", ActionType.SEARCH.value),
            target_url=data.get("target_url", ""),
            target_name=data.get("target_name", ""),
            result_data=data.get("result_data", {}),
            rating=data.get("rating"),
            score=data.get("score"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            simulated_action=data.get("simulated_action", {}),
            created_at=data.get("created_at"),
        )

    def save(self) -> str:
        """Save the simulation log to MongoDB."""
        collection = get_mongodb_collection("ghost_simulation_logs")
        if collection is None:
            logger.warning(
                "MongoDB collection 'ghost_simulation_logs' not available; skipping GhostSimulationLog save"
            )
            return self._id

        doc = self.to_dict()
        collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
        return self._id

    @classmethod
    def get(cls, log_id: str) -> Optional["GhostSimulationLog"]:
        """Get a simulation log by ID."""
        collection = get_mongodb_collection("ghost_simulation_logs")
        if collection is None:
            return None

        try:
            data = collection.find_one({"_id": log_id})
            if data:
                return cls.from_dict(data)
            return None
        except Exception as e:
            logger.error("Failed to get simulation log '%s': %s", log_id, type(e).__name__)
            return None

    @classmethod
    def get_by_ghost_campaign(cls, ghost_campaign_id: str) -> List["GhostSimulationLog"]:
        """Get all logs for a ghost campaign."""
        collection = get_mongodb_collection("ghost_simulation_logs")
        if collection is None:
            return []

        try:
            results = []
            for data in collection.find({"ghost_campaign_id": ghost_campaign_id}).sort("started_at", -1):
                results.append(cls.from_dict(data))
            return results
        except Exception as e:
            logger.error("Failed to get logs for ghost campaign '%s': %s", ghost_campaign_id, type(e).__name__)
            return []

    @classmethod
    def delete(cls, log_id: str) -> bool:
        """Delete a simulation log by ID."""
        collection = get_mongodb_collection("ghost_simulation_logs")
        if collection is None:
            return False

        try:
            result = collection.delete_one({"_id": log_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error("Failed to delete simulation log '%s': %s", log_id, type(e).__name__)
            return False

    def __str__(self):
        return f"{self.action_type} for {self.target_name}"

    @property
    def pk(self):
        """Get the primary key."""
        return self._id

    @pk.setter
    def pk(self, value):
        """Set the primary key."""
        self._id = value


class GhostTestScenario:
    """
    MongoDB GhostTestScenario model.

    Reusable test scenarios for ghost mode.
    Uses pymongo directly for data operations.
    """

    def __init__(
        self,
        _id: Optional[str] = None,
        name: str = "",
        description: str = "",
        test_cases: Optional[Dict[str, Any]] = None,
        is_public: bool = False,
        created_by_id: Optional[str] = None,
        runs_count: int = 0,
        avg_success_rate: float = 0.0,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.name = name
        self.description = description
        self.test_cases = test_cases or {}
        self.is_public = is_public
        self.created_by_id = created_by_id
        self.runs_count = runs_count
        self.avg_success_rate = avg_success_rate
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary for MongoDB storage."""
        return {
            "_id": self._id,
            "name": self.name,
            "description": self.description,
            "test_cases": self.test_cases,
            "is_public": self.is_public,
            "created_by_id": self.created_by_id,
            "runs_count": self.runs_count,
            "avg_success_rate": self.avg_success_rate,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GhostTestScenario":
        """Create GhostTestScenario instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            name=data.get("name", ""),
            description=data.get("description", ""),
            test_cases=data.get("test_cases", {}),
            is_public=data.get("is_public", False),
            created_by_id=data.get("created_by_id"),
            runs_count=data.get("runs_count", 0),
            avg_success_rate=data.get("avg_success_rate", 0.0),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    def save(self) -> str:
        """Save the test scenario to MongoDB."""
        collection = get_mongodb_collection("ghost_test_scenarios")
        if collection is None:
            logger.warning(
                "MongoDB collection 'ghost_test_scenarios' not available; skipping GhostTestScenario save"
            )
            return self._id

        self.updated_at = datetime.utcnow()
        doc = self.to_dict()
        collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
        return self._id

    @classmethod
    def get(cls, scenario_id: str) -> Optional["GhostTestScenario"]:
        """Get a test scenario by ID."""
        collection = get_mongodb_collection("ghost_test_scenarios")
        if collection is None:
            return None

        try:
            data = collection.find_one({"_id": scenario_id})
            if data:
                return cls.from_dict(data)
            return None
        except Exception as e:
            logger.error("Failed to get test scenario '%s': %s", scenario_id, type(e).__name__)
            return None

    @classmethod
    def get_public_scenarios(cls) -> List["GhostTestScenario"]:
        """Get all public test scenarios."""
        collection = get_mongodb_collection("ghost_test_scenarios")
        if collection is None:
            return []

        try:
            results = []
            for data in collection.find({"is_public": True}).sort("created_at", -1):
                results.append(cls.from_dict(data))
            return results
        except Exception as e:
            logger.error("Failed to get public test scenarios: %s", type(e).__name__)
            return []

    @classmethod
    def get_by_creator(cls, creator_id: str) -> List["GhostTestScenario"]:
        """Get all scenarios created by a user."""
        collection = get_mongodb_collection("ghost_test_scenarios")
        if collection is None:
            return []

        try:
            results = []
            for data in collection.find({"created_by_id": creator_id}).sort("created_at", -1):
                results.append(cls.from_dict(data))
            return results
        except Exception as e:
            logger.error("Failed to get scenarios for creator '%s': %s", creator_id, type(e).__name__)
            return []

    @classmethod
    def delete(cls, scenario_id: str) -> bool:
        """Delete a test scenario by ID."""
        collection = get_mongodb_collection("ghost_test_scenarios")
        if collection is None:
            return False

        try:
            result = collection.delete_one({"_id": scenario_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error("Failed to delete test scenario '%s': %s", scenario_id, type(e).__name__)
            return False

    def __str__(self):
        return self.name

    @property
    def pk(self):
        """Get the primary key."""
        return self._id

    @pk.setter
    def pk(self, value):
        """Set the primary key."""
        self._id = value
