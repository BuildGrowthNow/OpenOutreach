"""Tests for remote daemon components."""

from unittest.mock import patch

import pytest

from openoutreach.core.browser_detect import BrowserInfo, detect_browsers, get_preferred_browser
from openoutreach.core.daemon_remote import RemoteDaemon
from openoutreach.core.remote_client import DaemonConfig, RemoteClient


class TestBrowserDetect:
    """Test browser detection functionality."""

    def test_detect_browsers_returns_list(self):
        """Browser detection should return a list."""
        browsers = detect_browsers()
        assert isinstance(browsers, list)

    def test_get_preferred_browser(self):
        """Should return preferred browser or None."""
        browser = get_preferred_browser()
        assert browser is None or isinstance(browser, BrowserInfo)

    @patch("platform.system")
    def test_detect_browsers_windows(self, mock_system):
        """Should detect browsers on Windows."""
        mock_system.return_value = "Windows"
        with patch("pathlib.Path.exists", return_value=True):
            browsers = detect_browsers()
            assert len(browsers) > 0


class TestRemoteClient:
    """Test remote client functionality."""

    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """Client should initialize with correct parameters."""
        client = RemoteClient(
            api_url="https://api.example.com",
            token="test-token",
            daemon_id="test-daemon-id",
        )
        assert client.api_url == "https://api.example.com"
        assert client.daemon_id == "test-daemon-id"
        await client.close()

    @pytest.mark.asyncio
    async def test_daemon_config_parsing(self):
        """DaemonConfig should parse backend response correctly."""
        config_data = {
            "rate_limits": {
                "velocity": 20,
                "daily_connect_limit": 50,
                "daily_message_limit": 100,
                "cooldown_minutes": 5,
            },
            "active_hours": {
                "enabled": True,
                "start_hour": 9,
                "end_hour": 17,
                "timezone": "UTC",
                "days": [1, 2, 3, 4, 5],
            },
            "poll_interval_seconds": 30,
            "heartbeat_interval_seconds": 60,
        }

        config = DaemonConfig(
            velocity=config_data["rate_limits"]["velocity"],
            daily_connect_limit=config_data["rate_limits"]["daily_connect_limit"],
            daily_message_limit=config_data["rate_limits"]["daily_message_limit"],
            cooldown_minutes=config_data["rate_limits"]["cooldown_minutes"],
            enable_active_hours=config_data["active_hours"]["enabled"],
            active_start_hour=config_data["active_hours"]["start_hour"],
            active_end_hour=config_data["active_hours"]["end_hour"],
            active_timezone=config_data["active_hours"]["timezone"],
            active_days=config_data["active_hours"]["days"],
            poll_interval_seconds=config_data["poll_interval_seconds"],
            heartbeat_interval_seconds=config_data["heartbeat_interval_seconds"],
        )

        assert config.velocity == 20
        assert config.enable_active_hours is True
        assert config.active_timezone == "UTC"


class TestRemoteDaemon:
    """Test remote daemon functionality."""

    def test_daemon_initialization(self, tmp_path):
        """Daemon should initialize with correct parameters."""
        daemon = RemoteDaemon(
            api_url="https://api.example.com",
            token="test-token",
            linkedin_profile_id="test-profile",
            data_dir=tmp_path,
        )
        assert daemon.api_url == "https://api.example.com"
        assert daemon.linkedin_profile_id == "test-profile"
        assert daemon.data_dir == tmp_path

    def test_daemon_id_persistence(self, tmp_path):
        """Daemon ID should persist across instantiations."""
        daemon1 = RemoteDaemon(
            api_url="https://api.example.com",
            token="test-token",
            linkedin_profile_id="test-profile",
            data_dir=tmp_path,
        )
        daemon_id1 = daemon1.daemon_id

        daemon2 = RemoteDaemon(
            api_url="https://api.example.com",
            token="test-token",
            linkedin_profile_id="test-profile",
            data_dir=tmp_path,
        )
        daemon_id2 = daemon2.daemon_id

        assert daemon_id1 == daemon_id2

    def test_is_active_time_no_config(self, tmp_path):
        """Active time check should return True when no config."""
        daemon = RemoteDaemon(
            api_url="https://api.example.com",
            token="test-token",
            linkedin_profile_id="test-profile",
            data_dir=tmp_path,
        )
        assert daemon._is_active_time() is True

    def test_is_active_time_disabled(self, tmp_path):
        """Active time check should return True when active hours disabled."""
        daemon = RemoteDaemon(
            api_url="https://api.example.com",
            token="test-token",
            linkedin_profile_id="test-profile",
            data_dir=tmp_path,
        )
        daemon.config = DaemonConfig(
            velocity=20,
            daily_connect_limit=50,
            daily_message_limit=100,
            cooldown_minutes=5,
            enable_active_hours=False,
            active_start_hour=9,
            active_end_hour=17,
            active_timezone="UTC",
            active_days=[1, 2, 3, 4, 5],
            poll_interval_seconds=30,
            heartbeat_interval_seconds=60,
        )
        assert daemon._is_active_time() is True
