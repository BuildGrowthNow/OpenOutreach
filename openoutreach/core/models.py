# openoutreach/core/models.py
from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

if TYPE_CHECKING:
    from openoutreach.crm.models import Deal
    from openoutreach.linkedin.models import CampaignStateGraph, SearchKeyword


class SiteConfig(models.Model):
    """Singleton model for global site configuration (LLM keys, etc.)."""

    class LLMProvider(models.TextChoices):
        OPENAI = "openai", "OpenAI"
        ANTHROPIC = "anthropic", "Anthropic"
        GOOGLE = "google", "Google"
        GROQ = "groq", "Groq"
        MISTRAL = "mistral", "Mistral"
        COHERE = "cohere", "Cohere"
        OPENAI_COMPATIBLE = "openai_compatible", "OpenAI-compatible"

    llm_provider: models.CharField = models.CharField(  # type: ignore[var-annotated,assignment]
        max_length=32,
        choices=LLMProvider.choices,
        default=LLMProvider.OPENAI,
    )
    llm_api_key: models.CharField = models.CharField(
        max_length=500, blank=True, default=""
    )  # type: ignore[var-annotated]
    ai_model: models.CharField = models.CharField(
        max_length=200, blank=True, default=""
    )  # type: ignore[var-annotated]
    llm_api_base: models.CharField = models.CharField(
        max_length=500, blank=True, default=""
    )  # type: ignore[var-annotated]
    ai_writing_style: models.TextField = models.TextField(blank=True, default="")  # type: ignore[var-annotated]
    ai_say_rules: models.TextField = models.TextField(blank=True, default="")  # type: ignore[var-annotated]
    ai_avoid_rules: models.TextField = models.TextField(blank=True, default="")  # type: ignore[var-annotated]

    # BetterContact email-finder key; blank disables enrichment (see emails/bettercontact.py).
    finder_api_key: models.CharField = models.CharField(
        max_length=500, blank=True, default=""
    )  # type: ignore[var-annotated]

    # LinkedIn profile settings
    linkedin_username: models.CharField = models.CharField(
        max_length=50, blank=True, default=""
    )  # type: ignore[var-annotated]
    linkedin_campaign: models.CharField = models.CharField(
        max_length=100, blank=True, default=""
    )  # type: ignore[var-annotated]

    # Rate limit configuration - SMART vs MANUAL modes
    enable_smart_rate_limiting: models.BooleanField = models.BooleanField(
        default=False,
        help_text="Enable context-aware rate limiting (time-of-day, detectability, engagement patterns)"
    )  # type: ignore[var-annotated]

    class AggressivenessPreset(models.TextChoices):
        VERY_SLOW = "very_slow", "Very Slow (Safest)"
        SLOW = "slow", "Slow"
        AVERAGE = "average", "Average"
        AGGRESSIVE = "aggressive", "Aggressive"
        VERY_AGGRESSIVE = "very_aggressive", "Very Aggressive (Riskiest)"

    aggressiveness_preset: models.CharField = models.CharField(
        max_length=20,
        choices=AggressivenessPreset.choices,
        default=AggressivenessPreset.AVERAGE,
        help_text="Smart rate limiting aggressiveness level (only used when Smart Rate Limiting is ON)"
    )  # type: ignore[var-annotated]

    # Manual rate limit controls (only used when enable_smart_rate_limiting = False)
    daily_connection_limit: models.PositiveIntegerField = models.PositiveIntegerField(
        default=20,
        help_text="Daily connection limit (per LinkedIn profile)"
    )  # type: ignore[var-annotated]
    daily_follow_up_limit: models.PositiveIntegerField = models.PositiveIntegerField(
        default=25,
        help_text="Daily follow-up message limit (per LinkedIn profile)"
    )  # type: ignore[var-annotated]
    # velocity: actions per hour (only used when Smart Rate Limiting is OFF)
    velocity: models.PositiveIntegerField = models.PositiveIntegerField(
        default=20,
        help_text="Actions per hour - only used when Smart Rate Limiting is OFF (>= 30 = burst mode, < 30 = spread mode)"
    )  # type: ignore[var-annotated]

    # BetterContact email-finder key; blank disables enrichment (see emails/bettercontact.py).
    bettercontact_api_key = models.CharField(max_length=500, blank=True, default="")
    # Central contacts service (see openoutreach/contacts/). The token is earned
    # on the first contribution and persisted here — never in the repo; blank
    # means "not registered yet" (resolve misses until the first give-back mints
    # it). The URL is blank by default (falls back to DEFAULT_CONTACTS_API_URL).
    contacts_api_token = models.CharField(max_length=500, blank=True, default="")
    contacts_api_url = models.CharField(max_length=500, blank=True, default="")

    # Active hours configuration (when daemon executes tasks)
    enable_active_hours: models.BooleanField = models.BooleanField(default=True)  # type: ignore[var-annotated]
    active_start_hour: models.PositiveSmallIntegerField = models.PositiveSmallIntegerField(
        default=9, help_text="Start hour (0-23, inclusive)"
    )  # type: ignore[var-annotated]
    active_end_hour: models.PositiveSmallIntegerField = models.PositiveSmallIntegerField(
        default=19, help_text="End hour (0-23, exclusive)"
    )  # type: ignore[var-annotated]
    active_timezone: models.CharField = models.CharField(
        max_length=100, default="UTC", help_text="IANA timezone (e.g., America/New_York)"
    )  # type: ignore[var-annotated]
    active_days: models.CharField = models.CharField(
        max_length=50,
        default="1,2,3,4,5",
        help_text="Active weekdays as comma-separated integers (1=Monday, 7=Sunday)",
    )  # type: ignore[var-annotated]

    class Meta:
        verbose_name = "Site Configuration"
        verbose_name_plural = "Site Configuration"

    def __str__(self):
        return "Site Configuration"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "SiteConfig":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class CampaignTemplate(models.Model):
    """Template for creating campaigns with predefined settings."""

    id: models.AutoField  # type: ignore[assignment]

    name: models.CharField = models.CharField(max_length=200)  # type: ignore[var-annotated]
    description: models.TextField = models.TextField(blank=True)  # type: ignore[var-annotated]
    product_pitch: models.TextField = models.TextField(blank=True)  # type: ignore[var-annotated]
    campaign_objective: models.TextField = models.TextField(blank=True)  # type: ignore[var-annotated]
    booking_link: models.URLField = models.URLField(max_length=500, blank=True)  # type: ignore[var-annotated]
    icp_titles: models.JSONField = models.JSONField(default=list, blank=True)  # type: ignore[var-annotated]
    follow_up_strategy: models.TextField = models.TextField(blank=True)  # type: ignore[var-annotated]
    ghost_mode_enabled: models.BooleanField = models.BooleanField(default=False)  # type: ignore[var-annotated]

    # Template sharing
    is_public: models.BooleanField = models.BooleanField(default=False)  # type: ignore[var-annotated]
    created_by: models.ForeignKey = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="campaign_templates"
    )  # type: ignore[var-annotated]

    # Timestamps
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)  # type: ignore[var-annotated]
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)  # type: ignore[var-annotated]

    def __str__(self) -> str:
        return self.name

    class Meta:
        ordering = ["-created_at"]


