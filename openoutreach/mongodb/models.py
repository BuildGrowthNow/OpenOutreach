"""
MongoDB Models for OpenOutreach

This module provides MongoDB-compatible versions of the CRM models
that use pymongo directly for data operations.
"""

import logging
import time
from datetime import datetime, timezone as tz
from typing import Any, ClassVar, Dict, List, Optional, TypeVar
from uuid import uuid4

from pymongo.collection import Collection

from .connection import (
    get_mongodb,
    get_mongodb_collection,
    check_mongodb_connection,
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
        cached_profile: Optional[Dict[str, Any]] = None,
        contact_info: Optional[Dict[str, Any]] = None,
        api_email: Optional[str] = None,
        notes: Optional[str] = None,
        disqualified: bool = False,
        connection_degree: Optional[int] = None,
        user_id: Optional[str] = None,
        creation_date: Optional[datetime] = None,
        update_date: Optional[datetime] = None,
        phone: Optional[str] = None,
        phone_source: Optional[str] = None,
        phone_on_whatsapp: Optional[bool] = None,
        full_name: Optional[str] = None,
        company: Optional[str] = None,
        headline: Optional[str] = None,
    ):
        self._id = _id or str(uuid4())
        self.linkedin_url = linkedin_url
        self.public_identifier = public_identifier
        self.urn = urn
        self.embedding = embedding
        self.cached_profile = cached_profile
        self.contact_info = contact_info
        self.api_email = api_email
        self.notes = notes
        self.disqualified = disqualified
        self.connection_degree = connection_degree
        self.user_id = user_id
        self.creation_date = creation_date or datetime.now(tz.utc)
        self.update_date = update_date or datetime.now(tz.utc)
        self.phone = phone
        self.phone_source = phone_source
        self.phone_on_whatsapp = phone_on_whatsapp  # None=unknown, True=registered, False=not on WA
        self.full_name = full_name
        self.company = company
        self.headline = headline

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary for MongoDB storage."""
        data: Dict[str, Any] = {
            "_id": self._id,
            "linkedin_url": self.linkedin_url,
            "public_identifier": self.public_identifier,
            "disqualified": self.disqualified,
            "creation_date": self.creation_date,
            "update_date": self.update_date,
        }
        if self.urn is not None:
            data["urn"] = self.urn
        if self.embedding is not None:
            data["embedding"] = self.embedding
        if self.cached_profile is not None:
            data["cached_profile"] = self.cached_profile
        if self.contact_info is not None:
            data["contact_info"] = self.contact_info
        if self.api_email is not None:
            data["api_email"] = self.api_email
        if self.notes is not None:
            data["notes"] = self.notes
        if self.connection_degree is not None:
            data["connection_degree"] = self.connection_degree
        if self.user_id is not None:
            data["user_id"] = self.user_id
        if self.phone is not None:
            data["phone"] = self.phone
        if self.phone_source is not None:
            data["phone_source"] = self.phone_source
        if self.phone_on_whatsapp is not None:
            data["phone_on_whatsapp"] = self.phone_on_whatsapp
        if self.full_name is not None:
            data["full_name"] = self.full_name
        if self.company is not None:
            data["company"] = self.company
        if self.headline is not None:
            data["headline"] = self.headline
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
            cached_profile=data.get("cached_profile"),
            contact_info=data.get("contact_info"),
            api_email=data.get("api_email"),
            notes=data.get("notes"),
            disqualified=data.get("disqualified", False),
            connection_degree=data.get("connection_degree"),
            user_id=data.get("user_id"),
            creation_date=data.get("creation_date"),
            update_date=data.get("update_date"),
            phone=data.get("phone"),
            phone_source=data.get("phone_source"),
            phone_on_whatsapp=data.get("phone_on_whatsapp"),
            full_name=data.get("full_name"),
            company=data.get("company"),
            headline=data.get("headline"),
        )

    def save(self, update_fields: Optional[List[str]] = None) -> str:
        """Save the lead to MongoDB.

        If update_fields is given, only those fields are written (partial update).
        """
        from pymongo.errors import DuplicateKeyError

        collection = get_mongodb_collection("leads")
        if collection is None:
            raise RuntimeError("MongoDB collection 'leads' not available")

        self.update_date = datetime.now(tz.utc)

        try:
            if update_fields:
                field_map = self.to_dict()
                update_doc = {f: field_map[f] for f in update_fields if f in field_map}
                update_doc["update_date"] = self.update_date
                collection.update_one({"_id": self._id}, {"$set": update_doc}, upsert=True)
            else:
                doc = self.to_dict()
                collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
        except DuplicateKeyError:
            # Concurrent insert on public_identifier - load the winner's _id
            existing = collection.find_one({"public_identifier": self.public_identifier})
            if existing:
                self._id = str(existing["_id"])
        return self._id

    @classmethod
    def get(cls, lead_id: str) -> Optional["Lead"]:
        """Get a lead by ID."""
        collection = get_mongodb_collection("leads")
        if collection is None:
            return None

        data = collection.find_one({"_id": lead_id})
        if data:
            return cls.from_dict(data)
        return None

    @classmethod
    def find_by_public_identifier(cls, public_identifier: str) -> Optional["Lead"]:
        """Find a lead by public identifier."""
        collection = get_mongodb_collection("leads")
        if collection is None:
            return None

        data = collection.find_one({"public_identifier": public_identifier})
        if data:
            return cls.from_dict(data)
        return None

    @classmethod
    def get_by_public_id(cls, public_identifier: str) -> Optional["Lead"]:
        """Alias for find_by_public_identifier."""
        return cls.find_by_public_identifier(public_identifier)

    @classmethod
    def get_by_urn(cls, urn: str) -> Optional["Lead"]:
        """Get a lead by URN."""
        return cls.find_by_urn(urn)

    @classmethod
    def find_with_embeddings(cls, campaign_id: str) -> List["Lead"]:
        """Find leads that have embeddings for a campaign's deals."""
        collection = get_mongodb_collection("leads")
        if collection is None:
            return []
        deals_collection = get_mongodb_collection("deals")
        if deals_collection is None:
            return []
        lead_ids = [str(d["lead_id"]) for d in deals_collection.find(
            {"campaign_id": campaign_id}, {"lead_id": 1}
        )]
        if not lead_ids:
            return []
        return [cls.from_dict(d) for d in collection.find({
            "_id": {"$in": lead_ids},
            "embedding": {"$ne": None}
        })]

    @classmethod
    def find_by_linkedin_url(cls, linkedin_url: str) -> Optional["Lead"]:
        """Find a lead by LinkedIn URL."""
        collection = get_mongodb_collection("leads")
        if collection is None:
            return None

        data = collection.find_one({"linkedin_url": linkedin_url})
        if data:
            return cls.from_dict(data)
        return None

    @classmethod
    def find_by_urn(cls, urn: str) -> Optional["Lead"]:
        """Find a lead by URN."""
        collection = get_mongodb_collection("leads")
        if collection is None:
            return None

        data = collection.find_one({"urn": urn})
        if data:
            return cls.from_dict(data)
        return None

    @classmethod
    def find_by_user_id(cls, user_id: str) -> List["Lead"]:
        """Find leads by user ID."""
        collection = get_mongodb_collection("leads")
        if collection is None:
            return []

        return [cls.from_dict(d) for d in collection.find({"user_id": user_id})]

    @classmethod
    def delete(cls, lead_id: str) -> bool:
        """Delete a lead by ID."""
        collection = get_mongodb_collection("leads")
        if collection is None:
            return False

        result = collection.delete_one({"_id": lead_id})
        return result.deleted_count > 0

    def __str__(self):
        label = self.public_identifier or self.linkedin_url or f"Lead#{self._id[:8]}"
        if self.disqualified:
            return f"(Disqualified) {label}"
        return label

    @property
    def pk(self):
        return self._id

    @pk.setter
    def pk(self, value):
        self._id = value

    @property
    def id(self):
        return self._id

    @classmethod
    def objects(cls) -> "LeadManager":
        return LeadManager()

    # ------------------------------------------------------------------
    # Lazy accessors - live Voyager scrape on demand
    # ------------------------------------------------------------------

    def get_profile(self, session) -> Optional[Dict[str, Any]]:
        """Live Voyager scrape of the parsed profile dict.

        Opportunistically sets urn and cached_profile.
        """
        from linkedin_cli.api.client import PlaywrightLinkedinAPI
        from linkedin_cli.exceptions import ProfileInaccessibleError

        session.ensure_browser()
        api = PlaywrightLinkedinAPI(session=session)
        try:
            profile, _raw = api.get_profile(public_identifier=self.public_identifier)
        except ProfileInaccessibleError:
            return None
        if not profile:
            return None

        urn = profile.get("urn") or None
        self.cached_profile = profile
        update_fields = ["cached_profile"]
        if urn and self.urn != urn:
            existing = Lead.find_by_urn(urn)
            if existing and existing._id != self._id:
                logger.warning(
                    "URN %s already owned by another lead - skipping for %s",
                    urn,
                    self.public_identifier,
                )
            else:
                self.urn = urn
                update_fields.append("urn")
        self.save(update_fields=update_fields)
        return profile

    def capture_contact_info(self, session) -> None:
        """Scrape + persist the LinkedIn contact-info overlay once connected.

        Idempotent: non-null contact_info means we already tried.
        Also writes Lead.phone from the first phone_number found, if not already set.
        """
        if self.contact_info is not None:
            return
        from linkedin_cli.api.client import PlaywrightLinkedinAPI

        session.ensure_browser()
        api = PlaywrightLinkedinAPI(session=session)
        contact, _raw = api.get_contact_info(public_identifier=self.public_identifier)
        self.contact_info = contact

        update_fields = ["contact_info"]

        if self.phone is None and contact:
            phone_numbers = contact.get("phone_numbers") or []
            if phone_numbers:
                raw = phone_numbers[0]
                normalized: Optional[str] = None
                try:
                    import phonenumbers
                    parsed = phonenumbers.parse(raw, None)
                    if phonenumbers.is_valid_number(parsed):
                        normalized = phonenumbers.format_number(
                            parsed, phonenumbers.PhoneNumberFormat.E164
                        )
                except Exception:
                    pass
                self.phone = normalized if normalized else raw
                self.phone_source = "linkedin_contact"
                update_fields.extend(["phone", "phone_source"])

        self.save(update_fields=update_fields)

    def resolve_api_email(self) -> Optional[bool]:
        """Resolve + persist a work email via the finder.

        Returns True on hit, False on miss, None if finder unavailable.
        """
        if self.api_email:
            return True
        from openoutreach.emails.finder import (
            FinderQuery,
            FinderUnavailable,
            resolve_email,
        )

        try:
            result = resolve_email(FinderQuery(linkedin_url=self.linkedin_url), user_id=self.user_id)
        except FinderUnavailable:
            return None
        if result:
            self.api_email = result.email
            self.save(update_fields=["api_email"])
            return True
        return False

    def get_urn(self, session) -> str:
        """LinkedIn URN. Reads cached; falls back to a live scrape."""
        if self.urn:
            return self.urn
        self.get_profile(session)
        if self.urn:
            return self.urn
        raise ValueError(f"Lead {self._id}: could not resolve URN after re-fetch")

    def get_embedding(self, session):
        """384-dim embedding. Lazy: scrapes + embeds on first access."""
        if self.embedding is None:
            profile = self.get_profile(session)
            if profile:
                self.embed_from_profile(profile)
        return self.embedding_array

    def embed_from_profile(self, profile: dict) -> None:
        """Compute and persist the 384-dim embedding from an in-hand profile."""
        from openoutreach.linkedin.ml.embeddings import embed_text
        from openoutreach.linkedin.ml.profile_text import build_profile_text

        text = build_profile_text({"profile": profile})
        emb = embed_text(text)
        self.embedding = emb.tobytes()
        self.save(update_fields=["embedding"])

    def to_profile_dict(self) -> dict:
        """Standard profile dict shape used by qualifiers and pools."""
        return {
            "lead_id": self._id,
            "public_identifier": self.public_identifier,
            "url": self.linkedin_url or "",
            "connection_degree": self.connection_degree,
            "meta": {},
        }

    @property
    def embedding_array(self):
        """384-dim float32 numpy array from stored bytes, or None."""
        import numpy as np

        if self.embedding is None:
            return None
        return np.frombuffer(bytes(self.embedding), dtype=np.float32).copy()

    @embedding_array.setter
    def embedding_array(self, arr):
        import numpy as np

        self.embedding = np.asarray(arr, dtype=np.float32).tobytes()

    @classmethod
    def get_labeled_arrays(cls, campaign):
        """Labeled embeddings for a campaign as (X, y) numpy arrays for warm start."""
        import numpy as np
        from openoutreach.crm.models.deal import DealState, Outcome

        collection = get_mongodb_collection("deals")
        if collection is None:
            return np.empty((0, 384), dtype=np.float32), np.empty(0, dtype=np.int32)

        deals = collection.find(
            {"campaign_id": campaign._id if hasattr(campaign, "_id") else str(campaign)},
            {"lead_id": 1, "state": 1, "outcome": 1},
        )

        label_by_lead: Dict[str, int] = {}
        for d in deals:
            lid = d.get("lead_id")
            if not lid:
                continue
            state = d.get("state", "")
            outcome = d.get("outcome", "")
            if state == DealState.FAILED.value:
                if outcome == Outcome.WRONG_FIT.value:
                    label_by_lead[lid] = 0
            else:
                label_by_lead[lid] = 1

        if not label_by_lead:
            return np.empty((0, 384), dtype=np.float32), np.empty(0, dtype=np.int32)

        leads_collection = get_mongodb_collection("leads")
        if leads_collection is None:
            return np.empty((0, 384), dtype=np.float32), np.empty(0, dtype=np.int32)

        leads_with_emb = leads_collection.find(
            {"_id": {"$in": list(label_by_lead.keys())}, "embedding": {"$ne": None}},
            {"_id": 1, "embedding": 1},
        )

        emb_map = {d["_id"]: d["embedding"] for d in leads_with_emb}

        X_list, y_list = [], []
        for lid, label in label_by_lead.items():
            emb = emb_map.get(lid)
            if emb is None:
                continue
            X_list.append(np.frombuffer(bytes(emb), dtype=np.float32))
            y_list.append(label)

        if not X_list:
            return np.empty((0, 384), dtype=np.float32), np.empty(0, dtype=np.int32)

        return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.int32)


