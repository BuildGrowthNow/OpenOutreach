"""Test desktop updater functionality."""

from unittest.mock import AsyncMock, patch

import pytest

from openoutreach.desktop.updater import (
    _get_platform_asset_name,
    _get_platform_asset_names,
    check_for_updates,
)


def test_get_platform_asset_name_windows():
    """Test Windows asset name generation."""
    with patch("platform.system", return_value="Windows"):
        assert _get_platform_asset_name("1.2.3") == "OpenOutreach-1.2.3-Setup.exe"


def test_get_platform_asset_name_macos():
    """Test macOS asset name generation."""
    with patch("platform.system", return_value="Darwin"):
        assert _get_platform_asset_name("1.2.3") == "OpenOutreach-1.2.3.dmg"


def test_get_platform_asset_name_linux():
    """Test Linux returns empty (not supported)."""
    with patch("platform.system", return_value="Linux"):
        assert _get_platform_asset_name("1.2.3") == ""


def test_platform_asset_names_accept_current_and_legacy_branding():
    with patch("platform.system", return_value="Windows"):
        assert _get_platform_asset_names("1.2.3") == (
            "Lengrowth-1.2.3-Setup.exe",
            "OpenOutreach-1.2.3-Setup.exe",
        )


@pytest.mark.asyncio
async def test_check_for_updates_newer_version():
    """Test update detection when newer version available."""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = lambda: {
        "tag_name": "desktop-v2.0.0",
        "html_url": "https://github.com/test/releases/tag/v2.0.0",
        "body": "Release notes",
        "assets": [
            {
                "name": "OpenOutreach-2.0.0.dmg",
                "browser_download_url": "https://github.com/test/releases/download/v2.0.0/OpenOutreach-2.0.0.dmg",
            }
        ],
    }

    with patch("openoutreach.desktop.updater.__version__", "1.0.0"):
        with patch("httpx.AsyncClient") as mock_client:
            mock_ctx = AsyncMock()
            mock_ctx.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_ctx

            result = await check_for_updates()

            assert result is not None
            assert result["version"] == "2.0.0"
            assert "download_url" in result
            assert result["tag_name"] == "desktop-v2.0.0"


@pytest.mark.asyncio
async def test_check_for_updates_same_version():
    """Test no update when version is same."""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = lambda: {
        "tag_name": "desktop-v1.0.0",
        "html_url": "https://github.com/test/releases/tag/v1.0.0",
        "body": "Release notes",
        "assets": [],
    }

    with patch("openoutreach.desktop.updater.__version__", "1.0.0"):
        with patch("httpx.AsyncClient") as mock_client:
            mock_ctx = AsyncMock()
            mock_ctx.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_ctx

            result = await check_for_updates()

            assert result is None


@pytest.mark.asyncio
async def test_check_for_updates_network_error():
    """Test graceful handling of network errors."""
    with patch("httpx.AsyncClient") as mock_client:
        mock_ctx = AsyncMock()
        mock_ctx.get = AsyncMock(side_effect=Exception("Network error"))
        mock_client.return_value.__aenter__.return_value = mock_ctx

        result = await check_for_updates()

        assert result is None


@pytest.mark.asyncio
async def test_check_for_updates_fallback_to_release_page():
    """Test fallback to release page when asset not found."""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = lambda: {
        "tag_name": "desktop-v2.0.0",
        "html_url": "https://github.com/test/releases/tag/v2.0.0",
        "body": "Release notes",
        "assets": [
            {
                "name": "some-other-file.zip",
                "browser_download_url": "https://github.com/test/other.zip",
            }
        ],
    }

    with patch("openoutreach.desktop.updater.__version__", "1.0.0"):
        with patch("httpx.AsyncClient") as mock_client:
            mock_ctx = AsyncMock()
            mock_ctx.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_ctx

            result = await check_for_updates()

            assert result is not None
            # Should fallback to release page URL
            assert result["download_url"] == "https://github.com/test/releases/tag/v2.0.0"
