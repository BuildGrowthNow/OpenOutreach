"""Desktop app authentication using system keychain."""

from typing import Optional

import keyring

SERVICE_NAME = "OpenOutreach"


class AuthManager:
    """Manages authentication state using system keychain."""

    def __init__(self, config):
        self.config = config

    def is_logged_in(self) -> bool:
        """Check if user has valid credentials stored."""
        return self.get_token() is not None

    def get_token(self) -> Optional[str]:
        """Get stored JWT token."""
        try:
            return keyring.get_password(SERVICE_NAME, "token")
        except Exception:
            return None

    def get_refresh_token(self) -> Optional[str]:
        """Get stored refresh token."""
        try:
            return keyring.get_password(SERVICE_NAME, "refresh_token")
        except Exception:
            return None

    def get_profile_id(self) -> Optional[str]:
        """Get stored LinkedIn profile ID."""
        try:
            return keyring.get_password(SERVICE_NAME, "profile_id")
        except Exception:
            return None

    def login(self, token: str, profile_id: str, refresh_token: Optional[str] = None):
        """Store authentication credentials."""
        keyring.set_password(SERVICE_NAME, "token", token)
        keyring.set_password(SERVICE_NAME, "profile_id", profile_id)
        if refresh_token:
            keyring.set_password(SERVICE_NAME, "refresh_token", refresh_token)

    def update_token(self, token: str):
        """Update only the JWT token (after refresh)."""
        keyring.set_password(SERVICE_NAME, "token", token)

    def logout(self):
        """Remove stored credentials."""
        try:
            keyring.delete_password(SERVICE_NAME, "token")
        except keyring.errors.PasswordDeleteError:
            pass

        try:
            keyring.delete_password(SERVICE_NAME, "refresh_token")
        except keyring.errors.PasswordDeleteError:
            pass

        try:
            keyring.delete_password(SERVICE_NAME, "profile_id")
        except keyring.errors.PasswordDeleteError:
            pass
