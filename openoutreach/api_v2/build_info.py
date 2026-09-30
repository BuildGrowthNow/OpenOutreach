"""Public, non-secret identity for the running API build."""
from __future__ import annotations

import os


APP_VERSION = os.getenv("APP_VERSION", "2.1.2")


def resolve_build_commit() -> str:
    """Return the current platform release identity before legacy overrides."""
    for name in ("CONTAINER_VERSION", "SOURCE_VERSION", "BUILD_COMMIT", "GIT_COMMIT"):
        value = os.getenv(name)
        if value:
            return value
    return "unknown"


BUILD_COMMIT = resolve_build_commit()
