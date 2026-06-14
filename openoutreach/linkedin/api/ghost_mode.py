# openoutreach/linkedin/api/ghost_mode.py
"""
Ghost Mode API endpoints for managing ghost campaign simulations.
"""
from __future__ import annotations

import csv
import logging
from typing import Dict, Any

from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from openoutreach.linkedin.models.ghost_mode import GhostCampaign, GhostSimulationLog

logger = logging.getLogger(__name__)


def ghost_campaign_to_dict(ghost_campaign: GhostCampaign) -> Dict[str, Any]:
    """Convert GhostCampaign to dictionary for JSON response."""
    return {
        "id": ghost_campaign.id,
        "name": ghost_campaign.name,
        "description": ghost_campaign.description,
        "is_active": ghost_campaign.is_active,
        "mode_type": ghost_campaign.mode_type,
        "leads_processed": ghost_campaign.leads_processed,
        "connections_simulated": ghost_campaign.connections_simulated,
        "messages_simulated": ghost_campaign.messages_simulated,
        "conversions_simulated": ghost_campaign.conversions_simulated,
        "avg_rating": ghost_campaign.avg_rating,
        "avg_score": ghost_campaign.avg_score,
        "created_at": ghost_campaign.created_at.isoformat(),
        "updated_at": ghost_campaign.updated_at.isoformat(),
    }


@csrf_exempt
def ghost_start_view(request, campaign_id: int) -> JsonResponse:
    """Start ghost mode for a campaign."""
    from openoutreach.core.models import Campaign

    try:
        campaign = Campaign.objects.get(id=campaign_id)
    except Campaign.DoesNotExist:
        return JsonResponse({"error": "Campaign not found"}, status=404)

    # Create or get ghost campaign
    ghost_campaign, created = GhostCampaign.objects.get_or_create(
        campaign=campaign,
        defaults={
            "name": f"{campaign.name} - Ghost Mode",
            "mode_type": GhostCampaign.ModeType.SIMULATION,
            "start_time": timezone.now(),
        },
    )

    return JsonResponse({
        "success": True,
        "ghost_campaign_id": ghost_campaign.id,
        "message": f"Ghost mode started for {campaign.name}",
        "created": created,
    })


@csrf_exempt
def ghost_stop_view(request, campaign_id: int) -> JsonResponse:
    """Stop ghost mode for a campaign."""
    from openoutreach.core.models import Campaign

    try:
        campaign = Campaign.objects.get(id=campaign_id)
    except Campaign.DoesNotExist:
        return JsonResponse({"error": "Campaign not found"}, status=404)

    ghost_campaign = GhostCampaign.objects.filter(
        campaign=campaign, is_active=True
    ).first()
    if not ghost_campaign:
        return JsonResponse({
            "error": "No active ghost mode for this campaign"
        }, status=404)

    ghost_campaign.is_active = False
    ghost_campaign.end_time = timezone.now()
    ghost_campaign.save()

    return JsonResponse({
        "success": True,
        "message": f"Ghost mode stopped for {campaign.name}",
    })


def ghost_campaign_view(request, campaign_id: int) -> JsonResponse:
    """Get ghost campaign details."""
    try:
        ghost_campaign = GhostCampaign.objects.get(id=campaign_id)
    except GhostCampaign.DoesNotExist:
        return JsonResponse({"error": "Ghost campaign not found"}, status=404)

    return JsonResponse(ghost_campaign_to_dict(ghost_campaign))


def ghost_simulations_view(request, campaign_id: int) -> JsonResponse:
    """Get simulation logs for a ghost campaign."""
    try:
        ghost_campaign = GhostCampaign.objects.get(id=campaign_id)
    except GhostCampaign.DoesNotExist:
        return JsonResponse({"error": "Ghost campaign not found"}, status=404)

    # Get logs
    logs = GhostSimulationLog.objects.filter(
        ghost_campaign=ghost_campaign
    ).order_by("-started_at")

    return JsonResponse({
        "campaign_id": ghost_campaign.id,
        "total": logs.count(),
        "simulations": [
            {
                "id": log.id,
                "action_type": log.action_type,
                "target_name": log.target_name,
                "target_url": log.target_url,
                "result_data": log.result_data,
                "rating": log.rating,
                "score": log.score,
                "started_at": log.started_at.isoformat(),
                "completed_at": log.completed_at.isoformat(),
                "simulated_action": log.simulated_action,
            }
            for log in logs[:100]
        ],
    })


def ghost_export_csv_view(request, campaign_id: int) -> HttpResponse:
    """Export simulation results as CSV."""
    try:
        ghost_campaign = GhostCampaign.objects.get(id=campaign_id)
    except GhostCampaign.DoesNotExist:
        return JsonResponse({"error": "Ghost campaign not found"}, status=404)

    response = HttpResponse(
        content_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="ghost-mode-{ghost_campaign.name}.csv"',
        },
    )

    writer = csv.writer(response)
    writer.writerow([
        "timestamp", "action_type", "target_name", "target_url",
        "result_success", "rating", "score", "simulated_action"
    ])

    logs = GhostSimulationLog.objects.filter(ghost_campaign=ghost_campaign)
    for log in logs:
        writer.writerow([
            log.started_at.isoformat(),
            log.action_type,
            log.target_name,
            log.target_url,
            log.result_data.get("success", False),
            log.rating,
            log.score,
            log.simulated_action,
        ])

    return response


def ghost_export_json_view(request, campaign_id: int) -> JsonResponse:
    """Export simulation results as JSON."""
    try:
        ghost_campaign = GhostCampaign.objects.get(id=campaign_id)
    except GhostCampaign.DoesNotExist:
        return JsonResponse({"error": "Ghost campaign not found"}, status=404)

    logs = GhostSimulationLog.objects.filter(ghost_campaign=ghost_campaign)

    return JsonResponse({
        "campaign": ghost_campaign_to_dict(ghost_campaign),
        "total_simulations": logs.count(),
        "simulations": [
            {
                "id": log.id,
                "action_type": log.action_type,
                "target_name": log.target_name,
                "target_url": log.target_url,
                "result_data": log.result_data,
                "rating": log.rating,
                "score": log.score,
                "started_at": log.started_at.isoformat(),
                "completed_at": log.completed_at.isoformat(),
                "simulated_action": log.simulated_action,
            }
            for log in logs
        ],
    })