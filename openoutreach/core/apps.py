# openoutreach/core/apps.py
from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "openoutreach.core"
    label = "core"  # Use 'core' as the app label
    default_auto_field = "django.db.models.BigAutoField"
