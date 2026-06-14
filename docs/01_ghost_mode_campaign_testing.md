# Ghost Mode Campaign Testing

A safe pre-launch testing mode that allows you to validate your campaign setup without actually sending any messages or connection requests.

---

## Overview

Ghost Mode is a "safe test" mode where:
- **No LinkedIn actions are performed** - No messages sent, no connections requested
- **Full simulation** - All processing logic runs, but stops at the last moment
- **Results tracked** - What would have happened is logged and analyzed
- **Cost-free** - No API costs, no rate limit impact, no LinkedIn exposure
- **Risk-free learning** - Test your setup with zero risk to your account

This enables:
- Campaign design validation before going live
- A/B testing of different message variants safely
- Lead qualification accuracy testing
- Pipeline flow verification without real-world consequences
- Training and demo scenarios for new team members

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Ghost Mode Engine                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────────┐     ┌──────────────────┐     ┌──────────────────────┐  │
│  │  Campaign    │────▶│  Ghost Mode      │────▶│  Safe Execution      │  │
│  │  Scheduler   │     │  Interceptor     │     │  Engine              │  │
│  └──────────────┘     └──────────────────┘     └──────────────────────┘  │
│         │                     │                        │                │
│         ▼                     ▼                        ▼                │
│  ┌──────────────┐     ┌──────────────────┐     ┌──────────────────────┐  │
│  │ Ghost Queue  │     │  Tracking        │     │  Mock Services       │  │
│  │  (Simulated) │     │  & Analytics     │     │  (LinkedIn API)      │  │
│  └──────────────┘     └──────────────────┘     └──────────────────────┘  │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Ghost Mode Dashboard                            │
│                                                                           │
│  • Preview what would happen                                            │
│  • Analyze simulation results                                           │
│  • Compare different runs                                               │
│  • Export test scenarios                                                │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### 1. Ghost Mode Models (`linkedin/models/ghost_mode.py`)

```python
from django.db import models
from django.utils import timezone


class GhostCampaign(models.Model):
    """A campaign running in ghost mode."""
    
    campaign = models.ForeignKey('Campaign', on_delete=models.CASCADE)
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Mode settings
    is_active = models.BooleanField(default=True)
    mode_type = models.CharField(max_length=20, choices=[
        ('simulation', 'Simulation only'),
        ('validation', 'Validation with warnings'),
        ('dry_run', 'Dry run with all checks'),
    ])
    
    # What to test
    test_seed_leads = models.TextField(blank=True, help_text="Comma-separated LinkedIn URLs to test")
    test_keywords = models.TextField(blank=True, help_text="Keywords to search for")
    
    # Schedule
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    
    # Results
    leads_processed = models.PositiveIntegerField(default=0)
    connections_simulated = models.PositiveIntegerField(default=0)
    messages_simulated = models.PositiveIntegerField(default=0)
    conversions_simulated = models.PositiveIntegerField(default=0)
    
    # Quality metrics
    avg_rating = models.FloatField(default=0.0)
    avg_score = models.FloatField(default=0.0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Ghost campaigns"


class GhostSimulationLog(models.Model):
    """Logs a ghost mode simulation run."""
    
    ghost_campaign = models.ForeignKey(GhostCampaign, on_delete=models.CASCADE, related_name='logs')
    
    # Execution data
    action_type = models.CharField(max_length=20, choices=[
        ('search', 'Search for leads'),
        ('qualify', 'Qualify lead'),
        ('connect', 'Send connection'),
        ('message', 'Send message'),
        ('follow_up', 'Follow up message'),
        ('conversion', 'Conversion tracked'),
    ])
    
    target_url = models.URLField(blank=True)
    target_name = models.CharField(max_length=100, blank=True)
    
    # Results
    result_data = models.JSONField(default=dict)
    rating = models.FloatField(null=True, blank=True)
    score = models.FloatField(null=True, blank=True)
    
    # Timing
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField()
    
    # Simulation metadata
    simulated_action = models.JSONField(default=dict)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-started_at']


class GhostTestScenario(models.Model):
    """Reusable test scenarios for ghost mode."""
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Scenario definition
    test_cases = models.JSONField(default=dict)  # Array of test cases
    
    # Metadata
    is_public = models.BooleanField(default=False)
    created_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True)
    
    # Stats
    runs_count = models.PositiveIntegerField(default=0)
    avg_success_rate = models.FloatField(default=0.0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
```

