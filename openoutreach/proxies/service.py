"""Managed proxy inventory operations: import, assign, test, disable."""
from __future__ import annotations

import logging
import time
from typing import Any, Optional
from urllib.parse import quote, urlparse, urlunparse

import httpx

from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.mongodb.crypto import safe_decrypt
from openoutreach.proxies.models import (
    KIND_RESIDENTIAL,
    PROVIDER_MANUAL,
    STATUS_AVAILABLE,
    STATUS_ASSIGNED,
    STATUS_DISABLED,
    STATUS_RETIRED,
    Proxy,
    ProxyError,
    ProxyReuseError,
    ProxyUnavailableError,
    create_proxy,
)
from openoutreach.proxies.parser import parse_bulk_proxies
from openoutreach.proxies.region import normalize_region

logger = logging.getLogger(__name__)

_PROFILES = "linkedin_profiles"


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


def list_proxies(
    *,
    status: Optional[str] = None,
    country: Optional[str] = None,
    provider: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[Proxy], int]:
    collection = get_mongodb_collection("proxies")
    if collection is None:
        raise ProxyError("Proxy inventory is unavailable")
    query: dict[str, Any] = {}
    if status:
        query["status"] = status
    if country:
        query["country"] = country.upper()
    if provider:
        query["provider"] = provider
    total = collection.count_documents(query)
    docs = collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
    return [Proxy.from_dict(doc) for doc in docs], total


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
    collection = get_mongodb_collection("proxies")
    if collection is None:
        raise ProxyError("Proxy inventory is unavailable")

    created: list[Proxy] = []
    skipped = 0
    for entry in entries:
        existing = collection.find_one(
            {
                "host": entry["host"],
                "port": entry["port"],
                "username": entry["username"],
            },
            {"_id": 1},
        )
        if existing:
            skipped += 1
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
                provider=provider,
                kind=kind,
                protocol=entry["protocol"],
                created_by=created_by,
            )
        except ProxyError as exc:
            errors.append({"line": 0, "error": str(exc)})
            continue
        created.append(proxy)

    return {
        "created": len(created),
        "skipped": skipped,
        "failed": len(errors),
        "errors": errors,
        "proxies": [proxy.public_dict() for proxy in created],
    }


