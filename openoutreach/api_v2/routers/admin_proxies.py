"""Admin managed-proxy inventory endpoints (Phase 0)."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from openoutreach.api_v2.dependencies_v2 import get_admin_user
from openoutreach.billing.admin_security import AdminSecurityPolicy
from openoutreach.config import settings
from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.proxies.models import (
    KIND_DATACENTER,
    KIND_ISP,
    KIND_MOBILE,
    KIND_RESIDENTIAL,
    PROVIDER_MANUAL,
    PROVIDER_MASSIVE_ISP,
    PROVIDER_MASSIVE_RESIDENTIAL,
    ProxyError,
    ProxyReuseError,
    ProxyUnavailableError,
)
from openoutreach.proxies.region import RegionError, normalize_country
from openoutreach.proxies.service import (
    assign_proxy_to_profile,
    disable_proxy,
    import_proxies,
    list_proxies,
    test_proxy,
)

logger = logging.getLogger(__name__)


def _require_managed_proxies_enabled() -> None:
    if not getattr(settings, "MANAGED_PROXIES_ENABLED", True):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Managed proxy operations are disabled",
        )


router = APIRouter(
    prefix="/api/admin/proxies",
    tags=["admin-proxies"],
    dependencies=[Depends(_require_managed_proxies_enabled)],
)

_PROVIDERS = {
    PROVIDER_MANUAL,
    PROVIDER_MASSIVE_RESIDENTIAL,
    PROVIDER_MASSIVE_ISP,
}
_KINDS = {KIND_RESIDENTIAL, KIND_ISP, KIND_MOBILE, KIND_DATACENTER}


class ProxyImportRequest(BaseModel):
    """Bulk paste payload for the proxy inventory."""
    text: str
    provider: str = PROVIDER_MANUAL
    kind: str = KIND_RESIDENTIAL
    default_country: Optional[str] = None


class ProxyAssignRequest(BaseModel):
    """Assign one proxy to one cloud LinkedIn profile."""
    profile_id: str


def _error(exc: ProxyError) -> HTTPException:
    code = status.HTTP_409_CONFLICT if isinstance(
        exc, (ProxyUnavailableError, ProxyReuseError)
    ) else status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=code, detail=str(exc))


@router.get("", dependencies=[Depends(get_admin_user)])
async def list_proxy_inventory(
    status_filter: Optional[str] = Query(None, alias="status"),
    country: Optional[str] = Query(None),
    provider: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    """List proxies without exposing passwords."""
    try:
        proxies, total = list_proxies(
            status=status_filter,
            country=country,
            provider=provider,
            skip=skip,
            limit=limit,
        )
    except ProxyError as exc:
        raise _error(exc)
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "proxies": [proxy.public_dict() for proxy in proxies],
    }


@router.post("/import", dependencies=[Depends(get_admin_user)])
async def import_proxy_inventory(
    body: ProxyImportRequest,
    current_admin: str = Depends(get_admin_user),
) -> dict:
    """Bulk import pasted proxies. Passwords are encrypted and never returned."""
    provider = body.provider.strip().lower()
    kind = body.kind.strip().lower()
    if provider not in _PROVIDERS:
        raise HTTPException(status_code=400, detail="Invalid proxy provider")
    if kind not in _KINDS:
        raise HTTPException(status_code=400, detail="Invalid proxy kind")

    default_country = None
    if body.default_country:
        try:
            default_country = normalize_country(body.default_country)
        except RegionError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    try:
        result = import_proxies(
            body.text,
            provider=provider,
            kind=kind,
            default_country=default_country,
            created_by=current_admin,
        )
    except ProxyError as exc:
        raise _error(exc)

    AdminSecurityPolicy.log_admin_action(
        current_admin,
        "proxy.import",
        details={
            "created": result["created"],
            "skipped": result["skipped"],
            "failed": result["failed"],
        },
    )
    return result


@router.post("/{proxy_id}/test", dependencies=[Depends(get_admin_user)])
async def test_proxy_inventory(
    proxy_id: str,
    current_admin: str = Depends(get_admin_user),
) -> dict:
    """Test a proxy and persist its egress IP, country, and latency."""
    try:
        result = await test_proxy(proxy_id)
    except ProxyError as exc:
        raise _error(exc)

    AdminSecurityPolicy.log_admin_action(
        current_admin,
        "proxy.test",
        details={"proxy_id": proxy_id, "success": bool(result.get("success"))},
    )
    return result


@router.post("/{proxy_id}/assign", dependencies=[Depends(get_admin_user)])
async def assign_proxy_inventory(
    proxy_id: str,
    body: ProxyAssignRequest,
    current_admin: str = Depends(get_admin_user),
) -> dict:
    """Assign a proxy to a cloud LinkedIn profile."""
    profiles = get_mongodb_collection("linkedin_profiles")
    if profiles is None:
        raise HTTPException(status_code=503, detail="LinkedIn profiles are unavailable")
    profile = profiles.find_one({"_id": body.profile_id})
    if not profile:
        raise HTTPException(status_code=404, detail="LinkedIn profile not found")
    if profile.get("execution_mode") != "cloud":
        raise HTTPException(
            status_code=400,
            detail="Proxy assignment is only available for cloud profiles",
        )
    if profile.get("proxy_server"):
        raise HTTPException(
            status_code=409,
            detail="This profile already has a proxy",
        )

    try:
        proxy = assign_proxy_to_profile(
            proxy_id,
            body.profile_id,
            profile.get("user_id") or "",
        )
    except ProxyError as exc:
        raise _error(exc)

    AdminSecurityPolicy.log_admin_action(
        current_admin,
        "proxy.assign",
        target_user_id=profile.get("user_id"),
        details={"proxy_id": proxy_id, "profile_id": body.profile_id},
    )
    return {"proxy": proxy.public_dict(), "profile_id": body.profile_id}


@router.post("/{proxy_id}/disable", dependencies=[Depends(get_admin_user)])
async def disable_proxy_inventory(
    proxy_id: str,
    current_admin: str = Depends(get_admin_user),
) -> dict:
    """Disable an unassigned proxy."""
    try:
        proxy = disable_proxy(proxy_id)
    except ProxyError as exc:
        raise _error(exc)

    AdminSecurityPolicy.log_admin_action(
        current_admin,
        "proxy.disable",
        details={"proxy_id": proxy_id},
    )
    return {"proxy": proxy.public_dict()}