### 2. Ghost Mode Interceptor (`linkedin/services/ghost_mode.py`)

```python
from typing import Dict, Optional, List
from datetime import datetime
from django.utils import timezone

from linkedoutreach.linkedin.models import GhostCampaign, GhostSimulationLog
from linkedoutreach.crm.models import Deal


class GhostModeInterceptor:
    """Intercepts LinkedIn actions for ghost mode testing."""
    
    def __init__(self, campaign: GhostCampaign):
        self.campaign = campaign
        self.enabled = campaign.is_active
    
    def canProceed(self, action_type: str) -> bool:
        """Check if action should proceed (normal mode) or be intercepted (ghost mode)."""
        if not self.enabled:
            return True  # Not in ghost mode, proceed normally
        
        if action_type in ['search', 'qualify', 'connect', 'message', 'follow_up']:
            return False  # Ghost mode - don't actually perform
        
        return True
    
    def simulate_action(self, action_type: str, target_data: Dict, context: Dict = None) -> Dict:
        """Simulate an action in ghost mode."""
        if not self.enabled:
            return {'success': False, 'error': 'Ghost mode not enabled'}
        
        simulation_start = timezone.now()
        
        # Simulate different action types
        if action_type == 'search':
            result = self._simulate_search(target_data)
        elif action_type == 'qualify':
            result = self._simulate_qualify(target_data, context)
        elif action_type == 'connect':
            result = self._simulate_connect(target_data)
        elif action_type == 'message':
            result = self._simulate_message(target_data)
        elif action_type == 'follow_up':
            result = self._simulate_follow_up(target_data, context)
        else:
            result = {'success': True, 'message': f'Simulated {action_type}'}
        
        simulation_duration = (timezone.now() - simulation_start).total_seconds()
        
        # Log simulation
        GhostSimulationLog.objects.create(
            ghost_campaign=self.campaign,
            action_type=action_type,
            target_url=target_data.get('linkedin_url', ''),
            target_name=target_data.get('name', 'Unknown'),
            result_data=result,
            rating=result.get('rating', None),
            score=result.get('score', None),
            started_at=simulation_start,
            completed_at=timezone.now(),
            simulated_action={
                'action_type': action_type,
                'target': target_data,
                'context': context,
                'duration_seconds': simulation_duration,
            }
        )
        
        # Update campaign stats
        self._update_campaign_stats(action_type, result)
        
        return result
    
    def _simulate_search(self, target_data: Dict) -> Dict:
        """Simulate lead search."""
        # Return simulated results based on search keywords
        search_keywords = target_data.get('keywords', [])
        
        # Simulate finding 5-10 leads
        num_leads = self._random_int(5, 10)
        
        leads = []
        for i in range(num_leads):
            leads.append({
                'name': f'Lead_{i+1}',
                'public_identifier': f'lead{i+1}',
                'linkedin_url': f'https://linkedin.com/in/lead{i+1}',
                'company': self._random_item(['Company A', 'Company B', 'Company C']),
                'job_title': self._random_item(['Manager', 'Director', 'VP', 'Founder']),
                'industry': self._random_item(['Tech', 'Marketing', 'Sales', 'Finance']),
                'match_score': self._random_float(0.3, 0.9),
                'match_reason': f'Match found for keyword: {self._random_item(search_keywords)}',
            })
        
        return {
            'success': True,
            'leads_found': len(leads),
            'leads': leads,
        }
    
    def _simulate_qualify(self, target_data: Dict, context: Dict) -> Dict:
        """Simulate lead qualification."""
        # Simulate qualification based on profile data
        profile = target_data.get('profile', {})
        
        # Mock qualification logic
        score = self._random_float(0.4, 0.95)
        is_qualified = score > 0.6
        
        return {
            'success': True,
            'is_qualified': is_qualified,
            'score': score,
            'rating': 'good' if is_qualified else 'poor',
            'reason': 'Profile matches target criteria',
            'simulated_rating': self._random_int(1, 5),
        }
    
    def _simulate_connect(self, target_data: Dict) -> Dict:
        """Simulate connection request."""
        return {
            'success': True,
            'status': 'sent',  # Would be 'pending' in real mode
            'connection_degree': 1,
            'delay_hours': 48,  # Simulated delay
        }
    
    def _simulate_message(self, target_data: Dict) -> Dict:
        """Simulate sending a message."""
        message_text = target_data.get('message', '')
        
        # Simulate response probability
        response_probability = target_data.get('response_probability', 0.35)
        will_response = self._random_float(0, 1) < response_probability
        
        return {
            'success': True,
            'message_sent': True,
            'message_id': f'msg_{timezone.now().timestamp()}',
            'will_response': will_response,
            'simulated_delay_hours': 24 if will_response else None,
            'simulated_response_content': 'Thanks for connecting!' if will_response else None,
        }
    
    def _simulate_follow_up(self, target_data: Dict, context: Dict) -> Dict:
        """Simulate follow-up message."""
        days_since = target_data.get('days_since_connect', 3)
        
        # Simulate follow-up success based on timing
        best_timing = days_since in [2, 3, 5]
        
        return {
            'success': True,
            'follow_up_sent': True,
            'timing_score': 'optimal' if best_timing else 'acceptable',
            'will_response': self._random_float(0, 1) < 0.5,
        }
    
    def _random_int(self, min_val: int, max_val: int) -> int:
        """Simple random integer generator."""
        import random
        return random.randint(min_val, max_val)
    
    def _random_float(self, min_val: float, max_val: float) -> float:
        """Simple random float generator."""
        import random
        return random.uniform(min_val, max_val)
    
    def _random_item(self, items: List) -> any:
        """Get random item from list."""
        import random
        return random.choice(items) if items else None
    
    def _update_campaign_stats(self, action_type: str, result: Dict):
        """Update ghost campaign statistics."""
        if action_type == 'search':
            self.campaign.leads_processed += result.get('leads_found', 0)
        elif action_type == 'connect':
            self.campaign.connections_simulated += 1
        elif action_type == 'message':
            self.campaign.messages_simulated += 1
        elif action_type == 'qualify':
            if result.get('is_qualified'):
                self.campaign.conversions_simulated += 1
        
        # Update average rating/score
        all_logs = GhostSimulationLog.objects.filter(ghost_campaign=self.campaign)
        ratings = [log.rating for log in all_logs if log.rating is not None]
        scores = [log.score for log in all_logs if log.score is not None]
        
        if ratings:
            self.campaign.avg_rating = sum(ratings) / len(ratings)
        if scores:
            self.campaign.avg_score = sum(scores) / len(scores)
        
        self.campaign.save()


# Convenience functions
def ghost_interceptor(campaign: GhostCampaign) -> GhostModeInterceptor:
    """Create a ghost mode interceptor for a campaign."""
    return GhostModeInterceptor(campaign)
```

