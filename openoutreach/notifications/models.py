from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Notification(models.Model):
    """Notification model for real-time campaign updates."""

    TYPE_CAMPAIGN_STARTED = "campaign_started"
    TYPE_CAMPAIGN_PAUSED = "campaign_paused"
    TYPE_CAMPAIGN_COMPLETED = "campaign_completed"
    TYPE_RATE_LIMIT_WARNING = "rate_limit_warning"
    TYPE_NEW_MESSAGE = "new_message"
    TYPE_CAMPAIGN_ERROR = "campaign_error"
    TYPE_SYSTEM_ANNOUNCEMENT = "system_announcement"

    notification_type_choices = [
        (TYPE_CAMPAIGN_STARTED, "Campaign Started"),
        (TYPE_CAMPAIGN_PAUSED, "Campaign Paused"),
        (TYPE_CAMPAIGN_COMPLETED, "Campaign Completed"),
        (TYPE_RATE_LIMIT_WARNING, "Rate Limit Warning"),
        (TYPE_NEW_MESSAGE, "New Message"),
        (TYPE_CAMPAIGN_ERROR, "Campaign Error"),
        (TYPE_SYSTEM_ANNOUNCEMENT, "System Announcement"),
    ]

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
        help_text="User who receives the notification",
    )
    notification_type = models.CharField(
        max_length=50,
        choices=notification_type_choices,
        help_text="Type of notification",
    )
    title = models.CharField(max_length=255, help_text="Notification title")
    message = models.TextField(help_text="Notification message content")
    
    # Campaign is in the 'core' app
    campaign = models.ForeignKey(
        "core.Campaign",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Related campaign (if any)",
    )
    deal = models.ForeignKey(
        "crm.Deal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Related deal (if any)",
    )
    is_read = models.BooleanField(default=False, help_text="Whether notification has been read")
    read_at = models.DateTimeField(null=True, blank=True, help_text="When notification was read")
    data = models.JSONField(default=dict, blank=True, help_text="Additional JSON data for the notification")
    created_at = models.DateTimeField(default=timezone.now, help_text="When notification was created")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return f"{self.notification_type}: {self.title}"

    def mark_as_read(self):
        """Mark notification as read."""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])

    @classmethod
    def get_unread_count(cls, user):
        """Get unread notification count for a user."""
        return cls.objects.filter(recipient=user, is_read=False).count()

    @classmethod
    def create_notification(cls, recipient, notification_type, title, message, **kwargs):
        """Create a new notification."""
        return cls.objects.create(
            recipient=recipient,
            notification_type=notification_type,
            title=title,
            message=message,
            **kwargs
        )