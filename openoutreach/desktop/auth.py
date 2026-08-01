"""Desktop app authentication using system keychain."""

from typing import Optional

import keyring

SERVICE_NAME = "Lengrowth"
_LEGACY_SERVICE_NAME = "OpenOutreach"


class AuthManager:
    """Manages authentication state using system keychain."""

    def __init__(self, config):
        self.config = config

    def is_logged_in(self) -> bool:
        """Check if user has valid credentials stored."""
        return self.get_token() is not None

    def get_token(self) -> Optional[str]:
        """Get stored JWT token, migrating from legacy service name if needed."""
        try:
            token = keyring.get_password(SERVICE_NAME, "token")
            if token:
                return token
            # Migrate credentials stored under the old "OpenOutreach" service name
            legacy_token = keyring.get_password(_LEGACY_SERVICE_NAME, "token")
            if legacy_token:
                refresh = keyring.get_password(_LEGACY_SERVICE_NAME, "refresh_token")
                profile = keyring.get_password(_LEGACY_SERVICE_NAME, "profile_id")
                self.login(legacy_token, profile or "", refresh_token=refresh)
                try:
                    keyring.delete_password(_LEGACY_SERVICE_NAME, "token")
                    keyring.delete_password(_LEGACY_SERVICE_NAME, "refresh_token")
                    keyring.delete_password(_LEGACY_SERVICE_NAME, "profile_id")
                except Exception:
                    pass
                return legacy_token
            return None
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
        """Remove stored credentials from all service name variants."""
        for svc in (SERVICE_NAME, _LEGACY_SERVICE_NAME):
            for key in ("token", "refresh_token", "profile_id"):
                try:
                    keyring.delete_password(svc, key)
                except keyring.errors.PasswordDeleteError:
                    pass
                except Exception:
                    pass
