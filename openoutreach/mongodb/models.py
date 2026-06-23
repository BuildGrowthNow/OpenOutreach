"""
MongoDB Compatible Models for OpenOutreach

This module provides MongoDB-compatible versions of the CRM models
that work with the Djongo connector to use MongoDB as the database backend.

These models maintain compatibility with existing Django REST API endpoints
while leveraging MongoDB's document-based storage.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.utils import timezone

from .connection import get_mongodb_collection, check_mongodb_connection

if TYPE_CHECKING:
    from datetime import timedelta

logger = logging.getLogger(__name__)


class BaseMongoModel(models.Model):
    """
    Base class for MongoDB-compatible models.
    
    Provides common functionality for all MongoDB models including:
    - Auto-generated ObjectId
    - Timestamps
    - Custom save/delete methods
    - Document serialization
    """
    
    _id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    created_at: models.DateTimeField = models.DateTimeField(default=timezone.now)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)
    
    class Meta:  # type: ignore[misc]
        abstract = True
    
    def save(self, *args, **kwargs):
        """Override save to handle MongoDB-specific operations."""
        # Update updated_at timestamp
        if not self.created_at:
            self.created_at = timezone.now()
        self.updated_at = timezone.now()
        
        # Call parent save
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):  # type: ignore[override]
        """Override delete to handle MongoDB-specific operations."""
        return super().delete(*args, **kwargs)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary."""
        fields = self._meta.get_fields()
        data: Dict[str, Any] = {}
        
        for field in fields:
            if field.is_relation:
                continue
            try:
                value = getattr(self, field.name)
                if value is not None:
                    data[field.name] = value
            except AttributeError:
                pass
        
        return data
    
    def __str__(self):
        return f"{self.__class__.__name__}#{self._id}"


class Lead(BaseMongoModel):
    """
    MongoDB-compatible Lead model.
    
    Represents a lead in the CRM system with MongoDB-specific fields.
    """
    
    class Meta:  # type: ignore[misc]
        verbose_name = "Lead"
        verbose_name_plural = "Leads"
        indexes = [
            models.Index(fields=['public_identifier'], name='mongodb_lead_public_idx'),
            models.Index(fields=['linkedin_url'], name='mongodb_lead_url_idx'),
            models.Index(fields=['creation_date'], name='mongodb_lead_creation_idx'),
        ]
        db_table = 'leads'
    
    linkedin_url: models.URLField = models.URLField(max_length=200, unique=True)
    public_identifier: models.CharField = models.CharField(max_length=200, unique=True)
    urn: models.CharField | None = models.CharField(max_length=200, null=True, blank=True)
    embedding: models.BinaryField | None = models.BinaryField(null=True, blank=True)
    contact_info: models.JSONField = models.JSONField(null=True, blank=True, default=None)
    api_email: models.EmailField | None = models.EmailField(null=True, blank=True, default=None)
    disqualified: models.BooleanField = models.BooleanField(default=False)
    creation_date: models.DateTimeField = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        label = self.public_identifier or self.linkedin_url or f"Lead#{self._id}"
        if self.disqualified:
            return f"(Disqualified) {label}"
        return label


class Campaign(BaseMongoModel):
    """
    MongoDB-compatible Campaign model.
    
    Represents a marketing campaign with MongoDB-specific fields.
    """
    
    class Meta:  # type: ignore[misc]
        verbose_name = "Campaign"
        verbose_name_plural = "Campaigns"
        indexes = [
            models.Index(fields=['name'], name='mongodb_campaign_name_idx'),
            models.Index(fields=['is_paused'], name='mongodb_campaign_paused_idx'),
            models.Index(fields=['created_at'], name='mongodb_campaign_creation_idx'),
        ]
        db_table = 'campaigns'
    
    name: models.CharField = models.CharField(max_length=200, unique=True)
    product_docs: models.TextField = models.TextField(blank=True)
    campaign_objective: models.TextField = models.TextField(blank=True)
    booking_link: models.URLField = models.URLField(max_length=500, blank=True)
    is_freemium: models.BooleanField = models.BooleanField(default=False)
    action_fraction: models.FloatField = models.FloatField(default=0.2)
    seed_public_ids: models.JSONField = models.JSONField(default=list, blank=True)
    model_blob: models.BinaryField | None = models.BinaryField(null=True, blank=True)
    velocity: models.PositiveIntegerField = models.PositiveIntegerField(default=20)
    cooldown_minutes: models.PositiveIntegerField = models.PositiveIntegerField(default=0)
    is_paused: models.BooleanField = models.BooleanField(default=False)
    
    def __str__(self):
        return self.name


