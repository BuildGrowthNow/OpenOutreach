"""
Notification Service - replaces Django signals for notification creation.

Called explicitly from endpoints/daemon after relevant events.
Handles notification creation and real-time WebSocket delivery.

Replaces Django signals:
- post_save ChatMessage -> on_new_message
- post_save ActionLog -> on_action_error
- campaign status change -> on_campaign_status_change
"""
import logging
from typing import Optional, Any
from openoutreach.mongodb.dal import NotificationDAL
from openoutreach.mongodb import models
from openoutreach.mongodb.models_extended import Notification, ChatMessage, ActionLog

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for creating and managing notifications (replaces Django signals)"""

    @staticmethod
    async def on_new_message(chat_message: ChatMessage, campaign: models.Campaign):
        """
        Called after new inbound ChatMessage is created.
        Replaces post_save signal from Django.
        """
        if chat_message.is_outgoing:
            return  # Only notify on inbound messages

        try:
            # Get deal to link notification
            deal = models.Deal.get(chat_message.deal_id)
            if not deal or not campaign:
                return

            # Create notification
            notification = NotificationDAL.create_notification(
                recipient_id=campaign.user_id,
                notification_type=Notification.TYPE_NEW_MESSAGE,
                title=f"New message in '{campaign.name}'",
                message=chat_message.content[:100],
                campaign_id=campaign._id,
                deal_id=deal._id,
                data={"message_id": chat_message._id},
            )

            # Real-time delivery via WebSocket
            from openoutreach.api_v2.routers.websocket import emit_notification_to_user
            await emit_notification_to_user(campaign.user_id, {
                "notification_id": notification._id,
                "notification_type": Notification.TYPE_NEW_MESSAGE,
                "title": notification.title,
                "message": notification.message,
            })
        except Exception as e:
            logger.error(f"Failed to create new message notification: {e}")

    @staticmethod
    async def on_action_error(action_log: ActionLog):
        """
        Called after ActionLog with error is created.
        Replaces post_save signal from Django.
        """
        if not action_log.error_message:
            return

        try:
            campaign = models.Campaign.get(action_log.campaign_id)
            if not campaign:
                return

            NotificationDAL.create_notification(
                recipient_id=campaign.user_id,
                notification_type=Notification.TYPE_CAMPAIGN_ERROR,
                title=f"Error in '{campaign.name}'",
                message=action_log.error_message[:200],
                campaign_id=campaign._id,
            )

            # Real-time delivery via WebSocket
            from openoutreach.api_v2.routers.websocket import emit_campaign_error
            await emit_campaign_error(campaign._id, action_log.error_message)
        except Exception as e:
            logger.error(f"Failed to create action error notification: {e}")

    @staticmethod
    async def on_campaign_status_change(campaign: models.Campaign, status_change: str):
        """
        Called from campaign status endpoint.
        Replaces manual signal call from Django.
        """
        type_map = {
            "started": Notification.TYPE_CAMPAIGN_STARTED,
            "paused": Notification.TYPE_CAMPAIGN_PAUSED,
            "completed": Notification.TYPE_CAMPAIGN_COMPLETED,
        }
        notification_type = type_map.get(status_change)
        if not notification_type:
            return

        try:
            NotificationDAL.create_notification(
                recipient_id=campaign.user_id,
                notification_type=notification_type,
                title=f"Campaign '{campaign.name}' {status_change}",
                message=f"Campaign '{campaign.name}' has been {status_change}.",
                campaign_id=campaign._id,
            )

            # Real-time delivery via WebSocket
            from openoutreach.api_v2.routers.websocket import emit_campaign_status_update
            await emit_campaign_status_update(campaign._id, status_change)
        except Exception as e:
            logger.error(f"Failed to create campaign status notification: {e}")

    @staticmethod
    async def on_rate_limit_warning(linkedin_profile_id: str, warning: Any, user_id: str):
        """
        Called when rate limit warning is triggered.
        """
        try:
            NotificationDAL.create_notification(
                recipient_id=user_id,
                notification_type=Notification.TYPE_RATE_LIMIT_WARNING,
                title="Rate limit warning",
                message=f"Rate limit exceeded for {warning.action_type}: {warning.limit_exceeded} actions attempted, limit is {warning.actual_count}",
                data={"warning_id": warning._id, "linkedin_profile_id": linkedin_profile_id},
            )

            # Real-time delivery via WebSocket
            from openoutreach.api_v2.routers.websocket import emit_notification_to_user
            await emit_notification_to_user(user_id, {
                "notification_type": Notification.TYPE_RATE_LIMIT_WARNING,
                "title": "Rate limit warning",
                "message": f"Rate limit exceeded for {warning.action_type}",
            })
        except Exception as e:
            logger.error(f"Failed to create rate limit warning notification: {e}")
