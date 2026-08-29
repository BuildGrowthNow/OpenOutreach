from pathlib import Path
import json

from scripts import verify_production_ready as verifier


def test_django_import_scanner_is_native_and_precise(tmp_path: Path):
    source = tmp_path / "openoutreach"
    source.mkdir()
    (source / "safe.py").write_text("# from django import forms\nvalue = 1\n", encoding="utf-8")
    assert verifier._DJANGO_IMPORT.search((source / "safe.py").read_text(encoding="utf-8")) is None

    (source / "unsafe.py").write_text("from django.conf import settings\n", encoding="utf-8")
    assert verifier._DJANGO_IMPORT.search((source / "unsafe.py").read_text(encoding="utf-8"))


def test_production_prerequisites_require_independent_application_secrets(monkeypatch, capsys):
    for name in (
        "SECRET_KEY",
        "JWT_SECRET_KEY",
        "COOKIE_ENCRYPTION_KEY",
        "MONGODB_URI",
        "OPENOUTREACH_MONGODB_URI",
        "MONGODB_NAME",
        "OPENOUTREACH_MONGODB_NAME",
        "DAEMON_JWT_PRIVATE_KEY",
        "DAEMON_JWT_PRIVATE_KEY_B64",
        "DAEMON_JWT_PUBLIC_KEY",
        "DAEMON_JWT_PUBLIC_KEY_B64",
    ):
        monkeypatch.delenv(name, raising=False)

    assert verifier.check_production_prerequisites() is False
    output = capsys.readouterr().out
    assert "independent JWT signing key" in output
    assert "independent cookie encryption key" in output


def test_cloud_check_requires_no_store_and_expected_version(monkeypatch):
    class Response:
        def __init__(self, payload, headers=None):
            self._payload = json.dumps(payload).encode("utf-8")
            self.headers = headers or {}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return self._payload

    responses = iter(
        [
            Response(
                {"status": "operational", "build": {"commit": "abc123"}},
                {"Cache-Control": "no-store"},
            ),
            Response({"info": {"version": "2.1.2"}}),
            Response(
                {
                    "minimum_secure": "2.1.0",
                    "capabilities": ["device-auth", "typed-events"],
                }
            ),
        ]
    )
    monkeypatch.setattr(verifier, "urlopen", lambda request, timeout: next(responses))
    assert verifier.check_cloud_deployment("https://example.invalid", "2.1.2", "abc123") is True

    responses = iter(
        [
            Response({"status": "operational"}, {"Cache-Control": ""}),
            Response({"info": {"version": "2.1.2"}}),
        ]
    )
    assert verifier.check_cloud_deployment("https://example.invalid", "2.1.2") is False


def test_cloud_check_rejects_incomplete_secure_compatibility(monkeypatch):
    class Response:
        def __init__(self, payload, headers=None):
            self._payload = json.dumps(payload).encode("utf-8")
            self.headers = headers or {}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return self._payload

    responses = iter(
        [
            Response(
                {"status": "operational", "build": {"commit": "abc123"}},
                {"Cache-Control": "no-store"},
            ),
            Response({"info": {"version": "2.1.2"}}),
            Response({"minimum_secure": "2.1.0", "capabilities": ["device-auth"]}),
        ]
    )
    monkeypatch.setattr(verifier, "urlopen", lambda request, timeout: next(responses))
    assert verifier.check_cloud_deployment("https://example.invalid") is False


def test_frontend_check_requires_http_200_and_content(monkeypatch):
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b"<html>Lengrowth</html>"

    monkeypatch.setattr(verifier, "urlopen", lambda request, timeout: Response())
    assert verifier.check_frontend_deployment("https://example.invalid") is True

    class EmptyResponse(Response):
        def read(self):
            return b""

    monkeypatch.setattr(verifier, "urlopen", lambda request, timeout: EmptyResponse())
    assert verifier.check_frontend_deployment("https://example.invalid") is False
