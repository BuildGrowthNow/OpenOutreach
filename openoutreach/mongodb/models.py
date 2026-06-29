"""
MongoDB Models for OpenOutreach

This module provides MongoDB-compatible versions of the CRM models
that use pymongo directly for data operations.

Since Djongo is not compatible with Django 5.x, this module uses
pymongo directly for all MongoDB operations.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, TypeVar
from uuid import uuid4

from pymongo.collection import Collection
from pymongo.results import InsertOneResult, UpdateResult

from .connection import (
    get_mongodb,
    get_mongodb_collection,
    check_mongodb_connection,
    mongodb_connection,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class Lead:
    """
    MongoDB Lead model.
    
    Represents a lead in the CRM system with MongoDB-specific fields.
    Uses pymongo directly for data operations.
    """
    
    def __init__(
        self,
        _id: Optional[str] = None,
        linkedin_url: str = "",
        public_identifier: str = "",
        urn: Optional[str] = None,
        embedding: Optional[bytes] = None,
        contact_info: Optional[Dict[str, Any]] = None,
        api_email: Optional[str] = None,
        disqualified: bool = False,
        creation_date: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.linkedin_url = linkedin_url
        self.public_identifier = public_identifier
        self.urn = urn
        self.embedding = embedding
        self.contact_info = contact_info or {}
        self.api_email = api_email
        self.disqualified = disqualified
        self.creation_date = creation_date or datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary for MongoDB storage."""
        data = {
            "_id": self._id,
            "linkedin_url": self.linkedin_url,
            "public_identifier": self.public_identifier,
            "creation_date": self.creation_date,
        }
        if self.urn:
            data["urn"] = self.urn
        if self.embedding:
            data["embedding"] = self.embedding
        if self.contact_info:
            data["contact_info"] = self.contact_info
        if self.api_email:
            data["api_email"] = self.api_email
        data["disqualified"] = self.disqualified
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Lead":
        """Create Lead instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            linkedin_url=data.get("linkedin_url", ""),
            public_identifier=data.get("public_identifier", ""),
            urn=data.get("urn"),
            embedding=data.get("embedding"),
            contact_info=data.get("contact_info", {}),
            api_email=data.get("api_email"),
            disqualified=data.get("disqualified", False),
            creation_date=data.get("creation_date"),
        )
    
    def save(self) -> str:
        """Save the lead to MongoDB."""
        collection = get_mongodb_collection("leads")
        if collection is None:
            raise RuntimeError("MongoDB collection 'leads' not available")
        
        doc = self.to_dict()
        result = collection.update_one(
            {"_id": self._id},
            {"$set": doc},
            upsert=True
        )
        return str(result.upserted_id or self._id)
    
    @classmethod
    def get(cls, lead_id: str) -> Optional["Lead"]:
        """Get a lead by ID."""
        collection = get_mongodb_collection("leads")
        if collection is None:
            return None
        
        try:
            data = collection.find_one({"_id": lead_id})
            if data:
                return cls.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get lead '{lead_id}': {e}")
            return None
    
    @classmethod
    def find_by_public_identifier(cls, public_identifier: str) -> Optional["Lead"]:
        """Find a lead by public identifier."""
        collection = get_mongodb_collection("leads")
        if collection is None:
            return None
        
        try:
            data = collection.find_one({"public_identifier": public_identifier})
            if data:
                return cls.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to find lead by public_identifier '{public_identifier}': {e}")
            return None
    
    @classmethod
    def find_by_linkedin_url(cls, linkedin_url: str) -> Optional["Lead"]:
        """Find a lead by LinkedIn URL."""
        collection = get_mongodb_collection("leads")
        if collection is None:
            return None
        
        try:
            data = collection.find_one({"linkedin_url": linkedin_url})
            if data:
                return cls.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to find lead by linkedin_url '{linkedin_url}': {e}")
            return None
    
    @classmethod
    def delete(cls, lead_id: str) -> bool:
        """Delete a lead by ID."""
        collection = get_mongodb_collection("leads")
        if collection is None:
            return False
        
        try:
            result = collection.delete_one({"_id": lead_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete lead '{lead_id}': {e}")
            return False
    
    def __str__(self):
        label = self.public_identifier or self.linkedin_url or f"Lead#{self._id[:8]}"
        if self.disqualified:
            return f"(Disqualified) {label}"
        return label
    
    @property
    def pk(self):
        """Get the primary key."""
        return self._id
    
    @pk.setter
    def pk(self, value):
        """Set the primary key."""
        self._id = value
    
    @classmethod
    def objects(cls) -> "LeadManager":
        """Get the LeadManager for querying leads."""
        return LeadManager()


class LeadManager:
    """Manager for Lead queries."""
    
    def __init__(self):
        self.collection = None
    
    def _get_collection(self) -> Optional[Collection]:
        if self.collection is None:
            self.collection = get_mongodb_collection("leads")
        return self.collection
    
    def all(self) -> List[Lead]:
        """Get all leads."""
        collection = self._get_collection()
        if collection is None:
            return []
        
        try:
            leads = []
            for data in collection.find():
                leads.append(Lead.from_dict(data))
            return leads
        except Exception as e:
            logger.error(f"Failed to get all leads: {e}")
            return []
    
    def filter(self, **kwargs) -> List[Lead]:
        """Filter leads by criteria."""
        collection = self._get_collection()
        if collection is None:
            return []
        
        try:
            leads = []
            for data in collection.find(kwargs):
                leads.append(Lead.from_dict(data))
            return leads
        except Exception as e:
            logger.error(f"Failed to filter leads: {e}")
            return []
    
    def count(self) -> int:
        """Count total leads."""
        collection = self._get_collection()
        if collection is None:
            return 0
        
        try:
            return collection.count_documents({})
        except Exception as e:
            logger.error(f"Failed to count leads: {e}")
            return 0
    
    def get(self, **kwargs) -> Optional[Lead]:
        """Get a single lead by criteria."""
        collection = self._get_collection()
        if collection is None:
            return None
        
        try:
            data = collection.find_one(kwargs)
            if data:
                return Lead.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get lead: {e}")
            return None
    
    def get_or_create(self, defaults: Optional[Dict[str, Any]] = None, **kwargs) -> tuple["Lead", bool]:
        """Get existing lead or create new one."""
        existing = self.get(**kwargs)
        if existing:
            return existing, False
        
        data = kwargs.copy()
        if defaults:
            data.update(defaults)
        
        lead = Lead(**data)
        lead.save()
        return lead, True


class Campaign:
    """
    MongoDB Campaign model.
    
    Represents a marketing campaign with MongoDB-specific fields.
    Uses pymongo directly for data operations.
    """
    
    def __init__(
        self,
        _id: Optional[str] = None,
        name: str = "",
        product_docs: str = "",
        campaign_objective: str = "",
        booking_link: str = "",
        is_freemium: bool = False,
        action_fraction: float = 0.2,
        seed_public_ids: Optional[List[str]] = None,
        model_blob: Optional[bytes] = None,
        velocity: int = 20,
        cooldown_minutes: int = 0,
        is_paused: bool = False,
        created_at: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.name = name
        self.product_docs = product_docs
        self.campaign_objective = campaign_objective
        self.booking_link = booking_link
        self.is_freemium = is_freemium
        self.action_fraction = action_fraction
        self.seed_public_ids = seed_public_ids or []
        self.model_blob = model_blob
        self.velocity = velocity
        self.cooldown_minutes = cooldown_minutes
        self.is_paused = is_paused
        self.created_at = created_at or datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary for MongoDB storage."""
        data = {
            "_id": self._id,
            "name": self.name,
            "product_docs": self.product_docs,
            "campaign_objective": self.campaign_objective,
            "booking_link": self.booking_link,
            "is_freemium": self.is_freemium,
            "action_fraction": self.action_fraction,
            "seed_public_ids": self.seed_public_ids,
            "velocity": self.velocity,
            "cooldown_minutes": self.cooldown_minutes,
            "is_paused": self.is_paused,
            "created_at": self.created_at,
        }
        if self.model_blob:
            data["model_blob"] = self.model_blob
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Campaign":
        """Create Campaign instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            name=data.get("name", ""),
            product_docs=data.get("product_docs", ""),
            campaign_objective=data.get("campaign_objective", ""),
            booking_link=data.get("booking_link", ""),
            is_freemium=data.get("is_freemium", False),
            action_fraction=data.get("action_fraction", 0.2),
            seed_public_ids=data.get("seed_public_ids", []),
            model_blob=data.get("model_blob"),
            velocity=data.get("velocity", 20),
            cooldown_minutes=data.get("cooldown_minutes", 0),
            is_paused=data.get("is_paused", False),
            created_at=data.get("created_at"),
        )
    
    def save(self) -> str:
        """Save the campaign to MongoDB."""
        collection = get_mongodb_collection("campaigns")
        if collection is None:
            raise RuntimeError("MongoDB collection 'campaigns' not available")
        
        doc = self.to_dict()
        result = collection.update_one(
            {"_id": self._id},
            {"$set": doc},
            upsert=True
        )
        return str(result.upserted_id or self._id)
    
    @classmethod
    def get(cls, campaign_id: str) -> Optional["Campaign"]:
        """Get a campaign by ID."""
        collection = get_mongodb_collection("campaigns")
        if collection is None:
            return None
        
        try:
            data = collection.find_one({"_id": campaign_id})
            if data:
                return cls.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get campaign '{campaign_id}': {e}")
            return None
    
    @classmethod
    def find_by_name(cls, name: str) -> Optional["Campaign"]:
        """Find a campaign by name."""
        collection = get_mongodb_collection("campaigns")
        if collection is None:
            return None
        
        try:
            data = collection.find_one({"name": name})
            if data:
                return cls.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to find campaign by name '{name}': {e}")
            return None
    
    @classmethod
    def delete(cls, campaign_id: str) -> bool:
        """Delete a campaign by ID."""
        collection = get_mongodb_collection("campaigns")
        if collection is None:
            return False
        
        try:
            result = collection.delete_one({"_id": campaign_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete campaign '{campaign_id}': {e}")
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
    
    @classmethod
    def objects(cls) -> "CampaignManager":
        """Get the CampaignManager for querying campaigns."""
        return CampaignManager()


class CampaignManager:
    """Manager for Campaign queries."""
    
    def __init__(self):
        self.collection = None
    
    def _get_collection(self) -> Optional[Collection]:
        if self.collection is None:
            self.collection = get_mongodb_collection("campaigns")
        return self.collection
    
    def all(self) -> List[Campaign]:
        """Get all campaigns."""
        collection = self._get_collection()
        if collection is None:
            return []
        
        try:
            campaigns = []
            for data in collection.find():
                campaigns.append(Campaign.from_dict(data))
            return campaigns
        except Exception as e:
            logger.error(f"Failed to get all campaigns: {e}")
            return []
    
    def filter(self, **kwargs) -> List[Campaign]:
        """Filter campaigns by criteria."""
        collection = self._get_collection()
        if collection is None:
            return []
        
        try:
            campaigns = []
            for data in collection.find(kwargs):
                campaigns.append(Campaign.from_dict(data))
            return campaigns
        except Exception as e:
            logger.error(f"Failed to filter campaigns: {e}")
            return []
    
    def count(self) -> int:
        """Count total campaigns."""
        collection = self._get_collection()
        if collection is None:
            return 0
        
        try:
            return collection.count_documents({})
        except Exception as e:
            logger.error(f"Failed to count campaigns: {e}")
            return 0
    
    def get(self, **kwargs) -> Optional[Campaign]:
        """Get a single campaign by criteria."""
        collection = self._get_collection()
        if collection is None:
            return None
        
        try:
            data = collection.find_one(kwargs)
            if data:
                return Campaign.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get campaign: {e}")
            return None
    
    def get_or_create(self, defaults: Optional[Dict[str, Any]] = None, **kwargs) -> tuple["Campaign", bool]:
        """Get existing campaign or create new one."""
        existing = self.get(**kwargs)
        if existing:
            return existing, False
        
        data = kwargs.copy()
        if defaults:
            data.update(defaults)
        
        campaign = Campaign(**data)
        campaign.save()
        return campaign, True


class Deal:
    """
    MongoDB Deal model.
    
    Represents a deal in the CRM system linked to a lead and campaign.
    Uses pymongo directly for data operations.
    """
    
    class DealState:
        QUALIFIED = "Qualified"
        READY_TO_CONNECT = "Ready to Connect"
        PENDING = "Pending"
        CONNECTED = "Connected"
        COMPLETED = "Completed"
        FAILED = "Failed"
        NO_EMAIL = "No Email"
    
    class Outcome:
        CONVERTED = "converted"
        NOT_INTERESTED = "not_interested"
        WRONG_FIT = "wrong_fit"
        NO_BUDGET = "no_budget"
        HAS_SOLUTION = "has_solution"
        BAD_TIMING = "bad_timing"
        UNRESPONSIVE = "unresponsive"
        UNKNOWN = "unknown"
    
    def __init__(
        self,
        _id: Optional[str] = None,
        lead_id: str = "",
        campaign_id: str = "",
        state: str = DealState.QUALIFIED,
        outcome: str = "",
        reason: str = "",
        connect_attempts: int = 0,
        backoff_hours: int = 0,
        next_check_pending_at: Optional[datetime] = None,
        profile_summary: Optional[Dict[str, Any]] = None,
        chat_summary: Optional[Dict[str, Any]] = None,
        creation_date: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.lead_id = lead_id
        self.campaign_id = campaign_id
        self.state = state
        self.outcome = outcome
        self.reason = reason
        self.connect_attempts = connect_attempts
        self.backoff_hours = backoff_hours
        self.next_check_pending_at = next_check_pending_at
        self.profile_summary = profile_summary or {}
        self.chat_summary = chat_summary or {}
        self.creation_date = creation_date or datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary for MongoDB storage."""
        data = {
            "_id": self._id,
            "lead_id": self.lead_id,
            "campaign_id": self.campaign_id,
            "state": self.state,
            "outcome": self.outcome,
            "reason": self.reason,
            "connect_attempts": self.connect_attempts,
            "backoff_hours": self.backoff_hours,
            "profile_summary": self.profile_summary,
            "chat_summary": self.chat_summary,
            "creation_date": self.creation_date,
        }
        if self.next_check_pending_at:
            data["next_check_pending_at"] = self.next_check_pending_at
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Deal":
        """Create Deal instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            lead_id=data.get("lead_id", ""),
            campaign_id=data.get("campaign_id", ""),
            state=data.get("state", cls.DealState.QUALIFIED),
            outcome=data.get("outcome", ""),
            reason=data.get("reason", ""),
            connect_attempts=data.get("connect_attempts", 0),
            backoff_hours=data.get("backoff_hours", 0),
            next_check_pending_at=data.get("next_check_pending_at"),
            profile_summary=data.get("profile_summary", {}),
            chat_summary=data.get("chat_summary", {}),
            creation_date=data.get("creation_date"),
        )
    
    def save(self) -> str:
        """Save the deal to MongoDB."""
        collection = get_mongodb_collection("deals")
        if collection is None:
            raise RuntimeError("MongoDB collection 'deals' not available")
        
        doc = self.to_dict()
        result = collection.update_one(
            {"_id": self._id},
            {"$set": doc},
            upsert=True
        )
        return str(result.upserted_id or self._id)
    
    @classmethod
    def get(cls, deal_id: str) -> Optional["Deal"]:
        """Get a deal by ID."""
        collection = get_mongodb_collection("deals")
        if collection is None:
            return None
        
        try:
            data = collection.find_one({"_id": deal_id})
            if data:
                return cls.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get deal '{deal_id}': {e}")
            return None
    
    @classmethod
    def find_by_lead_id(cls, lead_id: str) -> List["Deal"]:
        """Find deals by lead ID."""
        collection = get_mongodb_collection("deals")
        if collection is None:
            return []
        
        try:
            deals = []
            for data in collection.find({"lead_id": lead_id}):
                deals.append(cls.from_dict(data))
            return deals
        except Exception as e:
            logger.error(f"Failed to find deals by lead_id '{lead_id}': {e}")
            return []
    
    @classmethod
    def find_by_campaign_id(cls, campaign_id: str) -> List["Deal"]:
        """Find deals by campaign ID."""
        collection = get_mongodb_collection("deals")
        if collection is None:
            return []
        
        try:
            deals = []
            for data in collection.find({"campaign_id": campaign_id}):
                deals.append(cls.from_dict(data))
            return deals
        except Exception as e:
            logger.error(f"Failed to find deals by campaign_id '{campaign_id}': {e}")
            return []
    
    @classmethod
    def delete(cls, deal_id: str) -> bool:
        """Delete a deal by ID."""
        collection = get_mongodb_collection("deals")
        if collection is None:
            return False
        
        try:
            result = collection.delete_one({"_id": deal_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete deal '{deal_id}': {e}")
            return False
    
    def __str__(self):
        return f"Deal#{self._id[:8]} - {self.state}"
    
    @property
    def pk(self):
        """Get the primary key."""
        return self._id
    
    @pk.setter
    def pk(self, value):
        """Set the primary key."""
        self._id = value
    
    @classmethod
    def objects(cls) -> "DealManager":
        """Get the DealManager for querying deals."""
        return DealManager()


class Message:
    """
    MongoDB Message model.
    
    Represents a message in the CRM system.
    Uses pymongo directly for data operations.
    """

    def __init__(
        self,
        _id: Optional[str] = None,
        deal_id: str = "",
        content: str = "",
        is_outgoing: bool = True,
        created_at: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.deal_id = deal_id
        self.content = content
        self.is_outgoing = is_outgoing
        self.created_at = created_at or datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary for MongoDB storage."""
        data = {
            "_id": self._id,
            "deal_id": self.deal_id,
            "content": self.content,
            "is_outgoing": self.is_outgoing,
            "created_at": self.created_at,
        }
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """Create Message instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            deal_id=data.get("deal_id", ""),
            content=data.get("content", ""),
            is_outgoing=data.get("is_outgoing", True),
            created_at=data.get("created_at"),
        )

    def save(self) -> str:
        """Save the message to MongoDB."""
        collection = get_mongodb_collection("messages")
        if collection is None:
            raise RuntimeError("MongoDB collection 'messages' not available")

        doc = self.to_dict()
        result = collection.update_one(
            {"_id": self._id},
            {"$set": doc},
            upsert=True
        )
        return str(result.upserted_id or self._id)

    @classmethod
    def get(cls, message_id: str) -> Optional["Message"]:
        """Get a message by ID."""
        collection = get_mongodb_collection("messages")
        if collection is None:
            return None

        try:
            data = collection.find_one({"_id": message_id})
            if data:
                return cls.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get message '{message_id}': {e}")
            return None

    @classmethod
    def find_by_deal_id(cls, deal_id: str) -> List["Message"]:
        """Find messages by deal ID."""
        collection = get_mongodb_collection("messages")
        if collection is None:
            return []

        try:
            messages = []
            for data in collection.find({"deal_id": deal_id}):
                messages.append(cls.from_dict(data))
            return messages
        except Exception as e:
            logger.error(f"Failed to find messages by deal_id '{deal_id}': {e}")
            return []

    @classmethod
    def delete(cls, message_id: str) -> bool:
        """Delete a message by ID."""
        collection = get_mongodb_collection("messages")
        if collection is None:
            return False

        try:
            result = collection.delete_one({"_id": message_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete message '{message_id}': {e}")
            return False

    def __str__(self) -> str:
        return f"Message#{self._id[:8]}"

    @property
    def pk(self):
        """Get the primary key."""
        return self._id

    @pk.setter
    def pk(self, value):
        """Set the primary key."""
        self._id = value

    @classmethod
    def objects(cls) -> "MessageManager":
        """Get the MessageManager for querying messages."""
        return MessageManager()


class MessageManager:
    """Manager for Message queries."""

    def __init__(self):
        self.collection = None

    def _get_collection(self) -> Optional[Collection]:
        if self.collection is None:
            self.collection = get_mongodb_collection("messages")
        return self.collection

    def all(self) -> List[Message]:
        """Get all messages."""
        collection = self._get_collection()
        if collection is None:
            return []

        try:
            messages = []
            for data in collection.find():
                messages.append(Message.from_dict(data))
            return messages
        except Exception as e:
            logger.error(f"Failed to get all messages: {e}")
            return []

    def filter(self, **kwargs) -> List[Message]:
        """Filter messages by criteria."""
        collection = self._get_collection()
        if collection is None:
            return []

        try:
            messages = []
            for data in collection.find(kwargs):
                messages.append(Message.from_dict(data))
            return messages
        except Exception as e:
            logger.error(f"Failed to filter messages: {e}")
            return []

    def count(self) -> int:
        """Count total messages."""
        collection = self._get_collection()
        if collection is None:
            return 0

        try:
            return collection.count_documents({})
        except Exception as e:
            logger.error(f"Failed to count messages: {e}")
            return 0

    def get(self, **kwargs) -> Optional[Message]:
        """Get a single message by criteria."""
        collection = self._get_collection()
        if collection is None:
            return None

        try:
            data = collection.find_one(kwargs)
            if data:
                return Message.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get message: {e}")
            return None

    def get_or_create(self, defaults: Optional[Dict[str, Any]] = None, **kwargs) -> tuple["Message", bool]:
        """Get existing message or create new one."""
        existing = self.get(**kwargs)
        if existing:
            return existing, False

        data = kwargs.copy()
        if defaults:
            data.update(defaults)

        message = Message(**data)
        message.save()
        return message, True


class Note:
    """
    MongoDB Note model.
    
    Represents a note on a deal.
    Uses pymongo directly for data operations.
    """

    def __init__(
        self,
        _id: Optional[str] = None,
        deal_id: str = "",
        content: str = "",
        created_by_id: Optional[str] = None,
        created_at: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.deal_id = deal_id
        self.content = content
        self.created_by_id = created_by_id
        self.created_at = created_at or datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary for MongoDB storage."""
        data = {
            "_id": self._id,
            "deal_id": self.deal_id,
            "content": self.content,
            "created_by_id": self.created_by_id,
            "created_at": self.created_at,
        }
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Note":
        """Create Note instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            deal_id=data.get("deal_id", ""),
            content=data.get("content", ""),
            created_by_id=data.get("created_by_id"),
            created_at=data.get("created_at"),
        )

    def save(self) -> str:
        """Save the note to MongoDB."""
        collection = get_mongodb_collection("notes")
        if collection is None:
            raise RuntimeError("MongoDB collection 'notes' not available")

        doc = self.to_dict()
        result = collection.update_one(
            {"_id": self._id},
            {"$set": doc},
            upsert=True
        )
        return str(result.upserted_id or self._id)

    @classmethod
    def get(cls, note_id: str) -> Optional["Note"]:
        """Get a note by ID."""
        collection = get_mongodb_collection("notes")
        if collection is None:
            return None

        try:
            data = collection.find_one({"_id": note_id})
            if data:
                return cls.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get note '{note_id}': {e}")
            return None

    @classmethod
    def find_by_deal_id(cls, deal_id: str) -> List["Note"]:
        """Find notes by deal ID."""
        collection = get_mongodb_collection("notes")
        if collection is None:
            return []

        try:
            notes = []
            for data in collection.find({"deal_id": deal_id}):
                notes.append(cls.from_dict(data))
            return notes
        except Exception as e:
            logger.error(f"Failed to find notes by deal_id '{deal_id}': {e}")
            return []

    @classmethod
    def delete(cls, note_id: str) -> bool:
        """Delete a note by ID."""
        collection = get_mongodb_collection("notes")
        if collection is None:
            return False

        try:
            result = collection.delete_one({"_id": note_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete note '{note_id}': {e}")
            return False

    def __str__(self) -> str:
        return f"Note#{self._id[:8]}"

    @property
    def pk(self):
        """Get the primary key."""
        return self._id

    @pk.setter
    def pk(self, value):
        """Set the primary key."""
        self._id = value

    @classmethod
    def objects(cls) -> "NoteManager":
        """Get the NoteManager for querying notes."""
        return NoteManager()


class NoteManager:
    """Manager for Note queries."""

    def __init__(self):
        self.collection = None

    def _get_collection(self) -> Optional[Collection]:
        if self.collection is None:
            self.collection = get_mongodb_collection("notes")
        return self.collection

    def all(self) -> List[Note]:
        """Get all notes."""
        collection = self._get_collection()
        if collection is None:
            return []

        try:
            notes = []
            for data in collection.find():
                notes.append(Note.from_dict(data))
            return notes
        except Exception as e:
            logger.error(f"Failed to get all notes: {e}")
            return []

    def filter(self, **kwargs) -> List[Note]:
        """Filter notes by criteria."""
        collection = self._get_collection()
        if collection is None:
            return []

        try:
            notes = []
            for data in collection.find(kwargs):
                notes.append(Note.from_dict(data))
            return notes
        except Exception as e:
            logger.error(f"Failed to filter notes: {e}")
            return []

    def count(self) -> int:
        """Count total notes."""
        collection = self._get_collection()
        if collection is None:
            return 0

        try:
            return collection.count_documents({})
        except Exception as e:
            logger.error(f"Failed to count notes: {e}")
            return 0

    def get(self, **kwargs) -> Optional[Note]:
        """Get a single note by criteria."""
        collection = self._get_collection()
        if collection is None:
            return None

        try:
            data = collection.find_one(kwargs)
            if data:
                return Note.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get note: {e}")
            return None

    def get_or_create(self, defaults: Optional[Dict[str, Any]] = None, **kwargs) -> tuple["Note", bool]:
        """Get existing note or create new one."""
        existing = self.get(**kwargs)
        if existing:
            return existing, False

        data = kwargs.copy()
        if defaults:
            data.update(defaults)

        note = Note(**data)
        note.save()
        return note, True


class LeadPersona:
    """
    MongoDB LeadPersona model.
    
    Represents a detailed digital twin of a lead.
    Uses pymongo directly for data operations.
    """

    def __init__(
        self,
        _id: Optional[str] = None,
        lead_id: str = "",
        campaign_id: str = "",
        pain_points: Optional[List[str]] = None,
        goals: Optional[List[str]] = None,
        messaging_preferences: Optional[Dict[str, Any]] = None,
        buy_signals: Optional[List[Dict[str, Any]]] = None,
        confidence_score: float = 0.5,
        recommendations: Optional[List[str]] = None,
        version: int = 1,
        generated_at: Optional[datetime] = None,
        last_updated: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.lead_id = lead_id
        self.campaign_id = campaign_id
        self.pain_points = pain_points or []
        self.goals = goals or []
        self.messaging_preferences = messaging_preferences or {}
        self.buy_signals = buy_signals or []
        self.confidence_score = confidence_score
        self.recommendations = recommendations or []
        self.version = version
        self.generated_at = generated_at or datetime.utcnow()
        self.last_updated = last_updated or datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary for MongoDB storage."""
        data = {
            "_id": self._id,
            "lead_id": self.lead_id,
            "campaign_id": self.campaign_id,
            "pain_points": self.pain_points,
            "goals": self.goals,
            "messaging_preferences": self.messaging_preferences,
            "buy_signals": self.buy_signals,
            "confidence_score": self.confidence_score,
            "recommendations": self.recommendations,
            "version": self.version,
            "generated_at": self.generated_at,
            "last_updated": self.last_updated,
        }
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LeadPersona":
        """Create LeadPersona instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            lead_id=data.get("lead_id", ""),
            campaign_id=data.get("campaign_id", ""),
            pain_points=data.get("pain_points", []),
            goals=data.get("goals", []),
            messaging_preferences=data.get("messaging_preferences", {}),
            buy_signals=data.get("buy_signals", []),
            confidence_score=data.get("confidence_score", 0.5),
            recommendations=data.get("recommendations", []),
            version=data.get("version", 1),
            generated_at=data.get("generated_at"),
            last_updated=data.get("last_updated"),
        )

    def save(self) -> str:
        """Save the lead persona to MongoDB."""
        collection = get_mongodb_collection("lead_personas")
        if collection is None:
            raise RuntimeError("MongoDB collection 'lead_personas' not available")

        doc = self.to_dict()
        result = collection.update_one(
            {"_id": self._id},
            {"$set": doc},
            upsert=True
        )
        return str(result.upserted_id or self._id)

    @classmethod
    def get(cls, persona_id: str) -> Optional["LeadPersona"]:
        """Get a lead persona by ID."""
        collection = get_mongodb_collection("lead_personas")
        if collection is None:
            return None

        try:
            data = collection.find_one({"_id": persona_id})
            if data:
                return cls.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get lead persona '{persona_id}': {e}")
            return None

    @classmethod
    def find_by_lead_id(cls, lead_id: str) -> List["LeadPersona"]:
        """Find lead personae by lead ID."""
        collection = get_mongodb_collection("lead_personas")
        if collection is None:
            return []

        try:
            personae = []
            for data in collection.find({"lead_id": lead_id}):
                personae.append(cls.from_dict(data))
            return personae
        except Exception as e:
            logger.error(f"Failed to find personae by lead_id '{lead_id}': {e}")
            return []

    @classmethod
    def find_by_campaign_id(cls, campaign_id: str) -> List["LeadPersona"]:
        """Find lead personae by campaign ID."""
        collection = get_mongodb_collection("lead_personas")
        if collection is None:
            return []

        try:
            personae = []
            for data in collection.find({"campaign_id": campaign_id}):
                personae.append(cls.from_dict(data))
            return personae
        except Exception as e:
            logger.error(f"Failed to find personae by campaign_id '{campaign_id}': {e}")
            return []

    @classmethod
    def delete(cls, persona_id: str) -> bool:
        """Delete a lead persona by ID."""
        collection = get_mongodb_collection("lead_personas")
        if collection is None:
            return False

        try:
            result = collection.delete_one({"_id": persona_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete lead persona '{persona_id}': {e}")
            return False

    def __str__(self) -> str:
        return f"LeadPersona v{self.version}#{self._id[:8]}"

    @property
    def pk(self):
        """Get the primary key."""
        return self._id

    @pk.setter
    def pk(self, value):
        """Set the primary key."""
        self._id = value

    @classmethod
    def objects(cls) -> "LeadPersonaManager":
        """Get the LeadPersonaManager for querying personae."""
        return LeadPersonaManager()


class LeadPersonaManager:
    """Manager for LeadPersona queries."""

    def __init__(self):
        self.collection = None

    def _get_collection(self) -> Optional[Collection]:
        if self.collection is None:
            self.collection = get_mongodb_collection("lead_personas")
        return self.collection

    def all(self) -> List[LeadPersona]:
        """Get all lead personae."""
        collection = self._get_collection()
        if collection is None:
            return []

        try:
            personae = []
            for data in collection.find():
                personae.append(LeadPersona.from_dict(data))
            return personae
        except Exception as e:
            logger.error(f"Failed to get all personae: {e}")
            return []

    def filter(self, **kwargs) -> List[LeadPersona]:
        """Filter personae by criteria."""
        collection = self._get_collection()
        if collection is None:
            return []

        try:
            personae = []
            for data in collection.find(kwargs):
                personae.append(LeadPersona.from_dict(data))
            return personae
        except Exception as e:
            logger.error(f"Failed to filter personae: {e}")
            return []

    def count(self) -> int:
        """Count total personae."""
        collection = self._get_collection()
        if collection is None:
            return 0

        try:
            return collection.count_documents({})
        except Exception as e:
            logger.error(f"Failed to count personae: {e}")
            return 0

    def get(self, **kwargs) -> Optional[LeadPersona]:
        """Get a single persona by criteria."""
        collection = self._get_collection()
        if collection is None:
            return None

        try:
            data = collection.find_one(kwargs)
            if data:
                return LeadPersona.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get persona: {e}")
            return None

    def get_or_create(self, defaults: Optional[Dict[str, Any]] = None, **kwargs) -> tuple["LeadPersona", bool]:
        """Get existing persona or create new one."""
        existing = self.get(**kwargs)
        if existing:
            return existing, False

        data = kwargs.copy()
        if defaults:
            data.update(defaults)

        persona = LeadPersona(**data)
        persona.save()
        return persona, True


class TrackedLink:
    """
    MongoDB TrackedLink model.
    
    Represents a tracked marketing link with UTM parameters.
    Uses pymongo directly for data operations.
    """

    def __init__(
        self,
        _id: Optional[str] = None,
        campaign_id: Optional[str] = None,
        original_url: str = "",
        short_code: str = "",
        is_active: bool = True,
        utm_source: str = "",
        utm_medium: str = "",
        utm_campaign: str = "",
        utm_term: str = "",
        utm_content: str = "",
        total_clicks: int = 0,
        unique_clicks: int = 0,
        created_at: Optional[datetime] = None,
        last_clicked_at: Optional[datetime] = None,
        last_ip: Optional[str] = None,
        last_user_agent: str = "",
    ):
        self._id = _id or str(uuid4())
        self.campaign_id = campaign_id
        self.original_url = original_url
        self.short_code = short_code
        self.is_active = is_active
        self.utm_source = utm_source
        self.utm_medium = utm_medium
        self.utm_campaign = utm_campaign
        self.utm_term = utm_term
        self.utm_content = utm_content
        self.total_clicks = total_clicks
        self.unique_clicks = unique_clicks
        self.created_at = created_at or datetime.utcnow()
        self.last_clicked_at = last_clicked_at
        self.last_ip = last_ip
        self.last_user_agent = last_user_agent

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary for MongoDB storage."""
        data = {
            "_id": self._id,
            "campaign_id": self.campaign_id,
            "original_url": self.original_url,
            "short_code": self.short_code,
            "is_active": self.is_active,
            "utm_source": self.utm_source,
            "utm_medium": self.utm_medium,
            "utm_campaign": self.utm_campaign,
            "utm_term": self.utm_term,
            "utm_content": self.utm_content,
            "total_clicks": self.total_clicks,
            "unique_clicks": self.unique_clicks,
            "created_at": self.created_at,
            "last_clicked_at": self.last_clicked_at,
            "last_ip": self.last_ip,
            "last_user_agent": self.last_user_agent,
        }
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrackedLink":
        """Create TrackedLink instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            campaign_id=data.get("campaign_id"),
            original_url=data.get("original_url", ""),
            short_code=data.get("short_code", ""),
            is_active=data.get("is_active", True),
            utm_source=data.get("utm_source", ""),
            utm_medium=data.get("utm_medium", ""),
            utm_campaign=data.get("utm_campaign", ""),
            utm_term=data.get("utm_term", ""),
            utm_content=data.get("utm_content", ""),
            total_clicks=data.get("total_clicks", 0),
            unique_clicks=data.get("unique_clicks", 0),
            created_at=data.get("created_at"),
            last_clicked_at=data.get("last_clicked_at"),
            last_ip=data.get("last_ip"),
            last_user_agent=data.get("last_user_agent", ""),
        )

    def save(self) -> str:
        """Save the tracked link to MongoDB."""
        collection = get_mongodb_collection("tracked_links")
        if collection is None:
            raise RuntimeError("MongoDB collection 'tracked_links' not available")

        doc = self.to_dict()
        result = collection.update_one(
            {"_id": self._id},
            {"$set": doc},
            upsert=True
        )
        return str(result.upserted_id or self._id)

    @classmethod
    def get(cls, link_id: str) -> Optional["TrackedLink"]:
        """Get a tracked link by ID."""
        collection = get_mongodb_collection("tracked_links")
        if collection is None:
            return None

        try:
            data = collection.find_one({"_id": link_id})
            if data:
                return cls.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get tracked link '{link_id}': {e}")
            return None

    @classmethod
    def find_by_short_code(cls, short_code: str) -> Optional["TrackedLink"]:
        """Find a tracked link by short code."""
        collection = get_mongodb_collection("tracked_links")
        if collection is None:
            return None

        try:
            data = collection.find_one({"short_code": short_code})
            if data:
                return cls.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to find tracked link by short_code '{short_code}': {e}")
            return None

    @classmethod
    def find_by_campaign_id(cls, campaign_id: str) -> List["TrackedLink"]:
        """Find tracked links by campaign ID."""
        collection = get_mongodb_collection("tracked_links")
        if collection is None:
            return []

        try:
            links = []
            for data in collection.find({"campaign_id": campaign_id}):
                links.append(cls.from_dict(data))
            return links
        except Exception as e:
            logger.error(f"Failed to find links by campaign_id '{campaign_id}': {e}")
            return []

    @classmethod
    def delete(cls, link_id: str) -> bool:
        """Delete a tracked link by ID."""
        collection = get_mongodb_collection("tracked_links")
        if collection is None:
            return False

        try:
            result = collection.delete_one({"_id": link_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete tracked link '{link_id}': {e}")
            return False

    def __str__(self) -> str:
        return f"TrackedLink#{self.short_code}"

    @property
    def pk(self):
        """Get the primary key."""
        return self._id

    @pk.setter
    def pk(self, value):
        """Set the primary key."""
        self._id = value

    @classmethod
    def objects(cls) -> "TrackedLinkManager":
        """Get the TrackedLinkManager for querying links."""
        return TrackedLinkManager()


class TrackedLinkManager:
    """Manager for TrackedLink queries."""

    def __init__(self):
        self.collection = None

    def _get_collection(self) -> Optional[Collection]:
        if self.collection is None:
            self.collection = get_mongodb_collection("tracked_links")
        return self.collection

    def all(self) -> List[TrackedLink]:
        """Get all tracked links."""
        collection = self._get_collection()
        if collection is None:
            return []

        try:
            links = []
            for data in collection.find():
                links.append(TrackedLink.from_dict(data))
            return links
        except Exception as e:
            logger.error(f"Failed to get all tracked links: {e}")
            return []

    def filter(self, **kwargs) -> List[TrackedLink]:
        """Filter tracked links by criteria."""
        collection = self._get_collection()
        if collection is None:
            return []

        try:
            links = []
            for data in collection.find(kwargs):
                links.append(TrackedLink.from_dict(data))
            return links
        except Exception as e:
            logger.error(f"Failed to filter tracked links: {e}")
            return []

    def count(self) -> int:
        """Count total tracked links."""
        collection = self._get_collection()
        if collection is None:
            return 0

        try:
            return collection.count_documents({})
        except Exception as e:
            logger.error(f"Failed to count tracked links: {e}")
            return 0

    def get(self, **kwargs) -> Optional[TrackedLink]:
        """Get a single tracked link by criteria."""
        collection = self._get_collection()
        if collection is None:
            return None

        try:
            data = collection.find_one(kwargs)
            if data:
                return TrackedLink.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get tracked link: {e}")
            return None

    def get_or_create(self, defaults: Optional[Dict[str, Any]] = None, **kwargs) -> tuple["TrackedLink", bool]:
        """Get existing tracked link or create new one."""
        existing = self.get(**kwargs)
        if existing:
            return existing, False

        data = kwargs.copy()
        if defaults:
            data.update(defaults)

        link = TrackedLink(**data)
        link.save()
        return link, True


class LinkClick:
    """
    MongoDB LinkClick model.
    
    Represents an individual click on a tracked link.
    Uses pymongo directly for data operations.
    """

    def __init__(
        self,
        _id: Optional[str] = None,
        link_id: str = "",
        ip_address: Optional[str] = None,
        user_agent: str = "",
        referrer: str = "",
        clicked_at: Optional[datetime] = None,
        device_type: str = "",
        country: str = "",
    ):
        self._id = _id or str(uuid4())
        self.link_id = link_id
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.referrer = referrer
        self.clicked_at = clicked_at or datetime.utcnow()
        self.device_type = device_type
        self.country = country

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary for MongoDB storage."""
        data = {
            "_id": self._id,
            "link_id": self.link_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "referrer": self.referrer,
            "clicked_at": self.clicked_at,
            "device_type": self.device_type,
            "country": self.country,
        }
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LinkClick":
        """Create LinkClick instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            link_id=data.get("link_id", ""),
            ip_address=data.get("ip_address"),
            user_agent=data.get("user_agent", ""),
            referrer=data.get("referrer", ""),
            clicked_at=data.get("clicked_at"),
            device_type=data.get("device_type", ""),
            country=data.get("country", ""),
        )

    def save(self) -> str:
        """Save the link click to MongoDB."""
        collection = get_mongodb_collection("link_clicks")
        if collection is None:
            raise RuntimeError("MongoDB collection 'link_clicks' not available")

        doc = self.to_dict()
        result = collection.update_one(
            {"_id": self._id},
            {"$set": doc},
            upsert=True
        )
        return str(result.upserted_id or self._id)

    @classmethod
    def get(cls, click_id: str) -> Optional["LinkClick"]:
        """Get a link click by ID."""
        collection = get_mongodb_collection("link_clicks")
        if collection is None:
            return None

        try:
            data = collection.find_one({"_id": click_id})
            if data:
                return cls.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get link click '{click_id}': {e}")
            return None

    @classmethod
    def find_by_link_id(cls, link_id: str) -> List["LinkClick"]:
        """Find link clicks by link ID."""
        collection = get_mongodb_collection("link_clicks")
        if collection is None:
            return []

        try:
            clicks = []
            for data in collection.find({"link_id": link_id}):
                clicks.append(cls.from_dict(data))
            return clicks
        except Exception as e:
            logger.error(f"Failed to find clicks by link_id '{link_id}': {e}")
            return []

    @classmethod
    def delete(cls, click_id: str) -> bool:
        """Delete a link click by ID."""
        collection = get_mongodb_collection("link_clicks")
        if collection is None:
            return False

        try:
            result = collection.delete_one({"_id": click_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete link click '{click_id}': {e}")
            return False

    def __str__(self) -> str:
        return f"LinkClick#{self._id[:8]}"

    @property
    def pk(self):
        """Get the primary key."""
        return self._id

    @pk.setter
    def pk(self, value):
        """Set the primary key."""
        self._id = value

    @classmethod
    def objects(cls) -> "LinkClickManager":
        """Get the LinkClickManager for querying clicks."""
        return LinkClickManager()


class LinkClickManager:
    """Manager for LinkClick queries."""

    def __init__(self):
        self.collection = None

    def _get_collection(self) -> Optional[Collection]:
        if self.collection is None:
            self.collection = get_mongodb_collection("link_clicks")
        return self.collection

    def all(self) -> List[LinkClick]:
        """Get all link clicks."""
        collection = self._get_collection()
        if collection is None:
            return []

        try:
            clicks = []
            for data in collection.find():
                clicks.append(LinkClick.from_dict(data))
            return clicks
        except Exception as e:
            logger.error(f"Failed to get all link clicks: {e}")
            return []

    def filter(self, **kwargs) -> List[LinkClick]:
        """Filter link clicks by criteria."""
        collection = self._get_collection()
        if collection is None:
            return []

        try:
            clicks = []
            for data in collection.find(kwargs):
                clicks.append(LinkClick.from_dict(data))
            return clicks
        except Exception as e:
            logger.error(f"Failed to filter link clicks: {e}")
            return []

    def count(self) -> int:
        """Count total link clicks."""
        collection = self._get_collection()
        if collection is None:
            return 0

        try:
            return collection.count_documents({})
        except Exception as e:
            logger.error(f"Failed to count link clicks: {e}")
            return 0

    def get(self, **kwargs) -> Optional[LinkClick]:
        """Get a single link click by criteria."""
        collection = self._get_collection()
        if collection is None:
            return None

        try:
            data = collection.find_one(kwargs)
            if data:
                return LinkClick.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get link click: {e}")
            return None

    def get_or_create(self, defaults: Optional[Dict[str, Any]] = None, **kwargs) -> tuple["LinkClick", bool]:
        """Get existing link click or create new one."""
        existing = self.get(**kwargs)
        if existing:
            return existing, False

        data = kwargs.copy()
        if defaults:
            data.update(defaults)

        click = LinkClick(**data)
        click.save()
        return click, True


class LinkDealConversion:
    """
    MongoDB LinkDealConversion model.
    
    Represents a conversion from a link click to a deal.
    Uses pymongo directly for data operations.
    """

    def __init__(
        self,
        _id: Optional[str] = None,
        link_id: str = "",
        click_id: Optional[str] = None,
        deal_id: str = "",
        converted_at: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.link_id = link_id
        self.click_id = click_id
        self.deal_id = deal_id
        self.converted_at = converted_at or datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary for MongoDB storage."""
        data = {
            "_id": self._id,
            "link_id": self.link_id,
            "click_id": self.click_id,
            "deal_id": self.deal_id,
            "converted_at": self.converted_at,
        }
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LinkDealConversion":
        """Create LinkDealConversion instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            link_id=data.get("link_id", ""),
            click_id=data.get("click_id"),
            deal_id=data.get("deal_id", ""),
            converted_at=data.get("converted_at"),
        )

    def save(self) -> str:
        """Save the link conversion to MongoDB."""
        collection = get_mongodb_collection("link_deal_conversions")
        if collection is None:
            raise RuntimeError("MongoDB collection 'link_deal_conversions' not available")

        doc = self.to_dict()
        result = collection.update_one(
            {"_id": self._id},
            {"$set": doc},
            upsert=True
        )
        return str(result.upserted_id or self._id)

    @classmethod
    def get(cls, conversion_id: str) -> Optional["LinkDealConversion"]:
        """Get a link conversion by ID."""
        collection = get_mongodb_collection("link_deal_conversions")
        if collection is None:
            return None

        try:
            data = collection.find_one({"_id": conversion_id})
            if data:
                return cls.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get link conversion '{conversion_id}': {e}")
            return None

    @classmethod
    def find_by_link_id(cls, link_id: str) -> List["LinkDealConversion"]:
        """Find conversions by link ID."""
        collection = get_mongodb_collection("link_deal_conversions")
        if collection is None:
            return []

        try:
            conversions = []
            for data in collection.find({"link_id": link_id}):
                conversions.append(cls.from_dict(data))
            return conversions
        except Exception as e:
            logger.error(f"Failed to find conversions by link_id '{link_id}': {e}")
            return []

    @classmethod
    def find_by_deal_id(cls, deal_id: str) -> List["LinkDealConversion"]:
        """Find conversions by deal ID."""
        collection = get_mongodb_collection("link_deal_conversions")
        if collection is None:
            return []

        try:
            conversions = []
            for data in collection.find({"deal_id": deal_id}):
                conversions.append(cls.from_dict(data))
            return conversions
        except Exception as e:
            logger.error(f"Failed to find conversions by deal_id '{deal_id}': {e}")
            return []

    @classmethod
    def delete(cls, conversion_id: str) -> bool:
        """Delete a link conversion by ID."""
        collection = get_mongodb_collection("link_deal_conversions")
        if collection is None:
            return False

        try:
            result = collection.delete_one({"_id": conversion_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete link conversion '{conversion_id}': {e}")
            return False

    def __str__(self) -> str:
        return f"LinkConversion#{self._id[:8]}"

    @property
    def pk(self):
        """Get the primary key."""
        return self._id

    @pk.setter
    def pk(self, value):
        """Set the primary key."""
        self._id = value

    @classmethod
    def objects(cls) -> "LinkDealConversionManager":
        """Get the LinkDealConversionManager for querying conversions."""
        return LinkDealConversionManager()


class LinkDealConversionManager:
    """Manager for LinkDealConversion queries."""

    def __init__(self):
        self.collection = None

    def _get_collection(self) -> Optional[Collection]:
        if self.collection is None:
            self.collection = get_mongodb_collection("link_deal_conversions")
        return self.collection

    def all(self) -> List[LinkDealConversion]:
        """Get all link conversions."""
        collection = self._get_collection()
        if collection is None:
            return []

        try:
            conversions = []
            for data in collection.find():
                conversions.append(LinkDealConversion.from_dict(data))
            return conversions
        except Exception as e:
            logger.error(f"Failed to get all conversions: {e}")
            return []

    def filter(self, **kwargs) -> List[LinkDealConversion]:
        """Filter conversions by criteria."""
        collection = self._get_collection()
        if collection is None:
            return []

        try:
            conversions = []
            for data in collection.find(kwargs):
                conversions.append(LinkDealConversion.from_dict(data))
            return conversions
        except Exception as e:
            logger.error(f"Failed to filter conversions: {e}")
            return []

    def count(self) -> int:
        """Count total conversions."""
        collection = self._get_collection()
        if collection is None:
            return 0

        try:
            return collection.count_documents({})
        except Exception as e:
            logger.error(f"Failed to count conversions: {e}")
            return 0

    def get(self, **kwargs) -> Optional[LinkDealConversion]:
        """Get a single conversion by criteria."""
        collection = self._get_collection()
        if collection is None:
            return None

        try:
            data = collection.find_one(kwargs)
            if data:
                return LinkDealConversion.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get conversion: {e}")
            return None

    def get_or_create(self, defaults: Optional[Dict[str, Any]] = None, **kwargs) -> tuple["LinkDealConversion", bool]:
        """Get existing conversion or create new one."""
        existing = self.get(**kwargs)
        if existing:
            return existing, False

        data = kwargs.copy()
        if defaults:
            data.update(defaults)

        conversion = LinkDealConversion(**data)
        conversion.save()
        return conversion, True


class LinkedInCredentials:
    """
    MongoDB LinkedInCredentials model.
    
    Represents LinkedIn credentials with encrypted storage.
    Uses pymongo directly for data operations.
    """

    STATUS_STORED = 'stored'
    STATUS_TESTED = 'tested'
    STATUS_ACTIVE = 'active'
    STATUS_INVALID = 'invalid'
    STATUS_EXPIRED = 'expired'
    STATUS_LOCKED = 'locked'
    STATUS_BACKUP = 'backup'

    def __init__(
        self,
        _id: Optional[str] = None,
        linkedin_profile_id: Optional[str] = None,
        email_encrypted: str = "",
        password_encrypted: str = "",
        username: str = "",
        status: str = STATUS_ACTIVE,
        last_verified: Optional[datetime] = None,
        verification_failed_at: Optional[datetime] = None,
        verification_failures: int = 0,
        usage_count: int = 0,
        last_used: Optional[datetime] = None,
        campaign_id: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        rotated_at: Optional[datetime] = None,
        rotation_required_days: int = 90,
        is_primary: bool = True,
        is_backup: bool = False,
        backup_of_id: Optional[str] = None,
        security_alert_sent_at: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.linkedin_profile_id = linkedin_profile_id
        self.email_encrypted = email_encrypted
        self.password_encrypted = password_encrypted
        self.username = username
        self.status = status
        self.last_verified = last_verified
        self.verification_failed_at = verification_failed_at
        self.verification_failures = verification_failures
        self.usage_count = usage_count
        self.last_used = last_used
        self.campaign_id = campaign_id
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()
        self.expires_at = expires_at
        self.rotated_at = rotated_at
        self.rotation_required_days = rotation_required_days
        self.is_primary = is_primary
        self.is_backup = is_backup
        self.backup_of_id = backup_of_id
        self.security_alert_sent_at = security_alert_sent_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary for MongoDB storage."""
        data = {
            "_id": self._id,
            "linkedin_profile_id": self.linkedin_profile_id,
            "email_encrypted": self.email_encrypted,
            "password_encrypted": self.password_encrypted,
            "username": self.username,
            "status": self.status,
            "last_verified": self.last_verified,
            "verification_failed_at": self.verification_failed_at,
            "verification_failures": self.verification_failures,
            "usage_count": self.usage_count,
            "last_used": self.last_used,
            "campaign_id": self.campaign_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expires_at": self.expires_at,
            "rotated_at": self.rotated_at,
            "rotation_required_days": self.rotation_required_days,
            "is_primary": self.is_primary,
            "is_backup": self.is_backup,
            "backup_of_id": self.backup_of_id,
            "security_alert_sent_at": self.security_alert_sent_at,
        }
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LinkedInCredentials":
        """Create LinkedInCredentials instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            linkedin_profile_id=data.get("linkedin_profile_id"),
            email_encrypted=data.get("email_encrypted", ""),
            password_encrypted=data.get("password_encrypted", ""),
            username=data.get("username", ""),
            status=data.get("status", cls.STATUS_ACTIVE),
            last_verified=data.get("last_verified"),
            verification_failed_at=data.get("verification_failed_at"),
            verification_failures=data.get("verification_failures", 0),
            usage_count=data.get("usage_count", 0),
            last_used=data.get("last_used"),
            campaign_id=data.get("campaign_id"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            expires_at=data.get("expires_at"),
            rotated_at=data.get("rotated_at"),
            rotation_required_days=data.get("rotation_required_days", 90),
            is_primary=data.get("is_primary", True),
            is_backup=data.get("is_backup", False),
            backup_of_id=data.get("backup_of_id"),
            security_alert_sent_at=data.get("security_alert_sent_at"),
        )

    def save(self) -> str:
        """Save the LinkedIn credentials to MongoDB."""
        collection = get_mongodb_collection("linkedin_credentials")
        if collection is None:
            raise RuntimeError("MongoDB collection 'linkedin_credentials' not available")

        doc = self.to_dict()
        result = collection.update_one(
            {"_id": self._id},
            {"$set": doc},
            upsert=True
        )
        return str(result.upserted_id or self._id)

    @classmethod
    def get(cls, credential_id: str) -> Optional["LinkedInCredentials"]:
        """Get LinkedIn credentials by ID."""
        collection = get_mongodb_collection("linkedin_credentials")
        if collection is None:
            return None

        try:
            data = collection.find_one({"_id": credential_id})
            if data:
                return cls.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get LinkedIn credentials '{credential_id}': {e}")
            return None

    @classmethod
    def find_by_profile_id(cls, profile_id: str) -> Optional["LinkedInCredentials"]:
        """Find credentials by LinkedIn profile ID."""
        collection = get_mongodb_collection("linkedin_credentials")
        if collection is None:
            return None

        try:
            data = collection.find_one({"linkedin_profile_id": profile_id})
            if data:
                return cls.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to find credentials by profile_id '{profile_id}': {e}")
            return None

    @classmethod
    def find_by_campaign_id(cls, campaign_id: str) -> List["LinkedInCredentials"]:
        """Find credentials by campaign ID."""
        collection = get_mongodb_collection("linkedin_credentials")
        if collection is None:
            return []

        try:
            credentials = []
            for data in collection.find({"campaign_id": campaign_id}):
                credentials.append(cls.from_dict(data))
            return credentials
        except Exception as e:
            logger.error(f"Failed to find credentials by campaign_id '{campaign_id}': {e}")
            return []

    @classmethod
    def delete(cls, credential_id: str) -> bool:
        """Delete LinkedIn credentials by ID."""
        collection = get_mongodb_collection("linkedin_credentials")
        if collection is None:
            return False

        try:
            result = collection.delete_one({"_id": credential_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete LinkedIn credentials '{credential_id}': {e}")
            return False

    def __str__(self) -> str:
        return f"LinkedInCredential#{self._id[:8]} ({self.username})"

    @property
    def pk(self):
        """Get the primary key."""
        return self._id

    @pk.setter
    def pk(self, value):
        """Set the primary key."""
        self._id = value

    @classmethod
    def objects(cls) -> "LinkedInCredentialsManager":
        """Get the LinkedInCredentialsManager for querying credentials."""
        return LinkedInCredentialsManager()


class LinkedInCredentialsManager:
    """Manager for LinkedInCredentials queries."""

    def __init__(self):
        self.collection = None

    def _get_collection(self) -> Optional[Collection]:
        if self.collection is None:
            self.collection = get_mongodb_collection("linkedin_credentials")
        return self.collection

    def all(self) -> List[LinkedInCredentials]:
        """Get all LinkedIn credentials."""
        collection = self._get_collection()
        if collection is None:
            return []

        try:
            credentials = []
            for data in collection.find():
                credentials.append(LinkedInCredentials.from_dict(data))
            return credentials
        except Exception as e:
            logger.error(f"Failed to get all LinkedIn credentials: {e}")
            return []

    def filter(self, **kwargs) -> List[LinkedInCredentials]:
        """Filter credentials by criteria."""
        collection = self._get_collection()
        if collection is None:
            return []

        try:
            credentials = []
            for data in collection.find(kwargs):
                credentials.append(LinkedInCredentials.from_dict(data))
            return credentials
        except Exception as e:
            logger.error(f"Failed to filter credentials: {e}")
            return []

    def count(self) -> int:
        """Count total credentials."""
        collection = self._get_collection()
        if collection is None:
            return 0

        try:
            return collection.count_documents({})
        except Exception as e:
            logger.error(f"Failed to count credentials: {e}")
            return 0

    def get(self, **kwargs) -> Optional[LinkedInCredentials]:
        """Get a single credential by criteria."""
        collection = self._get_collection()
        if collection is None:
            return None

        try:
            data = collection.find_one(kwargs)
            if data:
                return LinkedInCredentials.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get credential: {e}")
            return None

    def get_or_create(self, defaults: Optional[Dict[str, Any]] = None, **kwargs) -> tuple["LinkedInCredentials", bool]:
        """Get existing credential or create new one."""
        existing = self.get(**kwargs)
        if existing:
            return existing, False

        data = kwargs.copy()
        if defaults:
            data.update(defaults)

        credential = LinkedInCredentials(**data)
        credential.save()
        return credential, True


class LinkedInCredentialLog:
    """
    MongoDB LinkedInCredentialLog model.
    
    Represents an audit log for LinkedIn credential actions.
    Uses pymongo directly for data operations.
    """

    ACTION_VERIFIED = 'verified'
    ACTION_FAILED = 'failed'
    ACTION_LOCKED = 'locked'
    ACTION_UNLOCKED = 'unlocked'
    ACTION_ROTATED = 'rotated'
    ACTION_BACKUP = 'backup'
    ACTION_USAGE = 'usage'

    def __init__(
        self,
        _id: Optional[str] = None,
        credential_id: str = "",
        action: str = "",
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: str = "",
        created_at: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.credential_id = credential_id
        self.action = action
        self.details = details or {}
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.created_at = created_at or datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary for MongoDB storage."""
        data = {
            "_id": self._id,
            "credential_id": self.credential_id,
            "action": self.action,
            "details": self.details,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "created_at": self.created_at,
        }
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LinkedInCredentialLog":
        """Create LinkedInCredentialLog instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            credential_id=data.get("credential_id", ""),
            action=data.get("action", ""),
            details=data.get("details", {}),
            ip_address=data.get("ip_address"),
            user_agent=data.get("user_agent", ""),
            created_at=data.get("created_at"),
        )

    def save(self) -> str:
        """Save the credential log to MongoDB."""
        collection = get_mongodb_collection("linkedin_credential_logs")
        if collection is None:
            raise RuntimeError("MongoDB collection 'linkedin_credential_logs' not available")

        doc = self.to_dict()
        result = collection.update_one(
            {"_id": self._id},
            {"$set": doc},
            upsert=True
        )
        return str(result.upserted_id or self._id)

    @classmethod
    def get(cls, log_id: str) -> Optional["LinkedInCredentialLog"]:
        """Get a credential log by ID."""
        collection = get_mongodb_collection("linkedin_credential_logs")
        if collection is None:
            return None

        try:
            data = collection.find_one({"_id": log_id})
            if data:
                return cls.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get credential log '{log_id}': {e}")
            return None

    @classmethod
    def find_by_credential_id(cls, credential_id: str) -> List["LinkedInCredentialLog"]:
        """Find logs by credential ID."""
        collection = get_mongodb_collection("linkedin_credential_logs")
        if collection is None:
            return []

        try:
            logs = []
            for data in collection.find({"credential_id": credential_id}):
                logs.append(cls.from_dict(data))
            return logs
        except Exception as e:
            logger.error(f"Failed to find logs by credential_id '{credential_id}': {e}")
            return []

    @classmethod
    def delete(cls, log_id: str) -> bool:
        """Delete a credential log by ID."""
        collection = get_mongodb_collection("linkedin_credential_logs")
        if collection is None:
            return False

        try:
            result = collection.delete_one({"_id": log_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete credential log '{log_id}': {e}")
            return False

    def __str__(self) -> str:
        return f"LinkedInCredentialLog#{self._id[:8]} - {self.action}"

    @property
    def pk(self):
        """Get the primary key."""
        return self._id

    @pk.setter
    def pk(self, value):
        """Set the primary key."""
        self._id = value

    @classmethod
    def objects(cls) -> "LinkedInCredentialLogManager":
        """Get the LinkedInCredentialLogManager for querying logs."""
        return LinkedInCredentialLogManager()


class LinkedInCredentialLogManager:
    """Manager for LinkedInCredentialLog queries."""

    def __init__(self):
        self.collection = None

    def _get_collection(self) -> Optional[Collection]:
        if self.collection is None:
            self.collection = get_mongodb_collection("linkedin_credential_logs")
        return self.collection

    def all(self) -> List[LinkedInCredentialLog]:
        """Get all credential logs."""
        collection = self._get_collection()
        if collection is None:
            return []

        try:
            logs = []
            for data in collection.find():
                logs.append(LinkedInCredentialLog.from_dict(data))
            return logs
        except Exception as e:
            logger.error(f"Failed to get all credential logs: {e}")
            return []

    def filter(self, **kwargs) -> List[LinkedInCredentialLog]:
        """Filter logs by criteria."""
        collection = self._get_collection()
        if collection is None:
            return []

        try:
            logs = []
            for data in collection.find(kwargs):
                logs.append(LinkedInCredentialLog.from_dict(data))
            return logs
        except Exception as e:
            logger.error(f"Failed to filter logs: {e}")
            return []

    def count(self) -> int:
        """Count total logs."""
        collection = self._get_collection()
        if collection is None:
            return 0

        try:
            return collection.count_documents({})
        except Exception as e:
            logger.error(f"Failed to count logs: {e}")
            return 0

    def get(self, **kwargs) -> Optional[LinkedInCredentialLog]:
        """Get a single log by criteria."""
        collection = self._get_collection()
        if collection is None:
            return None

        try:
            data = collection.find_one(kwargs)
            if data:
                return LinkedInCredentialLog.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get log: {e}")
            return None

    def get_or_create(self, defaults: Optional[Dict[str, Any]] = None, **kwargs) -> tuple["LinkedInCredentialLog", bool]:
        """Get existing log or create new one."""
        existing = self.get(**kwargs)
        if existing:
            return existing, False

        data = kwargs.copy()
        if defaults:
            data.update(defaults)

        log = LinkedInCredentialLog(**data)
        log.save()
        return log, True


class SiteConfig:
    """
    MongoDB SiteConfig model.
    
    Represents global site configuration.
    Uses pymongo directly for data operations.
    """

    def __init__(
        self,
        _id: Optional[str] = None,
        llm_provider: str = "",
        llm_api_key: str = "",
        ai_model: str = "",
        llm_api_base: str = "",
        finder_api_key: str = "",
        linkedin_username: str = "",
        linkedin_campaign: str = "",
        daily_connection_limit: int = 20,
        daily_follow_up_limit: int = 25,
        velocity: int = 20,
        cooldown_minutes: int = 0,
        bettercontact_api_key: str = "",
        contacts_api_token: str = "",
        contacts_api_url: str = "",
    ):
        self._id = _id or str(uuid4())
        self.llm_provider = llm_provider
        self.llm_api_key = llm_api_key
        self.ai_model = ai_model
        self.llm_api_base = llm_api_base
        self.finder_api_key = finder_api_key
        self.linkedin_username = linkedin_username
        self.linkedin_campaign = linkedin_campaign
        self.daily_connection_limit = daily_connection_limit
        self.daily_follow_up_limit = daily_follow_up_limit
        self.velocity = velocity
        self.cooldown_minutes = cooldown_minutes
        self.bettercontact_api_key = bettercontact_api_key
        self.contacts_api_token = contacts_api_token
        self.contacts_api_url = contacts_api_url

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary for MongoDB storage."""
        data = {
            "_id": self._id,
            "llm_provider": self.llm_provider,
            "llm_api_key": self.llm_api_key,
            "ai_model": self.ai_model,
            "llm_api_base": self.llm_api_base,
            "finder_api_key": self.finder_api_key,
            "linkedin_username": self.linkedin_username,
            "linkedin_campaign": self.linkedin_campaign,
            "daily_connection_limit": self.daily_connection_limit,
            "daily_follow_up_limit": self.daily_follow_up_limit,
            "velocity": self.velocity,
            "cooldown_minutes": self.cooldown_minutes,
            "bettercontact_api_key": self.bettercontact_api_key,
            "contacts_api_token": self.contacts_api_token,
            "contacts_api_url": self.contacts_api_url,
        }
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SiteConfig":
        """Create SiteConfig instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            llm_provider=data.get("llm_provider", ""),
            llm_api_key=data.get("llm_api_key", ""),
            ai_model=data.get("ai_model", ""),
            llm_api_base=data.get("llm_api_base", ""),
            finder_api_key=data.get("finder_api_key", ""),
            linkedin_username=data.get("linkedin_username", ""),
            linkedin_campaign=data.get("linkedin_campaign", ""),
            daily_connection_limit=data.get("daily_connection_limit", 20),
            daily_follow_up_limit=data.get("daily_follow_up_limit", 25),
            velocity=data.get("velocity", 20),
            cooldown_minutes=data.get("cooldown_minutes", 0),
            bettercontact_api_key=data.get("bettercontact_api_key", ""),
            contacts_api_token=data.get("contacts_api_token", ""),
            contacts_api_url=data.get("contacts_api_url", ""),
        )

    def save(self) -> str:
        """Save the site config to MongoDB."""
        collection = get_mongodb_collection("site_config")
        if collection is None:
            raise RuntimeError("MongoDB collection 'site_config' not available")

        doc = self.to_dict()
        result = collection.update_one(
            {"_id": self._id},
            {"$set": doc},
            upsert=True
        )
        return str(result.upserted_id or self._id)

    @classmethod
    def get(cls, config_id: str) -> Optional["SiteConfig"]:
        """Get a site config by ID."""
        collection = get_mongodb_collection("site_config")
        if collection is None:
            return None

        try:
            data = collection.find_one({"_id": config_id})
            if data:
                return cls.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get site config '{config_id}': {e}")
            return None

    @classmethod
    def find_by_llm_provider(cls, llm_provider: str) -> Optional["SiteConfig"]:
        """Find site config by LLM provider."""
        collection = get_mongodb_collection("site_config")
        if collection is None:
            return None

        try:
            data = collection.find_one({"llm_provider": llm_provider})
            if data:
                return cls.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to find site config by llm_provider '{llm_provider}': {e}")
            return None

    @classmethod
    def delete(cls, config_id: str) -> bool:
        """Delete a site config by ID."""
        collection = get_mongodb_collection("site_config")
        if collection is None:
            return False

        try:
            result = collection.delete_one({"_id": config_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete site config '{config_id}': {e}")
            return False

    def __str__(self) -> str:
        return f"SiteConfig#{self._id[:8]}"

    @property
    def pk(self):
        """Get the primary key."""
        return self._id

    @pk.setter
    def pk(self, value):
        """Set the primary key."""
        self._id = value

    @classmethod
    def objects(cls) -> "SiteConfigManager":
        """Get the SiteConfigManager for querying configs."""
        return SiteConfigManager()


class SiteConfigManager:
    """Manager for SiteConfig queries."""

    def __init__(self):
        self.collection = None

    def _get_collection(self) -> Optional[Collection]:
        if self.collection is None:
            self.collection = get_mongodb_collection("site_config")
        return self.collection

    def all(self) -> List[SiteConfig]:
        """Get all site configs."""
        collection = self._get_collection()
        if collection is None:
            return []

        try:
            configs = []
            for data in collection.find():
                configs.append(SiteConfig.from_dict(data))
            return configs
        except Exception as e:
            logger.error(f"Failed to get all site configs: {e}")
            return []

    def filter(self, **kwargs) -> List[SiteConfig]:
        """Filter configs by criteria."""
        collection = self._get_collection()
        if collection is None:
            return []

        try:
            configs = []
            for data in collection.find(kwargs):
                configs.append(SiteConfig.from_dict(data))
            return configs
        except Exception as e:
            logger.error(f"Failed to filter configs: {e}")
            return []

    def count(self) -> int:
        """Count total configs."""
        collection = self._get_collection()
        if collection is None:
            return 0

        try:
            return collection.count_documents({})
        except Exception as e:
            logger.error(f"Failed to count configs: {e}")
            return 0

    def get(self, **kwargs) -> Optional[SiteConfig]:
        """Get a single config by criteria."""
        collection = self._get_collection()
        if collection is None:
            return None

        try:
            data = collection.find_one(kwargs)
            if data:
                return SiteConfig.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get config: {e}")
            return None

    def get_or_create(self, defaults: Optional[Dict[str, Any]] = None, **kwargs) -> tuple["SiteConfig", bool]:
        """Get existing config or create new one."""
        existing = self.get(**kwargs)
        if existing:
            return existing, False

        data = kwargs.copy()
        if defaults:
            data.update(defaults)

        config = SiteConfig(**data)
        config.save()
        return config, True


class Task:
    """
    MongoDB Task model.
    
    Represents a scheduled task in the system.
    Uses pymongo directly for data operations.
    """

    TASK_TYPE_CONNECT = "connect"
    TASK_TYPE_CHECK_PENDING = "check_pending"
    TASK_TYPE_FOLLOW_UP = "follow_up"
    TASK_TYPE_SEND_MANUAL_MESSAGE = "send_manual_message"

    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"

    def __init__(
        self,
        _id: Optional[str] = None,
        task_type: str = "",
        status: str = STATUS_PENDING,
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

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary for MongoDB storage."""
        data = {
            "_id": self._id,
            "task_type": self.task_type,
            "status": self.status,
            "scheduled_at": self.scheduled_at,
            "payload": self.payload,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Create Task instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            task_type=data.get("task_type", ""),
            status=data.get("status", cls.STATUS_PENDING),
            scheduled_at=data.get("scheduled_at"),
            payload=data.get("payload", {}),
            created_at=data.get("created_at"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
        )

    def save(self) -> str:
        """Save the task to MongoDB."""
        collection = get_mongodb_collection("tasks")
        if collection is None:
            raise RuntimeError("MongoDB collection 'tasks' not available")

        doc = self.to_dict()
        result = collection.update_one(
            {"_id": self._id},
            {"$set": doc},
            upsert=True
        )
        return str(result.upserted_id or self._id)

    @classmethod
    def get(cls, task_id: str) -> Optional["Task"]:
        """Get a task by ID."""
        collection = get_mongodb_collection("tasks")
        if collection is None:
            return None

        try:
            data = collection.find_one({"_id": task_id})
            if data:
                return cls.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get task '{task_id}': {e}")
            return None

    @classmethod
    def find_by_status(cls, status: str) -> List["Task"]:
        """Find tasks by status."""
        collection = get_mongodb_collection("tasks")
        if collection is None:
            return []

        try:
            tasks = []
            for data in collection.find({"status": status}):
                tasks.append(cls.from_dict(data))
            return tasks
        except Exception as e:
            logger.error(f"Failed to find tasks by status '{status}': {e}")
            return []

    @classmethod
    def delete(cls, task_id: str) -> bool:
        """Delete a task by ID."""
        collection = get_mongodb_collection("tasks")
        if collection is None:
            return False

        try:
            result = collection.delete_one({"_id": task_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete task '{task_id}': {e}")
            return False

    def __str__(self) -> str:
        return f"Task#{self._id[:8]} - {self.task_type} [{self.status}]"

    @property
    def pk(self):
        """Get the primary key."""
        return self._id

    @pk.setter
    def pk(self, value):
        """Set the primary key."""
        self._id = value

    @classmethod
    def objects(cls) -> "TaskManager":
        """Get the TaskManager for querying tasks."""
        return TaskManager()


class TaskManager:
    """Manager for Task queries."""

    def __init__(self):
        self.collection = None

    def _get_collection(self) -> Optional[Collection]:
        if self.collection is None:
            self.collection = get_mongodb_collection("tasks")
        return self.collection

    def all(self) -> List[Task]:
        """Get all tasks."""
        collection = self._get_collection()
        if collection is None:
            return []

        try:
            tasks = []
            for data in collection.find():
                tasks.append(Task.from_dict(data))
            return tasks
        except Exception as e:
            logger.error(f"Failed to get all tasks: {e}")
            return []

    def filter(self, **kwargs) -> List[Task]:
        """Filter tasks by criteria."""
        collection = self._get_collection()
        if collection is None:
            return []

        try:
            tasks = []
            for data in collection.find(kwargs):
                tasks.append(Task.from_dict(data))
            return tasks
        except Exception as e:
            logger.error(f"Failed to filter tasks: {e}")
            return []

    def count(self) -> int:
        """Count total tasks."""
        collection = self._get_collection()
        if collection is None:
            return 0

        try:
            return collection.count_documents({})
        except Exception as e:
            logger.error(f"Failed to count tasks: {e}")
            return 0

    def get(self, **kwargs) -> Optional[Task]:
        """Get a single task by criteria."""
        collection = self._get_collection()
        if collection is None:
            return None

        try:
            data = collection.find_one(kwargs)
            if data:
                return Task.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get task: {e}")
            return None

    def get_or_create(self, defaults: Optional[Dict[str, Any]] = None, **kwargs) -> tuple["Task", bool]:
        """Get existing task or create new one."""
        existing = self.get(**kwargs)
        if existing:
            return existing, False

        data = kwargs.copy()
        if defaults:
            data.update(defaults)

        task = Task(**data)
        task.save()
        return task, True


class DealManager:
    """Manager for Deal queries."""
    
    def __init__(self):
        self.collection = None
    
    def _get_collection(self) -> Optional[Collection]:
        if self.collection is None:
            self.collection = get_mongodb_collection("deals")
        return self.collection
    
    def all(self) -> List[Deal]:
        """Get all deals."""
        collection = self._get_collection()
        if collection is None:
            return []
        
        try:
            deals = []
            for data in collection.find():
                deals.append(Deal.from_dict(data))
            return deals
        except Exception as e:
            logger.error(f"Failed to get all deals: {e}")
            return []
    
    def filter(self, **kwargs) -> List[Deal]:
        """Filter deals by criteria."""
        collection = self._get_collection()
        if collection is None:
            return []
        
        try:
            deals = []
            for data in collection.find(kwargs):
                deals.append(Deal.from_dict(data))
            return deals
        except Exception as e:
            logger.error(f"Failed to filter deals: {e}")
            return []
    
    def count(self) -> int:
        """Count total deals."""
        collection = self._get_collection()
        if collection is None:
            return 0
        
        try:
            return collection.count_documents({})
        except Exception as e:
            logger.error(f"Failed to count deals: {e}")
            return 0
    
    def get(self, **kwargs) -> Optional[Deal]:
        """Get a single deal by criteria."""
        collection = self._get_collection()
        if collection is None:
            return None
        
        try:
            data = collection.find_one(kwargs)
            if data:
                return Deal.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get deal: {e}")
            return None
    
    def get_or_create(self, defaults: Optional[Dict[str, Any]] = None, **kwargs) -> tuple["Deal", bool]:
        """Get existing deal or create new one."""
        existing = self.get(**kwargs)
        if existing:
            return existing, False
        
        data = kwargs.copy()
        if defaults:
            data.update(defaults)
        
        deal = Deal(**data)
        deal.save()
        return deal, True


def ensure_mongodb_indexes():
    """Create required indexes for MongoDB collections."""
    if not check_mongodb_connection():
        logger.warning("MongoDB not connected, skipping index creation")
        return
    
    db = get_mongodb()
    if db is None:
        return
    
    indexes = [
        # Lead indexes
        ("leads", [
            ("public_identifier", {"name": "public_identifier_idx"}),
            ("linkedin_url", {"name": "linkedin_url_idx"}),
            ("creation_date", {"name": "creation_date_idx"}),
        ]),
        # Campaign indexes
        ("campaigns", [
            ("name", {"name": "name_idx"}),
            ("is_paused", {"name": "is_paused_idx"}),
        ]),
        # Deal indexes
        ("deals", [
            ("lead_id", {"name": "lead_id_idx"}),
            ("campaign_id", {"name": "campaign_id_idx"}),
            ("state", {"name": "state_idx"}),
        ]),
        # Message indexes
        ("messages", [
            ("deal_id", {"name": "deal_id_idx"}),
            ("created_at", {"name": "created_at_idx"}),
        ]),
        # Note indexes
        ("notes", [
            ("deal_id", {"name": "deal_id_idx"}),
            ("created_at", {"name": "created_at_idx"}),
        ]),
        # Lead Persona indexes
        ("lead_personas", [
            ("lead_id", {"name": "lead_id_idx"}),
            ("campaign_id", {"name": "campaign_id_idx"}),
            ("generated_at", {"name": "generated_at_idx"}),
        ]),
        # Tracked Link indexes
        ("tracked_links", [
            ("campaign_id", {"name": "campaign_id_idx"}),
            ("short_code", {"name": "short_code_idx"}),
            ("created_at", {"name": "created_at_idx"}),
        ]),
        # Link Click indexes
        ("link_clicks", [
            ("link_id", {"name": "link_id_idx"}),
            ("clicked_at", {"name": "clicked_at_idx"}),
            ("ip_address", {"name": "ip_address_idx"}),
        ]),
        # Link Deal Conversion indexes
        ("link_deal_conversions", [
            ("link_id", {"name": "link_id_idx"}),
            ("deal_id", {"name": "deal_id_idx"}),
            ("converted_at", {"name": "converted_at_idx"}),
        ]),
        # LinkedIn Credentials indexes
        ("linkedin_credentials", [
            ("linkedin_profile_id", {"name": "linkedin_profile_id_idx"}),
            ("campaign_id", {"name": "campaign_id_idx"}),
            ("status", {"name": "status_idx"}),
            ("last_verified", {"name": "last_verified_idx"}),
        ]),
        # LinkedIn Credential Log indexes
        ("linkedin_credential_logs", [
            ("credential_id", {"name": "credential_id_idx"}),
            ("created_at", {"name": "created_at_idx"}),
        ]),
        # Site Config indexes
        ("site_config", [
            ("llm_provider", {"name": "llm_provider_idx"}),
        ]),
        # Task indexes
        ("tasks", [
            ("status", {"name": "status_idx"}),
            ("scheduled_at", {"name": "scheduled_at_idx"}),
            ("task_type", {"name": "task_type_idx"}),
            ("created_at", {"name": "created_at_idx"}),
        ]),
    ]
    
    for collection_name, collection_indexes in indexes:
        try:
            collection = db[collection_name]
            for field_name, options in collection_indexes:
                try:
                    collection.create_index(field_name, name=options["name"])
                    logger.info(f"Created index '{options['name']}' on '{collection_name}'")
                except Exception as e:
                    logger.error(f"Failed to create index '{options['name']}': {e}")
        except Exception as e:
            logger.error(f"Failed to process indexes for '{collection_name}': {e}")
