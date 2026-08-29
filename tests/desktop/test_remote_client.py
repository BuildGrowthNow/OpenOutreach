import httpx
import pytest
from pathlib import Path

from openoutreach.desktop.remote_client import DesktopRemoteClient


@pytest.mark.asyncio
async def test_compatibility_is_available_before_device_exchange():
    client = DesktopRemoteClient("https://outreach-api.example", "", "device")
    try:
        async def request(method, path, **kwargs):
            assert method == "GET"
            assert path == "/api/daemon/v2/compatibility"
            assert "X-Daemon-Signature" not in kwargs["headers"]
            return httpx.Response(
                200, json={"force_update": False},
                request=httpx.Request("GET", "https://outreach-api.example/api/daemon/v2/compatibility"),
            )

        client._client.request = request
        assert (await client.get_compatibility())["force_update"] is False
    finally:
        await client.close()


def test_desktop_client_has_only_v2_operations():
    forbidden = ("get_credentials", "sync_cookies", "get_profile_details",
                 "get_campaign_details", "/api/daemon/tasks/")
    source = DesktopRemoteClient.__module__
    assert source == "openoutreach.desktop.remote_client"
    text = Path(__file__).parents[2].joinpath(
        "openoutreach", "desktop", "remote_client.py"
    ).read_text(encoding="utf-8")
    assert not any(value in text for value in forbidden)
