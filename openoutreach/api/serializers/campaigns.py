# Campaign serializers

from rest_framework import serializers
from openoutreach.core.models import Campaign, CampaignTemplate
from openoutreach.crm.models import Deal, Lead, TrackedLink
from openoutreach.linkedin.models import ActionLog


class TrackedLinkSerializer(serializers.ModelSerializer):
    """Serializer for TrackedLink model."""
    
    campaign = serializers.PrimaryKeyRelatedField(queryset=TrackedLink.objects.none(), required=False, allow_null=True)
    campaign_name = serializers.SerializerMethodField()
    total_clicks = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = TrackedLink
        fields = [
            'id', 'campaign', 'campaign_name', 'original_url', 'short_code',
            'is_active', 'total_clicks', 'unique_clicks',
            'utm_source', 'utm_medium', 'utm_campaign',
            'utm_term', 'utm_content',
            'created_at', 'last_clicked_at'
        ]
        read_only_fields = ['id', 'short_code', 'total_clicks', 'unique_clicks', 'created_at', 'last_clicked_at']
    
    def get_campaign_name(self, obj):
        return obj.campaign.name if obj.campaign else None
    
    def get_fields(self):
        fields = super().get_fields()
        # Only include campaigns that the current user has access to
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            from openoutreach.core.models import Campaign
            campaigns = Campaign.objects.filter(users=request.user)
            fields['campaign'].queryset = campaigns
        return fields


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
    is_paused = serializers.BooleanField(source='is_paused', read_only=False)
    
    # Links many-to-many field (read-only)
    links = serializers.SerializerMethodField()
    
    class Meta:  # type: ignore[misc]
        model = Campaign
        fields = [
            'id', 'name', 'description', 'product_docs', 'campaign_objective',
            'booking_link', 'is_freemium', 'ghost_mode_enabled', 'action_fraction', 'seed_public_ids',
            'velocity', 'cooldown_minutes', 'is_paused', 'model_blob',
            'users', 'user_count', 'deal_count', 'active_deals', 
            'completed_deals', 'failed_deals', 'links',
            'created_at', 'updated_at', 'status'
        ]
        read_only_fields = ['created_at', 'updated_at', 'status', 'links']
    
    def validate_is_paused(self, value: bool) -> bool:
        """Sync is_paused with status field for consistency."""
        # When is_paused changes, update status accordingly
        if 'is_paused' in self.initial_data and self.instance is not None:
            # If is_paused becomes True, status should be 'paused'
            if value and self.instance.status != 'paused':
                self.instance.status = 'paused'
                self.instance.save(update_fields=['status'])
            # If is_paused becomes False, status should be 'active' (only if it was 'paused')
            elif not value and self.instance.status == 'paused':
                self.instance.status = 'active'
                self.instance.save(update_fields=['status'])
        return value
    
    def validate_status(self, value: str) -> str:
        """Sync status with is_paused for consistency."""
        if 'status' in self.initial_data and self.instance is not None:
            # If status becomes 'paused', is_paused should be True
            if value == 'paused' and not self.instance.is_paused:
                self.instance.is_paused = True
                self.instance.save(update_fields=['is_paused'])
            # If status becomes 'active', is_paused should be False
            elif value == 'active' and self.instance.is_paused:
                self.instance.is_paused = False
                self.instance.save(update_fields=['is_paused'])
        return value
    
    def get_user_count(self, obj):
        return obj.users.count()
    
    def get_deal_count(self, obj):
        return obj.deals.count()
    
    def get_active_deals(self, obj):
        return obj.deals.filter(state__in=['QUALIFIED', 'READY_TO_CONNECT', 'PENDING', 'CONNECTED']).count()
    
    def get_completed_deals(self, obj):
        return obj.deals.filter(state='COMPLETED').count()
    
    def get_failed_deals(self, obj):
        return obj.deals.filter(state='FAILED').count()
    
    def get_links(self, obj):
        """Get links associated with this campaign."""
        links = obj.tracked_links.all()
        return TrackedLinkSerializer(links, many=True, context=self.context).data


class CampaignCreateSerializer(serializers.Serializer):
    """Serializer for creating a campaign."""
    
    name = serializers.CharField(max_length=200, required=True)
    description = serializers.CharField(required=False, allow_blank=True)
    product_docs = serializers.CharField(required=False, allow_blank=True)
    campaign_objective = serializers.CharField(required=False, allow_blank=True)
    booking_link = serializers.URLField(required=False, allow_blank=True)
    is_freemium = serializers.BooleanField(required=False, default=False)
    ghost_mode_enabled = serializers.BooleanField(required=False, default=False)
    action_fraction = serializers.FloatField(required=False, default=0.2, min_value=0, max_value=1)
    velocity = serializers.IntegerField(required=False, default=20, min_value=1)
    cooldown_minutes = serializers.IntegerField(required=False, default=0, min_value=0)
    is_paused = serializers.BooleanField(required=False, default=False)
    status = serializers.CharField(required=False, default='active')


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
    
    VALID_STATUSES = ['active', 'paused', 'draft']
    
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
    
    class Meta:
        model = CampaignTemplate
        fields = [
            'id', 'name', 'description', 'campaign_objective',
            'ghost_mode_enabled', 'velocity', 'cooldown_minutes',
            'is_public', 'created_by', 'created_by_username',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by', 'created_by_username']
    
    def get_created_by_username(self, obj):
        return obj.created_by.username if obj.created_by else None


class CampaignTemplateCreateSerializer(serializers.Serializer):
    """Serializer for creating/updating a campaign template."""
    
    name = serializers.CharField(max_length=200, required=True)
    description = serializers.CharField(required=False, allow_blank=True)
    campaign_objective = serializers.CharField(required=False, allow_blank=True)
    ghost_mode_enabled = serializers.BooleanField(required=False, default=False)
    velocity = serializers.IntegerField(required=False, default=20, min_value=1, max_value=100)
    cooldown_minutes = serializers.IntegerField(required=False, default=0, min_value=0, max_value=1440)
    is_public = serializers.BooleanField(required=False, default=False)
