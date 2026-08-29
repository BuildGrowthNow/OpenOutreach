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
    assert daemon.client.failed == [("task-1", "lease-1", "idem-1", "rate_limited", "local adapter outcome: rate_limited")]


@pytest.mark.asyncio
async def test_duplicate_outcome_completes_idempotently():
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

        async def post_typed_observation(self, *args):
            return {}

    daemon = SecureRemoteDaemon(
        "https://outreach-api.lengrowth.com", "", "li-1",
        identity=DeviceIdentity._new(),
        channel_executors={"linkedin": lambda task: {"outcome": "duplicate"}},
    )
    daemon.client = FakeClient()
    task = {"task_id": "task-1", "lease_id": "lease-1", "idempotency_key": "idem-1", "channel": "linkedin"}
    await daemon._execute(task, lambda _task: {"outcome": "duplicate"})
    assert daemon.client.completed == [("task-1", "lease-1", "idem-1", {"outcome": "duplicate"})]
    assert daemon.client.failed == []


def test_offline_completion_spool_survives_restart_and_preserves_bounds(tmp_path):
    from openoutreach.desktop.secure_daemon import OfflineCompletionStore

    path = tmp_path / "offline-completions.json"
    first = OfflineCompletionStore(path)
    item = ("task-1", "lease-1", "effect-1", {"outcome": "applied"})
    assert first.append(item) is True

    second = OfflineCompletionStore(path)
    assert second.peek() == item
    assert second.popleft() == item
    assert not path.read_text(encoding="utf-8").strip() or path.read_text(encoding="utf-8") == "[]"


def test_offline_completion_spool_rejects_secret_like_or_oversized_results(tmp_path):
    from openoutreach.desktop.secure_daemon import OfflineCompletionStore

    store = OfflineCompletionStore(tmp_path / "offline-completions.json")
    assert store.append(("task-1", "lease-1", "effect-1", {"access_token": "redacted"})) is False
    assert store.append(("task-2", "lease-2", "effect-2", {"data": "x" * (64 * 1024)})) is False
    assert store.peek() is None


def test_offline_completion_spool_restricts_posix_file_mode(tmp_path):
    import os

    from openoutreach.desktop.secure_daemon import OfflineCompletionStore

    path = tmp_path / "offline-completions.json"
    assert OfflineCompletionStore(path).append(
        ("task-1", "lease-1", "effect-1", {"outcome": "applied"})
    ) is True
    if os.name != "nt":
        assert os.stat(path).st_mode & 0o077 == 0


def test_offline_completion_spool_drops_tampered_unsafe_entries(tmp_path):
    import json

    from openoutreach.desktop.secure_daemon import OfflineCompletionStore

    path = tmp_path / "offline-completions.json"
    path.write_text(json.dumps([
        ["task-1", "lease-1", "effect-1", {"refresh_token": "secret"}],
        ["task-2", "lease-2", "effect-2", {"outcome": "applied"}],
    ]), encoding="utf-8")
    store = OfflineCompletionStore(path)
    assert store.peek() == ("task-2", "lease-2", "effect-2", {"outcome": "applied"})


@pytest.mark.asyncio
async def test_terminal_offline_completion_error_does_not_starve_queue(tmp_path):
    from openoutreach.desktop.secure_daemon import OfflineCompletionStore, SecureRemoteDaemon
    from openoutreach.desktop.device_identity import DeviceIdentity

    class ResponseError(Exception):
        def __init__(self, status_code):
            self.response = type("Response", (), {"status_code": status_code})()

    class FakeClient:
        def __init__(self):
            self.calls = []

        async def complete_task_v2(self, *args):
            self.calls.append(args[0])
            if len(self.calls) == 1:
                raise ResponseError(410)

    daemon = SecureRemoteDaemon(
        "https://outreach-api.lengrowth.com", "", "li-1",
        identity=DeviceIdentity._new(),
    )
    daemon.client = FakeClient()
    daemon._offline_completions = OfflineCompletionStore(tmp_path / "offline.json")
    first = ("task-1", "lease-1", "effect-1", {"outcome": "applied"})
    second = ("task-2", "lease-2", "effect-2", {"outcome": "applied"})
    assert daemon._offline_completions.append(first)
    assert daemon._offline_completions.append(second)

    await daemon._flush_offline_completions()

    assert daemon.client.calls == ["task-1", "task-2"]
    assert daemon._offline_completions.peek() is None
