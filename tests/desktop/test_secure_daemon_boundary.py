"""Static boundary tests for the distributed desktop entry point."""

from pathlib import Path


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


def test_secure_daemon_requires_explicit_profile_binding_per_channel():
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
        import asyncio
        asyncio.run(daemon.stop())


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
