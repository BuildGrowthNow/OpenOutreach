# openoutreach/core/models.py
from __future__ import annotations

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


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
    llm_api_key: models.CharField = models.CharField(max_length=500, blank=True, default="")  # type: ignore[var-annotated]
    ai_model: models.CharField = models.CharField(max_length=200, blank=True, default="")  # type: ignore[var-annotated]
    llm_api_base: models.CharField = models.CharField(max_length=500, blank=True, default="")  # type: ignore[var-annotated]

    # BetterContact email-finder key; blank disables enrichment (see emails/finder.py).
    finder_api_key: models.CharField = models.CharField(max_length=500, blank=True, default="")  # type: ignore[var-annotated]

    # LinkedIn profile settings
    linkedin_username: models.CharField = models.CharField(max_length=50, blank=True, default="")  # type: ignore[var-annotated]
    linkedin_campaign: models.CharField = models.CharField(max_length=100, blank=True, default="")  # type: ignore[var-annotated]

    # Rate limit configuration
    daily_connection_limit: models.PositiveIntegerField = models.PositiveIntegerField(default=20)  # type: ignore[var-annotated]
    daily_follow_up_limit: models.PositiveIntegerField = models.PositiveIntegerField(default=25)  # type: ignore[var-annotated]
    velocity: models.PositiveIntegerField = models.PositiveIntegerField(default=20)  # max actions per time period  # type: ignore[var-annotated]
    cooldown_minutes: models.PositiveIntegerField = models.PositiveIntegerField(default=0)  # minutes between actions  # type: ignore[var-annotated]

    
    # BetterContact email-finder key; blank disables enrichment (see emails/bettercontact.py).
    bettercontact_api_key = models.CharField(max_length=500, blank=True, default="")

    # Central contacts service (see openoutreach/contacts/). The token is earned
    # on the first contribution and persisted here — never in the repo; blank
    # means "not registered yet" (resolve misses until the first give-back mints
    # it). The URL is blank by default (falls back to DEFAULT_CONTACTS_API_URL).
    contacts_api_token = models.CharField(max_length=500, blank=True, default="")
    contacts_api_url = models.CharField(max_length=500, blank=True, default="")
    
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


class Campaign(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active"
        PAUSED = "paused"
        DRAFT = "draft"

    name: models.CharField = models.CharField(max_length=200, unique=True)  # type: ignore[var-annotated]
    description: models.TextField = models.TextField(blank=True)  # type: ignore[var-annotated]
    users: models.ManyToManyField = models.ManyToManyField(User, blank=True, related_name="campaigns")  # type: ignore[var-annotated]
    product_docs: models.TextField = models.TextField(blank=True)  # type: ignore[var-annotated]
    campaign_objective: models.TextField = models.TextField(blank=True)  # type: ignore[var-annotated]
    booking_link: models.URLField = models.URLField(max_length=500, blank=True)  # type: ignore[var-annotated]
    is_freemium: models.BooleanField = models.BooleanField(default=False)  # type: ignore[var-annotated]
    ghost_mode_enabled: models.BooleanField = models.BooleanField(default=False)  # type: ignore[var-annotated]
    action_fraction: models.FloatField = models.FloatField(default=0.2)  # type: ignore[var-annotated]
    seed_public_ids: models.JSONField = models.JSONField(default=list, blank=True)  # type: ignore[var-annotated]
    model_blob: models.BinaryField = models.BinaryField(null=True, blank=True)  # type: ignore[var-annotated]
    
    # Campaign configuration for auto-recovery
    velocity: models.PositiveIntegerField = models.PositiveIntegerField(default=20)  # max actions per time period  # type: ignore[var-annotated]
    cooldown_minutes: models.PositiveIntegerField = models.PositiveIntegerField(default=0)  # minutes between actions  # type: ignore[var-annotated]
    is_paused: models.BooleanField = models.BooleanField(default=False)  # pause the campaign  # type: ignore[var-annotated]
    status: models.CharField = models.CharField(  # type: ignore[var-annotated]
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    def __str__(self) -> str:
        return self.name


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

    class Status(models.TextChoices):
        PENDING = "pending"
        RUNNING = "running"
        COMPLETED = "completed"
        FAILED = "failed"

    task_type: models.CharField = models.CharField(max_length=20, choices=TaskType.choices)  # type: ignore[var-annotated]
    status: models.CharField = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)  # type: ignore[var-annotated]
    scheduled_at: models.DateTimeField = models.DateTimeField()  # type: ignore[var-annotated]
    payload: models.JSONField = models.JSONField(default=dict)  # type: ignore[var-annotated]
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)  # type: ignore[var-annotated]
    started_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)  # type: ignore[var-annotated]
    completed_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)  # type: ignore[var-annotated]

    objects = TaskQuerySet.as_manager()  # type: ignore[assignment, misc, var-annotated]

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
        return (self.payload or {}).get('last_error')

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
            updated_payload['last_error'] = error_message[:500]  # Truncate to avoid huge payloads
            self.payload = updated_payload
        self.save(update_fields=["status"])