class Deal(BaseMongoModel):
    """
    MongoDB-compatible Deal model.
    
    Represents a deal in the CRM system linked to a lead and campaign.
    """
    
    class DealState(models.TextChoices):
        QUALIFIED = "Qualified"
        READY_TO_CONNECT = "Ready to Connect"
        PENDING = "Pending"
        CONNECTED = "Connected"
        COMPLETED = "Completed"
        FAILED = "Failed"
        NO_EMAIL = "No Email"
    
    class Outcome(models.TextChoices):
        CONVERTED = "converted"
        NOT_INTERESTED = "not_interested"
        WRONG_FIT = "wrong_fit"
        NO_BUDGET = "no_budget"
        HAS_SOLUTION = "has_solution"
        BAD_TIMING = "bad_timing"
        UNRESPONSIVE = "unresponsive"
        UNKNOWN = "unknown"
    
    class Meta:  # type: ignore[misc]
        verbose_name = "Deal"
        verbose_name_plural = "Deals"
        indexes = [
            models.Index(fields=['lead_id'], name='mongodb_deal_lead_idx'),
            models.Index(fields=['campaign_id'], name='mongodb_deal_campaign_idx'),
            models.Index(fields=['state'], name='mongodb_deal_state_idx'),
        ]
        db_table = 'deals'
    
    # MongoDB uses string IDs for relationships
    lead_id: models.CharField = models.CharField(max_length=100, db_index=True)
    campaign_id: models.CharField = models.CharField(max_length=100, db_index=True)
    state: models.CharField = models.CharField(
        max_length=20,
        choices=DealState.choices,
        default=DealState.QUALIFIED,
    )
    outcome: models.CharField = models.CharField(
        max_length=20,
        choices=Outcome.choices,
        blank=True,
        default="",
    )
    reason: models.TextField = models.TextField(blank=True, default="")
    connect_attempts: models.IntegerField = models.IntegerField(default=0)
    backoff_hours: models.IntegerField = models.IntegerField(default=0)
    next_check_pending_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)
    profile_summary: models.JSONField = models.JSONField(null=True, blank=True, default=None)
    chat_summary: models.JSONField = models.JSONField(null=True, blank=True, default=None)
    
    def __str__(self):
        return f"Deal#{self._id} - {self.state}"


class Message(BaseMongoModel):
    """
    MongoDB-compatible Message model.
    
    Represents a CRM message linked to a deal.
    """
    
    class Meta:  # type: ignore[misc]
        verbose_name = "Message"
        verbose_name_plural = "Messages"
        indexes = [
            models.Index(fields=['deal_id'], name='mongodb_message_deal_idx'),
            models.Index(fields=['created_at'], name='mongodb_message_created_idx'),
        ]
        db_table = 'messages'
    
    deal_id: models.CharField = models.CharField(max_length=100, db_index=True)
    content: models.TextField = models.TextField()
    is_outgoing: models.BooleanField = models.BooleanField(default=True)
    
    def __str__(self):
        return f"Message #{self._id} for Deal #{self.deal_id}"
    
    @property
    def sender(self) -> str:
        """Get the sender of the message."""
        if self.is_outgoing:
            return "User"
        return "Lead"


