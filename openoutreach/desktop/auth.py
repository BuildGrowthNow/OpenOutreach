"""Desktop app authentication using system keychain."""

import json

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
            for key in ("token", "refresh_token", "profile_id", "daemon_channel_profile_ids"):
                try:
                    keyring.delete_password(svc, key)
                except keyring.errors.PasswordDeleteError:
                    pass
                except Exception:
                    pass

    def get_daemon_refresh_token(self) -> Optional[str]:
        try:
            return keyring.get_password(SERVICE_NAME, "daemon_refresh_token")
        except Exception:
            return None

    def get_daemon_device_id(self) -> Optional[str]:
        try:
            return keyring.get_password(SERVICE_NAME, "daemon_device_id")
        except Exception:
            return None

    def save_daemon_credentials(self, device_id: str, refresh_token: str) -> None:
        keyring.set_password(SERVICE_NAME, "daemon_device_id", device_id)
        keyring.set_password(SERVICE_NAME, "daemon_refresh_token", refresh_token)

    def clear_daemon_credentials(self) -> None:
        for key in ("daemon_device_id", "daemon_refresh_token"):
            try:
                keyring.delete_password(SERVICE_NAME, key)
            except Exception:
                pass

    def get_daemon_channel_profile_ids(self) -> dict[str, list[str]]:
        """Return non-secret channel bindings saved during device enrollment."""
        try:
            raw = keyring.get_password(SERVICE_NAME, "daemon_channel_profile_ids") or "{}"
            value = json.loads(raw)
            if not isinstance(value, dict):
                return {}
            return {
                str(channel): [str(profile_id) for profile_id in profile_ids]
                for channel, profile_ids in value.items()
                if isinstance(profile_ids, list) and profile_ids
            }
        except Exception:
            return {}

    def save_daemon_channel_profile_ids(self, bindings: dict[str, list[str]]) -> None:
        """Persist only server-issued opaque profile IDs, never credentials."""
        bounded = {
            str(channel): [str(profile_id)[:128] for profile_id in profile_ids[:20]]
            for channel, profile_ids in bindings.items()
            if isinstance(profile_ids, list) and profile_ids
        }
        keyring.set_password(
            SERVICE_NAME, "daemon_channel_profile_ids",
            json.dumps(bounded, sort_keys=True),
        )