class LeadManager:
    """Manager for Lead queries with Django-compatible interface."""

    def __init__(self):
        self.collection = None
        self._filter_query: Dict[str, Any] = {}
        self._exclude_query: Dict[str, Any] = {}

    def _get_collection(self) -> Optional[Collection]:
        if self.collection is None:
            self.collection = get_mongodb_collection("leads")
        return self.collection

    @staticmethod
    def _translate_kwargs(kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Translate Django-style lookups to MongoDB query operators."""
        query: Dict[str, Any] = {}
        for key, value in kwargs.items():
            if "__isnull" in key:
                field = key.replace("__isnull", "")
                if field == "pk":
                    field = "_id"
                query[field] = {"$eq": None} if value else {"$ne": None}
            elif "__in" in key:
                field = key.replace("__in", "")
                if field == "pk":
                    field = "_id"
                query[field] = {"$in": list(value)}
            elif "__gte" in key:
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
                field = key if key != "pk" else "_id"
                query[field] = value
        return query

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

    def filter(self, **kwargs) -> "LeadManager":
        """Filter leads by criteria. Returns self for chaining."""
        mgr = LeadManager()
        mgr._filter_query = {**self._filter_query, **self._translate_kwargs(kwargs)}
        mgr._exclude_query = self._exclude_query.copy()
        return mgr

    def exclude(self, **kwargs) -> "LeadManager":
        """Exclude leads matching criteria. Returns self for chaining."""
        mgr = LeadManager()
        mgr._filter_query = self._filter_query.copy()
        translated = self._translate_kwargs(kwargs)
        for k, v in translated.items():
            mgr._exclude_query[k] = v
        return mgr

    def _build_query(self) -> Dict[str, Any]:
        query = dict(self._filter_query)
        for field, val in self._exclude_query.items():
            if isinstance(val, dict):
                inverted = {}
                for op, v in val.items():
                    if op == "$eq":
                        inverted["$ne"] = v
                    elif op == "$ne":
                        inverted["$eq"] = v
                    elif op == "$in":
                        inverted["$nin"] = v
                    else:
                        inverted[op] = v
                query[field] = {**query.get(field, {}), **inverted} if field in query else inverted
            else:
                query[field] = {"$ne": val}
        return query

    def _find(self):
        collection = self._get_collection()
        if collection is None:
            return iter([])
        return collection.find(self._build_query())

    def exists(self) -> bool:
        """Check if any leads match the current filter."""
        collection = self._get_collection()
        if collection is None:
            return False
        return collection.count_documents(self._build_query(), limit=1) > 0

    def count(self) -> int:
        """Count matching leads."""
        collection = self._get_collection()
        if collection is None:
            return 0
        return collection.count_documents(self._build_query())

    def first(self) -> Optional[Lead]:
        """Return the first matching lead or None."""
        collection = self._get_collection()
        if collection is None:
            return None
        data = collection.find_one(self._build_query())
        if data:
            return Lead.from_dict(data)
        return None

    def values_list(self, *fields, flat: bool = False):
        """Return specified field values. With flat=True and one field, returns a flat list."""
        collection = self._get_collection()
        if collection is None:
            return []
        projection = {f if f != "pk" else "_id": 1 for f in fields}
        projection["_id"] = 1 if "_id" in projection or "pk" in fields else 0
        cursor = collection.find(self._build_query(), projection)
        results = []
        for doc in cursor:
            row = []
            for f in fields:
                key = "_id" if f == "pk" else f
                row.append(doc.get(key))
            if flat and len(fields) == 1:
                results.append(row[0])
            else:
                results.append(tuple(row))
        return results

    def get(self, **kwargs) -> Optional[Lead]:
        """Get a single lead by criteria."""
        collection = self._get_collection()
        if collection is None:
            return None
        query = self._translate_kwargs(kwargs) if kwargs else self._build_query()
        data = collection.find_one(query)
        if data:
            return Lead.from_dict(data)
        return None

    def create(self, **kwargs) -> Lead:
        """Create and save a new lead."""
        lead = Lead(**kwargs)
        lead.save()
        return lead

    def get_or_create(
        self, defaults: Optional[Dict[str, Any]] = None, **kwargs
    ) -> tuple["Lead", bool]:
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

    def __iter__(self):
        """Iterate over matching leads."""
        for data in self._find():
            yield Lead.from_dict(data)

    def __len__(self):
        return self.count()


class Campaign:
    """
    MongoDB Campaign model.

    Represents a marketing campaign with MongoDB-specific fields.
    Uses pymongo directly for data operations.

    Multi-tenant: Each campaign has an owner (user_id) and can be shared
    with team members (team_member_ids).
    """

    objects: ClassVar["CampaignManager"]

    class Status:
        """Campaign status constants."""
        ACTIVE = "active"
        PAUSED = "paused"
        DRAFT = "draft"

    def __init__(
        self,
        _id: Optional[str] = None,
        name: str = "",
        product_pitch: str = "",
        campaign_objective: str = "",
        booking_link: str = "",
        is_freemium: bool = False,
        action_fraction: float = 0.2,
        seed_public_ids: Optional[List[str]] = None,
        model_blob: Optional[bytes] = None,
        velocity: int = 20,
        cooldown_minutes: int = 0,
        is_paused: bool = False,
        status: str = "active",
        user_id: str = "",
        linkedin_profile_id: Optional[str] = None,
        team_member_ids: Optional[List[str]] = None,
        icp_titles: Optional[List[str]] = None,
        target_company_size: Optional[str] = None,
        follow_up_strategy: Optional[str] = None,
        target_degrees: Optional[List[int]] = None,
        created_at: Optional[datetime] = None,
        channel_sequence: Optional[List[str]] = None,
        channel_settings: Optional[Dict[str, Any]] = None,
        whatsapp_profile_id: Optional[str] = None,
        lead_source: str = "linkedin_search",
        maps_query: Optional[str] = None,
        maps_country_code: Optional[str] = None,
        maps_backends: Optional[List[str]] = None,
        classified_sites: Optional[List[str]] = None,
        maps_location: Optional[str] = None,
        maps_min_rating: Optional[float] = None,
        maps_session_state: Optional[Dict[str, Any]] = None,
    ):
        self._id = _id or str(uuid4())
        self.name = name
        self.product_pitch = product_pitch
        self.campaign_objective = campaign_objective
        self.booking_link = booking_link
        self.is_freemium = is_freemium
        self.action_fraction = action_fraction
        self.seed_public_ids = seed_public_ids or []
        self.model_blob = model_blob
        self.velocity = velocity
        self.cooldown_minutes = cooldown_minutes
        self.is_paused = is_paused
        self.status = status
        self.user_id = user_id
        self.linkedin_profile_id = linkedin_profile_id
        self.team_member_ids = team_member_ids or []
        self.icp_titles = icp_titles or []
        self.target_company_size = target_company_size
        self.follow_up_strategy = follow_up_strategy
        self.target_degrees = target_degrees if target_degrees is not None else [1, 2, 3]
        self.created_at = created_at or datetime.now(tz.utc)
        self.channel_sequence = channel_sequence if channel_sequence is not None else ["linkedin"]
        self.channel_settings = channel_settings if channel_settings is not None else {}
        self.whatsapp_profile_id = whatsapp_profile_id
        self.lead_source = lead_source
        self.maps_query = maps_query
        self.maps_country_code = maps_country_code
        self.maps_backends = maps_backends if maps_backends is not None else []
        self.classified_sites = classified_sites if classified_sites is not None else []
        self.maps_location = maps_location
        self.maps_min_rating = maps_min_rating
        self.maps_session_state = maps_session_state

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary for MongoDB storage."""
        data = {
            "_id": self._id,
            "name": self.name,
            "product_pitch": self.product_pitch,
            "campaign_objective": self.campaign_objective,
            "booking_link": self.booking_link,
            "is_freemium": self.is_freemium,
            "action_fraction": self.action_fraction,
            "seed_public_ids": self.seed_public_ids,
            "velocity": self.velocity,
            "cooldown_minutes": self.cooldown_minutes,
            "is_paused": self.is_paused,
            "status": self.status,
            "user_id": self.user_id,
            "linkedin_profile_id": self.linkedin_profile_id,
            "team_member_ids": self.team_member_ids,
            "icp_titles": self.icp_titles,
            "target_degrees": self.target_degrees,
            "created_at": self.created_at,
        }
        if self.model_blob:
            data["model_blob"] = self.model_blob
        if self.target_company_size is not None:
            data["target_company_size"] = self.target_company_size
        if self.follow_up_strategy is not None:
            data["follow_up_strategy"] = self.follow_up_strategy
        data["channel_sequence"] = self.channel_sequence
        data["channel_settings"] = self.channel_settings
        if self.whatsapp_profile_id is not None:
            data["whatsapp_profile_id"] = self.whatsapp_profile_id
        data["lead_source"] = self.lead_source
        data["maps_backends"] = self.maps_backends
        if self.maps_query is not None:
            data["maps_query"] = self.maps_query
        if self.maps_country_code is not None:
            data["maps_country_code"] = self.maps_country_code
        data["classified_sites"] = self.classified_sites
        if self.maps_location is not None:
            data["maps_location"] = self.maps_location
        if self.maps_min_rating is not None:
            data["maps_min_rating"] = self.maps_min_rating
        if self.maps_session_state is not None:
            data["maps_session_state"] = self.maps_session_state
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Campaign":
        """Create Campaign instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            name=data.get("name", ""),
            product_pitch=data.get("product_pitch", ""),
            campaign_objective=data.get("campaign_objective", ""),
            booking_link=data.get("booking_link", ""),
            is_freemium=data.get("is_freemium", False),
            action_fraction=data.get("action_fraction", 0.2),
            seed_public_ids=data.get("seed_public_ids", []),
            model_blob=data.get("model_blob"),
            velocity=data.get("velocity", 20),
            cooldown_minutes=data.get("cooldown_minutes", 0),
            is_paused=data.get("is_paused", False),
            status=data.get("status", "active"),
            user_id=data.get("user_id", ""),
            linkedin_profile_id=data.get("linkedin_profile_id"),
            team_member_ids=data.get("team_member_ids", []),
            icp_titles=data.get("icp_titles", []),
            target_company_size=data.get("target_company_size"),
            follow_up_strategy=data.get("follow_up_strategy"),
            target_degrees=data.get("target_degrees"),
            created_at=data.get("created_at"),
            channel_sequence=data.get("channel_sequence"),
            channel_settings=data.get("channel_settings"),
            whatsapp_profile_id=data.get("whatsapp_profile_id"),
            lead_source=data.get("lead_source", "linkedin_search"),
            maps_query=data.get("maps_query"),
            maps_country_code=data.get("maps_country_code"),
            maps_backends=data.get("maps_backends"),
            classified_sites=data.get("classified_sites"),
            maps_location=data.get("maps_location"),
            maps_min_rating=data.get("maps_min_rating"),
            maps_session_state=data.get("maps_session_state"),
        )

    def has_access(self, user_id: str) -> bool:
        """Check if a user has access to this campaign (owner OR team member)."""
        return user_id == self.user_id or user_id in self.team_member_ids

    def get_all_user_ids(self) -> List[str]:
        """Get all users with access (owner + team members)."""
        user_ids = [self.user_id] if self.user_id else []
        user_ids.extend(self.team_member_ids)
        return user_ids

    def save(self, update_fields: Optional[List[str]] = None) -> str:
        """Save the campaign to MongoDB.

        If update_fields is given, only those fields are written (partial update).
        """
        collection = get_mongodb_collection("campaigns")
        if collection is None:
            raise RuntimeError("MongoDB collection 'campaigns' not available")

        if update_fields:
            full = self.to_dict()
            doc = {f: full[f] for f in update_fields if f in full}
        else:
            doc = self.to_dict()
        result = collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
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

    def get_or_create(
        self, defaults: Optional[Dict[str, Any]] = None, **kwargs
    ) -> tuple["Campaign", bool]:
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


# Assign Campaign manager as class attribute
Campaign.objects = CampaignManager()


class Deal:
    """
    MongoDB Deal model.

    Represents a deal in the CRM system linked to a lead and campaign.
    Uses pymongo directly for data operations.
    """

    objects: ClassVar["DealManager"]

    class DealState:
        DISCOVERED = "Discovered"
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
        user_id: Optional[str] = None,
        state: str = DealState.DISCOVERED,
        outcome: str = "",
        reason: str = "",
        connect_attempts: int = 0,
        backoff_hours: int = 0,
        next_check_pending_at: Optional[datetime] = None,
        pending_since: Optional[datetime] = None,
        profile_summary: Optional[Dict[str, Any]] = None,
        chat_summary: Optional[Dict[str, Any]] = None,
        creation_date: Optional[datetime] = None,
        last_outgoing_at: Optional[datetime] = None,
        follow_up_cycled_at: Optional[datetime] = None,
        next_follow_up_at: Optional[datetime] = None,
        active_channel: str = "linkedin",
    ):
        self._id = _id or str(uuid4())
        self.lead_id = lead_id
        self.campaign_id = campaign_id
        self.user_id = user_id
        self.state = state
        self.outcome = outcome
        self.reason = reason
        self.connect_attempts = connect_attempts
        self.backoff_hours = backoff_hours
        self.next_check_pending_at = next_check_pending_at
        self.pending_since: Optional[datetime] = pending_since
        self.profile_summary = profile_summary or {}
        self.chat_summary = chat_summary or {}
        self.creation_date = creation_date or datetime.now(tz.utc)
        self.last_outgoing_at = last_outgoing_at
        self.follow_up_cycled_at = follow_up_cycled_at
        self.next_follow_up_at = next_follow_up_at
        self.active_channel = active_channel
        self._lead: Optional["Lead"] = None
        self.campaign: Optional["Campaign"] = None

    @property
    def lead(self) -> Optional["Lead"]:
        if self._lead is None and self.lead_id:
            self._lead = Lead.get(self.lead_id)
        return self._lead

    @lead.setter
    def lead(self, value: Optional["Lead"]) -> None:
        self._lead = value

    def refresh_from_db(self, fields=None):
        collection = get_mongodb_collection("deals")
        if collection is None:
            return
        data = collection.find_one({"_id": self._id})
        if data:
            if fields:
                for field in fields:
                    if field in data:
                        setattr(self, field, data[field])
            else:
                for key, value in data.items():
                    if hasattr(self, key):
                        setattr(self, key, value)

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
        if self.user_id:
            data["user_id"] = self.user_id
        if self.next_check_pending_at:
            data["next_check_pending_at"] = self.next_check_pending_at
        if self.pending_since:
            data["pending_since"] = self.pending_since
        if self.last_outgoing_at:
            data["last_outgoing_at"] = self.last_outgoing_at
        if self.follow_up_cycled_at:
            data["follow_up_cycled_at"] = self.follow_up_cycled_at
        if self.next_follow_up_at:
            data["next_follow_up_at"] = self.next_follow_up_at
        data["active_channel"] = self.active_channel
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Deal":
        """Create Deal instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            lead_id=data.get("lead_id", ""),
            campaign_id=data.get("campaign_id", ""),
            user_id=data.get("user_id"),
            state=data.get("state", cls.DealState.QUALIFIED),
            outcome=data.get("outcome", ""),
            reason=data.get("reason", ""),
            connect_attempts=data.get("connect_attempts", 0),
            backoff_hours=data.get("backoff_hours", 0),
            next_check_pending_at=data.get("next_check_pending_at"),
            pending_since=data.get("pending_since"),
            profile_summary=data.get("profile_summary", {}),
            chat_summary=data.get("chat_summary", {}),
            creation_date=data.get("creation_date"),
            last_outgoing_at=data.get("last_outgoing_at"),
            follow_up_cycled_at=data.get("follow_up_cycled_at"),
            next_follow_up_at=data.get("next_follow_up_at"),
            active_channel=data.get("active_channel", "linkedin"),
        )

    def save(self, update_fields: Optional[List[str]] = None) -> str:
        """Save the deal to MongoDB.

        If update_fields is given, only those fields are written (partial update).
        """
        from pymongo.errors import DuplicateKeyError

        collection = get_mongodb_collection("deals")
        if collection is None:
            raise RuntimeError("MongoDB collection 'deals' not available")

        if update_fields:
            doc = self.to_dict()
            partial = {k: doc[k] for k in update_fields if k in doc}
            collection.update_one({"_id": self._id}, {"$set": partial})
            return self._id

        doc = self.to_dict()
        try:
            result = collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
        except DuplicateKeyError:
            # (lead_id, campaign_id) already exists from a concurrent insert - load it
            existing = collection.find_one(
                {"lead_id": self.lead_id, "campaign_id": self.campaign_id}
            )
            if existing:
                self._id = str(existing["_id"])
            return self._id
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
    def get_by_lead_and_campaign(cls, lead_id: str, campaign_id: str) -> Optional["Deal"]:
        """Get deal by lead_id (UUID) or public_identifier and campaign."""
        collection = get_mongodb_collection("deals")
        if collection is None:
            return None
        data = collection.find_one({"lead_id": lead_id, "campaign_id": campaign_id})
        if data:
            return cls.from_dict(data)
        # Fallback: treat lead_id as a public_identifier and resolve to _id first
        lead = Lead.find_by_public_identifier(lead_id)
        if lead and lead._id != lead_id:
            data = collection.find_one({"lead_id": lead._id, "campaign_id": campaign_id})
            return cls.from_dict(data) if data else None
        return None

    @classmethod
    def find_by_state_and_campaign(cls, state: str, campaign_id: str) -> List["Deal"]:
        """Find deals by state and campaign."""
        collection = get_mongodb_collection("deals")
        if collection is None:
            return []
        return [cls.from_dict(d) for d in collection.find({"state": state, "campaign_id": campaign_id})]

    @classmethod
    def get_by_lead(cls, lead_id: str) -> Optional["Deal"]:
        """Get first deal for a lead."""
        collection = get_mongodb_collection("deals")
        if collection is None:
            return None
        data = collection.find_one({"lead_id": lead_id})
        return cls.from_dict(data) if data else None

    @classmethod
    def find_unevaluated(cls, campaign_id: str) -> List["Deal"]:
        """Find deals in DISCOVERED state for a campaign (not yet evaluated).

        Excludes deals where qualification_hold=True (ambiguous leads held for manual review).
        """
        from openoutreach.mongodb.connection import get_mongodb_collection
        collection = get_mongodb_collection("deals")
        if collection is None:
            return []
        return [cls.from_dict(d) for d in collection.find({
            "state": cls.DealState.DISCOVERED,
            "campaign_id": campaign_id,
            "qualification_hold": {"$ne": True},
        })]

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
    def find_by_user_id(cls, user_id: str) -> List["Deal"]:
        """Find deals by user ID."""
        collection = get_mongodb_collection("deals")
        if collection is None:
            return []

        try:
            deals = []
            for data in collection.find({"user_id": user_id}):
                deals.append(cls.from_dict(data))
            return deals
        except Exception as e:
            logger.error(f"Failed to find deals by user_id '{user_id}': {e}")
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




