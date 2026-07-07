# openoutreach/core/signals.py
"""Signal handlers for core models."""

import logging

from django.db.models.signals import pre_delete
from django.dispatch import receiver

from openoutreach.core.models import Campaign, Task

logger = logging.getLogger(__name__)


@receiver(pre_delete, sender=Campaign)
def cleanup_campaign_tasks(sender, instance, **kwargs):
    """Delete all tasks associated with a campaign when the campaign is deleted.

    Since Task.payload stores campaign_id as JSON (not a ForeignKey),
    Django's cascade delete won't work automatically.
    """
    campaign_id = instance.pk
    deleted_count, _ = Task.objects.filter(
        payload__campaign_id=campaign_id
    ).delete()

    if deleted_count > 0:
        logger.info(
            "Deleted %d tasks for campaign %d (%s)",
            deleted_count,
            campaign_id,
            instance.name,
        )
