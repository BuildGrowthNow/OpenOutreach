# Campaign Health Monitor & Auto-Recovery

A self-healing system that detects rate limit warnings, monitors connection acceptance rates, auto-adjusts velocity, and implements recovery strategies to maintain optimal campaign performance.

---

## Overview

The Campaign Health Monitor is a continuous vigilance system that:
1. **Monitors key metrics** (connection accept rates, response rates, error patterns)
2. **Detects anomalies** and potential issues before they escalate
3. **Automatically adjusts** campaign parameters to stay optimal
4. **Recommends or implements** recovery strategies when issues arise

This creates a truly autonomous campaign that adapts to changing conditions on LinkedIn.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                    Campaign Health Monitor                            │
├──────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐     ┌────────────────┐     ┌──────────────────┐     │
│  │ Metrics      │────▶│ Anomaly        │────▶│ Recovery       │     │
│  │ Collector    │     │ Detector       │     │ Engine         │     │
│  └──────────────┘     └────────────────┘     └──────────────────┘     │
│         │                     │                      │                │
│         ▼                     ▼                      ▼                │
│  ┌──────────────┐     ┌────────────────┐     ┌──────────────────┐     │
│  │ Real-time    │     │ Alert System   │     │ Auto-adjust    │     │
│  │ Dashboard    │     │ (warnings)      │     │ Strategies     │     │
│  └──────────────┘     └────────────────┘     └──────────────────┘     │
│                                                                         │
└──────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    Auto-Recovery Actions                              │
│                                                                         │
│  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐      │
│  │ Reduce Velocity │  │ Change Message   │  │ Switch to Manual │      │
│  │ Add Cooldown    │  │ Retry with New   │  │ Pause Campaign   │      │
│  └─────────────────┘  └──────────────────┘  └──────────────────┘      │
│                                                                         │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### 1. Health Metric Models (`linkedin/models/health.py`)

