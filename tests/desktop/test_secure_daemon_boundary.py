"""Static boundary tests for the distributed desktop entry point."""

from pathlib import Path

import pytest


ROOT = Path(__file__).parents[2]


def test_secure_desktop_daemon_has_no_database_imports():
    source = (ROOT / "openoutreach" / "desktop" / "secure_daemon.py").read_text(encoding="utf-8")
    forbidden = ("pymongo", "openoutreach.mongodb", "SECRET_KEY", "LLM_API_KEY", "MONGODB_URI")
    assert not any(value in source for value in forbidden)


def test_distributed_v2_client_does_not_import_legacy_server_client():
    source = (ROOT / "openoutreach" / "desktop" / "remote_client.py").read_text(encoding="utf-8")
    forbidden = ("openoutreach.core.remote_client", "openoutreach.api_v2.daemon_auth",
                 "openoutreach.mongodb", "MONGODB_URI", "SECRET_KEY")
    assert not any(value in source for value in forbidden)


def test_pyinstaller_spec_excludes_database_and_legacy_daemon():
    source = (ROOT / "desktop" / "openoutreach.spec").read_text(encoding="utf-8")
    for marker in (
        '"pymongo"',
        '"openoutreach.mongodb"',
        '"openoutreach.core.daemon_remote"',
        '"openoutreach.core.remote_client"',
    ):
        assert marker in source


@pytest.mark.asyncio
async def test_secure_daemon_requires_explicit_profile_binding_per_channel():
    from openoutreach.desktop.secure_daemon import SecureRemoteDaemon
    from openoutreach.desktop.device_identity import DeviceIdentity

    daemon = SecureRemoteDaemon(
        "https://outreach-api.lengrowth.com", "", "li-1",
        identity=DeviceIdentity._new(),
        channel_executors={"linkedin": lambda task: {}, "whatsapp": lambda task: {}},
        channel_profile_ids={"whatsapp": "wa-1"},
    )
    try:
        assert daemon.channel_profile_ids == {"linkedin": "li-1", "whatsapp": "wa-1"}
    finally:
        await daemon.stop()


def test_desktop_api_url_is_allowlisted_against_ssrf():
    from openoutreach.desktop.config import AppConfig

    assert AppConfig(api_url="https://outreach-api.lengrowth.com").api_url == "https://outreach-api.lengrowth.com"
    assert AppConfig(api_url="http://localhost:8001").api_url == "http://localhost:8001"
    for value in (
        "https://169.254.169.254/latest/meta-data",
        "https://attacker.example/",
        "https://user:password@outreach-api.lengrowth.com",
        "file:///etc/passwd",
    ):
        try:
            AppConfig(api_url=value)
        except ValueError:
            continue
        raise AssertionError(f"unapproved API URL accepted: {value}")


@pytest.mark.asyncio
async def test_adapter_failure_outcomes_are_reported_as_failures():
    from openoutreach.desktop.device_identity import DeviceIdentity
    from openoutreach.desktop.secure_daemon import SecureRemoteDaemon

    class FakeClient:
        def __init__(self):
            self.completed = []
            self.failed = []

        async def complete_task_v2(self, *args):
            self.completed.append(args)

        async def fail_task_v2(self, *args):
            self.failed.append(args)

    daemon = SecureRemoteDaemon(
        "https://outreach-api.lengrowth.com", "", "li-1",
        identity=DeviceIdentity._new(),
        channel_executors={"linkedin": lambda task: {"outcome": "rate_limited"}},
    )
    daemon.client = FakeClient()
    task = {"task_id": "task-1", "lease_id": "lease-1", "idempotency_key": "idem-1", "channel": "linkedin"}
    await daemon._execute(task, lambda _task: {"outcome": "rate_limited"})
    assert daemon.client.completed == []
    assert daemon.client.failed == [("task-1", "lease-1", "rate_limited", "local adapter outcome: rate_limited")]
