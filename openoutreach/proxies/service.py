"""Managed proxy inventory operations: import, assign, test, retire, usage.

Passwords are decrypted only to make an outbound proxy connection. They are
never logged and never serialized to an API response or CSV export.
"""
from __future__ import annotations

import asyncio
import csv
import io
import ipaddress
import logging
import re
import socket
import time
from datetime import datetime
from typing import Any, Optional
from urllib.parse import quote, urlparse, urlunparse

import httpx
from pymongo.collection import Collection

from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.mongodb.crypto import safe_decrypt, safe_encrypt
from openoutreach.proxies.models import (
    _ASSIGNMENTS_COLLECTION,
    _HEALTH_COLLECTION,
    _USAGE_COLLECTION,
    KIND_RESIDENTIAL,
    PROVIDER_MANUAL,
    STATUS_ASSIGNED,
    STATUS_AVAILABLE,
    STATUS_DISABLED,
    STATUS_ERROR,
    STATUS_RETIRED,
    Proxy,
    ProxyError,
    ProxyReuseError,
    ProxyUnavailableError,
    create_proxy,
)
from openoutreach.proxies.parser import (
    masked_preview_entry,
    parse_bulk_proxies,
)
from openoutreach.proxies.region import normalize_region

logger = logging.getLogger(__name__)

_PROFILES = "linkedin_profiles"
_PROXIES = "proxies"
_ACTIVE_ASSIGNMENT_FILTER = {"unassigned_at": None}


def validate_proxy_host(host: str) -> None:
    """Reject localhost, private, link-local, and reserved proxy endpoints.

    The admin test endpoint and the browser both make outbound requests through
    this host, so an internal address would be an SSRF pivot.
    """
    value = (host or "").strip()
    if not value:
        raise ProxyError("Proxy host is required")
    try:
        addresses = {
            info[4][0]
            for info in socket.getaddrinfo(value, None)
        }
    except socket.gaierror:
        raise ProxyError("Proxy host could not be resolved")

    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            raise ProxyError("Proxy host is invalid")
        if not ip.is_global:
            raise ProxyError("Proxy host must be a public address")


def normalize_proxy_server(proxy_server: str) -> str:
    """Validate a proxy URL and default to HTTP when no scheme is supplied."""
    value = (proxy_server or "").strip()
    if not value:
        raise ProxyError("Proxy server URL is required")
    if "://" not in value:
        value = f"http://{value}"
    parsed = urlparse(value)
    if parsed.scheme.lower() not in {"http", "https", "socks5", "socks5h"} or not parsed.hostname:
        raise ProxyError("Invalid proxy URL")
    validate_proxy_host(parsed.hostname)
    return value


def build_proxy_url(
    proxy_server: str,
    proxy_username: Optional[str],
    proxy_password: Optional[str],
) -> str:
    """Inject separately supplied proxy credentials into the proxy URL."""
    if not (proxy_username and proxy_password):
        return proxy_server
    parsed = urlparse(proxy_server)
    host = parsed.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    netloc = f"{quote(proxy_username, safe='')}:{quote(proxy_password, safe='')}@{host}"
    if parsed.port:
        netloc += f":{parsed.port}"
    return urlunparse((
        parsed.scheme,
        netloc,
        parsed.path,
        parsed.params,
        parsed.query,
        parsed.fragment,
    ))


def _massive_lifecycle(
    doc: dict[str, Any], action: str, *, reason: Optional[str] = None
) -> None:
    """Best-effort provider lifecycle sync for admin inventory actions."""
    if not doc.get("massive_account_id"):
        return
    try:
        from openoutreach.proxies.provisioning import (
            disable_massive_proxy,
            enable_massive_proxy,
            retire_massive_proxy,
        )

        proxy = Proxy.from_dict(doc)
        if action == "disable":
            disable_massive_proxy(proxy, reason=reason or "admin_disable")
        elif action == "enable":
            enable_massive_proxy(proxy, reason=reason or "admin_enable")
        elif action == "retire":
            retire_massive_proxy(proxy)
    except Exception as exc:  # pragma: no cover - provider must not block admin
        logger.warning(
            "massive_lifecycle_failed proxy_id=%s action=%s exception_type=%s",
            doc.get("_id"),
            action,
            type(exc).__name__,
        )


def _collection(name: str) -> Optional[Collection]:
    return get_mongodb_collection(name)


def _now() -> datetime:
    return Proxy.now()


def _build_query(
    *,
    status: Optional[str] = None,
    country: Optional[str] = None,
    provider: Optional[str] = None,
    kind: Optional[str] = None,
    assignment: Optional[str] = None,
    identity_id: Optional[str] = None,
    org_id: Optional[str] = None,
    search: Optional[str] = None,
) -> dict[str, Any]:
    conditions: list[dict[str, Any]] = []
    if status:
        conditions.append({"status": status})
    if country:
        conditions.append({"country": country.upper()})
    if provider:
        conditions.append({"provider": provider})
    if kind:
        conditions.append({"kind": kind})
    if identity_id:
        conditions.append({"identity_id": identity_id})
    if org_id:
        conditions.append({
            "$or": [
                {"assigned_org_id": org_id},
                {"last_assigned_org_id": org_id},
            ]
        })
    if assignment == "assigned":
        conditions.append({"status": STATUS_ASSIGNED})
        conditions.append({"linkedin_profile_id": {"$ne": None}})
    elif assignment == "unassigned":
        conditions.append({
            "$or": [
                {"status": {"$ne": STATUS_ASSIGNED}},
                {"linkedin_profile_id": None},
            ]
        })
    if search:
        pattern = re.escape(search.strip())
        conditions.append({
            "$or": [
                {"label": {"$regex": pattern, "$options": "i"}},
                {"host": {"$regex": pattern, "$options": "i"}},
                {"linkedin_profile_id": {"$regex": pattern, "$options": "i"}},
                {"last_assigned_profile_id": {"$regex": pattern, "$options": "i"}},
            ]
        })
    if not conditions:
        return {}
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


def list_proxies(
    *,
    status: Optional[str] = None,
    country: Optional[str] = None,
    provider: Optional[str] = None,
    kind: Optional[str] = None,
    assignment: Optional[str] = None,
    identity_id: Optional[str] = None,
    org_id: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[Proxy], int]:
    collection = _collection(_PROXIES)
    if collection is None:
        raise ProxyError("Proxy inventory is unavailable")
    query = _build_query(
        status=status,
        country=country,
        provider=provider,
        kind=kind,
        assignment=assignment,
        identity_id=identity_id,
        org_id=org_id,
        search=search,
    )
    total = collection.count_documents(query)
    docs = collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
    return [Proxy.from_dict(doc) for doc in docs], total


