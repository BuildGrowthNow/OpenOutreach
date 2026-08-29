"""Detect user's installed browsers for desktop daemon.

Supports Chrome, Edge, and Safari (macOS only). Used by the remote
daemon to automatically select the best available browser for automation.
"""

from __future__ import annotations

import logging
import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class BrowserInfo:
    """Information about a detected browser."""

    name: str  # "chrome" | "edge" | "safari"
    channel: str  # Playwright channel name
    path: Optional[str]  # Executable path
    version: Optional[str]


def detect_browsers() -> list[BrowserInfo]:
    """Detect installed browsers on the system.

    Returns:
        List of detected browsers with their information.
    """
    browsers = []
    system = platform.system()

    if system == "Darwin":  # macOS
        # Chrome
        chrome_path = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        if chrome_path.exists():
            browsers.append(
                BrowserInfo(
                    name="chrome",
                    channel="chrome",
                    path=str(chrome_path),
                    version=_get_mac_app_version("/Applications/Google Chrome.app"),
                )
            )

        # Edge
        edge_path = Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge")
        if edge_path.exists():
            browsers.append(
                BrowserInfo(
                    name="edge",
                    channel="msedge",
                    path=str(edge_path),
                    version=_get_mac_app_version("/Applications/Microsoft Edge.app"),
                )
            )

        # Safari (always present on macOS)
        browsers.append(
            BrowserInfo(
                name="safari",
                channel="webkit",  # Playwright uses webkit for Safari
                path="/Applications/Safari.app",
                version=None,
            )
        )

    elif system == "Windows":
        # Chrome
        chrome_paths = [
            Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe",
            Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
            Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
        ]
        for path in chrome_paths:
            if path.exists():
                browsers.append(
                    BrowserInfo(
                        name="chrome",
                        channel="chrome",
                        path=str(path),
                        version=None,
                    )
                )
                break

        # Edge (usually pre-installed on Windows 10/11)
        edge_paths = [
            Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
            Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
        ]
        for path in edge_paths:
            if path.exists():
                browsers.append(
                    BrowserInfo(
                        name="edge",
                        channel="msedge",
                        path=str(path),
                        version=None,
                    )
                )
                break

    return browsers


def get_preferred_browser() -> Optional[BrowserInfo]:
    """Get the best available browser for automation.

    Preference order: Chrome > Edge > Safari

    Returns:
        BrowserInfo for the preferred browser, or None if no supported browser found.
    """
    browsers = detect_browsers()

    # Preference: Chrome > Edge > Safari
    for name in ["chrome", "edge", "safari"]:
        for browser in browsers:
            if browser.name == name:
                return browser

    return browsers[0] if browsers else None


def _get_mac_app_version(app_path: str) -> Optional[str]:
    """Get version from macOS app bundle.

    Args:
        app_path: Path to .app bundle

    Returns:
        Version string or None if not available
    """
    try:
        result = subprocess.run(
            [
                "defaults",
                "read",
                f"{app_path}/Contents/Info",
                "CFBundleShortVersionString",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception as e:
        logger.debug("Could not get app version for %s: %s", app_path, type(e).__name__)
        return None
