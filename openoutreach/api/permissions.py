# API Permissions

from rest_framework import permissions
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """

    def has_permission(self, request, view):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True
        # Write permissions require authentication
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True
        # Write permissions are only allowed to the owner of the object
        return bool(getattr(obj, "user", None) == request.user)


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow admins to edit objects.
    """

    def has_permission(self, request, view):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True
        # Write permissions are only allowed to admin users
        return bool(request.user and getattr(request.user, "is_staff", False))


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Custom permission to only allow owners or admins to access objects.
    """

    def has_permission(self, request, view):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True
        # Write permissions require authentication
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Allow if user is admin
        if request.user and getattr(request.user, "is_staff", False):
            return True
        # Allow if user is owner
        if hasattr(obj, "user"):
            return obj.user == request.user
        # For objects without user field, check if created_by exists
        if hasattr(obj, "created_by"):
            return obj.created_by == request.user
        return False


class LoginThrottle(AnonRateThrottle):
    """
    Rate limit for login attempts - prevents brute force attacks.
    """

    rate = "5/day"
    scope = "login"


class PasswordResetThrottle(AnonRateThrottle):
    """
    Rate limit for password reset requests.
    """

    rate = "3/day"
    scope = "password_reset"


class RegisterThrottle(AnonRateThrottle):
    """
    Rate limit for registration attempts.
    """

    rate = "1/day"
    scope = "register"


class ApiKeyRateThrottle(UserRateThrottle):
    """
    Rate limit for API key usage.
    """

    rate = "1000/day"
    scope = "api_key"


class AuditLoggingMixin:
    """
    Mixin to add audit logging for authentication events.
    """

    def log_auth_event(self, event_type: str, user=None, details: dict | None = None):
        """
        Log authentication events for audit trail.

        Args:
            event_type: Type of event (login, logout, token_refresh, etc.)
            user: Django user object (optional)
            details: Additional event details (optional)
        """
        import logging
        from django.utils import timezone

        logger = logging.getLogger("audit")

        request = getattr(self, "request", None)
        log_data = {
            "event_type": event_type,
            "timestamp": timezone.now().isoformat(),
            "user_id": user.id if user else None,
            "user_email": user.email if user and hasattr(user, "email") else None,
            "ip_address": request.META.get("REMOTE_ADDR") if request else None,
            "details": details or {},
        }

        logger.info(f"AUTH_EVENT: {log_data}")
