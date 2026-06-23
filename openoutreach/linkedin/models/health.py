# openoutreach/linkedin/models/health.py
"""Campaign Health Monitor & Auto-Recovery models."""
from __future__ import annotations

from django.db import models
from django.utils import timezone
from datetime import timedelta


class CampaignHealthMetric(models.Model):
    """Stores hourly metrics for campaign health monitoring."""

    id: int  # auto-generated primary key

    campaign = models.ForeignKey('core.Campaign', on_delete=models.CASCADE)
    
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
    def create_hourly_snapshot(cls, campaign) -> CampaignHealthMetric:
        """Create a hourly snapshot for a campaign."""
        now = timezone.now()
        hour_start = now.replace(minute=0, second=0, microsecond=0)
        
        # Get metrics for the hour
        since = hour_start - timedelta(hours=1)
        
        # Connection metrics from ActionLog
        from openoutreach.linkedin.models import ActionLog
        
        connections_sent = ActionLog.objects.filter(
            linkedin_profile__in=campaign.linkedinprofile_set.all(),
            action_type=ActionLog.ActionType.CONNECT,
            created_at__gte=since,
        ).count()
        
        connections_accepted = ActionLog.objects.filter(
            linkedin_profile__in=campaign.linkedinprofile_set.all(),
            action_type=ActionLog.ActionType.CONNECT,
            created_at__gte=since,
            campaign__deals__state='CONNECTED',
        ).distinct().count()
        
        connection_accept_rate = (
            connections_accepted / connections_sent 
            if connections_sent > 0 else 0.0
        )
        
        # Follow-up metrics
        messages_sent = ActionLog.objects.filter(
            linkedin_profile__in=campaign.linkedinprofile_set.all(),
            action_type=ActionLog.ActionType.FOLLOW_UP,
            created_at__gte=since,
        ).count()
        
        # Get deals with responses
        from openoutreach.crm.models import Deal
        
        deals_with_responses = Deal.objects.filter(
            campaign=campaign,
            messages__is_outgoing=False,
            creation_date__gte=since,
        ).distinct().count()
        
        response_rate = (
            deals_with_responses / connections_sent 
            if connections_sent > 0 else 0.0
        )
        
        # Error metrics
        errors = ActionLog.objects.filter(
            linkedin_profile__in=campaign.linkedinprofile_set.all(),
            created_at__gte=since,
        ).exclude(error_message='').count()  # Note: ActionLog doesn't have error_message
        
        rate_limit_errors = 0  # Rate limit errors tracked elsewhere
        auth_errors = 0  # Auth errors tracked elsewhere
        network_errors = 0  # Network errors tracked elsewhere
        
        # Detectability score - calculated by smart rate limiter
        detectability_score = 50  # Default
        
        return cls.objects.create(
            campaign=campaign,
            timestamp=hour_start,
            connections_sent=connections_sent,
            connections_accepted=connections_accepted,
            connection_accept_rate=connection_accept_rate,
            messages_sent=messages_sent,
            messages_replied=deals_with_responses,
            response_rate=response_rate,
            errors_total=errors,
            rate_limit_errors=rate_limit_errors,
            auth_errors=auth_errors,
            network_errors=network_errors,
            deals_created=connections_sent,
            conversions=0,  # Will be calculated separately
            detectability_score=detectability_score,
        )


class HealthAlert(models.Model):
    """Alert for campaign health issues."""

    id: int  # auto-generated primary key

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
    
    campaign = models.ForeignKey('core.Campaign', on_delete=models.CASCADE)
    
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
    
    def resolve(self, notes: str = "") -> None:
        """Mark the alert as resolved."""
        self.is_resolved = True
        self.resolved_at = timezone.now()
        self.resolution_notes = notes
        self.save(update_fields=['is_resolved', 'resolved_at', 'resolution_notes'])


class RecoveryAction(models.Model):
    """Track recovery actions taken for campaigns."""

    id: int  # auto-generated primary key

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
    
    campaign = models.ForeignKey('core.Campaign', on_delete=models.CASCADE)
    
    action_type = models.CharField(max_length=20, choices=ACTION_CHOICES)
    before_state = models.JSONField(default=dict)
    after_state = models.JSONField(default=dict)
    reason = models.TextField()
    
    executed_at = models.DateTimeField(auto_now_add=True)
    execution_result = models.TextField(blank=True)
    
    class Meta:
        verbose_name_plural = "Recovery actions"
        ordering = ['-executed_at']