"""VNC session API endpoints."""
from fastapi import APIRouter, Depends, HTTPException

from openoutreach.api_v2.dependencies_v2 import get_current_user
from openoutreach.mongodb.models_user import User

router = APIRouter()


# Static routes MUST be registered before /{profile_id} to prevent FastAPI
# from matching "sessions" as a profile_id path parameter.

@router.get("/vnc/sessions")
async def list_vnc_sessions(user_id: str = Depends(get_current_user)):
    """List all active VNC sessions for the current user's profiles."""
    from openoutreach.core.vnc_manager import get_all_vnc_sessions
    from openoutreach.mongodb.connection import get_mongodb_collection
    from openoutreach.organizations.access import profile_access_query

    user = User.get(user_id)
    if not user:
        return {"sessions": {}}
    profiles = get_mongodb_collection("linkedin_profiles")
    if profiles is None:
        return {"sessions": {}}
    user_profile_ids = {
        str(doc["_id"])
        for doc in profiles.find({**profile_access_query(user), "active": True}, {"_id": 1})
    }

    # Filter VNC sessions to only accessible profiles
    all_sessions = get_all_vnc_sessions()
    user_sessions = {
        pid: info for pid, info in all_sessions.items()
        if pid in user_profile_ids
    }

    return {"sessions": user_sessions}


@router.get("/vnc/{profile_id}")
async def get_vnc_session(
    profile_id: str,
    user_id: str = Depends(get_current_user),
):
    """Get VNC session info for a specific LinkedIn profile.

    Returns websockify port for the profile's isolated VNC session.
    """
    from openoutreach.linkedin.models import LinkedInProfile
    from openoutreach.core.vnc_manager import get_vnc_url, _profile_indices
    from openoutreach.organizations.access import can_access_profile_doc

    # Verify org-scoped access to the profile
    try:
        profile = LinkedInProfile.get(profile_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Profile not found")

    user = User.get(user_id)
    if not user or not profile or not can_access_profile_doc(user, profile.to_dict()):
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
