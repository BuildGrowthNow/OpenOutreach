# openoutreach/urls.py
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include, URLPattern, URLResolver
from typing import Union

urlpatterns: list[Union[URLResolver, URLPattern]] = [
    path("admin/", admin.site.urls),
    # API endpoints
    path("api/", include("openoutreach.api.urls")),
    # CRM link redirect (must be before api to avoid prefix)
    path("l/", include("openoutreach.crm.urls")),
    # Notifications URLS (for real-time updates via SSE)
    path("api/", include("openoutreach.notifications.urls")),
]

# Use list.extend for type compatibility
urlpatterns.extend(static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT))
