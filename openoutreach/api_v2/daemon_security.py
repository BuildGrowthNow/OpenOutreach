"""Security policy helpers for the legacy desktop boundary.

The desktop is an untrusted client.  This module intentionally contains only
safe policy and redacted audit helpers; it must never serialize credentials or
server configuration.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from fastapi import HTTPException, Request, status
from openoutreach.config import settings

logger = logging.getLogger("openoutreach.security")

MIN_SECURE_DAEMON_VERSION = settings.DAEMON_MIN_SECURE_VERSION
FORBIDDEN_RESPONSE_KEYS = frozenset(
    {
        "secret_key",
        "jwt_secret",
        "jwt_secret_key",
        "cookie_encryption_key",
        "mongodb_uri",
        "mongodb_name",
        "llm_api_key",
        "provider_key",
        "stripe_secret_key",
        "server_env",
    }
)
_SECRET_LIKE = re.compile(r"(?:mongodb(?:\+srv)?://|sk-[A-Za-z0-9]|-----BEGIN .* PRIVATE KEY-----)")


def version_tuple(value: str) -> tuple[int, ...]:
    """Parse a client version without accepting prerelease suffixes as newer."""
    match = re.fullmatch(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", value or "")
    if not match:
        return (0,)
    return tuple(int(part or 0) for part in match.groups())


def is_secure_version(value: str | None) -> bool:
    return bool(value) and version_tuple(value) >= version_tuple(MIN_SECURE_DAEMON_VERSION)


def audit_event(request: Request, event: str, *, outcome: str, version: str | None = None) -> None:
    """Emit a structured event with no token, body, or target identifiers."""
    logger.warning(
        "security_event=%s outcome=%s request_id=%s source_ip=%s client_version=%s",
        event,
        outcome,
        request.headers.get("x-request-id", "-"),
        request.client.host if request.client else "-",
        version or "-",
    )


def assert_safe_response(value: Any) -> None:
    """Fail closed if a daemon response accidentally contains a forbidden field."""
    if isinstance(value, dict):
        for key, nested in value.items():
            if key.lower() in FORBIDDEN_RESPONSE_KEYS:
                raise RuntimeError("forbidden daemon response field")
            assert_safe_response(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            assert_safe_response(nested)
    elif isinstance(value, str) and _SECRET_LIKE.search(value):
        raise RuntimeError("secret-like daemon response value")


def require_secure_daemon(request: Request) -> None:
    """Reject legacy desktop clients before they can claim or receive data."""
    version = request.headers.get("x-daemon-version")
    if not is_secure_version(version):
        audit_event(request, "insecure_version_attempt", outcome="rejected", version=version)
        raise HTTPException(
            status_code=status.HTTP_426_UPGRADE_REQUIRED,
            detail="Desktop security update required",
            headers={"Cache-Control": "no-store"},
        )
