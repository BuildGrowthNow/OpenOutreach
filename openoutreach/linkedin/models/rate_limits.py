# openoutreach/linkedin/models/rate_limits.py
"""Smart Rate Limiting models with context awareness."""
from __future__ import annotations

from django.db import models
from django.utils import timezone
from datetime import datetime, time
from enum import Enum


class EngagementLevel(Enum):
    COLD = 'cold'
    HOT = 'hot'
    VERIFIED_WARM = 'verified_warm'
    ACTIVELY_ENGAGED = 'actively_engaged'


class LinkedInDetectability(Enum):
    NORMAL = 'normal'
    SUSPICIOUS = 'suspicious'
    WARNING = 'warning'
    CRITICAL = 'critical'


class SmartRateLimitContext(models.Model):
    """
    Stores contextual rate limiting data for rate limiting decisions.
    One per LinkedInProfile.
    """
    
    linkedin_profile = models.OneToOneField('LinkedInProfile', on_delete=models.CASCADE, related_name='rate_limit_context')
    
    # Context data
    time_of_day_limit_multiplier = models.FloatField(default=1.0)
    day_of_week_limit_multiplier = models.FloatField(default=1.0)
    
    detectability_score = models.PositiveIntegerField(default=50)  # 0-100, 100 = detected
    last_detectability_update = models.DateTimeField(auto_now=True)
    
    last_action_type = models.CharField(max_length=20, blank=True)
    last_action_at = models.DateTimeField(null=True, blank=True)
    
    consecutive_actions = models.PositiveIntegerField(default=0)
    action_streak_reset_at = models.DateTimeField(null=True, blank=True)
    
    # Per-campaign context stored as JSON
    campaign_context = models.JSONField(default=dict)  # {campaign_id: {phase, lead_count, etc}}
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Smart rate limit contexts"
    
    def __str__(self):
        return f"Rate limits for {self.linkedin_profile}"
    
    def get_effective_limit(self, action_type: str, campaign=None) -> int:
        """Calculate effective rate limit based on all context factors."""
        base_limit = self._get_base_limit(action_type)
        
        # Apply multipliers
        multipliers = [
            self.time_of_day_limit_multiplier,
            self.day_of_week_limit_multiplier,
            self._detectability_multiplier(),
        ]
        
        effective = base_limit
        for m in multipliers:
            effective = int(effective * m)
        
        # Reduce if campaign-specific limits are lower
        if campaign and str(campaign.id) in self.campaign_context:
            campaign_limit = self.campaign_context[str(campaign.id)].get('limit', float('inf'))
            effective = min(effective, campaign_limit)
        
        return max(1, effective)  # At least 1 action allowed
    
    def _get_base_limit(self, action_type: str) -> int:
        """Get base limit for action type."""
        base_limits = {
            'connect': 30,
            'follow_up': 40,
            'message': 50,
            'view_profile': 60,
        }
        return base_limits.get(action_type, 30)
    
    def _detectability_multiplier(self) -> float:
        """
        Calculate multiplier based on detectability score.
        
        0-30 (low) = 1.0
        31-60 (medium) = 0.7
        61-80 (high) = 0.4
        81+ (critical) = 0.1
        """
        if self.detectability_score <= 30:
            return 1.0
        elif self.detectability_score <= 60:
            return 0.7
        elif self.detectability_score <= 80:
            return 0.4
        else:
            return 0.1
    
    def record_action(self, action_type: str):
        """Record an action and update context."""
        now = timezone.now()
        
        # Update time-based context
        self._update_time_context(now)
        
        # Update action streak
        if self.last_action_type == action_type:
            self.consecutive_actions += 1
            if self.consecutive_actions > 5:
                # Too many consecutive same-type actions = suspicious
                self.detectability_score = min(100, self.detectability_score + 15)
        else:
            self.consecutive_actions = 1
        
        # Decay detectability slowly over time
        self.detectability_score = max(0, self.detectability_score - 1)
        
        self.last_action_type = action_type
        self.last_action_at = now
        self.save()
    
    def _update_time_context(self, now: datetime):
        """Update multipliers based on time of day and day of week."""
        hour = now.hour
        day_of_week = now.weekday()  # Monday = 0, Sunday = 6
        
        # Time of day multiplier
        if 9 <= hour <= 17:  # Business hours
            self.time_of_day_limit_multiplier = 1.0
        elif 7 <= hour <= 9 or 17 <= hour <= 20:  # Early/late
            self.time_of_day_limit_multiplier = 0.8
        elif 20 <= hour or hour <= 6:  # Night
            self.time_of_day_limit_multiplier = 0.3
        
        # Day of week multiplier
        if day_of_week >= 5:  # Weekend
            self.day_of_week_limit_multiplier = 0.5
        elif day_of_week == 6:  # Sunday
            self.day_of_week_limit_multiplier = 0.2
        else:  # Weekday
            self.day_of_week_limit_multiplier = 1.0
        
        # Friday effect (people wrap up week)
        if day_of_week == 4:  # Friday
            self.day_of_week_limit_multiplier = 0.8
    
    def update_detectability(self, score_delta: int):
        """Adjust detectability score (positive = more suspicious)."""
        self.detectability_score = max(0, min(100, self.detectability_score + score_delta))
        self.last_detectability_update = timezone.now()
        self.save()
    
    def get_engagement_level(self, lead) -> EngagementLevel:
        """Determine engagement level for a specific lead."""
        from openoutreach.crm.models import Deal
        
        deal = Deal.objects.filter(lead=lead).first()
        if not deal:
            return EngagementLevel.COLD
        
        # Check engagement signals
        if deal.outcome == 'converted':
            return EngagementLevel.VERIFIED_WARM
        
        # Days since first connection
        days_since = (timezone.now() - deal.creation_date).days
        if days_since < 3:
            return EngagementLevel.HOT
        
        # Response history
        if deal.outcome in ['not_interested', 'wrong_fit']:
            return EngagementLevel.COLD
        
        # Connection accepted, no response yet
        if deal.state == 'CONNECTED':
            hours_since = (timezone.now() - deal.update_date).total_seconds() / 3600
            if hours_since < 24:
                return EngagementLevel.ACTIVELY_ENGAGED
        
        return EngagementLevel.VERIFIED_WARM


class RateLimitWarning(models.Model):
    """Warning log for rate limit violations."""
    
    linkedin_profile = models.ForeignKey('LinkedInProfile', on_delete=models.CASCADE, related_name='rate_limit_warnings')
    action_type = models.CharField(max_length=20)
    limit_type = models.CharField(max_length=20)
    limit_exceeded = models.PositiveIntegerField()
    actual_count = models.PositiveIntegerField()
    
    warning_level = models.CharField(max_length=10, choices=[
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ])
    
    at_time = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-at_time']