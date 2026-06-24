# Settings API Views

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from openoutreach.core.models import SiteConfig


class SettingsView(APIView):
    """
    API view for managing system settings.
    
    GET /api/settings - Get all system settings
    PATCH /api/settings - Update system settings
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get all system settings."""
        config = SiteConfig.load()
        
        return Response({
            'llm': {
                'provider': config.llm_provider,
                'model': config.ai_model,
                'api_base': config.llm_api_base,
            },
            'rate_limits': {
                'daily_connection_limit': config.daily_connection_limit,
                'daily_follow_up_limit': config.daily_follow_up_limit,
                'velocity': config.velocity,
                'cooldown_minutes': config.cooldown_minutes,
            },
            'linkedin_profile': {
                'username': config.linkedin_username,
                'campaign': config.linkedin_campaign,
            },
        })
    
    def patch(self, request):
        """Update system settings."""
        config = SiteConfig.load()
        
        # Get data from request
        data = request.data
        
        # Update LLM config if provided
        llm_config = data.get('llm', {})
        if 'provider' in llm_config:
            config.llm_provider = llm_config['provider']
        if 'model' in llm_config:
            config.ai_model = llm_config['model']
        if 'api_base' in llm_config:
            config.llm_api_base = llm_config['api_base']
        
        # Update LinkedIn profile if provided
        linkedin_profile = data.get('linkedin_profile', {})
        if 'username' in linkedin_profile:
            config.linkedin_username = linkedin_profile['username']
        if 'campaign' in linkedin_profile:
            config.linkedin_campaign = linkedin_profile['campaign']
        
        # Update rate limits if provided
        rate_limits = data.get('rate_limits', {})
        if 'daily_connection_limit' in rate_limits:
            config.daily_connection_limit = rate_limits['daily_connection_limit']
        if 'daily_follow_up_limit' in rate_limits:
            config.daily_follow_up_limit = rate_limits['daily_follow_up_limit']
        if 'velocity' in rate_limits:
            config.velocity = rate_limits['velocity']
        if 'cooldown_minutes' in rate_limits:
            config.cooldown_minutes = rate_limits['cooldown_minutes']
        
        config.save()
        
        return Response({
            'llm': {
                'provider': config.llm_provider,
                'model': config.ai_model,
                'api_base': config.llm_api_base,
            },
            'rate_limits': {
                'daily_connection_limit': config.daily_connection_limit,
                'daily_follow_up_limit': config.daily_follow_up_limit,
                'velocity': config.velocity,
                'cooldown_minutes': config.cooldown_minutes,
            },
            'linkedin_profile': {
                'username': config.linkedin_username,
                'campaign': config.linkedin_campaign,
            },
        })


class DailyUsageView(APIView):
    """
    API view for getting daily usage statistics.
    
    GET /api/settings/daily-usage - Get daily usage statistics
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get daily usage statistics."""
        from openoutreach.linkedin.models import ActionLog
        from django.utils import timezone
        from datetime import date
        
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Count daily connections sent (across all LinkedIn profiles)
        daily_connections_sent = ActionLog.objects.filter(
            action_type=ActionLog.ActionType.CONNECT,
            created_at__gte=today_start,
        ).count()
        
        # Count daily messages sent (follow-ups) across all LinkedIn profiles
        daily_messages_sent = ActionLog.objects.filter(
            action_type=ActionLog.ActionType.FOLLOW_UP,
            created_at__gte=today_start,
        ).count()
        
        # Get the daily connection limit from site config
        config = SiteConfig.load()
        daily_limit = config.daily_connection_limit
        
        # Determine last reset time (midnight of the current day)
        last_reset = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        
        # Determine reset frequency
        reset_frequency = "daily"
        
        return Response({
            'daily_connections_sent': daily_connections_sent,
            'daily_messages_sent': daily_messages_sent,
            'daily_limit': daily_limit,
            'last_reset': last_reset,
            'reset_frequency': reset_frequency,
        })


class RateLimitsView(APIView):
    """
    API view for managing rate limits.
    
    GET /api/settings/rate-limits - Get rate limits
    PATCH /api/settings/rate-limits - Update rate limits
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get rate limits."""
        config = SiteConfig.load()
        
        return Response({
            'daily_connection_limit': config.daily_connection_limit,
            'daily_follow_up_limit': config.daily_follow_up_limit,
            'velocity': config.velocity,
            'cooldown_minutes': config.cooldown_minutes,
        })
    
    def patch(self, request):
        """Update rate limits."""
        config = SiteConfig.load()
        
        # Get rate limits from request
        rate_limits = request.data.get('rate_limits', {})
        
        # Update config with rate limits - handle both camelCase and snake_case
        if 'dailyConnectionLimit' in rate_limits:
            config.daily_connection_limit = rate_limits['dailyConnectionLimit']
        elif 'daily_connection_limit' in rate_limits:
            config.daily_connection_limit = rate_limits['daily_connection_limit']
            
        if 'dailyFollowUpLimit' in rate_limits:
            config.daily_follow_up_limit = rate_limits['dailyFollowUpLimit']
        elif 'daily_follow_up_limit' in rate_limits:
            config.daily_follow_up_limit = rate_limits['daily_follow_up_limit']
            
        if 'velocity' in rate_limits:
            config.velocity = rate_limits['velocity']
            
        if 'cooldown_minutes' in rate_limits:
            config.cooldown_minutes = rate_limits['cooldown_minutes']
        
        config.save()
        
        return Response({
            'daily_connection_limit': config.daily_connection_limit,
            'daily_follow_up_limit': config.daily_follow_up_limit,
            'velocity': config.velocity,
            'cooldown_minutes': config.cooldown_minutes,
        })