class Note(BaseMongoModel):
    """
    MongoDB-compatible Note model.
    
    Represents a note linked to a deal.
    """
    
    class Meta:  # type: ignore[misc]
        verbose_name = "Note"
        verbose_name_plural = "Notes"
        indexes = [
            models.Index(fields=['deal_id'], name='mongodb_note_deal_idx'),
            models.Index(fields=['created_at'], name='mongodb_note_created_idx'),
        ]
        db_table = 'notes'
    
    deal_id: models.CharField = models.CharField(max_length=100, db_index=True)
    content: models.TextField = models.TextField()
    created_by_id: models.CharField | None = models.CharField(max_length=100, null=True, blank=True)
    
    def __str__(self):
        return f"Note #{self._id} for Deal #{self.deal_id}"


class LeadPersona(BaseMongoModel):
    """
    MongoDB-compatible Lead Persona model.
    
    Stores LLM-generated detailed lead personas for hyper-personalization.
    """
    
    class Meta:  # type: ignore[misc]
        verbose_name = "Lead Persona"
        verbose_name_plural = "Lead Personas"
        indexes = [
            models.Index(fields=['lead_id'], name='mongodb_persona_lead_idx'),
            models.Index(fields=['campaign_id'], name='mongodb_persona_campaign_idx'),
            models.Index(fields=['confidence_score'], name='mongodb_persona_confidence_idx'),
        ]
        db_table = 'lead_personas'
        unique_together = ('lead_id', 'campaign_id')
    
    lead_id: models.CharField = models.CharField(max_length=100, db_index=True)
    campaign_id: models.CharField = models.CharField(max_length=100, db_index=True)
    
    # Persona fields (stored as JSON for flexibility)
    pain_points: models.JSONField = models.JSONField(default=list)
    goals: models.JSONField = models.JSONField(default=list)
    messaging_preferences: models.JSONField = models.JSONField(default=dict)
    buy_signals: models.JSONField = models.JSONField(default=list)
    confidence_score: models.FloatField = models.FloatField(default=0.5)
    recommendations: models.JSONField = models.JSONField(default=list)
    version: models.PositiveIntegerField = models.PositiveIntegerField(default=1)
    
    def __str__(self):
        return f"Persona v{self.version} for Lead {self.lead_id}"
    
    @property
    def is_high_confidence(self) -> bool:
        """Check if the persona has high confidence (>= 0.7)."""
        return self.confidence_score >= 0.7
    
    @property
    def has_buy_signals(self) -> bool:
        """Check if any buy signals were identified."""
        return len(self.buy_signals) > 0


class TrackedLink(BaseMongoModel):
    """
    MongoDB-compatible Tracked Link model.
    
    For tracking marketing links with UTM parameters.
    """
    
    class Meta:  # type: ignore[misc]
        verbose_name = "Tracked Link"
        verbose_name_plural = "Tracked Links"
        indexes = [
            models.Index(fields=['short_code'], name='mongodb_link_shortcode_idx'),
            models.Index(fields=['campaign_id'], name='mongodb_link_campaign_idx'),
            models.Index(fields=['created_at'], name='mongodb_link_created_idx'),
        ]
        db_table = 'tracked_links'
    
    campaign_id: models.CharField | None = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    original_url: models.URLField = models.URLField(max_length=1000)
    short_code: models.CharField = models.CharField(max_length=50, unique=True)
    is_active: models.BooleanField = models.BooleanField(default=True)
    utm_source: models.CharField = models.CharField(max_length=100, blank=True)
    utm_medium: models.CharField = models.CharField(max_length=100, blank=True)
    utm_campaign: models.CharField = models.CharField(max_length=100, blank=True)
    utm_term: models.CharField = models.CharField(max_length=100, blank=True)
    utm_content: models.CharField = models.CharField(max_length=100, blank=True)
    total_clicks: models.PositiveIntegerField = models.PositiveIntegerField(default=0)
    unique_clicks: models.PositiveIntegerField = models.PositiveIntegerField(default=0)
    last_clicked_at: models.DateTimeField | None = models.DateTimeField(null=True, blank=True)
    last_ip: models.GenericIPAddressField | None = models.GenericIPAddressField(null=True, blank=True)
    last_user_agent: models.CharField = models.CharField(max_length=500, blank=True)
    
    def __str__(self):
        return f"{self.short_code}"
    
    def get_short_url(self) -> str:
        """Get the short tracked URL."""
        return f"https://yourdomain.com/l/{self.short_code}"
    
    @property
    def conversion_rate(self) -> float:
        """Calculate conversion rate based on linked deals."""
        if self.total_clicks == 0:
            return 0.0
        return 0.0  # In MongoDB mode, we don't have deal_links relation


