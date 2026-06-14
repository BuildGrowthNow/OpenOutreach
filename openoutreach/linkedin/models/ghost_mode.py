# openoutreach/linkedin/models/ghost_mode.py
"""Ghost Mode campaign models for safe testing without sending real actions."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

from openoutreach.core.models import Campaign

User = get_user_model()


class GhostCampaign(models.Model):
    """A campaign running in ghost mode for safe testing."""

    class ModeType(models.TextChoices):
        SIMULATION = "simulation", "Simulation only"
        VALIDATION = "validation", "Validation with warnings"
        DRY_RUN = "dry_run", "Dry run with all checks"

    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name="ghost_campaigns",
    )

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    # Mode settings
    is_active = models.BooleanField(default=True)
    mode_type = models.CharField(
        max_length=20,
        choices=ModeType.choices,
        default=ModeType.SIMULATION,
    )

    # What to test
    test_seed_leads = models.TextField(
        blank=True,
        help_text="Comma-separated LinkedIn URLs to test",
    )
    test_keywords = models.TextField(
        blank=True,
        help_text="Keywords to search for",
    )

    # Schedule
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)

    # Results tracking
    leads_processed = models.PositiveIntegerField(default=0)
    connections_simulated = models.PositiveIntegerField(default=0)
    messages_simulated = models.PositiveIntegerField(default=0)
    conversions_simulated = models.PositiveIntegerField(default=0)

    # Quality metrics
    avg_rating = models.FloatField(default=0.0)
    avg_score = models.FloatField(default=0.0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Ghost campaigns"

    def __str__(self):
        return f"{self.name} (Ghost Mode)"


class GhostSimulationLog(models.Model):
    """Logs a ghost mode simulation run."""

    class ActionType(models.TextChoices):
        SEARCH = "search", "Search for leads"
        QUALIFY = "qualify", "Qualify lead"
        CONNECT = "connect", "Send connection"
        MESSAGE = "message", "Send message"
        FOLLOW_UP = "follow_up", "Follow up message"
        CONVERSION = "conversion", "Conversion tracked"

    ghost_campaign = models.ForeignKey(
        GhostCampaign,
        on_delete=models.CASCADE,
        related_name="logs",
    )

    # Execution data
    action_type = models.CharField(
        max_length=20,
        choices=ActionType.choices,
    )
    target_url = models.URLField(blank=True)
    target_name = models.CharField(max_length=100, blank=True)

    # Results
    result_data = models.JSONField(default=dict)
    rating = models.FloatField(null=True, blank=True)
    score = models.FloatField(null=True, blank=True)

    # Timing
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField()

    # Simulation metadata
    simulated_action = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.action_type} for {self.target_name}"


class GhostTestScenario(models.Model):
    """Reusable test scenarios for ghost mode."""

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    # Scenario definition
    test_cases = models.JSONField(default=dict)  # Array of test cases

    # Metadata
    is_public = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    # Stats
    runs_count = models.PositiveIntegerField(default=0)
    avg_success_rate = models.FloatField(default=0.0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name