# openoutreach/linkedin/models/state_machine.py
"""State Machine models for Campaign workflow automation."""

from __future__ import annotations

from django.db import models
from django.utils import timezone

from openoutreach.core.models import Campaign
from openoutreach.crm.models import Deal


class CampaignStateGraph(models.Model):
    """Represents a campaign's workflow state machine."""

    # Type hints for Django's automatic fields
    id: models.AutoField  # type: ignore[assignment]

    campaign = models.OneToOneField(
        Campaign, on_delete=models.CASCADE, related_name="state_graph"
    )

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    # JSON representation of the graph
    graph_data = models.JSONField(default=dict)

    # Validation status
    is_valid = models.BooleanField(default=False)
    validation_errors = models.JSONField(default=list)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Type hints for reverse relations (from other models)
    nodes: models.Manager  # type: ignore[assignment]
    transitions: models.Manager  # type: ignore[assignment]

    class Meta:
        verbose_name_plural = "Campaign state graphs"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.campaign.name}: {self.name}"


class StateNode(models.Model):
    """Represents a node in the state machine."""

    id: int  # auto-generated primary key

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

    name = models.CharField(max_length=100)
    node_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    state_graph = models.ForeignKey(
        CampaignStateGraph, on_delete=models.CASCADE, related_name="nodes"
    )

    # Configuration
    config = models.JSONField(default=dict)  # Node-specific settings

    # Positioning (for visual editor)
    x = models.FloatField(default=0)
    y = models.FloatField(default=0)

    # Metadata
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["state_graph", "x", "y"]
        verbose_name = "State node"
        verbose_name_plural = "State nodes"

    def __str__(self):
        return f"{self.name} ({self.node_type})"


class StateTransition(models.Model):
    """Represents a transition between nodes."""

    id: int  # auto-generated primary key

    source_node = models.ForeignKey(
        StateNode, on_delete=models.CASCADE, related_name="outgoing_transitions"
    )
    target_node = models.ForeignKey(
        StateNode, on_delete=models.CASCADE, related_name="incoming_transitions"
    )

    state_graph = models.ForeignKey(
        CampaignStateGraph, on_delete=models.CASCADE, related_name="transitions"
    )

    # Condition
    condition_type = models.CharField(max_length=50, default="always")
    condition_config = models.JSONField(default=dict)

    # Label (for display)
    label = models.CharField(max_length=100, blank=True)

    # Order (for multiple outgoing transitions)
    order = models.PositiveIntegerField(default=0)

    # Enabled
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["state_graph", "order"]
        verbose_name = "State transition"
        verbose_name_plural = "State transitions"

    def __str__(self):
        return f"{self.source_node.name} → {self.target_node.name}"


class CampaignState(models.Model):
    """Tracks the current state of a campaign follow-up."""

    id: int  # auto-generated primary key

    # Reverse relation
    execution_logs: models.Manager  # type: ignore[assignment]

    STATUS_ACTIVE = "active"
    STATUS_COMPLETED = "completed"
    STATUS_DROPPED = "dropped"
    STATUS_ERROR = "error"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_DROPPED, "Dropped"),
        (STATUS_ERROR, "Error"),
    ]

    deal = models.ForeignKey(
        Deal, on_delete=models.CASCADE, related_name="state_machines"
    )
    state_graph = models.ForeignKey(CampaignStateGraph, on_delete=models.CASCADE)

    current_node = models.ForeignKey(
        StateNode, on_delete=models.SET_NULL, null=True, blank=True
    )
    previous_nodes = models.JSONField(default=list)  # History of visited nodes

    # Execution state
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE
    )
    error_message = models.TextField(blank=True)

    # Wait tracking
    wait_until = models.DateTimeField(null=True, blank=True)
    wait_reason = models.CharField(max_length=100, blank=True)

    # Metadata
    metadata = models.JSONField(default=dict)

    # Timings
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "Campaign states"
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["deal", "status"]),
            models.Index(fields=["state_graph", "status"]),
        ]

    def __str__(self):
        return f"{self.deal} - {self.status}"


class CampaignExecutionLog(models.Model):
    """Logs each step of state machine execution."""

    id: int  # auto-generated primary key

    state_machine = models.ForeignKey(
        CampaignState, on_delete=models.CASCADE, related_name="execution_logs"
    )

    node = models.ForeignKey(
        StateNode, on_delete=models.SET_NULL, null=True, blank=True
    )
    transition = models.ForeignKey(
        StateTransition, on_delete=models.SET_NULL, null=True, blank=True
    )

    action = models.CharField(max_length=100)
    result = models.JSONField(default=dict)
    error = models.TextField(blank=True)

    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name_plural = "Campaign execution logs"
        indexes = [
            models.Index(fields=["state_machine", "timestamp"]),
        ]

    def __str__(self):
        return f"{self.action} at {self.timestamp}"