def get_proxy_stats() -> dict[str, Any]:
    """Return inventory counts for the admin dashboard."""
    collection = _collection(_PROXIES)
    if collection is None:
        raise ProxyError("Proxy inventory is unavailable")
    status_counts = {
        value: collection.count_documents({"status": value})
        for value in (
            STATUS_AVAILABLE,
            STATUS_ASSIGNED,
            STATUS_DISABLED,
            STATUS_ERROR,
            STATUS_RETIRED,
        )
    }
    provider_counts = {
        str(row["_id"]): int(row["count"])
        for row in collection.aggregate([
            {"$group": {"_id": "$provider", "count": {"$sum": 1}}},
        ])
    }
    country_counts = {
        str(row["_id"]): int(row["count"])
        for row in collection.aggregate([
            {"$match": {"country": {"$nin": [None, ""]}}},
            {"$group": {"_id": "$country", "count": {"$sum": 1}}},
        ])
    }
    profiles = _collection(_PROFILES)
    cloud_profiles_total = 0
    cloud_profiles_without_proxy = 0
    if profiles is not None:
        cloud_profiles_total = profiles.count_documents({"execution_mode": "cloud"})
        cloud_profiles_without_proxy = profiles.count_documents({
            "execution_mode": "cloud",
            "proxy_id": None,
            "proxy_server": None,
        })
    return {
        "total": collection.count_documents({}),
        "status": status_counts,
        "provider": provider_counts,
        "country": country_counts,
        "cloud_profiles_total": cloud_profiles_total,
        "cloud_profiles_without_proxy": cloud_profiles_without_proxy,
    }


def _duplicate_query(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "host": entry["host"],
        "port": entry["port"],
        "username": entry["username"],
    }


def preview_proxies(
    text: str,
    *,
    provider: str = PROVIDER_MANUAL,
    kind: str = KIND_RESIDENTIAL,
    default_country: Optional[str] = None,
) -> dict[str, Any]:
    """Parse and validate an import without persisting anything.

    The preview never contains passwords or raw usernames.
    """
    entries, errors = parse_bulk_proxies(text, default_country=default_country)
    collection = _collection(_PROXIES)
    valid: list[dict[str, Any]] = []
    duplicates = 0
    parse_errors = len(errors)
    for entry in entries:
        duplicate = False
        if collection is not None:
            duplicate = collection.find_one(
                _duplicate_query(entry),
                {"_id": 1},
            ) is not None
        if duplicate:
            duplicates += 1
            errors.append({
                "line": entry.get("line", 0),
                "error": "Proxy already imported",
            })
            continue
        valid.append(masked_preview_entry(
            entry,
            default_provider=provider,
            default_kind=kind,
        ))
    errors.sort(key=lambda item: (item.get("line") or 0, item.get("error") or ""))
    return {
        "entries": len(entries) + parse_errors,
        "valid": len(valid),
        "duplicates": duplicates,
        "failed": len(errors) - duplicates,
        "errors": errors,
        "preview": valid,
    }


def import_proxies(
    text: str,
    *,
    provider: str = PROVIDER_MANUAL,
    kind: str = KIND_RESIDENTIAL,
    default_country: Optional[str] = None,
    created_by: Optional[str] = None,
) -> dict[str, Any]:
    """Parse and persist pasted proxies, skipping duplicates.

    Passwords are encrypted before storage and never returned.
    """
    entries, errors = parse_bulk_proxies(text, default_country=default_country)
    collection = _collection(_PROXIES)
    if collection is None:
        raise ProxyError("Proxy inventory is unavailable")

    created: list[Proxy] = []
    skipped = 0
    for entry in entries:
        if collection.find_one(_duplicate_query(entry), {"_id": 1}):
            skipped += 1
            errors.append({
                "line": entry.get("line", 0),
                "error": "Proxy already imported",
            })
            continue
        try:
            proxy = create_proxy(
                host=entry["host"],
                port=entry["port"],
                username=entry["username"],
                password=entry["password"],
                country=entry["country"],
                subdivision=entry.get("subdivision"),
                city=entry.get("city"),
                provider=entry.get("provider") or provider,
                kind=entry.get("kind") or kind,
                protocol=entry["protocol"],
                label=entry.get("label") or "",
                region_mode=entry.get("region_mode") or "targeted",
                device_type=entry.get("device_type") or "common",
                created_by=created_by,
            )
        except (ProxyError, RuntimeError) as exc:
            errors.append({"line": entry.get("line", 0), "error": str(exc)})
            continue
        created.append(proxy)

    errors.sort(key=lambda item: (item.get("line") or 0, item.get("error") or ""))
    return {
        "created": len(created),
        "skipped": skipped,
        "failed": len(errors) - skipped,
        "errors": errors,
        "proxies": [proxy.public_dict() for proxy in created],
    }


def _csv_safe(value: Any) -> str:
    text = "" if value is None else str(value)
    if text[:1] in {"=", "+", "-", "@"}:
        return f"'{text}"
    return text


def export_proxies_csv(
    *,
    status: Optional[str] = None,
    country: Optional[str] = None,
    provider: Optional[str] = None,
    kind: Optional[str] = None,
    assignment: Optional[str] = None,
    identity_id: Optional[str] = None,
    org_id: Optional[str] = None,
    search: Optional[str] = None,
) -> str:
    """Return a masked CSV export. Passwords and secrets never appear."""
    proxies, _ = list_proxies(
        status=status,
        country=country,
        provider=provider,
        kind=kind,
        assignment=assignment,
        identity_id=identity_id,
        org_id=org_id,
        search=search,
        skip=0,
        limit=10_000,
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "label",
        "provider",
        "protocol",
        "host",
        "port",
        "username",
        "has_username",
        "country",
        "subdivision",
        "city",
        "kind",
        "region_mode",
        "device_type",
        "status",
        "identity_id",
        "assigned_profile_id",
        "assigned_user_id",
        "assigned_org_id",
        "last_tested_at",
        "last_test_ip",
        "last_test_country",
        "last_test_latency_ms",
        "country_mismatch",
        "last_error",
        "created_at",
    ])
    for proxy in proxies:
        writer.writerow([
            _csv_safe(proxy.label),
            _csv_safe(proxy.provider),
            _csv_safe(proxy.protocol),
            _csv_safe(proxy.host),
            proxy.port,
            "***" if proxy.username else "",
            "true" if proxy.username else "false",
            _csv_safe(proxy.country),
            _csv_safe(proxy.subdivision),
            _csv_safe(proxy.city),
            _csv_safe(proxy.kind),
            _csv_safe(proxy.region_mode),
            _csv_safe(proxy.device_type),
            _csv_safe(proxy.status),
            _csv_safe(proxy.identity_id),
            _csv_safe(proxy.linkedin_profile_id),
            _csv_safe(proxy.assigned_user_id),
            _csv_safe(proxy.assigned_org_id),
            proxy.last_tested_at.isoformat() if proxy.last_tested_at else "",
            _csv_safe(proxy.last_test_ip),
            _csv_safe(proxy.last_test_country),
            proxy.last_test_latency_ms if proxy.last_test_latency_ms is not None else "",
            "" if proxy.country_mismatch is None else str(proxy.country_mismatch).lower(),
            _csv_safe((proxy.last_error or "")[:300]),
            proxy.created_at.isoformat() if proxy.created_at else "",
        ])
    return buffer.getvalue()


