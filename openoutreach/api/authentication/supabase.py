"""
Supabase JWT Authentication for Django REST Framework

This module provides custom authentication classes that validate Supabase JWT tokens.
It also handles the automatic creation/linking of Django users with Supabase users.
"""

import logging
from datetime import datetime
from typing import Optional, Tuple, Any, Dict

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpRequest
from rest_framework.authentication import (
    BaseAuthentication,
    TokenAuthentication,
    get_authorization_header,
)
from rest_framework.exceptions import AuthenticationFailed, NotAuthenticated
import jwt
from jwt import PyJWTError

from openoutreach.mongodb.models import SupabaseUser
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

User = get_user_model()
logger = logging.getLogger(__name__)


class SupabaseJWTAuthentication(BaseAuthentication):
    """
    Custom JWT authentication class that validates Supabase JWT tokens.

    Uses the Supabase JWT verification approach:
    1. Extracts the JWT from the Authorization header
    2. Verifies the JWT signature using Supabase's public key
    3. Validates the token claims
    4. Creates/links Django user based on Supabase user

    Authentication header format: Authorization: Bearer <supabase_jwt_token>
    """

    # Supabase JWT algorithm - RS256 is the default for Supabase
    # HS256 can be used if configured in Supabase project settings
    ALGORITHM = "RS256"

    def authenticate(self, request: HttpRequest) -> Optional[Tuple[Any, Any]]:
        """
        Authenticate a request using Supabase JWT.

        Returns a tuple of (user, token) if authentication is successful.
        Returns None if authentication should be ignored.

        Raises AuthenticationFailed if authentication fails.
        """
        # Get the Authorization header
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")

        if not auth_header:
            return None

        # Check if it's a Bearer token
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None

        access_token = parts[1]

        if not access_token:
            return None

        try:
            # Verify and decode the token
            user = self._authenticate_token(access_token)
            return (user, access_token)

        except InvalidTokenError as e:
            raise AuthenticationFailed(str(e))
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise AuthenticationFailed("Invalid token")

    def _authenticate_token(self, token: str) -> Any:
        """
        Verify and decode the Supabase JWT token.

        This method uses direct JWT validation without calling Supabase API,
        which improves performance. For production, you may want to verify
        against Supabase's public key endpoint.
        """
        if not token:
            raise InvalidTokenError("Token is empty")

        try:
            # Decode the token without verification first to get user info
            decoded = jwt.decode(
                token,
                options={
                    "verify_signature": False,
                    "verify_exp": False,
                    "verify_nbf": False,
                },
            )

            # Get the Supabase user ID from the token
            supabase_user_id = decoded.get("sub")
            if not supabase_user_id:
                raise InvalidTokenError("Invalid token payload: missing user ID")

            # Verify token signature using the configured secret key
            self._verify_token_signature(token)

            # Create or get Django user linked to Supabase user
            user = self._get_or_create_user(decoded)

            return user

        except PyJWTError as e:
            raise InvalidTokenError(f"Token verification failed: {str(e)}")
        except Exception as e:
            logger.error(f"Token authentication error: {e}")
            raise InvalidTokenError("Invalid token")

    def _verify_token_signature(self, token: str) -> None:
        """
        Verify the JWT signature using the Supabase service key.

        For production, the signature should be verified using Supabase's
        public key from the /.well-known/jwks.json endpoint.
        """
        if not settings.SUPABASE_SERVICE_KEY:
            logger.warning(
                "SUPABASE_SERVICE_KEY not configured, skipping signature verification"
            )
            return

        try:
            # Decode the token with signature verification
            jwt.decode(
                token,
                settings.SUPABASE_SERVICE_KEY,
                algorithms=[self.ALGORITHM],
            )
        except PyJWTError as e:
            raise InvalidTokenError(f"Token signature verification failed: {str(e)}")

    def _get_or_create_user(self, token_data: Dict[str, Any]) -> Any:
        """
        Get or create a Django user linked to the Supabase user.

        Creates/updates a MongoDB SupabaseUser record for tracking.

        Args:
            token_data: Decoded JWT token data containing user information

        Returns:
            Django User instance
        """
        supabase_user_id = token_data.get("sub")
        email = token_data.get("email")
        full_name = token_data.get("user_metadata", {}).get("full_name")

        if not supabase_user_id or not email:
            raise InvalidTokenError("Token missing required user information")

        try:
            # Try to get existing user by Supabase user ID
            user, created = User.objects.get_or_create(
                username=supabase_user_id,  # Use Supabase user ID as username
                defaults={
                    "email": email,
                    "first_name": full_name or "",
                },
            )
            # user.id may raise Pylance error because Pylance doesn't know the concrete type
            # Casting to Any to tell Pylance the type is valid
            _user_id = cast(str, user.id)  # type: ignore[attr-defined]

            if created:
                # Create a dummy password since we don't store passwords for SSO users
                user.set_unusable_password()
                user.save()

                logger.info(
                    f"Created Django user for Supabase user: {supabase_user_id}"
                )

            # Create or update SupabaseUser in MongoDB for tracking
            self._link_supabase_user_to_django(supabase_user_id, _user_id, token_data)

            return user

        except Exception as e:
            logger.error(f"Error getting/creating user: {e}")
            raise AuthenticationFailed("Failed to authenticate user")

    def _link_supabase_user_to_django(
        self, supabase_user_id: str, django_user_id: str, token_data: Dict[str, Any]
    ) -> None:
        """
        Create or update SupabaseUser in MongoDB to link with Django user.

        Args:
            supabase_user_id: The Supabase user UUID
            django_user_id: The Django User's primary key
            token_data: The decoded JWT token data
        """
        try:
            # Get existing SupabaseUser or create new one
            supabase_user = SupabaseUser.get(supabase_user_id)

            if supabase_user is None:
                # Create new SupabaseUser record
                supabase_user = SupabaseUser(
                    supabase_user_id=supabase_user_id,
                    django_user_id=str(django_user_id),
                    email=token_data.get("email", ""),
                    full_name=token_data.get("user_metadata", {}).get("full_name", ""),
                    token_data=token_data,
                    is_active=True,
                )
                supabase_user.save()
                logger.info(
                    f"Created SupabaseUser record for Django user {django_user_id}"
                )
            else:
                # Update existing SupabaseUser record
                supabase_user.django_user_id = str(django_user_id)
                supabase_user.email = token_data.get("email", "")
                supabase_user.full_name = token_data.get("user_metadata", {}).get(
                    "full_name", ""
                )
                supabase_user.token_data = token_data
                supabase_user.last_login = datetime.utcnow()
                supabase_user.save()
                logger.info(
                    f"Updated SupabaseUser record for Django user {django_user_id}"
                )
        except Exception as e:
            logger.error(f"Error linking Supabase user to Django user: {e}")

    def authenticate_header(self, request: HttpRequest) -> str:
        """
        Return the WWW-Authenticate header to be used for 401 responses.
        """
        return "Bearer"


