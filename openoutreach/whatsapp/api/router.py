import base64
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from openoutreach.api_v2.dependencies_v2 import get_current_user
from openoutreach.billing.cloud_seats import (
    release_cloud_seat,
    reserve_cloud_seat,
    whatsapp_consumes_cloud_seat,
)
from openoutreach.config import settings
from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.organizations.access import (
    can_access_channel_doc,
    channel_access_query,
    resolve_org_context,
)
from openoutreach.organizations.enforcement import resolve_effective_plan
from openoutreach.proxies.models import Proxy
from openoutreach.proxies.region import normalize_region
from openoutreach.whatsapp.cloud import (
    WhatsAppCloudError,
    identity_has_duo_whatsapp,
    new_whatsapp_identity,
    resolve_duo_linkedin,
    resolve_duo_share,
    whatsapp_cloud_enabled,
)
from openoutreach.whatsapp.models.profile import (
    STATUS_CONNECTED,
    STATUS_DISCONNECTED,
    WhatsAppProfile,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────────

class WhatsAppProfileCreate(BaseModel):
    display_name: Optional[str] = None
    execution_mode: str = "desktop"
    # Cloud variants: duo_shared (share the LinkedIn proxy), duo_separate
    # (own proxy, same seat), whatsapp_only (own seat + proxy).
    cloud_mode: Optional[str] = None
    duo_linkedin_profile_id: Optional[str] = None
    proxy_region_country: Optional[str] = None
    proxy_region_subdivision: Optional[str] = None
    proxy_region_city: Optional[str] = None


class WhatsAppProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    status: Optional[str] = None


def _serialize(profile: WhatsAppProfile) -> Dict[str, Any]:
    qr_data_url = None
    if profile.qr_png_b64 and profile.status == STATUS_DISCONNECTED:
        qr_data_url = f"data:image/png;base64,{profile.qr_png_b64}"
    proxy_health: Dict[str, Any] = {}
    if profile.proxy_id:
        proxy = Proxy.get(profile.proxy_id)
        if proxy is not None:
            proxy_health = {
                "proxyStatus": proxy.status,
                "proxyMassiveStatus": proxy.massive_status,
                "proxyLastTestedAt": (
                    proxy.last_tested_at.isoformat()
                    if proxy.last_tested_at
                    else None
                ),
                "proxyLastTestCountry": proxy.last_test_country,
                "proxyCountryMismatch": proxy.country_mismatch,
                "proxyLastError": proxy.last_error,
            }
    return {
        "id": profile._id,
        "userId": profile.user_id,
        "orgId": profile.org_id,
        "assignedUserId": profile.assigned_user_id,
        "executionMode": profile.execution_mode,
        "cloudMode": profile.cloud_mode,
        "proxyMode": profile.proxy_mode,
        "proxyId": profile.proxy_id,
        "proxyRegionCountry": profile.proxy_region_country,
        "proxyRegionSubdivision": profile.proxy_region_subdivision,
        "proxyRegionCity": profile.proxy_region_city,
        "active": profile.active,
        "isActive": profile.is_active,
        "phoneNumber": profile.phone_number,
        "displayName": profile.display_name,
        "status": profile.status,
        "lastSeen": profile.last_seen.isoformat() if profile.last_seen else None,
        "createdAt": profile.created_at.isoformat() if profile.created_at else None,
        "qrDataUrl": qr_data_url,
        **proxy_health,
    }


def _authorized_profile(profile_id: str, user_id: str) -> WhatsAppProfile:
    from openoutreach.mongodb.models_user import User

    user = User.get(user_id)
    profile = WhatsAppProfile.get(profile_id)
    if user is None or profile is None:
        raise HTTPException(status_code=404, detail="WhatsApp profile not found")
    if not can_access_channel_doc(user, profile.to_dict()):
        raise HTTPException(status_code=404, detail="WhatsApp profile not found")
    return profile


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/profiles", response_model=List[Dict[str, Any]])
async def list_profiles(user_id: str = Depends(get_current_user)):
    from openoutreach.mongodb.models_user import User

    user = User.get(user_id)
    collection = get_mongodb_collection("whatsapp_profiles")
    if user is None or collection is None:
        return []
    profiles = [
        WhatsAppProfile.from_dict(doc)
        for doc in collection.find(channel_access_query(user))
    ]
    return [_serialize(p) for p in profiles]


@router.post("/profiles", response_model=Dict[str, Any], status_code=201)
async def create_profile(
    body: WhatsAppProfileCreate,
    user_id: str = Depends(get_current_user),
):
    from openoutreach.mongodb.models_user import User

    user = User.get(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    ctx = resolve_org_context(user)
    effective = resolve_effective_plan(user)

    execution_mode = (body.execution_mode or "desktop").strip().lower()
    if execution_mode not in {"desktop", "cloud"}:
        raise HTTPException(
            status_code=400,
            detail="execution_mode must be 'desktop' or 'cloud'",
        )

    cloud_mode = (body.cloud_mode or "").strip().lower()
    if execution_mode == "desktop":
        cloud_mode = "desktop"
    else:
        if not cloud_mode:
            cloud_mode = (
                "duo_shared" if body.duo_linkedin_profile_id else "whatsapp_only"
            )
        if cloud_mode not in {"duo_shared", "duo_separate", "whatsapp_only"}:
            raise HTTPException(
                status_code=400,
                detail=(
                    "cloud_mode must be 'duo_shared', 'duo_separate', or "
                    "'whatsapp_only'"
                ),
            )

    duo_proxy = None
    identity: Optional[str] = None
    region: Optional[tuple[str, Optional[str], Optional[str]]] = None
    seat_reserved = False
    assigned_user_id = user_id

    if execution_mode == "cloud":
        if not whatsapp_cloud_enabled():
            raise HTTPException(
                status_code=403,
                detail="WhatsApp cloud proxy is not enabled yet",
            )
        if not getattr(settings, "CLOUD_SEATS_ENABLED", True):
            raise HTTPException(
                status_code=403,
                detail="Cloud seats are disabled",
            )
        if not getattr(settings, "MANAGED_PROXIES_ENABLED", True):
            raise HTTPException(
                status_code=409,
                detail="Managed proxy provisioning is disabled",
            )
        if effective.cloud_seat_limit <= 0:
            raise HTTPException(
                status_code=402,
                detail="Cloud WhatsApp requires a Cloud seat",
            )
        if not effective.is_active:
            raise HTTPException(
                status_code=402,
                detail="Subscription is not active",
            )

        if cloud_mode in {"duo_shared", "duo_separate"}:
            if not body.duo_linkedin_profile_id:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Select the cloud LinkedIn profile this WhatsApp number "
                        "belongs to"
                    ),
                )
            try:
                if cloud_mode == "duo_shared":
                    duo_linkedin_doc, duo_proxy, identity = resolve_duo_share(
                        user, ctx.org_id, body.duo_linkedin_profile_id
                    )
                    assigned_user_id = str(
                        duo_linkedin_doc.get("assigned_user_id") or user_id
                    )
                    region = (
                        duo_proxy.country,
                        duo_proxy.subdivision,
                        duo_proxy.city,
                    )
                else:
                    linkedin_doc, identity = resolve_duo_linkedin(
                        user, ctx.org_id, body.duo_linkedin_profile_id
                    )
                    assigned_user_id = str(
                        linkedin_doc.get("assigned_user_id") or user_id
                    )
                    linkedin_proxy = Proxy.get(
                        str(linkedin_doc.get("proxy_id") or "")
                    )
                    if linkedin_proxy is None:
                        raise WhatsAppCloudError(
                            "The LinkedIn profile has no managed proxy yet"
                        )
                    region = normalize_region(
                        body.proxy_region_country or linkedin_proxy.country,
                        body.proxy_region_subdivision
                        or linkedin_proxy.subdivision,
                        body.proxy_region_city or linkedin_proxy.city,
                    )
            except WhatsAppCloudError as exc:
                raise HTTPException(status_code=409, detail=str(exc))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            if identity_has_duo_whatsapp(ctx.org_id, identity):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "This cloud seat already has a WhatsApp number; one "
                        "WhatsApp per Duo seat"
                    ),
                )
        else:
            if ctx.team_enabled and ctx.is_shared and ctx.role == "member":
                raise HTTPException(
                    status_code=403,
                    detail=(
                        "Ask a workspace owner or admin to assign a cloud seat. "
                        "Members can use a Duo on a LinkedIn profile assigned to "
                        "them or create desktop profiles."
                    ),
                )
            try:
                region = normalize_region(
                    body.proxy_region_country,
                    body.proxy_region_subdivision,
                    body.proxy_region_city,
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            identity = new_whatsapp_identity()
            reserved, seat_error = reserve_cloud_seat(
                user_id, effective.cloud_seat_limit
            )
            if not reserved:
                raise HTTPException(
                    status_code=402,
                    detail=seat_error or "Cloud seat limit reached",
                )
            seat_reserved = True

    coll = get_mongodb_collection("whatsapp_profiles")
    if execution_mode == "desktop":
        # Desktop WhatsApp keeps the existing plan limit. Cloud numbers are
        # counted by the unified cloud seat pool instead.
        desktop_filter = {
            "$or": [
                {"execution_mode": "desktop"},
                {"execution_mode": {"$exists": False}},
            ]
        }
        current_count = (
            coll.count_documents(
                {
                    "$and": [
                        {
                            "$or": [
                                {"org_id": ctx.org_id},
                                {"org_id": {"$exists": False}, "user_id": user_id},
                                {"org_id": None, "user_id": user_id},
                            ]
                        },
                        desktop_filter,
                    ],
                    "status": "connected",
                }
            )
            if coll is not None
            else 0
        )
        if current_count >= effective.whatsapp_account_limit:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"WhatsApp account limit reached "
                    f"({current_count}/{effective.whatsapp_account_limit}). "
                    "Upgrade your plan or ask a workspace owner to add capacity."
                ),
            )

    profile = WhatsAppProfile(
        # The workspace owner is the accounting/data owner; the creator keeps
        # the assignment so members see only their own numbers.
        user_id=ctx.accounting_owner_id,
        org_id=ctx.org_id,
        assigned_user_id=assigned_user_id,
        execution_mode=execution_mode,
        cloud_mode=cloud_mode,
        identity_id=identity,
        active=True,
        is_active=True,
        display_name=body.display_name,
        status=STATUS_DISCONNECTED,
    )

    try:
        profile.save()
        if execution_mode == "cloud":
            if cloud_mode == "duo_shared":
                from openoutreach.proxies.service import (
                    attach_shared_proxy_to_whatsapp,
                )

                if duo_proxy is None or identity is None:
                    raise WhatsAppCloudError(
                        "Cloud Duo proxy or identity is unavailable"
                    )
                attach_shared_proxy_to_whatsapp(
                    duo_proxy._id,
                    profile._id,
                    ctx.accounting_owner_id,
                    identity_id=identity,
                    org_id=ctx.org_id,
                    assigned_by=user_id,
                )
            else:
                from openoutreach.proxies.provisioning import (
                    provision_managed_proxy,
                )

                if region is None or identity is None:
                    raise WhatsAppCloudError(
                        "Cloud WhatsApp region or identity is unavailable"
                    )
                managed_proxy = provision_managed_proxy(
                    profile._id,
                    ctx.accounting_owner_id,
                    ctx.org_id,
                    region[0],
                    region[1],
                    region[2],
                    created_by=user_id,
                    channel="whatsapp",
                )
                # Best-effort egress check; a provider hiccup must not undo a
                # successfully created number. Admins can retest from the
                # proxy health page.
                try:
                    from openoutreach.proxies.service import test_proxy

                    await test_proxy(managed_proxy._id)
                except Exception as exc:  # pragma: no cover - network/provider
                    logger.warning(
                        "whatsapp_managed_proxy_egress_test_failed profile_id=%s exception_type=%s",
                        profile._id,
                        type(exc).__name__,
                    )
    except Exception as exc:
        WhatsAppProfile.delete(profile._id)
        if seat_reserved:
            release_cloud_seat(user_id)
        from openoutreach.proxies import ProxyError

        if execution_mode != "cloud":
            logger.error(
                "whatsapp_profile_create_failed profile_id=%s exception_type=%s",
                profile._id,
                type(exc).__name__,
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to create WhatsApp connection",
            )
        if isinstance(exc, (ProxyError, WhatsAppCloudError)):
            raise HTTPException(status_code=409, detail=str(exc))
        logger.warning(
            "whatsapp_cloud_provision_failed profile_id=%s exception_type=%s",
            profile._id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=409,
            detail="Could not provision a managed proxy for this WhatsApp number",
        )

    refreshed = WhatsAppProfile.get(profile._id) or profile
    return _serialize(refreshed)