class Campaign(models.Model):
    # Type hints for Django's automatic fields
    id: models.AutoField  # type: ignore[assignment]

    class Status(models.TextChoices):
        ACTIVE = "active"
        PAUSED = "paused"
        DRAFT = "draft"

    name: models.CharField = models.CharField(max_length=200, unique=True)  # type: ignore[var-annotated]
    description: models.TextField = models.TextField(blank=True)  # type: ignore[var-annotated]
    users: models.ManyToManyField = models.ManyToManyField(
        User, blank=True, related_name="campaigns"
    )  # type: ignore[var-annotated]
    product_pitch: models.TextField = models.TextField(blank=True)  # type: ignore[var-annotated]
    campaign_objective: models.TextField = models.TextField(blank=True)  # type: ignore[var-annotated]
    booking_link: models.URLField = models.URLField(max_length=500, blank=True)  # type: ignore[var-annotated]
    icp_titles: models.JSONField = models.JSONField(default=list, blank=True)  # type: ignore[var-annotated]
    follow_up_strategy: models.TextField = models.TextField(blank=True)  # type: ignore[var-annotated]
    is_freemium: models.BooleanField = models.BooleanField(default=False)  # type: ignore[var-annotated]
    ghost_mode_enabled: models.BooleanField = models.BooleanField(default=False)  # type: ignore[var-annotated]
    action_fraction: models.FloatField = models.FloatField(default=0.2)  # type: ignore[var-annotated]
    seed_public_ids: models.JSONField = models.JSONField(default=list, blank=True)  # type: ignore[var-annotated]
    model_blob: models.BinaryField = models.BinaryField(null=True, blank=True)  # type: ignore[var-annotated]

    # Campaign status (rate limiting moved to account-level SiteConfig)
    is_paused: models.BooleanField = models.BooleanField(
        default=False
    )  # pause the campaign  # type: ignore[var-annotated]
    status: models.CharField = models.CharField(  # type: ignore[var-annotated]
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    # Timestamps
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)  # type: ignore[var-annotated]
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)  # type: ignore[var-annotated]

    # Links - references to TrackedLink from crm app for URL tracking
    # Using a ManyToMany through a string reference to avoid circular imports
    # The existing TrackedLink model has a ForeignKey to Campaign already,
    # but we'll also allow multiple campaigns to use the same link
    # For now, we just reference the model for type hints
    if TYPE_CHECKING:
        from openoutreach.crm.models import TrackedLink

        tracked_links: models.Manager["TrackedLink"]

    # Type hints for reverse relations (from other apps)
    state_graph: "CampaignStateGraph"
    deals: "models.Manager[Deal]"
    search_keywords: "models.Manager[SearchKeyword]"

    def __str__(self) -> str:
        return self.name