def find_available_proxy(
    country: str,
    subdivision: Optional[str] = None,
    city: Optional[str] = None,
) -> Optional[Proxy]:
    """Find an unused proxy, preferring the narrowest matching region."""
    collection = get_mongodb_collection("proxies")
    if collection is None:
        return None

    base: dict[str, Any] = {
        "status": STATUS_AVAILABLE,
        "country": country.upper(),
        "linkedin_profile_id": None,
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


def assign_proxy_to_profile(
    proxy_id: str,
    profile_id: str,
    user_id: str,
) -> Proxy:
    """Atomically assign a proxy to a cloud profile.

    A proxy may only ever serve one LinkedIn profile. Reassigning the same
    profile is allowed; assigning a previously used proxy to a different
    profile is not.
    """
    collection = get_mongodb_collection("proxies")
    profiles = get_mongodb_collection(_PROFILES)
    if collection is None or profiles is None:
        raise ProxyError("Proxy inventory is unavailable")

    existing = collection.find_one({"_id": proxy_id})
    if not existing:
        raise ProxyUnavailableError("Proxy not found")
    if existing.get("linkedin_profile_id") not in (None, profile_id):
        raise ProxyReuseError(
            "This proxy was already used by another LinkedIn account and cannot be recycled"
        )

    profile_doc = profiles.find_one(
        {"_id": profile_id, "user_id": user_id},
        {"proxy_id": 1, "proxy_server": 1},
    )
    if not profile_doc:
        raise ProxyUnavailableError("LinkedIn profile not found")
    current_proxy_id = profile_doc.get("proxy_id")
    if current_proxy_id and current_proxy_id != proxy_id:
        raise ProxyError("This profile already has a different proxy")
    if profile_doc.get("proxy_server") and not current_proxy_id:
        raise ProxyError("This profile already has a BYO proxy")

    previous_owner = existing.get("linkedin_profile_id")
    claimed = collection.find_one_and_update(
        {
            "_id": proxy_id,
            "status": STATUS_AVAILABLE,
            "$or": [
                {"linkedin_profile_id": None},
                {"linkedin_profile_id": profile_id},
            ],
        },
        {
            "$set": {
                "status": STATUS_ASSIGNED,
                "linkedin_profile_id": profile_id,
                "assigned_user_id": user_id,
                "assigned_at": Proxy.now(),
                "updated_at": Proxy.now(),
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
                "active": True,
                "is_active": True,
                "daemon_status": "proxy_ready",
                "updated_at": Proxy.now(),
            }
        },
    )
    if getattr(updated, "modified_count", 0) == 0:
        if previous_owner is None:
            collection.update_one(
                {"_id": proxy_id, "linkedin_profile_id": profile_id},
                {
                    "$set": {
                        "status": STATUS_AVAILABLE,
                        "linkedin_profile_id": None,
                        "assigned_user_id": None,
                        "assigned_at": None,
                        "updated_at": Proxy.now(),
                    }
                },
            )
        raise ProxyUnavailableError(
            "Profile was assigned a different proxy concurrently"
        )
    logger.info("Assigned proxy %s to profile %s", proxy._id, profile_id)
    return proxy


def disable_proxy(proxy_id: str) -> Proxy:
    """Disable an unassigned proxy. Assigned proxies must be unassigned first."""
    collection = get_mongodb_collection("proxies")
    if collection is None:
        raise ProxyError("Proxy inventory is unavailable")
    doc = collection.find_one({"_id": proxy_id})
    if not doc:
        raise ProxyUnavailableError("Proxy not found")
    if doc.get("linkedin_profile_id"):
        raise ProxyError("Unassign the proxy before disabling it")
    collection.update_one(
        {"_id": proxy_id},
        {"$set": {"status": STATUS_DISABLED, "updated_at": Proxy.now()}},
    )
    return Proxy.get(proxy_id)  # type: ignore[return-value]


def retire_proxy_for_profile(profile_id: str) -> None:
    """Retire the proxy attached to a deleted profile; never recycle it."""
    collection = get_mongodb_collection("proxies")
    if collection is None:
        return
    collection.update_many(
        {"linkedin_profile_id": profile_id},
        {
            "$set": {
                "status": STATUS_RETIRED,
                "assigned_user_id": None,
                "updated_at": Proxy.now(),
            }
        },
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
                        country = (geo.json() or {}).get("country_code")
                except Exception:
                    country = None

            try:
                response = await client.get("https://www.linkedin.com/")
                linkedin_status = response.status_code
            except (httpx.ProxyError, httpx.TimeoutException):
                raise
            except Exception:
                linkedin_status = None
    except httpx.ProxyError:
        return {"success": False, "message": "Proxy connection failed", "error": "Proxy connection failed"}
    except httpx.TimeoutException:
        return {
            "success": False,
            "message": "Proxy connection timeout",
            "error": "Request timed out after 10 seconds",
        }
    except Exception:
        return {"success": False, "message": "Proxy test failed", "error": "Proxy test failed"}

    latency_ms = int((time.monotonic() - started) * 1000)

    if ip_status == 407 or linkedin_status == 407:
        return {
            "success": False,
            "message": "Proxy authentication failed",
            "error": "The proxy rejected the username or password (HTTP 407)",
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
            "latency_ms": latency_ms,
        }

    return {
        "success": True,
        "message": "Proxy connection successful",
        "ip": ip,
        "country": country,
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

    proxy.last_tested_at = Proxy.now()
    proxy.last_test_ip = result.get("ip")
    proxy.last_test_country = result.get("country")
    proxy.last_test_latency_ms = result.get("latency_ms")
    proxy.last_error = None if result.get("success") else str(result.get("error") or "")[:500]
    if not result.get("success"):
        proxy.status = "error" if proxy.status == STATUS_AVAILABLE else proxy.status
    elif proxy.status == "error":
        proxy.status = STATUS_AVAILABLE
    proxy.save()
    return result


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
    country_value, subdivision_value, city_value = normalize_region(country, subdivision, city)
    for _ in range(5):
        proxy = find_available_proxy(country_value, subdivision_value, city_value)
        if not proxy:
            break
        try:
            return assign_proxy_to_profile(proxy._id, profile_id, user_id)
        except ProxyUnavailableError:
            continue
    raise ProxyUnavailableError(
        f"No managed proxy is available for {country_value}. "
        "Contact support so we can add capacity for this region."
    )