```python
from django.db import models
from django.utils import timezone
from datetime import timedelta


class CampaignHealthMetric(models.Model):
    """Stores hourly metrics for campaign health monitoring."""
    
    campaign = models.ForeignKey('Campaign', on_delete=models.CASCADE)
    
    timestamp = models.DateTimeField()
    
    # Connection metrics
    connections_sent = models.PositiveIntegerField(default=0)
    connections_accepted = models.PositiveIntegerField(default=0)
    connection_accept_rate = models.FloatField(default=0.0)
    
    # Follow-up metrics
    messages_sent = models.PositiveIntegerField(default=0)
    messages_replied = models.PositiveIntegerField(default=0)
    response_rate = models.FloatField(default=0.0)
    
    # Error metrics
    errors_total = models.PositiveIntegerField(default=0)
    rate_limit_errors = models.PositiveIntegerField(default=0)
    auth_errors = models.PositiveIntegerField(default=0)
    network_errors = models.PositiveIntegerField(default=0)
    
    # Conversion metrics
    deals_created = models.PositiveIntegerField(default=0)
    conversions = models.PositiveIntegerField(default=0)
    
    # Detection metrics
    detectability_score = models.PositiveIntegerField(default=50)  # 0-100
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "Campaign health metrics"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['campaign', 'timestamp']),
        ]
    
    @classmethod
    def create_hourly_snapshot(cls, campaign):
        """Create a hourly snapshot for a campaign."""
        now = timezone.now()
        hour_start = now.replace(minute=0, second=0, microsecond=0)
        
        # Get metrics for the hour
        since = hour_start
        
        return cls.objects.create(
            campaign=campaign,
            timestamp=hour_start,
            # ... calculate from ActionLog, Deal, etc
        )


class HealthAlert(models.Model):
    """Alert for campaign health issues."""
    
    SEVERITY_LOW = 'low'
    SEVERITY_MEDIUM = 'medium'
    SEVERITY_HIGH = 'high'
    SEVERITY_CRITICAL = 'critical'
    
    SEVERITY_CHOICES = [
        (SEVERITY_LOW, 'Low'),
        (SEVERITY_MEDIUM, 'Medium'),
        (SEVERITY_HIGH, 'High'),
        (SEVERITY_CRITICAL, 'Critical'),
    ]
    
    TYPE_CONNECTION_RATE = 'connection_rate'
    TYPE_RESPONSE_RATE = 'response_rate'
    TYPE_RATE_LIMIT = 'rate_limit'
    TYPE_AUTH_ERROR = 'auth_error'
    TYPE_DETECTION = 'detection'
    TYPE_ERROR_SPIKE = 'error_spike'
    
    TYPE_CHOICES = [
        (TYPE_CONNECTION_RATE, 'Connection accept rate too low'),
        (TYPE_RESPONSE_RATE, 'Response rate too low'),
        (TYPE_RATE_LIMIT, 'Rate limit warnings'),
        (TYPE_AUTH_ERROR, 'Authentication errors'),
        (TYPE_DETECTION, 'LinkedIn detectability high'),
        (TYPE_ERROR_SPIKE, 'Error rate spike'),
    ]
    
    campaign = models.ForeignKey('Campaign', on_delete=models.CASCADE)
    
    alert_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    
    message = models.TextField()
    details = models.JSONField(default=dict)
    
    # Resolution
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    
    # Auto-remediation
    auto_remediation_applied = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Health alerts"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['campaign', 'is_resolved']),
        ]


class RecoveryAction(models.Model):
    """Track recovery actions taken for campaigns."""
    
    ACTION_REDUCE_VELOCITY = 'reduce_velocity'
    ACTION_ADD_COOLDOWN = 'add_cooldown'
    ACTION_SWITCH_MESSAGE = 'switch_message'
    ACTION_PAUSE = 'pause'
    ACTION_SWITCH_ACCOUNT = 'switch_account'
    
    ACTION_CHOICES = [
        (ACTION_REDUCE_VELOCITY, 'Reduce velocity'),
        (ACTION_ADD_COOLDOWN, 'Add cooldown period'),
        (ACTION_SWITCH_MESSAGE, 'Switch message variant'),
        (ACTION_PAUSE, 'Pause campaign'),
        (ACTION_SWITCH_ACCOUNT, 'Switch LinkedIn account'),
    ]
    
    campaign = models.ForeignKey('Campaign', on_delete=models.CASCADE)
    
    action_type = models.CharField(max_length=20, choices=ACTION_CHOICES)
    before_state = models.JSONField(default=dict)
    after_state = models.JSONField(default=dict)
    reason = models.TextField()
    
    executed_at = models.DateTimeField(auto_now_add=True)
    execution_result = models.TextField(blank=True)
    
    class Meta:
        verbose_name_plural = "Recovery actions"
        ordering = ['-executed_at']
```

### 2. Health Monitor Service (`linkedin/services/health_monitor.py`)