### 3. Task Handler Integration

Update task handlers to check ghost mode status:

```python
def handle_connect(task, session, qualifiers):
    """Handle connection task with ghost mode support."""
    from linkedoutreach.linkedin.services.ghost_mode import GhostModeInterceptor
    
    # Check if this is a ghost campaign
    campaign = session.campaign
    ghost_campaign = campaign.ghostcampaign_set.filter(is_active=True).first()
    
    if ghost_campaign:
        # Use ghost mode interceptor
        interceptor = GhostModeInterceptor(ghost_campaign)
        
        # Skip actual connection in ghost mode
        if not interceptor.canProceed('connect'):
            result = interceptor.simulate_action('connect', qualifiers, session)
            
            logger.info(f"Ghost mode simulation: {qualifiers.get('lead_name')} would be connected")
            
            # Don't actually send connection, but track as would happen
            return
        
        # Otherwise proceed with real connection
        # ... existing connection logic ...
    
    # ... rest of handler ...
```

Update `linkedin/tasks/follow_up.py`:

```python
def handle_follow_up(task, session, qualifiers):
    """Handle follow-up task with ghost mode support."""
    from linkedoutreach.linkedin.services.ghost_mode import GhostModeInterceptor
    
    # Check if ghost mode
    campaign = session.campaign
    ghost_campaign = campaign.ghostcampaign_set.filter(is_active=True).first()
    
    if ghost_campaign:
        interceptor = GhostModeInterceptor(ghost_campaign)
        
        if not interceptor.canProceed('follow_up'):
            result = interceptor.simulate_action('follow_up', qualifiers, session)
            
            logger.info(f"Ghost mode simulation: Would send follow-up to {qualifiers.get('lead_name')}")
            
            return
    
    # ... rest of handler ...
```

### 4. Ghost Mode Dashboard

