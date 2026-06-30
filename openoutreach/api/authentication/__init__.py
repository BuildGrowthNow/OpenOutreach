# API Authentication Package

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.authentication import SessionAuthentication
from django.conf import settings

# Supabase authentication
from .supabase import (
    SupabaseJWTAuthentication,
    InvalidTokenError,
    validate_supabase_token,
    create_or_link_django_user,
)

__all__ = [
    "JWTAuthentication",
    "SessionAuthentication",
    "SupabaseJWTAuthentication",
    "InvalidTokenError",
    "validate_supabase_token",
    "create_or_link_django_user",
]
