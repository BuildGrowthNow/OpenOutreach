# Message model for CRM

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Message(models.Model):
    """Represents a message in the CRM system."""
    
    class Meta:
        verbose_name = _("Message")
        verbose_name_plural = _("Messages")
    
    deal: models.ForeignKey = models.ForeignKey(  # type: ignore[var-annotated,assignment]
        'Deal',
        on_delete=models.CASCADE,
        related_name='crm_messages',
    )
    
    content: models.TextField = models.TextField()  # type: ignore[var-annotated]
    is_outgoing: models.BooleanField = models.BooleanField(default=True)  # type: ignore[var-annotated]
    
    created_at: models.DateTimeField = models.DateTimeField(default=timezone.now)  # type: ignore[var-annotated]
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)  # type: ignore[var-annotated]
    
    def __str__(self) -> str:
        deal_id: int = getattr(self, 'deal_id', 0)  # type: ignore[var-annotated]
        return f"Message #{self.pk} for Deal #{deal_id}"
    
    @property
    def sender(self) -> str:
        """Get the sender of the message."""
        if self.is_outgoing:
            return "User"
        return "Lead"
