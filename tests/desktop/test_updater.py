"""Test desktop updater functionality."""

import hashlib
import json
from unittest.mock import AsyncMock, patch

import pytest

from openoutreach.desktop.updater import (
    download_update,
    load_pending_update,
    _get_platform_asset_name,
    _get_platform_asset_names,
    check_for_updates,
    prompt_update,
)


def test_get_platform_asset_name_windows():
    """Test Windows asset name generation."""
    with patch("platform.system", return_value="Windows"):
        assert _get_platform_asset_name("1.2.3") == "Lengrowth-1.2.3-Setup.exe"


def test_prompt_update_redacts_query_parameters_from_log(caplog):
    with patch("openoutreach.desktop.updater.webbrowser.open") as open_browser:
        with caplog.at_level("INFO", logger="openoutreach.desktop.updater"):
            prompt_update({"download_url": "https://dl.example.test/app.exe?token=secret"})

    open_browser.assert_called_once_with("https://dl.example.test/app.exe?token=secret")
    assert "token=secret" not in caplog.text
    assert "https://dl.example.test/app.exe" in caplog.text


def test_get_platform_asset_name_macos():
    """Test macOS asset name generation."""
    with patch("platform.system", return_value="Darwin"):
        assert _get_platform_asset_name("1.2.3") == "Lengrowth-1.2.3.dmg"


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
        "tag_name": "desktop-v2.1.1",
        "html_url": "https://github.com/test/releases/tag/v2.1.1",
        "body": "Release notes",
        "assets": [
            {
        "name": "OpenOutreach-2.1.1.dmg",
        "browser_download_url": "https://github.com/test/releases/download/v2.1.1/OpenOutreach-2.1.1.dmg",
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
            assert result["version"] == "2.1.1"
            assert "download_url" in result
            assert result["tag_name"] == "desktop-v2.1.1"


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
        "tag_name": "desktop-v2.1.1",
        "html_url": "https://github.com/test/releases/tag/v2.1.1",
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
            assert result["download_url"] == "https://github.com/test/releases/tag/v2.1.1"


@pytest.mark.asyncio
async def test_download_update_requires_sha256_digest():
    """Unsigned/unhashed update downloads must fail closed."""
    with patch("httpx.AsyncClient") as mock_client:
        assert await download_update("https://example.invalid/update.exe") is None
        mock_client.assert_not_called()

    with patch("httpx.AsyncClient") as mock_client:
        assert await download_update(
            "https://example.invalid/update.exe", expected_digest="not-a-digest"
        ) is None
        mock_client.assert_not_called()


class _StreamResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    def raise_for_status(self):
        return None

    async def aiter_bytes(self, chunk_size=65536):
        yield self.payload


class _DownloadClient:
    def __init__(self, payload: bytes):
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    def stream(self, method, url):
        return _StreamResponse(self.payload)


@pytest.mark.asyncio
async def test_download_update_verifies_digest_and_replaces_atomically(tmp_path):
    payload = b"verified update payload"
    expected = hashlib.sha256(payload).hexdigest()
    pending_file = tmp_path / "pending_update.json"

    with patch("openoutreach.desktop.updater._PENDING_UPDATE_FILE", pending_file):
        with patch("httpx.AsyncClient", return_value=_DownloadClient(payload)):
            result = await download_update("https://example.invalid/update.exe", expected_digest=f"sha256:{expected}")

    assert result == str(tmp_path / "Lengrowth_update.exe")
    assert (tmp_path / "Lengrowth_update.exe").read_bytes() == payload
    assert not (tmp_path / "Lengrowth_update.exe.part").exists()


@pytest.mark.asyncio
async def test_download_update_removes_digest_mismatch(tmp_path):
    payload = b"tampered update payload"
    pending_file = tmp_path / "pending_update.json"
    expected = hashlib.sha256(b"different payload").hexdigest()

    with patch("openoutreach.desktop.updater._PENDING_UPDATE_FILE", pending_file):
        with patch("httpx.AsyncClient", return_value=_DownloadClient(payload)):
            result = await download_update("https://example.invalid/update.exe", expected_digest=expected)

    assert result is None
    assert not (tmp_path / "Lengrowth_update.exe").exists()
    assert not (tmp_path / "Lengrowth_update.exe.part").exists()


def test_load_pending_update_rechecks_digest(tmp_path):
    pending_file = tmp_path / "pending_update.json"
    update_file = tmp_path / "Lengrowth_update.exe"
    update_file.write_bytes(b"trusted bytes")
    digest = hashlib.sha256(update_file.read_bytes()).hexdigest()

    with patch("openoutreach.desktop.updater._PENDING_UPDATE_FILE", pending_file):
        pending_file.write_text(json.dumps({"exe_path": str(update_file), "digest": digest}))
        pending = load_pending_update()
        assert pending is not None
        assert pending["exe_path"] == str(update_file)

        update_file.write_bytes(b"tampered bytes")
        assert load_pending_update() is None
        assert not pending_file.exists()
