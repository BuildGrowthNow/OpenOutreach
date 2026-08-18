import base64
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from openoutreach.api_v2.dependencies_v2 import get_current_user
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
    return {
        "id": profile._id,
        "userId": profile.user_id,
        "phoneNumber": profile.phone_number,
        "displayName": profile.display_name,
        "status": profile.status,
        "lastSeen": profile.last_seen.isoformat() if profile.last_seen else None,
        "createdAt": profile.created_at.isoformat() if profile.created_at else None,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/profiles", response_model=List[Dict[str, Any]])
async def list_profiles(user_id: str = Depends(get_current_user)):
    profiles = WhatsAppProfile.find_by_user_id(user_id)
    return [_serialize(p) for p in profiles]


@router.post("/profiles", response_model=Dict[str, Any], status_code=201)
async def create_profile(
    body: WhatsAppProfileCreate,
    user_id: str = Depends(get_current_user),
):
    profile = WhatsAppProfile(
        user_id=user_id,
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
    profile = WhatsAppProfile.get(profile_id)
    if not profile or profile.user_id != user_id:
        raise HTTPException(status_code=404, detail="WhatsApp profile not found")
    return _serialize(profile)


@router.patch("/profiles/{profile_id}", response_model=Dict[str, Any])
async def update_profile(
    profile_id: str,
    body: WhatsAppProfileUpdate,
    user_id: str = Depends(get_current_user),
):
    profile = WhatsAppProfile.get(profile_id)
    if not profile or profile.user_id != user_id:
        raise HTTPException(status_code=404, detail="WhatsApp profile not found")
    update_fields = []
    if body.display_name is not None:
        profile.display_name = body.display_name
        update_fields.append("display_name")
    if body.status is not None:
        if body.status not in (STATUS_CONNECTED, STATUS_DISCONNECTED, "banned"):
            raise HTTPException(status_code=400, detail="Invalid status")
        profile.status = body.status
        update_fields.append("status")
    if update_fields:
        profile.save(update_fields=update_fields)
    return _serialize(profile)


@router.delete("/profiles/{profile_id}", status_code=204)
async def delete_profile(
    profile_id: str,
    user_id: str = Depends(get_current_user),
):
    profile = WhatsAppProfile.get(profile_id)
    if not profile or profile.user_id != user_id:
        raise HTTPException(status_code=404, detail="WhatsApp profile not found")
    WhatsAppProfile.delete(profile_id)


@router.get("/qr/{profile_id}")
async def get_qr(
    profile_id: str,
    user_id: str = Depends(get_current_user),
):
    """Return the current QR PNG for a disconnected profile.

    200 image/png  — QR is ready to scan
    200 JSON       — {"status": "connected"} when already authenticated
    202 JSON       — {"status": "pending"} when daemon is still generating QR
    404            — profile not found or does not belong to user
    """
    from fastapi.responses import JSONResponse

    profile = WhatsAppProfile.get(profile_id)
    if not profile or profile.user_id != user_id:
        raise HTTPException(status_code=404, detail="WhatsApp profile not found")

    if profile.status == STATUS_CONNECTED:
        return JSONResponse({"status": "connected"})

    if not profile.qr_png_b64:
        return JSONResponse({"status": "pending"}, status_code=202)

    try:
        png_bytes = base64.b64decode(profile.qr_png_b64)
    except Exception:
        raise HTTPException(status_code=500, detail="QR data corrupted")
    return Response(content=png_bytes, media_type="image/png")
