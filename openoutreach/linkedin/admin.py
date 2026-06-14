# openoutreach/linkedin/admin.py
from django.contrib import admin
from django.db import models

from openoutreach.crm.models import LeadPersona
from openoutreach.linkedin.models import LinkedInProfile, SearchKeyword
from openoutreach.linkedin.models.ghost_mode import GhostCampaign, GhostSimulationLog, GhostTestScenario
from openoutreach.linkedin.models.health import CampaignHealthMetric, HealthAlert, RecoveryAction
from openoutreach.linkedin.models.state_machine import (
    CampaignStateGraph,
    StateNode,
    StateTransition,
    CampaignState,
    CampaignExecutionLog,
)


@admin.register(LinkedInProfile)
class LinkedInProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "linkedin_username", "active", "legal_accepted")
    list_filter = ("active",)
    raw_id_fields = ("user", "self_lead")


@admin.register(SearchKeyword)
class SearchKeywordAdmin(admin.ModelAdmin):
    list_display = ("keyword", "campaign", "used", "used_at")
    list_filter = ("used", "campaign")
    raw_id_fields = ("campaign",)


@admin.register(GhostCampaign)
class GhostCampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "campaign", "is_active", "mode_type")
    list_filter = ("is_active", "mode_type", "campaign")
    raw_id_fields = ("campaign",)
    readonly_fields = (
        "created_at", "updated_at",
        "leads_processed", "connections_simulated",
        "messages_simulated", "conversions_simulated",
        "avg_rating", "avg_score",
    )


@admin.register(GhostSimulationLog)
class GhostSimulationLogAdmin(admin.ModelAdmin):
    list_display = (
        "action_type", "target_name", "ghost_campaign",
        "rating", "score", "started_at",
    )
    list_filter = (
        "action_type", "ghost_campaign",
    )
    raw_id_fields = ("ghost_campaign",)
    readonly_fields = (
        "started_at", "completed_at", "created_at",
        "target_name", "target_url", "result_data",
    )
    date_hierarchy = "started_at"


@admin.register(GhostTestScenario)
class GhostTestScenarioAdmin(admin.ModelAdmin):
    list_display = ("name", "created_by", "is_public", "runs_count", "avg_success_rate")
    list_filter = ("is_public",)
    raw_id_fields = ("created_by",)
    readonly_fields = ("created_at", "updated_at", "runs_count", "avg_success_rate")


@admin.register(CampaignHealthMetric)
class CampaignHealthMetricAdmin(admin.ModelAdmin):
    list_display = ("campaign", "timestamp", "connections_sent", "connection_accept_rate", "detectability_score")
    list_filter = ("campaign", "timestamp")
    readonly_fields = ("created_at",)
    date_hierarchy = "timestamp"


@admin.register(HealthAlert)
class HealthAlertAdmin(admin.ModelAdmin):
    list_display = ("message", "campaign", "alert_type", "severity", "is_resolved", "created_at")
    list_filter = ("alert_type", "severity", "is_resolved", "campaign")
    readonly_fields = ("created_at", "updated_at", "resolved_at")
    date_hierarchy = "created_at"


@admin.register(RecoveryAction)
class RecoveryActionAdmin(admin.ModelAdmin):
    list_display = ("campaign", "action_type", "executed_at", "reason")
    list_filter = ("action_type", "campaign")
    readonly_fields = ("executed_at",)
    date_hierarchy = "executed_at"


@admin.register(CampaignStateGraph)
class CampaignStateGraphAdmin(admin.ModelAdmin):
    list_display = ("campaign", "name", "is_active", "is_valid", "created_at")
    list_filter = ("is_active", "is_valid")
    readonly_fields = ("graph_data", "validation_errors", "created_at", "updated_at")
    list_select_related = ("campaign",)
    
    def save_model(self, request, obj, form, change):
        # Validate the graph before saving
        from openoutreach.linkedin.services.state_machine import StateMachineEngine
        is_valid, errors = StateMachineEngine(obj).validate_graph()
        obj.is_valid = is_valid
        obj.validation_errors = errors
        super().save_model(request, obj, form, change)


@admin.register(StateNode)
class StateNodeAdmin(admin.ModelAdmin):
    list_display = ("name", "node_type", "state_graph", "is_active", "x", "y")
    list_filter = ("node_type", "is_active", "state_graph")
    raw_id_fields = ("state_graph",)
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("state_graph",)


@admin.register(StateTransition)
class StateTransitionAdmin(admin.ModelAdmin):
    list_display = ("source_node", "target_node", "state_graph", "condition_type", "label", "is_active", "order")
    list_filter = ("condition_type", "is_active", "state_graph")
    raw_id_fields = ("source_node", "target_node", "state_graph")
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("source_node", "target_node", "state_graph")


@admin.register(CampaignState)
class CampaignStateAdmin(admin.ModelAdmin):
    list_display = ("deal", "state_graph", "current_node", "status", "started_at", "completed_at")
    list_filter = ("status", "state_graph")
    raw_id_fields = ("deal", "state_graph", "current_node")
    readonly_fields = ("previous_nodes", "error_message", "wait_until", "metadata", "started_at", "completed_at")
    list_select_related = ("deal", "state_graph", "current_node")
    date_hierarchy = "started_at"


@admin.register(CampaignExecutionLog)
class CampaignExecutionLogAdmin(admin.ModelAdmin):
    list_display = ("state_machine", "node", "action", "timestamp")
    list_filter = ("action", "state_machine", "node")
    raw_id_fields = ("state_machine", "node", "transition")
    readonly_fields = ("result", "error", "timestamp")
    list_select_related = ("state_machine", "node", "transition")
    date_hierarchy = "timestamp"


@admin.register(LeadPersona)
class LeadPersonaAdmin(admin.ModelAdmin):
    list_display = ("lead", "campaign", "confidence_score", "version", "generated_at", "is_high_confidence")
    list_filter = ("campaign", "generated_at", "version")
    search_fields = ("lead__public_identifier", "lead__linkedin_url")
    readonly_fields = ("generated_at", "last_updated", "version")
    raw_id_fields = ("lead", "campaign")
    
    fields = [
        'lead', 'campaign', 'version', 'confidence_score',
        'pain_points', 'goals', 'buy_signals', 'recommendations',
        'messaging_preferences', 'generated_at', 'last_updated'
    ]

    @admin.display(description="High Confidence")
    def is_high_confidence(self, obj):
        return obj.is_high_confidence
    is_high_confidence.boolean = True
    is_high_confidence.short_description = "High Confidence"
