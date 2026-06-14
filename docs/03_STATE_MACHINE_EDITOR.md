# State Machine Editor for Campaigns

A visual campaign workflow builder that allows users to define custom outreach sequences using a drag-and-drop state machine editor, with support for branching logic, conditions, and multi-path follow-ups.

---

## Overview

The State Machine Editor transforms outreach from a linear pipeline into a flexible workflow system:
- **Visual editor**: Drag-and-drop interface for building outreach flows
- **Conditional branches**: Send different messages based on responses, timing, or lead characteristics
- **Loop protection**: Prevent infinite loops with automatic cycle detection
- **Execution simulation**: Test your workflow before launching
- **Runtime visualization**: Watch your campaign flow in real-time

This enables sophisticated outreach patterns like:
- **Follow-up paths**: Different responses based on response received/no response
- **Timing-based routing**: Send different messages after different waiting periods
- ** qualification gates**: Route leads based on qualification score
- **Multi-channel flows**: Coordinate LinkedIn + email sequences

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      State Machine Editor                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────────┐     ┌──────────────────┐     ┌──────────────────────┐  │
│  │  Visual      │────▶│  State Machine   │────▶│  Campaign Router     │  │
│  │  Editor      │     │  Engine          │     │  (Runtime)           │  │
│  └──────────────┘     └──────────────────┘     └──────────────────────┘  │
│         │                     │                        │                │
│         ▼                     ▼                        ▼                │
│  ┌──────────────┐     ┌──────────────────┐     ┌──────────────────────┐  │
│  │  Node Types  │     │  Validation      │     │  Execution Engine    │  │
│  │  • Start     │     │  • Cycles        │     │  • State tracking    │  │
│  │  • Wait      │     │  • Transitions   │     │  • Decision making   │  │
│  │  • Message   │     │  • Conditions    │     │  • Path management   │  │
│  │  • Gate      │     │  • Constraints   │     │  • Retry logic       │  │
│  │  • End       │     └──────────────────┘     └──────────────────────┘  │
│  └──────────────┘                                                  │     │
│                                                                    ▼     │
│                                                              ┌──────────────────────┐  │
│                                                              │  Campaign Metrics  │  │
│                                                              │  • Flow efficiency │  │
│                                                              │  • Drop-off points │  │
│                                                              │  • Conversion rates│  │
│                                                              └──────────────────────┘  │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### 1. State Machine Models (`linkedin/models/state_machine.py`)

