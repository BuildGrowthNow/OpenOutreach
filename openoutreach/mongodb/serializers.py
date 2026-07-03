from datetime import datetime
from rest_framework import serializers
from .models import UserProfile


class UserProfileSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    user_id = serializers.CharField(max_length=100)
    email = serializers.EmailField(required=False, allow_blank=True)
    first_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    company = serializers.CharField(max_length=200, required=False, allow_blank=True)
    position = serializers.CharField(max_length=200, required=False, allow_blank=True)
    timezone = serializers.CharField(max_length=50, required=False, allow_blank=True)
    notification_preferences = serializers.DictField(child=serializers.BooleanField(), required=False)
    ui_preferences = serializers.DictField(required=False)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    def create(self, validated_data):
        """Create a new UserProfile in MongoDB."""
        profile = UserProfile(**validated_data)
        profile.save()
        return profile

    def update(self, instance, validated_data):
        """Update an existing UserProfile in MongoDB."""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.updated_at = datetime.utcnow()
        instance.save()
        return instance
