"""Best-effort local egress IP detection for support display only.

The address is reported to the API for the device list. It is never used for
authorization and it is never a proxy credential.
"""
from __future__ import annotations

import socket
from typing import Optional


def detect_local_ip() -> Optional[str]:
    """Return the local interface address used for outbound traffic.

    A UDP connect does not send a packet; it only asks the OS to select the
    route. If there is no usable IPv4 route, return ``None`` rather than a
    loopback address.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            value = str(sock.getsockname()[0]).strip()
    except OSError:
        return None
    if not value or value.startswith("127.") or value == "0.0.0.0":
        return None
    return value