def find_available_proxy(
    country: str,
    subdivision: Optional[str] = None,
    city: Optional[str] = None,
) -> Optional[Proxy]:
    """Find an unused proxy, preferring the narrowest matching region.

    A proxy that has ever been assigned is excluded: a used proxy may never be
    recycled to a different LinkedIn account.
    """
    collection = _collection(_PROXIES)
    if collection is None:
        return None

    base: dict[str, Any] = {
        "status": STATUS_AVAILABLE,
        "country": country.upper(),
        "linkedin_profile_id": None,
        "ever_assigned": {"$ne": True},
        # A proxy that has ever belonged to a workspace must not be handed to
        # a different organization, even if its local assignment was cleared.
        "assigned_org_id": None,
        "last_assigned_org_id": None,
    }
    queries: list[dict[str, Any]] = []
    if city and subdivision:
        queries.append({**base, "subdivision": subdivision.upper(), "city": city})
    if subdivision:
        queries.append({**base, "subdivision": subdivision.upper()})
    queries.append(base)

    for query in queries:
        doc = collection.find_one(query, sort=[("created_at", 1)])
        if doc:
            return Proxy.from_dict(doc)
    return None


def _record_assignment(
    *,
    proxy_id: str,
    profile_id: str,
    channel: str,
    identity_id: Optional[str],
    user_id: Optional[str],
    org_id: Optional[str],
    assigned_by: Optional[str],
) -> None:
    collection = _collection(_ASSIGNMENTS_COLLECTION)
    if collection is None:
        return
    try:
        collection.insert_one({
            "proxy_id": proxy_id,
            "identity_id": identity_id,
            "profile_id": profile_id,
            "channel": channel,
            "seat_id": None,
            "user_id": user_id,
            "org_id": org_id,
            "assigned_by": assigned_by,
            "assigned_at": _now(),
            "unassigned_at": None,
            "reason": None,
        })
    except Exception as exc:  # pragma: no cover - audit must not break assignment
        logger.warning(
            "proxy_assignment_audit_failed proxy_id=%s exception_type=%s",
            proxy_id,
            type(exc).__name__,
        )


def record_proxy_assignment(
    *,
    proxy_id: str,
    profile_id: str,
    channel: str,
    identity_id: Optional[str],
    user_id: Optional[str],
    org_id: Optional[str],
    assigned_by: Optional[str],
) -> None:
    """Public audit hook for channel assignments that share an existing proxy."""
    _record_assignment(
        proxy_id=proxy_id,
        profile_id=profile_id,
        channel=channel,
        identity_id=identity_id,
        user_id=user_id,
        org_id=org_id,
        assigned_by=assigned_by,
    )


def _close_assignment(
    *,
    proxy_id: str,
    profile_id: Optional[str],
    reason: Optional[str],
) -> None:
    collection = _collection(_ASSIGNMENTS_COLLECTION)
    if collection is None:
        return
    query: dict[str, Any] = {"proxy_id": proxy_id, **_ACTIVE_ASSIGNMENT_FILTER}
    if profile_id:
        query["profile_id"] = profile_id
    try:
        collection.update_many(
            query,
            {"$set": {"unassigned_at": _now(), "reason": reason}},
        )
    except Exception as exc:  # pragma: no cover
        logger.warning(
            "proxy_assignment_close_failed proxy_id=%s exception_type=%s",
            proxy_id,
            type(exc).__name__,
        )


