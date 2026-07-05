# openoutreach/api/views/linkedin_profile_health.py
"""LinkedIn Profile Health API View."""

import logging

from django.db import DatabaseError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .linkedin_common import schema_error_response, user_profiles_queryset


class LinkedInProfileHealthView(APIView):
    """
    API view for retrieving LinkedIn profile health status.

    GET /api/linkedin-profile-health - Get health status for all user's LinkedIn profiles
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get LinkedIn profile health status for authenticated user."""
        logger = logging.getLogger(__name__)

        try:
            from openoutreach.crm.models import LinkedInCredentialLog
        except Exception:
            LinkedInCredentialLog = None
            logger.exception("LinkedInCredentialLog import failed")

        try:
            profiles = user_profiles_queryset(request.user)
            total_profiles = profiles.count()
        except DatabaseError as exc:
            return schema_error_response(endpoint="linkedin-profile-health", exc=exc)

        profile_health_data = []
        for profile in profiles:
            # Get health status from credentials if available
            credentials_status = "unknown"
            health_score = 100
            last_error = None
            last_verification = None

            # Pyright ignores for dynamic Django reverse foreign key relationships
            if hasattr(profile, "credentials") and profile.credentials:  # type: ignore[attr-defined]
                cred = profile.credentials  # type: ignore[attr-defined]
                credentials_status = cred.status  # type: ignore[attr-defined]

                # Calculate health score based on credential status
                if cred.status == "invalid":  # type: ignore[attr-defined]
                    health_score = 0
                elif cred.status == "locked":  # type: ignore[attr-defined]
                    health_score = 40
                elif cred.status == "expired":  # type: ignore[attr-defined]
                    health_score = 60
                elif cred.status == "tested":  # type: ignore[attr-defined]
                    health_score = 80
                elif cred.status == "active":  # type: ignore[attr-defined]
                    health_score = 100

                # Get last verification error if available
                if LinkedInCredentialLog is not None:
                    try:
                        last_error_log = (
                            LinkedInCredentialLog.objects.filter(
                                credentials=cred  # type: ignore[attr-defined]
                            )
                            .exclude(action="verified")
                            .exclude(action="usage")
                            .last()
                        )

                        if last_error_log:
                            last_error = last_error_log.details.get(
                                "error_message"
                            ) or last_error_log.details.get("message")
                            if not last_error and "reason" in last_error_log.details:
                                last_error = last_error_log.details.get("reason")
                    except Exception:
                        last_error = None

                # Get last verification timestamp
                last_verification = (
                    cred.last_verified.isoformat() if cred.last_verified else None
                )  # type: ignore[attr-defined]

            profile_health_data.append(
                {
                    "id": profile.id,  # type: ignore[attr-defined]
                    "linkedin_username": profile.linkedin_username,
                    "status": profile.active,
                    "credentials_status": credentials_status,
                    "health_score": health_score,
                    "health_status": self._determine_health_status(
                        profile, credentials_status
                    ),
                    "needs_attention": credentials_status
                    in ["invalid", "locked", "expired"],
                    "last_error": last_error,
                    "last_verification": last_verification,
                }
            )

        return Response(
            {
                "profiles": profile_health_data,
                "count": len(profile_health_data),
                "total_profiles": total_profiles,
                "needs_attention_count": sum(
                    1 for p in profile_health_data if p["needs_attention"]
                ),
            }
        )

    def _determine_health_status(self, profile, credentials_status: str) -> str:
        """Determine the overall health status for display."""
        if not profile.active:
            return "inactive"

        if credentials_status == "active":
            return "active"
        elif credentials_status == "invalid":
            return "invalid"
        elif credentials_status == "expired":
            return "expired"
        elif credentials_status == "locked":
            return "locked"
        elif credentials_status == "tested":
            return "tested"
        elif credentials_status == "stored":
            return "stored"

        # Default based on profile active status
        return "active" if profile.active else "inactive"
