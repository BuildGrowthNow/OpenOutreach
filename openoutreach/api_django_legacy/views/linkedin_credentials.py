# openoutreach/api/views/linkedin_credentials.py
"""LinkedIn Credentials Management API Views."""

import logging
from typing import TYPE_CHECKING, Any

from django.db import DatabaseError
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

if TYPE_CHECKING:
    from openoutreach.crm.models import (
        LinkedInCredentialLog,
        LinkedInCredentials,
    )
    from openoutreach.linkedin.browser.session import AccountSession
    from openoutreach.linkedin.models import LinkedInProfile

try:
    from openoutreach.crm.models import (
        LinkedInCredentialLog,
        LinkedInCredentials,
    )
    from openoutreach.linkedin.browser.session import AccountSession
    from openoutreach.linkedin.models import LinkedInProfile
except Exception as _exc:  # pragma: no cover - import-time resilience
    LinkedInCredentialLog = None  # type: ignore[assignment]
    LinkedInCredentials = None  # type: ignore[assignment]
    AccountSession = None  # type: ignore[assignment]
    LinkedInProfile = None  # type: ignore[assignment]
    logging.getLogger(__name__).exception(
        "Failed to import LinkedIn credential models: %s", _exc
    )

from .linkedin_common import schema_error_response, user_primary_profile


def _sync_profile_login(*, profile: Any, email: str, password: str) -> None:
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


def _clear_profile_login(profile: Any) -> None:  # type: ignore[assignment, union-attr]
    """Remove login material from a LinkedInProfile after credential deletion."""
    update_fields = []
    if profile.linkedin_username != "":
        profile.linkedin_username = ""
        update_fields.append("linkedin_username")
    if profile.linkedin_password != "":
        profile.linkedin_password = ""
        update_fields.append("linkedin_password")
    if profile.cookie_data_encrypted is not None:
        profile.cookie_data_encrypted = None
        update_fields.append("cookie_data_encrypted")
    if profile.active:
        profile.active = False
        update_fields.append("active")
    if update_fields:
        profile.save(update_fields=update_fields)


import threading
import queue


class _PlaywrightWorker:
    """Keeps a Playwright browser alive in a dedicated thread.

    Playwright objects are thread-bound, so verify and confirm must run in
    the same thread.  This worker stays alive between the two calls.
    """

    def __init__(self, cred, session):
        self._cred = cred
        self._session = session
        self._cmd_q: queue.Queue = queue.Queue()
        self._result_q: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        """Worker loop: wait for commands, execute in-thread."""
        while True:
            cmd = self._cmd_q.get()
            if cmd == "verify":
                try:
                    result = self._cred.verify_credentials(
                        self._session, mark_as_active=True, mark_as_stored=True,
                    )
                except Exception as e:
                    result = (False, {"error_type": "verification_error", "message": str(e)[:500]})
                self._result_q.put(result)
            elif cmd == "confirm":
                try:
                    result = self._cred.confirm_challenge(self._session)
                except Exception as e:
                    result = (False, {"error_type": "verification_error", "message": str(e)[:200]})
                self._result_q.put(result)
            elif cmd == "shutdown":
                try:
                    self._session.close()
                except Exception:
                    pass
                break

    def verify(self) -> tuple:
        self._cmd_q.put("verify")
        return self._result_q.get(timeout=120)

    def confirm(self) -> tuple:
        self._cmd_q.put("confirm")
        return self._result_q.get(timeout=15)

    def shutdown(self):
        self._cmd_q.put("shutdown")


# Type alias for optional LinkedInCredentials (can be None if import fails)
LinkedInCredentialsType = Any

