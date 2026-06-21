# Settings serializers

from rest_framework import serializers
from django.conf import settings


class RateLimitsSerializer(serializers.Serializer):
    """Serializer for rate limit settings."""
    
    # Daily limits
    daily_connection_limit = serializers.IntegerField(default=50, min_value=1, max_value=1000)
    daily_follow_up_limit = serializers.IntegerField(default=20, min_value=1, max_value=500)
    
    # Global limits
    global_rate_limit_seconds = serializers.IntegerField(default=60, min_value=10, max_value=3600)
    global_rate_limit_requests = serializers.IntegerField(default=100, min_value=10, max_value=1000)
    
    # Safety limits
    safety_connection_limit = serializers.IntegerField(default=30, min_value=1, max_value=500)
    safety_follow_up_limit = serializers.IntegerField(default=15, min_value=1, max_value=200)
    
    # Cooldown settings
    min_cooldown_seconds = serializers.IntegerField(default=60, min_value=10, max_value=3600)
    max_cooldown_seconds = serializers.IntegerField(default=300, min_value=60, max_value=3600)


class SystemSettingsSerializer(serializers.Serializer):
    """Serializer for system-wide settings."""
    
    # UI Settings
    default_theme = serializers.ChoiceField(
        choices=['light', 'dark', 'system'],
        default='dark'
    )
    default_page_size = serializers.IntegerField(default=10, min_value=5, max_value=100)
    
    # API Settings
    api_rate_limit = serializers.IntegerField(default=100, min_value=10, max_value=1000)
    api_rate_window_seconds = serializers.IntegerField(default=3600, min_value=300, max_value=86400)
    
    # Email Settings
    smtp_host = serializers.CharField(required=False, allow_blank=True)
    smtp_port = serializers.IntegerField(required=False, default=587, min_value=1, max_value=65535)
    smtp_use_tls = serializers.BooleanField(default=True)
    
    # LinkedIn Settings
    linkedin_timeout_seconds = serializers.IntegerField(default=30, min_value=5, max_value=120)
    linkedin_retry_count = serializers.IntegerField(default=3, min_value=1, max_value=10)
    
    # Storage Settings
    max_file_size_mb = serializers.IntegerField(default=10, min_value=1, max_value=1000)
    retention_days = serializers.IntegerField(default=90, min_value=7, max_value=3650)