@router.get("/profiles/{profile_id}", response_model=Dict[str, Any])
async def get_profile(
    profile_id: str,
    user_id: str = Depends(get_current_user),
):
    profile = _authorized_profile(profile_id, user_id)
    return _serialize(profile)


@router.patch("/profiles/{profile_id}", response_model=Dict[str, Any])
async def update_profile(
    profile_id: str,
    body: WhatsAppProfileUpdate,
    user_id: str = Depends(get_current_user),
):
    profile = _authorized_profile(profile_id, user_id)
    # Connection state is owned by the desktop daemon after a successful QR
    # authentication.  Never allow a client to spoof it and bypass campaign
    # readiness checks.
    if body.status is not None:
        raise HTTPException(status_code=400, detail="WhatsApp connection status is read-only")
    update_fields = []
    if body.display_name is not None:
        profile.display_name = body.display_name
        update_fields.append("display_name")
    if update_fields:
        profile.save(update_fields=update_fields)
    return _serialize(profile)


@router.delete("/profiles/{profile_id}", status_code=204)
async def delete_profile(
    profile_id: str,
    user_id: str = Depends(get_current_user),
):
    profile = _authorized_profile(profile_id, user_id)
    release_seat = False
    if profile.execution_mode == "cloud":
        release_seat = whatsapp_consumes_cloud_seat(
            profile._id,
            org_id=profile.org_id,
            owner_user_id=profile.user_id,
        )
        from openoutreach.proxies.service import (
            retire_proxy_for_whatsapp_profile,
        )

        retire_proxy_for_whatsapp_profile(profile._id)
    WhatsAppProfile.delete(profile._id)
    if release_seat:
        release_cloud_seat(profile.user_id)


