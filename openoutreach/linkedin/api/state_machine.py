# openoutreach/linkedin/api/state_machine.py
"""
State Machine API endpoints for managing campaign workflow state machines.
"""
from __future__ import annotations

import logging
from typing import Dict, Any

from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from openoutreach.core.models import Campaign
from openoutreach.linkedin.models.state_machine import (
    CampaignStateGraph,
    StateNode,
    StateTransition,
    CampaignState,
    CampaignExecutionLog,
)

logger = logging.getLogger(__name__)


def state_graph_to_dict(state_graph: CampaignStateGraph) -> Dict[str, Any]:
    """Convert CampaignStateGraph to dictionary for JSON response."""
    return {
        "id": state_graph.id,
        "campaign_id": state_graph.campaign.id,
        "campaign_name": state_graph.campaign.name,
        "name": state_graph.name,
        "description": state_graph.description,
        "is_active": state_graph.is_active,
        "is_valid": state_graph.is_valid,
        "validation_errors": state_graph.validation_errors,
        "graph_data": state_graph.graph_data,
        "created_at": state_graph.created_at.isoformat(),
        "updated_at": state_graph.updated_at.isoformat(),
    }


def state_node_to_dict(node: StateNode) -> Dict[str, Any]:
    """Convert StateNode to dictionary for JSON response."""
    return {
        "id": node.id,
        "state_graph_id": node.state_graph.id,
        "name": node.name,
        "node_type": node.node_type,
        "config": node.config,
        "x": node.x,
        "y": node.y,
        "is_active": node.is_active,
        "description": node.description,
        "created_at": node.created_at.isoformat(),
        "updated_at": node.updated_at.isoformat(),
    }


def state_transition_to_dict(transition: StateTransition) -> Dict[str, Any]:
    """Convert StateTransition to dictionary for JSON response."""
    return {
        "id": transition.id,
        "state_graph_id": transition.state_graph.id,
        "source_node_id": transition.source_node.id,
        "source_node_name": transition.source_node.name,
        "target_node_id": transition.target_node.id,
        "target_node_name": transition.target_node.name,
        "condition_type": transition.condition_type,
        "condition_config": transition.condition_config,
        "label": transition.label,
        "order": transition.order,
        "is_active": transition.is_active,
        "created_at": transition.created_at.isoformat(),
        "updated_at": transition.updated_at.isoformat(),
    }


def state_machine_to_dict(state_machine: CampaignState) -> Dict[str, Any]:
    """Convert CampaignState to dictionary for JSON response."""
    return {
        "id": state_machine.id,
        "deal_id": state_machine.deal.id,
        "deal_urn": str(state_machine.deal.lead.urn) if state_machine.deal.lead.urn else None,
        "state_graph_id": state_machine.state_graph.id,
        "state_graph_name": state_machine.state_graph.name,
        "current_node_id": state_machine.current_node.id if state_machine.current_node else None,
        "current_node_name": state_machine.current_node.name if state_machine.current_node else None,
        "previous_nodes": state_machine.previous_nodes,
        "status": state_machine.status,
        "error_message": state_machine.error_message,
        "wait_until": state_machine.wait_until.isoformat() if state_machine.wait_until else None,
        "wait_reason": state_machine.wait_reason,
        "metadata": state_machine.metadata,
        "started_at": state_machine.started_at.isoformat(),
        "completed_at": state_machine.completed_at.isoformat() if state_machine.completed_at else None,
    }


