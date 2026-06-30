"""
Django Channels consumers for real-time notification delivery.
"""

import json
from channels.generic.websocket import AsyncWebsocketConsumer  # type: ignore[import-untyped]
from channels.db import database_sync_to_async  # type: ignore[import-untyped]
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time notifications.

    Clients connect to /ws/notifications/ and receive real-time
    updates when new notifications are created.
    """

    async def connect(self):
        """Handle WebSocket connection."""
        self.user = self.scope.get("user")

        # Check if user is authenticated
        if not self.user or not self.user.is_authenticated:
            await self.close()
            return

        # Create group name for this user's notifications
        self.group_name = f"notifications_{self.user.id}"

        # Add user to their notification group
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        await self.accept()

        # Send connection confirmation
        await self.send(
            text_data=json.dumps(
                {
                    "type": "connected",
                    "message": "Connected to notification stream",
                    "timestamp": timezone.now().isoformat(),
                }
            )
        )

    async def disconnect(self, code: int) -> None:
        """Handle WebSocket disconnection."""
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(
        self, text_data: str | None = None, bytes_data: bytes | None = None
    ):
        """Handle incoming WebSocket messages."""
        # Only handle text data, ignore bytes
        if text_data is None:
            return
        try:
            data = json.loads(text_data)
            action = data.get("action")

            if action == "ping":
                await self.send(
                    text_data=json.dumps(
                        {"type": "pong", "timestamp": timezone.now().isoformat()}
                    )
                )
            elif action == "mark_read":
                # Client requests to mark a notification as read
                notification_id = data.get("notification_id")
                await self.mark_notification_as_read(notification_id)
            else:
                await self.send(
                    text_data=json.dumps(
                        {"type": "error", "message": f"Unknown action: {action}"}
                    )
                )
        except json.JSONDecodeError:
            await self.send(
                text_data=json.dumps({"type": "error", "message": "Invalid JSON"})
            )

    @database_sync_to_async
    def mark_notification_as_read(self, notification_id):
        """Mark a notification as read."""
        from .models import Notification

        try:
            notification = Notification.objects.get(
                id=notification_id, recipient=self.user
            )
            notification.mark_as_read()
        except Notification.DoesNotExist:
            pass

    async def notification_message(self, event):
        """
        Handle notification messages from the channel layer.

        This method is called when a notification is sent to the group.
        """
        notification_data = event["data"]

        await self.send(
            text_data=json.dumps(
                {
                    "type": "notification",
                    "data": notification_data,
                    "timestamp": timezone.now().isoformat(),
                }
            )
        )

    async def notification_broadcast(self, event):
        """Handle broadcast notification messages."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "broadcast",
                    "data": event["data"],
                    "timestamp": timezone.now().isoformat(),
                }
            )
        )


class CampaignStatusConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time campaign status updates.

    Clients connect to /ws/campaigns/{campaign_id}/ and receive
    real-time updates about campaign status changes.
    """

    async def connect(self):
        """Handle campaign WebSocket connection."""
        self.user = self.scope.get("user")

        # Check if user is authenticated
        if not self.user or not self.user.is_authenticated:
            await self.close()
            return

        # Get campaign_id from URL route (typed as Any for compatibility)
        url_route = self.scope.get("url_route", {})
        kwargs = url_route.get("kwargs", {})
        campaign_id = kwargs.get("campaign_id")
        if campaign_id is not None:
            self.campaign_id = campaign_id
        else:
            # Fallback - direct access with type ignore for TypedDict
            self.campaign_id = self.scope["url_route"]["kwargs"]["campaign_id"]  # type: ignore[index]

        # Verify user has access to this campaign
        has_access = await self.check_campaign_access(self.campaign_id)
        if not has_access:
            await self.close()
            return

        # Create group name for this campaign
        self.group_name = f"campaign_{self.campaign_id}"

        # Add user to the campaign group
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        await self.accept()

        # Send connection confirmation
        await self.send(
            text_data=json.dumps(
                {
                    "type": "connected",
                    "message": f"Connected to campaign {self.campaign_id} updates",
                    "timestamp": timezone.now().isoformat(),
                }
            )
        )

    async def disconnect(self, code: int) -> None:
        """Handle campaign WebSocket disconnection."""
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    @database_sync_to_async
    def check_campaign_access(self, campaign_id):
        """Check if user has access to the campaign."""
        from openoutreach.core.models import Campaign

        try:
            assert self.user is not None
            campaign = Campaign.objects.get(id=campaign_id)
            return campaign.users.filter(id=self.user.id).exists()
        except Campaign.DoesNotExist:
            return False

    async def campaign_status_update(self, event):
        """Handle campaign status update messages."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "campaign_status_update",
                    "data": event["data"],
                    "timestamp": timezone.now().isoformat(),
                }
            )
        )

    async def campaign_error(self, event):
        """Handle campaign error messages."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "campaign_error",
                    "data": event["data"],
                    "timestamp": timezone.now().isoformat(),
                }
            )
        )
