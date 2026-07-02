# Campaign serializers

from rest_framework import serializers
from openoutreach.core.models import Campaign, CampaignTemplate
from openoutreach.crm.models import Deal, Lead, TrackedLink
from openoutreach.crm.models.deal import DealState
from openoutreach.linkedin.models import ActionLog
from django.utils import timezone
from datetime import timedelta


class TrackedLinkSerializer(serializers.ModelSerializer):
    """Serializer for TrackedLink model."""

    campaign = serializers.PrimaryKeyRelatedField(
        queryset=TrackedLink.objects.none(), required=False, allow_null=True
    )
    campaign_name = serializers.SerializerMethodField()
    total_clicks = serializers.IntegerField(read_only=True)

    class Meta:  # type: ignore[misc]
        model = TrackedLink
        fields = [
            "id",
            "campaign",
            "campaign_name",
            "original_url",
            "short_code",
            "is_active",
            "total_clicks",
            "unique_clicks",
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_term",
            "utm_content",
            "created_at",
            "last_clicked_at",
        ]
        read_only_fields = [
            "id",
            "short_code",
            "total_clicks",
            "unique_clicks",
            "created_at",
            "last_clicked_at",
        ]

    def get_campaign_name(self, obj):
        return obj.campaign.name if obj.campaign else None

    def get_fields(self):
        fields = super().get_fields()
        # Only include campaigns that the current user has access to
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            from openoutreach.core.models import Campaign

            campaigns = Campaign.objects.filter(users=request.user)
            fields["campaign"].queryset = campaigns  # type: ignore[assignment]
        return fields


class CampaignStatsSerializer(serializers.Serializer):
    """Serializer for computed campaign statistics."""

    def to_representation(self, instance):
        """Compute and return statistics for the campaign."""
        request = self.context.get("request") if self.context else None
        user = request.user if request and hasattr(request, "user") else None
        
        # Get deals for this campaign
        deals = instance.deals.all()

        # Count deals by state
        total_leads = deals.count()
        qualified = deals.filter(state=DealState.QUALIFIED).count()
        ready_to_connect = deals.filter(state=DealState.READY_TO_CONNECT).count()
        pending = deals.filter(state=DealState.PENDING).count()
        connected = deals.filter(state=DealState.CONNECTED).count()
        completed = deals.filter(state=DealState.COMPLETED).count()
        failed = deals.filter(state=DealState.FAILED).count()
        no_email = deals.filter(state=DealState.NO_EMAIL).count()

        # Count connection actions (send connect requests)
        connections_sent = ActionLog.objects.filter(
            campaign=instance,
            action_type=ActionLog.ActionType.CONNECT,
        ).count()

        # Count connections accepted (deals that became connected)
        connections_accepted = connected

        # Compute rates
        connection_accept_rate = (
            round((connections_accepted / connections_sent * 100), 2) if connections_sent > 0 else 0.0
        )

        # Count follow-up actions sent
        messages_sent = ActionLog.objects.filter(
            campaign=instance,
            action_type=ActionLog.ActionType.FOLLOW_UP,
        ).count()

        # Count responders (deals with at least one incoming message)
        messages_replied = deals.filter(messages__is_outgoing=False).distinct().count()

        # Response rate based on connections accepted
        response_rate = (
            round((messages_replied / connections_accepted * 100), 2) if connections_accepted > 0 else 0.0
        )

        # Lead stats
        leads = total_leads + ready_to_connect + pending

        return {
            "totalLeads": total_leads,
            "connected": connected,
            "messagesSent": messages_sent,
            "messagesReplied": messages_replied,
            "completed": completed,
            "qualified": qualified,
            "readyToConnect": ready_to_connect,
            "pending": pending,
            "failed": failed,
            "noEmail": no_email,
            "leads": leads,
            "connectionAcceptRate": connection_accept_rate,
            "responseRate": response_rate,
        }