```python
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey


class CampaignStateGraph(models.Model):
    """Represents a campaign's workflow state machine."""
    
    campaign = models.OneToOneField('Campaign', on_delete=models.CASCADE, related_name='state_graph')
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    # JSON representation of the graph
    graph_data = models.JSONField(default=dict)
    
    # Validation status
    is_valid = models.BooleanField(default=False)
    validation_errors = models.JSONField(default=list)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Campaign state graphs"


class StateNode(models.Model):
    """Represents a node in the state machine."""
    
    TYPE_START = 'start'
    TYPE_WAIT = 'wait'
    TYPE_MESSAGE = 'message'
    TYPE_GATE = 'gate'
    TYPE_DECISION = 'decision'
    TYPE_BRANCH = 'branch'
    TYPE_WEBHOOK = 'webhook'
    TYPE_END = 'end'
    
    TYPE_CHOICES = [
        (TYPE_START, 'Start'),
        (TYPE_WAIT, 'Wait/Delay'),
        (TYPE_MESSAGE, 'Send Message'),
        (TYPE_GATE, 'Qualification Gate'),
        (TYPE_DECISION, 'Decision'),
        (TYPE_BRANCH, 'Branch'),
        (TYPE_WEBHOOK, 'Webhook'),
        (TYPE_END, 'End'),
    ]
    
    name = models.CharField(max_length=100)
    node_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    state_graph = models.ForeignKey(CampaignStateGraph, on_delete=models.CASCADE, related_name='nodes')
    
    # Configuration
    config = models.JSONField(default=dict)  # Node-specific settings
    
    # Positioning (for visual editor)
    x = models.FloatField(default=0)
    y = models.FloatField(default=0)
    
    # Metadata
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['state_graph', 'x', 'y']


class StateTransition(models.Model):
    """Represents a transition between nodes."""
    
    source_node = models.ForeignKey(StateNode, on_delete=models.CASCADE, related_name='outgoing_transitions')
    target_node = models.ForeignKey(StateNode, on_delete=models.CASCADE, related_name='incoming_transitions')
    
    state_graph = models.ForeignKey(CampaignStateGraph, on_delete=models.CASCADE, related_name='transitions')
    
    # Condition
    condition_type = models.CharField(max_length=50, default='always')
    condition_config = models.JSONField(default=dict)
    
    # Label (for display)
    label = models.CharField(max_length=100, blank=True)
    
    # Order (for multiple outgoing transitions)
    order = models.PositiveIntegerField(default=0)
    
    # Enabled
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['state_graph', 'order']


class CampaignState(models.Model):
    """Tracks the current state of a campaign follow-up."""
    
    STATUS_ACTIVE = 'active'
    STATUS_COMPLETED = 'completed'
    STATUS_DROPPED = 'dropped'
    STATUS_ERROR = 'error'
    
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_DROPPED, 'Dropped'),
        (STATUS_ERROR, 'Error'),
    ]
    
    deal = models.ForeignKey('Deal', on_delete=models.CASCADE, related_name='state_machines')
    state_graph = models.ForeignKey(CampaignStateGraph, on_delete=models.CASCADE)
    
    current_node = models.ForeignKey(StateNode, on_delete=models.SET_NULL, null=True, blank=True)
    previous_nodes = models.JSONField(default=list)  # History of visited nodes
    
    # Execution state
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    error_message = models.TextField(blank=True)
    
    # Wait tracking
    wait_until = models.DateTimeField(null=True, blank=True)
    wait_reason = models.CharField(max_length=100, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict)
    
    # Timings
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name_plural = "Campaign states"
        ordering = ['-started_at']


class CampaignExecutionLog(models.Model):
    """Logs each step of state machine execution."""
    
    state_machine = models.ForeignKey(CampaignState, on_delete=models.CASCADE, related_name='execution_logs')
    
    node = models.ForeignKey(StateNode, on_delete=models.SET_NULL, null=True, blank=True)
    transition = models.ForeignKey(StateTransition, on_delete=models.SET_NULL, null=True, blank=True)
    
    action = models.CharField(max_length=100)
    result = models.JSONField(default=dict)
    error = models.TextField(blank=True)
    
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name_plural = "Campaign execution logs"
```

### 2. State Machine Engine (`linkedin/services/state_machine.py`)

