# Lead serializers

from rest_framework import serializers
from openoutreach.crm.models import Lead, Deal


class LeadSerializer(serializers.ModelSerializer):
    """Serializer for Lead model."""
    
    deals = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    
    class Meta:  # type: ignore[misc]
        model = Lead
        fields = [
            'id', 'public_identifier', 'linkedin_url', 'urn', 'disqualified',
            'creation_date', 'update_date', 'deals'
        ]
        read_only_fields = ['creation_date', 'update_date']


class LeadCreateSerializer(serializers.Serializer):
    """Serializer for creating a lead."""
    
    public_identifier = serializers.CharField(max_length=200, required=True)
    linkedin_url = serializers.URLField(required=False, allow_blank=True)
    disqualified = serializers.BooleanField(required=False, default=False)


class DealSerializer(serializers.ModelSerializer):
    """Serializer for Deal model."""
    
    class Meta:  # type: ignore[misc]
        model = Deal
        fields = [
            'id', 'lead', 'campaign', 'state', 'outcome', 'reason',
            'connect_attempts', 'backoff_hours', 'next_check_pending_at',
            'profile_summary', 'chat_summary', 'creation_date', 'update_date'
        ]
        read_only_fields = ['creation_date', 'update_date']