@csrf_exempt
def state_graph_create_view(request, campaign_id: int) -> JsonResponse:
    """Create a new state graph for a campaign."""
    try:
        campaign = Campaign.objects.get(id=campaign_id)
    except Campaign.DoesNotExist:
        return JsonResponse({"error": "Campaign not found"}, status=404)
    
    from openoutreach.linkedin.services.state_machine import StateMachineEngine
    
    if request.method == "POST":
        import json
        data = json.loads(request.body)
        
        # Validate graph data
        name = data.get("name", "Untitled State Graph")
        description = data.get("description", "")
        is_active = data.get("is_active", True)
        graph_data = data.get("graph_data", {"nodes": [], "transitions": []})
        
        state_graph, created = CampaignStateGraph.objects.get_or_create(
            campaign=campaign,
            defaults={
                "name": name,
                "description": description,
                "is_active": is_active,
                "graph_data": graph_data,
            }
        )
        
        if not created:
            state_graph.name = name
            state_graph.description = description
            state_graph.is_active = is_active
            state_graph.graph_data = graph_data
            state_graph.is_valid = False
            state_graph.validation_errors = []
            state_graph.save()
        
        # Validate the graph
        is_valid, errors = StateMachineEngine(state_graph).validate_graph()
        state_graph.is_valid = is_valid
        state_graph.validation_errors = errors
        state_graph.save()
        
        return JsonResponse({
            "success": True,
            "state_graph": state_graph_to_dict(state_graph),
            "validation_errors": errors,
            "created": created,
        })
    
    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
def state_graph_view(request, campaign_id: int) -> JsonResponse:
    """Get state graph details for a campaign."""
    try:
        state_graph = CampaignStateGraph.objects.get(campaign_id=campaign_id)
        return JsonResponse(state_graph_to_dict(state_graph))
    except CampaignStateGraph.DoesNotExist:
        return JsonResponse({
            "error": "State graph not found",
            "default": True,
            "message": "No state graph configured for this campaign",
        }, status=404)


@csrf_exempt
def state_graph_update_view(request, campaign_id: int) -> JsonResponse:
    """Update state graph for a campaign."""
    try:
        state_graph = CampaignStateGraph.objects.get(campaign_id=campaign_id)
    except CampaignStateGraph.DoesNotExist:
        return JsonResponse({"error": "State graph not found"}, status=404)
    
    if request.method == "POST":
        import json
        data = json.loads(request.body)
        
        # Update fields
        if "name" in data:
            state_graph.name = data["name"]
        if "description" in data:
            state_graph.description = data["description"]
        if "is_active" in data:
            state_graph.is_active = data["is_active"]
        if "graph_data" in data:
            state_graph.graph_data = data["graph_data"]
            state_graph.is_valid = False  # Reset validity on update
        
        state_graph.save()
        
        # Re-validate the graph
        from openoutreach.linkedin.services.state_machine import StateMachineEngine
        is_valid, errors = StateMachineEngine(state_graph).validate_graph()
        state_graph.is_valid = is_valid
        state_graph.validation_errors = errors
        state_graph.save()
        
        return JsonResponse({
            "success": True,
            "state_graph": state_graph_to_dict(state_graph),
            "validation_errors": errors,
        })
    
    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
def state_graph_validate_view(request, campaign_id: int) -> JsonResponse:
    """Validate state graph for a campaign."""
    try:
        state_graph = CampaignStateGraph.objects.get(campaign_id=campaign_id)
    except CampaignStateGraph.DoesNotExist:
        return JsonResponse({"error": "State graph not found"}, status=404)
    
    from openoutreach.linkedin.services.state_machine import StateMachineEngine
    is_valid, errors = StateMachineEngine(state_graph).validate_graph()
    
    state_graph.is_valid = is_valid
    state_graph.validation_errors = errors
    state_graph.save()
    
    return JsonResponse({
        "success": True,
        "is_valid": is_valid,
        "errors": errors,
        "warnings": [e for e in errors if e.get("type") != "missing_start" and e.get("type") != "multiple_starts"],
    })


@csrf_exempt
def state_graph_delete_view(request, campaign_id: int) -> JsonResponse:
    """Delete state graph for a campaign."""
    try:
        state_graph = CampaignStateGraph.objects.get(campaign_id=campaign_id)
    except CampaignStateGraph.DoesNotExist:
        return JsonResponse({"error": "State graph not found"}, status=404)
    
    if request.method == "DELETE":
        state_graph.delete()
        return JsonResponse({
            "success": True,
            "message": "State graph deleted successfully",
        })
    
    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
def state_graph_nodes_view(request, campaign_id: int) -> JsonResponse:
    """Get all nodes for a state graph."""
    try:
        state_graph = CampaignStateGraph.objects.get(campaign_id=campaign_id)
    except CampaignStateGraph.DoesNotExist:
        return JsonResponse({"error": "State graph not found"}, status=404)
    
    nodes = StateNode.objects.filter(state_graph=state_graph, is_active=True)
    
    return JsonResponse({
        "nodes": [state_node_to_dict(node) for node in nodes],
        "total": nodes.count(),
    })


