"""Campaign Health Monitoring API - MongoDB + FastAPI."""

from datetime import datetime, timezone as tz, timedelta
from typing import Any, Dict, List, Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from openoutreach.api_v2.dependencies_v2 import get_current_user, get_campaign_with_access
from openoutreach.linkedin.models import CampaignHealthMetric, HealthAlert, RecoveryAction
from openoutreach.mongodb.connection import get_mongodb_collection

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/campaigns", tags=["Campaign Health"])


# ============================================================================
# Response Models
# ============================================================================

class HealthMetricResponse(BaseModel):
    """Response model for health metric."""
    id: str
    campaign_id: str
    timestamp: datetime
    connections_sent: int
    connections_accepted: int
    connection_accept_rate: float
    messages_sent: int
    messages_replied: int
    response_rate: float
    errors_total: int
    rate_limit_errors: int
    auth_errors: int
    network_errors: int
    deals_created: int
    conversions: int
    detectability_score: int
    created_at: datetime


class HealthAlertResponse(BaseModel):
    """Response model for health alert."""
    id: str
    campaign_id: str
    alert_type: str
    severity: str
    message: str
    details: dict
    is_resolved: bool
    resolved_at: Optional[datetime] = None
    resolution_notes: str
    auto_remediation_applied: bool
    created_at: datetime
    updated_at: datetime


class RecoveryActionResponse(BaseModel):
    """Response model for recovery action."""
    id: str
    campaign_id: str
    action_type: str
    before_state: dict
    after_state: dict
    reason: str
    executed_at: datetime
    execution_result: str


class CampaignHealthSummary(BaseModel):
    """Overall health summary for a campaign."""
    campaign_id: str
    health_score: int  # 0-100
    status: str  # healthy, degraded, critical
    active_alerts: int
    recent_metrics: Optional[HealthMetricResponse] = None
    last_24h_stats: dict


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/{campaign_id}/health", response_model=CampaignHealthSummary)
async def get_campaign_health(
    campaign_id: str,
    user_id: str = Depends(get_current_user),
):
    """
    Get overall health summary for a campaign.

    Returns health score, status, active alerts, and recent metrics.
    """
    # Verify campaign access
    await get_campaign_with_access(campaign_id, user_id)

    # Get most recent metric
    collection = get_mongodb_collection("campaign_health_metrics")
    recent_metric = None

    if collection is not None:
        metric_data = collection.find_one(
            {"campaign_id": campaign_id},
            sort=[("timestamp", -1)]
        )
        if metric_data:
            metric = CampaignHealthMetric.from_dict(metric_data)
            recent_metric = HealthMetricResponse(
                id=metric._id,
                campaign_id=metric.campaign_id,
                timestamp=metric.timestamp,
                connections_sent=metric.connections_sent,
                connections_accepted=metric.connections_accepted,
                connection_accept_rate=metric.connection_accept_rate,
                messages_sent=metric.messages_sent,
                messages_replied=metric.messages_replied,
                response_rate=metric.response_rate,
                errors_total=metric.errors_total,
                rate_limit_errors=metric.rate_limit_errors,
                auth_errors=metric.auth_errors,
                network_errors=metric.network_errors,
                deals_created=metric.deals_created,
                conversions=metric.conversions,
                detectability_score=metric.detectability_score,
                created_at=metric.created_at,
            )

    # Count active alerts
    alert_collection = get_mongodb_collection("health_alerts")
    active_alerts_count = 0
    if alert_collection is not None:
        active_alerts_count = alert_collection.count_documents({
            "campaign_id": campaign_id,
            "is_resolved": False
        })

    # Get 24h stats
    day_ago = datetime.now(tz.utc) - timedelta(days=1)
    last_24h_stats = {}

    if collection is not None:
        metrics_24h = list(collection.find({
            "campaign_id": campaign_id,
            "timestamp": {"$gte": day_ago}
        }).sort("timestamp", 1))

        if metrics_24h:
            total_connections = sum(m.get("connections_sent", 0) for m in metrics_24h)
            total_accepted = sum(m.get("connections_accepted", 0) for m in metrics_24h)
            total_messages = sum(m.get("messages_sent", 0) for m in metrics_24h)
            total_replies = sum(m.get("messages_replied", 0) for m in metrics_24h)
            total_errors = sum(m.get("errors_total", 0) for m in metrics_24h)

            last_24h_stats = {
                "connections_sent": total_connections,
                "connections_accepted": total_accepted,
                "accept_rate": round((total_accepted / total_connections * 100) if total_connections else 0, 1),
                "messages_sent": total_messages,
                "messages_replied": total_replies,
                "response_rate": round((total_replies / total_messages * 100) if total_messages else 0, 1),
                "total_errors": total_errors,
            }

    # Calculate health score (0-100)
    health_score = 100
    if recent_metric:
        # Reduce score for errors
        health_score -= min(recent_metric.errors_total * 5, 30)
        # Reduce score for low accept rate
        if recent_metric.connection_accept_rate < 0.2:
            health_score -= 20
        # Reduce score for low response rate
        if recent_metric.response_rate < 0.1:
            health_score -= 20
        # Reduce score for high detectability
        health_score -= int(recent_metric.detectability_score * 0.3)

    health_score = max(0, health_score)

    # Determine status
    if health_score >= 80:
        status = "healthy"
    elif health_score >= 50:
        status = "degraded"
    else:
        status = "critical"

    return CampaignHealthSummary(
        campaign_id=campaign_id,
        health_score=health_score,
        status=status,
        active_alerts=active_alerts_count,
        recent_metrics=recent_metric,
        last_24h_stats=last_24h_stats,
    )