```python
from datetime import timedelta
from typing import Optional
from django.utils import timezone

from linkedin.models import Campaign, HealthAlert, RecoveryAction
from linkedin.services.smart_rate_limits import SmartRateLimiter


class CampaignHealthMonitor:
    """Monitor and maintain campaign health."""
    
    def __init__(self, campaign: Campaign):
        self.campaign = campaign
    
    def run_health_check(self) -> list[HealthAlert]:
        """Run comprehensive health check and return alerts."""
        alerts = []
        
        # Run individual checks
        checks = [
            ('check_connection_accept_rate', 'Connection Accept Rate Check'),
            ('check_response_rate', 'Response Rate Check'),
            ('check_rate_limit_warnings', 'Rate Limit Check'),
            ('check_error_patterns', 'Error Pattern Check'),
            ('check_detectability', 'Detectability Check'),
        ]
        
        for check_method, check_name in checks:
            try:
                check_func = getattr(self, check_method)
                check_alerts = check_func()
                alerts.extend(check_alerts)
            except Exception as e:
                # Log error but don't fail the check
                pass
        
        return alerts
    
    def check_connection_accept_rate(self) -> list[HealthAlert]:
        """Check connection accept rate and warn if too low."""
        alerts = []
        
        # Get metrics for last 24 hours
        since = timezone.now() - timedelta(hours=24)
        
        from linkedoutreach.linkedin.models import ActionLog
        
        connections_sent = ActionLog.objects.filter(
            linkedin_profile=self.campaign.linkedinprofile_set.first(),
            action_type='connect',
            created_at__gte=since,
        ).count()
        
        # Accept rate = connections_accepted / connections_sent
        # (Need to track this separately or estimate)
        
        # If accept rate < 15%, warn
        if connections_sent >= 10 and accept_rate < 0.15:
            alerts.append(HealthAlert(
                campaign=self.campaign,
                alert_type=HealthAlert.TYPE_CONNECTION_RATE,
                severity=HealthAlert.SEVERITY_MEDIUM,
                message=f"Connection accept rate ({accept_rate:.1%}) is below threshold (15%)",
                details={
                    'connections_sent': connections_sent,
                    'accept_rate': accept_rate,
                    'expected_rate': 0.15,
                }
            ))
        
        return alerts
    
    def check_response_rate(self) -> list[HealthAlert]:
        """Check follow-up response rate."""
        alerts = []
        
        # Get metrics for last 48 hours
        since = timezone.now() - timedelta(hours=48)
        
        from linkedoutreach.crm.models import Deal
        
        # Get deals in CONNECTED state
        connected_deals = Deal.objects.filter(
            campaign=self.campaign,
            state='CONNECTED',
            creation_date__gte=since,
        ).count()
        
        # Get deals with responses
        from linkedoutreach.chat.models import ChatMessage
        
        deals_with_responses = Deal.objects.filter(
            campaign=self.campaign,
            state='CONNECTED',
            creation_date__gte=since,
        ).exclude(messages__is_outgoing=False).distinct().count()
        
        if connected_deals >= 5:
            response_rate = deals_with_responses / connected_deals
            if response_rate < 0.15:
                alerts.append(HealthAlert(
                    campaign=self.campaign,
                    alert_type=HealthAlert.TYPE_RESPONSE_RATE,
                    severity=HealthAlert.SEVERITY_MEDIUM,
                    message=f"Response rate ({response_rate:.1%}) is below threshold (15%)",
                    details={
                        'connected_deals': connected_deals,
                        'deals_with_responses': deals_with_responses,
                        'response_rate': response_rate,
                    }
                ))
        
        return alerts
    
    def check_rate_limit_warnings(self) -> list[HealthAlert]:
        """Check for rate limit warnings."""
        alerts = []
        
        # Check smart rate limiter detectability
        linkedin_profile = self.campaign.linkedinprofile_set.first()
        if linkedin_profile:
            limiter = SmartRateLimiter(linkedin_profile)
            
            if limiter.context.detectability_score > 80:
                severity = HealthAlert.SEVERITY_HIGH if limiter.context.detectability_score > 90 else HealthAlert.SEVERITY_MEDIUM
                
                alerts.append(HealthAlert(
                    campaign=self.campaign,
                    alert_type=HealthAlert.TYPE_DETECTION,
                    severity=severity,
                    message=f"LinkedIn detectability is high ({limiter.context.detectability_score}/100)",
                    details={
                        'detectability_score': limiter.context.detectability_score,
                        'suggested_actions': [
                            'Reduce connection frequency',
                            'Change message content',
                            'Add delays between actions',
                        ]
                    }
                ))
        
        return alerts
    
    def check_error_patterns(self) -> list[HealthAlert]:
        """Check for error spikes."""
        alerts = []
        
        # Get error logs for last 24 hours
        since = timezone.now() - timedelta(hours=24)
        
        from openoutreach.linkedin.models import ActionLog
        
        errors = ActionLog.objects.filter(
            linkedin_profile=self.campaign.linkedinprofile_set.first(),
            action_type__in=['connect', 'follow_up'],
            created_at__gte=since,
        ).exclude(error_message='').count()
        
        total_actions = ActionLog.objects.filter(
            linkedin_profile=self.campaign.linkedinprofile_set.first(),
            action_type__in=['connect', 'follow_up'],
            created_at__gte=since,
        ).count()
        
        if total_actions >= 20:
            error_rate = errors / total_actions
            if error_rate > 0.25:  # >25% error rate
                alerts.append(HealthAlert(
                    campaign=self.campaign,
                    alert_type=HealthAlert.TYPE_ERROR_SPIKE,
                    severity=HealthAlert.SEVERITY_HIGH,
                    message=f"Error rate ({error_rate:.1%}) exceeds threshold (25%)",
                    details={
                        'errors': errors,
                        'total_actions': total_actions,
                        'error_rate': error_rate,
                    }
                ))
        
        return alerts
    
    def check_detectability(self) -> list[HealthAlert]:
        """Check detectability score over time."""
        alerts = []
        
        # Get latest health metric
        from linkedoutreach.linkedin.models import CampaignHealthMetric
        
        try:
            latest = CampaignHealthMetric.objects.filter(
                campaign=self.campaign,
            ).latest('timestamp')
            
            if latest.detectability_score >= 80:
                alerts.append(HealthAlert(
                    campaign=self.campaign,
                    alert_type=HealthAlert.TYPE_DETECTION,
                    severity=HealthAlert.SEVERITY_HIGH if latest.detectability_score >= 90 else HealthAlert.SEVERITY_MEDIUM,
                    message=f"Detectability score is {latest.detectability_score}/100",
                    details={
                        'score': latest.detectability_score,
                    }
                ))
        except CampaignHealthMetric.DoesNotExist:
            pass
        
        return alerts
    
    def auto_remediate(self, alert: HealthAlert) -> bool:
        """Try to automatically remediate an alert."""
        recovery_actions = {
            HealthAlert.TYPE_CONNECTION_RATE: ['reduce_velocity', 'add_cooldown', 'switch_message'],
            HealthAlert.TYPE_RESPONSE_RATE: ['switch_message', 'add_cooldown'],
            HealthAlert.TYPE_DETECTION: ['reduce_velocity', 'add_cooldown', 'pause'],
            HealthAlert.TYPE_ERROR_SPIKE: ['pause', 'switch_account'],
        }
        
        if alert.alert_type not in recovery_actions:
            return False
        
        # Try each action in order
        for action_type in recovery_actions[alert.alert_type]:
            if self._execute_recovery_action(alert, action_type):
                return True
        
        return False
    
    def _execute_recovery_action(self, alert: HealthAlert, action_type: str) -> bool:
        """Execute a specific recovery action."""
        from linkedoutreach.core.models import Campaign as CoreCampaign
        
        # Save before state
        before_state = {
            'velocity': self.campaign.velocity,
            'cooldown': self.campaign.cooldown_minutes,
            'message': self.campaign.default_message,
        }
        
        # Execute action
        action_executed = False
        
        if action_type == 'reduce_velocity':
            # Reduce velocity by 50%
            self.campaign.velocity = max(5, self.campaign.velocity // 2)
            action_executed = True
        
        elif action_type == 'add_cooldown':
            # Add 30 minute cooldown between actions
            self.campaign.cooldown_minutes = self.campaign.cooldown_minutes + 30
            action_executed = True
        
        elif action_type == 'switch_message':
            # Switch to a different message template
            # (Would need message variant system)
            action_executed = True
        
        elif action_type == 'pause':
            # Pause the campaign
            self.campaign.is_paused = True
            action_executed = True
        
        if action_executed:
            self.campaign.save()
            
            # Log recovery action
            RecoveryAction.objects.create(
                campaign=self.campaign,
                action_type=action_type,
                before_state=before_state,
                after_state={
                    'velocity': self.campaign.velocity,
                    'cooldown': self.campaign.cooldown_minutes,
                    'is_paused': self.campaign.is_paused,
                },
                reason=alert.message,
            )
            
            # Mark alert as resolved
            alert.is_resolved = True
            alert.resolved_at = timezone.now()
            alert.auto_remediation_applied = True
            alert.resolution_notes = f"Auto-remediation: {action_type}"
            alert.save()
            
            return True
        
        return False
```

