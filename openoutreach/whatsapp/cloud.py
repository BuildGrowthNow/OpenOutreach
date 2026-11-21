"""Cloud Duo shared-IP helpers for WhatsApp (Phase 4).

A Cloud Duo seat already owns one cloud LinkedIn profile and its managed
proxy. A WhatsApp number belonging to the same client identity may share that
seat and proxy. This module resolves and validates that relationship; it never
provisions a second seat or a second proxy.
"""
from __future__ import annotations

from typing import Any

from openoutreach.config import settings
from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.organizations.access import can_access_channel_doc
from openoutreach.proxies.models import (
    STATUS_DISABLED,
    STATUS_RETIRED,
    Proxy,
)

_BLOCKED_MASSIVE_STATUSES = {
    "disabled",
    "budget_disabled",
    "retired",
    "error",
}


class WhatsAppCloudError(ValueError):
    """A Cloud Duo WhatsApp request is not valid for this workspace."""


class WhatsAppCloudProxyError(RuntimeError):
    """A cloud WhatsApp session cannot start without a healthy proxy."""


def whatsapp_cloud_enabled() -> bool:
    """Cloud Duo needs both the product gate and the server-WA runtime gate."""
    return bool(
        getattr(settings, "WHATSAPP_CLOUD_PROXY_ENABLED", False)
        and getattr(settings, "DAEMON_V2_WHATSAPP_ENABLED", False)
    )


def resolve_duo_share(
    user: Any,
    org_id: str,
    linkedin_profile_id: str,
) -> tuple[dict[str, Any], Proxy, str]:
    """Return the LinkedIn profile, shared proxy, and identity for a Duo.

    The caller must be allowed to see the LinkedIn profile (owner/admin or the
    assigned member). The proxy must still be assigned to that exact profile,
    belong to the same workspace, and not already serve another cloud WhatsApp
    number.
    """
    profiles = get_mongodb_collection("linkedin_profiles")
    whatsapp = get_mongodb_collection("whatsapp_profiles")
    if profiles is None or whatsapp is None:
        raise WhatsAppCloudError("WhatsApp cloud storage is unavailable")

    profile = profiles.find_one({"_id": linkedin_profile_id})
    if not profile:
        raise WhatsAppCloudError("LinkedIn profile not found in this workspace")
    if str(profile.get("org_id") or "") != str(org_id):
        raise WhatsAppCloudError("LinkedIn profile belongs to another workspace")
    if profile.get("execution_mode") != "cloud":
        raise WhatsAppCloudError("Cloud Duo requires a cloud LinkedIn profile")
    if profile.get("active") is False or profile.get("is_active") is False:
        raise WhatsAppCloudError("The cloud LinkedIn seat is paused; assign it first")
    if not can_access_channel_doc(user, profile):
        raise WhatsAppCloudError("LinkedIn profile is not assigned to you")

    proxy_id = str(profile.get("proxy_id") or "")
    if not proxy_id:
        raise WhatsAppCloudError("The LinkedIn profile has no managed proxy yet")
    proxy = Proxy.get(proxy_id)
    if proxy is None:
        raise WhatsAppCloudError("The LinkedIn profile's managed proxy was not found")
    if proxy.status in {STATUS_RETIRED, STATUS_DISABLED}:
        raise WhatsAppCloudError("The LinkedIn profile's proxy is not active")
    if proxy.massive_status in _BLOCKED_MASSIVE_STATUSES:
        raise WhatsAppCloudError("The LinkedIn profile's proxy is not active")
    if proxy.linkedin_profile_id != linkedin_profile_id:
        raise WhatsAppCloudError("The proxy is not assigned to that LinkedIn profile")
    if proxy.assigned_org_id and str(proxy.assigned_org_id) != str(org_id):
        raise WhatsAppCloudError("The proxy belongs to another workspace")

    identity = str(
        profile.get("identity_id") or profile.get("user_id") or linkedin_profile_id
    )
    if proxy.identity_id and str(proxy.identity_id) != identity:
        raise WhatsAppCloudError("The proxy identity does not match the LinkedIn profile")

    existing = whatsapp.find_one(
        {"proxy_id": proxy._id, "execution_mode": "cloud"},
        {"_id": 1},
    )
    if existing:
        raise WhatsAppCloudError(
            "This cloud seat already has a WhatsApp number; one WhatsApp per Duo seat"
        )

    return profile, proxy, identity


__all__ = [
    "WhatsAppCloudError",
    "WhatsAppCloudProxyError",
    "resolve_duo_share",
    "whatsapp_cloud_enabled",
]