def assign_proxy_to_profile(
    proxy_id: str,
    profile_id: str,
    user_id: str,
    *,
    assigned_by: Optional[str] = None,
    channel: str = "linkedin",
) -> Proxy:
    """Atomically assign a proxy to a cloud profile.

    Rules enforced here:
    - one active proxy per profile;
    - at most one LinkedIn account per proxy;
    - no cross-tenant or cross-identity assignment;
    - a used proxy may only return to the same LinkedIn profile.
    """
    collection = _collection(_PROXIES)
    profiles = _collection(_PROFILES)
    if collection is None or profiles is None:
        raise ProxyError("Proxy inventory is unavailable")

    existing = collection.find_one({"_id": proxy_id})
    if not existing:
        raise ProxyUnavailableError("Proxy not found")
    proxy = Proxy.from_dict(existing)
    if proxy.status == STATUS_RETIRED:
        raise ProxyUnavailableError("Retired proxies cannot be assigned")
    if proxy.linkedin_profile_id not in (None, profile_id):
        raise ProxyReuseError(
            "This proxy was already used by another LinkedIn account and cannot be recycled"
        )
    if (
        proxy.ever_assigned
        and not proxy.last_assigned_profile_id
        and proxy.linkedin_profile_id != profile_id
    ):
        raise ProxyReuseError(
            "This proxy was already used and cannot be assigned to a different LinkedIn account"
        )
    if proxy.is_used and proxy.last_assigned_profile_id not in (None, profile_id):
        raise ProxyReuseError(
            "This proxy was already used by another LinkedIn account and cannot be recycled"
        )
    if proxy.last_assigned_user_id not in (None, user_id):
        raise ProxyReuseError(
            "This proxy belongs to another workspace and cannot be reassigned"
        )
    validate_proxy_host(proxy.host)

    profile_doc = profiles.find_one(
        {"_id": profile_id},
        {
            "user_id": 1,
            "proxy_id": 1,
            "proxy_server": 1,
            "identity_id": 1,
            "org_id": 1,
        },
    )
    if not profile_doc:
        raise ProxyUnavailableError("LinkedIn profile not found")
    if profile_doc.get("user_id") != user_id:
        raise ProxyError("LinkedIn profile belongs to another workspace")

    current_proxy_id = profile_doc.get("proxy_id")
    if current_proxy_id and current_proxy_id != proxy_id:
        raise ProxyError("This profile already has a different proxy")
    if profile_doc.get("proxy_server") and not current_proxy_id:
        raise ProxyError("This profile already has a BYO proxy")

    profile_identity = profile_doc.get("identity_id") or user_id
    profile_org = profile_doc.get("org_id")
    org_value = profile_org or proxy.assigned_org_id or proxy.last_assigned_org_id
    if proxy.identity_id and proxy.identity_id != profile_identity:
        raise ProxyError("Proxy identity does not match the profile identity")
    if proxy.assigned_org_id and profile_org and proxy.assigned_org_id != profile_org:
        raise ProxyError("Proxy belongs to another organization")

    previous_identity = proxy.identity_id
    was_used = proxy.is_used
    claimed = collection.find_one_and_update(
        {
            "_id": proxy_id,
            "$or": [
                {
                    "status": STATUS_AVAILABLE,
                    "linkedin_profile_id": None,
                    "ever_assigned": {"$ne": True},
                },
                {
                    "status": {"$in": [STATUS_AVAILABLE, STATUS_DISABLED, STATUS_ERROR]},
                    "linkedin_profile_id": None,
                    "last_assigned_profile_id": profile_id,
                },
                {
                    "status": STATUS_ASSIGNED,
                    "linkedin_profile_id": profile_id,
                },
            ],
        },
        {
            "$set": {
                "status": STATUS_ASSIGNED,
                "linkedin_profile_id": profile_id,
                "identity_id": proxy.identity_id or profile_identity,
                "assigned_user_id": user_id,
                "assigned_org_id": org_value,
                "assigned_at": _now(),
                "assigned_by": assigned_by,
                "ever_assigned": True,
                "last_assigned_profile_id": profile_id,
                "last_assigned_user_id": user_id,
                "last_assigned_org_id": org_value,
                "disabled_at": None,
                "updated_at": _now(),
            }
        },
        return_document=True,
    )
    if not claimed:
        raise ProxyUnavailableError("Proxy is not available")

    proxy = Proxy.from_dict(claimed)
    # Persist the proxy's real region, not the requested fallback target.
    country, subdivision, city = proxy.country, proxy.subdivision, proxy.city
    updated = profiles.update_one(
        {
            "_id": profile_id,
            "user_id": user_id,
            # A concurrent assignment must not leave this proxy orphaned.
            "proxy_id": {"$in": [None, proxy_id]},
        },
        {
            "$set": {
                "proxy_server": proxy.proxy_server,
                "proxy_username": proxy.username,
                "proxy_password": None,
                "proxy_password_encrypted": proxy.password_encrypted,
                "proxy_id": proxy._id,
                "proxy_mode": "managed",
                "proxy_region_country": country,
                "proxy_region_subdivision": subdivision,
                "proxy_region_city": city,
                "identity_id": profile_identity,
                "active": True,
                "is_active": True,
                "daemon_status": "proxy_ready",
                "updated_at": _now(),
            }
        },
    )
    if getattr(updated, "modified_count", 0) == 0:
        if not was_used:
            collection.update_one(
                {"_id": proxy_id, "linkedin_profile_id": profile_id},
                {
                    "$set": {
                        "status": STATUS_AVAILABLE,
                        "linkedin_profile_id": None,
                        "identity_id": previous_identity,
                        "assigned_user_id": None,
                        "assigned_org_id": None,
                        "assigned_at": None,
                        "assigned_by": None,
                        "ever_assigned": False,
                        "last_assigned_profile_id": None,
                        "last_assigned_user_id": None,
                        "last_assigned_org_id": None,
                        "updated_at": _now(),
                    }
                },
            )
        else:
            collection.update_one(
                {"_id": proxy_id, "linkedin_profile_id": profile_id},
                {
                    "$set": {
                        "status": STATUS_DISABLED,
                        "linkedin_profile_id": None,
                        "assigned_user_id": None,
                        "assigned_org_id": None,
                        "assigned_at": None,
                        "assigned_by": None,
                        "disabled_at": _now(),
                        "updated_at": _now(),
                    }
                },
            )
        raise ProxyUnavailableError(
            "Profile was assigned a different proxy concurrently"
        )

    _record_assignment(
        proxy_id=proxy._id,
        profile_id=profile_id,
        channel=channel,
        identity_id=profile_identity,
        user_id=user_id,
        org_id=org_value,
        assigned_by=assigned_by,
    )
    logger.info("Assigned proxy %s to profile %s", proxy._id, profile_id)
    return proxy


def _clear_cloud_whatsapp_proxy_links(proxy_id: str) -> None:
    """Detach a shared proxy from its Cloud Duo WhatsApp profile."""
    collection = _collection("whatsapp_profiles")
    if collection is None:
        return
    try:
        collection.update_many(
            {"proxy_id": proxy_id, "execution_mode": "cloud"},
            {
                "$set": {
                    "proxy_id": None,
                    "proxy_mode": "none",
                    "proxy_region_country": None,
                    "proxy_region_subdivision": None,
                    "proxy_region_city": None,
                }
            },
        )
    except Exception as exc:  # pragma: no cover - lifecycle must not block
        logger.warning(
            "whatsapp_proxy_unlink_failed proxy_id=%s exception_type=%s",
            proxy_id,
            type(exc).__name__,
        )


def unassign_proxy(
    proxy_id: str,
    *,
    reason: Optional[str] = None,
    actor: Optional[str] = None,
) -> Proxy:
    """Unassign a proxy, pause the profile, and keep the proxy reserved.

    The proxy is disabled rather than returned to the available pool because a
    used proxy may never be assigned to a different LinkedIn account.
    """
    collection = _collection(_PROXIES)
    profiles = _collection(_PROFILES)
    if collection is None:
        raise ProxyError("Proxy inventory is unavailable")
    existing = collection.find_one({"_id": proxy_id})
    if not existing:
        raise ProxyUnavailableError("Proxy not found")
    profile_id = existing.get("linkedin_profile_id")
    if not profile_id:
        raise ProxyError("Proxy is not assigned to a profile")

    _massive_lifecycle(existing, "disable", reason=reason or "admin_unassign")

    claimed = collection.find_one_and_update(
        {"_id": proxy_id, "linkedin_profile_id": profile_id},
        {
            "$set": {
                "status": STATUS_DISABLED,
                "linkedin_profile_id": None,
                "assigned_user_id": None,
                "assigned_org_id": None,
                "assigned_at": None,
                "ever_assigned": True,
                "last_assigned_profile_id": profile_id,
                "last_assigned_user_id": existing.get("assigned_user_id")
                or existing.get("last_assigned_user_id"),
                "last_assigned_org_id": existing.get("assigned_org_id")
                or existing.get("last_assigned_org_id"),
                "disabled_at": _now(),
                "updated_at": _now(),
            }
        },
        return_document=True,
    )
    if not claimed:
        raise ProxyUnavailableError("Proxy assignment changed concurrently")

    if profiles is not None:
        profiles.update_one(
            {"_id": profile_id, "proxy_id": proxy_id},
            {
                "$set": {
                    "proxy_server": None,
                    "proxy_username": None,
                    "proxy_password": None,
                    "proxy_password_encrypted": None,
                    "proxy_id": None,
                    "proxy_mode": "none",
                    "active": False,
                    "is_active": False,
                    "daemon_status": "proxy_unassigned",
                    "updated_at": _now(),
                }
            },
        )
    _clear_cloud_whatsapp_proxy_links(proxy_id)
    _close_assignment(
        proxy_id=proxy_id,
        profile_id=None,
        reason=reason or f"unassigned_by_{actor or 'admin'}",
    )
    logger.info("Unassigned proxy %s from profile %s", proxy_id, profile_id)
    return Proxy.from_dict(claimed)


