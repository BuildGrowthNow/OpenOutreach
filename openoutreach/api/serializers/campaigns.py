# Campaign serializers

from rest_framework import serializers
from openoutreach.core.models import Campaign
from openoutreach.crm.models import Deal, Lead
from openoutreach.linkedin.models import ActionLog


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
    
    class Meta:  # type: ignore[misc]
        model = Campaign
        fields = [
            'id', 'name', 'description', 'product_docs', 'campaign_objective',
            'booking_link', 'is_freemium', 'ghost_mode_enabled', 'action_fraction', 'seed_public_ids',
            'velocity', 'cooldown_minutes', 'is_paused', 'model_blob',
            'users', 'user_count', 'deal_count', 'active_deals', 
            'completed_deals', 'failed_deals', 'created_at', 'updated_at', 'status'
        ]
        read_only_fields = ['created_at', 'updated_at', 'status']
    
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
    """Serializer for updating a campaign."""
    
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