def _ensure_profile_for_credential(
    *,
    user,
    cred,
    email: str | None = None,
    password: str | None = None,
) -> Any:  # type: ignore[assignment, return-value]
    """Attach credentials to the user's LinkedInProfile, creating one when needed."""
    if LinkedInCredentials is None:
        logging.getLogger(__name__).warning(
            "LinkedInCredentials model not available, skipping profile sync"
        )
        return None
    if LinkedInProfile is None:
        logging.getLogger(__name__).warning(
            "LinkedInProfile model not available, skipping profile sync"
        )
        return None
    if AccountSession is None:
        logging.getLogger(__name__).warning(
            "AccountSession not available, skipping profile sync"
        )

    login_email = email or cred.get_email()
    login_password = password or cred.get_password()
    profile = cred.linkedin_profile or user_primary_profile(user)

    if profile is None:
        profile = LinkedInProfile.objects.create(  # type: ignore[attr-defined]
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
        # Clear any stale credential that still holds a UNIQUE FK to this profile
        LinkedInCredentials.objects.filter(linkedin_profile=profile).exclude(
            pk=cred.pk
        ).update(linkedin_profile=None)
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
                linkedin_profile = LinkedInProfile.objects.only("id", "user_id").get(  # type: ignore[attr-defined]
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
            except (LinkedInProfile.DoesNotExist, AttributeError):  # type: ignore[attr-defined]
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
                action="created",
                details={"created_by": request.user.username},
            )

            return Response(
                {
                    "success": True,
                    "id": cred.pk,
                    "message": "Credentials created successfully.",
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
            action="updated",
            details={"updated_by": request.user.username},
        )

        # Note: We don't auto-verify here because verification can block for several
        # minutes if LinkedIn presents a checkpoint/challenge. Users should explicitly
        # click "Verify" to test the updated credentials.

        message = "Credentials updated successfully"
        if "email" in data or "password" in data:
            message += ". Click 'Verify' to test the connection."

        return Response(
            {
                "success": True,
                "id": cred.pk,
                "message": message,
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
        """Delete LinkedIn credentials and clear the linked profile login state."""
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

        profile = cred.linkedin_profile
        credential_id = cred.pk

        if profile is not None:
            _clear_profile_login(profile)

        cred.delete()

        return Response(
            {
                "success": True,
                "message": "Credential deleted successfully",
                "id": credential_id,
            }
        )


class LinkedInCredentialsVerifyView(APIView):
    """
    API view for verifying LinkedIn credentials.

    POST /api/linkedin-credentials/{id}/verify - Verify credentials
    """

    permission_classes = [IsAuthenticated]

    # Persistent worker threads keyed by credential PK.
    # Each holds the Playwright browser alive so confirm can use it.
    _workers: dict = {}

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
                {"success": False, "error": "Credential not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            _ensure_profile_for_credential(user=request.user, cred=cred)
        except DatabaseError as exc:
            return schema_error_response(
                endpoint="linkedin-credentials:verify", exc=exc
            )

        # Clean up any stale worker for this credential
        old_worker = self.__class__._workers.pop(pk, None)
        if old_worker:
            old_worker.shutdown()

        try:
            session = AccountSession(cred.linkedin_profile)  # type: ignore[arg-type]
            worker = _PlaywrightWorker(cred, session)
            success, details = worker.verify()

            error_type = details.get("error_type")

            if error_type == "awaiting_challenge":
                self.__class__._workers[pk] = worker
            else:
                worker.shutdown()

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
                    "error_type": error_type,
                },
            }
            if not success:
                response_data["error"] = details.get("message", "Verification failed")

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            error_msg = str(e)[:500]
            import logging as _logging
            _logging.getLogger(__name__).error("Verification request failed: %s", error_msg)
            cred.mark_as_invalid(reason=error_msg)
            return Response(
                {
                    "success": False,
                    "error": f"Verification error: {error_msg}",
                    "credentials": {
                        "id": cred.pk,
                        "status": cred.status,
                        "linkedin_profile_id": getattr(cred, "linkedin_profile_id", None),
                    },
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class LinkedInCredentialsConfirmView(APIView):
    """Confirm that a challenge was completed in VNC.

    POST /api/linkedin-credentials/{id}/confirm
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk=None):
        if LinkedInCredentials is None:
            return Response(
                {"error": "LinkedIn credentials support unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            cred = LinkedInCredentials.objects.get(pk=pk)
        except LinkedInCredentials.DoesNotExist:
            return Response(
                {"success": False, "error": "Credential not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        worker = LinkedInCredentialsVerifyView._workers.get(pk)
        if not worker:
            return Response(
                {
                    "success": False,
                    "error": "No pending challenge session. Please start verification again.",
                    "details": {"error_type": "session_expired"},
                },
                status=status.HTTP_409_CONFLICT,
            )

        success, details = worker.confirm()

        if success:
            LinkedInCredentialsVerifyView._workers.pop(pk, None)
            worker.shutdown()

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
            response_data["error"] = details.get("message", "Challenge not completed")

        return Response(response_data, status=status.HTTP_200_OK)


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
