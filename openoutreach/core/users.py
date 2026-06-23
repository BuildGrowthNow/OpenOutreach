# openoutreach/core/users.py
"""Custom User model with password reset fields."""

from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from datetime import timedelta


class CustomUser(AbstractUser):
    """
    Custom user model extending Django's AbstractUser.
    
    Adds password reset fields for the password reset functionality.
    """
    id: models.AutoField  # type: ignore[assignment]
    email: str  # type: ignore[assignment]
    username: str  # type: ignore[assignment]
    first_name: str  # type: ignore[assignment]
    last_name: str  # type: ignore[assignment]
    is_staff: bool  # type: ignore[assignment]
    is_active: bool  # type: ignore[assignment]
    is_superuser: bool  # type: ignore[assignment]
    last_login: timezone.datetime  # type: ignore[assignment]
    date_joined: timezone.datetime  # type: ignore[assignment]

    # Password reset fields
    password_reset_token = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        default='',
        help_text='Token for password reset validation',
    )
    password_reset_expires = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Expiry time for the password reset token',
    )

    class Meta:  # type: ignore[misc]
        db_table = 'auth_user'

    def __str__(self) -> str:
        return self.username

    def is_password_reset_expired(self) -> bool:
        """Check if the password reset token has expired."""
        if self.password_reset_expires is None:
            return True
        return timezone.now() > self.password_reset_expires

    def set_password_reset_token(self, token: str, hours: int = 24) -> None:
        """Set a password reset token with expiry."""
        self.password_reset_token = token
        self.password_reset_expires = timezone.now() + timedelta(hours=hours)
        self.save(update_fields=['password_reset_token', 'password_reset_expires'])

    def clear_password_reset_token(self) -> None:
        """Clear the password reset token."""
        self.password_reset_token = ''
        self.password_reset_expires = None
        self.save(update_fields=['password_reset_token', 'password_reset_expires'])