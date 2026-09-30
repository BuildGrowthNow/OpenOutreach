from openoutreach.api_v2 import build_info


def test_scalingo_release_identity_wins_over_legacy_build_commit(monkeypatch):
    monkeypatch.setenv("CONTAINER_VERSION", "current-scalingo-release")
    monkeypatch.setenv("SOURCE_VERSION", "current-source-release")
    monkeypatch.setenv("BUILD_COMMIT", "stale-legacy-release")

    assert build_info.resolve_build_commit() == "current-scalingo-release"


def test_build_identity_falls_back_to_legacy_sources(monkeypatch):
    for name in ("CONTAINER_VERSION", "SOURCE_VERSION", "BUILD_COMMIT", "GIT_COMMIT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GIT_COMMIT", "legacy-git-release")

    assert build_info.resolve_build_commit() == "legacy-git-release"
