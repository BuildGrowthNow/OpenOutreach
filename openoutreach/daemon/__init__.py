# openoutreach/daemon/__init__.py
"""OpenOutreach daemon - pure Python task queue worker."""

from .main import run_daemon, DaemonConfig

__all__ = ["run_daemon", "DaemonConfig"]
