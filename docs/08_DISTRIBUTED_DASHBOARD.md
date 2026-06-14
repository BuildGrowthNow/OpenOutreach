# Distributed Dashboard with WebSocket Updates

Real-time campaign monitoring dashboard that provides instant visibility into campaign performance, lead discovery, and outreach progress without requiring page refreshes.

---

## Overview

The Distributed Dashboard uses a decoupled architecture:
- **Daemon/Worker**: Runs campaigns, emits events via Redis/PubSub
- **API Server**: Handles requests, exposes event stream
- **WebSocket/Server-Sent Events**: Pushes real-time updates to clients
- **Frontend**: React dashboard that automatically updates

This enables users to:
- Watch live campaign activity
- See new leads as they're discovered
- Track connection requests in real-time
- View follow-up messages being sent
- Monitor campaign health metrics

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Distributed Dashboard                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────┐     ┌──────────────┐     ┌──────────────┐     ┌────────┐  │
│  │  Daemon  │────▶│   Redis      │────▶│   API      │────▶│WebSocket │  │
│  │  (Worker)│     │   Pub/Sub    │     │   Server   │     │  Server  │  │
│  └──────────┘     └──────────────┘     └──────────────┘     └────────┘  │
│        │                    │                    │                     │
│        ▼                    ▼                    ▼                     │
│  ┌──────────┐     ┌──────────────┐     ┌──────────────┐                 │
│  │ Campaign │     │  Event Bus   │     │  REST API    │                 │
│  │ Updates  │     │  Queue       │     │  Endpoints   │                 │
│  └──────────┘     └──────────────┘     └──────────────┘                 │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                        Frontend Dashboard                        │   │
│  │  ┌──────────────────────────────────────────────────────────────┐│   │
│  │  │  • Live activity feed                                        ││   │
│  │  │  • Real-time campaign stats                                  ││   │
│  │  │  • New leads discovered                                      ││   │
│  │  │  • Connection acceptances                                    ││   │
│  │  │  • Follow-up messages                                        ││   │
│  │  └──────────────────────────────────────────────────────────────┘│   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### 1. Event Publisher Service (`linkedin/services/events.py`)

```python
import json
import redis
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, asdict

from django.conf import settings


@dataclass
class CampaignEvent:
    """Event data structure for dashboard updates."""
    
    event_type: str  # 'lead_found', 'connection_sent', 'connected', 'message_sent', etc.
    campaign_id: str
    campaign_name: str
    lead_id: Optional[str] = None
    lead_name: Optional[str] = None
    lead_url: Optional[str] = None
    public_identifier: Optional[str] = None
    details: dict = None
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat() + 'Z'
        if self.details is None:
            self.details = {}
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))


class EventPublisher:
    """Publishes events to Redis for dashboard consumption."""
    
    def __init__(self):
        redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        self.channel_prefix = 'openoutreach:events:'
    
    def publish(self, event: CampaignEvent):
        """Publish event to Redis channel."""
        channel = f"{self.channel_prefix}{event.campaign_id}"
        message = event.to_json()
        
        # Publish to channel
        self.redis_client.publish(channel, message)
        
        # Also store in stream for new connections
        stream_key = f"{self.channel_prefix}stream"
        self.redis_client.xadd(stream_key, {'message': message})
    
    def publish_lead_found(self, campaign_id: str, campaign_name: str, lead_name: str, lead_url: str, public_identifier: str):
        """Publish lead discovery event."""
        event = CampaignEvent(
            event_type='lead_found',
            campaign_id=campaign_id,
            campaign_name=campaign_name,
            lead_name=lead_name,
            lead_url=lead_url,
            public_identifier=public_identifier,
            details={'source': 'linkedin_search'}
        )
        self.publish(event)
    
    def publish_connection_sent(self, campaign_id: str, campaign_name: str, lead_name: str, lead_url: str):
        """Publish connection request sent event."""
        event = CampaignEvent(
            event_type='connection_sent',
            campaign_id=campaign_id,
            campaign_name=campaign_name,
            lead_name=lead_name,
            lead_url=lead_url,
        )
        self.publish(event)
    
    def publish_connected(self, campaign_id: str, campaign_name: str, lead_name: str, lead_url: str):
        """Publish connection accepted event."""
        event = CampaignEvent(
            event_type='connected',
            campaign_id=campaign_id,
            campaign_name=campaign_name,
            lead_name=lead_name,
            lead_url=lead_url,
        )
        self.publish(event)
    
    def publish_message_sent(self, campaign_id: str, campaign_name: str, lead_name: str, lead_url: str):
        """Publish follow-up message sent event."""
        event = CampaignEvent(
            event_type='message_sent',
            campaign_id=campaign_id,
            campaign_name=campaign_name,
            lead_name=lead_name,
            lead_url=lead_url,
        )
        self.publish(event)
    
    def publish_conversion(self, campaign_id: str, campaign_name: str, lead_name: str, lead_url: str):
        """Publish conversion event."""
        event = CampaignEvent(
            event_type='conversion',
            campaign_id=campaign_id,
            campaign_name=campaign_name,
            lead_name=lead_name,
            lead_url=lead_url,
            details={'stage': 'converted'},
        )
        self.publish(event)


# Convenience function
publish_event = EventPublisher()
```

