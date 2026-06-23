# Note model for CRM

from typing import TYPE_CHECKING
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser
    User = AbstractUser
else:
    User = get_user_model()


class Note(models.Model):
    """Represents a note on a deal."""
    
    # Type hints for Django's automatic fields
    id: models.AutoField  # type: ignore[assignment]
    deal_id: int  # type: ignore[assignment]
    
    class Meta:
        verbose_name = _("Note")
        verbose_name_plural = _("Notes")
    
    deal = models.ForeignKey(  # type: ignore[assignment]
        'Deal',
        on_delete=models.CASCADE,
        related_name='notes',
    )
    
    content = models.TextField()  # type: ignore[assignment]
    
    created_by = models.ForeignKey(  # type: ignore[assignment]
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notes',
    )
    
    created_at = models.DateTimeField(default=timezone.now)  # type: ignore[assignment]
    updated_at = models.DateTimeField(auto_now=True)  # type: ignore[assignment]
    
    def __str__(self) -> str:
        return f"Note #{self.pk} for Deal #{self.deal_id}"