```typescript
interface GhostSimulation {
  id: string;
  actionType: string;
  targetName: string;
  targetUrl: string;
  resultData: any;
  rating: number | null;
  score: number | null;
  startTime: string;
  completedAt: string;
  simulatedAction: any;
}

export function GhostModeDashboard({ campaignId }: { campaignId: string }) {
  const [campaign, setCampaign] = useState<any | null>(null);
  const [simulations, setSimulations] = useState<GhostSimulation[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');

  useEffect(() => {
    fetchGhostCampaign();
    fetchSimulations();
  }, [campaignId]);

  const fetchGhostCampaign = async () => {
    const res = await fetch(`/api/ghost/campaigns/${campaignId}/`);
    const data = await res.json();
    setCampaign(data);
  };

  const fetchSimulations = async () => {
    const res = await fetch(`/api/ghost/simulations/${campaignId}/`);
    const data = await res.json();
    setSimulations(data);
  };

  if (loading) return <LoadingSpinner />;

  return (
    <div className="space-y-6">
      {/* Campaign Stats */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard label="Leads Processed" value={campaign?.leadsProcessed || 0} />
        <StatCard label="Connections Simulated" value={campaign?.connectionsSimulated || 0} />
        <StatCard label="Messages Simulated" value={campaign?.messagesSimulated || 0} />
        <StatCard label="Avg Rating" value={campaign?.avgRating?.toFixed(2) || '0.00'} />
      </div>

      {/* Filters */}
      <div className="flex gap-2">
        <select value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="all">All Actions</option>
          <option value="search">Search</option>
          <option value="qualify">Qualify</option>
          <option value="connect">Connect</option>
          <option value="message">Message</option>
        </select>
      </div>

      {/* Simulation List */}
      <div className="space-y-2">
        {simulations
          .filter(s => filter === 'all' || s.actionType === filter)
          .map(sim => (
            <SimulationCard key={sim.id} simulation={sim} />
          ))}
      </div>

      {/* Export Results */}
      <div className="flex gap-2">
        <button className="p-2 bg-blue-600 text-white rounded">
          Export to CSV
        </button>
        <button className="p-2 bg-green-600 text-white rounded">
          Save as Scenario
        </button>
        <button className="p-2 bg-purple-600 text-white rounded">
          Share Results
        </button>
      </div>
    </div>
  );
}

function SimulationCard({ simulation }: { simulation: GhostSimulation }) {
  const actionIcons = {
    search: '🔍',
    qualify: '✅',
    connect: '🤝',
    message: '💬',
    follow_up: '🔁',
    conversion: '🎉',
  };

  return (
    <div className="bg-white border rounded-lg p-4">
      <div className="flex items-start gap-4">
        <div className="text-3xl">
          {actionIcons[simulation.actionType as keyof typeof actionIcons]}
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="font-semibold">{simulation.targetName}</span>
            <span className="text-xs text-gray-500">
              {simulation.actionType.toUpperCase()}
            </span>
            <span className="text-xs text-gray-400">
              {new Date(simulation.completedAt).toLocaleString()}
            </span>
          </div>
          {simulation.resultData.rating && (
            <div className="mt-2 flex items-center gap-2">
              <span className="text-sm">Rating:</span>
              <div className="flex">
                {Array.from({ length: 5 }).map((_, i) => (
                  <span
                    key={i}
                    className={`text-xl ${
                      i < Math.round(simulation.resultData.rating)
                        ? 'text-yellow-400'
                        : 'text-gray-200'
                    }`}
                  >
                    ★
                  </span>
                ))}
              </div>
              <span className="text-xs text-gray-500 ml-2">
                Score: {simulation.resultData.score?.toFixed(2)}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
```

### 5. Ghost Mode API Endpoints