### 2. API Endpoints for Events (`linkedin/api/events.py`)

```python
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
import redis
import json
from datetime import datetime, timedelta

from openoutreach.core.models import Campaign


def events.stream_view(request, campaign_id):
    """
    Server-Sent Events endpoint for real-time dashboard updates.
    
    Clients connect via:
    var eventSource = new EventSource('/api/campaigns/{id}/events/');
    
    Events received:
    {
      "event_type": "lead_found",
      "campaign_id": "...",
      "campaign_name": "...",
      "lead_name": "John Doe",
      "lead_url": "https://linkedin.com/in/johndoe",
      "timestamp": "2024-01-15T12:00:00Z"
    }
    """
    campaign = Campaign.objects.filter(id=campaign_id).first()
    if not campaign:
        return JsonResponse({'error': 'Campaign not found'}, status=404)
    
    response = HttpResponse(
        content_type='text/event-stream',
        content_type='text/event-stream; charset=utf-8'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'  # Disable nginx buffering
    
    # Send initial connection event
    response.write(f'data: {json.dumps({"event": "connected", "timestamp": datetime.utcnow().isoformat() + "Z"})}\n\n')
    response.flush()
    
    # Connect to Redis
    redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
    redis_client = redis.from_url(redis_url, decode_responses=True)
    channel = f'openoutreach:events:{campaign_id}'
    
    # Subscribe to channel
    pubsub = redis_client.pubsub()
    pubsub.subscribe(channel)
    
    try:
        for message in pubsub.listen():
            if message['type'] == 'message':
                event_data = json.loads(message['data'])
                response.write(f'data: {json.dumps(event_data)}\n\n')
                response.flush()
    except GeneratorExit:
        pass
    finally:
        pubsub.unsubscribe()
    
    return response


def events.stats_view(request, campaign_id):
    """
    Get current campaign statistics.
    
    GET /api/campaigns/{id}/stats/
    """
    campaign = Campaign.objects.filter(id=campaign_id).first()
    if not campaign:
        return JsonResponse({'error': 'Campaign not found'}, status=404)
    
    from linkedoutreach.crm.models import Deal, Lead
    from linkedoutreach.linkedin.models import ActionLog
    from datetime import timedelta
    
    now = timezone.now()
    since_24h = now - timedelta(hours=24)
    
    # Calculate metrics
    total_leads = Deal.objects.filter(campaign=campaign).count()
    qualified_leads = Deal.objects.filter(campaign=campaign, state='QUALIFIED').count()
    connected_leads = Deal.objects.filter(campaign=campaign, state='CONNECTED').count()
    converted_leads = Deal.objects.filter(campaign=campaign, outcome='converted').count()
    
    # 24h stats
    connections_24h = ActionLog.objects.filter(
        linkedin_profile=campaign.linkedinprofile_set.first(),
        action_type='connect',
        created_at__gte=since_24h,
    ).count()
    
    messages_24h = ActionLog.objects.filter(
        linkedin_profile=campaign.linkedinprofile_set.first(),
        action_type='follow_up',
        created_at__gte=since_24h,
    ).count()
    
    stats = {
        'campaign_id': str(campaign.id),
        'campaign_name': campaign.name,
        'total_leads': total_leads,
        'qualified_leads': qualified_leads,
        'connected_leads': connected_leads,
        'converted_leads': converted_leads,
        'connections_24h': connections_24h,
        'messages_24h': messages_24h,
        'response_rate': round(converted_leads / max(1, connected_leads), 3) if connected_leads > 0 else 0,
        'last_updated': now.isoformat(),
    }
    
    return JsonResponse(stats)


def events.activity_feed_view(request, campaign_id):
    """
    Get recent activity feed.
    
    GET /api/campaigns/{id}/activity-feed/?limit=50
    """
    campaign = Campaign.objects.filter(id=campaign_id).first()
    if not campaign:
        return JsonResponse({'error': 'Campaign not found'}, status=404)
    
    limit = int(request.GET.get('limit', 50))
    
    # Get recent deals with their activities
    from linkedoutreach.crm.models import Deal
    from linkedoutreach.chat.models import ChatMessage
    
    recent_deals = Deal.objects.filter(campaign=campaign).order_by('-update_date')[:limit]
    
    activity = []
    for deal in recent_deals:
        deal_activity = {
            'type': 'deal',
            'id': str(deal.id),
            'lead_name': deal.lead.public_identifier,
            'state': deal.state,
            'outcome': deal.outcome,
            'updated_at': deal.update_date.isoformat(),
        }
        
        # Get last message if exists
        last_message = ChatMessage.objects.filter(related_object_id=deal.id).first()
        if last_message:
            deal_activity['last_message'] = {
                'content': last_message.content[:100] + '...' if len(last_message.content) > 100 else last_message.content,
                'direction': 'outgoing' if last_message.is_outgoing else 'incoming',
                'created_at': last_message.created_at.isoformat(),
            }
        
        activity.append(deal_activity)
    
    return JsonResponse({'activity': activity, 'total': len(activity)})
```

