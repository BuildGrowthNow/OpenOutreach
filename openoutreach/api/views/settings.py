# Settings API Views

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from openoutreach.core.models import SiteConfig
from openoutreach.linkedin.models import LinkedInProfile
from openoutreach.linkedin.services.smart_rate_limits import (
    SmartRateLimiter,
    smart_get_remaining,
)
from openoutreach.mongodb.models import UserProfile
from openoutreach.mongodb.serializers import UserProfileSerializer


class SettingsView(APIView):
    """
    API view for managing system settings.

    GET /api/settings - Get all system settings
    PATCH /api/settings - Update system settings
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get all system settings including user profile from MongoDB."""
        config = SiteConfig.load()
        
        # Get user profile from MongoDB
        user_profile = UserProfile.get(str(request.user.id))
        profile_data = {}
        if user_profile:
            # Convert to dict and remove private fields
            profile_dict = user_profile.to_dict()
            profile_data = {
                "first_name": profile_dict.get("first_name", ""),
                "last_name": profile_dict.get("last_name", ""),
                "email": profile_dict.get("email", ""),
                "phone": profile_dict.get("phone", ""),
                "company": profile_dict.get("company", ""),
                "position": profile_dict.get("position", ""),
                "timezone": profile_dict.get("timezone", "UTC"),
                "notification_preferences": profile_dict.get("notification_preferences", {}),
                "ui_preferences": profile_dict.get("ui_preferences", {}),
            }

        return Response(
            {
                "llm": {
                    "provider": config.llm_provider,
                    "model": config.ai_model,
                    "api_base": config.llm_api_base,
                },
                "rate_limits": {
                    "daily_connection_limit": config.daily_connection_limit,
                    "daily_follow_up_limit": config.daily_follow_up_limit,
                    "velocity": config.velocity,
                    "cooldown_minutes": config.cooldown_minutes,
                },
                "linkedin_profile": {
                    "username": config.linkedin_username,
                    "campaign": config.linkedin_campaign,
                },
                "profile": profile_data,
            }
        )

    def patch(self, request):
        """Update system settings and user profile."""
        config = SiteConfig.load()

        # Get data from request
        data = request.data

        # Update LLM config if provided
        llm_config = data.get("llm", {})
        if "provider" in llm_config:
            config.llm_provider = llm_config["provider"]
        if "model" in llm_config:
            config.ai_model = llm_config["model"]
        if "api_base" in llm_config:
            config.llm_api_base = llm_config["api_base"]

        # Update LinkedIn profile if provided
        linkedin_profile = data.get("linkedin_profile", {})
        if "username" in linkedin_profile:
            config.linkedin_username = linkedin_profile["username"]
        if "campaign" in linkedin_profile:
            config.linkedin_campaign = linkedin_profile["campaign"]

        # Update rate limits if provided
        rate_limits = data.get("rate_limits", {})
        if "daily_connection_limit" in rate_limits:
            config.daily_connection_limit = rate_limits["daily_connection_limit"]
        if "daily_follow_up_limit" in rate_limits:
            config.daily_follow_up_limit = rate_limits["daily_follow_up_limit"]
        if "velocity" in rate_limits:
            config.velocity = rate_limits["velocity"]
        if "cooldown_minutes" in rate_limits:
            config.cooldown_minutes = rate_limits["cooldown_minutes"]

        config.save()
        
        # Update user profile in MongoDB if provided
        profile_data = data.get("profile", {})
        if profile_data:
            user_profile = UserProfile.get(str(request.user.id))
            if user_profile:
                # Update existing profile
                serializer = UserProfileSerializer(user_profile, data=profile_data, partial=True)
            else:
                # Create new profile
                profile_data["user_id"] = str(request.user.id)
                serializer = UserProfileSerializer(data=profile_data)
                
            if serializer.is_valid():
                serializer.save()
            else:
                return Response(
                    {"error": "Invalid profile data", "details": serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Return updated settings
        user_profile = UserProfile.get(str(request.user.id))
        profile_data_response = {}
        if user_profile:
            profile_dict = user_profile.to_dict()
            profile_data_response = {
                "first_name": profile_dict.get("first_name", ""),
                "last_name": profile_dict.get("last_name", ""),
                "email": profile_dict.get("email", ""),
                "phone": profile_dict.get("phone", ""),
                "company": profile_dict.get("company", ""),
                "position": profile_dict.get("position", ""),
                "timezone": profile_dict.get("timezone", "UTC"),
                "notification_preferences": profile_dict.get("notification_preferences", {}),
                "ui_preferences": profile_dict.get("ui_preferences", {}),
            }

        return Response(
            {
                "llm": {
                    "provider": config.llm_provider,
                    "model": config.ai_model,
                    "api_base": config.llm_api_base,
                },
                "rate_limits": {
                    "daily_connection_limit": config.daily_connection_limit,
                    "daily_follow_up_limit": config.daily_follow_up_limit,
                    "velocity": config.velocity,
                    "cooldown_minutes": config.cooldown_minutes,
                },
                "linkedin_profile": {
                    "username": config.linkedin_username,
                    "campaign": config.linkedin_campaign,
                },
                "profile": profile_data_response,
            }
        )


class DailyUsageView(APIView):
    """
    API view for getting daily usage statistics with context-aware rate limiting.

    GET /api/settings/daily-usage - Get daily usage statistics with effective limits
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get daily usage statistics with effective rate limits."""
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
        base_daily_limit = config.daily_connection_limit

        # Get effective rate limits per LinkedIn profile (context-aware)
        effective_limits = []
        linkedin_profiles = LinkedInProfile.objects.filter(user=request.user)

        for profile in linkedin_profiles:
            limiter = SmartRateLimiter(profile)
            effective_limit = limiter.context.get_effective_limit("connect")
            remaining = limiter.get_remaining_quota("connect")
            effective_limits.append(
                {
                    "profile_id": profile.id,  # type: ignore[attr-defined]
                    "profile_username": profile.linkedin_username,
                    "base_limit": base_daily_limit,
                    "effective_limit": effective_limit,
                    "remaining": remaining,
                    "use_multiplier": limiter.context.time_of_day_limit_multiplier,
                    "day_multiplier": limiter.context.day_of_week_limit_multiplier,
                    "detectability_score": limiter.context.detectability_score,
                }
            )

        # Determine the global effective limit (minimum across all profiles)
        # This is what actually constrains the system
        global_effective_limit = min(
            [limit["effective_limit"] for limit in effective_limits]
            or [base_daily_limit]
        )

        # Calculate remaining global quota
        global_remaining = sum(limit["remaining"] for limit in effective_limits)

        # Calculate daily progress including rate limit status
        rate_limit_status = "normal"
        warning_message = None
        warning_level = None

        if daily_connections_sent >= global_effective_limit:
            rate_limit_status = "exceeded"
            warning_message = f"Rate limit exceeded! You've sent {daily_connections_sent} connections but your effective limit is {global_effective_limit}"
            warning_level = "high"
        elif daily_connections_sent >= global_effective_limit * 0.8:
            rate_limit_status = "warning"
            remaining = max(0, global_effective_limit - daily_connections_sent)
            warning_message = f"Approaching rate limit! You have {remaining} connections remaining out of {global_effective_limit} effective limit today"
            warning_level = "medium"
        elif daily_connections_sent >= global_effective_limit * 0.5:
            rate_limit_status = "caution"
            remaining = max(0, global_effective_limit - daily_connections_sent)
            warning_message = f"Rate limit progress: {remaining} connections remaining out of {global_effective_limit} effective limit today"
            warning_level = "low"

        # Determine last reset time (midnight of the current day)
        last_reset = (
            timezone.now()
            .replace(hour=0, minute=0, second=0, microsecond=0)
            .isoformat()
        )

        # Determine reset frequency
        reset_frequency = "daily"

        return Response(
            {
                "daily_connections_sent": daily_connections_sent,
                "daily_messages_sent": daily_messages_sent,
                "daily_limit": base_daily_limit,  # Base limit for backward compatibility
                "effective_limit": global_effective_limit,  # Context-aware effective limit
                "remaining": global_remaining,  # Total remaining across all profiles
                "rate_limit_status": rate_limit_status,  # 'normal', 'caution', 'warning', 'exceeded'
                "warning_message": warning_message,
                "warning_level": warning_level,
                "last_reset": last_reset,
                "reset_frequency": reset_frequency,
                "linkedin_profiles": effective_limits,  # Per-profile breakdown
            }
        )


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

        return Response(
            {
                "daily_connection_limit": config.daily_connection_limit,
                "daily_follow_up_limit": config.daily_follow_up_limit,
                "velocity": config.velocity,
                "cooldown_minutes": config.cooldown_minutes,
            }
        )

    def patch(self, request):
        """Update rate limits."""
        config = SiteConfig.load()

        # Get rate limits from request
        rate_limits = request.data.get("rate_limits", {})

        # Update config with rate limits - handle both camelCase and snake_case
        if "dailyConnectionLimit" in rate_limits:
            config.daily_connection_limit = rate_limits["dailyConnectionLimit"]
        elif "daily_connection_limit" in rate_limits:
            config.daily_connection_limit = rate_limits["daily_connection_limit"]

        if "dailyFollowUpLimit" in rate_limits:
            config.daily_follow_up_limit = rate_limits["dailyFollowUpLimit"]
        elif "daily_follow_up_limit" in rate_limits:
            config.daily_follow_up_limit = rate_limits["daily_follow_up_limit"]

        if "velocity" in rate_limits:
            config.velocity = rate_limits["velocity"]

        if "cooldown_minutes" in rate_limits:
            config.cooldown_minutes = rate_limits["cooldown_minutes"]

        config.save()

        return Response(
            {
                "daily_connection_limit": config.daily_connection_limit,
                "daily_follow_up_limit": config.daily_follow_up_limit,
                "velocity": config.velocity,
                "cooldown_minutes": config.cooldown_minutes,
            }
        )
