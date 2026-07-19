"""VNC session management for per-profile browser isolation.

Each active LinkedInProfile gets its own:
- Xvfb display (:100 + profile_index)
- x11vnc server (5900 + profile_index)
- websockify proxy (6080 + profile_index)

This allows multiple users to view their own browser sessions without cross-contamination.
"""
from __future__ import annotations

import logging
import os
import subprocess
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Base ports for VNC services
VNC_DISPLAY_BASE = 100
VNC_PORT_BASE = 5900
WEBSOCKIFY_PORT_BASE = 6080

# Process tracking
_vnc_processes: dict[str, dict[str, subprocess.Popen]] = {}


class VNCSession:
    """Manages VNC infrastructure for a single LinkedIn profile."""

    def __init__(self, profile_id: str, profile_index: int):
        self.profile_id = profile_id
        self.profile_index = profile_index
        self.display_num = VNC_DISPLAY_BASE + profile_index
        self.vnc_port = VNC_PORT_BASE + profile_index
        self.websockify_port = WEBSOCKIFY_PORT_BASE + profile_index
        self.display = f":{self.display_num}"

        self.xvfb_proc: Optional[subprocess.Popen] = None
        self.x11vnc_proc: Optional[subprocess.Popen] = None
        self.websockify_proc: Optional[subprocess.Popen] = None

    def start(self) -> bool:
        """Start all VNC services for this profile. Returns True on success."""
        if not self._is_vnc_enabled():
            logger.debug("VNC disabled (ENABLE_VNC != true), skipping for %s", self.profile_id)
            return False

        try:
            self._cleanup_lock_file()
            self._start_xvfb()
            self._start_x11vnc()
            self._start_websockify()

            # Track processes globally (all are non-None at this point)
            assert self.xvfb_proc is not None
            assert self.x11vnc_proc is not None
            assert self.websockify_proc is not None
            _vnc_processes[self.profile_id] = {
                "xvfb": self.xvfb_proc,
                "x11vnc": self.x11vnc_proc,
                "websockify": self.websockify_proc,
            }

            logger.info(
                "VNC session started for profile %s: display=%s, vnc_port=%d, web_port=%d",
                self.profile_id, self.display, self.vnc_port, self.websockify_port,
            )
            return True

        except Exception as e:
            logger.error("Failed to start VNC session for %s: %s", self.profile_id, e)
            self.stop()
            return False

    def stop(self) -> None:
        """Stop all VNC services for this profile."""
        for proc in [self.websockify_proc, self.x11vnc_proc, self.xvfb_proc]:
            if proc:
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except Exception as e:
                    logger.debug("Error stopping VNC process: %s", e)

        if self.profile_id in _vnc_processes:
            del _vnc_processes[self.profile_id]

        logger.info("VNC session stopped for profile %s", self.profile_id)

    def _is_vnc_enabled(self) -> bool:
        return os.getenv("ENABLE_VNC", "false").lower() == "true"

    def _cleanup_lock_file(self) -> None:
        """Remove stale X lock file if it exists."""
        lock_file = f"/tmp/.X{self.display_num}-lock"
        if os.path.exists(lock_file):
            try:
                os.remove(lock_file)
            except OSError:
                pass

    def _start_xvfb(self) -> None:
        """Start virtual framebuffer."""
        self.xvfb_proc = subprocess.Popen(
            [
                "Xvfb",
                self.display,
                "-screen", "0", "1920x1080x24",
                "-nolisten", "tcp",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1)  # Let Xvfb initialize

        if self.xvfb_proc.poll() is not None:
            raise RuntimeError(f"Xvfb failed to start on {self.display}")

    def _start_x11vnc(self) -> None:
        """Start VNC server."""
        self.x11vnc_proc = subprocess.Popen(
            [
                "x11vnc",
                "-display", self.display,
                "-rfbport", str(self.vnc_port),
                "-forever",
                "-shared",
                "-nopw",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.5)

        if self.x11vnc_proc.poll() is not None:
            raise RuntimeError(f"x11vnc failed to start on port {self.vnc_port}")

    def _start_websockify(self) -> None:
        """Start websockify proxy for noVNC."""
        self.websockify_proc = subprocess.Popen(
            [
                "websockify",
                "--web", "/opt/noVNC",
                str(self.websockify_port),
                f"localhost:{self.vnc_port}",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.5)

        if self.websockify_proc.poll() is not None:
            raise RuntimeError(f"websockify failed to start on port {self.websockify_port}")


# Global profile index registry: maps profile_id -> index
_profile_indices: dict[str, int] = {}
_next_index = 0


def get_or_create_vnc_session(profile_id: str) -> VNCSession:
    """Get or create a VNC session for the given profile ID."""
    global _next_index

    # Assign stable index to this profile
    if profile_id not in _profile_indices:
        _profile_indices[profile_id] = _next_index
        _next_index += 1

    profile_index = _profile_indices[profile_id]
    session = VNCSession(profile_id, profile_index)

    # Start session if not already running
    if profile_id not in _vnc_processes:
        session.start()

    return session


def stop_vnc_session(profile_id: str) -> None:
    """Stop VNC session for the given profile."""
    if profile_id in _vnc_processes:
        if profile_id in _profile_indices:
            profile_index = _profile_indices[profile_id]
            session = VNCSession(profile_id, profile_index)
            session.stop()


def get_vnc_url(profile_id: str) -> Optional[str]:
    """Get the websockify URL for the given profile's VNC session."""
    if profile_id not in _profile_indices:
        return None

    profile_index = _profile_indices[profile_id]
    port = WEBSOCKIFY_PORT_BASE + profile_index
    return f"http://localhost:{port}"


def get_all_vnc_sessions() -> dict[str, dict]:
    """Return info about all active VNC sessions."""
    sessions = {}
    for profile_id, profile_index in _profile_indices.items():
        if profile_id in _vnc_processes:
            sessions[profile_id] = {
                "profile_id": profile_id,
                "display": f":{VNC_DISPLAY_BASE + profile_index}",
                "vnc_port": VNC_PORT_BASE + profile_index,
                "websockify_port": WEBSOCKIFY_PORT_BASE + profile_index,
            }
    return sessions