class LinkClick(BaseMongoModel):
    """
    MongoDB-compatible Link Click model.
    
    Stores individual click records for detailed analytics.
    """
    
    class Meta:  # type: ignore[misc]
        verbose_name = "Link Click"
        verbose_name_plural = "Link Clicks"
        indexes = [
            models.Index(fields=['link_id'], name='mongodb_click_link_idx'),
            models.Index(fields=['clicked_at'], name='mongodb_click_time_idx'),
            models.Index(fields=['ip_address'], name='mongodb_click_ip_idx'),
        ]
        db_table = 'link_clicks'
    
    link_id: models.CharField = models.CharField(max_length=100, db_index=True)
    clicked_at: models.DateTimeField = models.DateTimeField(default=timezone.now)
    ip_address: models.GenericIPAddressField | None = models.GenericIPAddressField(null=True, blank=True)
    user_agent: models.CharField = models.CharField(max_length=500, blank=True)
    referrer: models.CharField = models.CharField(max_length=500, blank=True)
    device_type: models.CharField = models.CharField(
        max_length=20,
        choices=[
            ('desktop', 'Desktop'),
            ('mobile', 'Mobile'),
            ('tablet', 'Tablet'),
        ],
        blank=True
    )
    country: models.CharField = models.CharField(max_length=100, blank=True)
    
    def __str__(self):
        return f"Click on Link {self.link_id} at {self.clicked_at}"
    
    def detect_device(self) -> Optional[str]:
        """Detect device type from user agent."""
        if not self.user_agent:
            return None
        
        ua_lower = self.user_agent.lower()
        
        if 'mobile' in ua_lower or 'android' in ua_lower or 'iphone' in ua_lower:
            self.device_type = 'mobile'
        elif 'ipad' in ua_lower or 'tablet' in ua_lower:
            self.device_type = 'tablet'
        else:
            self.device_type = 'desktop'
        
        return self.device_type


class LinkDealConversion(BaseMongoModel):
    """
    MongoDB-compatible Link Deal Conversion model.
    
    Links link clicks to actual deal conversions.
    """
    
    class Meta:  # type: ignore[misc]
        verbose_name = "Link Conversion"
        verbose_name_plural = "Link Conversions"
        indexes = [
            models.Index(fields=['link_id'], name='mongodb_conv_link_idx'),
            models.Index(fields=['deal_id'], name='mongodb_conv_deal_idx'),
        ]
        db_table = 'link_deal_conversions'
    
    link_id: models.CharField = models.CharField(max_length=100, db_index=True)
    click_id: models.CharField | None = models.CharField(max_length=100, null=True, blank=True)
    deal_id: models.CharField = models.CharField(max_length=100, db_index=True)
    
    def __str__(self):
        return f"Conversion: Link {self.link_id} -> Deal {self.deal_id}"


