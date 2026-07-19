"""URL protocol handler for openoutreach:// callback."""

import logging
import sys
import urllib.parse
from typing import Optional

logger = logging.getLogger(__name__)


def parse_auth_callback(url: str) -> Optional[dict]:
    """Parse openoutreach://auth callback URL.

    Args:
        url: URL like "openoutreach://auth?token=xxx&profile_id=yyy"

    Returns:
        Dict with token and profile_id, or None if invalid
    """
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "openoutreach" or parsed.netloc != "auth":
            return None

        params = urllib.parse.parse_qs(parsed.query)
        token = params.get("token", [None])[0]
        profile_id = params.get("profile_id", [None])[0]

        if not token or not profile_id:
            return None

        return {"token": token, "profile_id": profile_id}

    except Exception as e:
        logger.error("Failed to parse auth callback: %s", e)
        return None


def register_protocol_handler():
    """Register openoutreach:// protocol handler (Windows only).

    On macOS, this is handled by the app bundle's Info.plist.
    On Windows, this must be called on first launch to write registry entries.
    """
    if sys.platform != "win32":
        return

    import winreg
    from pathlib import Path

    try:
        # Get executable path
        if getattr(sys, "frozen", False):
            exe_path = sys.executable
        else:
            exe_path = f'{sys.executable} "{Path(__file__).parent / "app.py"}"'

        # Create registry entries
        key_path = r"Software\Classes\openoutreach"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.SetValue(key, "", winreg.REG_SZ, "URL:OpenOutreach Protocol")
            winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")

        with winreg.CreateKey(
            winreg.HKEY_CURRENT_USER, key_path + r"\shell\open\command"
        ) as key:
            winreg.SetValue(key, "", winreg.REG_SZ, f'"{exe_path}" "%1"')

        logger.info("Protocol handler registered")

    except Exception as e:
        logger.warning("Failed to register protocol handler: %s", e)


def handle_protocol_url(url: str, auth_manager) -> bool:
    """Handle openoutreach:// protocol URL.

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
        auth_manager.login(creds["token"], creds["profile_id"])
        logger.info("Login successful via protocol callback")
        return True
    except Exception as e:
        logger.error("Failed to store credentials: %s", e)
        return False