class UserProfile:
    """
    MongoDB UserProfile model.
    
    Stores extended user profile settings that complement the Django User model.
    Uses pymongo directly for data operations.
    """
    
    def __init__(
        self,
        _id: Optional[str] = None,
        user_id: str = "",        first_name: str = "",
        last_name: str = "",
        email: str = "",
        phone: str = "",
        company: str = "",
        position: str = "",
        timezone: str = "UTC",
        notification_preferences: Optional[Dict[str, bool]] = None,
        ui_preferences: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.user_id = user_id
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.phone = phone
        self.company = company
        self.position = position
        self.timezone = timezone
        self.notification_preferences = notification_preferences or {
            "email_notifications": True,
            "sms_notifications": False,
            "push_notifications": True,
            "marketing_emails": False
        }
        self.ui_preferences = ui_preferences or {
            "theme": "light",
            "language": "en",
            "sidebar_collapsed": False
        }
        self.created_at = created_at or datetime.now(tz.utc)
        self.updated_at = updated_at or datetime.now(tz.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary for MongoDB storage."""
        data = {
            "_id": self._id,
            "user_id": self.user_id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "phone": self.phone,
            "company": self.company,
            "position": self.position,
            "timezone": self.timezone,
            "notification_preferences": self.notification_preferences,
            "ui_preferences": self.ui_preferences,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserProfile":
        """Create UserProfile instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            user_id=data.get("user_id", ""),
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            email=data.get("email", ""),
            phone=data.get("phone", ""),
            company=data.get("company", ""),
            position=data.get("position", ""),
            timezone=data.get("timezone", "UTC"),
            notification_preferences=data.get("notification_preferences"),
            ui_preferences=data.get("ui_preferences"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )
    
    def save(self) -> str:
        """Save the user profile to MongoDB."""
        from pymongo.errors import DuplicateKeyError

        collection = get_mongodb_collection("user_profiles")
        if collection is None:
            raise RuntimeError("MongoDB collection 'user_profiles' not available")

        self.updated_at = datetime.now(tz.utc)
        doc = self.to_dict()
        doc.pop("_id", None)

        try:
            result = collection.update_one({"user_id": self.user_id}, {"$set": doc}, upsert=True)
        except DuplicateKeyError:
            existing = collection.find_one({"user_id": self.user_id})
            if existing:
                self._id = str(existing["_id"])
            return self._id
        return str(result.upserted_id or self._id)
    
    @classmethod
    def get(cls, user_id: str) -> Optional["UserProfile"]:
        """Get a user profile by user ID."""
        collection = get_mongodb_collection("user_profiles")
        if collection is None:
            return None
        
        try:
            data = collection.find_one({"user_id": user_id})
            if data:
                return cls.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get user profile for user '{user_id}': {e}")
            return None
    
    @classmethod
    def delete(cls, user_id: str) -> bool:
        """Delete a user profile by user ID."""
        collection = get_mongodb_collection("user_profiles")
        if collection is None:
            return False
        
        try:
            result = collection.delete_one({"user_id": user_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete user profile for user '{user_id}': {e}")
            return False
    
    def __str__(self):
        return f"UserProfile#{self._id[:8]} ({self.first_name} {self.last_name})"
    
    @property
    def pk(self):
        """Get the primary key."""
        return self._id
    
    @pk.setter
    def pk(self, value):
        """Set the primary key."""
        self._id = value
    
    @classmethod
    def objects(cls) -> "UserProfileManager":
        """Get the UserProfileManager for querying user profiles."""
        return UserProfileManager()


class UserProfileManager:
    """Manager for UserProfile queries."""
    
    def __init__(self):
        self.collection = None
    
    def _get_collection(self) -> Optional[Collection]:
        if self.collection is None:
            self.collection = get_mongodb_collection("user_profiles")
        return self.collection
    
    def all(self) -> List[UserProfile]:
        """Get all user profiles."""
        collection = self._get_collection()
        if collection is None:
            return []
        
        try:
            profiles = []
            for data in collection.find():
                profiles.append(UserProfile.from_dict(data))
            return profiles
        except Exception as e:
            logger.error(f"Failed to get all user profiles: {e}")
            return []
    
    def filter(self, **kwargs) -> List[UserProfile]:
        """Filter user profiles by criteria."""
        collection = self._get_collection()
        if collection is None:
            return []
        
        try:
            profiles = []
            for data in collection.find(kwargs):
                profiles.append(UserProfile.from_dict(data))
            return profiles
        except Exception as e:
            logger.error(f"Failed to filter user profiles: {e}")
            return []
    
    def count(self) -> int:
        """Count total user profiles."""
        collection = self._get_collection()
        if collection is None:
            return 0
        
        try:
            return collection.count_documents({})
        except Exception as e:
            logger.error(f"Failed to count user profiles: {e}")
            return 0
    
    def get(self, **kwargs) -> Optional[UserProfile]:
        """Get a single user profile by criteria."""
        collection = self._get_collection()
        if collection is None:
            return None
        
        try:
            data = collection.find_one(kwargs)
            if data:
                return UserProfile.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get user profile: {e}")
            return None
    
    def get_or_create(
        self, defaults: Optional[Dict[str, Any]] = None, **kwargs
    ) -> tuple["UserProfile", bool]:
        """Get existing user profile or create new one."""
        existing = self.get(**kwargs)
        if existing:
            return existing, False
        
        data = kwargs.copy()
        if defaults:
            data.update(defaults)
        
        profile = UserProfile(**data)
        profile.save()
        return profile, True


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
        user_id: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.deal_id = deal_id
        self.content = content
        self.is_outgoing = is_outgoing
        self.user_id = user_id
        self.created_at = created_at or datetime.now(tz.utc)
        self.updated_at = updated_at or datetime.now(tz.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary for MongoDB storage."""
        data: Dict[str, Any] = {
            "_id": self._id,
            "deal_id": self.deal_id,
            "content": self.content,
            "is_outgoing": self.is_outgoing,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self.user_id:
            data["user_id"] = self.user_id
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """Create Message instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            deal_id=data.get("deal_id", ""),
            content=data.get("content", ""),
            is_outgoing=data.get("is_outgoing", True),
            user_id=data.get("user_id"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    @property
    def sender(self) -> str:
        """Get the sender of the message."""
        return "User" if self.is_outgoing else "Lead"

    def save(self) -> str:
        """Save the message to MongoDB."""
        collection = get_mongodb_collection("messages")
        if collection is None:
            raise RuntimeError("MongoDB collection 'messages' not available")

        doc = self.to_dict()
        result = collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
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
    def find_by_user_id(cls, user_id: str) -> List["Message"]:
        """Find messages by user ID."""
        collection = get_mongodb_collection("messages")
        if collection is None:
            return []

        try:
            messages = []
            for data in collection.find({"user_id": user_id}):
                messages.append(cls.from_dict(data))
            return messages
        except Exception as e:
            logger.error(f"Failed to find messages by user_id '{user_id}': {e}")
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

    def get_or_create(
        self, defaults: Optional[Dict[str, Any]] = None, **kwargs
    ) -> tuple["Message", bool]:
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
        user_id: Optional[str] = None,
        created_at: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.deal_id = deal_id
        self.content = content
        self.created_by_id = created_by_id
        self.user_id = user_id
        self.created_at = created_at or datetime.now(tz.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary for MongoDB storage."""
        data = {
            "_id": self._id,
            "deal_id": self.deal_id,
            "content": self.content,
            "created_at": self.created_at,
        }
        if self.created_by_id:
            data["created_by_id"] = self.created_by_id
        if self.user_id:
            data["user_id"] = self.user_id
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Note":
        """Create Note instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            deal_id=data.get("deal_id", ""),
            content=data.get("content", ""),
            created_by_id=data.get("created_by_id"),
            user_id=data.get("user_id"),
            created_at=data.get("created_at"),
        )

    def save(self) -> str:
        """Save the note to MongoDB."""
        collection = get_mongodb_collection("notes")
        if collection is None:
            raise RuntimeError("MongoDB collection 'notes' not available")

        doc = self.to_dict()
        result = collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
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
    def find_by_user_id(cls, user_id: str) -> List["Note"]:
        """Find notes by user ID."""
        collection = get_mongodb_collection("notes")
        if collection is None:
            return []

        try:
            notes = []
            for data in collection.find({"user_id": user_id}):
                notes.append(cls.from_dict(data))
            return notes
        except Exception as e:
            logger.error(f"Failed to find notes by user_id '{user_id}': {e}")
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

    def get_or_create(
        self, defaults: Optional[Dict[str, Any]] = None, **kwargs
    ) -> tuple["Note", bool]:
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
        user_id: Optional[str] = None,
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
        self.user_id = user_id
        self.pain_points = pain_points or []
        self.goals = goals or []
        self.messaging_preferences = messaging_preferences or {}
        self.buy_signals = buy_signals or []
        self.confidence_score = confidence_score
        self.recommendations = recommendations or []
        self.version = version
        self.generated_at = generated_at or datetime.now(tz.utc)
        self.last_updated = last_updated or datetime.now(tz.utc)

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
        if self.user_id:
            data["user_id"] = self.user_id
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LeadPersona":
        """Create LeadPersona instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            lead_id=data.get("lead_id", ""),
            campaign_id=data.get("campaign_id", ""),
            user_id=data.get("user_id"),
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
        from pymongo.errors import DuplicateKeyError

        collection = get_mongodb_collection("lead_personas")
        if collection is None:
            raise RuntimeError("MongoDB collection 'lead_personas' not available")

        doc = self.to_dict()
        try:
            result = collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
        except DuplicateKeyError:
            existing = collection.find_one({"lead_id": self.lead_id, "campaign_id": self.campaign_id})
            if existing:
                self._id = str(existing["_id"])
            return self._id
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
    def find_by_user_id(cls, user_id: str) -> List["LeadPersona"]:
        """Find lead personae by user ID."""
        collection = get_mongodb_collection("lead_personas")
        if collection is None:
            return []

        try:
            personae = []
            for data in collection.find({"user_id": user_id}):
                personae.append(cls.from_dict(data))
            return personae
        except Exception as e:
            logger.error(f"Failed to find personae by user_id '{user_id}': {e}")
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
        return self._id

    @pk.setter
    def pk(self, value):
        self._id = value

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence_score >= 0.7

    @property
    def has_buy_signals(self) -> bool:
        return len(self.buy_signals) > 0

    def get_formatted_pain_points(self, limit: int = 3) -> List[str]:
        return self.pain_points[:limit] if self.pain_points else []

    def get_formatted_goals(self, limit: int = 3) -> List[str]:
        return self.goals[:limit] if self.goals else []

    def get_formatted_buy_signals(self, limit: int = 3) -> List[str]:
        return (
            [s.get("description", "Unknown") for s in self.buy_signals[:limit]]
            if self.buy_signals
            else []
        )

    @classmethod
    def objects(cls) -> "LeadPersonaManager":
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

    def get_or_create(
        self, defaults: Optional[Dict[str, Any]] = None, **kwargs
    ) -> tuple["LeadPersona", bool]:
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
        user_id: Optional[str] = None,
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
        self.user_id = user_id
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
        self.created_at = created_at or datetime.now(tz.utc)
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
        if self.user_id:
            data["user_id"] = self.user_id
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrackedLink":
        """Create TrackedLink instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            campaign_id=data.get("campaign_id"),
            user_id=data.get("user_id"),
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
        result = collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
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
            logger.error(
                f"Failed to find tracked link by short_code '{short_code}': {e}"
            )
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
    def find_by_user_id(cls, user_id: str) -> List["TrackedLink"]:
        """Find tracked links by user ID."""
        collection = get_mongodb_collection("tracked_links")
        if collection is None:
            return []

        try:
            links = []
            for data in collection.find({"user_id": user_id}):
                links.append(cls.from_dict(data))
            return links
        except Exception as e:
            logger.error(f"Failed to find links by user_id '{user_id}': {e}")
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

    def record_click(
        self, ip_address: Optional[str] = None, user_agent: Optional[str] = None
    ) -> None:
        """Record a click on this link."""
        self.total_clicks += 1
        self.last_clicked_at = datetime.now(tz.utc)
        if ip_address:
            self.last_ip = ip_address
        if user_agent:
            self.last_user_agent = user_agent[:500]
        collection = get_mongodb_collection("tracked_links")
        if collection is not None:
            collection.update_one(
                {"_id": self._id},
                {"$set": {
                    "total_clicks": self.total_clicks,
                    "last_clicked_at": self.last_clicked_at,
                    "last_ip": self.last_ip,
                    "last_user_agent": self.last_user_agent,
                }},
            )

    @property
    def conversion_rate(self) -> float:
        """Calculate conversion rate based on linked deal conversions."""
        if self.total_clicks == 0:
            return 0.0
        collection = get_mongodb_collection("link_deal_conversions")
        if collection is None:
            return 0.0
        count = collection.count_documents({"link_id": self._id})
        return round(count / self.total_clicks * 100, 2)

    def get_short_url(self, base_url: Optional[str] = None) -> str:
        """Get the short tracked URL."""
        base = base_url or "https://outreach.lengrowth.com"
        return f"{base}/l/{self.short_code}"

    def __str__(self) -> str:
        return f"TrackedLink#{self.short_code}"

    @property
    def pk(self):
        return self._id

    @pk.setter
    def pk(self, value):
        self._id = value

    @classmethod
    def objects(cls) -> "TrackedLinkManager":
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

    def get_or_create(
        self, defaults: Optional[Dict[str, Any]] = None, **kwargs
    ) -> tuple["TrackedLink", bool]:
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
        self.clicked_at = clicked_at or datetime.now(tz.utc)
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
        result = collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
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

    def detect_device(self) -> Optional[str]:
        """Detect device type from user agent."""
        if not self.user_agent:
            return None
        ua_lower = self.user_agent.lower()
        if "mobile" in ua_lower or "android" in ua_lower or "iphone" in ua_lower:
            self.device_type = "mobile"
        elif "ipad" in ua_lower or "tablet" in ua_lower:
            self.device_type = "tablet"
        else:
            self.device_type = "desktop"
        collection = get_mongodb_collection("link_clicks")
        if collection is not None:
            collection.update_one(
                {"_id": self._id}, {"$set": {"device_type": self.device_type}}
            )
        return self.device_type

    def __str__(self) -> str:
        return f"LinkClick#{self._id[:8]}"

    @property
    def pk(self):
        return self._id

    @pk.setter
    def pk(self, value):
        self._id = value

    @classmethod
    def objects(cls) -> "LinkClickManager":
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

    def get_or_create(
        self, defaults: Optional[Dict[str, Any]] = None, **kwargs
    ) -> tuple["LinkClick", bool]:
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
        self.converted_at = converted_at or datetime.now(tz.utc)

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
            raise RuntimeError(
                "MongoDB collection 'link_deal_conversions' not available"
            )

        doc = self.to_dict()
        result = collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
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

    def get_or_create(
        self, defaults: Optional[Dict[str, Any]] = None, **kwargs
    ) -> tuple["LinkDealConversion", bool]:
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

    Securely stored LinkedIn credentials with encryption at rest via Fernet (AES-256).
    """

    STATUS_STORED = "stored"
    STATUS_TESTED = "tested"
    STATUS_ACTIVE = "active"
    STATUS_INVALID = "invalid"
    STATUS_EXPIRED = "expired"
    STATUS_LOCKED = "locked"
    STATUS_BACKUP = "backup"

    def __init__(
        self,
        _id: Optional[str] = None,
        linkedin_profile_id: Optional[str] = None,
        email_encrypted: str = "",
        password_encrypted: str = "",
        username: str = "",
        status: str = "stored",
        last_verified: Optional[datetime] = None,
        verification_failed_at: Optional[datetime] = None,
        verification_failures: int = 0,
        usage_count: int = 0,
        last_used: Optional[datetime] = None,
        campaign_id: Optional[str] = None,
        user_id: Optional[str] = None,
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
        self.user_id = user_id
        self.created_at = created_at or datetime.now(tz.utc)
        self.updated_at = updated_at or datetime.now(tz.utc)
        self.expires_at = expires_at
        self.rotated_at = rotated_at
        self.rotation_required_days = rotation_required_days
        self.is_primary = is_primary
        self.is_backup = is_backup
        self.backup_of_id = backup_of_id
        self.security_alert_sent_at = security_alert_sent_at

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
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
        if self.user_id:
            data["user_id"] = self.user_id
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LinkedInCredentials":
        return cls(
            _id=str(data.get("_id")),
            linkedin_profile_id=data.get("linkedin_profile_id"),
            email_encrypted=data.get("email_encrypted", ""),
            password_encrypted=data.get("password_encrypted", ""),
            username=data.get("username", ""),
            status=data.get("status", cls.STATUS_STORED),
            last_verified=data.get("last_verified"),
            verification_failed_at=data.get("verification_failed_at"),
            verification_failures=data.get("verification_failures", 0),
            usage_count=data.get("usage_count", 0),
            last_used=data.get("last_used"),
            campaign_id=data.get("campaign_id"),
            user_id=data.get("user_id"),
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

    def save(self, update_fields: Optional[List[str]] = None) -> str:
        """Save to MongoDB. If update_fields given, partial update only."""
        collection = get_mongodb_collection("linkedin_credentials")
        if collection is None:
            raise RuntimeError("MongoDB collection 'linkedin_credentials' not available")

        self.updated_at = datetime.now(tz.utc)

        if update_fields:
            field_map = self.to_dict()
            update_doc = {f: field_map[f] for f in update_fields if f in field_map}
            update_doc["updated_at"] = self.updated_at
            collection.update_one({"_id": self._id}, {"$set": update_doc}, upsert=True)
        else:
            doc = self.to_dict()
            collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
        return self._id

    @classmethod
    def get(cls, credential_id: str) -> Optional["LinkedInCredentials"]:
        collection = get_mongodb_collection("linkedin_credentials")
        if collection is None:
            return None
        data = collection.find_one({"_id": credential_id})
        if data:
            return cls.from_dict(data)
        return None

    @classmethod
    def find_by_profile_id(cls, profile_id: str) -> Optional["LinkedInCredentials"]:
        collection = get_mongodb_collection("linkedin_credentials")
        if collection is None:
            return None
        data = collection.find_one({"linkedin_profile_id": profile_id})
        if data:
            return cls.from_dict(data)
        return None

    @classmethod
    def find_by_campaign_id(cls, campaign_id: str) -> List["LinkedInCredentials"]:
        collection = get_mongodb_collection("linkedin_credentials")
        if collection is None:
            return []
        return [cls.from_dict(d) for d in collection.find({"campaign_id": campaign_id})]

    @classmethod
    def find_by_user_id(cls, user_id: str) -> List["LinkedInCredentials"]:
        collection = get_mongodb_collection("linkedin_credentials")
        if collection is None:
            return []
        return [cls.from_dict(d) for d in collection.find({"user_id": user_id})]

    @classmethod
    def delete(cls, credential_id: str) -> bool:
        collection = get_mongodb_collection("linkedin_credentials")
        if collection is None:
            return False
        result = collection.delete_one({"_id": credential_id})
        return result.deleted_count > 0

    # ==================== Encryption Methods ====================

    @classmethod
    def encrypt(cls, plaintext: str) -> str:
        """Encrypt a string using Fernet AES encryption."""
        from openoutreach.mongodb.crypto import encrypt_text
        return encrypt_text(plaintext)

    @classmethod
    def decrypt(cls, ciphertext: str) -> str:
        """Decrypt a string using Fernet AES decryption."""
        from openoutreach.mongodb.crypto import decrypt_text
        return decrypt_text(ciphertext)

    def get_email(self) -> str:
        """Get the decrypted email address."""
        if not self.email_encrypted:
            return ""
        return self.decrypt(self.email_encrypted)

    def set_email(self, email: str) -> None:
        """Set and encrypt the email address."""
        self.email_encrypted = self.encrypt(email)

    def get_password(self) -> str:
        """Get the decrypted password."""
        if not self.password_encrypted:
            return ""
        return self.decrypt(self.password_encrypted)

    def set_password(self, password: str) -> None:
        """Set and encrypt the password."""
        self.password_encrypted = self.encrypt(password)

    def get_public_email(self) -> str:
        """Get a masked version of the email for display."""
        try:
            email = self.get_email()
            if "@" in email:
                local, domain = email.rsplit("@", 1)
                if len(local) > 2:
                    return f"{local[0]}***@{domain}"
                return f"***@{domain}"
            return "***@***"
        except Exception:
            return "***@***"

    # ==================== Status Methods ====================

    def mark_verified(self) -> None:
        """Mark credentials as verified and active."""
        self.status = self.STATUS_ACTIVE
        self.last_verified = datetime.now(tz.utc)
        self.verification_failures = 0
        self.verification_failed_at = None
        self.save(update_fields=["status", "last_verified", "verification_failures", "verification_failed_at"])

    def mark_verification_failed(self) -> None:
        """Mark verification as failed."""
        self.status = self.STATUS_INVALID
        self.verification_failed_at = datetime.now(tz.utc)
        self.verification_failures += 1
        self.save(update_fields=["status", "verification_failed_at", "verification_failures"])

    def mark_as_invalid(self, reason: str = "") -> None:
        self.status = self.STATUS_INVALID
        self.verification_failed_at = datetime.now(tz.utc)
        self.verification_failures += 1
        if reason:
            self._save_verification_log("invalid", reason)
        self.save(update_fields=["status", "verification_failed_at", "verification_failures"])

    def mark_as_active(self) -> None:
        self.status = self.STATUS_ACTIVE
        self.save(update_fields=["status"])

    def mark_as_expired(self) -> None:
        self.status = self.STATUS_EXPIRED
        self.save(update_fields=["status"])

    def mark_as_locked(self, reason: str = "") -> None:
        self.status = self.STATUS_LOCKED
        if reason:
            self._save_verification_log("locked", reason)
        self.save(update_fields=["status"])

    def unlock(self) -> None:
        if self.status == self.STATUS_LOCKED:
            self.status = self.STATUS_ACTIVE
            self.save(update_fields=["status"])

    # ==================== Verification Methods ====================

    def verify_credentials(
        self, session, mark_as_active: bool = True, mark_as_stored: bool = False
    ) -> tuple:
        """Verify credentials via browser automation.

        Returns (success, details) tuple.
        """
        from linkedin_cli.browser.login import launch_browser, submit_login_form
        from linkedin_cli.page_state import classify_page, PageState

        logger.info("Starting LinkedIn credential verification for %s", self.get_public_email())

        try:
            session.page, session.context, session.browser, session.playwright = launch_browser()
            session.username = self.get_email()
            session.password = self.get_password()
            submit_login_form(session, session.username, session.password)

            page_state = classify_page(session.page)
            logger.info("Post-login page state: %s (%s)", page_state, session.page.url)

            if page_state == PageState.FEED:
                return self._mark_verified(session, mark_as_active)

            logger.warning(
                "Challenge detected for %s (state=%s) - browser kept alive for VNC",
                self.get_public_email(), page_state,
            )
            self.status = self.STATUS_LOCKED
            self.save(update_fields=["status"])
            LinkedInCredentialLog(
                credential_id=self._id,
                action="locked",
                details={
                    "error_type": "awaiting_challenge",
                    "page_state": str(page_state),
                    "checkpoint_url": session.page.url,
                },
            ).save()

            return False, {
                "verified_at": None,
                "failures": self.verification_failures,
                "status": self.STATUS_LOCKED,
                "message": "LinkedIn requires verification. Complete the challenge in the browser viewer, then confirm.",
                "error_type": "awaiting_challenge",
            }

        except Exception as e:
            error_msg = str(e)[:500]
            is_timeout = "timeout" in error_msg.lower()
            logger.error("Credential verification failed for %s: %s", self.get_public_email(), error_msg)

            LinkedInCredentialLog(
                credential_id=self._id,
                action="failed",
                details={
                    "error_type": "timeout" if is_timeout else "verification_error",
                    "error_message": error_msg,
                },
            ).save()

            if mark_as_stored:
                self.status = self.STATUS_STORED
                self.save(update_fields=["status"])
            else:
                self.mark_as_invalid(reason=error_msg)

            return False, {
                "verified_at": None,
                "failures": self.verification_failures,
                "status": self.status,
                "message": f"Verification {'timed out' if is_timeout else 'error'}: {error_msg}",
                "error_type": "timeout" if is_timeout else "verification_error",
            }

    def confirm_challenge(self, session) -> tuple:
        """Check if the user resolved the challenge in VNC and finalize auth."""
        from linkedin_cli.page_state import classify_page, PageState

        if not session.page or session.page.is_closed():
            return False, {
                "verified_at": None,
                "status": self.status,
                "message": "Browser session expired. Please try again.",
                "error_type": "session_expired",
            }

        try:
            page_state = classify_page(session.page)

            if page_state == PageState.CHECKPOINT:
                try:
                    session.page.goto("https://www.linkedin.com/feed/", timeout=15000)
                    session.page.wait_for_load_state("domcontentloaded", timeout=10000)
                    page_state = classify_page(session.page)
                except Exception:
                    page_state = classify_page(session.page)

            if page_state == PageState.FEED:
                return self._mark_verified(session, mark_as_active=True)

            return False, {
                "verified_at": None,
                "status": self.STATUS_LOCKED,
                "message": "Challenge not yet completed. Finish the verification in the browser viewer and try again.",
                "error_type": "challenge_incomplete",
            }
        except Exception as e:
            return False, {
                "verified_at": None,
                "status": self.status,
                "message": f"Error checking challenge status: {str(e)[:200]}",
                "error_type": "verification_error",
            }

    def _mark_verified(self, session, mark_as_active: bool) -> tuple:
        """Common path: mark credential active, save cookies, discover username."""
        from openoutreach.linkedin.browser.launch import _save_cookies

        self._discover_username(session)
        _save_cookies(session)

        self.last_verified = datetime.now(tz.utc)
        self.verification_failures = 0
        self.status = self.STATUS_ACTIVE if mark_as_active else self.STATUS_TESTED
        self.save(update_fields=["last_verified", "verification_failures", "status", "username"])

        LinkedInCredentialLog(
            credential_id=self._id,
            action="verified",
            details={"verified_by": "browser_automation", "status": self.status},
        ).save()

        return True, {
            "verified_at": self.last_verified.isoformat(),
            "failures": 0,
            "status": self.status,
            "message": "LinkedIn credentials verified successfully",
            "error_type": None,
        }

    def _discover_username(self, session) -> None:
        """Extract the LinkedIn username from the current authenticated page."""
        try:
            me_link = session.page.query_selector("a[href*='/in/']")
            if me_link:
                href = me_link.get_attribute("href") or ""
                parts = [p for p in href.split("/") if p]
                if "in" in parts:
                    idx = parts.index("in")
                    if idx + 1 < len(parts):
                        username = parts[idx + 1]
                        if username and username != "me":
                            self.username = username
                            return

            session.page.goto("https://www.linkedin.com/in/me/", timeout=10000)
            session.page.wait_for_load_state("domcontentloaded", timeout=5000)
            url = session.page.url
            if "/in/" in url:
                parts = [p for p in url.split("/") if p]
                if "in" in parts:
                    idx = parts.index("in")
                    if idx + 1 < len(parts):
                        username = parts[idx + 1]
                        if username and username != "me":
                            self.username = username
        except Exception as e:
            logger.debug("Could not discover username: %s", e)

    def check_checkpoint_challenge(self, session) -> tuple:
        """Check if LinkedIn is presenting a checkpoint/challenge."""
        try:
            current_url = session.page.url
            checkpoint_patterns = [
                "checkpoint", "challenge", "secondary", "sms",
                "email", "security", "2fa", "verify",
            ]
            for pattern in checkpoint_patterns:
                if pattern in current_url.lower():
                    return True, f"Checkpoint detected: {current_url}"

            checkpoint_selectors = [
                "h1:has-text('check')", "h1:has-text('Security')",
                "h1:has-text('Confirm')", "h1:has-text('Verify')",
                "h1:has-text('Challenge')", "[class*='checkpoint']",
                "[class*='challenge']",
            ]
            for selector in checkpoint_selectors:
                elements = session.page.query_selector_all(selector)
                if elements:
                    return True, f"Checkpoint element detected: {selector}"

            return False, "No checkpoint detected"
        except Exception as e:
            return False, str(e)

    # ==================== Usage & Rotation ====================

    def record_usage(self, campaign=None, action_type: str = "") -> None:
        self.usage_count += 1
        self.last_used = datetime.now(tz.utc)
        if campaign:
            cid = campaign._id if hasattr(campaign, "_id") else str(campaign)
            if self.campaign_id != cid:
                self.campaign_id = cid
        self.save(update_fields=["usage_count", "last_used", "campaign_id"])

    def needs_rotation(self) -> bool:
        if self.status != self.STATUS_ACTIVE:
            return False
        if self.expires_at is None:
            return False
        return datetime.now(tz.utc) >= self.expires_at

    def rotate_credentials(
        self, new_email: Optional[str] = None, new_password: Optional[str] = None
    ) -> None:
        from datetime import timedelta

        if new_email:
            self.set_email(new_email)
        if new_password:
            self.set_password(new_password)
        self.rotated_at = datetime.now(tz.utc)
        self.expires_at = datetime.now(tz.utc) + timedelta(days=self.rotation_required_days)
        self.is_primary = False
        self.is_backup = True
        self.save(update_fields=[
            "email_encrypted", "password_encrypted", "rotated_at",
            "expires_at", "is_primary", "is_backup",
        ])

    def create_backup(
        self, email: Optional[str] = None, password: Optional[str] = None
    ) -> "LinkedInCredentials":
        backup = LinkedInCredentials(
            username=f"Backup of {self.username or 'credential'}",
            email_encrypted=self.email_encrypted if email is None else self.encrypt(email),
            password_encrypted=self.password_encrypted if password is None else self.encrypt(password),
            status=self.STATUS_BACKUP,
            is_primary=False,
            is_backup=True,
            backup_of_id=self._id,
            expires_at=self.expires_at,
            rotation_required_days=self.rotation_required_days,
            user_id=self.user_id,
        )
        backup.save()
        return backup

    # ==================== Health Status ====================

    def get_health_status(self) -> Dict[str, Any]:
        now = datetime.now(tz.utc)
        days_since_rotation = 0
        if self.rotated_at:
            days_since_rotation = (now - self.rotated_at).days

        days_until_expiry = None
        if self.expires_at:
            days_until_expiry = (self.expires_at - now).days

        return {
            "id": self._id,
            "username": self.username or "",
            "public_email": self.get_public_email(),
            "status": self.status,
            "is_primary": self.is_primary,
            "is_backup": self.is_backup,
            "usage_count": self.usage_count,
            "days_since_rotation": days_since_rotation,
            "days_until_expiry": days_until_expiry,
            "verification_failures": self.verification_failures,
            "last_verified": self.last_verified.isoformat() if self.last_verified else None,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "health_score": self._calculate_health_score(),
        }

    def _calculate_health_score(self) -> int:
        score = 100
        if self.status == self.STATUS_INVALID:
            score -= 50
        elif self.status == self.STATUS_LOCKED:
            score -= 30
        elif self.status == self.STATUS_EXPIRED:
            score -= 20
        if self.rotated_at:
            days_old = (datetime.now(tz.utc) - self.rotated_at).days
            if days_old > self.rotation_required_days:
                score -= 20
        score -= self.verification_failures * 5
        return max(0, min(100, score))

    def _save_verification_log(self, action: str, reason: str) -> None:
        LinkedInCredentialLog(
            credential_id=self._id,
            action=action,
            details={"reason": reason},
        ).save()

    def __str__(self) -> str:
        return f"LinkedInCredential#{self._id[:8]} ({self.get_public_email()})"

    @property
    def pk(self):
        return self._id

    @pk.setter
    def pk(self, value):
        self._id = value

    @classmethod
    def objects(cls) -> "LinkedInCredentialsManager":
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

    def get_or_create(
        self, defaults: Optional[Dict[str, Any]] = None, **kwargs
    ) -> tuple["LinkedInCredentials", bool]:
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

    ACTION_VERIFIED = "verified"
    ACTION_FAILED = "failed"
    ACTION_LOCKED = "locked"
    ACTION_UNLOCKED = "unlocked"
    ACTION_ROTATED = "rotated"
    ACTION_BACKUP = "backup"
    ACTION_USAGE = "usage"

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
        self.created_at = created_at or datetime.now(tz.utc)

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
            raise RuntimeError(
                "MongoDB collection 'linkedin_credential_logs' not available"
            )

        doc = self.to_dict()
        result = collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
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

    def get_or_create(
        self, defaults: Optional[Dict[str, Any]] = None, **kwargs
    ) -> tuple["LinkedInCredentialLog", bool]:
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


# Per-user TTL cache for SiteConfig.load - avoids a MongoDB round-trip on
# every daemon loop iteration. Keyed by user_id (None for the singleton).
# Format: {user_id: (loaded_at_monotonic, SiteConfig)}
_SITE_CONFIG_CACHE: dict = {}
_SITE_CONFIG_TTL = 60.0  # seconds


class SiteConfig:
    """
    MongoDB SiteConfig model.

    Represents global site configuration.
    Uses pymongo directly for data operations.
    """

    def __init__(
        self,
        _id: Optional[str] = None,
        user_id: Optional[str] = None,
        llm_provider: str = "",
        llm_api_key: str = "",
        ai_model: str = "",
        llm_api_base: str = "",
        finder_api_key: str = "",
        linkedin_username: str = "",
        linkedin_campaign: str = "",
        daily_connection_limit: int = 20,
        daily_follow_up_limit: int = 40,
        velocity: int = 20,
        cooldown_minutes: int = 0,
        bettercontact_api_key: str = "",
        contacts_api_token: str = "",
        contacts_api_url: str = "",
        enable_active_hours: bool = False,
        active_start_hour: int = 9,
        active_end_hour: int = 18,
        active_timezone: str = "UTC",
        active_days: Optional[List[int]] = None,
        enable_smart_rate_limiting: bool = False,
        aggressiveness_preset: str = "average",
        ai_writing_style: str = "",
        ai_say_rules: str = "",
        ai_avoid_rules: str = "",
        wa_daily_limit: int = 20,
        wa_enable_active_hours: bool = False,
        wa_active_start_hour: int = 8,
        wa_active_end_hour: int = 21,
        wa_active_days: Optional[List[int]] = None,
    ):
        self._id = _id or str(uuid4())
        self.user_id = user_id
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
        self.enable_active_hours = enable_active_hours
        self.active_start_hour = active_start_hour
        self.active_end_hour = active_end_hour
        self.active_timezone = active_timezone
        self.active_days = active_days if active_days is not None else [1, 2, 3, 4, 5]
        self.enable_smart_rate_limiting = enable_smart_rate_limiting
        self.aggressiveness_preset = aggressiveness_preset
        self.ai_writing_style = ai_writing_style
        self.ai_say_rules = ai_say_rules
        self.ai_avoid_rules = ai_avoid_rules
        self.wa_daily_limit = wa_daily_limit
        self.wa_enable_active_hours = wa_enable_active_hours
        self.wa_active_start_hour = wa_active_start_hour
        self.wa_active_end_hour = wa_active_end_hour
        self.wa_active_days = wa_active_days if wa_active_days is not None else [1, 2, 3, 4, 5, 6, 7]

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary for MongoDB storage."""
        data = {
            "_id": self._id,
            "user_id": self.user_id,
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
            "enable_active_hours": self.enable_active_hours,
            "active_start_hour": self.active_start_hour,
            "active_end_hour": self.active_end_hour,
            "active_timezone": self.active_timezone,
            "active_days": self.active_days,
            "enable_smart_rate_limiting": self.enable_smart_rate_limiting,
            "aggressiveness_preset": self.aggressiveness_preset,
            "ai_writing_style": self.ai_writing_style,
            "ai_say_rules": self.ai_say_rules,
            "ai_avoid_rules": self.ai_avoid_rules,
            "wa_daily_limit": self.wa_daily_limit,
            "wa_enable_active_hours": self.wa_enable_active_hours,
            "wa_active_start_hour": self.wa_active_start_hour,
            "wa_active_end_hour": self.wa_active_end_hour,
            "wa_active_days": self.wa_active_days,
        }
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SiteConfig":
        """Create SiteConfig instance from MongoDB document."""
        return cls(
            _id=str(data.get("_id")),
            user_id=data.get("user_id"),
            llm_provider=data.get("llm_provider", ""),
            llm_api_key=data.get("llm_api_key", ""),
            ai_model=data.get("ai_model", ""),
            llm_api_base=data.get("llm_api_base", ""),
            finder_api_key=data.get("finder_api_key", ""),
            linkedin_username=data.get("linkedin_username", ""),
            linkedin_campaign=data.get("linkedin_campaign", ""),
            daily_connection_limit=data.get("daily_connection_limit", 20),
            daily_follow_up_limit=data.get("daily_follow_up_limit", 40),
            velocity=data.get("velocity", 20),
            cooldown_minutes=data.get("cooldown_minutes", 0),
            bettercontact_api_key=data.get("bettercontact_api_key", ""),
            contacts_api_token=data.get("contacts_api_token", ""),
            contacts_api_url=data.get("contacts_api_url", ""),
            enable_active_hours=data.get("enable_active_hours", False),
            active_start_hour=data.get("active_start_hour", 9),
            active_end_hour=data.get("active_end_hour", 18),
            active_timezone=data.get("active_timezone", "UTC"),
            active_days=data.get("active_days"),
            enable_smart_rate_limiting=data.get("enable_smart_rate_limiting", False),
            aggressiveness_preset=data.get("aggressiveness_preset", "average"),
            ai_writing_style=data.get("ai_writing_style", ""),
            ai_say_rules=data.get("ai_say_rules", ""),
            ai_avoid_rules=data.get("ai_avoid_rules", ""),
            wa_daily_limit=data.get("wa_daily_limit", 20),
            wa_enable_active_hours=data.get("wa_enable_active_hours", False),
            wa_active_start_hour=data.get("wa_active_start_hour", 8),
            wa_active_end_hour=data.get("wa_active_end_hour", 21),
            wa_active_days=data.get("wa_active_days"),
        )

    def save(self) -> str:
        """Save the site config to MongoDB."""
        from pymongo.errors import DuplicateKeyError

        collection = get_mongodb_collection("site_config")
        if collection is None:
            raise RuntimeError("MongoDB collection 'site_config' not available")

        doc = self.to_dict()
        try:
            result = collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
        except DuplicateKeyError:
            existing = collection.find_one({"user_id": self.user_id})
            if existing:
                self._id = str(existing["_id"])
            return self._id
        return str(result.upserted_id or self._id)

    @classmethod
    def load(cls, user_id: Optional[str] = None) -> "SiteConfig":
        """Load a SiteConfig. If user_id is given, loads that user's config;
        otherwise returns the first document (backwards-compatible singleton).

        Results are cached in-process for 60 s to avoid a MongoDB round-trip
        on every daemon loop iteration. Call ``SiteConfig.invalidate(user_id)``
        after writes that need to be seen immediately (e.g. API settings save).
        """
        cache_key = user_id
        cached = _SITE_CONFIG_CACHE.get(cache_key)
        if cached is not None:
            loaded_at, config = cached
            if time.monotonic() - loaded_at < _SITE_CONFIG_TTL:
                return config

        collection = get_mongodb_collection("site_config")
        if collection is None:
            return cls()

        try:
            query = {"user_id": user_id} if user_id else {}
            data = collection.find_one(query)
            if data:
                config = cls.from_dict(data)
            else:
                config = cls(user_id=user_id)
                config.save()
            _SITE_CONFIG_CACHE[cache_key] = (time.monotonic(), config)
            return config
        except Exception as e:
            logger.error(f"Failed to load site config: {e}")
            return cls()

    @classmethod
    def invalidate(cls, user_id: Optional[str] = None) -> None:
        """Evict the in-process cache entry for *user_id* so the next
        ``load()`` call fetches fresh data from MongoDB."""
        _SITE_CONFIG_CACHE.pop(user_id, None)

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
            logger.error(
                f"Failed to find site config by llm_provider '{llm_provider}': {e}"
            )
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

    def get_or_create(
        self, defaults: Optional[Dict[str, Any]] = None, **kwargs
    ) -> tuple["SiteConfig", bool]:
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

    objects: ClassVar["TaskManager"]

    TASK_TYPE_CONNECT = "connect"
    TASK_TYPE_CHECK_PENDING = "check_pending"
    TASK_TYPE_FOLLOW_UP = "follow_up"
    TASK_TYPE_SEND_MANUAL_MESSAGE = "send_manual_message"

    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"

    class TaskType:
        CONNECT = "connect"
        CHECK_PENDING = "check_pending"
        FOLLOW_UP = "follow_up"
        SEND_MANUAL_MESSAGE = "send_manual_message"
        WHATSAPP_MESSAGE = "whatsapp_message"
        WHATSAPP_FOLLOW_UP = "whatsapp_follow_up"
        WHATSAPP_SYNC = "whatsapp_sync"

    class Status:
        PENDING = "pending"
        RUNNING = "running"
        COMPLETED = "completed"
        FAILED = "failed"

    def __init__(
        self,
        _id: Optional[str] = None,
        task_type: str = "",
        status: str = STATUS_PENDING,
        scheduled_at: Optional[datetime] = None,
        payload: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        linkedin_profile_id: Optional[str] = None,
        channel: str = "linkedin",
        created_at: Optional[datetime] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.task_type = task_type
        self.status = status
        self.scheduled_at = scheduled_at or datetime.now(tz.utc)
        self.payload = payload or {}
        self.user_id = user_id
        self.linkedin_profile_id = linkedin_profile_id
        self.channel = channel
        self.created_at = created_at or datetime.now(tz.utc)
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
        }
        data["channel"] = self.channel
        if self.user_id:
            data["user_id"] = self.user_id
        if self.linkedin_profile_id:
            data["linkedin_profile_id"] = self.linkedin_profile_id
        if self.started_at:
            data["started_at"] = self.started_at
        if self.completed_at:
            data["completed_at"] = self.completed_at
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
            user_id=data.get("user_id"),
            linkedin_profile_id=data.get("linkedin_profile_id"),
            channel=data.get("channel", "linkedin"),
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
        result = collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
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
    def find_by_user_id(cls, user_id: str) -> List["Task"]:
        """Find tasks by user ID."""
        collection = get_mongodb_collection("tasks")
        if collection is None:
            return []

        try:
            tasks = []
            for data in collection.find({"user_id": user_id}):
                tasks.append(cls.from_dict(data))
            return tasks
        except Exception as e:
            logger.error(f"Failed to find tasks by user_id '{user_id}': {e}")
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

    def mark_running(self) -> None:
        """Mark task as running."""
        self.status = self.STATUS_RUNNING
        self.started_at = datetime.now(tz.utc)
        self.save()

    def mark_completed(self) -> None:
        """Mark task as completed."""
        self.status = self.STATUS_COMPLETED
        self.completed_at = datetime.now(tz.utc)
        self.save()

    def mark_failed(self, error_message: Optional[str] = None) -> None:
        """Mark task as failed."""
        self.status = self.STATUS_FAILED
        self.completed_at = datetime.now(tz.utc)
        self.save()

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

    objects: "TaskManager"


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

    def get_or_create(
        self, defaults: Optional[Dict[str, Any]] = None, **kwargs
    ) -> tuple["Task", bool]:
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

    def bulk_create(self, tasks: List["Task"]) -> List["Task"]:
        """Save multiple tasks at once."""
        collection = self._get_collection()
        if collection is None:
            return tasks
        docs = [t.to_dict() for t in tasks]
        if docs:
            collection.insert_many(docs)
        return tasks

    def pending(self) -> "TaskManager":
        """Return a filtered view of pending tasks."""
        return _FilteredTaskManager({"status": Task.STATUS_PENDING})

    def claim_next(self, linkedin_profile_id: Optional[str] = None, channel: Optional[str] = None) -> Optional["Task"]:
        """Atomically claim the next pending task, optionally scoped to a profile."""
        collection = self._get_collection()
        if collection is None:
            return None
        from datetime import datetime, timezone as _tz
        now = datetime.now(_tz.utc)
        query: Dict[str, Any] = {"status": Task.STATUS_PENDING, "scheduled_at": {"$lte": now}}
        if linkedin_profile_id:
            query["linkedin_profile_id"] = linkedin_profile_id
        if channel == "linkedin":
            query["$or"] = [{"channel": "linkedin"}, {"channel": {"$exists": False}}]
        elif channel is not None:
            query["channel"] = channel
        from pymongo import ReturnDocument
        doc = collection.find_one_and_update(
            query,
            {"$set": {"status": Task.STATUS_RUNNING, "started_at": now}},
            sort=[("scheduled_at", 1)],
            return_document=ReturnDocument.AFTER,
        )
        if doc:
            return Task.from_dict(doc)
        return None

    def seconds_to_next(self, linkedin_profile_id: Optional[str] = None, channel: Optional[str] = None) -> Optional[float]:
        """Seconds until next pending task is due, optionally scoped to a profile."""
        collection = self._get_collection()
        if collection is None:
            return None
        from datetime import datetime, timezone as _tz
        query: Dict[str, Any] = {"status": Task.STATUS_PENDING}
        if linkedin_profile_id:
            query["linkedin_profile_id"] = linkedin_profile_id
        if channel == "linkedin":
            query["$or"] = [{"channel": "linkedin"}, {"channel": {"$exists": False}}]
        elif channel is not None:
            query["channel"] = channel
        doc = collection.find_one(
            query,
            sort=[("scheduled_at", 1)],
        )
        if doc and doc.get("scheduled_at"):
            delta = (doc["scheduled_at"] - datetime.now(_tz.utc)).total_seconds()
            return max(0.0, delta)
        return None


class _FilteredTaskManager(TaskManager):
    """TaskManager with a pre-applied filter."""

    def __init__(self, base_query: Dict[str, Any]):
        super().__init__()
        self._base_query = base_query

    def filter(self, **kwargs) -> List[Task]:
        query = {**self._base_query, **kwargs}
        collection = self._get_collection()
        if collection is None:
            return []
        try:
            return [Task.from_dict(d) for d in collection.find(query)]
        except Exception:
            return []

    def count(self) -> int:
        collection = self._get_collection()
        if collection is None:
            return 0
        try:
            return collection.count_documents(self._base_query)
        except Exception:
            return 0


Task.objects = TaskManager()


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

    def get_or_create(
        self, defaults: Optional[Dict[str, Any]] = None, **kwargs
    ) -> tuple["Deal", bool]:
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


# Assign Deal manager as class attribute
Deal.objects = DealManager()


def ensure_mongodb_indexes():
    """Create required indexes for MongoDB collections, only if they don't already exist."""
    if not check_mongodb_connection():
        logger.warning("MongoDB not connected, skipping index creation")
        return

    db = get_mongodb()
    if db is None:
        return

    indexes = [
        # Lead indexes
        (
            "leads",
            [
                ("public_identifier", {"name": "public_identifier_idx"}),
                ("linkedin_url", {"name": "linkedin_url_idx"}),
                ("creation_date", {"name": "creation_date_idx"}),
                ("user_id", {"name": "user_id_idx"}),
            ],
        ),
        # Campaign indexes
        (
            "campaigns",
            [
                ("name", {"name": "name_idx"}),
                ("is_paused", {"name": "is_paused_idx"}),
            ],
        ),
        # Deal indexes
        (
            "deals",
            [
                ("lead_id", {"name": "lead_id_idx"}),
                ("campaign_id", {"name": "campaign_id_idx"}),
                ("state", {"name": "state_idx"}),
                ("user_id", {"name": "user_id_idx"}),
            ],
        ),
        # Message indexes
        (
            "messages",
            [
                ("deal_id", {"name": "deal_id_idx"}),
                ("created_at", {"name": "created_at_idx"}),
                ("user_id", {"name": "user_id_idx"}),
            ],
        ),
        # Note indexes
        (
            "notes",
            [
                ("deal_id", {"name": "deal_id_idx"}),
                ("created_at", {"name": "created_at_idx"}),
                ("user_id", {"name": "user_id_idx"}),
            ],
        ),
        # Lead Persona indexes
        (
            "lead_personas",
            [
                ("lead_id", {"name": "lead_id_idx"}),
                ("campaign_id", {"name": "campaign_id_idx"}),
                ("generated_at", {"name": "generated_at_idx"}),
                ("user_id", {"name": "user_id_idx"}),
            ],
        ),
        # Tracked Link indexes
        (
            "tracked_links",
            [
                ("campaign_id", {"name": "campaign_id_idx"}),
                ("short_code", {"name": "short_code_idx"}),
                ("created_at", {"name": "created_at_idx"}),
                ("user_id", {"name": "user_id_idx"}),
            ],
        ),
        # Link Click indexes
        (
            "link_clicks",
            [
                ("link_id", {"name": "link_id_idx"}),
                ("clicked_at", {"name": "clicked_at_idx"}),
                ("ip_address", {"name": "ip_address_idx"}),
            ],
        ),
        # Link Deal Conversion indexes
        (
            "link_deal_conversions",
            [
                ("link_id", {"name": "link_id_idx"}),
                ("deal_id", {"name": "deal_id_idx"}),
                ("converted_at", {"name": "converted_at_idx"}),
            ],
        ),
        # LinkedIn Credentials indexes
        (
            "linkedin_credentials",
            [
                ("linkedin_profile_id", {"name": "linkedin_profile_id_idx"}),
                ("campaign_id", {"name": "campaign_id_idx"}),
                ("status", {"name": "status_idx"}),
                ("last_verified", {"name": "last_verified_idx"}),
                ("user_id", {"name": "user_id_idx"}),
            ],
        ),
        # LinkedIn Credential Log indexes
        (
            "linkedin_credential_logs",
            [
                ("credential_id", {"name": "credential_id_idx"}),
                ("created_at", {"name": "created_at_idx"}),
            ],
        ),
        # Site Config indexes
        (
            "site_config",
            [
                ("llm_provider", {"name": "llm_provider_idx"}),
            ],
        ),
        # Task indexes
        (
            "tasks",
            [
                ("status", {"name": "status_idx"}),
                ("scheduled_at", {"name": "scheduled_at_idx"}),
                ("task_type", {"name": "task_type_idx"}),
                ("created_at", {"name": "created_at_idx"}),
                ("user_id", {"name": "user_id_idx"}),
            ],
        ),
        # User Profile indexes
        (
            "user_profiles",
            [
                ("user_id", {"name": "user_id_idx", "unique": True}),
                ("email", {"name": "email_idx"}),
                ("created_at", {"name": "created_at_idx"}),
            ],
        ),
    ]

    for collection_name, collection_indexes in indexes:
        try:
            collection = db[collection_name]
            # Get existing indexes for this collection
            existing_indexes = []
            try:
                existing_indexes = [idx["name"] for idx in collection.list_indexes()]
            except Exception as e:
                logger.debug(f"Could not list indexes for '{collection_name}': {e}")
            
            for field_name, options in collection_indexes:
                index_name = options["name"]
                # Only create index if it doesn't already exist
                if index_name not in existing_indexes:
                    try:
                        collection.create_index(field_name, name=index_name)
                        logger.info(
                            f"Created index '{index_name}' on '{collection_name}'"
                        )
                    except Exception as e:
                        logger.error(f"Failed to create index '{index_name}': {e}")
                else:
                    logger.debug(
                        f"Index '{index_name}' already exists on '{collection_name}', skipping"
                    )
        except Exception as e:
            logger.error(f"Failed to process indexes for '{collection_name}': {e}")