```python
# linkedin/api/ghost_mode.py

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from linkedoutreach.linkedin.models import GhostCampaign, GhostSimulationLog
from linkedoutreach.linkedin.services.ghost_mode import GhostModeInterceptor


@csrf_exempt
def ghost_start_view(request, campaign_id):
    """Start ghost mode for a campaign."""
    from linkedoutreach.linkedin.models import Campaign
    
    campaign = Campaign.objects.filter(id=campaign_id).first()
    if not campaign:
        return JsonResponse({'error': 'Campaign not found'}, status=404)
    
    # Create or get ghost campaign
    ghost_campaign, created = GhostCampaign.objects.get_or_create(
        campaign=campaign,
        defaults={
            'name': f'{campaign.name} - Ghost Mode',
            'mode_type': 'simulation',
            'start_time': timezone.now(),
        }
    )
    
    return JsonResponse({
        'success': True,
        'ghost_campaign_id': ghost_campaign.id,
        'message': f'Ghost mode started for {campaign.name}',
    })


@csrf_exempt
def ghost_stop_view(request, campaign_id):
    """Stop ghost mode for a campaign."""
    from linkedoutreach.linkedin.models import Campaign
    
    campaign = Campaign.objects.filter(id=campaign_id).first()
    if not campaign:
        return JsonResponse({'error': 'Campaign not found'}, status=404)
    
    ghost_campaign = GhostCampaign.objects.filter(campaign=campaign, is_active=True).first()
    if not ghost_campaign:
        return JsonResponse({'error': 'No active ghost mode for this campaign'}, status=404)
    
    ghost_campaign.is_active = False
    ghost_campaign.end_time = timezone.now()
    ghost_campaign.save()
    
    return JsonResponse({
        'success': True,
        'message': f'Ghost mode stopped for {campaign.name}',
    })


def ghost_campaign_view(request, campaign_id):
    """Get ghost campaign details."""
    ghost_campaign = GhostCampaign.objects.filter(id=campaign_id).first()
    if not ghost_campaign:
        return JsonResponse({'error': 'Ghost campaign not found'}, status=404)
    
    return JsonResponse({
        'id': ghost_campaign.id,
        'name': ghost_campaign.name,
        'description': ghost_campaign.description,
        'is_active': ghost_campaign.is_active,
        'mode_type': ghost_campaign.mode_type,
        'leads_processed': ghost_campaign.leads_processed,
        'connections_simulated': ghost_campaign.connections_simulated,
        'messages_simulated': ghost_campaign.messages_simulated,
        'conversions_simulated': ghost_campaign.conversions_simulated,
        'avg_rating': ghost_campaign.avg_rating,
        'avg_score': ghost_campaign.avg_score,
        'created_at': ghost_campaign.created_at.isoformat(),
    })


def ghost_simulations_view(request, campaign_id):
    """Get simulation logs for a ghost campaign."""
    ghost_campaign = GhostCampaign.objects.filter(id=campaign_id).first()
    if not ghost_campaign:
        return JsonResponse({'error': 'Ghost campaign not found'}, status=404)
    
    # Get logs
    logs = GhostSimulationLog.objects.filter(ghost_campaign=ghost_campaign).order_by('-started_at')
    
    return JsonResponse({
        'campaign_id': ghost_campaign.id,
        'total': logs.count(),
        'simulations': [{
            'id': log.id,
            'action_type': log.action_type,
            'target_name': log.target_name,
            'target_url': log.target_url,
            'result_data': log.result_data,
            'rating': log.rating,
            'score': log.score,
            'started_at': log.started_at.isoformat(),
            'completed_at': log.completed_at.isoformat(),
            'simulated_action': log.simulated_action,
        } for log in logs[:100]],
    })


def ghost_export_csv_view(request, campaign_id):
    """Export simulation results as CSV."""
    import csv
    from django.http import HttpResponse
    
    ghost_campaign = GhostCampaign.objects.filter(id=campaign_id).first()
    if not ghost_campaign:
        return JsonResponse({'error': 'Ghost campaign not found'}, status=404)
    
    response = HttpResponse(
        content_type='text/csv',
        headers={'Content-Disposition': f'attachment; filename="ghost-mode-{ghost_campaign.name}.csv"'},
    )
    
    writer = csv.writer(response)
    writer.writerow([
        'timestamp', 'action_type', 'target_name', 'target_url',
        'result_success', 'rating', 'score', 'simulated_action'
    ])
    
    logs = GhostSimulationLog.objects.filter(ghost_campaign=ghost_campaign)
    for log in logs:
        writer.writerow([
            log.started_at.isoformat(),
            log.action_type,
            log.target_name,
            log.target_url,
            log.result_data.get('success', False),
            log.rating,
            log.score,
            log.simulated_action,
        ])
    
    return response
```

---

## Migration Plan

1. Create Ghost Mode models
2. Run migration
3. Build ghost mode interceptor service
4. Update task handlers to check ghost mode
5. Create dashboard UI
6. Add API endpoints
7. Test thoroughly

---

## Benefits

| Feature | Before | After |
|---------|--------|-------|
| Safety | N/A | Zero risk testing |
| Cost | Full cost | Free testing |
| Speed | Wait for real results | Instant simulation |
| Learning | Trial by fire | Guided practice |
| Configuration | Production-only | Safe rehearsal |

Ghost mode enables confident campaign setup with complete visibility into what would happen without any actual consequences.