def disable_proxy(proxy_id: str) -> Proxy:
    """Disable an unassigned proxy. Assigned proxies must be unassigned first."""
    collection = _collection(_PROXIES)
    if collection is None:
        raise ProxyError("Proxy inventory is unavailable")
    doc = collection.find_one({"_id": proxy_id})
    if not doc:
        raise ProxyUnavailableError("Proxy not found")
    if doc.get("linkedin_profile_id"):
        raise ProxyError("Unassign the proxy before disabling it")
    if doc.get("status") == STATUS_RETIRED:
        raise ProxyError("Retired proxies cannot be disabled")
    _massive_lifecycle(doc, "disable", reason="admin_disable")
    collection.update_one(
        {"_id": proxy_id},
        {"$set": {"status": STATUS_DISABLED, "disabled_at": _now(), "updated_at": _now()}},
    )
    return Proxy.get(proxy_id)  # type: ignore[return-value]


def enable_proxy(proxy_id: str) -> Proxy:
    """Re-enable an unassigned proxy that is disabled or in error."""
    collection = _collection(_PROXIES)
    if collection is None:
        raise ProxyError("Proxy inventory is unavailable")
    doc = collection.find_one({"_id": proxy_id})
    if not doc:
        raise ProxyUnavailableError("Proxy not found")
    if doc.get("status") == STATUS_RETIRED:
        raise ProxyError("Retired proxies cannot be enabled")
    if doc.get("linkedin_profile_id"):
        raise ProxyError("Unassign the proxy before enabling it")
    _massive_lifecycle(doc, "enable", reason="admin_enable")
    collection.update_one(
        {"_id": proxy_id},
        {"$set": {"status": STATUS_AVAILABLE, "disabled_at": None, "updated_at": _now()}},
    )
    return Proxy.get(proxy_id)  # type: ignore[return-value]


def retire_proxy(proxy_id: str, *, reason: Optional[str] = None) -> Proxy:
    """Retire an unassigned proxy permanently. Retired records are kept."""
    collection = _collection(_PROXIES)
    if collection is None:
        raise ProxyError("Proxy inventory is unavailable")
    doc = collection.find_one({"_id": proxy_id})
    if not doc:
        raise ProxyUnavailableError("Proxy not found")
    if doc.get("linkedin_profile_id"):
        raise ProxyError("Unassign the proxy before retiring it")
    if doc.get("status") == STATUS_RETIRED:
        return Proxy.from_dict(doc)
    _massive_lifecycle(doc, "retire")
    _clear_cloud_whatsapp_proxy_links(proxy_id)
    collection.update_one(
        {"_id": proxy_id},
        {
            "$set": {
                "status": STATUS_RETIRED,
                "retired_at": _now(),
                "updated_at": _now(),
                "retire_reason": reason or "admin_retired",
            }
        },
    )
    _close_assignment(proxy_id=proxy_id, profile_id=None, reason=reason or "retired")
    return Proxy.get(proxy_id)  # type: ignore[return-value]


def rotate_proxy_password(proxy_id: str, password: str) -> Proxy:
    """Rotate a manual proxy password. Massive credentials rotate upstream."""
    collection = _collection(_PROXIES)
    if collection is None:
        raise ProxyError("Proxy inventory is unavailable")
    doc = collection.find_one({"_id": proxy_id})
    if not doc:
        raise ProxyUnavailableError("Proxy not found")
    if doc.get("provider") != PROVIDER_MANUAL:
        raise ProxyError(
            "Managed provider credentials rotate at the provider level"
        )
    encrypted = safe_encrypt(password)
    if not encrypted:
        raise ProxyError("Failed to encrypt proxy password")
    collection.update_one(
        {"_id": proxy_id},
        {
            "$set": {
                "password_encrypted": encrypted,
                "rotated_at": _now(),
                "updated_at": _now(),
            }
        },
    )
    # The assigned profile carries its own encrypted copy for browser launch.
    profiles = _collection(_PROFILES)
    assigned_profile_id = doc.get("linkedin_profile_id")
    if profiles is not None and assigned_profile_id:
        profiles.update_one(
            {"_id": assigned_profile_id, "proxy_id": proxy_id},
            {
                "$set": {
                    "proxy_password_encrypted": encrypted,
                    "updated_at": _now(),
                }
            },
        )
    return Proxy.get(proxy_id)  # type: ignore[return-value]


def _shared_cloud_whatsapp_proxy_ids(proxy_ids: list[str]) -> set[str]:
    """Return proxy IDs still used by a Cloud Duo WhatsApp profile."""
    collection = _collection("whatsapp_profiles")
    if collection is None or not proxy_ids:
        return set()
    try:
        return {
            str(doc["proxy_id"])
            for doc in collection.find(
                {"proxy_id": {"$in": proxy_ids}, "execution_mode": "cloud"},
                {"proxy_id": 1},
            )
        }
    except Exception:
        return set()


def retire_proxy_for_profile(profile_id: str) -> None:
    """Retire the proxy attached to a deleted profile; never recycle it."""
    collection = _collection(_PROXIES)
    if collection is None:
        return
    # Phase 2: disable the provider sub-account before clearing the local
    # profile link. Disabling is reversible for audit; the record is never
    # deleted or reused.
    try:
        from openoutreach.proxies.provisioning import retire_massive_for_profile

        retire_massive_for_profile(profile_id)
    except Exception as exc:  # pragma: no cover - deletion must still complete
        logger.warning(
            "massive_retire_for_profile_failed profile_id=%s exception_type=%s",
            profile_id,
            type(exc).__name__,
        )
    retire_query: dict[str, Any] = {
        "$or": [
            {"linkedin_profile_id": profile_id},
            {"last_assigned_profile_id": profile_id},
        ],
        "status": {"$ne": STATUS_RETIRED},
    }
    candidate_ids = [
        str(doc["_id"])
        for doc in collection.find(retire_query, {"_id": 1})
    ]
    shared_ids = _shared_cloud_whatsapp_proxy_ids(candidate_ids)
    if shared_ids:
        retire_query["_id"] = {"$nin": list(shared_ids)}
        for shared_id in shared_ids:
            _close_assignment(
                proxy_id=shared_id,
                profile_id=None,
                reason="linkedin_profile_deleted",
            )
    collection.update_many(
        retire_query,
        {
            "$set": {
                "status": STATUS_RETIRED,
                "linkedin_profile_id": None,
                "assigned_user_id": None,
                "assigned_org_id": None,
                "assigned_at": None,
                "ever_assigned": True,
                "last_assigned_profile_id": profile_id,
                "retired_at": _now(),
                "updated_at": _now(),
                "retire_reason": "profile_deleted",
            }
        },
    )
    assignments = _collection(_ASSIGNMENTS_COLLECTION)
    if assignments is not None:
        try:
            assignments.update_many(
                {"profile_id": profile_id, **_ACTIVE_ASSIGNMENT_FILTER},
                {"$set": {"unassigned_at": _now(), "reason": "profile_deleted"}},
            )
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "proxy_assignment_close_failed profile_id=%s exception_type=%s",
                profile_id,
                type(exc).__name__,
            )


