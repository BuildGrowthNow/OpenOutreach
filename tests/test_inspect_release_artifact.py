import importlib.util
from pathlib import Path


def _load_scanner():
    path = Path(__file__).parents[1] / "scripts" / "inspect_release_artifact.py"
    spec = importlib.util.spec_from_file_location("artifact_scanner", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_artifact_scanner_rejects_backend_markers():
    scanner = _load_scanner()
    report = scanner.inspect_bytes(b"safe-client pymongo MONGODB_URI")
    assert set(report["forbidden_markers"]) >= {"pymongo", "MONGODB_URI"}


def test_artifact_scanner_returns_hash_and_no_payload():
    scanner = _load_scanner()
    report = scanner.inspect_bytes(b"safe-client")
    assert report["forbidden_markers"] == []
    assert len(report["sha256"]) == 64
    assert "data" not in report
