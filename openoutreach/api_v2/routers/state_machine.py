"""State Machine API endpoints - MongoDB + FastAPI."""

from datetime import datetime
from typing import List, Optional, Dict, Any
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from openoutreach.api_v2.dependencies_v2 import get_current_user, get_campaign_with_access
from openoutreach.linkedin.models import (
    CampaignStateGraph,
    StateNode,
    StateTransition,
)
from openoutreach.mongodb.connection import get_mongodb_collection

logger = logging.getLogger(__name__)
router = APIRouter(tags=["State Machine"])


# ============================================================================
# Request/Response Models
# ============================================================================

class StateNodeCreate(BaseModel):
    """Request to create a state node."""
    name: str = Field(..., min_length=1, max_length=100)
    node_type: str = Field(..., description="Node type (start, wait, message, gate, etc.)")
    config: Dict[str, Any] = Field(default_factory=dict)
    x: float = Field(default=0.0)
    y: float = Field(default=0.0)
    description: str = Field(default="")


class StateNodeUpdate(BaseModel):
    """Request to update a state node."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    config: Optional[Dict[str, Any]] = None
    x: Optional[float] = None
    y: Optional[float] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class StateNodeResponse(BaseModel):
    """Response model for state node."""
    id: str
    state_graph_id: str
    name: str
    node_type: str
    config: Dict[str, Any]
    x: float
    y: float
    is_active: bool
    description: str
    created_at: datetime
    updated_at: datetime


class StateTransitionCreate(BaseModel):
    """Request to create a state transition."""
    source_node_id: str
    target_node_id: str
    condition_type: str = Field(default="always")
    condition_config: Dict[str, Any] = Field(default_factory=dict)
    label: str = Field(default="")
    order: int = Field(default=0, ge=0)


class StateTransitionUpdate(BaseModel):
    """Request to update a state transition."""
    condition_type: Optional[str] = None
    condition_config: Optional[Dict[str, Any]] = None
    label: Optional[str] = None
    order: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class StateTransitionResponse(BaseModel):
    """Response model for state transition."""
    id: str
    state_graph_id: str
    source_node_id: str
    target_node_id: str
    condition_type: str
    condition_config: Dict[str, Any]
    label: str
    order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CampaignStateGraphCreate(BaseModel):
    """Request to create a campaign state graph."""
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="")


class CampaignStateGraphUpdate(BaseModel):
    """Request to update a campaign state graph."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    graph_data: Optional[Dict[str, Any]] = None


class CampaignStateGraphResponse(BaseModel):
    """Response model for campaign state graph."""
    id: str
    campaign_id: str
    name: str
    description: str
    is_active: bool
    is_valid: bool
    validation_errors: List[str]
    graph_data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class CampaignStateGraphDetail(BaseModel):
    """Detailed response including nodes and transitions."""
    graph: CampaignStateGraphResponse
    nodes: List[StateNodeResponse]
    transitions: List[StateTransitionResponse]


# ============================================================================
# Campaign State Graph Endpoints
# ============================================================================

@router.get("/campaigns/{campaign_id}", response_model=Optional[CampaignStateGraphDetail])
async def get_campaign_state_graph(
    campaign_id: str,
    user_id: str = Depends(get_current_user),
):
    """
    Get state machine graph for a campaign.

    Returns the workflow definition including all nodes and transitions.
    """
    # Verify campaign access
    await get_campaign_with_access(campaign_id, user_id)

    # Get state graph
    graph = CampaignStateGraph.get_by_campaign(campaign_id)
    if not graph:
        return None

    # Get nodes and transitions
    nodes = StateNode.get_by_graph(graph._id)
    transitions = StateTransition.get_by_graph(graph._id)

    return CampaignStateGraphDetail(
        graph=CampaignStateGraphResponse(
            id=graph._id,
            campaign_id=graph.campaign_id,
            name=graph.name,
            description=graph.description,
            is_active=graph.is_active,
            is_valid=graph.is_valid,
            validation_errors=graph.validation_errors,
            graph_data=graph.graph_data,
            created_at=graph.created_at,
            updated_at=graph.updated_at,
        ),
        nodes=[
            StateNodeResponse(
                id=n._id,
                state_graph_id=n.state_graph_id,
                name=n.name,
                node_type=n.node_type,
                config=n.config,
                x=n.x,
                y=n.y,
                is_active=n.is_active,
                description=n.description,
                created_at=n.created_at,
                updated_at=n.updated_at,
            )
            for n in nodes
        ],
        transitions=[
            StateTransitionResponse(
                id=t._id,
                state_graph_id=t.state_graph_id,
                source_node_id=t.source_node_id,
                target_node_id=t.target_node_id,
                condition_type=t.condition_type,
                condition_config=t.condition_config,
                label=t.label,
                order=t.order,
                is_active=t.is_active,
                created_at=t.created_at,
                updated_at=t.updated_at,
            )
            for t in transitions
        ],
    )


