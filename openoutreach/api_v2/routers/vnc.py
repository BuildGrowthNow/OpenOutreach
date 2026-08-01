"""VNC session API endpoints."""
from fastapi import APIRouter, Depends, HTTPException

from openoutreach.api_v2.dependencies_v2 import get_current_user
from openoutreach.mongodb.models_user import User

router = APIRouter()


# Static routes MUST be registered before /{profile_id} to prevent FastAPI
# from matching "sessions" as a profile_id path parameter.

@router.get("/vnc/sessions")
async def list_vnc_sessions(current_user: User = Depends(get_current_user)):
    """List all active VNC sessions for the current user's profiles."""
    from openoutreach.linkedin.models import LinkedInProfile
    from openoutreach.core.vnc_manager import get_all_vnc_sessions

    # Get user's profiles
    user_id = getattr(current_user, '_id', None)
    if not user_id:
        return {"sessions": {}}
    user_profiles = LinkedInProfile.objects.filter(user_id=user_id, active=True)
    user_profile_ids = {str(p.pk) for p in user_profiles}

    # Filter VNC sessions to only user's profiles
    all_sessions = get_all_vnc_sessions()
    user_sessions = {
        pid: info for pid, info in all_sessions.items()
        if pid in user_profile_ids
    }

    return {"sessions": user_sessions}


@router.get("/vnc/{profile_id}")
async def get_vnc_session(
    profile_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get VNC session info for a specific LinkedIn profile.

    Returns websockify port for the profile's isolated VNC session.
    """
    from openoutreach.linkedin.models import LinkedInProfile
    from openoutreach.core.vnc_manager import get_vnc_url, _profile_indices

    # Verify profile belongs to current user
    try:
        profile = LinkedInProfile.get(profile_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Profile not found")

    user_id = getattr(current_user, '_id', None)
    profile_user_id = getattr(profile, 'user_id', None)
    if not user_id or (profile_user_id and profile_user_id != user_id):
        raise HTTPException(status_code=403, detail="Not authorized to access this profile")

    vnc_url = get_vnc_url(profile_id)
    if not vnc_url:
        raise HTTPException(
            status_code=503,
            detail="VNC session not available. The daemon may not be running or VNC may be disabled.",
        )

    # Return the websockify port for this profile
    profile_index = _profile_indices.get(profile_id, 0)
    websockify_port = 6080 + profile_index

    return {
        "profile_id": profile_id,
        "websockify_port": websockify_port,
        "vnc_url": f"/vnc/{profile_id}",  # Frontend will proxy through this
    }
