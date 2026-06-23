# openoutreach/linkedin/services/state_machine.py
"""State Machine Engine for Campaign workflow automation."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Dict, List, Optional, Tuple

from django.utils import timezone

from openoutreach.core.models import Campaign
from openoutreach.crm.models import Deal
from openoutreach.linkedin.models.state_machine import (
    CampaignStateGraph,
    StateNode,
    StateTransition,
    CampaignState,
    CampaignExecutionLog,
)

logger = logging.getLogger(__name__)


class StateMachineEngine:
    """Engine for executing state machines."""
    
    def __init__(self, state_graph: CampaignStateGraph):
        self.state_graph = state_graph
    
    def get_node(self, node_id: int) -> Optional[StateNode]:
        """Get a node by ID."""
        try:
            return StateNode.objects.get(id=node_id, state_graph=self.state_graph)
        except StateNode.DoesNotExist:
            return None
    
    def get_transitions(self, node: StateNode) -> List[StateTransition]:
        """Get outgoing transitions for a node."""
        return list(StateTransition.objects.filter(
            source_node=node,
            state_graph=self.state_graph,
            is_active=True,
        ).order_by('order'))
    
    def evaluate_condition(self, node: StateNode, deal: Deal, last_message: Optional[Dict] = None) -> bool:
        """Evaluate a condition on a node."""
        condition_type = node.config.get('condition_type', 'always')
        
        if condition_type == 'always':
            return True
        elif condition_type == 'response_received':
            return bool(last_message and last_message.get('is_outgoing', False))
        elif condition_type == 'no_response_yet':
            return not (last_message and last_message.get('is_outgoing', False))
        elif condition_type == 'qualification_score':
            min_score = node.config.get('min_score', 0.5)
            return getattr(deal, 'qualification_score', 0) >= min_score
        elif condition_type == 'days_since':
            days = node.config.get('days', 0)
            days_since = (timezone.now() - deal.update_date).days
            return days_since >= days
        elif condition_type == 'message_count':
            count = node.config.get('min_count', 0)
            return deal.messages.count() >= count if hasattr(deal, 'messages') else False
        
        return True
    
    def next_node(self, current_node: StateNode, deal: Deal, last_message: Optional[Dict] = None) -> Optional[StateNode]:
        """Determine the next node based on current state and conditions."""
        transitions = self.get_transitions(current_node)
        
        for transition in transitions:
            if self.evaluate_condition(transition.target_node, deal, last_message):
                return transition.target_node
        
        return None
    
    def execute_step(self, state_machine: CampaignState, session=None) -> Tuple[bool, str]:
        """Execute one step of the state machine."""
        current_node = state_machine.current_node
        deal = state_machine.deal
        
        if not current_node:
            return False, "No current node set"
        
        # Execute node action
        result = self._execute_node(current_node, deal, session)
        
        if not result['success']:
            state_machine.status = CampaignState.STATUS_ERROR
            state_machine.error_message = result.get('error', 'Node execution failed')
            state_machine.save()
            return False, result.get('error', 'Node execution failed')
        
        # Store execution log
        CampaignExecutionLog.objects.create(
            state_machine=state_machine,
            node=current_node,
            action=current_node.node_type,
            result=result.get('output', {}),
        )
        
        # Determine next node
        next_node = self.next_node(current_node, deal, result.get('last_message'))
        
        if next_node:
            state_machine.previous_nodes.append(current_node.id)
            state_machine.current_node = next_node
            state_machine.save()
            
            # Wait if it's a wait node
            if next_node.node_type == StateNode.TYPE_WAIT:
                wait_minutes = next_node.config.get('wait_minutes', 1440)
                state_machine.wait_until = timezone.now() + timedelta(minutes=wait_minutes)
                state_machine.wait_reason = next_node.config.get('reason', 'Scheduled wait')
                state_machine.save()
        else:
            # No more transitions - end the state machine
            state_machine.status = CampaignState.STATUS_COMPLETED
            state_machine.completed_at = timezone.now()
            state_machine.save()
        
        return True, "Step completed"
    
    def _execute_node(self, node: StateNode, deal: Deal, session=None) -> Dict:
        """Execute a node's action."""
        if node.node_type == StateNode.TYPE_WAIT:
            return {'success': True, 'output': {'waited': True}}
        
        elif node.node_type == StateNode.TYPE_MESSAGE:
            # Get message template
            template_id = node.config.get('message_template_id')
            template_text = node.config.get('message_template_text', '')
            
            # Get the user to send the message from
            linkedin_profile = session.linkedin_profile if session and hasattr(session, 'linkedin_profile') else None
            
            if linkedin_profile and not linkedin_profile.can_execute("follow_up"):
                return {
                    'success': False,
                    'output': {'message_sent': False},
                    'error': 'Daily limit reached',
                }
            
            # Simulate sending message (production would use the actual LinkedIn client)
            # Get chat messages for this deal
            try:
                from openoutreach.chat.models import ChatMessage
                
                # Create outgoing message
                outgoing_message = ChatMessage.objects.create(
                    deal=deal,
                    sender='outgoing',
                    message=template_text,
                    is_outgoing=True,
                    creation_date=timezone.now(),
                )
                
                if linkedin_profile:
                    linkedin_profile.record_action("follow_up", deal.campaign)
                
                return {
                    'success': True,
                    'output': {
                        'message_sent': True,
                        'message_id': outgoing_message.id,
                    },
                    'last_message': {'is_outgoing': True},
                }
            except Exception as e:
                logger.error(f"Failed to execute message node: {e}")
                return {
                    'success': False,
                    'output': {'message_sent': False},
                    'error': str(e),
                }
        
        elif node.node_type == StateNode.TYPE_DECISION:
            # Decision nodes don't perform actions, just route
            return {'success': True, 'output': {'decision_made': True}}
        
        elif node.node_type == StateNode.TYPE_BRANCH:
            # Branch nodes use config to determine next step
            return {'success': True, 'output': {'branch_taken': True}}
        
        elif node.node_type == StateNode.TYPE_GATE:
            # Gate nodes apply qualification criteria
            min_score = node.config.get('min_score', 0.5)
            score = getattr(deal, 'qualification_score', 0)
            passed = score >= min_score
            
            return {
                'success': True,
                'output': {
                    'gate_passed': passed,
                    'score': score,
                    'min_score': min_score,
                },
            }
        
        elif node.node_type == StateNode.TYPE_WEBHOOK:
            # Webhook nodes trigger external events
            webhook_url = node.config.get('webhook_url', '')
            webhook_method = node.config.get('webhook_method', 'POST')
            webhook_payload = node.config.get('webhook_payload', {})
            
            # Placeholder for webhook execution
            return {
                'success': True,
                'output': {
                    'webhook_triggered': True,
                    'url': webhook_url,
                    'method': webhook_method,
                },
            }
        
        elif node.node_type == StateNode.TYPE_START:
            # Start node initialization
            return {'success': True, 'output': {'started': True}}
        
        elif node.node_type == StateNode.TYPE_END:
            # End node - campaign completed
            return {'success': True, 'output': {'completed': True}}
        
        else:
            # Unknown node type
            return {'success': True, 'output': {'action': node.node_type}}
    
    def validate_graph(self) -> Tuple[bool, List[Dict]]:
        """Validate the state graph for issues."""
        errors = []
        warnings = []
        
        nodes = self.state_graph.nodes.filter(is_active=True)
        
        # Check for start node
        start_nodes = nodes.filter(node_type=StateNode.TYPE_START)
        if not start_nodes.exists():
            errors.append({"type": "missing_start", "message": "No start node defined"})
        elif start_nodes.count() > 1:
            errors.append({"type": "multiple_starts", "message": f"Multiple start nodes defined: {start_nodes.count()}"})
        
        # Check for cycles using DFS
        visited = set()
        rec_stack = set()
        
        def has_cycle(node_id: int) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)
            
            node = self.get_node(node_id)
            if not node:
                return False
            
            for transition in self.get_transitions(node):
                child_id = transition.target_node.id
                if child_id not in visited:
                    if has_cycle(child_id):
                        return True
                elif child_id in rec_stack:
                    return True
            
            rec_stack.remove(node_id)
            return False
        
        # Check from start nodes
        for start_node in start_nodes:
            if has_cycle(start_node.id):
                errors.append({"type": "cycles", "message": "Cycle detected in state graph"})
                break
        
        # Check for unreachable nodes
        reachable = set()
        
        def find_reachable(node_id: int):
            reachable.add(node_id)
            node = self.get_node(node_id)
            if not node:
                return
            
            for transition in self.get_transitions(node):
                find_reachable(transition.target_node.id)
        
        for start_node in start_nodes:
            find_reachable(start_node.id)
        
        for node in nodes:
            if node.id not in reachable:
                warnings.append({"type": "unreachable", "message": f"Node '{node.name}' (ID: {node.id}) is unreachable"})
        
        # Check for nodes without outgoing transitions (except end nodes)
        for node in nodes:
            if node.node_type != StateNode.TYPE_END:
                transitions = self.get_transitions(node)
                if not transitions:
                    warnings.append({"type": "no_outgoing", "message": f"Node '{node.name}' has no outgoing transitions"})
        
        return len(errors) == 0, errors + warnings
    
    def simulate_execution(self, deal: Deal, start_node_id: Optional[int] = None) -> Dict:
        """Simulate state machine execution for a deal."""
        simulation = {
            'path': [],
            'nodes_visited': [],
            'transitions_used': [],
            'final_status': 'pending',
            'messages_sent': [],
            'completed': False,
            'error': None,
        }
        
        current_node = None
        
        # Get start node or use provided one
        if start_node_id:
            current_node = self.get_node(start_node_id)
        else:
            current_node = self.state_graph.nodes.filter(
                node_type=StateNode.TYPE_START
            ).first()
        
        max_steps = 100  # Prevent infinite loops in simulation
        steps = 0
        
        while current_node and steps < max_steps:
            steps += 1
            
            # Record node visit
            simulation['nodes_visited'].append({
                'id': current_node.id,
                'name': current_node.name,
                'type': current_node.node_type,
                'x': current_node.x,
                'y': current_node.y,
            })
            
            # Check if message node
            if current_node.node_type == StateNode.TYPE_MESSAGE:
                template = current_node.config.get('message_template_text', '')
                if template:
                    simulation['messages_sent'].append(template)
            
            # Get next node
            next_node = self.next_node(current_node, deal)
            
            if next_node:
                # Find the transition used
                try:
                    transition = StateTransition.objects.get(
                        source_node=current_node,
                        target_node=next_node,
                        state_graph=self.state_graph,
                    )
                    simulation['transitions_used'].append({
                        'source': current_node.id,
                        'target': next_node.id,
                        'label': transition.label or 'Default',
                        'condition': transition.condition_type,
                    })
                except StateTransition.DoesNotExist:
                    pass  # Use default transition
            
            current_node = next_node
        
        simulation['final_status'] = 'completed' if current_node and current_node.node_type == StateNode.TYPE_END else 'incomplete'
        simulation['completed'] = simulation['final_status'] == 'completed'
        simulation['steps'] = steps
        
        return simulation


