"""
Supabase JWT Authentication for Django REST Framework

This module provides custom authentication classes that validate Supabase JWT tokens.
It also handles the automatic creation/linking of Django users with Supabase users.
"""

import logging
from datetime import datetime
from typing import Optional, Tuple, Any, Dict, Union

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
from jwt.algorithms import ECAlgorithm, RSAAlgorithm, HMACAlgorithm
import requests
import json

from openoutreach.mongodb.models import SupabaseUser
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

User = get_user_model()
logger = logging.getLogger(__name__)


def get_supabase_jwks():
    """Fetch Supabase's public keys from JWKS endpoint."""
    supabase_url = getattr(settings, 'SUPABASE_URL', None)
    if not supabase_url:
        logger.warning("[SupabaseAuth] SUPABASE_URL not configured")
        return None
    # Supabase exposes JWKS at a few possible endpoints depending on project config.
    # Try them in order until one succeeds.
    candidates = [
        f"{supabase_url}/auth/v1/certs",
        f"{supabase_url}/auth/v1/.well-known/jwks.json",
        f"{supabase_url}/.well-known/jwks.json",
        f"{supabase_url}/auth/v1/jwks",
        f"{supabase_url}/rest/v1/jwks",
    ]

    for jwks_uri in candidates:
        try:
            response = requests.get(jwks_uri, timeout=5)
            response.raise_for_status()
            logger.info(f"[SupabaseAuth] Fetched JWKS from {jwks_uri}")
            return response.json()
        except Exception as e:
                    # Use print to ensure message appears in container logs even if logging is misconfigured
                    print(f"[SupabaseAuth] JWKS fetch failed for {jwks_uri}: {e}")
                    logger.debug(f"[SupabaseAuth] JWKS fetch failed for {jwks_uri}: {e}")

    print(f"[SupabaseAuth] Failed to fetch JWKS from any known Supabase endpoint for {supabase_url}")
    logger.error(f"[SupabaseAuth] Failed to fetch JWKS from any known Supabase endpoint for {supabase_url}")
    return None


def decode_jwk_key(key: Dict[str, Any]) -> Optional[Any]:
    """
    Decode a JWK key into a key object or bytes suitable for `jwt.decode()`.

    Returns a PEM/key object or None if decoding fails.
    """
    try:
        kty = key.get('kty')
        if not kty:
            return None

        # Convert JWK dict to a PEM/public key object accepted by PyJWT
        jwk_json = json.dumps(key)
        if kty == 'RSA':
            return RSAAlgorithm.from_jwk(jwk_json)
        elif kty == 'EC':
            return ECAlgorithm.from_jwk(jwk_json)
        elif kty == 'oct':
            # symmetric key (HMAC)
            # the 'k' field is base64url-encoded key material
            k = key.get('k')
            if k:
                return HMACAlgorithm.from_jwk(jwk_json)
        return None
    except Exception as e:
        logger.error(f"[SupabaseAuth] Failed to decode JWK key: {e}")
        return None


def verify_token_with_jwks(token: str) -> Dict[str, Any]:
    """
    Verify a Supabase JWT token using the JWKS endpoint.
    Supports HS256, RS256, and ES256 algorithms.
    
    Returns the decoded payload if verification succeeds.
    Raises InvalidTokenError if verification fails.
    """
    if not token:
        raise InvalidTokenError("Token is empty")
    
    # First decode without verification to inspect
    try:
        # Decode header to get algorithm
        header = jwt.get_unverified_header(token)
        alg = header.get('alg', 'HS256')
        kid = header.get('kid')
        logger.info(f"[SupabaseAuth] Token algorithm: {alg}, kid: {kid}")
    except Exception as e:
        raise InvalidTokenError(f"Failed to decode token header: {e}")
    
    # Decode payload without verification
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        logger.info(f"[SupabaseAuth] Token payload decoded successfully")
    except Exception as e:
        raise InvalidTokenError(f"Failed to decode token payload: {e}")
    
    # Check if SUPABASE_SERVICE_KEY is available for HS256
    service_key = getattr(settings, 'SUPABASE_SERVICE_KEY', None)
    if service_key and alg.startswith('HS'):
        try:
            payload = jwt.decode(
                token,
                service_key,
                algorithms=[alg],
                options={"verify_aud": False},
            )
            logger.info(f"[SupabaseAuth] Token verified successfully with {alg} using SERVICE_KEY")
            return payload
        except PyJWTError as e:
            logger.warning(f"[SupabaseAuth] {alg} verification with SERVICE_KEY failed: {e}")
    
    # Try JWKS for RS256/ES256 or if SERVICE_KEY verification failed
    if alg.startswith('RS') or alg.startswith('ES'):
        jwks = get_supabase_jwks()
        if jwks:
            # Find the key in JWKS
            key_obj = None
            if kid:
                for key in jwks.get('keys', []):
                    if key.get('kid') == kid:
                        key_obj = decode_jwk_key(key)
                        break
            
            if key_obj:
                try:
                    # Get the allowed algorithms based on the token's algorithm
                    if alg == 'RS256':
                        allowed_algorithms = ['RS256']
                    elif alg == 'ES256':
                        allowed_algorithms = ['ES256']
                    elif alg == 'RS384':
                        allowed_algorithms = ['RS384']
                    elif alg == 'RS512':
                        allowed_algorithms = ['RS512']
                    elif alg == 'ES384':
                        allowed_algorithms = ['ES384']
                    elif alg == 'ES512':
                        allowed_algorithms = ['ES512']
                    else:
                        allowed_algorithms = [alg]
                    
                    payload = jwt.decode(
                        token,
                        key_obj,
                        algorithms=allowed_algorithms,  # type: ignore[arg-type]
                        options={"verify_aud": False},
                    )
                    logger.info(f"[SupabaseAuth] Token verified successfully with {alg} using JWKS")
                    return payload
                except PyJWTError as e:
                    raise InvalidTokenError(f"{alg} verification failed: {e}")
            
            logger.warning(f"[SupabaseAuth] No matching key found in JWKS for kid: {kid}")
    
    raise InvalidTokenError("No suitable verification method found")


