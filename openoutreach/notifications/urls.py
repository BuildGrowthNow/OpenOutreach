from django.urls import path, re_path
from rest_framework.urlpatterns import format_suffix_patterns

from .views import (
    NotificationListView,
    NotificationMarkAllAsReadView,
    NotificationSummaryView,
    NotificationDetailView,
)
from . import sse

# Notification URL Patterns
urlpatterns = [
    # Notification list and management
    path("notifications/", NotificationListView.as_view(), name="notification-list"),
    path(
        "notifications/read-all/",
        NotificationMarkAllAsReadView.as_view(),
        name="notification-read-all",
    ),
    path(
        "notifications/summary/",
        NotificationSummaryView.as_view(),
        name="notification-summary",
    ),
    path(
        "notifications/<int:pk>/",
        NotificationDetailView.as_view(),
        name="notification-detail",
    ),
    path(
        "notifications/<int:pk>/read/",
        NotificationDetailView.as_view(),
        name="notification-read",
    ),
    # SSE endpoint for real-time notifications
    path("notifications/sse/", sse.sse_notification_stream, name="notification-sse"),
]

# Fallback patterns for both trailing-slash and no-trailing-slash versions
urlpatterns += [
    re_path(
        r"^notifications$",
        NotificationListView.as_view(),
        name="notification-list-no-slash",
    ),
    re_path(
        r"^notifications/read-all$",
        NotificationMarkAllAsReadView.as_view(),
        name="notification-read-all-no-slash",
    ),
    re_path(
        r"^notifications/summary$",
        NotificationSummaryView.as_view(),
        name="notification-summary-no-slash",
    ),
    re_path(
        r"^notifications/(?P<pk>[0-9]+)$",
        NotificationDetailView.as_view(),
        name="notification-detail-no-slash",
    ),
    re_path(
        r"^notifications/(?P<pk>[0-9]+)/read$",
        NotificationDetailView.as_view(),
        name="notification-read-no-slash",
    ),
    re_path(
        r"^notifications/sse$",
        sse.sse_notification_stream,
        name="notification-sse-no-slash",
    ),
]

urlpatterns = format_suffix_patterns(urlpatterns)
