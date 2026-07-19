"""Simple auto-updater using GitHub releases."""

import logging
import platform
import webbrowser
from typing import Optional

import httpx
from packaging import version

from openoutreach.desktop.__version__ import __version__

logger = logging.getLogger(__name__)

GITHUB_RELEASES_URL = (
    "https://api.github.com/repos/Lengrowth/outbound/releases/latest"
)


def _get_platform_asset_name() -> str:
    """Get the expected asset filename for current platform."""
    system = platform.system().lower()
    if system == "darwin":
        return "Lengrowth-macOS.dmg"
    elif system == "windows":
        return "Lengrowth-Windows-Setup.exe"
    return ""


async def check_for_updates() -> Optional[dict]:
    """Check GitHub for newer version.

    Returns:
        Dict with version, download_url, platform_download_url, and notes if update available
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(GITHUB_RELEASES_URL)
            if response.status_code != 200:
                logger.warning("Failed to check for updates: %s", response.status_code)
                return None

            release = response.json()
            tag_name = release["tag_name"]

            # Tags are like "v1.0.1-a3f2b1c" — extract semver prefix
            latest_version = tag_name.lstrip("v").split("-")[0]

            if version.parse(latest_version) > version.parse(__version__):
                # Match platform asset by fixed name
                assets = release.get("assets", [])
                expected_name = _get_platform_asset_name()
                platform_url = None

                if expected_name:
                    for asset in assets:
                        if asset["name"] == expected_name:
                            platform_url = asset["browser_download_url"]
                            break

                # Fallback to release page if specific asset not found
                download_url = platform_url or release["html_url"]

                return {
                    "version": latest_version,
                    "download_url": download_url,
                    "release_page": release["html_url"],
                    "notes": release.get("body", ""),
                    "tag_name": tag_name,
                }

            return None

    except Exception as e:
        logger.warning("Update check failed: %s", e)
        return None


def prompt_update(update_info: dict):
    """Open browser to download the update.

    Opens platform-specific download URL if available, otherwise release page.
    """
    try:
        url = update_info.get("download_url", update_info.get("release_page"))
        if url:
            logger.info("Opening update URL: %s", url)
            webbrowser.open(url)
        else:
            logger.error("No download URL available in update info")
    except Exception as e:
        logger.error("Failed to open update URL: %s", e)