```python
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from django.utils import timezone

from linkedoutreach.linkedin.models import CampaignStateGraph, StateNode, StateTransition, CampaignState
from linkedoutreach.crm.models import Deal


class StateMachineEngine:
    """Engine for executing state machines."""
    
    def __init__(self, state_graph: CampaignStateGraph):
        self.state_graph = state_graph
    
    def get_node(self, node_id: str) -> Optional[StateNode]:
        """Get a node by ID."""
        try:
            return StateNode.objects.get(id=node_id, state_graph=self.state_graph)
        except StateNode.DoesNotExist:
            return None
    
    def get_transitions(self, node: StateNode) -> List[StateTransition]:
        """Get outgoing transitions for a node."""
        return StateTransition.objects.filter(
            source_node=node,
            state_graph=self.state_graph,
            is_active=True,
        ).order_by('order')
    
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
            return deal.qualification_score >= min_score
        elif condition_type == 'days_since':
            days = node.config.get('days', 0)
            days_since = (timezone.now() - deal.update_date).days
            return days_since >= days
        elif condition_type == 'message_count':
            count = node.config.get('min_count', 0)
            return deal.chatmessage_set.count() >= count
        
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
            
            # Send message
            from linkedoutreach.linkedin.services.events import EventPublisher
            publisher = EventPublisher()
            
            publisher.publish_message_sent(
                campaign_id=str(deal.campaign.id),
                campaign_name=deal.campaign.name,
                lead_name=deal.lead.public_identifier,
                lead_url=deal.lead.linkedin_url,
            )
            
            return {
                'success': True,
                'output': {'message_sent': True},
                'last_message': {'is_outgoing': True},
            }
        
        elif node.node_type == StateNode.TYPE_DECISION:
            # Decision nodes don't perform actions, just route
            return {'success': True, 'output': {'decision_made': True}}
        
        elif node.node_type == StateNode.TYPE_BRANCH:
            # Branch nodes use config to determine next step
            return {'success': True, 'output': {'branch_taken': True}}
        
        else:
            # Start, End, Gate, Webhook nodes
            return {'success': True, 'output': {'action': node.node_type}}
    
    def validate_graph(self) -> Tuple[bool, List[Dict]]:
        """Validate the state graph for issues."""
        errors = []
        warnings = []
        
        nodes = self.state_graph.nodes.filter(is_active=True)
        
        # Check for start node
        start_nodes = nodes.filter(node_type=StateNode.TYPE_START)
        if not start_nodes.exists():
            errors.append("No start node defined")
        elif start_nodes.count() > 1:
            errors.append("Multiple start nodes defined")
        
        # Check for cycles using DFS
        visited = set()
        rec_stack = set()
        
        def has_cycle(node_id: str) -> bool:
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
                errors.append("Cycle detected in state graph")
                break
        
        # Check for unreachable nodes
        reachable = set()
        
        def find_reachable(node_id: str):
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
                warnings.append(f"Node '{node.name}' is unreachable")
        
        return len(errors) == 0, errors + warnings
```

### 3.Campaign Router Integration

Update the task handlers to use state machine engine:

```python
def handle_follow_up(task, session, qualifiers):
    """Handle follow-up task with state machine routing."""
    from linkedoutreach.linkedin.services.state_machine import StateMachineEngine
    
    # Get or create state machine for deal
    deal = qualifiers['deal']
    state_graph = deal.campaign.state_graph
    
    if not state_graph or not state_graph.is_active:
        # Fall back to default behavior
        return handle_follow_up_default(task, session, qualifiers)
    
    # Get or create state machine instance
    state_machine, created = CampaignState.objects.get_or_create(
        deal=deal,
        state_graph=state_graph,
        defaults={
            'current_node': state_graph.nodes.filter(node_type=StateNode.TYPE_START).first(),
            'status': CampaignState.STATUS_ACTIVE,
        }
    )
    
    # Check if we should wait
    if state_machine.wait_until and timezone.now() < state_machine.wait_until:
        # Re-enqueue with delay
        _re_enqueue_with_delay(task, delay_seconds=3600)
        return
    
    # Execute the state machine
    engine = StateMachineEngine(state_graph)
    success, message = engine.execute_step(state_machine, session)
    
    if not success:
        logger.error(f"State machine execution failed: {message}")
        return handle_follow_up_default(task, session, qualifiers)
    
    # Continue following up based on state machine
    # (The machine will update deal state for next check_pending)
```


### 4. Frontend Visual Editor

