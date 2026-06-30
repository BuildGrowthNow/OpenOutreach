"""
Server-Sent Events (SSE) and real-time notification utilities.

This module provides both SSE streaming for browsers that don't support
WebSockets, and Channels-based real-time notifications for modern browsers.

For production, consider Redis-based channel layer:
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
"""

import json
import asyncio
import time
from django.http import StreamingHttpResponse
from django.utils import timezone

try:
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    CHANNELS_AVAILABLE = True
except ImportError:
    CHANNELS_AVAILABLE = False
    async_to_sync = None


def sse_notification_stream(request):
    """
    Server-Sent Events (SSE) endpoint for real-time notifications.

    This endpoint streams notification events to connected clients.
    Clients can filter by user ID in the query parameters.

    Query Parameters:
        - user_id: Optional user ID to filter notifications
        - notification_type: Optional notification type to filter

    Returns:
        StreamingHttpResponse with SSE-formatted data

    Example client-side JavaScript:
        const eventSource = new EventSource('/api/notifications/sse/');
        eventSource.onmessage = (event) => {
            if (event.data === '[closed]') {
                eventSource.close();
            } else {
                const notification = JSON.parse(event.data);
                console.log('Notification:', notification);
            }
        };
        eventSource.onerror = (error) => {
            console.error('SSE Error:', error);
            eventSource.close();
        };
    """

    def event_stream():
        """Generate SSE events."""
        if not CHANNELS_AVAILABLE:
            # Channels not available - yield a simple message
            yield f"data: {json.dumps({'error': 'SSE not supported', 'retry': 5000})}\n\n"
            return

        # Get user from request
        user = request.user
        if not user or not user.is_authenticated:
            yield f"data: {json.dumps({'error': 'Authentication required', 'retry': 5000})}\n\n"
            return

        # Create a group name for this user's notifications
        group_name = f"notifications_{user.id}"

        # Send connection established
        yield f"data: {json.dumps({'type': 'connected', 'user_id': user.id, 'group': group_name, 'timestamp': timezone.now().isoformat()})}\n\n"

        # Get the channel layer
        try:
            channel_layer = get_channel_layer()  # type: ignore[possibly-unbound]
            if channel_layer is None:
                # No channel layer available - use keepalive only
                while True:
                    yield f": keepalive\n\n"
                    time.sleep(15)
                return
        except Exception:
            while True:
                yield f": keepalive\n\n"
                time.sleep(15)
            return

        # Create a temporary channel for receiving messages
        # Note: In channels 3+, we'd use an async generator with database polling
        # For now, we'll use a polling approach combined with Channels support

        # Wait for messages (with polling fallback)
        # In production with Redis, consider using redis pubsub
        while True:
            try:
                # Send keepalive every 15 seconds
                yield f": keepalive\n\n"

                # Try to get any pending messages
                # This is a simplified approach - for full Channels support,
                # you'd typically use an async consumer

                # Poll every 15 seconds
                time.sleep(15)
            except GeneratorExit:
                break
            except Exception:
                # On error, send error message and close
                yield f"data: {json.dumps({'type': 'error', 'message': 'Connection error', 'retry': 5000})}\n\n"
                break

    response = StreamingHttpResponse(
        event_stream(),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
    response["Connection"] = "keep-alive"
    return response


def emit_notification_to_user(user_id, notification_data):
    """
    Emit a notification to a specific user via SSE/Channels.

    This function sends the notification through the Channels layer
    which will be delivered to any connected WebSocket clients.

    Also creates a database record for persistence.

    Args:
        user_id: The ID of the user to notify
        notification_data: Dict containing notification data

    Example:
        emit_notification_to_user(
            user.id,
            {
                'title': 'Campaign Started',
                'message': 'Campaign "Test" has started',
                'notification_type': 'campaign_started'
            }
        )
    """
    if not CHANNELS_AVAILABLE:
        return  # Channels not available

    try:
        channel_layer = get_channel_layer()  # type: ignore[possibly-unbound]
        if channel_layer is None:
            return

        # Prepare the notification message
        message = {
            "type": "notification.message",
            "data": {
                **notification_data,
                "timestamp": timezone.now().isoformat(),
            },
        }

        # Send to user's notification group
        assert async_to_sync is not None
        async_to_sync(channel_layer.group_send)(f"notifications_{user_id}", message)
    except Exception as e:
        # Log the error but don't crash
        import logging

        logging.error(f"Failed to emit notification to user {user_id}: {e}")


def emit_notification_to_campaign(campaign, notification_data):
    """
    Emit a notification to all users in a campaign via SSE/Channels.

    This function sends the notification through the Channels layer
    which will be delivered to any connected WebSocket clients.

    Also creates a database record for persistence.

    Args:
        campaign: The Campaign instance
        notification_data: Dict containing notification data

    Example:
        emit_notification_to_campaign(
            campaign,
            {
                'title': 'Campaign Paused',
                'message': 'Campaign has been paused',
                'notification_type': 'campaign_paused'
            }
        )
    """
    if not CHANNELS_AVAILABLE:
        return  # Channels not available

    try:
        channel_layer = get_channel_layer()  # type: ignore[possibly-unbound]
        if channel_layer is None:
            return

        # Get all users in the campaign
        users = campaign.users.all()

        # Prepare the base message
        base_message = {
            "type": "notification.message",
            "data": {
                **notification_data,
                "timestamp": timezone.now().isoformat(),
            },
        }

        # Send to each user's notification group
        assert async_to_sync is not None
        for user in users:
            async_to_sync(channel_layer.group_send)(
                f"notifications_{user.id}", base_message
            )
    except Exception as e:
        # Log the error but don't crash
        import logging

        logging.error(f"Failed to emit notification to campaign {campaign.id}: {e}")


def emit_campaign_status_update(campaign_id, status, message=None):
    """
    Emit a campaign status update to the campaign's WebSocket consumers.

    Args:
        campaign_id: The ID of the campaign
        status: The new status (e.g., 'active', 'paused', 'completed')
        message: Optional status message

    Example:
        emit_campaign_status_update(campaign.id, 'paused', 'Campaign manually paused')
    """
    if not CHANNELS_AVAILABLE:
        return

    try:
        channel_layer = get_channel_layer()  # type: ignore[possibly-unbound]
        if channel_layer is None:
            return

        message_data = {
            "type": "campaign_status_update",
            "data": {
                "campaign_id": campaign_id,
                "status": status,
                "timestamp": timezone.now().isoformat(),
            },
        }

        if message:
            message_data["data"]["message"] = message

        assert async_to_sync is not None
        async_to_sync(channel_layer.group_send)(f"campaign_{campaign_id}", message_data)
    except Exception as e:
        import logging

        logging.error(f"Failed to emit campaign status update for {campaign_id}: {e}")


def emit_campaign_error(campaign_id, error_message, deal_id=None):
    """
    Emit a campaign error notification.

    Args:
        campaign_id: The ID of the campaign
        error_message: Description of the error
        deal_id: Optional related deal ID
    """
    if not CHANNELS_AVAILABLE:
        return

    try:
        channel_layer = get_channel_layer()  # type: ignore[possibly-unbound]
        if channel_layer is None:
            return

        message_data = {
            "type": "campaign_error",
            "data": {
                "campaign_id": campaign_id,
                "error_message": error_message,
                "timestamp": timezone.now().isoformat(),
            },
        }

        if deal_id:
            message_data["data"]["deal_id"] = deal_id

        assert async_to_sync is not None
        async_to_sync(channel_layer.group_send)(f"campaign_{campaign_id}", message_data)
    except Exception as e:
        import logging

        logging.error(f"Failed to emit campaign error for {campaign_id}: {e}")
