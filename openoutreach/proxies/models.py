"""Minimal managed-proxy inventory for Phase 0.

Passwords are encrypted at rest with the shared Mongo crypto helpers and are
never serialized to API responses or logs.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.mongodb.crypto import safe_encrypt

logger = logging.getLogger(__name__)

STATUS_AVAILABLE = "available"
STATUS_ASSIGNED = "assigned"
STATUS_DISABLED = "disabled"
STATUS_ERROR = "error"
STATUS_RETIRED = "retired"

PROVIDER_MANUAL = "manual"
PROVIDER_MASSIVE_RESIDENTIAL = "massive_residential"
PROVIDER_MASSIVE_ISP = "massive_isp"

KIND_RESIDENTIAL = "residential"
KIND_ISP = "isp"
KIND_MOBILE = "mobile"
KIND_DATACENTER = "datacenter"

REGION_MODE_FIXED = "fixed"
REGION_MODE_TARGETED = "targeted"

PROVIDERS = {PROVIDER_MANUAL, PROVIDER_MASSIVE_RESIDENTIAL, PROVIDER_MASSIVE_ISP}
KINDS = {KIND_RESIDENTIAL, KIND_ISP, KIND_MOBILE, KIND_DATACENTER}
DEVICE_TYPES = {"common", "mobile", "tv"}
REGION_MODES = {REGION_MODE_FIXED, REGION_MODE_TARGETED}

_COLLECTION = "proxies"
_ASSIGNMENTS_COLLECTION = "proxy_assignments"
_HEALTH_COLLECTION = "proxy_health_checks"
_USAGE_COLLECTION = "proxy_usage_snapshots"


class ProxyError(ValueError):
    """Base error for proxy inventory operations."""


class ProxyUnavailableError(ProxyError):
    """The proxy is not available for this assignment."""


class ProxyReuseError(ProxyError):
    """A used proxy may never be assigned to a different LinkedIn account."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Proxy:
    """A single managed proxy identity."""

    def __init__(
        self,
        _id: Optional[str] = None,
        provider: str = PROVIDER_MANUAL,
        label: str = "",
        protocol: str = "http",
        host: str = "",
        port: int = 0,
        username: Optional[str] = None,
        password_encrypted: Optional[str] = None,
        country: str = "",
        subdivision: Optional[str] = None,
        city: Optional[str] = None,
        region_mode: str = "targeted",
        kind: str = KIND_RESIDENTIAL,
        device_type: str = "common",
        status: str = STATUS_AVAILABLE,
        identity_id: Optional[str] = None,
        linkedin_profile_id: Optional[str] = None,
        assigned_user_id: Optional[str] = None,
        assigned_org_id: Optional[str] = None,
        assigned_at: Optional[datetime] = None,
        assigned_by: Optional[str] = None,
        ever_assigned: bool = False,
        last_assigned_profile_id: Optional[str] = None,
        last_assigned_user_id: Optional[str] = None,
        last_assigned_org_id: Optional[str] = None,
        massive_account_id: Optional[str] = None,
        massive_parent_username: Optional[str] = None,
        massive_subuser: Optional[str] = None,
        traffic_limit_bytes: Optional[int] = None,
        used_bytes: int = 0,
        limit_reached: bool = False,
        last_tested_at: Optional[datetime] = None,
        last_test_ip: Optional[str] = None,
        last_test_country: Optional[str] = None,
        last_test_city: Optional[str] = None,
        last_test_latency_ms: Optional[int] = None,
        last_test_error_type: Optional[str] = None,
        last_error: Optional[str] = None,
        retired_at: Optional[datetime] = None,
        disabled_at: Optional[datetime] = None,
        rotated_at: Optional[datetime] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        created_by: Optional[str] = None,
    ):
        self._id = _id or str(uuid4())
        self.provider = provider
        self.label = label or f"{host}:{port}"
        self.protocol = protocol
        self.host = host
        self.port = port
        self.username = username
        self.password_encrypted = password_encrypted
        self.country = country
        self.subdivision = subdivision
        self.city = city
        self.region_mode = region_mode
        self.kind = kind
        self.device_type = device_type
        self.status = status
        self.identity_id = identity_id
        self.linkedin_profile_id = linkedin_profile_id
        self.assigned_user_id = assigned_user_id
        self.assigned_org_id = assigned_org_id
        self.assigned_at = assigned_at
        self.assigned_by = assigned_by
        self.ever_assigned = ever_assigned
        self.last_assigned_profile_id = last_assigned_profile_id
        self.last_assigned_user_id = last_assigned_user_id
        self.last_assigned_org_id = last_assigned_org_id
        self.massive_account_id = massive_account_id
        self.massive_parent_username = massive_parent_username
        self.massive_subuser = massive_subuser
        self.traffic_limit_bytes = traffic_limit_bytes
        self.used_bytes = used_bytes
        self.limit_reached = limit_reached
        self.last_tested_at = last_tested_at
        self.last_test_ip = last_test_ip
        self.last_test_country = last_test_country
        self.last_test_city = last_test_city
        self.last_test_latency_ms = last_test_latency_ms
        self.last_test_error_type = last_test_error_type
        self.last_error = last_error
        self.retired_at = retired_at
        self.disabled_at = disabled_at
        self.rotated_at = rotated_at
        self.created_at = created_at or _now()
        self.updated_at = updated_at or _now()
        self.created_by = created_by

    @property
    def proxy_server(self) -> str:
        return f"{self.protocol}://{self.host}:{self.port}"

    @property
    def is_used(self) -> bool:
        """A used proxy may never be assigned to a different LinkedIn account."""
        return bool(
            self.ever_assigned
            or self.linkedin_profile_id
            or self.last_assigned_profile_id
        )

    @staticmethod
    def now() -> datetime:
        return _now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "_id": self._id,
            "provider": self.provider,
            "label": self.label,
            "protocol": self.protocol,
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "password_encrypted": self.password_encrypted,
            "country": self.country,
            "subdivision": self.subdivision,
            "city": self.city,
            "region_mode": self.region_mode,
            "kind": self.kind,
            "device_type": self.device_type,
            "status": self.status,
            "identity_id": self.identity_id,
            "linkedin_profile_id": self.linkedin_profile_id,
            "assigned_user_id": self.assigned_user_id,
            "assigned_org_id": self.assigned_org_id,
            "assigned_at": self.assigned_at,
            "assigned_by": self.assigned_by,
            "ever_assigned": self.ever_assigned,
            "last_assigned_profile_id": self.last_assigned_profile_id,
            "last_assigned_user_id": self.last_assigned_user_id,
            "last_assigned_org_id": self.last_assigned_org_id,
            "massive_account_id": self.massive_account_id,
            "massive_parent_username": self.massive_parent_username,
            "massive_subuser": self.massive_subuser,
            "traffic_limit_bytes": self.traffic_limit_bytes,
            "used_bytes": self.used_bytes,
            "limit_reached": self.limit_reached,
            "last_tested_at": self.last_tested_at,
            "last_test_ip": self.last_test_ip,
            "last_test_country": self.last_test_country,
            "last_test_city": self.last_test_city,
            "last_test_latency_ms": self.last_test_latency_ms,
            "last_test_error_type": self.last_test_error_type,
            "last_error": self.last_error,
            "retired_at": self.retired_at,
            "disabled_at": self.disabled_at,
            "rotated_at": self.rotated_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "created_by": self.created_by,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Proxy":
        return cls(
            _id=str(data.get("_id")),
            provider=data.get("provider", PROVIDER_MANUAL),
            label=data.get("label", ""),
            protocol=data.get("protocol", "http"),
            host=data.get("host", ""),
            port=int(data.get("port") or 0),
            username=data.get("username"),
            password_encrypted=data.get("password_encrypted"),
            country=data.get("country", ""),
            subdivision=data.get("subdivision"),
            city=data.get("city"),
            region_mode=data.get("region_mode", "targeted"),
            kind=data.get("kind", KIND_RESIDENTIAL),
            device_type=data.get("device_type", "common"),
            status=data.get("status", STATUS_AVAILABLE),
            identity_id=data.get("identity_id"),
            linkedin_profile_id=data.get("linkedin_profile_id"),
            assigned_user_id=data.get("assigned_user_id"),
            assigned_org_id=data.get("assigned_org_id"),
            assigned_at=data.get("assigned_at"),
            assigned_by=data.get("assigned_by"),
            ever_assigned=bool(data.get("ever_assigned", False)),
            last_assigned_profile_id=data.get("last_assigned_profile_id"),
            last_assigned_user_id=data.get("last_assigned_user_id"),
            last_assigned_org_id=data.get("last_assigned_org_id"),
            massive_account_id=data.get("massive_account_id"),
            massive_parent_username=data.get("massive_parent_username"),
            massive_subuser=data.get("massive_subuser"),
            traffic_limit_bytes=data.get("traffic_limit_bytes"),
            used_bytes=data.get("used_bytes", 0),
            limit_reached=data.get("limit_reached", False),
            last_tested_at=data.get("last_tested_at"),
            last_test_ip=data.get("last_test_ip"),
            last_test_country=data.get("last_test_country"),
            last_test_city=data.get("last_test_city"),
            last_test_latency_ms=data.get("last_test_latency_ms"),
            last_test_error_type=data.get("last_test_error_type"),
            last_error=data.get("last_error"),
            retired_at=data.get("retired_at"),
            disabled_at=data.get("disabled_at"),
            rotated_at=data.get("rotated_at"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            created_by=data.get("created_by"),
        )

    @property
    def country_mismatch(self) -> Optional[bool]:
        """True when the last egress country differs from the expected one."""
        if not self.country or not self.last_test_country:
            return None
        return self.country.upper() != self.last_test_country.upper()

    def public_dict(self) -> dict[str, Any]:
        """Serialize for API responses without credentials."""
        username = self.username or None
        masked_username = "***" if username else None
        return {
            "id": self._id,
            "provider": self.provider,
            "label": self.label,
            "protocol": self.protocol,
            "host": self.host,
            "port": self.port,
            "username": masked_username,
            "has_username": bool(username),
            "has_password": bool(self.password_encrypted),
            "country": self.country,
            "subdivision": self.subdivision,
            "city": self.city,
            "region_mode": self.region_mode,
            "kind": self.kind,
            "device_type": self.device_type,
            "status": self.status,
            "identity_id": self.identity_id,
            "linkedin_profile_id": self.linkedin_profile_id,
            "assigned_user_id": self.assigned_user_id,
            "assigned_org_id": self.assigned_org_id,
            "assigned_at": self.assigned_at.isoformat() if self.assigned_at else None,
            "assigned_by": self.assigned_by,
            "ever_assigned": self.ever_assigned,
            "last_assigned_profile_id": self.last_assigned_profile_id,
            "last_assigned_user_id": self.last_assigned_user_id,
            "last_assigned_org_id": self.last_assigned_org_id,
            "massive_account_id": self.massive_account_id,
            "massive_subuser": self.massive_subuser,
            "traffic_limit_bytes": self.traffic_limit_bytes,
            "used_bytes": self.used_bytes,
            "limit_reached": self.limit_reached,
            "last_tested_at": self.last_tested_at.isoformat() if self.last_tested_at else None,
            "last_test_ip": self.last_test_ip,
            "last_test_country": self.last_test_country,
            "last_test_city": self.last_test_city,
            "last_test_latency_ms": self.last_test_latency_ms,
            "last_test_error_type": self.last_test_error_type,
            "country_mismatch": self.country_mismatch,
            "last_error": self.last_error,
            "retired_at": self.retired_at.isoformat() if self.retired_at else None,
            "disabled_at": self.disabled_at.isoformat() if self.disabled_at else None,
            "rotated_at": self.rotated_at.isoformat() if self.rotated_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def save(self) -> str:
        collection = get_mongodb_collection(_COLLECTION)
        if collection is None:
            raise RuntimeError("MongoDB collection 'proxies' not available")
        self.updated_at = _now()
        collection.update_one({"_id": self._id}, {"$set": self.to_dict()}, upsert=True)
        return self._id

    @classmethod
    def get(cls, proxy_id: str) -> Optional["Proxy"]:
        collection = get_mongodb_collection(_COLLECTION)
        if collection is None:
            return None
        data = collection.find_one({"_id": proxy_id})
        return cls.from_dict(data) if data else None


def create_proxy(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    country: str,
    provider: str = PROVIDER_MANUAL,
    kind: str = KIND_RESIDENTIAL,
    protocol: str = "http",
    subdivision: Optional[str] = None,
    city: Optional[str] = None,
    label: str = "",
    region_mode: str = REGION_MODE_TARGETED,
    device_type: str = "common",
    identity_id: Optional[str] = None,
    massive_parent_username: Optional[str] = None,
    massive_subuser: Optional[str] = None,
    created_by: Optional[str] = None,
) -> Proxy:
    """Create and persist one proxy with an encrypted password."""
    from openoutreach.proxies.service import validate_proxy_host

    validate_proxy_host(host)
    encrypted = safe_encrypt(password)
    if not encrypted:
        raise ProxyError("Failed to encrypt proxy password")
    proxy = Proxy(
        provider=provider,
        label=label,
        protocol=protocol,
        host=host,
        port=port,
        username=username,
        password_encrypted=encrypted,
        country=country,
        subdivision=subdivision,
        city=city,
        region_mode=region_mode,
        kind=kind,
        device_type=device_type,
        identity_id=identity_id,
        massive_parent_username=massive_parent_username,
        massive_subuser=massive_subuser,
        created_by=created_by,
    )
    proxy.save()
    return proxy
