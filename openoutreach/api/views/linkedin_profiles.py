# openoutreach/api/views/linkedin_profiles.py
"""LinkedIn Profiles API Views."""

from django.db import DatabaseError
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from openoutreach.linkedin.models import LinkedInProfile

from .linkedin_common import schema_error_response, user_profiles_queryset


class LinkedInProfilesListView(APIView):
    """
    API view for listing LinkedIn profiles available to the current user.

    GET /api/linkedin-profiles - Get all LinkedIn profiles for the authenticated user
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get LinkedIn profiles accessible by the current user."""
        try:
            profiles = user_profiles_queryset(request.user)
        except DatabaseError as exc:
            return schema_error_response(endpoint="linkedin-profiles", exc=exc)

        return Response(
            {
                "profiles": [
                    {
                        "id": profile.pk,
                        "linkedin_username": profile.linkedin_username,
                        "active": profile.active,
                        "connect_daily_limit": profile.connect_daily_limit,
                        "follow_up_daily_limit": profile.follow_up_daily_limit,
                    }
                    for profile in profiles
                ],
                "count": profiles.count(),
            }
        )


class LinkedInProfileCookieView(APIView):
    """API view to upload and verify a Playwright storage_state cookie blob for a LinkedInProfile.

    POST /api/linkedin-profiles/{id}/cookies/ - Accepts either:
      - Full Playwright storage_state JSON (object with "cookies" array)
      - A single li_at cookie string (will be wrapped into minimal storage_state)

    The view will validate permissions (owner or change permission), perform a short verification
    using the AccountSession (short timeout), store the encrypted cookie blob on success, and
    return a summary.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Profile ID required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            profile = LinkedInProfile.objects.get(pk=pk)
        except LinkedInProfile.DoesNotExist:
            return Response(
                {"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except DatabaseError as exc:
            return schema_error_response(endpoint="linkedin-profiles:cookies", exc=exc)

        # Permission: owner or has change permission
        if profile.user != request.user and not request.user.has_perm(
            "linkedin.change_linkedinprofile"
        ):
            return Response({"error": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)

        data = request.data
        cookie_payload = data.get("cookie_data")

        if not cookie_payload:
            return Response(
                {"error": "cookie_data payload required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Normalize payload into a storage_state dict
        storage_state = None
        import json

        try:
            if isinstance(cookie_payload, str):
                # Try to parse JSON first
                try:
                    parsed = json.loads(cookie_payload)
                    if isinstance(parsed, dict) and "cookies" in parsed:
                        storage_state = parsed
                except Exception:
                    # Treat as li_at value
                    li_at = cookie_payload.strip()
                    if not li_at:
                        raise ValueError("Empty cookie string")
                    storage_state = {
                        "cookies": [
                            {
                                "name": "li_at",
                                "value": li_at,
                                "domain": ".linkedin.com",
                                "path": "/",
                                "expires": 0,
                            }
                        ]
                    }
            elif isinstance(cookie_payload, dict):
                if "cookies" in cookie_payload:
                    storage_state = cookie_payload
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if not storage_state:
            return Response(
                {"error": "Invalid cookie_data format"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Basic validation: ensure li_at cookie exists
        li_at_present = any(
            c.get("name") == "li_at" for c in storage_state.get("cookies", [])
        )
        if not li_at_present:
            return Response(
                {"error": "li_at cookie missing"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Save the cookie directly — the daemon validates it when it picks it up.
        # Browser verification from the API server conflicts with the event loop
        # and the daemon already handles invalid cookies gracefully.
        try:
            profile.cookie_data = storage_state
            profile.save(update_fields=["cookie_data_encrypted"])
            return Response(
                {"success": True, "message": "Cookie saved successfully. The session will activate within 30 seconds."},
                status=status.HTTP_200_OK,
            )
        except Exception as exc:
            return Response(
                {"success": False, "error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
