"""The retired state-machine API must not be accidentally re-exposed."""

from openoutreach.api_v2.main import app


def test_legacy_state_machine_routes_are_not_mounted():
    # FastAPI may expose nested router/include entries without a concrete
    # path. Only concrete route objects participate in the public path set.
    paths = {
        route.path
        for route in app.routes
        if getattr(route, "path", None) is not None
    }
    assert not any(path.startswith("/api/state-machines") for path in paths)