def _error_type(result: dict[str, Any]) -> Optional[str]:
    if result.get("success"):
        return None
    explicit = result.get("error_type")
    if explicit:
        return str(explicit)
    message = str(result.get("error") or result.get("message") or "").lower()
    if "407" in message or "authentication" in message:
        return "proxy_auth"
    if "timeout" in message or "timed out" in message:
        return "timeout"
    if "connection" in message:
        return "connection"
    return "unknown"


def record_health_check(
    proxy: Proxy,
    result: dict[str, Any],
    *,
    checked_at: Optional[datetime] = None,
) -> None:
    """Persist one health-check result without credentials."""
    collection = _collection(_HEALTH_COLLECTION)
    if collection is None:
        return
    expected = (proxy.country or "").upper() or None
    actual = (result.get("country") or "").upper() or None
    country_match: Optional[bool] = None
    if expected and actual:
        country_match = expected == actual
    try:
        collection.insert_one({
            "proxy_id": proxy._id,
            "checked_at": checked_at or _now(),
            "success": bool(result.get("success")),
            "egress_ip": result.get("ip"),
            "egress_country": actual,
            "egress_city": result.get("city"),
            "expected_country": expected,
            "country_match": country_match,
            "latency_ms": result.get("latency_ms"),
            "error_type": _error_type(result),
            "error": (str(result.get("error"))[:500] if result.get("error") else None),
        })
    except Exception as exc:  # pragma: no cover
        logger.warning(
            "proxy_health_record_failed proxy_id=%s exception_type=%s",
            proxy._id,
            type(exc).__name__,
        )


async def check_proxy_connection(
    proxy_server: str,
    proxy_username: Optional[str] = None,
    proxy_password: Optional[str] = None,
) -> dict[str, Any]:
    """Test proxy connectivity and return the egress IP, country, and latency."""
    proxy_url = build_proxy_url(
        normalize_proxy_server(proxy_server),
        proxy_username,
        proxy_password,
    )
    started = time.monotonic()
    ip: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    ip_status: Optional[int] = None
    linkedin_status: Optional[int] = None

    try:
        async with httpx.AsyncClient(proxy=proxy_url, timeout=10.0) as client:
            try:
                ip_response = await client.get("https://api.ipify.org?format=json")
                ip_status = ip_response.status_code
                if ip_response.status_code == 200:
                    ip = ip_response.json().get("ip")
            except (httpx.ProxyError, httpx.TimeoutException):
                raise
            except Exception:
                ip = None

            if ip:
                try:
                    geo = await client.get("https://ipapi.co/json/")
                    if geo.status_code == 200:
                        geo_data = geo.json() or {}
                        country = geo_data.get("country_code")
                        city = geo_data.get("city")
                except Exception:
                    country = None
                    city = None

            # ipapi.co can rate-limit or omit fields. Fall back to ipinfo.io so
            # the admin test still reports the egress country for mismatch checks.
            if ip and not country:
                try:
                    info = await client.get("https://ipinfo.io/json")
                    if info.status_code == 200:
                        info_data = info.json() or {}
                        country = info_data.get("country")
                        city = city or info_data.get("city")
                except Exception:
                    pass

            try:
                response = await client.get("https://www.linkedin.com/")
                linkedin_status = response.status_code
            except (httpx.ProxyError, httpx.TimeoutException):
                raise
            except Exception:
                linkedin_status = None
    except httpx.ProxyError:
        return {
            "success": False,
            "message": "Proxy connection failed",
            "error": "Proxy connection failed",
            "error_type": "connection",
        }
    except httpx.TimeoutException:
        return {
            "success": False,
            "message": "Proxy connection timeout",
            "error": "Request timed out after 10 seconds",
            "error_type": "timeout",
        }
    except Exception:
        return {
            "success": False,
            "message": "Proxy test failed",
            "error": "Proxy test failed",
            "error_type": "unknown",
        }

    latency_ms = int((time.monotonic() - started) * 1000)

    if ip_status == 407 or linkedin_status == 407:
        return {
            "success": False,
            "message": "Proxy authentication failed",
            "error": "The proxy rejected the username or password (HTTP 407)",
            "error_type": "proxy_auth",
            "latency_ms": latency_ms,
        }

    if ip is None and linkedin_status not in (200, 301, 302, 403, 999):
        return {
            "success": False,
            "message": "Proxy connected but no request succeeded",
            "error": (
                "Unexpected proxy response "
                f"(IP check HTTP {ip_status}, LinkedIn HTTP {linkedin_status})"
            ),
            "error_type": "http_error",
            "latency_ms": latency_ms,
        }

    return {
        "success": True,
        "message": "Proxy connection successful",
        "ip": ip,
        "country": country,
        "city": city,
        "status_code": linkedin_status,
        "latency_ms": latency_ms,
    }


async def test_proxy(proxy_id: str) -> dict[str, Any]:
    """Test a stored proxy and persist its health fields."""
    proxy = Proxy.get(proxy_id)
    if not proxy:
        raise ProxyUnavailableError("Proxy not found")
    password = safe_decrypt(proxy.password_encrypted or "")
    result = await check_proxy_connection(proxy.proxy_server, proxy.username, password)

    checked_at = _now()
    result["expected_country"] = proxy.country or None
    result["country_match"] = (
        proxy.country.upper() == str(result.get("country") or "").upper()
        if proxy.country and result.get("country")
        else None
    )

    proxy.last_tested_at = checked_at
    proxy.last_test_ip = result.get("ip")
    proxy.last_test_country = result.get("country")
    proxy.last_test_city = result.get("city")
    proxy.last_test_latency_ms = result.get("latency_ms")
    proxy.last_test_error_type = _error_type(result)
    proxy.last_error = None if result.get("success") else str(result.get("error") or "")[:500]
    if not result.get("success"):
        if proxy.status in (STATUS_AVAILABLE, STATUS_ERROR):
            proxy.status = STATUS_ERROR
    elif proxy.status == STATUS_ERROR:
        proxy.status = STATUS_AVAILABLE
    proxy.save()
    record_health_check(proxy, result, checked_at=checked_at)
    return result