class InvalidTokenError(Exception):
    """Custom exception for invalid tokens."""

    pass


class SupabaseSessionAuthentication(TokenAuthentication):
    """
    Alternative authentication class that validates Supabase sessions.

    This class is designed for use with session-based authentication
    where the session token is passed in the Authorization header.
    """

    keyword = "Bearer"
    model = None

    def authenticate(self, request: HttpRequest):
        """
        Authenticate the request using Supabase session token.
        """
        auth = get_authorization_header(request).split()  # type: ignore[arg-type]

        if not auth or auth[0].lower() != self.keyword.lower().encode():
            return None

        if len(auth) == 1:
            raise AuthenticationFailed("Invalid token header: No credentials provided.")
        elif len(auth) > 2:
            raise AuthenticationFailed(
                "Invalid token header: Token string should not contain spaces."
            )

        token = auth[1].decode()

        try:
            user = self._validate_token(token)
            return (user, token)
        except Exception as e:
            logger.error(f"Session authentication error: {e}")
            raise AuthenticationFailed("Invalid token")

    def _validate_token(self, token: str) -> Any:
        """
        Validate the Supabase session token.
        """
        # This is a placeholder - implement actual token validation
        # based on your requirements
        raise NotImplementedError("Token validation must be implemented")

    def authenticate_credentials(self, key: str) -> Any:
        """
        Authenticate the given token.
        """
        raise NotImplementedError("Authentication credentials must be implemented")


def validate_supabase_token(token: str) -> Dict[str, Any]:
    """
    Validate a Supabase JWT token and return the decoded payload.

    Args:
        token: The JWT token to validate

    Returns:
        Decoded token payload as a dictionary

    Raises:
        AuthenticationFailed: If token is invalid
    """
    if not token:
        raise AuthenticationFailed("Token is required")

    try:
        # Decode without verification to get payload
        payload = jwt.decode(
            token,
            options={"verify_signature": False},
        )

        # Verify signature if service key is available
        if hasattr(settings, "SUPABASE_SERVICE_KEY") and settings.SUPABASE_SERVICE_KEY:
            jwt.decode(
                token,
                settings.SUPABASE_SERVICE_KEY,
                algorithms=["HS256"],
            )

        return payload

    except PyJWTError as e:
        raise AuthenticationFailed(f"Invalid token: {str(e)}")
    except Exception as e:
        logger.error(f"Token validation error: {e}")
        raise AuthenticationFailed("Invalid token")


def create_or_link_django_user(token_data: Dict[str, Any]) -> Any:
    """
    Create or link a Django user with a Supabase user.

    Args:
        token_data: Decoded JWT token data containing user information

    Returns:
        Django User instance
    """
    supabase_user_id = token_data.get("sub")
    email = token_data.get("email")
    full_name = token_data.get("user_metadata", {}).get("full_name")

    if not supabase_user_id or not email:
        raise AuthenticationFailed("Token missing required user information")

    try:
        user, created = User.objects.get_or_create(
            username=supabase_user_id,
            defaults={
                "email": email,
                "first_name": full_name or "",
            },
        )

        if created:
            user.set_unusable_password()
            user.save()
            logger.info(f"Created Django user for Supabase user: {supabase_user_id}")

        return user

    except Exception as e:
        logger.error(f"Error getting/creating user: {e}")
        raise AuthenticationFailed("Failed to authenticate user")