### 3. Frontend Dashboard Component

```typescript
interface CampaignEvent {
  event_type: string;
  campaign_id: string;
  campaign_name: string;
  lead_id?: string;
  lead_name?: string;
  lead_url?: string;
  public_identifier?: string;
  details?: any;
  timestamp: string;
}

interface CampaignStats {
  campaign_id: string;
  campaign_name: string;
  total_leads: number;
  qualified_leads: number;
  connected_leads: number;
  converted_leads: number;
  connections_24h: number;
  messages_24h: number;
  response_rate: number;
  last_updated: string;
}

export function DistributedCampaignDashboard({ campaignId }: { campaignId: string }) {
  const [stats, setStats] = useState<CampaignStats | null>(null);
  const [events, setEvents] = useState<CampaignEvent[]>([]);
  const [eventSource, setEventSource] = useState<EventSource | null>(null);
  const [loading, setLoading] = useState(true);

  // Fetch initial stats
  useEffect(() => {
    fetch(`/api/campaigns/${campaignId}/stats/`)
      .then(r => r.json())
      .then(setStats)
      .finally(() => setLoading(false));
  }, [campaignId]);

  // Connect to SSE event stream
  useEffect(() => {
    const source = new EventSource(`/api/campaigns/${campaignId}/events/`);
    
    source.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        // Update stats on key events
        if (data.event_type === 'lead_found') {
          setStats(prev => prev ? { ...prev, total_leads: prev.total_leads + 1 } : null);
        } else if (data.event_type === 'connected') {
          setStats(prev => prev ? { ...prev, connected_leads: prev.connected_leads + 1 } : null);
        } else if (data.event_type === 'conversion') {
          setStats(prev => prev ? { ...prev, converted_leads: prev.converted_leads + 1 } : null);
        }
        
        // Add to events array
        setEvents(prev => [data, ...prev]);
      } catch (e) {
        console.error('Error parsing event:', e);
      }
    };
    
    source.onerror = (error) => {
      console.error('SSE error:', error);
      source.close();
    };
    
    setEventSource(source);
    
    return () => source.close();
  }, [campaignId]);

  if (loading) return <LoadingSpinner />;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Stats Dashboard */}
      <div className="lg:col-span-1 space-y-6">
        <StatsCard title="Total Leads" value={stats?.total_leads || 0} />
        <StatsCard title="Connected" value={stats?.connected_leads || 0} />
        <StatsCard title="Converted" value={stats?.converted_leads || 0} />
        <StatsCard title="Connections (24h)" value={stats?.connections_24h || 0} />
        <StatsCard title="Response Rate" value={`${(stats?.response_rate || 0) * 100}%`} />
      </div>

      {/* Live Activity Feed */}
      <div className="lg:col-span-2">
        <ActivityFeed events={events} />
      </div>
    </div>
  );
}

function StatsCard({ title, value }: { title: string; value: string | number }) {
  return (
    <div className="bg-white p-6 rounded-lg border">
      <div className="text-sm text-gray-500 mb-2">{title}</div>
      <div className="text-4xl font-bold">{value}</div>
    </div>
  );
}

function ActivityFeed({ events }: { events: CampaignEvent[] }) {
  return (
    <div className="bg-white rounded-lg border overflow-hidden">
      <div className="p-4 border-b">
        <h3 className="font-semibold">Live Activity</h3>
      </div>
      
      <div className="max-h-96 overflow-y-auto">
        {events.map((event, index) => (
          <ActivityItem key={index} event={event} />
        ))}
        
        {events.length === 0 && (
          <div className="p-8 text-center text-gray-500">
            No activity yet. Waiting for campaign to start...
          </div>
        )}
      </div>
    </div>
  );
}

function ActivityItem({ event }: { event: CampaignEvent }) {
  const icons = {
    lead_found: '🔍',
    connection_sent: '🤝',
    connected: '✅',
    message_sent: '💬',
    conversion: '🎉',
  };
  
  const colors = {
    lead_found: 'bg-blue-100 text-blue-800',
    connection_sent: 'bg-purple-100 text-purple-800',
    connected: 'bg-green-100 text-green-800',
    message_sent: 'bg-orange-100 text-orange-800',
    conversion: 'bg-yellow-100 text-yellow-800',
  };
  
  return (
    <div className="p-4 border-b last:border-b-0 hover:bg-gray-50 transition-colors">
      <div className="flex items-start gap-3">
        <div className={`text-2xl ${colors[event.event_type as keyof typeof colors]}`}>
          {icons[event.event_type as keyof typeof icons]}
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">
              {event.event_type.replace('_', ' ').toUpperCase()}
            </span>
            <span className="text-xs text-gray-500">
              {new Date(event.timestamp).toLocaleTimeString()}
            </span>
          </div>
          {event.lead_name && (
            <p className="text-sm text-gray-600 mt-1">
              {event.lead_name}
            </p>
          )}
          {event.lead_url && (
            <a
              href={event.lead_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-blue-500 hover:underline mt-1 block"
            >
              {event.lead_url}
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
```

