# openoutreach/api/views/linkedin_credentials.py
"""LinkedIn Credentials Management API Views."""

import logging

from django.db import DatabaseError
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

try:
    from openoutreach.crm.models import LinkedInCredentialLog, LinkedInCredentials
except Exception as _exc:  # pragma: no cover - import-time resilience
    LinkedInCredentialLog = None
    LinkedInCredentials = None
    logging.getLogger(__name__).exception(
        "Failed to import LinkedIn credential models: %s", _exc
    )

from openoutreach.linkedin.browser.session import AccountSession
from openoutreach.linkedin.models import LinkedInProfile

from .linkedin_common import schema_error_response, user_primary_profile


def _sync_profile_login(*, profile: LinkedInProfile, email: str, password: str) -> None:
    """Keep the daemon-owned LinkedInProfile login fields in sync with credentials."""
    update_fields = []
    if profile.linkedin_username != email:
        profile.linkedin_username = email
        update_fields.append("linkedin_username")
    if profile.linkedin_password != password:
        profile.linkedin_password = password
        update_fields.append("linkedin_password")
    if update_fields:
        profile.save(update_fields=update_fields)


def _ensure_profile_for_credential(
    *,
    user,
    cred,
    email: str | None = None,
    password: str | None = None,
) -> LinkedInProfile:
    """Attach credentials to the user's LinkedInProfile, creating one when needed."""
    login_email = email or cred.get_email()
    login_password = password or cred.get_password()
    profile = cred.linkedin_profile or user_primary_profile(user)

    if profile is None:
        profile = LinkedInProfile.objects.create(
            user=user,
            linkedin_username=login_email,
            linkedin_password=login_password,
            active=False,
        )
    else:
        _sync_profile_login(
            profile=profile,
            email=login_email,
            password=login_password,
        )

    if getattr(cred, "linkedin_profile_id", None) != profile.pk:
        cred.linkedin_profile = profile
        cred.save(update_fields=["linkedin_profile"])

    return profile