async def run_health_checks(
    proxy_ids: Optional[list[str]] = None,
    *,
    include_all: bool = False,
    concurrency: int = 5,
) -> dict[str, Any]:
    """Test selected proxies, or every non-retired proxy, with bounded fan-out."""
    collection = _collection(_PROXIES)
    if collection is None:
        raise ProxyError("Proxy inventory is unavailable")
    if proxy_ids:
        docs = list(collection.find({
            "_id": {"$in": proxy_ids},
            "status": {"$ne": STATUS_RETIRED},
        }))
    elif include_all:
        docs = list(collection.find({"status": {"$ne": STATUS_RETIRED}}).limit(500))
    else:
        raise ProxyError("Select at least one proxy")

    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def _check(proxy_id: str) -> dict[str, Any]:
        async with semaphore:
            try:
                result = await test_proxy(proxy_id)
                return {"proxy_id": proxy_id, "success": bool(result.get("success"))}
            except ProxyError as exc:
                return {"proxy_id": proxy_id, "success": False, "error": str(exc)}
            except Exception as exc:  # pragma: no cover - defensive isolation
                logger.warning(
                    "proxy_health_check_failed proxy_id=%s exception_type=%s",
                    proxy_id,
                    type(exc).__name__,
                )
                return {
                    "proxy_id": proxy_id,
                    "success": False,
                    "error": "Proxy health check failed",
                }

    results = await asyncio.gather(*[_check(str(doc.get("_id"))) for doc in docs])
    return {
        "tested": len(results),
        "passed": sum(1 for item in results if item.get("success")),
        "failed": sum(1 for item in results if not item.get("success")),
        "results": results,
    }


def list_health_checks(
    *,
    proxy_id: Optional[str] = None,
    only_failures: bool = False,
    only_mismatch: bool = False,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[dict[str, Any]], int]:
    collection = _collection(_HEALTH_COLLECTION)
    if collection is None:
        return [], 0
    query: dict[str, Any] = {}
    if proxy_id:
        query["proxy_id"] = proxy_id
    if only_failures:
        query["success"] = False
    if only_mismatch:
        query["country_match"] = False
    total = collection.count_documents(query)
    docs = collection.find(query).sort("checked_at", -1).skip(skip).limit(limit)
    results: list[dict[str, Any]] = []
    for doc in docs:
        checked_at = doc.get("checked_at")
        results.append({
            "id": str(doc.get("_id")),
            "proxy_id": doc.get("proxy_id"),
            "checked_at": checked_at.isoformat() if isinstance(checked_at, datetime) else None,
            "success": bool(doc.get("success")),
            "egress_ip": doc.get("egress_ip"),
            "egress_country": doc.get("egress_country"),
            "egress_city": doc.get("egress_city"),
            "expected_country": doc.get("expected_country"),
            "country_match": doc.get("country_match"),
            "latency_ms": doc.get("latency_ms"),
            "error_type": doc.get("error_type"),
            "error": doc.get("error"),
        })
    return results, total


def list_assignments(
    *,
    active: Optional[bool] = None,
    proxy_id: Optional[str] = None,
    profile_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[dict[str, Any]], int]:
    collection = _collection(_ASSIGNMENTS_COLLECTION)
    if collection is None:
        return [], 0
    query: dict[str, Any] = {}
    if active is True:
        query.update(_ACTIVE_ASSIGNMENT_FILTER)
    elif active is False:
        query["unassigned_at"] = {"$ne": None}
    if proxy_id:
        query["proxy_id"] = proxy_id
    if profile_id:
        query["profile_id"] = profile_id
    total = collection.count_documents(query)
    docs = collection.find(query).sort("assigned_at", -1).skip(skip).limit(limit)
    results: list[dict[str, Any]] = []
    for doc in docs:
        assigned_at = doc.get("assigned_at")
        unassigned_at = doc.get("unassigned_at")
        results.append({
            "id": str(doc.get("_id")),
            "proxy_id": doc.get("proxy_id"),
            "identity_id": doc.get("identity_id"),
            "profile_id": doc.get("profile_id"),
            "channel": doc.get("channel"),
            "user_id": doc.get("user_id"),
            "org_id": doc.get("org_id"),
            "assigned_by": doc.get("assigned_by"),
            "assigned_at": assigned_at.isoformat() if isinstance(assigned_at, datetime) else None,
            "unassigned_at": unassigned_at.isoformat() if isinstance(unassigned_at, datetime) else None,
            "reason": doc.get("reason"),
        })
    return results, total


def _proxy_for_subuser(subuser: str) -> Optional[Proxy]:
    collection = _collection(_PROXIES)
    if collection is None:
        return None
    doc = collection.find_one({"massive_subuser": subuser})
    if doc:
        return Proxy.from_dict(doc)
    doc = collection.find_one({
        "$or": [
            {"massive_subuser": f"subaccount-{subuser}"},
            {"linkedin_profile_id": subuser},
            {"last_assigned_profile_id": subuser},
        ]
    })
    if doc:
        return Proxy.from_dict(doc)
    marker = "subaccount-"
    if marker in subuser:
        tail = subuser.split(marker, 1)[1]
        token = tail.split("-country-", 1)[0].split("-session-", 1)[0]
        if token:
            doc = collection.find_one({
                "$or": [
                    {"linkedin_profile_id": token},
                    {"last_assigned_profile_id": token},
                    {"massive_subuser": f"subaccount-{token}"},
                ]
            })
            if doc:
                return Proxy.from_dict(doc)
    return None


def record_usage_snapshot(
    *,
    proxy: Proxy,
    subuser: str,
    bytes_used: int,
    period_start: str,
    period_end: str,
    channel: str = "linkedin",
    source: str = "massive_reporting",
) -> None:
    """Upsert one usage snapshot keyed by proxy and period."""
    collection = _collection(_USAGE_COLLECTION)
    if collection is None:
        return
    now = _now()
    profile_id = proxy.linkedin_profile_id or proxy.last_assigned_profile_id
    user_id = proxy.assigned_user_id or proxy.last_assigned_user_id
    org_id = proxy.assigned_org_id or proxy.last_assigned_org_id
    collection.update_one(
        {
            "proxy_id": proxy._id,
            "subuser": subuser,
            "channel": channel,
            "period_start": period_start,
            "period_end": period_end,
            "source": source,
        },
        {
            "$set": {
                "proxy_id": proxy._id,
                "subuser": subuser,
                "profile_id": profile_id,
                "user_id": user_id,
                "org_id": org_id,
                "channel": channel,
                "bytes": max(0, int(bytes_used)),
                "period_start": period_start,
                "period_end": period_end,
                "source": source,
                "synced_at": now,
            }
        },
        upsert=True,
    )
    proxies = _collection(_PROXIES)
    if proxies is not None:
        proxies.update_one(
            {"_id": proxy._id},
            {"$set": {"used_bytes": max(0, int(bytes_used)), "updated_at": now}},
        )