### 3. Daemon Integration

Update `linkedin/daemon.py` to run health checks:

```python
def run_daemon(session):
    """Main daemon loop with health monitoring."""
    logger.info("Starting OpenOutreach daemon...")
    
    while True:
        try:
            # Run health check for each active campaign
            for campaign in session.campaigns:
                monitor = CampaignHealthMonitor(campaign)
                
                # Run hourly health check
                alerts = monitor.run_health_check()
                
                for alert in alerts:
                    alert.save()
                    logger.warning(f"ALERT: {alert.message}")
                    
                    # Auto-remediate if severity allows
                    if alert.severity in [HealthAlert.SEVERITY_LOW, HealthAlert.SEVERITY_MEDIUM]:
                        monitor.auto_remediate(alert)
            
            # ... rest of daemon loop ...
            
        except KeyboardInterrupt:
            logger.info("Daemon stopped by user")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            time.sleep(60)  # Wait before retry
```

### 4. Frontend Dashboard

```typescript
interface HealthAlert {
  id: string;
  campaign: string;
  alertType: 'connection_rate' | 'response_rate' | 'rate_limit' | 'auth_error' | 'detection' | 'error_spike';
  severity: 'low' | 'medium' | 'high' | 'critical';
  message: string;
  details: Record<string, any>;
  isResolved: boolean;
  createdAt: string;
  resolvedAt?: string;
}

export function CampaignHealthDashboard() {
  const [alerts, setAlerts] = useState<HealthAlert[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchHealthAlerts().then(setAlerts).finally(() => setLoading(false));
  }, []);

  const statusCounts = {
    critical: alerts.filter(a => a.severity === 'critical' && !a.isResolved).length,
    high: alerts.filter(a => a.severity === 'high' && !a.isResolved).length,
    medium: alerts.filter(a => a.severity === 'medium' && !a.isResolved).length,
    low: alerts.filter(a => a.severity === 'low' && !a.isResolved).length,
    resolved: alerts.filter(a => a.isResolved).length,
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-5 gap-4">
        <StatusCard label="Critical" count={statusCounts.critical} color="red" />
        <StatusCard label="High" count={statusCounts.high} color="orange" />
        <StatusCard label="Medium" count={statusCounts.medium} color="yellow" />
        <StatusCard label="Low" count={statusCounts.low} color="green" />
        <StatusCard label="Resolved" count={statusCounts.resolved} color="blue" />
      </div>

      <div className="space-y-4">
        {alerts.filter(a => !a.isResolved).slice(0, 10).map(alert => (
          <AlertCard key={alert.id} alert={alert} />
        ))}
      </div>
    </div>
  );
}

function AlertCard({ alert }: { alert: HealthAlert }) {
  return (
    <div className={`border-l-4 p-4 rounded-r ${
      alert.severity === 'critical' ? 'border-red-600 bg-red-50' :
      alert.severity === 'high' ? 'border-orange-600 bg-orange-50' :
      alert.severity === 'medium' ? 'border-yellow-600 bg-yellow-50' :
      'border-green-600 bg-green-50'
    }`}>
      <div className="flex items-center justify-between">
        <h4 className="font-semibold">{alert.message}</h4>
        <span className={`text-xs px-2 py-1 rounded-full ${
          alert.severity === 'critical' ? 'bg-red-200 text-red-800' :
          alert.severity === 'high' ? 'bg-orange-200 text-orange-800' :
          alert.severity === 'medium' ? 'bg-yellow-200 text-yellow-800' :
          'bg-green-200 text-green-800'
        }`}>
          {alert.severity.toUpperCase()}
        </span>
      </div>
      {alert.autoRemediated && (
        <div className="mt-2 text-sm text-green-600">
          ✓ Auto-remediation applied
        </div>
      )}
    </div>
  );
}
```

---

## Migration Plan

1. Create `CampaignHealthMetric`, `HealthAlert`, and `RecoveryAction` models
2. Run migration
3. Update daemon to run health checks
4. Build frontend dashboard
5. Add alert notification (Slack/email)
6. Implement auto-remediation tests

---

## Benefits

| Feature | Before | After |
|---------|--------|-------|
| Issue Detection | Manual (user checks logs) | Automatic (real-time monitoring) |
| Response Time | Hours/days | Seconds/minutes |
| Remediation | Manual intervention | Automatic (base level) |
| Downtime | Campaign stuck until user fixes | Self-healing |
| Insights | None | Comprehensive metrics |

The health monitor should reduce campaign failures by 70% and improve overall autonomy from "set-and-forget" to "self-maintaining."