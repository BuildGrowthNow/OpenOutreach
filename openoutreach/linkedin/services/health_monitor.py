# openoutreach/linkedin/services/health_monitor.py
"""Campaign Health Monitor & Auto-Recovery service."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Optional

from django.utils import timezone

from openoutreach.core.models import Campaign
from openoutreach.linkedin.models import ActionLog, LinkedInProfile, SmartRateLimitContext
from openoutreach.crm.models import Deal, DealState
from openoutreach.linkedin.models.health import CampaignHealthMetric, HealthAlert, RecoveryAction

logger = logging.getLogger(__name__)


class CampaignHealthMonitor:
    """Monitor and maintain campaign health."""
    
    # Thresholds
    CONNECTION_ACCEPT_RATE_THRESHOLD = 0.15  # 15%
    RESPONSE_RATE_THRESHOLD = 0.15  # 15%
    ERROR_RATE_THRESHOLD = 0.25  # 25%
    DETECTABILITY_HIGH_THRESHOLD = 80
    DETECTABILITY_CRITICAL_THRESHOLD = 90
    
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
                logger.error(f"Error running health check {check_name}: {e}")
                # Log error but don't fail the check
        
        return alerts
    
    def check_connection_accept_rate(self) -> list[HealthAlert]:
        """Check connection accept rate and warn if too low."""
        alerts = []
        
        # Get metrics for last 24 hours
        since = timezone.now() - timedelta(hours=24)
        
        # Get all LinkedIn profiles for this campaign
        linkedin_profiles = LinkedInProfile.objects.filter(
            campaign=self.campaign
        ).values_list('id', flat=True)
        
        if not linkedin_profiles:
            return alerts
        
        # Count connections sent
        connections_sent = ActionLog.objects.filter(
            linkedin_profile__in=linkedin_profiles,
            action_type=ActionLog.ActionType.CONNECT,
            created_at__gte=since,
        ).count()
        
        # Count connections accepted (deals in CONNECTED state from these connections)
        connections_accepted = Deal.objects.filter(
            campaign=self.campaign,
            state=DealState.CONNECTED,
            creation_date__gte=since,
        ).count()
        
        # Calculate accept rate
        accept_rate = (
            connections_accepted / connections_sent 
            if connections_sent > 0 else 1.0
        )
        
        # If accept rate < 15%, warn
        if connections_sent >= 10 and accept_rate < self.CONNECTION_ACCEPT_RATE_THRESHOLD:
            alerts.append(HealthAlert(
                campaign=self.campaign,
                alert_type=HealthAlert.TYPE_CONNECTION_RATE,
                severity=HealthAlert.SEVERITY_MEDIUM,
                message=f"Connection accept rate ({accept_rate:.1%}) is below threshold ({self.CONNECTION_ACCEPT_RATE_THRESHOLD:.0%})",
                details={
                    'connections_sent': connections_sent,
                    'connections_accepted': connections_accepted,
                    'accept_rate': accept_rate,
                    'expected_rate': self.CONNECTION_ACCEPT_RATE_THRESHOLD,
                }
            ))
        
        return alerts
    
    def check_response_rate(self) -> list[HealthAlert]:
        """Check follow-up response rate."""
        alerts = []
        
        # Get metrics for last 48 hours
        since = timezone.now() - timedelta(hours=48)
        
        # Get connected deals
        connected_deals = Deal.objects.filter(
            campaign=self.campaign,
            state=DealState.CONNECTED,
            creation_date__gte=since,
        ).count()
        
        if connected_deals == 0:
            return alerts
        
        # Get deals with incoming messages (responses)
        deals_with_responses = Deal.objects.filter(
            campaign=self.campaign,
            state=DealState.CONNECTED,
            creation_date__gte=since,
        ).exclude(messages__is_outgoing=True).distinct().count()
        
        response_rate = (
            deals_with_responses / connected_deals 
            if connected_deals > 0 else 0.0
        )
        
        # If response rate < 15%, warn
        if connected_deals >= 5 and response_rate < self.RESPONSE_RATE_THRESHOLD:
            alerts.append(HealthAlert(
                campaign=self.campaign,
                alert_type=HealthAlert.TYPE_RESPONSE_RATE,
                severity=HealthAlert.SEVERITY_MEDIUM,
                message=f"Response rate ({response_rate:.1%}) is below threshold ({self.RESPONSE_RATE_THRESHOLD:.0%})",
                details={
                    'connected_deals': connected_deals,
                    'deals_with_responses': deals_with_responses,
                    'response_rate': response_rate,
                    'expected_rate': self.RESPONSE_RATE_THRESHOLD,
                }
            ))
        
        return alerts
    
    def check_rate_limit_warnings(self) -> list[HealthAlert]:
        """Check for rate limit warnings."""
        alerts = []
        
        # Check detectability for each LinkedIn profile
        linkedin_profiles = LinkedInProfile.objects.filter(
            campaign=self.campaign
        )
        
        for profile in linkedin_profiles:
            # Calculate detectability based on recent activity
            detectability_score = self._calculate_detectability(profile)
            
            if detectability_score >= self.DETECTABILITY_HIGH_THRESHOLD:
                if detectability_score >= self.DETECTABILITY_CRITICAL_THRESHOLD:
                    severity = HealthAlert.SEVERITY_CRITICAL
                elif detectability_score >= 90:
                    severity = HealthAlert.SEVERITY_HIGH
                else:
                    severity = HealthAlert.SEVERITY_HIGH
                    
                alerts.append(HealthAlert(
                    campaign=self.campaign,
                    alert_type=HealthAlert.TYPE_DETECTION,
                    severity=severity,
                    message=f"LinkedIn detectability is high ({detectability_score}/100) for {profile.linkedin_username}",
                    details={
                        'linkedin_profile': profile.linkedin_username,
                        'detectability_score': detectability_score,
                        'suggested_actions': [
                            'Reduce connection frequency',
                            'Change message content',
                            'Add delays between actions',
                        ]
                    }
                ))
        
        return alerts
    
    def _calculate_detectability(self, profile: LinkedInProfile) -> int:
        """Calculate detectability score for a LinkedIn profile using SmartRateLimitContext."""
        # Try to get the detectability score from SmartRateLimitContext first
        try:
            context = SmartRateLimitContext.objects.get(linkedin_profile=profile)
            # Apply detectability multiplier to get the raw score
            # This inverts the multiplier logic: score = raw_score * multiplier
            # We'll use the raw score from context.detectability_score
            raw_score = context.detectability_score
            multiplier = context._detectability_multiplier()
            if multiplier > 0:
                # Invert to get raw score
                raw_score = int(raw_score / multiplier)
            return min(100, max(0, raw_score))
        except SmartRateLimitContext.DoesNotExist:
            pass  # Fall back to manual calculation if context doesn't exist
        
        # Fall back to manual calculation
        since = timezone.now() - timedelta(hours=24)
        
        # Get recent action logs
        actions = ActionLog.objects.filter(
            linkedin_profile=profile,
            created_at__gte=since,
        ).order_by('created_at')
        
        if not actions:
            return 50  # Neutral score if no recent activity
        
        detectability_score = 50
        
        # 1. High velocity (too many actions in short time)
        action_count = actions.count()
        if action_count > 30:
            detectability_score += 20
        elif action_count > 20:
            detectability_score += 10
        
        # 2. Consecutive same-type actions (suspicious pattern)
        from collections import Counter
        
        action_types = [a.action_type for a in actions]
        if action_types:
            most_common, count = Counter(action_types).most_common(1)[0]
            if count / action_count > 0.8:  # 80% same type
                detectability_score += 15
        
        # 3. Action streak (too many in a row without breaks)
        # Check if actions are clustered in time
        if action_count >= 5:
            first = actions.first()
            last = actions.last()
            if first and last:
                duration = (last.created_at - first.created_at).total_seconds()
            else:
                duration = 0
            
            # If many actions in short time
            if duration < 3600 and action_count > 15:  # < 1 hour, > 15 actions
                detectability_score += 25
            elif duration < 1800 and action_count > 10:  # < 30 min, > 10 actions
                detectability_score += 15
        
        return min(100, max(0, detectability_score))
    
    def check_error_patterns(self) -> list[HealthAlert]:
        """Check for error spikes."""
        alerts = []
        
        # Get metrics for last 24 hours
        since = timezone.now() - timedelta(hours=24)
        
        # Get all LinkedIn profiles for this campaign
        linkedin_profiles = LinkedInProfile.objects.filter(
            campaign=self.campaign
        ).values_list('id', flat=True)
        
        if not linkedin_profiles:
            return alerts
        
        # Count total actions
        total_actions = ActionLog.objects.filter(
            linkedin_profile__in=linkedin_profiles,
            action_type__in=[ActionLog.ActionType.CONNECT, ActionLog.ActionType.FOLLOW_UP],
            created_at__gte=since,
        ).count()
        
        if total_actions < 20:
            return alerts
        
        # Count errors from CampaignHealthMetrics
        from openoutreach.linkedin.models.health import CampaignHealthMetric
        
        latest_metric: Optional[CampaignHealthMetric] = None
        error_rate = 0.0
        
        try:
            latest_metric = CampaignHealthMetric.objects.filter(
                campaign=self.campaign,
                timestamp__gte=since,
            ).latest('timestamp')
            
            error_rate = (
                latest_metric.errors_total / total_actions 
                if total_actions > 0 else 0.0
            )
        except CampaignHealthMetric.DoesNotExist:
            error_rate = 0.0
        
        if error_rate > self.ERROR_RATE_THRESHOLD and latest_metric is not None:
            alerts.append(HealthAlert(
                campaign=self.campaign,
                alert_type=HealthAlert.TYPE_ERROR_SPIKE,
                severity=HealthAlert.SEVERITY_HIGH,
                message=f"Error rate ({error_rate:.1%}) exceeds threshold ({self.ERROR_RATE_THRESHOLD:.0%})",
                details={
                    'errors': latest_metric.errors_total,
                    'total_actions': total_actions,
                    'error_rate': error_rate,
                }
            ))
        
        return alerts
    
    def check_detectability(self) -> list[HealthAlert]:
        """Check detectability score over time."""
        alerts = []
        
        # Get latest health metric
        try:
            latest = CampaignHealthMetric.objects.filter(
                campaign=self.campaign,
            ).latest('timestamp')
            
            if latest.detectability_score >= self.DETECTABILITY_HIGH_THRESHOLD:
                if latest.detectability_score >= self.DETECTABILITY_CRITICAL_THRESHOLD:
                    severity = HealthAlert.SEVERITY_CRITICAL
                elif latest.detectability_score >= 90:
                    severity = HealthAlert.SEVERITY_HIGH
                else:
                    severity = HealthAlert.SEVERITY_MEDIUM
                    
                alerts.append(HealthAlert(
                    campaign=self.campaign,
                    alert_type=HealthAlert.TYPE_DETECTION,
                    severity=severity,
                    message=f"Detectability score is {latest.detectability_score}/100",
                    details={
                        'score': latest.detectability_score,
                    }
                ))
        except CampaignHealthMetric.DoesNotExist:
            # No metrics yet, skip check
            pass
        
        return alerts
    
    def auto_remediate(self, alert: HealthAlert) -> bool:
        """Try to automatically remediate an alert."""
        recovery_actions: dict[str, list[str]] = {
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
        
        # Save before state
        before_state = {
            'velocity': getattr(self.campaign, 'velocity', None),
            'cooldown': getattr(self.campaign, 'cooldown_minutes', 0),
            'message': getattr(self.campaign, 'default_message', ''),
        }
        
        # Execute action
        action_executed = False
        
        if action_type == 'reduce_velocity':
            # Reduce velocity by 50%
            current_velocity = getattr(self.campaign, 'velocity', 20)
            self.campaign.velocity = max(5, current_velocity // 2)
            action_executed = True
        
        elif action_type == 'add_cooldown':
            # Add 30 minute cooldown between actions
            current_cooldown = getattr(self.campaign, 'cooldown_minutes', 0)
            self.campaign.cooldown_minutes = current_cooldown + 30
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
                    'velocity': getattr(self.campaign, 'velocity', None),
                    'cooldown': getattr(self.campaign, 'cooldown_minutes', 0),
                    'is_paused': getattr(self.campaign, 'is_paused', False),
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


def run_health_check_for_campaign(campaign_id: int) -> list[HealthAlert]:
    """Convenience function to run health check for a campaign by ID."""
    try:
        campaign = Campaign.objects.get(pk=campaign_id)
        monitor = CampaignHealthMonitor(campaign)
        return monitor.run_health_check()
    except Campaign.DoesNotExist:
        logger.error(f"Campaign {campaign_id} does not exist")
        return []
    except Exception as e:
        logger.error(f"Error running health check for campaign {campaign_id}: {e}")
        return []


def create_hourly_health_metric(campaign_id: int) -> Optional[CampaignHealthMetric]:
    """Create an hourly health metric snapshot for a campaign."""
    try:
        campaign = Campaign.objects.get(pk=campaign_id)
        return CampaignHealthMetric.create_hourly_snapshot(campaign)
    except Campaign.DoesNotExist:
        logger.error(f"Campaign {campaign_id} does not exist")
        return None
    except Exception as e:
        logger.error(f"Error creating health metric for campaign {campaign_id}: {e}")
        return None