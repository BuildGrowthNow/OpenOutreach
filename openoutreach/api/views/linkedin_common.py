"""Shared helpers for LinkedIn API views."""

from __future__ import annotations

import logging

from django.db import DatabaseError
from rest_framework import status
from rest_framework.response import Response

from openoutreach.linkedin.models import LinkedInProfile

logger = logging.getLogger(__name__)

LINKEDIN_PROFILE_ONLY_FIELDS = (
    "id",
    "user_id",
    "linkedin_username",
    "linkedin_password",
    "active",
    "connect_daily_limit",
    "follow_up_daily_limit",
)

LINKEDIN_SCHEMA_OUT_OF_SYNC_MESSAGE = (
    "LinkedIn data is temporarily unavailable because the backend database schema "
    "is out of date. Run `python manage.py migrate` and restart the backend."
)


def user_profiles_queryset(user):
    """Return the current user's LinkedIn profiles using a minimal column set."""
    return LinkedInProfile.objects.filter(user=user).only(*LINKEDIN_PROFILE_ONLY_FIELDS)


def user_primary_profile(user):
    """Return the current user's LinkedIn profile, if one exists."""
    return user_profiles_queryset(user).first()


def schema_error_response(*, endpoint: str, exc: DatabaseError) -> Response:
    """Return a stable JSON response for schema drift or other database errors."""
    logger.exception("%s failed due to database error: %s", endpoint, exc)
    return Response(
        {
            "error": LINKEDIN_SCHEMA_OUT_OF_SYNC_MESSAGE,
            "code": "linkedin_schema_out_of_sync",
        },
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )
