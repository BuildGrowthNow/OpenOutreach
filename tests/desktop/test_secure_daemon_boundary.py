"""Static boundary tests for the distributed desktop entry point."""

from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_secure_desktop_daemon_has_no_database_imports():
    source = (ROOT / "openoutreach" / "desktop" / "secure_daemon.py").read_text(encoding="utf-8")
    forbidden = ("pymongo", "openoutreach.mongodb", "SECRET_KEY", "LLM_API_KEY", "MONGODB_URI")
    assert not any(value in source for value in forbidden)


def test_pyinstaller_spec_excludes_database_and_legacy_daemon():
    source = (ROOT / "desktop" / "openoutreach.spec").read_text(encoding="utf-8")
    assert '"pymongo"' not in source
    assert '"openoutreach.mongodb"' not in source
    assert '"openoutreach.core.daemon_remote"' not in source