@router.post("/campaigns/{campaign_id}", response_model=CampaignStateGraphResponse, status_code=201)
async def create_campaign_state_graph(
    campaign_id: str,
    request: CampaignStateGraphCreate,
    user_id: str = Depends(get_current_user),
):
    """
    Create a state machine graph for a campaign.

    This defines the workflow that all leads in the campaign will follow.
    """
    # Verify campaign access
    await get_campaign_with_access(campaign_id, user_id)

    # Check if graph already exists
    existing = CampaignStateGraph.get_by_campaign(campaign_id)
    if existing:
        raise HTTPException(status_code=400, detail="State graph already exists for this campaign")

    # Create graph
    graph = CampaignStateGraph(
        campaign_id=campaign_id,
        name=request.name,
        description=request.description,
    )
    graph.save()

    return CampaignStateGraphResponse(
        id=graph._id,
        campaign_id=graph.campaign_id,
        name=graph.name,
        description=graph.description,
        is_active=graph.is_active,
        is_valid=graph.is_valid,
        validation_errors=graph.validation_errors,
        graph_data=graph.graph_data,
        created_at=graph.created_at,
        updated_at=graph.updated_at,
    )


@router.patch("/campaigns/{campaign_id}")
async def update_campaign_state_graph(
    campaign_id: str,
    request: CampaignStateGraphUpdate,
    user_id: str = Depends(get_current_user),
):
    """Update campaign state graph."""
    # Verify campaign access
    await get_campaign_with_access(campaign_id, user_id)

    # Get graph
    graph = CampaignStateGraph.get_by_campaign(campaign_id)
    if not graph:
        raise HTTPException(status_code=404, detail="State graph not found")

    # Update fields
    if request.name is not None:
        graph.name = request.name
    if request.description is not None:
        graph.description = request.description
    if request.is_active is not None:
        graph.is_active = request.is_active
    if request.graph_data is not None:
        graph.graph_data = request.graph_data

    graph.save()

    return {"success": True, "message": "State graph updated"}


@router.delete("/campaigns/{campaign_id}", status_code=204)
async def delete_campaign_state_graph(
    campaign_id: str,
    user_id: str = Depends(get_current_user),
):
    """Delete campaign state graph and all associated nodes/transitions."""
    # Verify campaign access
    await get_campaign_with_access(campaign_id, user_id)

    # Get graph
    graph = CampaignStateGraph.get_by_campaign(campaign_id)
    if not graph:
        raise HTTPException(status_code=404, detail="State graph not found")

    # Delete nodes, transitions, and graph
    collection = get_mongodb_collection("state_nodes")
    if collection is not None:
        collection.delete_many({"state_graph_id": graph._id})

    collection = get_mongodb_collection("state_transitions")
    if collection is not None:
        collection.delete_many({"state_graph_id": graph._id})

    collection = get_mongodb_collection("campaign_state_graphs")
    if collection is not None:
        collection.delete_one({"_id": graph._id})

    return None


# ============================================================================
# State Node Endpoints
# ============================================================================

@router.post("/campaigns/{campaign_id}/nodes", response_model=StateNodeResponse, status_code=201)
async def create_state_node(
    campaign_id: str,
    request: StateNodeCreate,
    user_id: str = Depends(get_current_user),
):
    """Create a new node in the state machine."""
    # Verify campaign access
    await get_campaign_with_access(campaign_id, user_id)

    # Get graph
    graph = CampaignStateGraph.get_by_campaign(campaign_id)
    if not graph:
        raise HTTPException(status_code=404, detail="State graph not found. Create it first.")

    # Create node
    node = StateNode(
        state_graph_id=graph._id,
        name=request.name,
        node_type=request.node_type,
        config=request.config,
        x=request.x,
        y=request.y,
        description=request.description,
    )
    node.save()

    return StateNodeResponse(
        id=node._id,
        state_graph_id=node.state_graph_id,
        name=node.name,
        node_type=node.node_type,
        config=node.config,
        x=node.x,
        y=node.y,
        is_active=node.is_active,
        description=node.description,
        created_at=node.created_at,
        updated_at=node.updated_at,
    )


