# State Machine API Views

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.http import Http404
import logging

from openoutreach.core.models import Campaign
from openoutreach.crm.models import Deal
from openoutreach.linkedin.models import (
    CampaignStateGraph,
    StateNode,
    StateTransition,
    CampaignState,
)

logger = logging.getLogger(__name__)


class StateMachineExecutionView(APIView):
    """
    API view for executing state machine for a campaign and deal.

    POST /api/state-machine/execute - Execute state machine for a deal
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Execute state machine for a campaign and deal.

        Input: { campaign_id: number, deal_id: number }
        """
        campaign_id = request.data.get("campaign_id")
        deal_id = request.data.get("deal_id")

        if not campaign_id or not deal_id:
            return Response(
                {"success": False, "error": "campaign_id and deal_id are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            campaign = Campaign.objects.get(id=campaign_id)
        except Campaign.DoesNotExist:
            return Response(
                {"success": False, "error": "Campaign not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            deal = Deal.objects.get(id=deal_id, campaign=campaign)
        except Deal.DoesNotExist:
            return Response(
                {"success": False, "error": "Deal not found in this campaign"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            state_graph = campaign.state_graph
            if not state_graph.is_active:
                return Response(
                    {"success": False, "error": "State graph is not active"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except CampaignStateGraph.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "error": "No state machine defined for this campaign",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Create or get state machine
        state_machine, created = CampaignState.objects.get_or_create(
            deal=deal,
            state_graph=state_graph,
            defaults={
                "current_node": state_graph.nodes.filter(
                    node_type=StateNode.TYPE_START
                ).first(),
                "status": CampaignState.STATUS_ACTIVE,
            },
        )

        if not state_machine.current_node:
            return Response(
                {"success": False, "error": "No start node defined in state machine"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from openoutreach.linkedin.services.state_machine import StateMachineEngine

        try:
            engine = StateMachineEngine(state_graph)
            success, message = engine.execute_step(state_machine)

            if not success:
                return Response(
                    {"success": False, "error": message},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get execution logs
            logs = state_machine.execution_logs.all().order_by("-timestamp")[:10]

            return Response(
                {
                    "success": True,
                    "execution": {
                        "state_machine_id": state_machine.id,
                        "current_node_id": (
                            state_machine.current_node.id
                            if state_machine.current_node
                            else None
                        ),
                        "current_node_name": (
                            state_machine.current_node.name
                            if state_machine.current_node
                            else None
                        ),
                        "status": state_machine.status,
                        "steps_executed": logs.count(),
                        "logs": [
                            {
                                "id": log.id,
                                "node_id": log.node.id if log.node else None,
                                "node_name": log.node.name if log.node else None,
                                "action": log.action,
                                "result": log.result,
                                "timestamp": log.timestamp.isoformat(),
                            }
                            for log in logs
                        ],
                        "error": None,
                    },
                }
            )

        except Exception as e:
            logger.exception(f"Error executing state machine: {e}")
            return Response(
                {"success": False, "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CampaignStateMachineSimulationView(APIView):
    """
    API view for simulating campaign-specific state machine execution.

    POST /api/campaigns/{id}/state-machine/simulate - Simulate campaign state machine
    """

    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            return Campaign.objects.get(pk=pk)
        except Campaign.DoesNotExist:
            raise Http404

    def post(self, request, pk):
        """
        Simulate state machine execution for a campaign.

        Input: { deal_id: number, input: string, start_state: string, max_steps: number }
        """
        campaign = self.get_object(pk)

        deal_id = request.data.get("deal_id")
        input_text = request.data.get("input", "")
        start_state = request.data.get("start_state", "")
        max_steps = request.data.get("max_steps", 10)

        if not deal_id:
            return Response(
                {"success": False, "error": "deal_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            Deal.objects.get(id=deal_id, campaign=campaign)
        except Deal.DoesNotExist:
            return Response(
                {"success": False, "error": "Deal not found in this campaign"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            state_graph = campaign.state_graph
        except CampaignStateGraph.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "error": "No state machine defined for this campaign",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Simulate execution with user input
        path = []
        nodes_visited = []
        transitions_used = []
        messages_sent = []
        current_state = start_state or "start"
        steps = 0
        error = None

        # Get all nodes and transitions
        all_nodes = {node.id: node for node in state_graph.nodes.all()}
        all_transitions = list(state_graph.transitions.all())

        # Start from start node if no state specified
        if not start_state:
            start_node = state_graph.nodes.filter(
                node_type=StateNode.TYPE_START
            ).first()
            current_state = start_node.id if start_node else ""

        while current_state and steps < max_steps:
            if current_state not in all_nodes:
                error = f"Unknown node: {current_state}"
                break

            node = all_nodes[current_state]
            nodes_visited.append(node.id)
            path.append(
                {
                    "node": node.id,
                    "name": node.name,
                    "type": node.node_type,
                    "timestamp": (
                        str(node.created_at) if hasattr(node, "created_at") else ""
                    ),
                }
            )

            # Get messages from node config
            if node.config and "message" in node.config:
                messages_sent.append(node.config["message"])

            # Find next transition based on input
            next_transition = None
            for trans in all_transitions:
                if trans.source_node.id == current_state:
                    # Simple condition evaluation
                    if trans.condition_type in ["always", "response"]:
                        next_transition = trans
                        break

            if not next_transition:
                break

            transitions_used.append(next_transition.id)
            current_state = next_transition.target_node.id
            steps += 1

        # Determine final state
        final_state = state_graph.nodes.filter(
            id=current_state, node_type=StateNode.TYPE_END
        ).exists()

        return Response(
            {
                "success": True,
                "simulation": {
                    "input": input_text,
                    "start_state": start_state,
                    "path": path,
                    "nodes_visited": len(nodes_visited),
                    "transitions_used": len(transitions_used),
                    "final_state": current_state if current_state else "completed",
                    "messages_sent": messages_sent,
                    "completed": final_state,
                    "steps": steps,
                    "error": error,
                },
            }
        )


# Alias for StateMachineSimulationView
StateMachineSimulationView = CampaignStateMachineSimulationView