```typescript
interface NodeConfig {
  id: string;
  type: NodeType;
  name: string;
  x: number;
  y: number;
  config: any;
}

interface TransitionConfig {
  id: string;
  source: string;
  target: string;
  condition: string;
  label: string;
}

type NodeType = 'start' | 'wait' | 'message' | 'gate' | 'decision' | 'branch' | 'webhook' | 'end';

export function StateMachineEditor({ campaignId }: { campaignId: string }) {
  const [nodes, setNodes] = useState<NodeConfig[]>([]);
  const [transitions, setTransitions] = useState<TransitionConfig[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  
  // Load graph data
  useEffect(() => {
    fetch(`/api/campaigns/${campaignId}/state-graph/`)
      .then(r => r.json())
      .then(data => {
        setNodes(data.nodes);
        setTransitions(data.transitions);
      });
  }, [campaignId]);
  
  return (
    <div className="flex h-screen">
      {/* Node Palette */}
      <div className="w-64 p-4 bg-gray-50 border-r">
        <h3 className="font-semibold mb-4">Nodes</h3>
        <NodePalette onDragStart={handleDragStart} />
      </div>
      
      {/* Canvas */}
      <div className="flex-1 p-8 bg-gray-100 overflow-auto">
        <StateMachineCanvas
          nodes={nodes}
          transitions={transitions}
          onDragStart={handleDragStart}
          onDragMove={handleDragMove}
          onDragEnd={handleDragEnd}
          onConnect={handleConnect}
          onDelete={handleDelete}
          config={campaignConfig}
        />
        
        <div className="fixed bottom-4 right-4 flex gap-2">
          <button 
            onClick={saveGraph}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Save Graph
          </button>
          <button 
            onClick={validateGraph}
            className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
          >
            Validate
          </button>
        </div>
      </div>
    </div>
  );
}

function StateMachineCanvas({ nodes, transitions, onDragStart, onDragMove, onDragEnd, onConnect, onDelete, config }) {
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  
  return (
    <div className="relative w-full h-full">
      {/* Grid background */}
      <div className="absolute inset-0 opacity-10 pointer-events-none">
        <div className="w-full h-full" style={{ 
          backgroundImage: 'radial-gradient(#999 1px, transparent 1px)', 
          backgroundSize: '20px 20px' 
        }} />
      </div>
      
      {/* Transitions as SVG connections */}
      <svg className="absolute inset-0 w-full h-full pointer-events-none">
        {transitions.map(t => {
          const source = nodes.find(n => n.id === t.source);
          const target = nodes.find(n => n.id === t.target);
          
          if (!source || !target) return null;
          
          return (
            <g key={t.id}>
              <path
                d={`M ${source.x + 100} ${source.y + 30} L ${target.x + 100} ${target.y + 30}`}
                stroke="#666"
                strokeWidth="2"
                fill="none"
              />
              {t.label && (
                <text x={(source.x + target.x) / 2} y={(source.y + target.y) / 2 - 10} textAnchor="middle" fill="#666" fontSize="12">
                  {t.label}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      
      {/* Nodes */}
      {nodes.map(node => (
        <NodeCard
          key={node.id}
          node={node}
          hovered={hoveredNode === node.id}
          onMouseEnter={() => setHoveredNode(node.id)}
          onMouseLeave={() => setHoveredNode(null)}
          onDragStart={onDragStart}
          onDelete={() => onDelete(node.id)}
        />
      ))}
    </div>
  );
}

function NodeCard({ node, hovered, onMouseEnter, onMouseLeave, onDragStart, onDelete }) {
  const types = {
    start: { color: 'bg-green-500', icon: '🚀' },
    wait: { color: 'bg-yellow-500', icon: '⏳' },
    message: { color: 'bg-blue-500', icon: '💬' },
    gate: { color: 'bg-purple-500', icon: '🛡️' },
    decision: { color: 'bg-orange-500', icon: '🤔' },
    branch: { color: 'bg-indigo-500', icon: '🌿' },
    webhook: { color: 'bg-pink-500', icon: '🔌' },
    end: { color: 'bg-red-500', icon: '🏁' },
  };
  
  const typeConfig = types[node.type as keyof typeof types] || { color: 'bg-gray-500', icon: '☐' };
  
  return (
    <div
      className={`absolute w-48 p-4 rounded-lg shadow-lg border-2 transition-all ${
        hovered ? 'border-blue-500 scale-105' : 'border-gray-300'
      } ${typeConfig.color} bg-white text-gray-900`}
      style={{ left: node.x, top: node.y }}
      onMouseDown={(e) => onDragStart(e, node.id)}
    >
      <div className="flex items-center justify-between">
        <span className="text-xl">{typeConfig.icon}</span>
        <button onClick={onDelete} className="text-gray-400 hover:text-red-500">×</button>
      </div>
      <h4 className="font-semibold mt-2">{node.name}</h4>
      <p className="text-xs text-gray-500 mt-1">{node.type}</p>
    </div>
  );
}

function NodePalette({ onDragStart }) {
  const nodeTypes = [
    { type: 'start', label: 'Start', icon: '🚀' },
    { type: 'message', label: 'Send Message', icon: '💬' },
    { type: 'wait', label: 'Wait', icon: '⏳' },
    { type: 'gate', label: 'Gate', icon: '🛡️' },
    { type: 'decision', label: 'Decision', icon: '🤔' },
    { type: 'branch', label: 'Branch', icon: '🌿' },
    { type: 'end', label: 'End', icon: '🏁' },
  ];
  
  return (
    <div className="space-y-2">
      {nodeTypes.map(nodeType => (
        <div
          key={nodeType.type}
          draggable
          onDragStart={(e) => {
            e.dataTransfer.setData('nodeType', nodeType.type);
            e.dataTransfer.setData('nodeName', nodeType.label);
            onDragStart(e);
          }}
          className="p-3 bg-white border rounded cursor-move hover:border-blue-400"
        >
          <span className="text-xl mr-2">{nodeType.icon}</span>
          {nodeType.label}
        </div>
      ))}
    </div>
  );
}
```

