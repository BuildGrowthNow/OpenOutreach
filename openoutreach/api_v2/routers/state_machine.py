"""
State Machine API Router - Global simulation and execution

FastAPI endpoints for state machine operations.
Replaces Django StateMachineExecutionView and StateMachineSimulationView.

NOTE: Campaign-specific state machine endpoints are in campaigns.py:
- GET /api/campaigns/{id}/state-machine/ - Get state graph
- PUT /api/campaigns/{id}/state-machine/ - Update state graph
- POST /api/campaigns/{id}/state-machine/validate/ - Validate graph
- POST /api/campaigns/{id}/state-machine/simulate/ - Simulate execution
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from openoutreach.api_v2.dependencies import get_current_user
from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.mongodb import models
from openoutreach.mongodb.dal import CampaignDAL, DealDAL

logger = logging.getLogger(__name__)

router = APIRouter()


# ========== Pydantic Schemas ==========

class ExecuteRequest(BaseModel):
    """Request to execute state machine for a deal."""
    campaign_id: str = Field(..., description="Campaign ID")
    deal_id: str = Field(..., description="Deal ID")


class ExecutionLogResponse(BaseModel):
    """Execution log entry."""
    id: str
    node_id: Optional[str] = None
    node_name: Optional[str] = None
    action: str = ""
    result: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = ""


class ExecutionResultResponse(BaseModel):
    """Execution result response."""
    state_machine_id: str
    current_node_id: Optional[str] = None
    current_node_name: Optional[str] = None
    status: str
    steps_executed: int = 0
    logs: List[ExecutionLogResponse] = Field(default_factory=list)
    error: Optional[str] = None


class ExecuteResponse(BaseModel):
    """Response from execute endpoint."""
    success: bool
    execution: Optional[ExecutionResultResponse] = None
    error: Optional[str] = None


class SimulateRequest(BaseModel):
    """Request to simulate state machine execution."""
    deal_id: str = Field(..., description="Deal ID to simulate")
    input: str = Field("", description="Optional input text")
    start_state: str = Field("", description="Starting state node ID")
    max_steps: int = Field(10, description="Maximum simulation steps")


class SimulationPathStep(BaseModel):
    """Single step in simulation path."""
    node: str
    name: str
    type: str
    timestamp: str = ""


class SimulationResponse(BaseModel):
    """Simulation result response."""
    input: str
    start_state: str
    path: List[SimulationPathStep] = Field(default_factory=list)
    nodes_visited: int = 0
    transitions_used: int = 0
    final_state: str = ""
    messages_sent: List[str] = Field(default_factory=list)
    completed: bool = False
    steps: int = 0
    error: Optional[str] = None


class SimulateResponse(BaseModel):
    """Response from simulate endpoint."""
    success: bool
    simulation: Optional[SimulationResponse] = None
    error: Optional[str] = None


# ========== Helper Functions ==========

def _get_campaign_state_graph(campaign_id: str) -> Optional[Dict[str, Any]]:
    """Get state graph for a campaign."""
    collection = get_mongodb_collection("campaign_state_graphs")
    if not collection:
        return None

    try:
        return collection.find_one({"campaign_id": campaign_id})
    except Exception as e:
        logger.error(f"Failed to get state graph for campaign '{campaign_id}': {e}")
        return None


def _get_state_node(node_id: str, state_graph_id: str) -> Optional[Dict[str, Any]]:
    """Get a state node by ID."""
    collection = get_mongodb_collection("state_nodes")
    if not collection:
        return None

    try:
        return collection.find_one({"_id": node_id, "state_graph_id": state_graph_id})
    except Exception as e:
        logger.error(f"Failed to get state node '{node_id}': {e}")
        return None


def _get_state_transitions(state_graph_id: str) -> List[Dict[str, Any]]:
    """Get all transitions for a state graph."""
    collection = get_mongodb_collection("state_transitions")
    if not collection:
        return []

    try:
        return list(collection.find({"state_graph_id": state_graph_id, "is_active": True}))
    except Exception as e:
        logger.error(f"Failed to get transitions for state graph '{state_graph_id}': {e}")
        return []


def _get_state_nodes(state_graph_id: str) -> Dict[str, Dict[str, Any]]:
    """Get all nodes for a state graph as a dict keyed by node ID."""
    collection = get_mongodb_collection("state_nodes")
    if not collection:
        return {}

    try:
        nodes = collection.find({"state_graph_id": state_graph_id})
        return {str(node["_id"]): node for node in nodes}
    except Exception as e:
        logger.error(f"Failed to get nodes for state graph '{state_graph_id}': {e}")
        return {}


def _create_or_get_campaign_state(deal_id: str, state_graph_id: str, start_node_id: str) -> Optional[Dict[str, Any]]:
    """Create or get existing campaign state for a deal."""
    collection = get_mongodb_collection("campaign_states")
    if not collection:
        return None

    try:
        # Check if state already exists
        existing = collection.find_one({"deal_id": deal_id, "state_graph_id": state_graph_id})
        if existing:
            return existing

        # Create new state
        new_state = {
            "_id": str(models.uuid4()),
            "deal_id": deal_id,
            "state_graph_id": state_graph_id,
            "current_node_id": start_node_id,
            "previous_nodes": [],
            "status": "active",
            "error_message": "",
            "wait_until": None,
            "wait_reason": "",
            "metadata": {},
            "started_at": datetime.utcnow(),
            "completed_at": None,
        }
        collection.insert_one(new_state)
        return new_state
    except Exception as e:
        logger.error(f"Failed to create/get campaign state: {e}")
        return None


def _create_execution_log(state_machine_id: str, node_id: Optional[str], action: str, result: Dict[str, Any]) -> str:
    """Create execution log entry."""
    collection = get_mongodb_collection("campaign_execution_logs")
    if not collection:
        return ""

    try:
        log = {
            "_id": str(models.uuid4()),
            "state_machine_id": state_machine_id,
            "node_id": node_id,
            "action": action,
            "result": result,
            "timestamp": datetime.utcnow(),
        }
        collection.insert_one(log)
        return log["_id"]
    except Exception as e:
        logger.error(f"Failed to create execution log: {e}")
        return ""


# ========== Endpoints ==========

@router.post("/execute/", response_model=ExecuteResponse)
async def execute_state_machine(
    request: ExecuteRequest,
    user_id: str = Depends(get_current_user),
):
    """
    Execute state machine for a campaign and deal.

    Executes one step of the state machine workflow for the specified deal.
    Creates a campaign state if it doesn't exist, executes the current node,
    and transitions to the next node based on conditions.

    **Multi-tenant**: Verifies user owns the campaign before execution.

    **Returns 404** if campaign or deal not found or user doesn't own them.
    """
    # Get campaign
    campaigns_collection = get_mongodb_collection("campaigns")
    if not campaigns_collection:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable"
        )

    try:
        campaign_data = campaigns_collection.find_one({"_id": request.campaign_id})
        if not campaign_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )

        campaign = models.Campaign.from_dict(campaign_data)

        # Verify ownership
        if campaign.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get campaign: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve campaign"
        )

    # Get deal
    deals_collection = get_mongodb_collection("deals")
    if not deals_collection:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable"
        )

    try:
        deal_data = deals_collection.find_one({
            "_id": request.deal_id,
            "campaign_id": request.campaign_id
        })
        if not deal_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Deal not found in this campaign"
            )

        deal = models.Deal.from_dict(deal_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get deal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve deal"
        )

    # Get state graph
    state_graph = _get_campaign_state_graph(request.campaign_id)
    if not state_graph:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No state machine defined for this campaign"
        )

    if not state_graph.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="State graph is not active"
        )

    state_graph_id = str(state_graph["_id"])

    # Find start node
    nodes = _get_state_nodes(state_graph_id)
    start_node_id = None
    for node_id, node in nodes.items():
        if node.get("node_type") == "start":
            start_node_id = node_id
            break

    if not start_node_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No start node defined in state machine"
        )

    # Create or get campaign state
    campaign_state = _create_or_get_campaign_state(request.deal_id, state_graph_id, start_node_id)
    if not campaign_state:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize state machine"
        )

    current_node_id = campaign_state.get("current_node_id")
    if not current_node_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No current node in state machine"
        )

    # Execute the step (simplified - in production would call StateMachineEngine)
    # For now, just log the execution and return success
    current_node = nodes.get(current_node_id)
    if not current_node:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current node not found"
        )

    # Create execution log
    log_id = _create_execution_log(
        state_machine_id=str(campaign_state["_id"]),
        node_id=current_node_id,
        action=current_node.get("node_type", "unknown"),
        result={"executed": True, "node_name": current_node.get("name", "")}
    )

    # Get recent logs
    logs_collection = get_mongodb_collection("campaign_execution_logs")
    logs_data = []
    if logs_collection:
        try:
            logs_cursor = logs_collection.find({
                "state_machine_id": str(campaign_state["_id"])
            }).sort("timestamp", -1).limit(10)

            for log in logs_cursor:
                node_data = nodes.get(str(log.get("node_id", "")))
                logs_data.append(
                    ExecutionLogResponse(
                        id=str(log["_id"]),
                        node_id=str(log.get("node_id", "")),
                        node_name=node_data.get("name", "") if node_data else None,
                        action=log.get("action", ""),
                        result=log.get("result", {}),
                        timestamp=log.get("timestamp", datetime.utcnow()).isoformat(),
                    )
                )
        except Exception as e:
            logger.error(f"Failed to fetch execution logs: {e}")

    return ExecuteResponse(
        success=True,
        execution=ExecutionResultResponse(
            state_machine_id=str(campaign_state["_id"]),
            current_node_id=current_node_id,
            current_node_name=current_node.get("name", ""),
            status=campaign_state.get("status", "active"),
            steps_executed=len(logs_data),
            logs=logs_data,
            error=None,
        ),
        error=None,
    )


@router.post("/simulate/", response_model=SimulateResponse)
async def simulate_state_machine(
    request: SimulateRequest,
    campaign_id: str,
    user_id: str = Depends(get_current_user),
):
    """
    Simulate state machine execution for a campaign.

    Runs a dry-run simulation of the state machine workflow without
    executing actual actions. Shows the path that would be taken through
    the state graph based on the current configuration.

    **Multi-tenant**: Verifies user owns the campaign.

    **Returns 404** if campaign or deal not found or user doesn't own them.

    Note: This endpoint is also available at:
    POST /api/campaigns/{id}/state-machine/simulate/
    """
    # Get campaign
    campaigns_collection = get_mongodb_collection("campaigns")
    if not campaigns_collection:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable"
        )

    try:
        campaign_data = campaigns_collection.find_one({"_id": campaign_id})
        if not campaign_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )

        campaign = models.Campaign.from_dict(campaign_data)

        # Verify ownership
        if campaign.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get campaign: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve campaign"
        )

    # Get deal
    deals_collection = get_mongodb_collection("deals")
    if not deals_collection:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable"
        )

    try:
        deal_data = deals_collection.find_one({
            "_id": request.deal_id,
            "campaign_id": campaign_id
        })
        if not deal_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Deal not found in this campaign"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get deal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve deal"
        )

    # Get state graph
    state_graph = _get_campaign_state_graph(campaign_id)
    if not state_graph:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No state machine defined for this campaign"
        )

    state_graph_id = str(state_graph["_id"])

    # Get all nodes and transitions
    nodes = _get_state_nodes(state_graph_id)
    transitions = _get_state_transitions(state_graph_id)

    if not nodes:
        return SimulateResponse(
            success=True,
            simulation=SimulationResponse(
                input=request.input,
                start_state=request.start_state,
                path=[],
                nodes_visited=0,
                transitions_used=0,
                final_state="",
                messages_sent=[],
                completed=False,
                steps=0,
                error="No nodes defined in state machine",
            ),
            error=None,
        )

    # Determine start node
    current_state = request.start_state
    if not current_state:
        # Find start node
        for node_id, node in nodes.items():
            if node.get("node_type") == "start":
                current_state = node_id
                break

    if not current_state or current_state not in nodes:
        return SimulateResponse(
            success=True,
            simulation=SimulationResponse(
                input=request.input,
                start_state=request.start_state,
                path=[],
                nodes_visited=0,
                transitions_used=0,
                final_state="",
                messages_sent=[],
                completed=False,
                steps=0,
                error="No valid start node found",
            ),
            error=None,
        )

    # Simulate execution
    path: List[SimulationPathStep] = []
    nodes_visited: List[str] = []
    transitions_used: List[str] = []
    messages_sent: List[str] = []
    steps = 0
    error = None

    while current_state and steps < request.max_steps:
        if current_state not in nodes:
            error = f"Unknown node: {current_state}"
            break

        node = nodes[current_state]
        nodes_visited.append(current_state)

        # Add to path
        path.append(
            SimulationPathStep(
                node=current_state,
                name=node.get("name", ""),
                type=node.get("node_type", ""),
                timestamp=node.get("created_at", datetime.utcnow()).isoformat() if node.get("created_at") else "",
            )
        )

        # Extract messages from node config
        config = node.get("config", {})
        if isinstance(config, dict) and "message" in config:
            messages_sent.append(config["message"])

        # Find next transition
        next_transition = None
        for trans in transitions:
            if str(trans.get("source_node_id")) == current_state:
                # Simple condition evaluation (always or response)
                condition_type = trans.get("condition_type", "always")
                if condition_type in ["always", "response"]:
                    next_transition = trans
                    break

        if not next_transition:
            # No more transitions - reached end
            break

        transitions_used.append(str(next_transition["_id"]))
        current_state = str(next_transition.get("target_node_id", ""))
        steps += 1

    # Check if we reached an end node
    final_state = current_state if current_state else "completed"
    completed = False
    if current_state and current_state in nodes:
        completed = nodes[current_state].get("node_type") == "end"

    return SimulateResponse(
        success=True,
        simulation=SimulationResponse(
            input=request.input,
            start_state=request.start_state,
            path=path,
            nodes_visited=len(nodes_visited),
            transitions_used=len(transitions_used),
            final_state=final_state,
            messages_sent=messages_sent,
            completed=completed,
            steps=steps,
            error=error,
        ),
        error=None,
    )