class LinkedInCredentialsView(APIView):
    """
    API view for managing LinkedIn credentials.

    GET /api/linkedin-credentials - Get all credentials for current user
    POST /api/linkedin-credentials - Create new credentials
    PATCH /api/linkedin-credentials/{id} - Update credentials
    DELETE /api/linkedin-credentials/{id} - Delete credentials (deactivate)
    """

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Get credentials accessible by the current user."""
        if LinkedInCredentials is None:
            raise RuntimeError("LinkedInCredentials model not available")
        return LinkedInCredentials.objects.all()

    def get(self, request):
        """Get all LinkedIn credentials for the authenticated user."""
        if LinkedInCredentials is None:
            return Response(
                {"error": "LinkedIn credentials support unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        try:
            credentials = self.get_queryset().filter(
                linkedin_profile__user=request.user
            )
        except DatabaseError as exc:
            return schema_error_response(endpoint="linkedin-credentials", exc=exc)

        return Response(
            {
                "credentials": [
                    {
                        "id": cred.pk,
                        "username": cred.username,
                        "public_email": cred.get_public_email(),
                        "status": cred.status,
                        "is_primary": cred.is_primary,
                        "is_backup": cred.is_backup,
                        "usage_count": cred.usage_count,
                        "last_verified": (
                            cred.last_verified.isoformat()
                            if cred.last_verified
                            else None
                        ),
                        "last_used": (
                            cred.last_used.isoformat() if cred.last_used else None
                        ),
                        "health_status": cred.get_health_status(),
                        "linkedin_profile_id": getattr(
                            cred, "linkedin_profile_id", None
                        ),
                    }
                    for cred in credentials
                ],
                "count": credentials.count(),
            }
        )

    def post(self, request):
        """Create new LinkedIn credentials."""
        if LinkedInCredentials is None or LinkedInCredentialLog is None:
            return Response(
                {"error": "LinkedIn credentials support unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        data = request.data

        # Validate required fields
        email = data.get("email")
        password = data.get("password")
        username = data.get("username", "")
        linkedin_profile_id = data.get("linkedin_profile_id")

        if not email or not password:
            raise ValidationError(
                {
                    "email": "Email is required",
                    "password": "Password is required",
                }
            )

        # Validate linkedin_profile_id if provided
        linkedin_profile = None
        if linkedin_profile_id:
            try:
                linkedin_profile = LinkedInProfile.objects.only("id", "user_id").get(
                    id=linkedin_profile_id
                )
                # Verify the profile belongs to the current user or user has permission
                # Allow access if: user owns the profile OR user has change permission
                if linkedin_profile.user != request.user and not request.user.has_perm(
                    "linkedin.change_linkedinprofile", linkedin_profile
                ):
                    raise ValidationError(
                        {
                            "linkedin_profile_id": "You do not have access to this LinkedIn profile"
                        }
                    )
            except LinkedInProfile.DoesNotExist:
                raise ValidationError(
                    {"linkedin_profile_id": "LinkedIn profile not found"}
                )
            except DatabaseError as exc:
                return schema_error_response(
                    endpoint="linkedin-credentials:create", exc=exc
                )

        try:
            # Create encrypted credentials
            cred = LinkedInCredentials(
                username=username,
                linkedin_profile=linkedin_profile,
            )
            cred.set_email(email)
            cred.set_password(password)
            cred.save()

            try:
                _ensure_profile_for_credential(
                    user=request.user,
                    cred=cred,
                    email=email,
                    password=password,
                )
            except DatabaseError as exc:
                return schema_error_response(
                    endpoint="linkedin-credentials:create", exc=exc
                )

            # Create audit log entry
            LinkedInCredentialLog.objects.create(
                credentials=cred,
                action=LinkedInCredentialLog.ACTION_VERIFIED,
                details={"created_by": request.user.username},
            )

            return Response(
                {
                    "success": True,
                    "id": cred.pk,
                    "message": "Credentials created successfully",
                    "credentials": {
                        "id": cred.pk,
                        "username": cred.username,
                        "public_email": cred.get_public_email(),
                        "status": cred.status,
                        "linkedin_profile_id": getattr(
                            cred, "linkedin_profile_id", None
                        ),
                    },
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            return Response(
                {
                    "success": False,
                    "error": str(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    def patch(self, request, pk=None):
        """Update LinkedIn credentials."""
        if LinkedInCredentials is None or LinkedInCredentialLog is None:
            return Response(
                {"error": "LinkedIn credentials support unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if not pk:
            raise ValidationError({"detail": "Credential ID required"})

        try:
            cred = LinkedInCredentials.objects.get(pk=pk)
        except LinkedInCredentials.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "error": "Credential not found",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        data = request.data

        # Update username if provided
        if "username" in data:
            cred.username = data["username"]

        # Update credentials if provided
        if "email" in data:
            cred.set_email(data["email"])
        if "password" in data:
            cred.set_password(data["password"])

        # Update status if provided
        if "status" in data:
            cred.status = data["status"]

        cred.save()

        try:
            _ensure_profile_for_credential(user=request.user, cred=cred)
        except DatabaseError as exc:
            return schema_error_response(
                endpoint="linkedin-credentials:update", exc=exc
            )

        # Create audit log entry
        LinkedInCredentialLog.objects.create(
            credentials=cred,
            action=LinkedInCredentialLog.ACTION_VERIFIED,
            details={"updated_by": request.user.username},
        )

        return Response(
            {
                "success": True,
                "id": cred.pk,
                "message": "Credentials updated successfully",
                "credentials": {
                    "id": cred.pk,
                    "username": cred.username,
                    "public_email": cred.get_public_email(),
                    "status": cred.status,
                    "linkedin_profile_id": getattr(cred, "linkedin_profile_id", None),
                },
            }
        )

    def delete(self, request, pk=None):
        """Deactivate/delete LinkedIn credentials."""
        if LinkedInCredentials is None or LinkedInCredentialLog is None:
            return Response(
                {"error": "LinkedIn credentials support unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if not pk:
            raise ValidationError({"detail": "Credential ID required"})

        try:
            cred = LinkedInCredentials.objects.get(pk=pk)
        except LinkedInCredentials.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "error": "Credential not found",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Soft delete - mark as inactive instead of hard deleting
        cred.status = LinkedInCredentials.STATUS_INVALID
        cred.save(update_fields=["status"])

        LinkedInCredentialLog.objects.create(
            credentials=cred,
            action=LinkedInCredentialLog.ACTION_FAILED,
            details={"deleted_by": request.user.username},
        )

        return Response(
            {
                "success": True,
                "message": "Credential deactivated successfully",
            }
        )


class LinkedInCredentialsVerifyView(APIView):
    """
    API view for verifying LinkedIn credentials.

    POST /api/linkedin-credentials/{id}/verify - Verify credentials
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk=None):
        """Verify LinkedIn credentials using real LinkedIn browser automation."""
        if LinkedInCredentials is None:
            return Response(
                {"error": "LinkedIn credentials support unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if not pk:
            raise ValidationError({"detail": "Credential ID required"})

        try:
            cred = LinkedInCredentials.objects.get(pk=pk)
        except LinkedInCredentials.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "error": "Credential not found",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Ensure the credential is attached to a LinkedInProfile and the daemon
        # login fields stay in sync with the stored credential values.
        try:
            _ensure_profile_for_credential(user=request.user, cred=cred)
        except DatabaseError as exc:
            return schema_error_response(
                endpoint="linkedin-credentials:verify", exc=exc
            )

        # Create session for verification
        try:
            session = AccountSession(cred.linkedin_profile)

            # Perform verification with browser automation
            success, details = cred.verify_credentials(
                session=session,
                mark_as_active=True,
                mark_as_stored=True,  # Keep as stored if verification errors
            )

            # Build detailed response
            response_data = {
                "success": success,
                "credentials": {
                    "id": cred.pk,
                    "status": cred.status,
                    "last_verified": (
                        cred.last_verified.isoformat() if cred.last_verified else None
                    ),
                    "verification_failures": cred.verification_failures,
                    "linkedin_profile_id": getattr(cred, "linkedin_profile_id", None),
                },
                "details": {
                    "verified_at": details.get("verified_at"),
                    "message": details.get("message"),
                    "error_type": details.get("error_type"),
                },
            }

            if not success:
                response_data["error"] = details.get("message", "Verification failed")

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            error_msg = str(e)[:500]
            logger = __import__("logging").getLogger(__name__)
            logger.error(f"Verification request failed: {error_msg}")
            cred.mark_as_invalid(reason=error_msg)

            return Response(
                {
                    "success": False,
                    "error": f"Verification error: {error_msg}",
                    "credentials": {
                        "id": cred.pk,
                        "status": cred.status,
                        "linkedin_profile_id": getattr(
                            cred, "linkedin_profile_id", None
                        ),
                    },
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class LinkedInCredentialsRotationView(APIView):
    """
    API view for credential rotation.

    POST /api/linkedin-credentials/{id}/rotate - Rotate credentials
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk=None):
        """Rotate LinkedIn credentials."""
        if LinkedInCredentials is None or LinkedInCredentialLog is None:
            return Response(
                {"error": "LinkedIn credentials support unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if not pk:
            raise ValidationError({"detail": "Credential ID required"})

        try:
            cred = LinkedInCredentials.objects.get(pk=pk)
        except LinkedInCredentials.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "error": "Credential not found",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        data = request.data
        new_email = data.get(
            "email", cred.get_email() if hasattr(cred, "get_email") else None
        )
        new_password = data.get(
            "password", cred.get_password() if hasattr(cred, "get_password") else None
        )

        if new_email:
            cred.set_email(new_email)
        if new_password:
            cred.set_password(new_password)

        # Rotate the credentials
        cred.rotate_credentials()

        # Create backup
        backup = cred.create_backup()

        # Create audit log entry
        LinkedInCredentialLog.objects.create(
            credentials=cred,
            action=LinkedInCredentialLog.ACTION_ROTATED,
            details={
                "rotated_by": request.user.username,
                "backup_id": backup.pk,
            },
        )

        return Response(
            {
                "success": True,
                "message": "Credentials rotated successfully",
                "new_credentials": {
                    "id": cred.pk,
                    "public_email": cred.get_public_email(),
                    "is_backup": cred.is_backup,
                },
                "backup_credentials": {
                    "id": backup.pk,
                    "public_email": backup.get_public_email(),
                },
            }
        )


class LinkedInCredentialsHealthView(APIView):
    """
    API view for credential health monitoring.

    GET /api/linkedin-credentials/{id}/health - Get health status
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        """Get LinkedIn credentials health status."""
        if LinkedInCredentials is None:
            return Response(
                {"error": "LinkedIn credentials support unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if not pk:
            raise ValidationError({"detail": "Credential ID required"})

        try:
            cred = LinkedInCredentials.objects.get(pk=pk)
        except LinkedInCredentials.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "error": "Credential not found",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        health_status = cred.get_health_status()

        return Response(
            {
                "success": True,
                "credentials_id": cred.pk,
                "health_status": health_status,
            }
        )


class LinkedInCredentialsLogsView(APIView):
    """
    API view for credential audit logs.

    GET /api/linkedin-credentials/{id}/logs - Get audit logs
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        """Get LinkedIn credentials audit logs."""
        if LinkedInCredentials is None:
            return Response(
                {"error": "LinkedIn credentials support unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if not pk:
            raise ValidationError({"detail": "Credential ID required"})

        try:
            cred = LinkedInCredentials.objects.get(pk=pk)
        except LinkedInCredentials.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "error": "Credential not found",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        logs = cred.logs.all().order_by("-created_at")[:100]  # type: ignore[attr-defined]

        return Response(
            {
                "success": True,
                "credentials_id": cred.pk,
                "logs": [
                    {
                        "id": log.pk,
                        "action": log.action,
                        "details": log.details,
                        "ip_address": log.ip_address,
                        "created_at": log.created_at.isoformat(),
                    }
                    for log in logs
                ],
                "count": logs.count(),
            }
        )
