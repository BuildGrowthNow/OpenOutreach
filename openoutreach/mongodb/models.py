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