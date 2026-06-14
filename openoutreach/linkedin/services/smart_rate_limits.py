# openoutreach/linkedin/services/smart_rate_limits.py
"""Smart Rate Limiting service with context-aware decisions."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from django.utils import timezone

from openoutreach.linkedin.models import LinkedInProfile, SmartRateLimitContext, RateLimitWarning


class SmartRateLimiter:
    """Smart rate limiting service with context-aware decisions."""
    
    def __init__(self, linkedin_profile: LinkedInProfile):
        self.linkedin_profile = linkedin_profile
        self.context = self._get_or_create_context()
    
    def _get_or_create_context(self) -> SmartRateLimitContext:
        """Get or create rate limit context for profile."""
        context, _ = SmartRateLimitContext.objects.get_or_create(
            linkedin_profile=self.linkedin_profile
        )
        return context
    
    def can_execute(self, action_type: str, campaign=None) -> bool:
        """Check if action can be executed given current context."""
        effective_limit = self.context.get_effective_limit(action_type, campaign)
        
        # Count recent actions (last 24 hours)
        since = timezone.now() - timedelta(hours=24)
        recent_count = self._count_recent_actions(action_type, since)
        
        return recent_count < effective_limit
    
    def record_action(self, action_type: str, campaign=None):
        """Record an action and update rate limit context."""
        self.context.record_action(action_type)
        
        # Also record in ActionLog for backward compatibility
        self._record_action_log(action_type)
    
    def get_remaining_quota(self, action_type: str, campaign=None) -> int:
        """Get remaining quota for action type."""
        effective_limit = self.context.get_effective_limit(action_type, campaign)
        since = timezone.now() - timedelta(hours=24)
        recent_count = self._count_recent_actions(action_type, since)
        
        return max(0, effective_limit - recent_count)
    
    def get_quota_breakdown(self, action_type: str, campaign=None) -> dict:
        """Get detailed breakdown of rate limiting."""
        base_limit = self.context._get_base_limit(action_type)
        
        return {
            'base_limit': base_limit,
            'time_multiplier': self.context.time_of_day_limit_multiplier,
            'day_multiplier': self.context.day_of_week_limit_multiplier,
            'detectability_multiplier': self.context._detectability_multiplier(),
            'effective_limit': self.context.get_effective_limit(action_type, campaign),
            'recent_24h': self._count_recent_actions(action_type),
            'remaining': self.get_remaining_quota(action_type, campaign),
            'detectability_score': self.context.detectability_score,
            'context': {
                'time_of_day': timezone.now().strftime('%H:%M'),
                'day_of_week': timezone.now().strftime('%A'),
            }
        }
    
    def _count_recent_actions(self, action_type: str, since: Optional[datetime] = None) -> int:
        """Count recent actions of a given type."""
        if since is None:
            since = timezone.now() - timedelta(hours=24)
        
        from openoutreach.linkedin.models import ActionLog
        
        return ActionLog.objects.filter(
            linkedin_profile=self.linkedin_profile,
            action_type=action_type,
            created_at__gte=since,
        ).count()
    
    def _record_action_log(self, action_type: str):
        """Record action in ActionLog."""
        from openoutreach.linkedin.models import ActionLog
        
        ActionLog.objects.create(
            linkedin_profile=self.linkedin_profile,
            campaign=None,  # Will be set in handler
            action_type=action_type,
        )
    
    def check_detectability(self) -> bool:
        """Check if detectability is too high."""
        return self.context.detectability_score > 80
    
    def get_detectability_warning(self) -> Optional[RateLimitWarning]:
        """Get warning if detectability is high."""
        if self.context.detectability_score <= 80:
            return None
        
        level = 'high' if self.context.detectability_score > 90 else 'medium'
        
        return RateLimitWarning(
            linkedin_profile=self.linkedin_profile,
            action_type='detection',
            limit_type='detectability',
            limit_exceeded=80,
            actual_count=self.context.detectability_score,
            warning_level=level,
        )


def smart_can_execute(linkedin_profile: LinkedInProfile, action_type: str, campaign=None) -> bool:
    """Convenience function for can_execute."""
    limiter = SmartRateLimiter(linkedin_profile)
    return limiter.can_execute(action_type, campaign)


def smart_record_action(linkedin_profile: LinkedInProfile, action_type: str, campaign=None):
    """Convenience function for record_action."""
    limiter = SmartRateLimiter(linkedin_profile)
    limiter.record_action(action_type, campaign)


def smart_get_remaining(linkedin_profile: LinkedInProfile, action_type: str, campaign=None) -> int:
    """Convenience function for get_remaining_quota."""
    limiter = SmartRateLimiter(linkedin_profile)
    return limiter.get_remaining_quota(action_type, campaign)