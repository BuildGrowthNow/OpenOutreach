"""
Analytics API Router - Overview dashboard with filters

FastAPI endpoints for aggregated analytics across campaigns.
Replaces Django AnalyticsOverviewView.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from openoutreach.api_v2.dependencies_v2 import get_current_user
from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.mongodb import models
from openoutreach.crm.models.deal import DealState

logger = logging.getLogger(__name__)

router = APIRouter()


# ========== Pydantic Schemas ==========

class PipelineStats(BaseModel):
    """Pipeline stage counts."""
    qualified: int = 0
    ready_to_connect: int = 0
    pending: int = 0
    connected: int = 0
    completed: int = 0
    failed: int = 0
    no_email: int = 0


class OverviewStats(BaseModel):
    """Overview statistics."""
    connections_sent: int = Field(default=0, serialization_alias="connectionsSent")
    connections_accepted: int = Field(default=0, serialization_alias="connectionsAccepted")
    connection_accept_rate: float = Field(default=0.0, serialization_alias="connectionAcceptRate")
    messages_sent: int = Field(default=0, serialization_alias="messagesSent")
    messages_replied: int = Field(default=0, serialization_alias="messagesReplied")
    response_rate: float = Field(default=0.0, serialization_alias="responseRate")
    conversions: int = 0
    conversion_rate: float = Field(default=0.0, serialization_alias="conversionRate")


class OverviewTotals(BaseModel):
    """Overview totals."""
    leads: int = 0
    qualified: int = 0
    ready_to_connect: int = Field(default=0, serialization_alias="readyToConnect")
    connected: int = 0
    pending: int = 0
    failed: int = 0
    no_email: int = Field(default=0, serialization_alias="noEmail")
    connection_accept_rate: float = Field(default=0.0, serialization_alias="connectionAcceptRate")
    response_rate: float = Field(default=0.0, serialization_alias="responseRate")
    conversion_rate: float = Field(default=0.0, serialization_alias="conversionRate")


class CampaignStats(BaseModel):
    """Campaign-specific statistics."""
    total_leads: int = Field(default=0, serialization_alias="totalLeads")
    active_leads: int = Field(default=0, serialization_alias="activeLeads")
    qualified: int = 0
    ready_to_connect: int = Field(default=0, serialization_alias="readyToConnect")
    pending: int = 0
    connected: int = 0
    completed: int = 0
    failed: int = 0
    no_email: int = Field(default=0, serialization_alias="noEmail")
    connections_sent: int = Field(default=0, serialization_alias="connectionsSent")
    connections_accepted: int = Field(default=0, serialization_alias="connectionsAccepted")
    messages_sent: int = Field(default=0, serialization_alias="messagesSent")
    messages_replied: int = Field(default=0, serialization_alias="messagesReplied")
    responses: int = 0
    connection_accept_rate: float = Field(default=0.0, serialization_alias="connectionAcceptRate")
    response_rate: float = Field(default=0.0, serialization_alias="responseRate")
    conversion_rate: float = Field(default=0.0, serialization_alias="conversionRate")


class CampaignOverview(BaseModel):
    """Campaign overview with stats."""
    id: str
    name: str
    description: str = ""
    status: str
    stats: CampaignStats


class AnalyticsOverviewResponse(BaseModel):
    """Analytics overview response."""
    period: str
    stats: OverviewStats
    pipeline: PipelineStats
    totals: OverviewTotals
    campaigns: list[CampaignOverview]
    data: dict  # Duplicate root-level data for backward compatibility

    class Config:
        populate_by_name = True


# ========== Helper Functions ==========

def _calculate_period_days(period: str) -> int:
    """Convert period string to number of days."""
    period_map = {
        "7d": 7,
        "30d": 30,
        "90d": 90,
    }
    return period_map.get(period, 30)


def _calculate_rate(numerator: int, denominator: int) -> float:
    """Calculate percentage rate with zero-safe division."""
    if denominator == 0:
        return 0.0
    return round((numerator / denominator * 100), 2)


def _get_deals_by_state(campaign_id: str, state: str) -> int:
    """Count deals in a specific state for a campaign."""
    deals_collection = get_mongodb_collection("deals")
    if deals_collection is None:
        return 0

    try:
        return deals_collection.count_documents({
            "campaign_id": campaign_id,
            "state": state
        })
    except Exception as e:
        logger.error(f"Failed to count deals for state '{state}': {e}")
        return 0


def _get_action_logs_count(campaign_id: str, action_type: str, since: datetime) -> int:
    """Count action logs for a campaign, action type, and time range."""
    action_logs_collection = get_mongodb_collection("action_logs")
    if action_logs_collection is None:
        return 0

    try:
        return action_logs_collection.count_documents({
            "campaign_id": campaign_id,
            "action_type": action_type,
            "status": {"$nin": ["failed", "error"]},
            "created_at": {"$gte": since}
        })
    except Exception as e:
        logger.error(f"Failed to count action logs for type '{action_type}': {e}")
        return 0


def _get_messages_replied_count(campaign_id: str, since: datetime) -> int:
    """Count distinct deals with inbound messages in time range."""
    messages_collection = get_mongodb_collection("chat_messages")
    if messages_collection is None:
        return 0

    try:
        # Get deals that have inbound messages (is_outgoing=False)
        pipeline = [
            {
                "$match": {
                    "deal_id": {"$exists": True},
                    "is_outgoing": False,
                    "creation_date": {"$gte": since}
                }
            },
            {
                "$lookup": {
                    "from": "deals",
                    "localField": "deal_id",
                    "foreignField": "_id",
                    "as": "deal"
                }
            },
            {"$unwind": "$deal"},
            {
                "$match": {
                    "deal.campaign_id": campaign_id
                }
            },
            {
                "$group": {
                    "_id": "$deal_id"
                }
            },
            {
                "$count": "total"
            }
        ]

        result = list(messages_collection.aggregate(pipeline))
        return result[0]["total"] if result else 0
    except Exception as e:
        logger.error(f"Failed to count messages replied: {e}")
        return 0


# ========== Endpoints ==========

@router.get("/overview", response_model=AnalyticsOverviewResponse, response_model_by_alias=True)
async def get_analytics_overview(
    user_id: str = Depends(get_current_user),
    campaign_id: Optional[str] = Query(None, description="Filter by specific campaign ID"),
    period: str = Query("30d", pattern="^(7d|30d|90d)$", description="Time period (7d, 30d, 90d)")
):
    """
    Get aggregated analytics across all campaigns or a specific campaign.

    Returns overview stats, pipeline counts, totals, and per-campaign breakdowns.
    Supports filtering by campaign_id and time period.

    **Multi-tenant**: Filters by user_id from authentication.
    """
    # Get campaigns for user
    campaigns_collection = get_mongodb_collection("campaigns")
    if campaigns_collection is None:
        return AnalyticsOverviewResponse(
            period=period,
            stats=OverviewStats(),
            pipeline=PipelineStats(),
            totals=OverviewTotals(),
            campaigns=[],
            data={}
        )

    # Build campaign query
    campaign_query = {"user_id": user_id}
    if campaign_id:
        campaign_query["_id"] = campaign_id

    try:
        campaigns = []
        for data in campaigns_collection.find(campaign_query).sort("name", 1):
            campaigns.append(models.Campaign.from_dict(data))
    except Exception as e:
        logger.error(f"Failed to fetch campaigns: {e}")
        campaigns = []

    if not campaigns:
        return AnalyticsOverviewResponse(
            period=period,
            stats=OverviewStats(),
            pipeline=PipelineStats(),
            totals=OverviewTotals(),
            campaigns=[],
            data={}
        )

    # Calculate time range
    period_days = _calculate_period_days(period)
    since = datetime.now(timezone.utc) - timedelta(days=period_days)

    # Get deals collection
    deals_collection = get_mongodb_collection("deals")
    action_logs_collection = get_mongodb_collection("action_logs")
    leads_collection = get_mongodb_collection("leads")

    if deals_collection is None or action_logs_collection is None:
        return AnalyticsOverviewResponse(
            period=period,
            stats=OverviewStats(),
            pipeline=PipelineStats(),
            totals=OverviewTotals(),
            campaigns=[],
            data={}
        )

    campaign_ids = [c._id for c in campaigns]

    # ========== Calculate Totals Across All Campaigns ==========

    # Pipeline totals (all deals, not time-filtered)
    total_qualified = deals_collection.count_documents({
        "campaign_id": {"$in": campaign_ids},
        "state": DealState.QUALIFIED.value
    })
    total_ready_to_connect = deals_collection.count_documents({
        "campaign_id": {"$in": campaign_ids},
        "state": DealState.READY_TO_CONNECT.value
    })
    total_pending = deals_collection.count_documents({
        "campaign_id": {"$in": campaign_ids},
        "state": DealState.PENDING.value
    })
    total_connected = deals_collection.count_documents({
        "campaign_id": {"$in": campaign_ids},
        "state": DealState.CONNECTED.value
    })
    total_completed = deals_collection.count_documents({
        "campaign_id": {"$in": campaign_ids},
        "state": DealState.COMPLETED.value
    })
    total_failed = deals_collection.count_documents({
        "campaign_id": {"$in": campaign_ids},
        "state": DealState.FAILED.value
    })
    total_no_email = deals_collection.count_documents({
        "campaign_id": {"$in": campaign_ids},
        "state": DealState.NO_EMAIL.value
    })

    # Stats totals (time-filtered)
    total_connections_sent = action_logs_collection.count_documents({
        "campaign_id": {"$in": campaign_ids},
        "action_type": "connect",
        "status": {"$nin": ["failed", "error"]},
        "created_at": {"$gte": since}
    })
    total_connections_accepted = deals_collection.count_documents({
        "campaign_id": {"$in": campaign_ids},
        "state": DealState.CONNECTED.value,
        "creation_date": {"$gte": since}
    })
    total_messages_sent = action_logs_collection.count_documents({
        "campaign_id": {"$in": campaign_ids},
        "action_type": "follow_up",
        "status": {"$nin": ["failed", "error"]},
        "created_at": {"$gte": since}
    })

    # Calculate messages replied (distinct deals with inbound messages)
    messages_collection = get_mongodb_collection("chat_messages")
    total_messages_replied = 0
    if messages_collection is not None:
        try:
            pipeline = [
                {
                    "$match": {
                        "is_outgoing": False,
                        "creation_date": {"$gte": since}
                    }
                },
                {
                    "$lookup": {
                        "from": "deals",
                        "localField": "deal_id",
                        "foreignField": "_id",
                        "as": "deal"
                    }
                },
                {"$unwind": "$deal"},
                {
                    "$match": {
                        "deal.campaign_id": {"$in": campaign_ids}
                    }
                },
                {
                    "$group": {
                        "_id": "$deal_id"
                    }
                },
                {"$count": "total"}
            ]
            result = list(messages_collection.aggregate(pipeline))
            total_messages_replied = result[0]["total"] if result else 0
        except Exception as e:
            logger.error(f"Failed to count total messages replied: {e}")

    total_conversions = deals_collection.count_documents({
        "campaign_id": {"$in": campaign_ids},
        "state": DealState.COMPLETED.value,
        "creation_date": {"$gte": since}
    })

    # Calculate rates
    connection_accept_rate = _calculate_rate(total_connections_accepted, total_connections_sent)
    response_rate = _calculate_rate(total_messages_replied, total_messages_sent)
    conversion_rate = _calculate_rate(total_conversions, total_qualified)

    # ========== Build Per-Campaign Stats ==========

    campaigns_data = []
    for campaign in campaigns:
        # Pipeline counts (not time-filtered)
        qualified = _get_deals_by_state(campaign._id, DealState.QUALIFIED.value)
        ready_to_connect = _get_deals_by_state(campaign._id, DealState.READY_TO_CONNECT.value)
        pending = _get_deals_by_state(campaign._id, DealState.PENDING.value)
        connected_current = _get_deals_by_state(campaign._id, DealState.CONNECTED.value)
        completed_current = _get_deals_by_state(campaign._id, DealState.COMPLETED.value)
        failed = _get_deals_by_state(campaign._id, DealState.FAILED.value)
        no_email = _get_deals_by_state(campaign._id, DealState.NO_EMAIL.value)

        total_leads = deals_collection.count_documents({"campaign_id": campaign._id})
        active_leads = qualified + ready_to_connect + pending + connected_current

        # Action counts (time-filtered)
        connections_sent = _get_action_logs_count(campaign._id, "connect", since)
        connections_accepted = deals_collection.count_documents({
            "campaign_id": campaign._id,
            "state": DealState.CONNECTED.value,
            "creation_date": {"$gte": since}
        })
        messages_sent = _get_action_logs_count(campaign._id, "follow_up", since)
        messages_replied = _get_messages_replied_count(campaign._id, since)
        conversions = deals_collection.count_documents({
            "campaign_id": campaign._id,
            "state": DealState.COMPLETED.value,
            "creation_date": {"$gte": since}
        })

        # Calculate campaign rates
        campaign_connection_rate = _calculate_rate(connections_accepted, connections_sent)
        campaign_response_rate = _calculate_rate(messages_replied, messages_sent)
        campaign_conversion_rate = _calculate_rate(conversions, qualified)

        campaigns_data.append(
            CampaignOverview(
                id=campaign._id,
                name=campaign.name,
                description=getattr(campaign, 'description', '') or "",
                status=campaign.status,
                stats=CampaignStats(
                    total_leads=total_leads,
                    active_leads=active_leads,
                    qualified=qualified,
                    ready_to_connect=ready_to_connect,
                    pending=pending,
                    connected=connected_current,
                    completed=completed_current,
                    failed=failed,
                    no_email=no_email,
                    connections_sent=connections_sent,
                    connections_accepted=connections_accepted,
                    messages_sent=messages_sent,
                    messages_replied=messages_replied,
                    responses=messages_replied,
                    connection_accept_rate=campaign_connection_rate,
                    response_rate=campaign_response_rate,
                    conversion_rate=campaign_conversion_rate,
                )
            )
        )

    # ========== Build Response ==========

    pipeline = PipelineStats(
        qualified=total_qualified,
        ready_to_connect=total_ready_to_connect,
        pending=total_pending,
        connected=total_connected,
        completed=total_completed,
        failed=total_failed,
        no_email=total_no_email,
    )

    stats = OverviewStats(
        connections_sent=total_connections_sent,
        connections_accepted=total_connections_accepted,
        connection_accept_rate=connection_accept_rate,
        messages_sent=total_messages_sent,
        messages_replied=total_messages_replied,
        response_rate=response_rate,
        conversions=total_conversions,
        conversion_rate=conversion_rate,
    )

    total_leads = (
        leads_collection.count_documents({"user_id": user_id})
        if leads_collection is not None
        else 0
    )

    totals = OverviewTotals(
        leads=total_leads,
        qualified=total_qualified,
        ready_to_connect=total_ready_to_connect,
        connected=total_connected,
        pending=total_pending,
        failed=total_failed,
        no_email=total_no_email,
        connection_accept_rate=connection_accept_rate,
        response_rate=response_rate,
        conversion_rate=conversion_rate,
    )

    # Duplicate data at root level for backward compatibility
    data_dict = {
        "period": period,
        "stats": stats.model_dump(by_alias=True),
        "pipeline": pipeline.model_dump(),
        "totals": totals.model_dump(by_alias=True),
        "campaigns": [c.model_dump(by_alias=True) for c in campaigns_data],
    }

    return AnalyticsOverviewResponse(
        period=period,
        stats=stats,
        pipeline=pipeline,
        totals=totals,
        campaigns=campaigns_data,
        data=data_dict,
    )


@router.get("/activity")
async def get_recent_activity(
    user_id: str = Depends(get_current_user),
    limit: int = Query(10, ge=1, le=50),
):
    """Recent activity feed across all campaigns for the current user."""
    action_logs_collection = get_mongodb_collection("action_logs")
    if action_logs_collection is None:
        return {"data": []}

    # Scope by user's campaign_ids — action_logs don't store user_id directly
    campaigns_collection = get_mongodb_collection("campaigns")
    user_campaign_ids: list[str] = []
    if campaigns_collection is not None:
        user_campaign_ids = [
            str(doc["_id"])
            for doc in campaigns_collection.find({"user_id": user_id}, {"_id": 1})
        ]

    if not user_campaign_ids:
        return {"data": []}

    logs = list(
        action_logs_collection.find({"campaign_id": {"$in": user_campaign_ids}})
        .sort("created_at", -1)
        .limit(limit)
    )

    # Build a campaign name lookup for the returned logs
    campaign_ids = list({log.get("campaign_id") for log in logs if log.get("campaign_id")})
    campaign_names: dict[str, str] = {}
    if campaign_ids and campaigns_collection is not None:
        for doc in campaigns_collection.find({"_id": {"$in": campaign_ids}}, {"_id": 1, "name": 1}):
            campaign_names[str(doc["_id"])] = doc.get("name", "")

    entries = []
    for log in logs:
        details = log.get("details") or {}
        campaign_id = log.get("campaign_id", "")
        entries.append({
            "id": str(log.get("_id", "")),
            "type": log.get("action_type", ""),
            "status": log.get("status", "completed"),
            "error": log.get("error_message") or None,
            "timestamp": (log["created_at"].isoformat() + "Z") if log.get("created_at") else "",
            "campaignId": campaign_id,
            "campaignName": campaign_names.get(campaign_id, ""),
            "leadName": details.get("lead_name") or details.get("public_identifier") or "",
            "details": details,
        })

    return {"data": entries}
