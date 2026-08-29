from pathlib import Path


APP = Path(__file__).parents[2] / "openoutreach" / "desktop" / "app.py"
CONFIG = Path(__file__).parents[2] / "openoutreach" / "desktop" / "config.py"
REMOTE_DAEMON = Path(__file__).parents[2] / "openoutreach" / "core" / "daemon_remote.py"
MIGRATION = Path(__file__).parents[2] / "openoutreach" / "migrations" / "add_execution_mode_to_profiles.py"


def test_windows_daemon_log_path_and_rotation_are_explicit():
    app = APP.read_text(encoding="utf-8")
    config = CONFIG.read_text(encoding="utf-8")

    assert 'base = Path.home() / "AppData/Local/Lengrowth"' in config
    assert 'log_file = log_dir / "daemon.log"' in app
    assert "RotatingFileHandler" in app
    assert "maxBytes=5 * 1024 * 1024" in app
    assert "backupCount=3" in app


def test_desktop_logging_does_not_emit_raw_callback_or_exception_values():
    app = APP.read_text(encoding="utf-8")
    updater = (APP.parent / "updater.py").read_text(encoding="utf-8")

    assert 'logger.error("Failed to resolve profile_id after refresh: %s", e2)' not in app
    assert 'logger.info("Opening update URL: %s", url)' not in updater
    assert "urlunsplit" in updater


def test_standalone_entrypoints_use_redacting_formatter():
    assert "RedactingFormatter" in REMOTE_DAEMON.read_text(encoding="utf-8")
    assert "RedactingFormatter" in MIGRATION.read_text(encoding="utf-8")