### 4. Integration with Task Handlers

Update `linkedin/tasks/connect.py` to emit events:

```python
def handle_connect(task, session, qualifiers):
    """Handle connection task with event publishing."""
    from linkedoutreach.linkedin.services.events import EventPublisher
    from linkedoutreach.linkedin.services.events import publish_event
    
    campaign = session.campaign
    publisher = EventPublisher()
    
    # ... existing lead finding logic ...
    
    # Publish event when lead found
    publisher.publish_lead_found(
        campaign_id=str(campaign.id),
        campaign_name=campaign.name,
        lead_name=profile.get('first_name', 'Unknown'),
        lead_url=profile.get('linkedin_url'),
        public_identifier=public_id,
    )
    
    # ... existing connection sending logic ...
    
    # Publish event when connection sent
    publisher.publish_connection_sent(
        campaign_id=str(campaign.id),
        campaign_name=campaign.name,
        lead_name=profile.get('first_name', 'Unknown'),
        lead_url=profile.get('linkedin_url'),
    )
    
    # ... rest of handler
```

Update `linkedin/tasks/follow_up.py` to emit events:

```python
def handle_follow_up(task, session, qualifiers):
    """Handle follow-up task with event publishing."""
    from linkedoutreach.linkedin.services.events import EventPublisher
    
    publisher = EventPublisher()
    
    # ... existing follow-up logic ...
    
    # Publish event when message sent
    publisher.publish_message_sent(
        campaign_id=str(campaign.id),
        campaign_name=campaign.name,
        lead_name=lead.public_identifier,
        lead_url=lead.linkedin_url,
    )
    
    # ... rest of handler
```

### 5. Redis Setup

Add Redis to `docker-compose.yml`:

```yaml
services:
  redis:
    image: redis:7-alpine
    container_name: openoutreach-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
  
  app:
    # ... existing app config ...
    depends_on:
      - redis

volumes:
  redis_data:
```

---

## Migration Plan

1. Add Redis to deployment
2. Create event publisher service
3. Add API endpoints for events
4. Update task handlers to emit events
5. Build frontend dashboard
6. Deploy and test

---

## Benefits

| Feature | Before | After |
|---------|--------|-------|
| Visibility | Check logs, admin panel | Real-time live view |
| Updates | Manual refresh | Auto-push via SSE |
| Activity | Historical only | Live + historical |
| Alerts | Email/notification | In-app real-time |
| Accessibility | Admin login required | Any logged-in user |

The distributed dashboard provides immediate visibility into campaign operations, making it much easier to monitor and manage outreach campaigns in real-time.