class SupabaseJWTAuthentication(BaseAuthentication):
    """
    Custom JWT authentication class that validates Supabase JWT tokens.
    
    This class now supports:
    1. Automatic detection of token algorithm (HS256, RS256, ES256)
    2. Verification using Supabase's JWKS endpoint (public keys)
    3. Fallback to SERVICE_KEY for HS256 tokens
    4. Detailed logging for debugging
    
    Authentication header format: Authorization: Bearer <supabase_jwt_token>
    """

    def authenticate(self, request: HttpRequest) -> Optional[Tuple[Any, Any]]:
        """
        Authenticate a request using Supabase JWT.

        Returns a tuple of (user, token) if authentication is successful.
        Returns None if authentication should be ignored.

        Raises AuthenticationFailed if authentication fails.
        """
        # Get the Authorization header
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        logger.info(f"[SupabaseJWTAuth] Checking auth header: '{auth_header[:50] if auth_header else '(empty)'}...'")
        print(f"[SupabaseJWTAuth] Raw Authorization header: {auth_header[:200]}")
        
        if not auth_header:
            logger.debug("[SupabaseJWTAuth] No Authorization header found, skipping auth")
            return None

        # Check if it's a Bearer token
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            logger.debug(f"[SupabaseJWTAuth] Invalid Bearer format: '{auth_header}'")
            return None

        access_token = parts[1]

        if not access_token:
            logger.debug("[SupabaseJWTAuth] Empty access token")
            return None

        logger.debug(f"[SupabaseJWTAuth] Token prefix: {access_token[:30]}...")
        logger.info("[SupabaseJWTAuth] Attempting token verification")

        try:
            # Log token header for debugging
            try:
                th = jwt.get_unverified_header(access_token)
                print(f"[SupabaseJWTAuth] Token header: {th}")
                logger.debug(f"Token header: {th}")
            except Exception as _e:
                print(f"[SupabaseJWTAuth] Failed to get token header: {_e}")

            # Verify and decode the token using JWKS
            user = self._authenticate_token(access_token)
            logger.info(f"[SupabaseJWTAuth] Successfully authenticated user: {user.username if hasattr(user, 'username') else user}")
            return (user, access_token)

        except InvalidTokenError as e:
            logger.error(f"[SupabaseJWTAuth] Invalid token error: {e}")
            raise AuthenticationFailed(str(e))
        except Exception as e:
            logger.error(f"[SupabaseJWTAuth] Authentication error: {e}", exc_info=True)
            raise AuthenticationFailed(f"Invalid token: {str(e)}")

    def _authenticate_token(self, token: str) -> Any:
        """
        Verify and decode the Supabase JWT token using JWKS.
        
        This method uses JWKS (JSON Web Key Set) to verify the token signature,
        which supports HS256, RS256, and ES256 algorithms used by Supabase.
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

            # Verify token signature using JWKS
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
        Verify the JWT signature using Supabase's JWKS endpoint.
        
        This method automatically detects the algorithm and uses the
        appropriate verification method.
        """
        try:
            # Use the new JWKS-based verification
            payload = verify_token_with_jwks(token)
            logger.info("[SupabaseJWTAuth] Signature verification successful")
        except InvalidTokenError as e:
            raise

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
        # Use JWKS for verification
        payload = verify_token_with_jwks(token)
        return payload

    except InvalidTokenError as e:
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