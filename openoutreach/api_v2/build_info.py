"""Public, non-secret identity for the running API build."""
from __future__ import annotations

import os


APP_VERSION = os.getenv("APP_VERSION", "2.1.2")
BUILD_COMMIT = os.getenv("BUILD_COMMIT", os.getenv("GIT_COMMIT", "unknown"))
