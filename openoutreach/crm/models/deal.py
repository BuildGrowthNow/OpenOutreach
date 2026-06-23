from __future__ import annotations
# Deal model for CRM

from typing import TYPE_CHECKING

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from openoutreach.core.models import Campaign
    from openoutreach.chat.models import ChatMessage
    from . import Lead


class DealState(models.TextChoices):
    """OpenOutreach-owned funnel state for a Deal.

    OpenOutreach owns these values, not linkedin_cli. The library's connect/status
    verbs only *observe* three of them off the LinkedIn UI — QUALIFIED, PENDING,
    CONNECTED — and hand them back as plain strings over the CLI boundary; every
    other state is written only here: READY_TO_CONNECT (passed the GP threshold),
    COMPLETED/FAILED (outcome), and NO_EMAIL (enrichment found no address — the
    deal is held out of the connect pool without advancing the LinkedIn state
    machine). String values match the library's UI states so lifting a returned
    string into this enum is a plain ``DealState(value)`` lookup at the boundary.
    """
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


class Deal(models.Model):
    class Meta:
        verbose_name = _("Deal")
        verbose_name_plural = _("Deals")
        constraints = [
            models.UniqueConstraint(fields=["lead", "campaign"], name="unique_deal_per_campaign"),
        ]

    lead: models.ForeignKey = models.ForeignKey("Lead", on_delete=models.CASCADE)  # type: ignore[var-annotated,assignment]
    campaign: models.ForeignKey = models.ForeignKey(  # type: ignore[var-annotated,assignment]
        "core.Campaign", on_delete=models.CASCADE, related_name="deals",
    )
    state: models.CharField = models.CharField(  # type: ignore[var-annotated]
        max_length=20,
        choices=DealState.choices,
        default=DealState.QUALIFIED,
    )
    outcome: models.CharField = models.CharField(  # type: ignore[var-annotated]
        max_length=20,
        choices=Outcome.choices,
        blank=True,
        default="",
    )
    reason: models.TextField = models.TextField(blank=True, default="")  # type: ignore[var-annotated]
    connect_attempts: models.IntegerField = models.IntegerField(default=0)  # type: ignore[var-annotated]
    backoff_hours: models.IntegerField = models.IntegerField(default=0)  # type: ignore[var-annotated]
    next_check_pending_at: models.DateTimeField = models.DateTimeField(null=True, blank=True, db_index=True)  # type: ignore[var-annotated]
    profile_summary: models.JSONField = models.JSONField(null=True, blank=True, default=None)  # type: ignore[var-annotated]
    chat_summary: models.JSONField = models.JSONField(null=True, blank=True, default=None)  # type: ignore[var-annotated]
    creation_date: models.DateTimeField = models.DateTimeField(default=timezone.now)  # type: ignore[var-annotated]
    update_date: models.DateTimeField = models.DateTimeField(auto_now=True)  # type: ignore[var-annotated]

    # Type hints for Django's automatic fields and reverse relations
    id: models.AutoField  # type: ignore[assignment]
    lead_id: int  # type: ignore[assignment]
    campaign_id: int  # type: ignore[assignment]
    messages: models.Manager  # type: ignore[assignment]
    state_machines: models.Manager  # type: ignore[assignment]
    
    # Email tracking - used for mailbox pacing (per-box daily limits)
    mailbox: models.ForeignKey = models.ForeignKey(  # type: ignore[var-annotated,assignment]
        "emails.Mailbox",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deals',
    )
    email_sent_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)  # type: ignore[var-annotated]

    def __str__(self) -> str:
        lead_id: int = getattr(self, 'lead_id', 0)  # type: ignore[var-annotated]
        lead_str = str(self.lead) if lead_id else "?"
        return f"{lead_str} [{self.state}]"