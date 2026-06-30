# CRM views

from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from .models import TrackedLink, LinkClick


def link_redirect(request, short_code):
    """Redirect through tracked link to original URL while recording click."""
    try:
        link = TrackedLink.objects.get(short_code=short_code, is_active=True)
    except TrackedLink.DoesNotExist:
        return HttpResponse("Link not found", status=404)

    # Record the click
    ip_address = request.META.get("REMOTE_ADDR")
    user_agent = request.META.get("HTTP_USER_AGENT", "")

    link.record_click(ip_address=ip_address, user_agent=user_agent)

    # Store detailed click info
    LinkClick.objects.create(
        link=link,
        ip_address=ip_address,
        user_agent=user_agent,
        referrer=request.META.get("HTTP_REFERER", ""),
    )

    return HttpResponseRedirect(link.original_url)