@csrf_exempt
def state_graph_transitions_view(request, campaign_id: int) -> JsonResponse:
    """Get all transitions for a state graph."""
    try:
        state_graph = CampaignStateGraph.objects.get(campaign_id=campaign_id)
    except CampaignStateGraph.DoesNotExist:
        return JsonResponse({"error": "State graph not found"}, status=404)
    
    transitions = StateTransition.objects.filter(state_graph=state_graph, is_active=True)
    
    return JsonResponse({
        "transitions": [state_transition_to_dict(t) for t in transitions],
        "total": transitions.count(),
    })


@csrf_exempt
def simulate_state_machine_view(request, campaign_id: int, deal_id: int) -> JsonResponse:
    """Simulate state machine execution for a deal."""
    try:
        campaign = Campaign.objects.get(id=campaign_id)
        deal = campaign.deals.get(id=deal_id)
    except Campaign.DoesNotExist:
        return JsonResponse({"error": "Campaign not found"}, status=404)
    except Campaign.deals.model.DoesNotExist:
        return JsonResponse({"error": "Deal not found"}, status=404)
    
    try:
        state_graph = campaign.state_graph
        if not state_graph or not state_graph.is_active:
            return JsonResponse({
                "success": False,
                "error": "State graph not active",
            }, status=400)
        
        from openoutreach.linkedin.services.state_machine import simulate_state_machine
        result = simulate_state_machine(campaign_id, deal_id)
        
        return JsonResponse(result)
    
    except Exception as e:
        logger.exception(f"Error simulating state machine: {e}")
        return JsonResponse({
            "success": False,
            "error": str(e),
        }, status=500)


@csrf_exempt
def execute_state_machine_step_view(request, state_machine_id: int) -> JsonResponse:
    """Execute one step of a state machine."""
    try:
        state_machine = CampaignState.objects.get(id=state_machine_id)
    except CampaignState.DoesNotExist:
        return JsonResponse({"error": "State machine not found"}, status=404)
    
    if request.method == "POST":
        from openoutreach.linkedin.services.state_machine import StateMachineEngine
        
        # Get session from request (in production, you'd pass the session through)
        session = None  # Will be handled by the caller
        
        engine = StateMachineEngine(state_machine.state_graph)
        success, message = engine.execute_step(state_machine, session)
        
        return JsonResponse({
            "success": success,
            "message": message,
            "state_machine": state_machine_to_dict(state_machine),
        })
    
    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
def state_machine_execution_logs_view(request, state_machine_id: int) -> JsonResponse:
    """Get execution logs for a state machine."""
    try:
        state_machine = CampaignState.objects.get(id=state_machine_id)
    except CampaignState.DoesNotExist:
        return JsonResponse({"error": "State machine not found"}, status=404)
    
    logs = state_machine.execution_logs.all().order_by("-timestamp")
    
    return JsonResponse({
        "state_machine_id": state_machine.id,
        "total": logs.count(),
        "logs": [
            {
                "id": log.id,
                "node_id": log.node.id if log.node else None,
                "node_name": log.node.name if log.node else None,
                "transition_id": log.transition.id if log.transition else None,
                "action": log.action,
                "result": log.result,
                "error": log.error,
                "timestamp": log.timestamp.isoformat(),
            }
            for log in logs[:100]
        ],
    })


@csrf_exempt
def state_machines_view(request, campaign_id: int) -> JsonResponse:
    """Get all state machines for a campaign."""
    try:
        campaign = Campaign.objects.get(id=campaign_id)
    except Campaign.DoesNotExist:
        return JsonResponse({"error": "Campaign not found"}, status=404)
    
    state_machines = CampaignState.objects.filter(
        deal__campaign=campaign
    ).order_by("-started_at")
    
    return JsonResponse({
        "campaign_id": campaign.id,
        "total": state_machines.count(),
        "state_machines": [
            state_machine_to_dict(sm) for sm in state_machines[:50]
        ],
    })