class LinkedInCredentials(BaseMongoModel):
    """
    MongoDB-compatible LinkedIn Credentials model.
    
    Securely stored LinkedIn credentials with encryption at rest.
    """
    
    STATUS_ACTIVE = 'active'
    STATUS_INVALID = 'invalid'
    STATUS_EXPIRED = 'expired'
    STATUS_LOCKED = 'locked'
    STATUS_BACKUP = 'backup'
    
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_INVALID, 'Invalid - needs re-verification'),
        (STATUS_EXPIRED, 'Expired - needs rotation'),
        (STATUS_LOCKED, 'Locked - temporarily disabled'),
        (STATUS_BACKUP, 'Backup credential'),
    ]
    
    class Meta:  # type: ignore[misc]
        verbose_name = 'LinkedIn Credential'
        verbose_name_plural = 'LinkedIn Credentials'
        indexes = [
            models.Index(fields=['status', 'expires_at']),
            models.Index(fields=['campaign_id', 'status']),
        ]
        db_table = 'linkedin_credentials'
    
    linkedin_profile_id: models.CharField | None = models.CharField(max_length=100, null=True, blank=True)
    email_encrypted: models.BinaryField = models.BinaryField(max_length=500)
    password_encrypted: models.BinaryField = models.BinaryField(max_length=500)
    username: models.CharField = models.CharField(max_length=200, blank=True)
    status: models.CharField = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
    )
    last_verified: models.DateTimeField = models.DateTimeField(null=True, blank=True)
    verification_failed_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)
    verification_failures: models.PositiveIntegerField = models.PositiveIntegerField(default=0)
    usage_count: models.PositiveIntegerField = models.PositiveIntegerField(default=0)
    last_used: models.DateTimeField = models.DateTimeField(null=True, blank=True)
    campaign_id: models.CharField | None = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    expires_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)
    rotated_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)
    rotation_required_days: models.PositiveIntegerField = models.PositiveIntegerField(default=90)
    is_primary: models.BooleanField = models.BooleanField(default=True)
    is_backup: models.BooleanField = models.BooleanField(default=False)
    backup_of_id: models.CharField | None = models.CharField(max_length=100, null=True, blank=True)
    security_alert_sent_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"LinkedInCredential #{self._id} ({self.get_public_email()})"
    
    def get_public_email(self) -> str:
        """Get a masked version of the email for display."""
        try:
            # In MongoDB mode, the email would be stored as plain text in the document
            # For now, return a placeholder
            return "***@***"
        except Exception:
            return "***@***"
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get a comprehensive health status for these credentials."""
        now = timezone.now()
        days_since_rotation = 0
        if self.rotated_at:
            days_since_rotation = (now - self.rotated_at).days
        
        days_until_expiry: Optional[int] = None
        if self.expires_at:
            days_until_expiry = (self.expires_at - now).days
        
        return {
            'id': str(self._id),
            'username': self.username or '',
            'public_email': self.get_public_email(),
            'status': self.status,
            'is_primary': self.is_primary,
            'is_backup': self.is_backup,
            'usage_count': self.usage_count,
            'days_since_rotation': days_since_rotation,
            'days_until_expiry': days_until_expiry,
            'verification_failures': self.verification_failures,
            'last_verified': self.last_verified.isoformat() if self.last_verified else None,
            'last_used': self.last_used.isoformat() if self.last_used else None,
            'health_score': self._calculate_health_score(),
        }
    
    def _calculate_health_score(self) -> int:
        """Calculate a health score (0-100) for these credentials."""
        score = 100
        
        if self.status == self.STATUS_INVALID:
            score -= 50
        elif self.status == self.STATUS_LOCKED:
            score -= 30
        elif self.status == self.STATUS_EXPIRED:
            score -= 20
        
        if self.rotated_at:
            days_old = (timezone.now() - self.rotated_at).days
            if days_old > self.rotation_required_days:
                score -= 20
        
        score -= self.verification_failures * 5
        
        return max(0, min(100, score))


class LinkedInCredentialLog(BaseMongoModel):
    """
    MongoDB-compatible LinkedIn Credential Log model.
    
    Audit log for LinkedIn credential actions.
    """
    
    ACTION_VERIFIED = 'verified'
    ACTION_FAILED = 'failed'
    ACTION_LOCKED = 'locked'
    ACTION_UNLOCKED = 'unlocked'
    ACTION_ROTATED = 'rotated'
    ACTION_BACKUP = 'backup'
    ACTION_USAGE = 'usage'
    
    ACTION_CHOICES = [
        (ACTION_VERIFIED, 'Verified'),
        (ACTION_FAILED, 'Failed'),
        (ACTION_LOCKED, 'Locked'),
        (ACTION_UNLOCKED, 'Unlocked'),
        (ACTION_ROTATED, 'Rotated'),
        (ACTION_BACKUP, 'Backup Created'),
        (ACTION_USAGE, 'Usage Recorded'),
    ]
    
    class Meta:  # type: ignore[misc]
        verbose_name = 'LinkedIn Credential Log'
        verbose_name_plural = 'LinkedIn Credential Logs'
        indexes = [
            models.Index(fields=['credentials_id'], name='mongodb_credentiallog_cred_idx'),
            models.Index(fields=['created_at'], name='mongodb_credentiallog_created_idx'),
        ]
        db_table = 'linkedin_credential_logs'
    
    credentials_id: models.CharField = models.CharField(max_length=100, db_index=True)
    action: models.CharField = models.CharField(max_length=20, choices=ACTION_CHOICES)
    details: models.JSONField = models.JSONField(default=dict, blank=True)
    ip_address: models.GenericIPAddressField | None = models.GenericIPAddressField(null=True, blank=True)
    user_agent: models.CharField = models.CharField(max_length=500, blank=True)
    
    def __str__(self):
        return f"{self.credentials_id} - {self.action} at {self.created_at}"


class SiteConfig(BaseMongoModel):
    """
    MongoDB-compatible Site Configuration model.
    """
    
    class LLMProvider(models.TextChoices):
        OPENAI = "openai"
        ANTHROPIC = "anthropic"
        GOOGLE = "google"
        GROQ = "groq"
        MISTRAL = "mistral"
        COHERE = "cohere"
        OPENAI_COMPATIBLE = "openai_compatible"
    
    class Meta:  # type: ignore[misc]
        verbose_name = "Site Configuration"
        verbose_name_plural = "Site Configuration"
        db_table = 'site_config'
    
    llm_provider: models.CharField = models.CharField(
        max_length=32,
        choices=LLMProvider.choices,
        default=LLMProvider.OPENAI,
    )
    llm_api_key: models.CharField = models.CharField(max_length=500, blank=True, default="")
    ai_model: models.CharField = models.CharField(max_length=200, blank=True, default="")
    llm_api_base: models.CharField = models.CharField(max_length=500, blank=True, default="")
    finder_api_key: models.CharField = models.CharField(max_length=500, blank=True, default="")
    
    def __str__(self):
        return "Site Configuration"
    
    def save(self, *args, **kwargs):
        """Ensure only one SiteConfig exists."""
        self.pk = 1
        super().save(*args, **kwargs)
    
    @classmethod
    def load(cls) -> 'SiteConfig':
        """Load the site configuration."""
        try:
            return cls.objects.get(pk=1)
        except cls.DoesNotExist:
            return cls.objects.create(pk=1)


class Task(BaseMongoModel):
    """
    MongoDB-compatible Task model.
    
    For scheduling and managing background tasks.
    """
    
    class TaskType(models.TextChoices):
        CONNECT = "connect"
        CHECK_PENDING = "check_pending"
        FOLLOW_UP = "follow_up"
    
    class Status(models.TextChoices):
        PENDING = "pending"
        RUNNING = "running"
        COMPLETED = "completed"
        FAILED = "failed"
    
    class Meta:  # type: ignore[misc]
        verbose_name = "Task"
        verbose_name_plural = "Tasks"
        indexes = [
            models.Index(fields=['status', 'scheduled_at'], name='mongodb_task_status_sched_idx'),
        ]
        db_table = 'tasks'
    
    task_type: models.CharField = models.CharField(max_length=20, choices=TaskType.choices)
    status: models.CharField = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    scheduled_at: models.DateTimeField = models.DateTimeField()
    payload: models.JSONField = models.JSONField(default=dict)
    started_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)
    completed_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.task_type} [{self.status}]"
    
    def mark_running(self):
        """Mark task as running."""
        self.status = self.Status.RUNNING
        self.started_at = timezone.now()
        self.save(update_fields=["status", "started_at"])
    
    def mark_completed(self):
        """Mark task as completed."""
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "completed_at"])
    
    def mark_failed(self):
        """Mark task as failed."""
        self.status = self.Status.FAILED
        self.save(update_fields=["status"])


# Management functions for MongoDB models

def ensure_mongodb_indexes():
    """Create required indexes for MongoDB collections."""
    from .connection import get_mongodb_collection, mongodb_connection
    
    if not check_mongodb_connection():
        logger.warning("MongoDB not connected, skipping index creation")
        return
    
    indexes = [
        # Lead indexes
        ('leads', [
            {'name': 'public_identifier_idx', 'fields': {'public_identifier': 1}},
            {'name': 'linkedin_url_idx', 'fields': {'linkedin_url': 1}},
            {'name': 'creation_date_idx', 'fields': {'creation_date': 1}},
        ]),
        # Campaign indexes
        ('campaigns', [
            {'name': 'name_idx', 'fields': {'name': 1}},
            {'name': 'paused_idx', 'fields': {'is_paused': 1}},
        ]),
        # Deal indexes
        ('deals', [
            {'name': 'lead_idx', 'fields': {'lead_id': 1}},
            {'name': 'campaign_idx', 'fields': {'campaign_id': 1}},
            {'name': 'state_idx', 'fields': {'state': 1}},
        ]),
        # Message indexes
        ('messages', [
            {'name': 'deal_idx', 'fields': {'deal_id': 1}},
        ]),
        # Link indexes
        ('tracked_links', [
            {'name': 'shortcode_idx', 'fields': {'short_code': 1}},
            {'name': 'campaign_idx', 'fields': {'campaign_id': 1}},
        ]),
    ]
    
    for collection_name, collection_indexes in indexes:
        collection = mongodb_connection.get_collection(collection_name)
        if collection is not None:
            for idx in collection_indexes:
                try:
                    collection.create_index(list(idx["fields"].items()), name=idx["name"])
                    logger.info(f"Created index '{idx['name']}' on '{collection_name}'")
                except Exception as e:
                    logger.error(f"Failed to create index '{idx['name']}': {e}")


def get_mongodb_lead(lead_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a lead from MongoDB by ID.
    
    Args:
        lead_id: The MongoDB ObjectId as string
        
    Returns:
        Lead document or None if not found
    """
    collection = get_mongodb_collection('leads')
    if collection is None:
        return None
    
    try:
        from bson import ObjectId  # type: ignore
        lead = collection.find_one({'_id': ObjectId(lead_id)})  # type: ignore
        if lead:
            lead['_id'] = str(lead['_id'])
        return lead
    except Exception as e:
        logger.error(f"Failed to get lead '{lead_id}': {e}")
        return None


def get_mongodb_campaign(campaign_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a campaign from MongoDB by ID.
    
    Args:
        campaign_id: The MongoDB ObjectId as string
        
    Returns:
        Campaign document or None if not found
    """
    collection = get_mongodb_collection('campaigns')
    if collection is None:
        return None
    
    try:
        from bson import ObjectId  # type: ignore
        campaign = collection.find_one({'_id': ObjectId(campaign_id)})  # type: ignore
        if campaign:
            campaign['_id'] = str(campaign['_id'])
        return campaign
    except Exception as e:
        logger.error(f"Failed to get campaign '{campaign_id}': {e}")
        return None