# NOTE: We use the existing TrackedLink from crm.models.link for link tracking
# This avoids duplicate models and allows both apps to share the same functionality


class TaskQuerySet(models.QuerySet):
    def pending(self) -> "TaskQuerySet":  # type: ignore[misc]
        return self.filter(status=Task.Status.PENDING).order_by("scheduled_at")

    def claim_next(self) -> "Task | None":
        return self.pending().filter(scheduled_at__lte=timezone.now()).first()  # type: ignore[call-arg,no-any-return]

    def seconds_to_next(self) -> float | None:
        """Seconds until the next pending task, or None if queue is empty."""
        next_task = self.pending().only("scheduled_at").first()  # type: ignore[call-arg]
        if next_task is None:
            return None
        return max((next_task.scheduled_at - timezone.now()).total_seconds(), 0)  # type: ignore[misc]


class Task(models.Model):
    class TaskType(models.TextChoices):
        CONNECT = "connect"
        CHECK_PENDING = "check_pending"
        FOLLOW_UP = "follow_up"
        SEND_MANUAL_MESSAGE = "send_manual_message"

    class Status(models.TextChoices):
        PENDING = "pending"
        RUNNING = "running"
        COMPLETED = "completed"
        FAILED = "failed"

    task_type: models.CharField = models.CharField(
        max_length=20, choices=TaskType.choices
    )  # type: ignore[var-annotated]
    status: models.CharField = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )  # type: ignore[var-annotated]
    scheduled_at: models.DateTimeField = models.DateTimeField()  # type: ignore[var-annotated]
    payload: models.JSONField = models.JSONField(default=dict)  # type: ignore[var-annotated]
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)  # type: ignore[var-annotated]
    started_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)  # type: ignore[var-annotated]
    completed_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)  # type: ignore[var-annotated]

    objects: TaskQuerySet = TaskQuerySet.as_manager()  # type: ignore[assignment, misc, var-annotated]

    class Meta:
        indexes = [
            models.Index(
                fields=["status", "scheduled_at"],
                name="core_task_status_sched_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.task_type} [{self.status}] scheduled={self.scheduled_at}"

    def get_error_message(self) -> str | None:
        """Get the last error message from payload if available."""
        return (self.payload or {}).get("last_error")

    def mark_running(self):
        self.status = self.Status.RUNNING
        self.started_at = timezone.now()
        self.save(update_fields=["status", "started_at"])

    def mark_completed(self):
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
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
            updated_payload["last_error"] = error_message[
                :500
            ]  # Truncate to avoid huge payloads
            self.payload = updated_payload
        self.save(update_fields=["status"])
