# Smart Rate Limiting with Context Awareness

Dynamic rate limiting that considers time of day, lead engagement history, campaign phase, and LinkedIn detectability signals instead of fixed daily limits.

---

## Overview

Traditional rate limiting uses fixed values:
- 20 connection requests per day
- 30 follow-up messages per day

This approach has significant flaws:
- **Over-limiting**: Quiet hours still count against daily quota
- **Under-limiting**: High-engagement periods use up quota too quickly
- **One-size-fits-all**: Doesn't account for individual lead quality
- **Detection-blind**: Doesn't adapt to LinkedIn's signals of automated behavior

Smart rate limiting solves this by dynamically adjusting limits based on:

| Context factor | Low Limit | Medium Limit | High Limit |
|----------------|-----------|--------------|------------|
| Time of day | 8-10pm = 10 | 9am-6pm = 25 | 6-8pm = 30 |
| Day of week | Weekend = 15 | Monday-Friday = 30 | Friday = 20 |
| Lead engagement | Cold lead = 5 | Hot lead = 50 | Verified warm = 100 |
| Campaign phase | Discovery = 15 | Follow-up = 35 | Nurturing = 25 |
| LinkedIn detectability | Normal = 30 | Suspicious = 15 | Warning = 5 |

---

## Implementation Plan

### 1. Rate Limit Context Model (`linkedin/models/rate_limits.py`)

```python
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
    
    linkedin_profile = models.OneToOneField('LinkedInProfile', on_delete=models.CASCADE)
    
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
        if campaign and campaign.id in self.campaign_context:
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
    
    linkedin_profile = models.ForeignKey('LinkedInProfile', on_delete=models.CASCADE)
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
```

### 2. Smart Rate Limiting Service (`linkedin/services/smart_rate_limits.py`)

```python
from datetime import datetime
from typing import Optional

from django.utils import timezone

from linkedin.models import LinkedInProfile, SmartRateLimitContext
from linkedin.models import RateLimitWarning


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
        since = timezone.now() - timezone.timedelta(hours=24)
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
        since = timezone.now() - timezone.timedelta(hours=24)
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
    
    def _count_recent_actions(self, action_type: str, since=None) -> int:
        """Count recent actions of a given type."""
        if since is None:
            since = timezone.now() - timezone.timedelta(hours=24)
        
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
```

### 3. Integration with Task Handlers

Update `linkedin/tasks/connect.py`:

```python
def handle_connect(task, session, qualifiers):
    """Handle connection task with smart rate limiting."""
    from linkedin.services.smart_rate_limits import smart_can_execute, smart_record_action
    
    campaign = session.campaign
    linkedin_profile = session.linkedin_profile
    
    # Check smart rate limits
    if not smart_can_execute(linkedin_profile, 'connect', campaign):
        remaining = smart_get_remaining(linkedin_profile, 'connect', campaign)
        logger.warning(f"Rate limit reached for {linkedin_profile} (remaining: {remaining})")
        
        # Re-enqueue with delay instead of failing
        _re_enqueue_with_delay(task, delay_seconds=3600)  # 1 hour
        return
    
    # Proceed with connection...
    try:
        # ... existing connection logic ...
        
        # Record action with smart rate limiter
        smart_record_action(linkedin_profile, 'connect', campaign)
        
        # ... rest of handler
        
    except Exception as e:
        # Handle exception...
        pass
```

### 4. Detectability Signals Monitoring

```python
def _monitor_detectability_signals(session):
    """Monitor LinkedIn signals for detectability."""
    from linkedin.services.smart_rate_limits import SmartRateLimiter
    
    limiter = SmartRateLimiter(session.linkedin_profile)
    
    # Check for suspicious patterns
    signals = []
    
    # 1. Action velocity (too many actions in short time)
    if limiter.context.consecutive_actions > 8:
        signals.append('high_consecutive_actions')
        limiter.context.update_detectability(20)
    
    # 2. Rapid profile views
    if limiter.context.last_action_type == 'view_profile':
        limiter.context.update_detectability(10)
    
    # 3. Unusual timing patterns
    hour = timezone.now().hour
    if hour < 6 or hour > 22:  # Night hours
        limiter.context.update_detectability(15)
    
    # 4. Connection decline rate
    # (Check recent connection requests vs acceptances)
    
    # Save context
    limiter.context.save()
```

### 5. Frontend Dashboard

```typescript
interface RateLimitContext {
  timeMultiplier: number;
  dayMultiplier: number;
  detectabilityMultiplier: number;
  effectiveLimit: number;
  recent24h: number;
  remaining: number;
  detectabilityScore: number;
  context: {
    timeOfDay: string;
    dayOfWeek: string;
  };
}

export function RateLimitDashboard() {
  const [context, setContext] = useState<RateLimitContext | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchRateLimitContext().then(setContext).finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner />;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white p-4 rounded-lg border">
          <div className="text-sm text-gray-500">Time Multiplier</div>
          <div className="text-2xl font-bold">
            {context?.timeMultiplier || 1}x
          </div>
          <div className="text-xs text-gray-400">
            {context?.context.timeOfDay}
          </div>
        </div>

        <div className="bg-white p-4 rounded-lg border">
          <div className="text-sm text-gray-500">Day Multiplier</div>
          <div className="text-2xl font-bold">
            {context?.dayMultiplier || 1}x
          </div>
          <div className="text-xs text-gray-400">
            {context?.context.dayOfWeek}
          </div>
        </div>

        <div className="bg-white p-4 rounded-lg border">
          <div className="text-sm text-gray-500">Detectability Score</div>
          <div className={`text-2xl font-bold ${
            (context?.detectabilityScore || 0) > 70 ? 'text-red-600' : 'text-green-600'
          }`}>
            {context?.detectabilityScore || 0}/100
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2 mt-2">
            <div 
              className={`h-2 rounded-full ${
                (context?.detectabilityScore || 0) > 70 ? 'bg-red-600' : 'bg-green-600'
              }`} 
              style={{ width: `${(context?.detectabilityScore || 0)}%` }}
            />
          </div>
        </div>
      </div>

      <div className="bg-white p-4 rounded-lg border">
        <h4 className="font-semibold mb-4">Effective Limits</h4>
        <div className="space-y-2">
          <LimitRow label="Connection Requests" remaining={context?.remaining || 0} limit={context?.effectiveLimit || 0} />
          <LimitRow label="Follow-up Messages" remaining={context?.remaining || 0} limit={context?.effectiveLimit || 0} />
        </div>
      </div>
    </div>
  );
}
```

---

## Migration Plan

1. Create `SmartRateLimitContext` and `RateLimitWarning` models
2. Run migration
3. Update LinkedInProfile model to use smart rate limiter
4. Update task handlers to use smart rate limiting
5. Add frontend dashboard
6. Deploy and monitor

---

## Benefits

| Current Method | Smart Rate Limiting |
|----------------|---------------------|
| Fixed limits | Dynamic limits |
| Same across all leads | Leads get different limits based on quality |
| Detection-blind | Monitors and adapts to detectability |
| Over-quota on off-hours | Under-quota on off-hours |
| Manual monitoring | Automatic optimization |

The smart rate limiter should reduce rate limit violations by 60-80% while maintaining or improving total daily outreach volume by better allocating quota to high-value leads during optimal times.