class CampaignSerializer(serializers.ModelSerializer):
    """Serializer for Campaign model."""

    users = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    user_count = serializers.SerializerMethodField()
    deal_count = serializers.SerializerMethodField()
    active_deals = serializers.SerializerMethodField()
    completed_deals = serializers.SerializerMethodField()
    failed_deals = serializers.SerializerMethodField()
    ghost_mode_enabled = serializers.BooleanField()
    # Sync status with is_paused for frontend compatibility
    is_paused = serializers.BooleanField(source="is_paused", read_only=False)

    # Links many-to-many field (read-only)
    links = serializers.SerializerMethodField()
    
    # Computed statistics
    stats = serializers.SerializerMethodField()

    class Meta:  # type: ignore[misc]
        model = Campaign
        fields = [
            "id",
            "name",
            "description",
            "product_docs",
            "campaign_objective",
            "booking_link",
            "is_freemium",
            "ghost_mode_enabled",
            "action_fraction",
            "seed_public_ids",
            "velocity",
            "cooldown_minutes",
            "is_paused",
            "model_blob",
            "users",
            "user_count",
            "deal_count",
            "active_deals",
            "completed_deals",
            "failed_deals",
            "links",
            "stats",
            "created_at",
            "updated_at",
            "status",
        ]
        read_only_fields = ["created_at", "updated_at", "status", "links"]

    def get_user_count(self, obj):
        return obj.users.count()

    def get_deal_count(self, obj):
        return obj.deals.count()

    def get_active_deals(self, obj):
        return obj.deals.filter(
            state__in=["QUALIFIED", "READY_TO_CONNECT", "PENDING", "CONNECTED"]
        ).count()

    def get_completed_deals(self, obj):
        return obj.deals.filter(state="COMPLETED").count()

    def get_failed_deals(self, obj):
        return obj.deals.filter(state="FAILED").count()

    def get_links(self, obj):
        """Get links associated with this campaign."""
        links = obj.tracked_links.all()
        return TrackedLinkSerializer(links, many=True, context=self.context).data

    def get_stats(self, obj):
        """Compute and return statistics for the campaign."""
        # Get deals for this campaign
        deals = obj.deals.all()
        
        # Count deals by state
        total_leads = deals.count()
        qualified = deals.filter(state=DealState.QUALIFIED).count()
        ready_to_connect = deals.filter(state=DealState.READY_TO_CONNECT).count()
        pending = deals.filter(state=DealState.PENDING).count()
        connected = deals.filter(state=DealState.CONNECTED).count()
        completed = deals.filter(state=DealState.COMPLETED).count()
        failed = deals.filter(state=DealState.FAILED).count()
        no_email = deals.filter(state=DealState.NO_EMAIL).count()

        # Count connection actions (send connect requests)
        connections_sent = ActionLog.objects.filter(
            campaign=obj,
            action_type=ActionLog.ActionType.CONNECT,
        ).count()

        # Count connections accepted (deals that became connected)
        connections_accepted = connected

        # Compute rates
        connection_accept_rate = (
            round((connections_accepted / connections_sent * 100), 2) if connections_sent > 0 else 0.0
        )

        # Count follow-up actions sent
        messages_sent = ActionLog.objects.filter(
            campaign=obj,
            action_type=ActionLog.ActionType.FOLLOW_UP,
        ).count()

        # Count responders (deals with at least one incoming message)
        messages_replied = deals.filter(messages__is_outgoing=False).distinct().count()

        # Response rate based on connections accepted
        response_rate = (
            round((messages_replied / connections_accepted * 100), 2) if connections_accepted > 0 else 0.0
        )

        # Lead stats
        leads = total_leads + ready_to_connect + pending

        return {
            "totalLeads": total_leads,
            "connected": connected,
            "messagesSent": messages_sent,
            "messagesReplied": messages_replied,
            "completed": completed,
            "qualified": qualified,
            "readyToConnect": ready_to_connect,
            "pending": pending,
            "failed": failed,
            "noEmail": no_email,
            "leads": leads,
            "connectionAcceptRate": connection_accept_rate,
            "responseRate": response_rate,
        }


class CampaignCreateSerializer(serializers.Serializer):
    """Serializer for creating a campaign."""

    name = serializers.CharField(max_length=200, required=True)
    description = serializers.CharField(required=False, allow_blank=True)
    product_docs = serializers.CharField(required=False, allow_blank=True)
    campaign_objective = serializers.CharField(required=False, allow_blank=True)
    booking_link = serializers.URLField(required=False, allow_blank=True)
    is_freemium = serializers.BooleanField(required=False, default=False)
    ghost_mode_enabled = serializers.BooleanField(required=False, default=False)
    action_fraction = serializers.FloatField(
        required=False, default=0.2, min_value=0, max_value=1
    )
    velocity = serializers.IntegerField(required=False, default=20, min_value=1)
    cooldown_minutes = serializers.IntegerField(required=False, default=0, min_value=0)
    is_paused = serializers.BooleanField(required=False, default=False)
    status = serializers.CharField(required=False, default="active")


class CampaignUpdateSerializer(serializers.Serializer):
    """Serializer for updating a campaign. Uses partial validation to avoid
    requiring all fields on update."""

    name = serializers.CharField(max_length=200, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    product_docs = serializers.CharField(required=False, allow_blank=True)
    campaign_objective = serializers.CharField(required=False, allow_blank=True)
    booking_link = serializers.URLField(required=False, allow_blank=True)
    is_freemium = serializers.BooleanField(required=False)
    ghost_mode_enabled = serializers.BooleanField(required=False)
    action_fraction = serializers.FloatField(required=False, min_value=0, max_value=1)
    velocity = serializers.IntegerField(required=False, min_value=1)
    cooldown_minutes = serializers.IntegerField(required=False, min_value=0)
    is_paused = serializers.BooleanField(required=False)
    model_blob = serializers.JSONField(required=False)
    status = serializers.CharField(required=False)

    VALID_STATUSES = ["active", "paused", "draft"]

    def validate_status(self, value: str) -> str:
        """Validate status is one of the allowed values."""
        if value is not None and value.lower() not in self.VALID_STATUSES:
            raise serializers.ValidationError(
                f"Invalid status. Must be one of: {', '.join(self.VALID_STATUSES)}"
            )
        return value.lower() if value else value


class CampaignTemplateSerializer(serializers.ModelSerializer):
    """Serializer for CampaignTemplate model."""

    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    created_by_username = serializers.SerializerMethodField()

    class Meta:  # type: ignore[misc]
        model = CampaignTemplate
        fields = [
            "id",
            "name",
            "description",
            "campaign_objective",
            "ghost_mode_enabled",
            "velocity",
            "cooldown_minutes",
            "is_public",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "created_by",
            "created_by_username",
        ]

    def get_created_by_username(self, obj):
        return obj.created_by.username if obj.created_by else None


class CampaignTemplateCreateSerializer(serializers.Serializer):
    """Serializer for creating/updating a campaign template."""

    name = serializers.CharField(max_length=200, required=True)
    description = serializers.CharField(required=False, allow_blank=True)
    campaign_objective = serializers.CharField(required=False, allow_blank=True)
    ghost_mode_enabled = serializers.BooleanField(required=False, default=False)
    velocity = serializers.IntegerField(
        required=False, default=20, min_value=1, max_value=100
    )
    cooldown_minutes = serializers.IntegerField(
        required=False, default=0, min_value=0, max_value=1440
    )
    is_public = serializers.BooleanField(required=False, default=False)