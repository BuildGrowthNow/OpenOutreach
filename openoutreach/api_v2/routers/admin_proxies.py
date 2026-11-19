"""Admin managed-proxy operations (Phase 1).

Every route is admin-only and gated by ``MANAGED_PROXIES_ENABLED``. Passwords,
Massive keys, cookies, and tokens are never returned or logged.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

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
from openoutreach.proxies.rate_limit import AdminActionRateLimiter
from openoutreach.proxies.region import RegionError, normalize_country
from openoutreach.proxies.service import (
    assign_proxy_to_profile,
    disable_proxy,
    enable_proxy,
    export_proxies_csv,
    get_proxy_stats,
    get_usage_summary,
    import_proxies,
    list_assignments,
    list_health_checks,
    list_proxies,
    preview_proxies,
    retire_proxy,
    rotate_proxy_password,
    run_health_checks,
    test_proxy,
    unassign_proxy,
)


def _require_managed_proxies_enabled() -> None:
    if not getattr(settings, "MANAGED_PROXIES_ENABLED", True):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Managed proxy operations are disabled",
        )


router = APIRouter(
    prefix="/api/admin/proxies",
    tags=["admin-proxies"],
    dependencies=[
        Depends(_require_managed_proxies_enabled),
        Depends(get_admin_user),
    ],
)

_PROVIDERS = {
    PROVIDER_MANUAL,
    PROVIDER_MASSIVE_RESIDENTIAL,
    PROVIDER_MASSIVE_ISP,
}
_KINDS = {KIND_RESIDENTIAL, KIND_ISP, KIND_MOBILE, KIND_DATACENTER}
_BULK_ACTIONS = {"test", "unassign", "enable", "disable", "retire"}


class ProxyImportRequest(BaseModel):
    """Bulk paste payload for the proxy inventory.

    Length is validated inside the handler so a FastAPI 422 response can never
    echo the pasted text (which may contain passwords).
    """
    text: str
    provider: str = PROVIDER_MANUAL
    kind: str = KIND_RESIDENTIAL
    default_country: Optional[str] = None


class ProxyPreviewRequest(BaseModel):
    """Preview a bulk paste without persisting anything."""
    text: str
    provider: str = PROVIDER_MANUAL
    kind: str = KIND_RESIDENTIAL
    default_country: Optional[str] = None


class ProxyAssignRequest(BaseModel):
    """Assign one proxy to one cloud LinkedIn profile."""
    profile_id: str = Field(min_length=1, max_length=128)


class ProxyUnassignRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=200)


class ProxyRotateRequest(BaseModel):
    """New manual-proxy password. Validated in the handler to avoid 422 echo."""
    password: str


class ProxyBulkRequest(BaseModel):
    """Apply one action to selected proxies or to a filtered set."""
    action: str
    proxy_ids: list[str] = Field(default_factory=list, max_length=1000)
    all: bool = False
    provider: Optional[str] = None
    country: Optional[str] = None
    status_filter: Optional[str] = Field(default=None, alias="status")
    assignment: Optional[str] = None
    identity_id: Optional[str] = None
    org_id: Optional[str] = None
    kind: Optional[str] = None
    search: Optional[str] = None


class ProxyUsageSyncRequest(BaseModel):
    from_date: Optional[str] = Field(default=None, max_length=32)
    to_date: Optional[str] = Field(default=None, max_length=32)


class ProxyFallbackRequest(BaseModel):
    profile_id: str = Field(min_length=1, max_length=128)


class MassiveProvisionRequest(BaseModel):
    profile_id: str = Field(min_length=1, max_length=128)


class MassiveAllocateRequest(BaseModel):
    bytes: int = Field(ge=1, le=1_000_000_000_000)


def _error(exc: ProxyError) -> HTTPException:
    code = status.HTTP_409_CONFLICT if isinstance(
        exc, (ProxyUnavailableError, ProxyReuseError)
    ) else status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=code, detail=str(exc))


def _require_rate_limit(admin_id: str, action: str) -> None:
    allowed, message = AdminActionRateLimiter.check(admin_id, action)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=message or "Rate limit reached",
        )
    AdminActionRateLimiter.record(admin_id, action)


def _audit(
    admin_id: str,
    action: str,
    *,
    target_user_id: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
) -> None:
    AdminSecurityPolicy.log_admin_action(
        admin_id,
        action,
        target_user_id=target_user_id,
        details=details or {},
    )


def _normalize_default_country(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        return normalize_country(value)
    except RegionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _validate_import_text(text: str) -> str:
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Paste at least one proxy")
    if len(text) > 2_000_000:
        raise HTTPException(status_code=413, detail="Import text is too large")
    return text


def _bulk_proxy_ids(body: ProxyBulkRequest) -> list[str]:
    if body.proxy_ids:
        return body.proxy_ids
    if not body.all:
        return []
    proxies, _ = list_proxies(
        status=body.status_filter,
        country=body.country,
        provider=body.provider,
        kind=body.kind,
        assignment=body.assignment,
        identity_id=body.identity_id,
        org_id=body.org_id,
        search=body.search,
        skip=0,
        limit=500,
    )
    return [proxy._id for proxy in proxies]


@router.get("", dependencies=[Depends(get_admin_user)])
async def list_proxy_inventory(
    status_filter: Optional[str] = Query(None, alias="status"),
    country: Optional[str] = Query(None),
    provider: Optional[str] = Query(None),
    kind: Optional[str] = Query(None),
    assignment: Optional[str] = Query(None, pattern="^(assigned|unassigned)$"),
    identity_id: Optional[str] = Query(None),
    org_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None, max_length=200),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    """List proxies without exposing passwords."""
    try:
        proxies, total = list_proxies(
            status=status_filter,
            country=country,
            provider=provider,
            kind=kind,
            assignment=assignment,
            identity_id=identity_id,
            org_id=org_id,
            search=search,
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


@router.get("/stats", dependencies=[Depends(get_admin_user)])
async def proxy_inventory_stats() -> dict:
    """Return counts by status, provider, and country."""
    try:
        return get_proxy_stats()
    except ProxyError as exc:
        raise _error(exc)


@router.post("/parse", dependencies=[Depends(get_admin_user)])
async def parse_proxy_inventory(body: ProxyPreviewRequest) -> dict:
    """Preview a bulk paste with masked credentials and per-line errors."""
    text = _validate_import_text(body.text)
    default_country = _normalize_default_country(body.default_country)
    provider = body.provider.strip().lower()
    kind = body.kind.strip().lower()
    if provider not in _PROVIDERS:
        raise HTTPException(status_code=400, detail="Invalid proxy provider")
    if kind not in _KINDS:
        raise HTTPException(status_code=400, detail="Invalid proxy kind")
    try:
        return preview_proxies(
            text,
            provider=provider,
            kind=kind,
            default_country=default_country,
        )
    except ProxyError as exc:
        raise _error(exc)


@router.post("/import", dependencies=[Depends(get_admin_user)])
async def import_proxy_inventory(
    body: ProxyImportRequest,
    current_admin: str = Depends(get_admin_user),
) -> dict:
    """Bulk import pasted proxies. Passwords are encrypted and never returned."""
    _require_rate_limit(current_admin, "proxy_import")
    text = _validate_import_text(body.text)
    provider = body.provider.strip().lower()
    kind = body.kind.strip().lower()
    if provider not in _PROVIDERS:
        raise HTTPException(status_code=400, detail="Invalid proxy provider")
    if kind not in _KINDS:
        raise HTTPException(status_code=400, detail="Invalid proxy kind")
    default_country = _normalize_default_country(body.default_country)

    try:
        result = import_proxies(
            text,
            provider=provider,
            kind=kind,
            default_country=default_country,
            created_by=current_admin,
        )
    except ProxyError as exc:
        raise _error(exc)

    _audit(
        current_admin,
        "proxy.import",
        details={
            "created": result["created"],
            "skipped": result["skipped"],
            "failed": result["failed"],
            "provider": provider,
            "kind": kind,
        },
    )
    return result


@router.get("/export", dependencies=[Depends(get_admin_user)])
async def export_proxy_inventory(
    status_filter: Optional[str] = Query(None, alias="status"),
    country: Optional[str] = Query(None),
    provider: Optional[str] = Query(None),
    kind: Optional[str] = Query(None),
    assignment: Optional[str] = Query(None, pattern="^(assigned|unassigned)$"),
    identity_id: Optional[str] = Query(None),
    org_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None, max_length=200),
    current_admin: str = Depends(get_admin_user),
) -> Response:
    """Export a masked CSV. Passwords and Massive keys never appear."""
    try:
        csv_text = export_proxies_csv(
            status=status_filter,
            country=country,
            provider=provider,
            kind=kind,
            assignment=assignment,
            identity_id=identity_id,
            org_id=org_id,
            search=search,
        )
    except ProxyError as exc:
        raise _error(exc)
    _audit(
        current_admin,
        "proxy.export",
        details={"status": status_filter, "provider": provider, "country": country},
    )
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="proxies-export.csv"'},
    )


@router.get("/cloud-profiles", dependencies=[Depends(get_admin_user)])
async def list_cloud_profiles(
    search: Optional[str] = Query(None, max_length=200),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    """List cloud profiles for the assignment picker. No credentials returned."""
    profiles = get_mongodb_collection("linkedin_profiles")
    if profiles is None:
        raise HTTPException(status_code=503, detail="LinkedIn profiles are unavailable")
    query: dict[str, Any] = {"execution_mode": "cloud"}
    if search:
        query["linkedin_username"] = {"$regex": re.escape(search.strip()), "$options": "i"}
    docs = list(profiles.find(query).sort("created_at", -1).limit(limit))
    user_ids = [doc.get("user_id") for doc in docs if doc.get("user_id")]
    emails: dict[str, str] = {}
    users = get_mongodb_collection("users")
    if users is not None and user_ids:
        for user in users.find({"_id": {"$in": user_ids}}, {"email": 1}):
            emails[str(user.get("_id"))] = str(user.get("email") or "")
    return {
        "profiles": [
            {
                "id": str(doc.get("_id")),
                "username": doc.get("linkedin_username") or doc.get("username"),
                "user_id": doc.get("user_id"),
                "email": emails.get(str(doc.get("user_id")), ""),
                "identity_id": doc.get("identity_id"),
                "org_id": doc.get("org_id"),
                "proxy_id": doc.get("proxy_id"),
                "proxy_mode": doc.get("proxy_mode", "none"),
                "has_proxy": bool(doc.get("proxy_server")),
                "is_active": bool(doc.get("is_active", True)),
            }
            for doc in docs
        ]
    }


@router.get("/assignments", dependencies=[Depends(get_admin_user)])
async def list_proxy_assignments(
    active: Optional[bool] = Query(None),
    proxy_id: Optional[str] = Query(None),
    profile_id: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    """List active and historical proxy assignments."""
    assignments, total = list_assignments(
        active=active,
        proxy_id=proxy_id,
        profile_id=profile_id,
        skip=skip,
        limit=limit,
    )
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "assignments": assignments,
    }


@router.get("/health", dependencies=[Depends(get_admin_user)])
async def list_proxy_health(
    proxy_id: Optional[str] = Query(None),
    only_failures: bool = Query(False),
    only_mismatch: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    """List recent health-check results, including country mismatches."""
    checks, total = list_health_checks(
        proxy_id=proxy_id,
        only_failures=only_failures,
        only_mismatch=only_mismatch,
        skip=skip,
        limit=limit,
    )
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "checks": checks,
    }


@router.get("/usage", dependencies=[Depends(get_admin_user)])
async def proxy_usage(
    period_start: Optional[str] = Query(None),
    period_end: Optional[str] = Query(None),
    limit: int = Query(1000, ge=1, le=5000),
) -> dict:
    """Internal usage per proxy, profile, and workspace. Admin only."""
    return get_usage_summary(
        period_start=period_start,
        period_end=period_end,
        limit=limit,
    )


@router.get("/massive/status", dependencies=[Depends(get_admin_user)])
async def massive_configuration_status() -> dict:
    """Show Massive configuration presence and alerts. No key values."""
    from openoutreach.proxies.provisioning import massive_admin_status

    return massive_admin_status()


@router.post("/sync-massive", dependencies=[Depends(get_admin_user)])
async def sync_massive_usage_endpoint(
    body: ProxyUsageSyncRequest,
    current_admin: str = Depends(get_admin_user),
) -> dict:
    """Sync Reporting API usage with group_by=subuser."""
    from openoutreach.proxies.massive_client import (
        default_usage_period,
        sync_massive_usage,
    )

    default_start, default_end = default_usage_period()
    from_date = body.from_date or default_start
    to_date = body.to_date or default_end
    try:
        result = await sync_massive_usage(from_date, to_date)
    except ProxyError as exc:
        raise _error(exc)
    _audit(
        current_admin,
        "proxy.usage_sync",
        details={
            "matched": result["matched"],
            "skipped": result["skipped"],
            "period_start": from_date,
            "period_end": to_date,
        },
    )
    return result


@router.post("/test", dependencies=[Depends(get_admin_user)])
async def test_selected_proxies(
    body: ProxyBulkRequest,
    current_admin: str = Depends(get_admin_user),
) -> dict:
    """Test selected proxies or every non-retired proxy."""
    _require_rate_limit(current_admin, "proxy_test")
    if body.action != "test":
        raise HTTPException(status_code=400, detail="This endpoint only accepts action=test")
    ids = _bulk_proxy_ids(body)
    try:
        result = await run_health_checks(ids or None, include_all=body.all)
    except ProxyError as exc:
        raise _error(exc)
    _audit(
        current_admin,
        "proxy.test",
        details={
            "bulk": True,
            "tested": result["tested"],
            "passed": result["passed"],
            "failed": result["failed"],
            "proxy_ids": [item["proxy_id"] for item in result["results"]],
        },
    )
    return result


@router.post("/bulk", dependencies=[Depends(get_admin_user)])
async def bulk_proxy_action(
    body: ProxyBulkRequest,
    current_admin: str = Depends(get_admin_user),
) -> dict:
    """Run test/unassign/enable/disable/retire on selected or filtered proxies."""
    action = body.action.strip().lower()
    if action not in _BULK_ACTIONS:
        raise HTTPException(status_code=400, detail="Invalid bulk action")
    if action == "test":
        _require_rate_limit(current_admin, "proxy_test")
        ids = _bulk_proxy_ids(body)
        try:
            result = await run_health_checks(ids or None, include_all=body.all)
        except ProxyError as exc:
            raise _error(exc)
        _audit(
            current_admin,
            "proxy.test",
            details={
                "bulk": True,
                "tested": result["tested"],
                "passed": result["passed"],
                "failed": result["failed"],
                "proxy_ids": [item["proxy_id"] for item in result["results"]],
            },
        )
        return result

    ids = _bulk_proxy_ids(body)
    if not ids:
        raise HTTPException(status_code=400, detail="Select at least one proxy")

    results: list[dict[str, Any]] = []
    for proxy_id in ids:
        try:
            if action == "unassign":
                proxy = unassign_proxy(proxy_id, reason="bulk_unassign", actor=current_admin)
            elif action == "enable":
                proxy = enable_proxy(proxy_id)
            elif action == "disable":
                proxy = disable_proxy(proxy_id)
            else:
                proxy = retire_proxy(proxy_id, reason="bulk_retire")
            results.append({"proxy_id": proxy_id, "ok": True, "status": proxy.status})
        except ProxyError as exc:
            results.append({"proxy_id": proxy_id, "ok": False, "error": str(exc)})

    processed = sum(1 for item in results if item["ok"])
    failed = len(results) - processed
    _audit(
        current_admin,
        f"proxy.{action}",
        details={
            "bulk": True,
            "processed": processed,
            "failed": failed,
            "proxy_ids": ids,
        },
    )
    return {
        "action": action,
        "processed": processed,
        "failed": failed,
        "results": results,
    }


@router.post("/provision-fallback", dependencies=[Depends(get_admin_user)])
async def provision_fallback_proxy(
    body: ProxyFallbackRequest,
    current_admin: str = Depends(get_admin_user),
) -> dict:
    """Create and assign a Massive fallback proxy for one cloud profile."""
    from openoutreach.proxies.massive_client import provision_massive_fallback

    profiles = get_mongodb_collection("linkedin_profiles")
    if profiles is None:
        raise HTTPException(status_code=503, detail="LinkedIn profiles are unavailable")
    profile = profiles.find_one({"_id": body.profile_id})
    if not profile:
        raise HTTPException(status_code=404, detail="LinkedIn profile not found")
    if profile.get("execution_mode") != "cloud":
        raise HTTPException(status_code=400, detail="Only cloud profiles use managed proxies")
    if profile.get("proxy_server"):
        raise HTTPException(status_code=409, detail="This profile already has a proxy")
    country = profile.get("proxy_region_country")
    if not country:
        raise HTTPException(status_code=400, detail="Profile has no proxy region")
    user_id = str(profile.get("user_id") or "")
    if not user_id:
        raise HTTPException(status_code=400, detail="Profile has no workspace owner")
    try:
        fallback = provision_massive_fallback(
            body.profile_id,
            country,
            profile.get("proxy_region_subdivision"),
            profile.get("proxy_region_city"),
            created_by=current_admin,
        )
    except ProxyError as exc:
        raise _error(exc)
    try:
        proxy = assign_proxy_to_profile(
            fallback._id,
            body.profile_id,
            user_id,
            assigned_by=current_admin,
        )
    except ProxyError as exc:
        retire_proxy(fallback._id, reason="fallback_assignment_failed")
        raise _error(exc)
    _audit(
        current_admin,
        "proxy.assign",
        target_user_id=user_id,
        details={
            "proxy_id": proxy._id,
            "profile_id": body.profile_id,
            "provider": proxy.provider,
            "fallback": True,
        },
    )
    return {"proxy": proxy.public_dict(), "profile_id": body.profile_id}


@router.get("/massive/accounts", dependencies=[Depends(get_admin_user)])
async def massive_accounts() -> dict:
    """List Reseller sub-accounts with local profile/org context."""
    from openoutreach.proxies.provisioning import (
        list_massive_subaccounts,
        reseller_status,
    )

    accounts = list_massive_subaccounts()
    return {
        "configured": reseller_status().get("configured", False),
        "accounts": accounts,
        "parent_usage": {
            "accounts": len(accounts),
            "used_bytes": sum(int(row.get("used_bytes") or 0) for row in accounts),
            "limit_bytes": sum(int(row.get("limit_bytes") or 0) for row in accounts),
            "limit_reached": sum(1 for row in accounts if row.get("limit_reached")),
            "proxy_access_revoked": sum(
                1 for row in accounts if row.get("proxy_access") is False
            ),
        },
    }


@router.get("/massive/alerts", dependencies=[Depends(get_admin_user)])
async def massive_internal_alerts() -> dict:
    """Internal alerts: limit, proxy access, country mismatch, failures."""
    from openoutreach.proxies.provisioning import massive_alerts

    return {"alerts": massive_alerts()}


@router.post("/massive/sync", dependencies=[Depends(get_admin_user)])
async def sync_massive_reseller(
    body: ProxyUsageSyncRequest,
    current_admin: str = Depends(get_admin_user),
) -> dict:
    """Sync cumulative sub-account usage and enforce internal budgets."""
    _require_rate_limit(current_admin, "proxy_massive_sync")
    from openoutreach.proxies.massive_client import default_usage_period
    from openoutreach.proxies.provisioning import (
        sync_massive_accounts,
        sync_massive_reporting,
    )

    try:
        result = sync_massive_accounts(actor_user_id=current_admin)
        default_start, default_end = default_usage_period()
        try:
            result["reporting"] = sync_massive_reporting(
                body.from_date or default_start,
                body.to_date or default_end,
                actor_user_id=current_admin,
            )
        except ProxyError as exc:
            # Cumulative sync and budgets already succeeded; reporting is a
            # separate provider surface and may be disabled independently.
            result["reporting_error"] = type(exc).__name__
    except ProxyError as exc:
        raise _error(exc)
    _audit(
        current_admin,
        "proxy.massive_sync",
        details={
            "accounts": result.get("accounts"),
            "matched": result.get("matched"),
            "unmatched": result.get("unmatched"),
            "budget": result.get("budget"),
        },
    )
    return result


@router.post("/massive/provision", dependencies=[Depends(get_admin_user)])
async def provision_massive_subaccount(
    body: MassiveProvisionRequest,
    current_admin: str = Depends(get_admin_user),
) -> dict:
    """Provision a Reseller sub-account for one cloud profile."""
    _require_rate_limit(current_admin, "proxy_massive_provision")
    profiles = get_mongodb_collection("linkedin_profiles")
    if profiles is None:
        raise HTTPException(status_code=503, detail="LinkedIn profiles are unavailable")
    profile = profiles.find_one({"_id": body.profile_id})
    if not profile:
        raise HTTPException(status_code=404, detail="LinkedIn profile not found")
    if profile.get("execution_mode") != "cloud":
        raise HTTPException(status_code=400, detail="Only cloud profiles use managed proxies")
    if profile.get("proxy_server") or profile.get("proxy_id"):
        raise HTTPException(status_code=409, detail="This profile already has a proxy")
    country = profile.get("proxy_region_country")
    if not country:
        raise HTTPException(status_code=400, detail="Profile has no proxy region")
    user_id = str(profile.get("user_id") or "")
    if not user_id:
        raise HTTPException(status_code=400, detail="Profile has no workspace owner")
    from openoutreach.proxies.provisioning import (
        provision_reseller_proxy,
        validate_city_pool,
    )

    try:
        validate_city_pool(country, profile.get("proxy_region_city"))
        proxy = provision_reseller_proxy(
            body.profile_id,
            user_id,
            profile.get("org_id"),
            country,
            profile.get("proxy_region_subdivision"),
            profile.get("proxy_region_city"),
            created_by=current_admin,
        )
    except ProxyError as exc:
        raise _error(exc)
    _audit(
        current_admin,
        "proxy.provision",
        target_user_id=user_id,
        details={
            "proxy_id": proxy._id,
            "profile_id": body.profile_id,
            "massive_account_id": proxy.massive_account_id,
        },
    )
    return {"proxy": proxy.public_dict(), "profile_id": body.profile_id}


@router.post("/massive/{proxy_id}/disable", dependencies=[Depends(get_admin_user)])
async def disable_massive_subaccount(
    proxy_id: str,
    current_admin: str = Depends(get_admin_user),
) -> dict:
    from openoutreach.proxies.models import Proxy
    from openoutreach.proxies.provisioning import disable_massive_proxy

    proxy = Proxy.get(proxy_id)
    if proxy is None:
        raise HTTPException(status_code=404, detail="Proxy not found")
    if not proxy.massive_account_id:
        raise HTTPException(status_code=400, detail="Not a Reseller sub-account")
    if not disable_massive_proxy(
        proxy, reason="admin_disable", actor_user_id=current_admin
    ):
        raise HTTPException(status_code=409, detail="Massive disable failed")
    _audit(
        current_admin,
        "proxy.massive_disable",
        target_user_id=proxy.assigned_user_id,
        details={"proxy_id": proxy_id, "massive_account_id": proxy.massive_account_id},
    )
    return {"proxy": proxy.public_dict()}


@router.post("/massive/{proxy_id}/enable", dependencies=[Depends(get_admin_user)])
async def enable_massive_subaccount(
    proxy_id: str,
    current_admin: str = Depends(get_admin_user),
) -> dict:
    from openoutreach.proxies.models import Proxy
    from openoutreach.proxies.provisioning import enable_massive_proxy

    proxy = Proxy.get(proxy_id)
    if proxy is None:
        raise HTTPException(status_code=404, detail="Proxy not found")
    if not proxy.massive_account_id:
        raise HTTPException(status_code=400, detail="Not a Reseller sub-account")
    if not enable_massive_proxy(
        proxy, reason="admin_enable", actor_user_id=current_admin
    ):
        raise HTTPException(status_code=409, detail="Massive enable failed")
    _audit(
        current_admin,
        "proxy.massive_enable",
        target_user_id=proxy.assigned_user_id,
        details={"proxy_id": proxy_id, "massive_account_id": proxy.massive_account_id},
    )
    return {"proxy": proxy.public_dict()}


@router.post("/massive/{proxy_id}/rotate", dependencies=[Depends(get_admin_user)])
async def rotate_massive_subaccount(
    proxy_id: str,
    current_admin: str = Depends(get_admin_user),
) -> dict:
    """Rotate the provider password; the new secret is never returned."""
    _require_rate_limit(current_admin, "proxy_massive_rotate")
    from openoutreach.proxies.models import Proxy
    from openoutreach.proxies.provisioning import rotate_massive_password

    proxy = Proxy.get(proxy_id)
    if proxy is None:
        raise HTTPException(status_code=404, detail="Proxy not found")
    try:
        proxy = rotate_massive_password(proxy, actor_user_id=current_admin)
    except ProxyError as exc:
        raise _error(exc)
    _audit(
        current_admin,
        "proxy.massive_rotate",
        target_user_id=proxy.assigned_user_id,
        details={"proxy_id": proxy_id, "massive_account_id": proxy.massive_account_id},
    )
    return {"proxy": proxy.public_dict()}


@router.post("/massive/{proxy_id}/allocate", dependencies=[Depends(get_admin_user)])
async def allocate_massive_traffic(
    proxy_id: str,
    body: MassiveAllocateRequest,
    current_admin: str = Depends(get_admin_user),
) -> dict:
    """Top up the sub-account's cumulative lifetime allowance."""
    _require_rate_limit(current_admin, "proxy_massive_allocate")
    from openoutreach.proxies.massive_reseller import (
        MassiveResellerClient,
        MassiveResellerConfig,
    )
    from openoutreach.proxies.models import Proxy

    proxy = Proxy.get(proxy_id)
    if proxy is None:
        raise HTTPException(status_code=404, detail="Proxy not found")
    if not proxy.massive_account_id:
        raise HTTPException(status_code=400, detail="Not a Reseller sub-account")
    config = MassiveResellerConfig.from_settings()
    if config is None:
        raise HTTPException(status_code=503, detail="Massive Reseller is not configured")
    try:
        account = MassiveResellerClient(config).allocate_traffic(
            proxy.massive_account_id, body.bytes
        )
    except ProxyError as exc:
        raise _error(exc)
    proxies = get_mongodb_collection("proxies")
    if proxies is not None:
        new_limit = account.get("limit_bytes") or (
            (proxy.massive_limit_bytes or 0) + body.bytes
        )
        proxies.update_one(
            {"_id": proxy_id},
            {
                "$set": {
                    "massive_limit_bytes": new_limit,
                    "traffic_limit_bytes": new_limit,
                    "massive_last_sync_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
    _audit(
        current_admin,
        "proxy.massive_allocate",
        target_user_id=proxy.assigned_user_id,
        details={"proxy_id": proxy_id, "bytes": body.bytes},
    )
    return {"proxy": Proxy.get(proxy_id).public_dict()}  # type: ignore[union-attr]


@router.get("/pool-stats", dependencies=[Depends(get_admin_user)])
async def massive_pool_stats(country: Optional[str] = Query(None, max_length=2)) -> dict:
    """Cached country/city node counts and region warnings."""
    from openoutreach.proxies.provisioning import pool_stats_summary

    return pool_stats_summary(country)


@router.get("/pool-stats/regions", dependencies=[Depends(get_admin_user)])
async def massive_pool_stats_regions() -> dict:
    from openoutreach.proxies.provisioning import pool_stats_client

    client = pool_stats_client()
    if client is None:
        raise HTTPException(status_code=503, detail="Massive Pool Stats is not configured")
    try:
        return {"regions": client.regions()}
    except ProxyError as exc:
        raise _error(exc)


@router.post("/{proxy_id}/test", dependencies=[Depends(get_admin_user)])
async def test_proxy_inventory(
    proxy_id: str,
    current_admin: str = Depends(get_admin_user),
) -> dict:
    """Test a proxy and persist its egress IP, country, and latency."""
    _require_rate_limit(current_admin, "proxy_test")
    try:
        result = await test_proxy(proxy_id)
    except ProxyError as exc:
        raise _error(exc)
    _audit(
        current_admin,
        "proxy.test",
        details={
            "proxy_id": proxy_id,
            "success": bool(result.get("success")),
            "country_match": result.get("country_match"),
        },
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
    current_proxy_id = profile.get("proxy_id")
    if profile.get("proxy_server") and not current_proxy_id:
        raise HTTPException(
            status_code=409,
            detail="This profile already has a BYO proxy",
        )
    if current_proxy_id and current_proxy_id != proxy_id:
        raise HTTPException(
            status_code=409,
            detail="This profile already has a different proxy",
        )

    try:
        proxy = assign_proxy_to_profile(
            proxy_id,
            body.profile_id,
            str(profile.get("user_id") or ""),
            assigned_by=current_admin,
        )
    except ProxyError as exc:
        raise _error(exc)

    _audit(
        current_admin,
        "proxy.assign",
        target_user_id=profile.get("user_id"),
        details={"proxy_id": proxy_id, "profile_id": body.profile_id},
    )
    return {"proxy": proxy.public_dict(), "profile_id": body.profile_id}


@router.post("/{proxy_id}/unassign", dependencies=[Depends(get_admin_user)])
async def unassign_proxy_inventory(
    proxy_id: str,
    body: ProxyUnassignRequest,
    current_admin: str = Depends(get_admin_user),
) -> dict:
    """Unassign a proxy and pause its profile. The proxy is not recycled."""
    try:
        proxy = unassign_proxy(proxy_id, reason=body.reason, actor=current_admin)
    except ProxyError as exc:
        raise _error(exc)
    _audit(
        current_admin,
        "proxy.unassign",
        target_user_id=proxy.last_assigned_user_id,
        details={
            "proxy_id": proxy_id,
            "profile_id": proxy.last_assigned_profile_id,
            "reason": body.reason,
        },
    )
    return {"proxy": proxy.public_dict()}


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
    _audit(current_admin, "proxy.disable", details={"proxy_id": proxy_id})
    return {"proxy": proxy.public_dict()}


@router.post("/{proxy_id}/enable", dependencies=[Depends(get_admin_user)])
async def enable_proxy_inventory(
    proxy_id: str,
    current_admin: str = Depends(get_admin_user),
) -> dict:
    """Re-enable an unassigned proxy."""
    try:
        proxy = enable_proxy(proxy_id)
    except ProxyError as exc:
        raise _error(exc)
    _audit(current_admin, "proxy.enable", details={"proxy_id": proxy_id})
    return {"proxy": proxy.public_dict()}


@router.post("/{proxy_id}/retire", dependencies=[Depends(get_admin_user)])
async def retire_proxy_inventory(
    proxy_id: str,
    current_admin: str = Depends(get_admin_user),
) -> dict:
    """Retire an unassigned proxy. The record is kept for audit."""
    try:
        proxy = retire_proxy(proxy_id, reason="admin_retired")
    except ProxyError as exc:
        raise _error(exc)
    _audit(current_admin, "proxy.retire", details={"proxy_id": proxy_id})
    return {"proxy": proxy.public_dict()}


@router.post("/{proxy_id}/rotate", dependencies=[Depends(get_admin_user)])
async def rotate_proxy_credentials(
    proxy_id: str,
    body: ProxyRotateRequest,
    current_admin: str = Depends(get_admin_user),
) -> dict:
    """Rotate a manual proxy password. The new password is never returned."""
    if len(body.password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Proxy password must be at least 8 characters",
        )
    if len(body.password) > 512:
        raise HTTPException(status_code=400, detail="Proxy password is too long")
    try:
        proxy = rotate_proxy_password(proxy_id, body.password)
    except ProxyError as exc:
        raise _error(exc)
    _audit(current_admin, "proxy.rotate", details={"proxy_id": proxy_id})
    return {"proxy": proxy.public_dict()}


@router.get("/{proxy_id}/health", dependencies=[Depends(get_admin_user)])
async def proxy_health_history(
    proxy_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    """Return health-check history for one proxy."""
    checks, total = list_health_checks(
        proxy_id=proxy_id,
        skip=skip,
        limit=limit,
    )
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "checks": checks,
    }