def get_usage_summary(
    *,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
    limit: int = 1000,
) -> dict[str, Any]:
    """Aggregate internal proxy usage per proxy, profile, and workspace."""
    collection = _collection(_USAGE_COLLECTION)
    if collection is None:
        return {
            "total_bytes": 0,
            "period_start": period_start,
            "period_end": period_end,
            "per_proxy": [],
            "per_profile": [],
            "per_workspace": [],
        }
    query: dict[str, Any] = {}
    if period_start:
        query["period_start"] = {"$gte": period_start}
    if period_end:
        query["period_end"] = {"$lte": period_end}
    docs = list(collection.find(query).sort("period_start", -1).limit(limit))

    proxies_collection = _collection(_PROXIES)
    profiles_collection = _collection(_PROFILES)
    users_collection = _collection("users")
    proxy_labels: dict[str, dict[str, Any]] = {}
    profile_labels: dict[str, str] = {}
    workspace_labels: dict[str, str] = {}
    if proxies_collection is not None:
        proxy_ids = {str(doc.get("proxy_id")) for doc in docs if doc.get("proxy_id")}
        for doc in proxies_collection.find({"_id": {"$in": list(proxy_ids)}}):
            proxy_labels[str(doc.get("_id"))] = {
                "label": doc.get("label"),
                "status": doc.get("status"),
                "provider": doc.get("provider"),
            }
    if profiles_collection is not None:
        profile_ids = {str(doc.get("profile_id")) for doc in docs if doc.get("profile_id")}
        for doc in profiles_collection.find({"_id": {"$in": list(profile_ids)}}):
            profile_labels[str(doc.get("_id"))] = str(
                doc.get("linkedin_username") or doc.get("username") or ""
            )
    if users_collection is not None:
        user_ids = {str(doc.get("user_id")) for doc in docs if doc.get("user_id")}
        for doc in users_collection.find({"_id": {"$in": list(user_ids)}}):
            workspace_labels[str(doc.get("_id"))] = str(doc.get("email") or "")

    per_proxy: dict[str, dict[str, Any]] = {}
    per_profile: dict[str, dict[str, Any]] = {}
    per_workspace: dict[str, dict[str, Any]] = {}
    per_channel: dict[str, dict[str, Any]] = {}
    total_bytes = 0
    for doc in docs:
        bytes_used = int(doc.get("bytes") or 0)
        total_bytes += bytes_used
        proxy_id = str(doc.get("proxy_id") or "")
        profile_id = str(doc.get("profile_id") or "")
        user_id = str(doc.get("user_id") or "")
        org_id = str(doc.get("org_id") or "")
        channel = str(doc.get("channel") or "linkedin")

        proxy_entry = per_proxy.setdefault(proxy_id, {
            "proxy_id": proxy_id,
            "label": proxy_labels.get(proxy_id, {}).get("label"),
            "status": proxy_labels.get(proxy_id, {}).get("status"),
            "provider": proxy_labels.get(proxy_id, {}).get("provider"),
            "bytes": 0,
            "profile_ids": set(),
            "workspace_ids": set(),
        })
        proxy_entry["bytes"] += bytes_used
        if profile_id:
            proxy_entry["profile_ids"].add(profile_id)
        if user_id:
            proxy_entry["workspace_ids"].add(user_id)

        if profile_id:
            profile_entry = per_profile.setdefault(profile_id, {
                "profile_id": profile_id,
                "label": profile_labels.get(profile_id, ""),
                "workspace_id": user_id or None,
                "bytes": 0,
                "proxy_ids": set(),
            })
            profile_entry["bytes"] += bytes_used
            if proxy_id:
                profile_entry["proxy_ids"].add(proxy_id)

        workspace_key = org_id or user_id
        if workspace_key:
            workspace_entry = per_workspace.setdefault(workspace_key, {
                "workspace_id": workspace_key,
                "label": workspace_labels.get(user_id, "") if user_id else "",
                "bytes": 0,
                "proxy_ids": set(),
                "profile_ids": set(),
            })
            workspace_entry["bytes"] += bytes_used
            if proxy_id:
                workspace_entry["proxy_ids"].add(proxy_id)
            if profile_id:
                workspace_entry["profile_ids"].add(profile_id)

        channel_entry = per_channel.setdefault(channel, {
            "channel": channel,
            "bytes": 0,
            "proxy_ids": set(),
            "profile_ids": set(),
        })
        channel_entry["bytes"] += bytes_used
        if proxy_id:
            channel_entry["proxy_ids"].add(proxy_id)
        if profile_id:
            channel_entry["profile_ids"].add(profile_id)

    def _finalize(entries: dict[str, dict[str, Any]], set_fields: tuple[str, ...]) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        for entry in entries.values():
            item = dict(entry)
            for field in set_fields:
                item[field] = sorted(item[field])
            output.append(item)
        return sorted(output, key=lambda item: item.get("bytes", 0), reverse=True)

    return {
        "total_bytes": total_bytes,
        "period_start": period_start,
        "period_end": period_end,
        "per_proxy": _finalize(per_proxy, ("profile_ids", "workspace_ids")),
        "per_profile": _finalize(per_profile, ("proxy_ids",)),
        "per_workspace": _finalize(per_workspace, ("proxy_ids", "profile_ids")),
        "per_channel": _finalize(per_channel, ("proxy_ids", "profile_ids")),
    }


def assign_proxy_for_new_profile(
    profile_id: str,
    user_id: str,
    country: str,
    subdivision: Optional[str] = None,
    city: Optional[str] = None,
) -> Proxy:
    """Find and assign a matching proxy, raising a clear error when none exists.

    Two concurrent account creations may discover the same candidate. The
    proxy claim itself is atomic, so retry a few times with a fresh candidate
    instead of failing the customer's account creation.
    """
    from openoutreach.config import settings

    if not getattr(settings, "MANAGED_PROXIES_ENABLED", True):
        raise ProxyUnavailableError("Managed proxy provisioning is disabled")
    country_value, subdivision_value, city_value = normalize_region(country, subdivision, city)
    for _ in range(5):
        proxy = find_available_proxy(country_value, subdivision_value, city_value)
        if not proxy:
            break
        try:
            return assign_proxy_to_profile(proxy._id, profile_id, user_id)
        except ProxyUnavailableError:
            continue

    from openoutreach.proxies.massive_client import (
        MassiveConfig,
        provision_massive_fallback,
    )

    if MassiveConfig.from_settings() is not None:
        fallback = provision_massive_fallback(
            profile_id,
            country_value,
            subdivision_value,
            city_value,
        )
        try:
            return assign_proxy_to_profile(fallback._id, profile_id, user_id)
        except ProxyError:
            retire_proxy(fallback._id, reason="fallback_assignment_failed")
            raise

    raise ProxyUnavailableError(
        f"No managed proxy is available for {country_value}. "
        "Contact support so we can add capacity for this region."
    )
