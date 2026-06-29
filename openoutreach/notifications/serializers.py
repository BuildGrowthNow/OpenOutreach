from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for Notification model."""

    recipient_username = serializers.CharField(source="recipient.username", read_only=True)
    campaign_name = serializers.CharField(source="campaign.name", read_only=True, allow_null=True)
    deal_name = serializers.CharField(source="deal.lead.name", read_only=True, allow_null=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "recipient",
            "recipient_username",
            "notification_type",
            "title",
            "message",
            "campaign",
            "campaign_name",
            "deal",
            "deal_name",
            "is_read",
            "read_at",
            "data",
            "created_at",
        ]
        read_only_fields = ["id", "is_read", "read_at", "created_at", "recipient"]

    def create(self, validated_data):
        """Create notification with current user as recipient."""
        validated_data["recipient"] = self.context["request"].user
        return super().create(validated_data)


class NotificationSummarySerializer(serializers.Serializer):
    """Serializer for notification summary (unread count)."""

    unread_count = serializers.IntegerField()
    recent_notifications = NotificationSerializer(many=True, read_only=True)