"""
Notification Service - Multi-Tenant Notification Routing

Called explicitly from endpoints/daemon after relevant events.
Handles notification creation and real-time WebSocket delivery.
Routes notifications to campaign owner + team members.

Replaces Django signals:
- post_save ChatMessage -> on_new_message
- post_save ActionLog -> on_action_error
- campaign status change -> on_campaign_status_change
"""
import logging
from typing import Optional, List
from openoutreach.mongodb.dal import NotificationDAL
from openoutreach.mongodb import models
from openoutreach.mongodb.models_extended import Notification, ChatMessage, ActionLog

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for creating and managing notifications with multi-tenant team routing"""

    @staticmethod
    async def notify_campaign_users(
        campaign: models.Campaign,
        notification_type: str,
        title: str,
        message: str,
        deal_id: Optional[str] = None,
        data: Optional[dict] = None,
    ) -> List[str]:
        """
        Send notification to ALL users with campaign access (owner + team).

        Args:
            campaign: Campaign model instance
            notification_type: Type of notification (use Notification.TYPE_* constants)
            title: Notification title
            message: Notification message
            deal_id: Optional deal ID reference
            data: Optional additional data

        Returns:
            List of created notification IDs
        """
        recipient_ids = campaign.get_all_user_ids()
        notification_ids = []

        for recipient_id in recipient_ids:
            try:
                notification = NotificationDAL.create_notification(
                    recipient_id=recipient_id,
                    notification_type=notification_type,
                    title=title,
                    message=message,
                    campaign_id=campaign._id,
                    deal_id=deal_id,
                    data=data or {},
                )
                notification_ids.append(notification._id)

                # Real-time delivery via WebSocket
                from openoutreach.api_v2.routers.websocket import emit_notification_to_user
                await emit_notification_to_user(recipient_id, {
                    "notification_id": notification._id,
                    "notification_type": notification_type,
                    "title": title,
                    "message": message,
                    "campaign_id": campaign._id,
                    "deal_id": deal_id,
                })
            except Exception as e:
                logger.error(f"Failed to create notification for user {recipient_id}: {e}")

        logger.info(
            f"Sent '{notification_type}' notification to {len(recipient_ids)} users "
            f"for campaign {campaign._id}"
        )
        return notification_ids

    @staticmethod
    async def on_new_message(chat_message: ChatMessage, campaign: models.Campaign):
        """
        Called after new inbound ChatMessage is created.
        Notifies ALL campaign users (owner + team members).
        """
        if chat_message.is_outgoing:
            return  # Only notify on inbound messages

        try:
            # Get deal to link notification
            deal = models.Deal.get(chat_message.deal_id)
            if not deal or not campaign:
                return

            await NotificationService.notify_campaign_users(
                campaign=campaign,
                notification_type=Notification.TYPE_NEW_MESSAGE,
                title=f"New message in '{campaign.name}'",
                message=chat_message.content[:100],
                deal_id=deal._id,
                data={"message_id": chat_message._id},
            )
        except Exception as e:
            logger.error(f"Failed to create new message notification: {e}")

    @staticmethod
    async def on_action_error(action_log: ActionLog):
        """
        Called after ActionLog with error is created.
        Notifies ALL campaign users (owner + team members).
        """
        if not action_log.error_message:
            return

        try:
            campaign = models.Campaign.get(action_log.campaign_id)
            if not campaign:
                return

            await NotificationService.notify_campaign_users(
                campaign=campaign,
                notification_type=Notification.TYPE_CAMPAIGN_ERROR,
                title=f"Error in '{campaign.name}'",
                message=action_log.error_message[:200],
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
        Notifies ALL campaign users (owner + team members).
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
            await NotificationService.notify_campaign_users(
                campaign=campaign,
                notification_type=notification_type,
                title=f"Campaign '{campaign.name}' {status_change}",
                message=f"Campaign '{campaign.name}' has been {status_change}.",
            )

            # Real-time delivery via WebSocket
            from openoutreach.api_v2.routers.websocket import emit_campaign_status_update
            await emit_campaign_status_update(campaign._id, status_change)
        except Exception as e:
            logger.error(f"Failed to create campaign status notification: {e}")

    @staticmethod
    async def on_rate_limit_warning(
        campaign: models.Campaign,
        profile_username: str,
        warning_message: str
    ):
        """
        Called when rate limit warning is triggered.
        Notifies ALL campaign users (owner + team members).
        """
        try:
            await NotificationService.notify_campaign_users(
                campaign=campaign,
                notification_type=Notification.TYPE_RATE_LIMIT_WARNING,
                title=f"Rate limit warning for {profile_username}",
                message=f"Rate limit in '{campaign.name}': {warning_message}",
            )
        except Exception as e:
            logger.error(f"Failed to create rate limit warning notification: {e}")