def validate_state_graph(graph_id: int) -> Tuple[bool, List[Dict]]:
    """Convenience function to validate a state graph by ID."""
    try:
        state_graph = CampaignStateGraph.objects.get(pk=graph_id)
        engine = StateMachineEngine(state_graph)
        return engine.validate_graph()
    except CampaignStateGraph.DoesNotExist:
        logger.error(f"State graph {graph_id} does not exist")
        return False, [{"type": "not_found", "message": f"State graph {graph_id} does not exist"}]
    except Exception as e:
        logger.error(f"Error validating state graph {graph_id}: {e}")
        return False, [{"type": "error", "message": str(e)}]


def simulate_state_machine(campaign_id: int, deal_id: int, node_id: Optional[int] = None) -> Dict:
    """Simulate a state machine execution for a deal."""
    from openoutreach.core.models import Campaign
    from openoutreach.crm.models import Deal

    try:
        campaign = Campaign.objects.get(pk=campaign_id)
        deal = Deal.objects.get(pk=deal_id, campaign=campaign)
        state_graph = campaign.state_graph
        
        if not state_graph or not state_graph.is_active:
            return {
                'success': False,
                'error': 'State graph not active',
            }
        
        engine = StateMachineEngine(state_graph)
        simulation = engine.simulate_execution(deal, node_id)
        
        return {'success': True, 'simulation': simulation}
    except Campaign.DoesNotExist:
        logger.error(f"Campaign {campaign_id} does not exist")
        return {'success': False, 'error': 'Campaign not found'}
    except Deal.DoesNotExist:
        logger.error(f"Deal {deal_id} not found for campaign {campaign_id}")
        return {'success': False, 'error': 'Deal not found'}
    except Exception as e:
        logger.error(f"Error simulating state machine for campaign {campaign_id}, deal {deal_id}: {e}")
        return {'success': False, 'error': str(e)}