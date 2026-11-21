"""Tests for the desktop local-IP display helper."""
from __future__ import annotations

from openoutreach.desktop.local_ip import detect_local_ip


class _Socket:
    def __init__(self, address=None, error=None):
        self.address = address
        self.error = error

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def connect(self, _target):
        if self.error:
            raise self.error

    def getsockname(self):
        return (self.address, 12345)


def test_detect_local_ip_returns_interface_address(monkeypatch):
    monkeypatch.setattr(
        "openoutreach.desktop.local_ip.socket.socket",
        lambda *args, **kwargs: _Socket("192.168.1.25"),
    )
    assert detect_local_ip() == "192.168.1.25"


def test_detect_local_ip_ignores_loopback_and_failures(monkeypatch):
    monkeypatch.setattr(
        "openoutreach.desktop.local_ip.socket.socket",
        lambda *args, **kwargs: _Socket("127.0.0.1"),
    )
    assert detect_local_ip() is None

    monkeypatch.setattr(
        "openoutreach.desktop.local_ip.socket.socket",
        lambda *args, **kwargs: _Socket(error=OSError("no route")),
    )
    assert detect_local_ip() is None
