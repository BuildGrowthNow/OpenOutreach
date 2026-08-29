"""URL protocol handler for lengrowth:// callback."""

import logging
import sys
import urllib.parse
from typing import Optional

logger = logging.getLogger(__name__)


def parse_auth_callback(url: str) -> Optional[dict]:
    """Parse lengrowth://auth callback URL.

    Args:
        url: A legacy callback URL from a pre-bridge client. Current clients
             must use the in-process bridge and must not place credentials in
             custom-protocol URLs, browser history, or process arguments.

    Returns:
        Legacy credential dict, or None if invalid. Callers should keep this
        path behind minimum-secure-version enforcement during migration.
    """
    try:
        parsed = urllib.parse.urlparse(url)
        # Accept the pre-2.0 scheme for already-installed clients, while all
        # new app registrations and callbacks use the branded scheme.
        if parsed.scheme not in {"lengrowth", "openoutreach"} or parsed.netloc != "auth":
            return None

        params = urllib.parse.parse_qs(parsed.query)
        token = params.get("token", [None])[0]
        profile_id = params.get("profile_id", [None])[0]

        if not token or not profile_id:
            return None

        return {
            "token": token,
            "refresh_token": params.get("refresh_token", [None])[0],
            "profile_id": profile_id,
        }

    except Exception as e:
        logger.error("Failed to parse auth callback; exception_type=%s", type(e).__name__)
        return None


def register_protocol_handler():
    """Register lengrowth:// protocol handler (Windows only).

    On macOS, this is handled by the app bundle's Info.plist.
    On Windows, this must be called on first launch to write registry entries.
    """
    if sys.platform != "win32":
        return

    import winreg
    from pathlib import Path

    try:
        if getattr(sys, "frozen", False):
            exe_path = sys.executable
        else:
            exe_path = f'{sys.executable} "{Path(__file__).parent / "app.py"}"'

        desired_command = f'"{exe_path}" "%1"'
        cmd_key_path = r"Software\Classes\lengrowth\shell\open\command"

        # Only write if the command value is missing or points to a different exe
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, cmd_key_path
            ) as key:
                current, _ = winreg.QueryValueEx(key, "")
                if current == desired_command:
                    return  # Already registered correctly
        except FileNotFoundError:
            pass  # Key doesn't exist yet - proceed with creation

        key_path = r"Software\Classes\lengrowth"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.SetValue(key, "", winreg.REG_SZ, "URL:Lengrowth Protocol")
            winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")

        with winreg.CreateKey(
            winreg.HKEY_CURRENT_USER, cmd_key_path
        ) as key:
            winreg.SetValue(key, "", winreg.REG_SZ, desired_command)

        logger.info("Protocol handler registered")

    except Exception as e:
        logger.warning("Failed to register protocol handler: %s", type(e).__name__)


def handle_protocol_url(url: str, auth_manager) -> bool:
    """Handle lengrowth:// protocol URL.

    Args:
        url: Protocol URL from command line
        auth_manager: AuthManager instance to store credentials

    Returns:
        True if handled successfully, False otherwise
    """
    creds = parse_auth_callback(url)
    if not creds:
        return False

    try:
        auth_manager.login(
            creds["token"],
            creds.get("profile_id") or "",
            refresh_token=creds.get("refresh_token"),
        )
        logger.info("Login successful via protocol callback")
        return True
    except Exception as e:
        logger.error("Failed to store credentials; exception_type=%s", type(e).__name__)
        return False