@router.patch("/campaigns/{campaign_id}/nodes/{node_id}")
async def update_state_node(
    campaign_id: str,
    node_id: str,
    request: StateNodeUpdate,
    user_id: str = Depends(get_current_user),
):
    """Update a state node."""
    # Verify campaign access
    await get_campaign_with_access(campaign_id, user_id)

    # Get node
    collection = get_mongodb_collection("state_nodes")
    if collection is None:
        raise HTTPException(status_code=500, detail="Database not available")

    node_data = collection.find_one({"_id": node_id})
    if not node_data:
        raise HTTPException(status_code=404, detail="Node not found")

    node = StateNode.from_dict(node_data)

    # Update fields
    if request.name is not None:
        node.name = request.name
    if request.config is not None:
        node.config = request.config
    if request.x is not None:
        node.x = request.x
    if request.y is not None:
        node.y = request.y
    if request.description is not None:
        node.description = request.description
    if request.is_active is not None:
        node.is_active = request.is_active

    node.save()

    return {"success": True, "message": "Node updated"}


@router.delete("/campaigns/{campaign_id}/nodes/{node_id}", status_code=204)
async def delete_state_node(
    campaign_id: str,
    node_id: str,
    user_id: str = Depends(get_current_user),
):
    """Delete a state node and its transitions."""
    # Verify campaign access
    await get_campaign_with_access(campaign_id, user_id)

    # Delete transitions
    collection = get_mongodb_collection("state_transitions")
    if collection is not None:
        collection.delete_many({"$or": [{"source_node_id": node_id}, {"target_node_id": node_id}]})

    # Delete node
    collection = get_mongodb_collection("state_nodes")
    if collection is not None:
        collection.delete_one({"_id": node_id})

    return None


# ============================================================================
# State Transition Endpoints
# ============================================================================

@router.post("/campaigns/{campaign_id}/transitions", response_model=StateTransitionResponse, status_code=201)
async def create_state_transition(
    campaign_id: str,
    request: StateTransitionCreate,
    user_id: str = Depends(get_current_user),
):
    """Create a new transition between nodes."""
    # Verify campaign access
    await get_campaign_with_access(campaign_id, user_id)

    # Get graph
    graph = CampaignStateGraph.get_by_campaign(campaign_id)
    if not graph:
        raise HTTPException(status_code=404, detail="State graph not found")

    # Verify nodes exist
    collection = get_mongodb_collection("state_nodes")
    if collection is None:
        raise HTTPException(status_code=500, detail="Database not available")

    source_exists = collection.count_documents({"_id": request.source_node_id, "state_graph_id": graph._id}) > 0
    target_exists = collection.count_documents({"_id": request.target_node_id, "state_graph_id": graph._id}) > 0

    if not source_exists or not target_exists:
        raise HTTPException(status_code=400, detail="Source or target node not found in this graph")

    # Create transition
    transition = StateTransition(
        state_graph_id=graph._id,
        source_node_id=request.source_node_id,
        target_node_id=request.target_node_id,
        condition_type=request.condition_type,
        condition_config=request.condition_config,
        label=request.label,
        order=request.order,
    )
    transition.save()

    return StateTransitionResponse(
        id=transition._id,
        state_graph_id=transition.state_graph_id,
        source_node_id=transition.source_node_id,
        target_node_id=transition.target_node_id,
        condition_type=transition.condition_type,
        condition_config=transition.condition_config,
        label=transition.label,
        order=transition.order,
        is_active=transition.is_active,
        created_at=transition.created_at,
        updated_at=transition.updated_at,
    )


@router.patch("/campaigns/{campaign_id}/transitions/{transition_id}")
async def update_state_transition(
    campaign_id: str,
    transition_id: str,
    request: StateTransitionUpdate,
    user_id: str = Depends(get_current_user),
):
    """Update a state transition."""
    # Verify campaign access
    await get_campaign_with_access(campaign_id, user_id)

    # Get transition
    collection = get_mongodb_collection("state_transitions")
    if collection is None:
        raise HTTPException(status_code=500, detail="Database not available")

    trans_data = collection.find_one({"_id": transition_id})
    if not trans_data:
        raise HTTPException(status_code=404, detail="Transition not found")

    transition = StateTransition.from_dict(trans_data)

    # Update fields
    if request.condition_type is not None:
        transition.condition_type = request.condition_type
    if request.condition_config is not None:
        transition.condition_config = request.condition_config
    if request.label is not None:
        transition.label = request.label
    if request.order is not None:
        transition.order = request.order
    if request.is_active is not None:
        transition.is_active = request.is_active

    transition.save()

    return {"success": True, "message": "Transition updated"}


@router.delete("/campaigns/{campaign_id}/transitions/{transition_id}", status_code=204)
async def delete_state_transition(
    campaign_id: str,
    transition_id: str,
    user_id: str = Depends(get_current_user),
):
    """Delete a state transition."""
    # Verify campaign access
    await get_campaign_with_access(campaign_id, user_id)

    # Delete transition
    collection = get_mongodb_collection("state_transitions")
    if collection is not None:
        collection.delete_one({"_id": transition_id})

    return None
