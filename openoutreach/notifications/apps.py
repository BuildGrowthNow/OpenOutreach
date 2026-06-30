from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "openoutreach.notifications"

    def ready(self):
        # Import signals when app is ready
        import openoutreach.notifications.signals  # noqa: F401
