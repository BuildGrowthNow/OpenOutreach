"""
Django signals for notification creation with real-time delivery.

Signals:
- create_new_message_notification: When a new message is received
- create_campaign_status_change_notification: For campaign status changes
- create_rate_limit_warning_notification: For rate limit warnings
- create_campaign_error_notification: For campaign errors
- create_action_error_notification: For action log errors
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Notification


def get_model(app_label, model_name):
    """Lazy model lookup to avoid circular imports."""
    from django.apps import apps

    return apps.get_model(app_label, model_name)


def create_notification_with_realtime(
    recipient, notification_type, title, message, **kwargs
):
    """
    Create a notification and emit real-time update if Channels is available.

    Args:
        recipient: User or list of users to notify
        notification_type: Type of notification
        title: Notification title
        message: Notification message
        **kwargs: Additional notification data (campaign, deal, etc.)
    """
    # Import here to avoid circular imports
    try:
        from .sse import emit_notification_to_user
    except ImportError:
        emit_notification_to_user = None

    # Support single user or multiple users
    recipients = recipient if isinstance(recipient, (list, tuple)) else [recipient]

    notifications_created = []
    for user in recipients:
        notification = Notification.objects.create(
            recipient=user,
            notification_type=notification_type,
            title=title,
            message=message,
            **kwargs,
        )
        notifications_created.append(notification)

        # Emit real-time notification if Channels is available
        if emit_notification_to_user:
            try:
                notification_data = {
                    "notification_id": notification.id,  # type: ignore[attr-defined]
                    "notification_type": notification_type,
                    "title": title,
                    "message": message,
                    "timestamp": timezone.now().isoformat(),
                }
                # Merge kwargs into data if they're not None
                if kwargs.get("campaign"):
                    notification_data["campaign_id"] = kwargs["campaign"].id
                if kwargs.get("deal"):
                    notification_data["deal_id"] = kwargs["deal"].id
                if kwargs.get("data"):
                    notification_data["data"] = kwargs["data"]

                emit_notification_to_user(user.id, notification_data)
            except Exception:
                # Don't crash if emit fails
                pass

    return notifications_created


def create_campaign_status_change_notification(campaign, status_change, user=None):
    """
    Create a notification when a campaign status changes.

    Args:
        campaign: The Campaign instance
        status_change: String describing the change (e.g., "paused", "started", "completed")
        user: Optional specific user to notify (defaults to all campaign users)
    """
    Notification = get_model("notifications", "Notification")

    try:
        from .sse import emit_notification_to_user, emit_campaign_status_update
    except ImportError:
        emit_notification_to_user = None
        emit_campaign_status_update = None

    if status_change == "paused":
        title = f"Campaign '{campaign.name}' paused"
        message = f"The campaign '{campaign.name}' has been paused by a user."
        notification_type = Notification.TYPE_CAMPAIGN_PAUSED
        status_value = "paused"
    elif status_change == "started":
        title = f"Campaign '{campaign.name}' started"
        message = f"The campaign '{campaign.name}' has been started by a user."
        notification_type = Notification.TYPE_CAMPAIGN_STARTED
        status_value = "active"
    elif status_change == "completed":
        title = f"Campaign '{campaign.name}' completed"
        message = f"The campaign '{campaign.name}' has completed all its activities."
        notification_type = Notification.TYPE_CAMPAIGN_COMPLETED
        status_value = "completed"
    else:
        return  # Unknown status change

    # Notify all users associated with the campaign
    recipients = [user] if user else campaign.users.all()

    if not recipients:
        return

    for u in recipients:
        notification = Notification.objects.create(
            recipient=u,
            notification_type=notification_type,
            title=title,
            message=message,
            campaign=campaign,
        )

        # Emit real-time notification if Channels is available
        if emit_notification_to_user:
            try:
                emit_notification_to_user(
                    u.id,
                    {
                        "notification_id": notification.id,
                        "notification_type": notification_type,
                        "title": title,
                        "message": message,
                        "timestamp": timezone.now().isoformat(),
                    },
                )
            except Exception:
                pass

    # Emit campaign status update via WebSocket
    if emit_campaign_status_update:
        try:
            emit_campaign_status_update(campaign.id, status_value, message)
        except Exception:
            pass


def create_rate_limit_warning_notification(
    campaign, profile_username, warning_message, user=None
):
    """
    Create a notification for rate limit warnings.

    Args:
        campaign: The Campaign instance
        profile_username: The LinkedIn profile username that hit the rate limit
        warning_message: Description of the rate limit warning
        user: Optional specific user to notify (defaults to all campaign users)
    """
    Notification = get_model("notifications", "Notification")

    try:
        from .sse import emit_notification_to_user
    except ImportError:
        emit_notification_to_user = None

    title = f"Rate limit warning for {profile_username}"
    message = f"Rate limit warning for '{campaign.name}': {warning_message}"

    recipients = [user] if user else campaign.users.all()

    if not recipients:
        return

    for u in recipients:
        notification = Notification.objects.create(
            recipient=u,
            notification_type=Notification.TYPE_RATE_LIMIT_WARNING,
            title=title,
            message=message,
            campaign=campaign,
        )

        # Emit real-time notification if Channels is available
        if emit_notification_to_user:
            try:
                emit_notification_to_user(
                    u.id,
                    {
                        "notification_id": notification.id,
                        "notification_type": Notification.TYPE_RATE_LIMIT_WARNING,
                        "title": title,
                        "message": message,
                        "timestamp": timezone.now().isoformat(),
                    },
                )
            except Exception:
                pass


def create_campaign_error_notification(campaign, error_message, deal=None, user=None):
    """
    Create a notification for campaign errors.

    Args:
        campaign: The Campaign instance
        error_message: Description of the error
        deal: Optional related Deal
        user: Optional specific user to notify
    """
    Notification = get_model("notifications", "Notification")

    try:
        from .sse import emit_notification_to_user, emit_campaign_error
    except ImportError:
        emit_notification_to_user = None
        emit_campaign_error = None

    title = f"Campaign error in '{campaign.name}'"
    message = f"Error in '{campaign.name}': {error_message}"

    recipients = [user] if user else campaign.users.all()

    if not recipients:
        return

    for u in recipients:
        notification = Notification.objects.create(
            recipient=u,
            notification_type=Notification.TYPE_CAMPAIGN_ERROR,
            title=title,
            message=message,
            campaign=campaign,
            deal=deal,
        )

        # Emit real-time notification if Channels is available
        if emit_notification_to_user:
            try:
                emit_notification_to_user(
                    u.id,
                    {
                        "notification_id": notification.id,
                        "notification_type": Notification.TYPE_CAMPAIGN_ERROR,
                        "title": title,
                        "message": message,
                        "timestamp": timezone.now().isoformat(),
                    },
                )
            except Exception:
                pass

    # Emit campaign error via WebSocket
    if emit_campaign_error:
        try:
            emit_campaign_error(campaign.id, error_message, deal.id if deal else None)
        except Exception:
            pass


@receiver(post_save, sender="chat.ChatMessage")
def create_new_message_notification(sender, instance, created, **kwargs):
    """Create notification when a new message is received (inbound)."""
    if not created:
        return

    # Check if this is an inbound message
    if not getattr(instance, "is_outgoing", True):
        return  # Only create notifications for inbound messages

    try:
        # Get related models
        Deal = get_model("crm", "Deal")
        Campaign = get_model("core", "Campaign")

        # Get the deal and campaign
        deal = instance.deal
        campaign = deal.campaign if hasattr(deal, "campaign") else None

        if not campaign:
            return

        # Get all users associated with the campaign (excluding the message sender)
        campaign_users = (
            campaign.users.exclude(id=instance.owner_id)
            if instance.owner
            else campaign.users.all()
        )

        if not campaign_users:
            return

        # Create notifications with real-time delivery
        for user in campaign_users:
            create_notification_with_realtime(
                recipient=user,
                notification_type=Notification.TYPE_NEW_MESSAGE,
                title=f"New message from {deal.lead.name or deal.lead.public_identifier}",
                message=f"You have a new message in '{campaign.name}': {instance.content[:100]}",
                campaign=campaign,
                deal=deal,
                data={
                    "message_id": instance.id,
                    "deal_id": deal.id,
                },
            )
    except Exception:
        # Log error but don't crash the signal
        import logging

        logging.exception("Error in create_new_message_notification")


@receiver(post_save, sender="linkedin.ActionLog")
def create_action_error_notification(sender, instance, created, **kwargs):
    """Create error notification when an ActionLog entry has an error."""
    if not created:
        return

    try:
        # Get error message from the action log
        error_message = None

        # Check for error_message attribute
        if hasattr(instance, "error_message") and instance.error_message:
            error_message = instance.error_message

        # Check for error in payload (for ActionLog entries stored in payload)
        elif hasattr(instance, "payload") and instance.payload:
            error_message = instance.payload.get("error")

        if not error_message:
            return

        # Get related models
        Deal = get_model("crm", "Deal")
        Campaign = get_model("core", "Campaign")

        # Get the deal and campaign
        deal = instance.deal if hasattr(instance, "deal") else None
        campaign = instance.campaign if hasattr(instance, "campaign") else None

        if not campaign:
            # Try to get campaign from deal
            if deal:
                campaign = deal.campaign if hasattr(deal, "campaign") else None

        if not campaign:
            return

        # Create error notification for all campaign users
        create_campaign_error_notification(campaign, error_message, deal=deal)
    except Exception:
        # Log error but don't crash the signal
        import logging

        logging.exception("Error in create_action_error_notification")
