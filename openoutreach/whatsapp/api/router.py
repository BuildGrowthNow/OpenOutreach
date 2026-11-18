import base64
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from openoutreach.api_v2.dependencies_v2 import get_current_user
from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.organizations.access import (
    can_access_channel_doc,
    channel_access_query,
    resolve_org_context,
)
from openoutreach.organizations.enforcement import resolve_effective_plan
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


class WhatsAppProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    status: Optional[str] = None


def _serialize(profile: WhatsAppProfile) -> Dict[str, Any]:
    qr_data_url = None
    if profile.qr_png_b64 and profile.status == STATUS_DISCONNECTED:
        qr_data_url = f"data:image/png;base64,{profile.qr_png_b64}"
    return {
        "id": profile._id,
        "userId": profile.user_id,
        "orgId": profile.org_id,
        "assignedUserId": profile.assigned_user_id,
        "executionMode": profile.execution_mode,
        "proxyMode": profile.proxy_mode,
        "phoneNumber": profile.phone_number,
        "displayName": profile.display_name,
        "status": profile.status,
        "lastSeen": profile.last_seen.isoformat() if profile.last_seen else None,
        "createdAt": profile.created_at.isoformat() if profile.created_at else None,
        "qrDataUrl": qr_data_url,
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
    coll = get_mongodb_collection("whatsapp_profiles")
    # Only connected profiles count against the limit; pending QR-scan ones don't.
    current_count = (
        coll.count_documents(
            {
                "$or": [
                    {"org_id": ctx.org_id},
                    {"org_id": {"$exists": False}, "user_id": user_id},
                    {"org_id": None, "user_id": user_id},
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
        assigned_user_id=user_id,
        execution_mode="desktop",
        display_name=body.display_name,
        status=STATUS_DISCONNECTED,
    )
    profile.save()
    return _serialize(profile)


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
    WhatsAppProfile.delete(profile._id)


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