@router.get("/{campaign_id}/health/metrics", response_model=List[HealthMetricResponse])
async def get_health_metrics(
    campaign_id: str,
    user_id: str = Depends(get_current_user),
    hours: int = Query(default=24, ge=1, le=168, description="Hours of history to fetch"),
):
    """
    Get historical health metrics for a campaign.

    Returns up to 168 hours (7 days) of metrics.
    """
    # Verify campaign access
    await get_campaign_with_access(campaign_id, user_id)

    # Get metrics
    collection = get_mongodb_collection("campaign_health_metrics")
    if collection is None:
        return []

    since = datetime.now(tz.utc) - timedelta(hours=hours)

    metrics = []
    for data in collection.find({
        "campaign_id": campaign_id,
        "timestamp": {"$gte": since}
    }).sort("timestamp", 1):
        metric = CampaignHealthMetric.from_dict(data)
        metrics.append(HealthMetricResponse(
            id=metric._id,
            campaign_id=metric.campaign_id,
            timestamp=metric.timestamp,
            connections_sent=metric.connections_sent,
            connections_accepted=metric.connections_accepted,
            connection_accept_rate=metric.connection_accept_rate,
            messages_sent=metric.messages_sent,
            messages_replied=metric.messages_replied,
            response_rate=metric.response_rate,
            errors_total=metric.errors_total,
            rate_limit_errors=metric.rate_limit_errors,
            auth_errors=metric.auth_errors,
            network_errors=metric.network_errors,
            deals_created=metric.deals_created,
            conversions=metric.conversions,
            detectability_score=metric.detectability_score,
            created_at=metric.created_at,
        ))

    return metrics


@router.get("/{campaign_id}/health/alerts", response_model=List[HealthAlertResponse])
async def get_health_alerts(
    campaign_id: str,
    user_id: str = Depends(get_current_user),
    unresolved_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=100),
):
    """
    Get health alerts for a campaign.

    Shows warnings and errors that require attention.
    """
    # Verify campaign access
    await get_campaign_with_access(campaign_id, user_id)

    # Get alerts
    collection = get_mongodb_collection("health_alerts")
    if collection is None:
        return []

    query: Dict[str, Any] = {"campaign_id": campaign_id}
    if unresolved_only:
        query["is_resolved"] = False

    alerts = []
    for data in collection.find(query).sort("created_at", -1).limit(limit):
        alert = HealthAlert.from_dict(data)
        alerts.append(HealthAlertResponse(
            id=alert._id,
            campaign_id=alert.campaign_id,
            alert_type=alert.alert_type,
            severity=alert.severity,
            message=alert.message,
            details=alert.details,
            is_resolved=alert.is_resolved,
            resolved_at=alert.resolved_at,
            resolution_notes=alert.resolution_notes,
            auto_remediation_applied=alert.auto_remediation_applied,
            created_at=alert.created_at,
            updated_at=alert.updated_at,
        ))

    return alerts


@router.post("/{campaign_id}/health/alerts/{alert_id}/resolve")
async def resolve_health_alert(
    campaign_id: str,
    alert_id: str,
    user_id: str = Depends(get_current_user),
):
    """Mark a health alert as resolved."""
    # Verify campaign access
    await get_campaign_with_access(campaign_id, user_id)

    # Resolve alert
    collection = get_mongodb_collection("health_alerts")
    if collection is None:
        raise HTTPException(status_code=500, detail="Database not available")

    result = collection.update_one(
        {"_id": alert_id, "campaign_id": campaign_id},
        {"$set": {"is_resolved": True, "resolved_at": datetime.now(tz.utc)}}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Alert not found")

    return {"success": True, "message": "Alert resolved"}


@router.get("/{campaign_id}/health/recovery-actions", response_model=List[RecoveryActionResponse])
async def get_recovery_actions(
    campaign_id: str,
    user_id: str = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=100),
):
    """
    Get recovery actions executed for a campaign.

    Shows automated fixes and their results.
    """
    # Verify campaign access
    await get_campaign_with_access(campaign_id, user_id)

    # Get recovery actions
    collection = get_mongodb_collection("recovery_actions")
    if collection is None:
        return []

    actions = []
    for data in collection.find({
        "campaign_id": campaign_id
    }).sort("executed_at", -1).limit(limit):
        action = RecoveryAction.from_dict(data)
        actions.append(RecoveryActionResponse(
            id=action._id,
            campaign_id=action.campaign_id,
            action_type=action.action_type,
            before_state=action.before_state,
            after_state=action.after_state,
            reason=action.reason,
            executed_at=action.executed_at,
            execution_result=action.execution_result,
        ))

    return actions
