# State Machine API Views

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.http import Http404

from openoutreach.core.models import Campaign
from openoutreach.crm.models import Deal
from openoutreach.linkedin.models import CampaignStateGraph, StateNode, StateTransition


class StateMachineSimulationView(APIView):
    """
    API view for simulating state machine execution.
    
    POST /api/state-machine/simulate - Simulate state machine execution
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Simulate state machine execution for a campaign and deal.
        
        Input: { campaign_id: number, deal_id: number }
        """
        campaign_id = request.data.get('campaign_id')
        deal_id = request.data.get('deal_id')
        
        if not campaign_id or not deal_id:
            return Response({
                'success': False,
                'error': 'campaign_id and deal_id are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            campaign = Campaign.objects.get(id=campaign_id)
        except Campaign.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Campaign not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        try:
           Deal.objects.get(id=deal_id, campaign=campaign)
        except Deal.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Deal not found in this campaign'
            }, status=status.HTTP_404_NOT_FOUND)
        
        try:
            state_graph = campaign.state_graph
        except CampaignStateGraph.DoesNotExist:
            return Response({
                'success': False,
                'error': 'No state machine defined for this campaign'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Simulate execution
        nodes_visited = []
        transitions_used = []
        current_node = state_graph.nodes.filter(node_type=StateNode.TYPE_START).first()
        
        if not current_node:
            return Response({
                'success': False,
                'error': 'No start node defined in state machine'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        path = []
        messages_sent = []
        steps = 0
        max_steps = 100
        
        while current_node and steps < max_steps:
            nodes_visited.append(current_node.id)
            path.append({
                'node': current_node.id,
                'name': current_node.name,
                'type': current_node.node_type
            })
            
            # Get messages from node config
            if current_node.config and 'message' in current_node.config:
                messages_sent.append(current_node.config['message'])
            
            # Find next transition
            next_transition = state_graph.transitions.filter(source_node=current_node).first()
            
            if not next_transition:
                break
            
            transitions_used.append(next_transition.id)
            current_node = next_transition.target_node
            steps += 1
        
        # Determine final status
        final_status = 'COMPLETED' if current_node and current_node.node_type == StateNode.TYPE_END else 'IN_PROGRESS'
        
        return Response({
            'success': True,
            'simulation': {
                'path': path,
                'nodes_visited': len(nodes_visited),
                'transitions_used': len(transitions_used),
                'final_status': final_status,
                'messages_sent': messages_sent,
                'completed': final_status == 'COMPLETED',
                'steps': steps,
                'error': None
            }
        })


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
        
        deal_id = request.data.get('deal_id')
        input_text = request.data.get('input', '')
        start_state = request.data.get('start_state', '')
        max_steps = request.data.get('max_steps', 10)
        
        if not deal_id:
            return Response({
                'success': False,
                'error': 'deal_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            Deal.objects.get(id=deal_id, campaign=campaign)
        except Deal.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Deal not found in this campaign'
            }, status=status.HTTP_404_NOT_FOUND)
        
        try:
            state_graph = campaign.state_graph
        except CampaignStateGraph.DoesNotExist:
            return Response({
                'success': False,
                'error': 'No state machine defined for this campaign'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Simulate execution with user input
        path = []
        nodes_visited = []
        transitions_used = []
        messages_sent = []
        current_state = start_state or 'start'
        steps = 0
        error = None
        
        # Get all nodes and transitions
        all_nodes = {node.id: node for node in state_graph.nodes.all()}
        all_transitions = list(state_graph.transitions.all())
        
        # Start from start node if no state specified
        if not start_state:
            start_node = state_graph.nodes.filter(node_type=StateNode.TYPE_START).first()
            current_state = start_node.id if start_node else ''
        
        while current_state and steps < max_steps:
            if current_state not in all_nodes:
                error = f"Unknown node: {current_state}"
                break
            
            node = all_nodes[current_state]
            nodes_visited.append(node.id)
            path.append({
                'node': node.id,
                'name': node.name,
                'type': node.node_type,
                'timestamp': str(node.created_at) if hasattr(node, 'created_at') else ''
            })
            
            # Get messages from node config
            if node.config and 'message' in node.config:
                messages_sent.append(node.config['message'])
            
            # Find next transition based on input
            next_transition = None
            for trans in all_transitions:
                if trans.source_node.id == current_state:
                    # Simple condition evaluation
                    if trans.condition_type in ['always', 'response']:
                        next_transition = trans
                        break
            
            if not next_transition:
                break
            
            transitions_used.append(next_transition.id)
            current_state = next_transition.target_node.id
            steps += 1
        
        # Determine final state
        final_state = state_graph.nodes.filter(id=current_state, node_type=StateNode.TYPE_END).exists()
        
        return Response({
            'success': True,
            'simulation': {
                'input': input_text,
                'start_state': start_state,
                'path': path,
                'nodes_visited': len(nodes_visited),
                'transitions_used': len(transitions_used),
                'final_state': current_state if current_state else 'completed',
                'messages_sent': messages_sent,
                'completed': final_state,
                'steps': steps,
                'error': error
            }
        })