@router.post("/qr/{profile_id}/reset", status_code=204)
async def reset_qr(
    profile_id: str,
    user_id: str = Depends(get_current_user),
):
    """Clear the stored QR so the daemon regenerates it on the next poll cycle."""
    profile = _authorized_profile(profile_id, user_id)
    if profile.status == STATUS_CONNECTED:
        raise HTTPException(status_code=400, detail="Profile already connected")
    profile.qr_png_b64 = None
    profile.save(update_fields=["qr_png_b64"])


@router.get("/qr/{profile_id}")
async def get_qr(
    profile_id: str,
    user_id: str = Depends(get_current_user),
):
    """Return the current QR PNG for a disconnected profile.

    200 image/png  - QR is ready to scan
    200 JSON       - {"status": "connected"} when already authenticated
    202 JSON       - {"status": "pending"} when daemon is still generating QR
    404            - profile not found or does not belong to user
    """
    from fastapi.responses import JSONResponse

    profile = _authorized_profile(profile_id, user_id)

    if profile.status == STATUS_CONNECTED:
        return JSONResponse({"status": "connected"})

    if not profile.qr_png_b64:
        return JSONResponse({"status": "pending"}, status_code=202)

    try:
        png_bytes = base64.b64decode(profile.qr_png_b64)
    except Exception:
        raise HTTPException(status_code=500, detail="QR data corrupted")
    return Response(content=png_bytes, media_type="image/png")
