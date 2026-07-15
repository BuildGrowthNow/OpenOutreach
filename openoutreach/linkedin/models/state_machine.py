"""State Machine models for Campaign workflow automation - MongoDB version."""

from __future__ import annotations

from datetime import datetime, timezone as tz
from typing import Optional, Dict, Any, List
from uuid import uuid4

from openoutreach.mongodb.connection import get_mongodb_collection


class CampaignStateGraph:
    """
    MongoDB model for campaign workflow state machine.
    Represents the visual flow of a campaign's automated actions.
    """

    def __init__(
        self,
        _id: Optional[str] = None,
        campaign_id: str = "",
        name: str = "",
        description: str = "",
        is_active: bool = True,
        graph_data: Optional[Dict[str, Any]] = None,
        is_valid: bool = False,
        validation_errors: Optional[List[str]] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.campaign_id = campaign_id
        self.name = name
        self.description = description
        self.is_active = is_active
        self.graph_data = graph_data or {}
        self.is_valid = is_valid
        self.validation_errors = validation_errors or []
        self.created_at = created_at or datetime.now(tz.utc)
        self.updated_at = updated_at or datetime.now(tz.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to MongoDB document."""
        return {
            "_id": self._id,
            "campaign_id": self.campaign_id,
            "name": self.name,
            "description": self.description,
            "is_active": self.is_active,
            "graph_data": self.graph_data,
            "is_valid": self.is_valid,
            "validation_errors": self.validation_errors,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CampaignStateGraph":
        """Create instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            campaign_id=data.get("campaign_id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            is_active=data.get("is_active", True),
            graph_data=data.get("graph_data", {}),
            is_valid=data.get("is_valid", False),
            validation_errors=data.get("validation_errors", []),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    def save(self) -> str:
        """Save to MongoDB."""
        collection = get_mongodb_collection("campaign_state_graphs")
        if collection is None:
            raise RuntimeError("MongoDB collection not available")

        self.updated_at = datetime.now(tz.utc)
        doc = self.to_dict()
        collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
        return self._id

    @classmethod
    def get_by_campaign(cls, campaign_id: str) -> Optional["CampaignStateGraph"]:
        """Get state graph for a campaign."""
        collection = get_mongodb_collection("campaign_state_graphs")
        if collection is None:
            return None

        data = collection.find_one({"campaign_id": campaign_id})
        return cls.from_dict(data) if data else None


class StateNode:
    """
    MongoDB model for a node in the state machine.
    Represents a step in the campaign workflow (send message, wait, decision, etc.)
    """

    # Node types
    TYPE_START = "start"
    TYPE_WAIT = "wait"
    TYPE_MESSAGE = "message"
    TYPE_GATE = "gate"
    TYPE_DECISION = "decision"
    TYPE_BRANCH = "branch"
    TYPE_WEBHOOK = "webhook"
    TYPE_END = "end"
    TYPE_LINK = "link"

    TYPE_CHOICES = [
        (TYPE_START, "Start"),
        (TYPE_WAIT, "Wait/Delay"),
        (TYPE_MESSAGE, "Send Message"),
        (TYPE_GATE, "Qualification Gate"),
        (TYPE_DECISION, "Decision"),
        (TYPE_BRANCH, "Branch"),
        (TYPE_WEBHOOK, "Webhook"),
        (TYPE_LINK, "Insert Tracked Link"),
        (TYPE_END, "End"),
    ]

    def __init__(
        self,
        _id: Optional[str] = None,
        state_graph_id: str = "",
        name: str = "",
        node_type: str = TYPE_START,
        config: Optional[Dict[str, Any]] = None,
        x: float = 0.0,
        y: float = 0.0,
        is_active: bool = True,
        description: str = "",
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.state_graph_id = state_graph_id
        self.name = name
        self.node_type = node_type
        self.config = config or {}
        self.x = x
        self.y = y
        self.is_active = is_active
        self.description = description
        self.created_at = created_at or datetime.now(tz.utc)
        self.updated_at = updated_at or datetime.now(tz.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to MongoDB document."""
        return {
            "_id": self._id,
            "state_graph_id": self.state_graph_id,
            "name": self.name,
            "node_type": self.node_type,
            "config": self.config,
            "x": self.x,
            "y": self.y,
            "is_active": self.is_active,
            "description": self.description,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateNode":
        """Create instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            state_graph_id=data.get("state_graph_id", ""),
            name=data.get("name", ""),
            node_type=data.get("node_type", cls.TYPE_START),
            config=data.get("config", {}),
            x=data.get("x", 0.0),
            y=data.get("y", 0.0),
            is_active=data.get("is_active", True),
            description=data.get("description", ""),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    def save(self) -> str:
        """Save to MongoDB."""
        collection = get_mongodb_collection("state_nodes")
        if collection is None:
            raise RuntimeError("MongoDB collection not available")

        self.updated_at = datetime.now(tz.utc)
        doc = self.to_dict()
        collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
        return self._id

    @classmethod
    def get_by_graph(cls, state_graph_id: str) -> List["StateNode"]:
        """Get all nodes for a state graph."""
        collection = get_mongodb_collection("state_nodes")
        if collection is None:
            return []

        nodes = []
        for data in collection.find({"state_graph_id": state_graph_id}).sort("x", 1):
            nodes.append(cls.from_dict(data))
        return nodes


class StateTransition:
    """
    MongoDB model for a transition between state nodes.
    Represents the flow from one step to another with optional conditions.
    """

    def __init__(
        self,
        _id: Optional[str] = None,
        state_graph_id: str = "",
        source_node_id: str = "",
        target_node_id: str = "",
        condition_type: str = "always",
        condition_config: Optional[Dict[str, Any]] = None,
        label: str = "",
        order: int = 0,
        is_active: bool = True,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.state_graph_id = state_graph_id
        self.source_node_id = source_node_id
        self.target_node_id = target_node_id
        self.condition_type = condition_type
        self.condition_config = condition_config or {}
        self.label = label
        self.order = order
        self.is_active = is_active
        self.created_at = created_at or datetime.now(tz.utc)
        self.updated_at = updated_at or datetime.now(tz.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to MongoDB document."""
        return {
            "_id": self._id,
            "state_graph_id": self.state_graph_id,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "condition_type": self.condition_type,
            "condition_config": self.condition_config,
            "label": self.label,
            "order": self.order,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateTransition":
        """Create instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            state_graph_id=data.get("state_graph_id", ""),
            source_node_id=data.get("source_node_id", ""),
            target_node_id=data.get("target_node_id", ""),
            condition_type=data.get("condition_type", "always"),
            condition_config=data.get("condition_config", {}),
            label=data.get("label", ""),
            order=data.get("order", 0),
            is_active=data.get("is_active", True),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    def save(self) -> str:
        """Save to MongoDB."""
        collection = get_mongodb_collection("state_transitions")
        if collection is None:
            raise RuntimeError("MongoDB collection not available")

        self.updated_at = datetime.now(tz.utc)
        doc = self.to_dict()
        collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
        return self._id

    @classmethod
    def get_by_graph(cls, state_graph_id: str) -> List["StateTransition"]:
        """Get all transitions for a state graph."""
        collection = get_mongodb_collection("state_transitions")
        if collection is None:
            return []

        transitions = []
        for data in collection.find({"state_graph_id": state_graph_id}).sort("order", 1):
            transitions.append(cls.from_dict(data))
        return transitions


class CampaignState:
    """
    MongoDB model tracking current state of a campaign execution for a deal.
    Tracks which node a specific lead/deal is currently at in the workflow.
    """

    def __init__(
        self,
        _id: Optional[str] = None,
        deal_id: str = "",
        state_graph_id: str = "",
        current_node_id: Optional[str] = None,
        state_data: Optional[Dict[str, Any]] = None,
        is_active: bool = True,
        completed: bool = False,
        completed_at: Optional[datetime] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.deal_id = deal_id
        self.state_graph_id = state_graph_id
        self.current_node_id = current_node_id
        self.state_data = state_data or {}
        self.is_active = is_active
        self.completed = completed
        self.completed_at = completed_at
        self.created_at = created_at or datetime.now(tz.utc)
        self.updated_at = updated_at or datetime.now(tz.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to MongoDB document."""
        return {
            "_id": self._id,
            "deal_id": self.deal_id,
            "state_graph_id": self.state_graph_id,
            "current_node_id": self.current_node_id,
            "state_data": self.state_data,
            "is_active": self.is_active,
            "completed": self.completed,
            "completed_at": self.completed_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CampaignState":
        """Create instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            deal_id=data.get("deal_id", ""),
            state_graph_id=data.get("state_graph_id", ""),
            current_node_id=data.get("current_node_id"),
            state_data=data.get("state_data", {}),
            is_active=data.get("is_active", True),
            completed=data.get("completed", False),
            completed_at=data.get("completed_at"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    def save(self) -> str:
        """Save to MongoDB."""
        collection = get_mongodb_collection("campaign_states")
        if collection is None:
            raise RuntimeError("MongoDB collection not available")

        self.updated_at = datetime.now(tz.utc)
        doc = self.to_dict()
        collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
        return self._id

    @classmethod
    def get_by_deal(cls, deal_id: str) -> Optional["CampaignState"]:
        """Get current state for a deal."""
        collection = get_mongodb_collection("campaign_states")
        if collection is None:
            return None

        data = collection.find_one({"deal_id": deal_id, "is_active": True})
        return cls.from_dict(data) if data else None


class CampaignExecutionLog:
    """
    MongoDB model for logging state machine execution events.
    Tracks the history of a deal moving through the workflow.
    """

    def __init__(
        self,
        _id: Optional[str] = None,
        campaign_state_id: str = "",
        node_id: str = "",
        node_type: str = "",
        action: str = "",
        result: str = "",
        error_message: str = "",
        executed_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self._id = _id or str(uuid4())
        self.campaign_state_id = campaign_state_id
        self.node_id = node_id
        self.node_type = node_type
        self.action = action
        self.result = result
        self.error_message = error_message
        self.executed_at = executed_at or datetime.now(tz.utc)
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to MongoDB document."""
        return {
            "_id": self._id,
            "campaign_state_id": self.campaign_state_id,
            "node_id": self.node_id,
            "node_type": self.node_type,
            "action": self.action,
            "result": self.result,
            "error_message": self.error_message,
            "executed_at": self.executed_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CampaignExecutionLog":
        """Create instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            campaign_state_id=data.get("campaign_state_id", ""),
            node_id=data.get("node_id", ""),
            node_type=data.get("node_type", ""),
            action=data.get("action", ""),
            result=data.get("result", ""),
            error_message=data.get("error_message", ""),
            executed_at=data.get("executed_at"),
            metadata=data.get("metadata", {}),
        )

    def save(self) -> str:
        """Save to MongoDB."""
        collection = get_mongodb_collection("campaign_execution_logs")
        if collection is None:
            raise RuntimeError("MongoDB collection not available")

        doc = self.to_dict()
        collection.insert_one(doc)
        return self._id

    @classmethod
    def get_by_state(cls, campaign_state_id: str, limit: int = 50) -> List["CampaignExecutionLog"]:
        """Get execution logs for a campaign state."""
        collection = get_mongodb_collection("campaign_execution_logs")
        if collection is None:
            return []

        logs = []
        for data in collection.find(
            {"campaign_state_id": campaign_state_id}
        ).sort("executed_at", -1).limit(limit):
            logs.append(cls.from_dict(data))
        return logs
