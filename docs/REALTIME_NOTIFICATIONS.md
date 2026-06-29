# Real-Time Notifications Documentation

## Overview

OpenOutreach now has a complete real-time notification system built on Django Channels. This allows users to receive instant notifications for campaign events, errors, and other important events without needing to manually refresh the page.

## Architecture

The real-time notification system uses a combination of:

1. **Django Channels** - For WebSocket support and real-time communication
2. **ASGI** - Alternative server gateway interface for async Django applications
3. **SSE (Server-Sent Events)** - Fallback for browsers without WebSocket support
4. **Signal-based notification emission** - Automatic notification creation on model changes

## Components

### 1. Consumers (`openoutreach/notifications/consumers.py`)

WebSocket consumers handle client connections and message broadcasting:

- `NotificationConsumer` - General notification stream for all users
- `CampaignStatusConsumer` - Campaign-specific updates

### 2. Routing (`openoutreach/routing.py`)

ASGI routing configuration that maps WebSocket URLs to consumers:

```
/ws/notifications/         -> NotificationConsumer
/ws/campaigns/{id}/       -> CampaignStatusConsumer
```

### 3. SSE Endpoint (`openoutreach/notifications/sse.py`)

Server-Sent Events endpoint for browsers without WebSocket support:

- `/api/notifications/sse/` - SSE stream for notifications

### 4. Notification Signals (`openoutreach/notifications/signals.py`)

Automatic notification creation triggered by Django signals:

- `create_new_message_notification` - New message received
- `create_action_error_notification` - Action errors
- Custom functions for status changes and error notifications

## API Endpoints

### SSE Endpoint

**GET `/api/notifications/sse/`**

Server-Sent Events stream for real-time notifications.

**Example client-side JavaScript:**
```javascript
const eventSource = new EventSource('/api/notifications/sse/');
eventSource.onmessage = (event) => {
    if (event.data === '[closed]') {
        eventSource.close();
    } else {
        const notification = JSON.parse(event.data);
        console.log('Notification:', notification);
        showNotification(notification);
    }
};
eventSource.onerror = (error) => {
    console.error('SSE Error:', error);
    eventSource.close();
};
```

### WebSocket Endpoints

**General Notifications:**
```
ws://localhost:8000/ws/notifications/
```

**Campaign Updates:**
```
ws://localhost:8000/ws/campaigns/{campaign_id}/
```

## Notification Types

| Type | Description |
|------|-------------|
| `campaign_started` | Campaign started |
| `campaign_paused` | Campaign paused |
| `campaign_completed` | Campaign completed |
| `rate_limit_warning` | Rate limit warning |
| `new_message` | New message received |
| `campaign_error` | Campaign error |
| `system_announcement` | System-wide announcement |

## Configuration

### Base Settings (`openoutreach/settings/base.py`)

```python
INSTALLED_APPS = [
    # ...
    "channels",
    # ...
]

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer"
    }
}

ASGI_APPLICATION = "openoutreach.routing.application"
```

### Development Settings (`openoutreach/settings/development.py`)

Uses in-memory channel layer for development. For production, use Redis:

```python
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("localhost", 6379)],
            "capacity": 1500,
            "expiry": 10,
        },
    },
}
```

## Usage

### Emitting Notifications

**To a specific user:**
```python
from openoutreach.notifications.sse import emit_notification_to_user

emit_notification_to_user(user.id, {
    "title": "Campaign Started",
    "message": "Campaign 'Test' has started",
    "notification_type": "campaign_started"
})
```

**To all users in a campaign:**
```python
from openoutreach.notifications.sse import emit_notification_to_campaign

emit_notification_to_campaign(campaign, {
    "title": "Campaign Paused",
    "message": "Campaign has been paused",
    "notification_type": "campaign_paused"
})
```

**Campaign status update:**
```python
from openoutreach.notifications.sse import emit_campaign_status_update

emit_campaign_status_update(campaign.id, "paused", "Campaign manually paused")
```

**Campaign error:**
```python
from openoutreach.notifications.sse import emit_campaign_error

emit_campaign_error(campaign.id, "Rate limit exceeded", deal.id)
```

## Frontend Integration

### UsinguseToast Hook

The frontend already has a `useToast` hook for handling notifications:

```typescript
import { useToast } from '@/components/ui/use-toast';

const { toast } = useToast();
toast({
    title: "New Notification",
    description: "Your campaign has been paused",
});
```

### WebSocket Connection (Optional)

For advanced use cases, you can connect directly to the WebSocket:

```typescript
const socket = new WebSocket('ws://localhost:8000/ws/notifications/');

socket.onmessage = (event) => {
    const notification = JSON.parse(event.data);
    console.log('Received:', notification);
};

socket.onopen = () => {
    console.log('Connected to notification stream');
};

socket.onerror = (error) => {
    console.error('WebSocket error:', error);
};

socket.onclose = () => {
    console.log('Disconnected from notification stream');
};
```

## Production Deployment

For production, you need to:

1. **Install Redis** (for production channel layer)
2. **Configure ASGI** with a proper server (Daphne or Uvicorn)
3. **Set up WebSocket handling** in your reverse proxy (nginx)

### ASGI Configuration

```python
# openoutreach/asgi.py
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from notifications import consumers

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'openoutreach.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter([
            path("ws/notifications/", consumers.NotificationConsumer.as_asgi()),
            path("ws/campaigns/<int:campaign_id>/", consumers.CampaignStatusConsumer.as_asgi()),
        ])
    ),
})
```

### Nginx Configuration

```nginx
location /ws/ {
    proxy_pass http://localhost:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

## Testing

Run the Django check to verify configuration:

```bash
python manage.py check
```

## Files Modified

- `requirements/base.txt` - Added `django-channels`
- `openoutreach/settings/base.py` - Added `channels` to INSTALLED_APPS and CHANNEL_LAYERS config
- `openoutreach/notifications/consumers.py` - New WebSocket consumers
- `openoutreach/notifications/sse.py` - SSE endpoint with Channels support
- `openoutreach/notifications/signals.py` - Notification signals with real-time emission
- `openoutreach/routing.py` - ASGI routing configuration
- `openoutreach/api/views/campaigns.py` - Campaign status change notifications

## Next Steps

For a complete production deployment:

1. Install Redis for production channel layer
2. Configure Daphne/Uvicorn as ASGI server
3. Set up proper SSL/TLS for WebSocket connections
4. Configure rate limiting for WebSocket connections
5. Add WebSocket health monitoring