"""Desktop app authentication using system keychain."""

from typing import Optional

import keyring

SERVICE_NAME = "Lengrowth"


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

    def get_profile_id(self) -> Optional[str]:
        """Get stored LinkedIn profile ID."""
        try:
            return keyring.get_password(SERVICE_NAME, "profile_id")
        except Exception:
            return None

    def login(self, token: str, profile_id: str):
        """Store authentication credentials."""
        keyring.set_password(SERVICE_NAME, "token", token)
        keyring.set_password(SERVICE_NAME, "profile_id", profile_id)

    def logout(self):
        """Remove stored credentials."""
        try:
            keyring.delete_password(SERVICE_NAME, "token")
        except keyring.errors.PasswordDeleteError:
            pass

        try:
            keyring.delete_password(SERVICE_NAME, "profile_id")
        except keyring.errors.PasswordDeleteError:
            pass
