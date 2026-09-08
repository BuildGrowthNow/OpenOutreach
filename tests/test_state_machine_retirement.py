"""The retired state-machine API must not be accidentally re-exposed."""

from openoutreach.api_v2.main import app


def test_legacy_state_machine_routes_are_not_mounted():
    paths = {route.path for route in app.routes}
    assert not any(path.startswith("/api/state-machines") for path in paths)
