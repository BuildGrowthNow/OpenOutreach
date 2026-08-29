import importlib.util
from pathlib import Path


def _load_verifier():
    path = Path(__file__).parents[1] / "scripts" / "verify_production_ready.py"
    spec = importlib.util.spec_from_file_location("production_verifier", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_verifier_does_not_call_local_smoke_production_ready(monkeypatch, capsys):
    verifier = _load_verifier()
    for key in (
        "MONGODB_URI", "OPENOUTREACH_MONGODB_URI", "MONGODB_NAME",
        "OPENOUTREACH_MONGODB_NAME", "DAEMON_JWT_PRIVATE_KEY",
        "DAEMON_JWT_PRIVATE_KEY_B64", "DAEMON_JWT_PUBLIC_KEY",
        "DAEMON_JWT_PUBLIC_KEY_B64",
    ):
        monkeypatch.delenv(key, raising=False)
    assert verifier.check_production_prerequisites() is False
    assert "Local source/smoke checks are not evidence" in capsys.readouterr().out