### 5. Simulation Mode

```python
def simulate_state_machine(cam paign_id: str, lead_id: str) -> Dict:
    """Simulate a state machine execution for a lead."""
    from linkedoutreach.linkedin.services.state_machine import StateMachineEngine
    from linkedoutreach.crm.models import Deal
    
    deal = Deal.objects.get(id=lead_id, campaign_id=campaign_id)
    state_graph = deal.campaign.state_graph
    
    if not state_graph or not state_graph.is_valid:
        return {'success': False, 'error': 'State graph not valid'}
    
    engine = StateMachineEngine(state_graph)
    
    # Simulate state machine execution
    simulation = {
        'path': [],
        'nodes_visited': [],
        'transitions_used': [],
        'final_status': 'pending',
        'messages_sent': [],
    }
    
    current_node = state_graph.nodes.filter(node_type=StateNode.TYPE_START).first()
    
    while current_node:
        simulation['nodes_visited'].append({
            'id': current_node.id,
            'name': current_node.name,
            'type': current_node.node_type,
        })
        
        if current_node.node_type == StateNode.TYPE_MESSAGE:
            template = current_node.config.get('message_template', '')
            simulation['messages_sent'].append(template)
        
        next_node = engine.next_node(current_node, deal)
        
        if next_node:
            transition = StateTransition.objects.get(
                source_node=current_node,
                target_node=next_node,
            )
            simulation['transitions_used'].append({
                'source': current_node.id,
                'target': next_node.id,
                'label': transition.label or 'Default',
            })
        
        current_node = next_node
    
    simulation['final_status'] = 'completed' if current_node and current_node.node_type == StateNode.TYPE_END else 'incomplete'
    
    return {'success': True, 'simulation': simulation}
```

---

## Migration Plan

1. Create State Machine models
2. Run migration
3. Build state machine engine
4. Create visual editor frontend
5. Integrate with task handlers
6. Add simulation mode

---

## Benefits

| Feature | Before | After |
|---------|--------|-------|
| Workflow | Linear pipeline | Flexible state machine |
| Branching | Hardcoded logic | Visual conditions |
| Personalization | Single path | Multi-path routing |
| Testing | Deploy to test | Simulate before launch |
| Monitoring | Generic stats | Flow-specific metrics |

State machines enable sophisticated, personalized outreach sequences while maintaining simplicity through visual editing.