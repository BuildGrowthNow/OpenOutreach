from pathlib import Path


COMPOSE = Path(__file__).parents[1] / "docker-compose.yml"
START = Path(__file__).parents[1] / "compose" / "linkedin" / "start"


def test_production_compose_fails_closed_for_required_runtime_settings():
    compose = COMPOSE.read_text(encoding="utf-8")
    assert "SECRET_KEY=${SECRET_KEY:?SECRET_KEY must be configured}" in compose
    assert "MONGODB_URI=${MONGODB_URI:?MONGODB_URI must be configured}" in compose
    assert "MONGODB_NAME=${MONGODB_NAME:?MONGODB_NAME must be configured}" in compose
    assert "APP_URL=${APP_URL:?APP_URL must be configured}" in compose
    assert "CORS_ALLOWED_ORIGINS=${CORS_ALLOWED_ORIGINS:?CORS_ALLOWED_ORIGINS must be configured}" in compose
    assert "change-in-production" not in compose
    assert "APP_URL=${APP_URL:-http://localhost:3000}" not in compose


def test_passwordless_vnc_is_not_a_production_default():
    compose = COMPOSE.read_text(encoding="utf-8")
    assert "ENABLE_VNC=${ENABLE_VNC:-false}" in compose
    assert "ENABLE_VNC=${ENABLE_VNC:-true}" not in compose
    assert '"127.0.0.1:6080:6080"' in compose
    assert '"127.0.0.1:5900:5900"' in compose
    assert '"6080:6080"' not in compose
    assert '"5900:5900"' not in compose


def test_explicit_vnc_requires_a_password_file():
    start = START.read_text(encoding="utf-8")
    assert 'requires a non-empty VNC_PASSWORD_FILE' in start
    assert "-passwdfile \"$VNC_PASSWORD_FILE\"" in start
    assert "-nopw" not in start
