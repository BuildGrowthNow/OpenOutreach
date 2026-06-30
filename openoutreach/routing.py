"""
ASGI routing configuration for Django Channels.
"""

from typing import Any

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter

from django.core.asgi import get_asgi_application
from django.urls import path

from notifications import consumers

# Type ignore for ASGI application types ( Channels uses dynamic typing)
application: Any = ProtocolTypeRouter(
    {  # type: ignore[assignment]
        # HTTP requests go through Django as usual
        "http": get_asgi_application(),
        # WebSocket requests are routed here
        "websocket": AuthMiddlewareStack(  # type: ignore[call-arg]
            URLRouter(
                [
                    # General notification stream
                    path("ws/notifications/", consumers.NotificationConsumer.as_asgi()),  # type: ignore[misc]
                    # Campaign-specific status updates
                    path("ws/campaigns/<int:campaign_id>/", consumers.CampaignStatusConsumer.as_asgi()),  # type: ignore[misc]
                ]
            )
        ),
    }
)
