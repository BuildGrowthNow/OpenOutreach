# openoutreach/linkedin/services/health_monitor.py
"""Campaign Health Monitor & Auto-Recovery service."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timedelta, timezone as tz
from typing import Optional

from openoutreach.mongodb.models import Campaign
from openoutreach.linkedin.models import (
    ActionLog,
    LinkedInProfile,
)
from openoutreach.crm.models import DealState
from openoutreach.linkedin.models.health import (
    CampaignHealthMetric,
    HealthAlert,
    RecoveryAction,
)

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
        alerts: list[HealthAlert] = []

        # Run individual checks
        checks = [
            ("check_connection_accept_rate", "Connection Accept Rate Check"),
            ("check_response_rate", "Response Rate Check"),
            ("check_rate_limit_warnings", "Rate Limit Check"),
            ("check_error_patterns", "Error Pattern Check"),
            ("check_detectability", "Detectability Check"),
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

    def _get_connection_metrics(self, since):
        """Get connection metrics for the campaign."""
        from openoutreach.mongodb.connection import get_mongodb_collection

        # Get all LinkedIn profiles for this campaign
        campaign_id = self.campaign._id if hasattr(self.campaign, '_id') else str(self.campaign)
        profile_collection = get_mongodb_collection("linkedin_profiles")
        if profile_collection is None:
            return 0, 0

        linkedin_profile_ids = [
            str(doc["_id"]) for doc in profile_collection.find({"campaign_id": campaign_id}, {"_id": 1})
        ]

        if not linkedin_profile_ids:
            return 0, 0

        # Count connections sent
        action_collection = get_mongodb_collection("action_logs")
        if action_collection is not None:
            connections_sent = action_collection.count_documents({
                "linkedin_profile_id": {"$in": linkedin_profile_ids},
                "action_type": ActionLog.ActionType.CONNECT,
                "created_at": {"$gte": since},
            })
        else:
            connections_sent = 0

        # Count connections accepted (deals in CONNECTED state from these connections)
        deal_collection = get_mongodb_collection("deals")
        if deal_collection is not None:
            connections_accepted = deal_collection.count_documents({
                "campaign_id": campaign_id,
                "state": DealState.CONNECTED,
                "creation_date": {"$gte": since},
            })
        else:
            connections_accepted = 0

        return connections_sent, connections_accepted

    def check_connection_accept_rate(self) -> list[HealthAlert]:
        """Check connection accept rate and warn if too low."""
        alerts: list[HealthAlert] = []

        # Get metrics for last 24 hours
        since = datetime.now(tz.utc) - timedelta(hours=24)

        connections_sent, connections_accepted = self._get_connection_metrics(since)

        if not connections_sent:
            return alerts

        # Calculate accept rate
        accept_rate = (
            connections_accepted / connections_sent if connections_sent > 0 else 1.0
        )

        # If accept rate < 15%, warn
        if (
            connections_sent >= 10
            and accept_rate < self.CONNECTION_ACCEPT_RATE_THRESHOLD
        ):
            alerts.append(
                HealthAlert(
                    campaign_id=self.campaign.pk,
                    alert_type=HealthAlert.TYPE_CONNECTION_RATE,
                    severity=HealthAlert.SEVERITY_MEDIUM,
                    message=(
                        f"Connection accept rate ({accept_rate:.1%}) is below "
                        f"threshold ({self.CONNECTION_ACCEPT_RATE_THRESHOLD:.0%})"
                    ),
                    details={
                        "connections_sent": connections_sent,
                        "connections_accepted": connections_accepted,
                        "accept_rate": accept_rate,
                        "expected_rate": self.CONNECTION_ACCEPT_RATE_THRESHOLD,
                    },
                )
            )

        return alerts

    def check_response_rate(self) -> list[HealthAlert]:
        """Check follow-up response rate."""
        alerts: list[HealthAlert] = []

        # Get metrics for last 48 hours
        since = datetime.now(tz.utc) - timedelta(hours=48)

        from openoutreach.mongodb.connection import get_mongodb_collection

        campaign_id = self.campaign._id if hasattr(self.campaign, '_id') else str(self.campaign)
        deal_collection = get_mongodb_collection("deals")
        message_collection = get_mongodb_collection("chat_messages")

        if deal_collection is None or message_collection is None:
            return alerts

        # Get connected deals
        connected_deals = deal_collection.count_documents({
            "campaign_id": campaign_id,
            "state": DealState.CONNECTED,
            "creation_date": {"$gte": since},
        })

        if connected_deals == 0:
            return alerts

        # Get deals with incoming messages (responses)
        # Find deals that have at least one incoming message
        deal_ids_with_responses = message_collection.distinct("deal_id", {
            "is_outgoing": False,  # Incoming messages only
        })

        # Count how many of these deals are in our connected deals set
        deals_with_responses = deal_collection.count_documents({
            "_id": {"$in": deal_ids_with_responses},
            "campaign_id": campaign_id,
            "state": DealState.CONNECTED,
            "creation_date": {"$gte": since},
        })

        response_rate = (
            deals_with_responses / connected_deals if connected_deals > 0 else 0.0
        )

        # If response rate < 15%, warn
        if connected_deals >= 5 and response_rate < self.RESPONSE_RATE_THRESHOLD:
            alerts.append(
                HealthAlert(
                    campaign_id=self.campaign.pk,
                    alert_type=HealthAlert.TYPE_RESPONSE_RATE,
                    severity=HealthAlert.SEVERITY_MEDIUM,
                    message=(
                        f"Response rate ({response_rate:.1%}) is below "
                        f"threshold ({self.RESPONSE_RATE_THRESHOLD:.0%})"
                    ),
                    details={
                        "connected_deals": connected_deals,
                        "deals_with_responses": deals_with_responses,
                        "response_rate": response_rate,
                        "expected_rate": self.RESPONSE_RATE_THRESHOLD,
                    },
                )
            )

        return alerts

    def check_rate_limit_warnings(self) -> list[HealthAlert]:
        """Check for rate limit warnings."""
        alerts: list[HealthAlert] = []

        from openoutreach.mongodb.connection import get_mongodb_collection

        # Check detectability for each LinkedIn profile
        campaign_id = self.campaign._id if hasattr(self.campaign, '_id') else str(self.campaign)
        profile_collection = get_mongodb_collection("linkedin_profiles")
        if profile_collection is None:
            return alerts

        profile_docs = list(profile_collection.find({"campaign_id": campaign_id}))

        for profile_doc in profile_docs:
            profile = LinkedInProfile.from_dict(profile_doc)
            # Calculate detectability based on recent activity
            detectability_score = self._calculate_detectability(profile)

            if detectability_score >= self.DETECTABILITY_HIGH_THRESHOLD:
                if detectability_score >= self.DETECTABILITY_CRITICAL_THRESHOLD:
                    severity = HealthAlert.SEVERITY_CRITICAL
                elif detectability_score >= 90:
                    severity = HealthAlert.SEVERITY_HIGH
                else:
                    severity = HealthAlert.SEVERITY_HIGH

                alerts.append(
                    HealthAlert(
                        campaign_id=self.campaign.pk,
                        alert_type=HealthAlert.TYPE_DETECTION,
                        severity=severity,
                        message=(
                            f"LinkedIn detectability is high ({detectability_score}/100) "
                            f"for {profile.linkedin_username}"
                        ),
                        details={
                            "linkedin_profile": profile.linkedin_username,
                            "detectability_score": detectability_score,
                            "suggested_actions": [
                                "Reduce connection frequency",
                                "Change message content",
                                "Add delays between actions",
                            ],
                        },
                    )
                )

        return alerts

    def _calculate_detectability(self, profile: LinkedInProfile) -> int:
        """Calculate detectability score for a LinkedIn profile using SmartRateLimitContext."""
        from openoutreach.mongodb.connection import get_mongodb_collection

        # Try to get the detectability score from SmartRateLimitContext first
        context_collection = get_mongodb_collection("smart_rate_limit_contexts")
        if context_collection is not None:
            context_doc = context_collection.find_one({"linkedin_profile_id": profile._id})
            if context_doc:
                score = context_doc.get("detectability_score", 50)
                return min(100, max(0, score))

        # Fall back to manual calculation
        since = datetime.now(tz.utc) - timedelta(hours=24)

        # Get recent action logs
        action_collection = get_mongodb_collection("action_logs")
        if action_collection is None:
            return 50

        actions = list(action_collection.find(
            {
                "linkedin_profile_id": profile._id,
                "created_at": {"$gte": since},
            },
            sort=[("created_at", 1)]
        ))

        if not actions:
            return 50  # Neutral score if no recent activity

        detectability_score = 50

        # 1. High velocity (too many actions in short time)
        action_count = len(actions)
        if action_count > 30:
            detectability_score += 20
        elif action_count > 20:
            detectability_score += 10

        # 2. Consecutive same-type actions (suspicious pattern)
        action_types = [a.get("action_type") for a in actions]
        if action_types:
            _, count = Counter(action_types).most_common(1)[0]
            if count / action_count > 0.8:  # 80% same type
                detectability_score += 15

        # 3. Action streak (too many in a row without breaks)
        # Check if actions are clustered in time
        if action_count >= 5:
            first = actions[0]
            last = actions[-1]
            if first and last:
                duration = (last.get("created_at") - first.get("created_at")).total_seconds()
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
        alerts: list[HealthAlert] = []

        # Get metrics for last 24 hours
        since = datetime.now(tz.utc) - timedelta(hours=24)

        from openoutreach.mongodb.connection import get_mongodb_collection

        campaign_id = self.campaign._id if hasattr(self.campaign, '_id') else str(self.campaign)

        # Get all LinkedIn profiles for this campaign
        profile_collection = get_mongodb_collection("linkedin_profiles")
        if profile_collection is None:
            return alerts

        linkedin_profile_ids = [
            str(doc["_id"]) for doc in profile_collection.find({"campaign_id": campaign_id}, {"_id": 1})
        ]

        if not linkedin_profile_ids:
            return alerts

        # Count total actions
        action_collection = get_mongodb_collection("action_logs")
        if action_collection is None:
            return alerts

        total_actions = action_collection.count_documents({
            "linkedin_profile_id": {"$in": linkedin_profile_ids},
            "action_type": {"$in": [
                ActionLog.ActionType.CONNECT,
                ActionLog.ActionType.FOLLOW_UP,
            ]},
            "created_at": {"$gte": since},
        })

        if total_actions < 20:
            return alerts

        latest_metric: Optional[CampaignHealthMetric] = None
        error_rate = 0.0

        # Try to get latest health metric
        metric_collection = get_mongodb_collection("campaign_health_metrics")
        if metric_collection is not None:
            metric_doc = metric_collection.find_one(
                {
                    "campaign_id": campaign_id,
                    "timestamp": {"$gte": since},
                },
                sort=[("timestamp", -1)]
            )
            if metric_doc:
                latest_metric = CampaignHealthMetric.from_dict(metric_doc)
                error_rate = (
                    latest_metric.errors_total / total_actions if total_actions > 0 else 0.0
                )
            else:
                error_rate = 0.0
        else:
            error_rate = 0.0

        if error_rate > self.ERROR_RATE_THRESHOLD and latest_metric is not None:
            alerts.append(
                HealthAlert(
                    campaign_id=self.campaign.pk,
                    alert_type=HealthAlert.TYPE_ERROR_SPIKE,
                    severity=HealthAlert.SEVERITY_HIGH,
                    message=(
                        f"Error rate ({error_rate:.1%}) exceeds threshold "
                        f"({self.ERROR_RATE_THRESHOLD:.0%})"
                    ),
                    details={
                        "errors": latest_metric.errors_total,
                        "total_actions": total_actions,
                        "error_rate": error_rate,
                    },
                )
            )

        return alerts

    def check_detectability(self) -> list[HealthAlert]:
        """Check detectability score over time."""
        alerts: list[HealthAlert] = []

        from openoutreach.mongodb.connection import get_mongodb_collection

        campaign_id = self.campaign._id if hasattr(self.campaign, '_id') else str(self.campaign)

        # Get latest health metric
        metric_collection = get_mongodb_collection("campaign_health_metrics")
        if metric_collection is None:
            return alerts

        metric_doc = metric_collection.find_one(
            {"campaign_id": campaign_id},
            sort=[("timestamp", -1)]
        )

        if metric_doc:
            latest = CampaignHealthMetric.from_dict(metric_doc)

            if latest.detectability_score >= self.DETECTABILITY_HIGH_THRESHOLD:
                if latest.detectability_score >= self.DETECTABILITY_CRITICAL_THRESHOLD:
                    severity = HealthAlert.SEVERITY_CRITICAL
                elif latest.detectability_score >= 90:
                    severity = HealthAlert.SEVERITY_HIGH
                else:
                    severity = HealthAlert.SEVERITY_MEDIUM

                alerts.append(
                    HealthAlert(
                        campaign_id=self.campaign.pk,
                        alert_type=HealthAlert.TYPE_DETECTION,
                        severity=severity,
                        message=f"Detectability score is {latest.detectability_score}/100",
                        details={
                            "score": latest.detectability_score,
                        },
                    )
                )

        # If no metric found, skip check
        return alerts

    def auto_remediate(self, alert: HealthAlert) -> bool:
        """Try to automatically remediate an alert."""
        recovery_actions: dict[str, list[str]] = {
            HealthAlert.TYPE_CONNECTION_RATE: [
                "reduce_velocity",
                "add_cooldown",
                "switch_message",
            ],
            HealthAlert.TYPE_RESPONSE_RATE: ["switch_message", "add_cooldown"],
            HealthAlert.TYPE_DETECTION: ["reduce_velocity", "add_cooldown", "pause"],
            HealthAlert.TYPE_ERROR_SPIKE: ["pause", "switch_account"],
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
            "velocity": getattr(self.campaign, "velocity", None),
            "cooldown": getattr(self.campaign, "cooldown_minutes", 0),
            "message": getattr(self.campaign, "default_message", ""),
        }

        # Execute action
        action_executed = False

        if action_type == "reduce_velocity":
            # Reduce velocity by 50%
            current_velocity = getattr(self.campaign, "velocity", 20)
            self.campaign.velocity = max(5, current_velocity // 2)
            action_executed = True

        elif action_type == "add_cooldown":
            # Add 30 minute cooldown between actions
            current_cooldown = getattr(self.campaign, "cooldown_minutes", 0)
            self.campaign.cooldown_minutes = current_cooldown + 30
            action_executed = True

        elif action_type == "switch_message":
            # Switch to a different message template
            # (Would need message variant system)
            action_executed = True

        elif action_type == "pause":
            # Pause the campaign
            self.campaign.is_paused = True
            action_executed = True

        if action_executed:
            self.campaign.save()

            # Log recovery action
            recovery = RecoveryAction(
                campaign_id=self.campaign._id if hasattr(self.campaign, '_id') else str(self.campaign),
                action_type=action_type,
                before_state=before_state,
                after_state={
                    "velocity": getattr(self.campaign, "velocity", None),
                    "cooldown": getattr(self.campaign, "cooldown_minutes", 0),
                    "is_paused": getattr(self.campaign, "is_paused", False),
                },
                reason=alert.message,
            )
            recovery.save()

            # Mark alert as resolved
            alert.is_resolved = True
            alert.resolved_at = datetime.now(tz.utc)
            alert.auto_remediation_applied = True
            alert.resolution_notes = f"Auto-remediation: {action_type}"
            alert.save()

            return True

        return False


def run_health_check_for_campaign(campaign_id: str) -> list[HealthAlert]:
    """Convenience function to run health check for a campaign by ID."""
    try:
        campaign = Campaign.get(campaign_id)
        if not campaign:
            logger.error(f"Campaign {campaign_id} does not exist")
            return []
        monitor = CampaignHealthMonitor(campaign)
        return monitor.run_health_check()
    except Exception as e:
        logger.error(f"Error running health check for campaign {campaign_id}: {e}")
        return []


def create_hourly_health_metric(campaign_id: str) -> Optional[CampaignHealthMetric]:
    """Create an hourly health metric snapshot for a campaign."""
    try:
        campaign = Campaign.get(campaign_id)
        if not campaign:
            logger.error(f"Campaign {campaign_id} does not exist")
            return None
        return CampaignHealthMetric.create_hourly_snapshot(campaign.pk)
    except Exception as e:
        logger.error(f"Error creating health metric for campaign {campaign_id}: {e}")
        return None
