# openoutreach/linkedin/admin.py
from django.contrib import admin

from openoutreach.linkedin.models import ActionLog, LinkedInProfile, SearchKeyword
from openoutreach.linkedin.models.ghost_mode import GhostCampaign, GhostSimulationLog, GhostTestScenario


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
