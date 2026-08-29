"""Daemon v2 authentication primitives.

This module is deliberately independent of the desktop runtime. Private
signing keys and refresh-token records belong to the backend only.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping, cast
from urllib.parse import parse_qsl, urlencode

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, padding
from cryptography.exceptions import InvalidSignature
import jwt

DAEMON_AUDIENCE = "daemon-gateway"
DAEMON_TOKEN_TYPE = "daemon_access"
DAEMON_ACCESS_LIFETIME = timedelta(minutes=5)
MAX_CLOCK_SKEW = timedelta(minutes=2)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def random_refresh_token() -> str:
    return _b64(secrets.token_bytes(32))


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def constant_time_secret_match(value: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_secret(value), expected_hash)


def new_enrollment_code() -> tuple[str, str]:
    """Return plaintext code once plus the backend-only hash to persist."""
    code = _b64(secrets.token_bytes(24))
    return code, hash_secret(code)


def canonical_request(
    method: str,
    path: str,
    query: str,
    body: bytes,
    timestamp: int,
    nonce: str,
    access_token_id: str,
) -> bytes:
    """Canonical proof input; equivalent requests produce identical bytes."""
    normalized_query = urlencode(sorted(parse_qsl(query, keep_blank_values=True)))
    body_digest = hashlib.sha256(body).hexdigest()
    return "\n".join(
        (
            method.upper(),
            path or "/",
            normalized_query,
            body_digest,
            str(timestamp),
            nonce,
            access_token_id,
        )
    ).encode("utf-8")


def sign_request(private_key_pem: bytes, canonical: bytes) -> str:
    key = cast(Any, serialization.load_pem_private_key(private_key_pem, password=None))
    if isinstance(key, ed25519.Ed25519PrivateKey):
        signature = key.sign(canonical)
    else:
        signature = key.sign(canonical, padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH), hashes.SHA256())
    return _b64(signature)


def verify_request(public_key_pem: bytes, canonical: bytes, signature: str) -> bool:
    try:
        key = cast(Any, serialization.load_pem_public_key(public_key_pem))
        if isinstance(key, ed25519.Ed25519PublicKey):
            key.verify(_unb64(signature), canonical)
        else:
            key.verify(_unb64(signature), canonical, padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH), hashes.SHA256())
        return True
    except (ValueError, TypeError, binascii.Error, InvalidSignature):
        return False


def issue_daemon_access_token(
    private_key_pem: str | bytes,
    *,
    key_id: str,
    device_id: str,
    tenant_id: str,
    profile_ids: Iterable[str],
    scopes: Iterable[str],
    channel_profile_ids: Mapping[str, Iterable[str]] | None = None,
    token_id: str | None = None,
    now: datetime | None = None,
) -> str:
    """Issue a short-lived, audience-restricted daemon token."""
    if not device_id or not tenant_id or not key_id:
        raise ValueError("daemon token identity is incomplete")
    issued = now or datetime.now(timezone.utc)
    payload = {
        "sub": device_id,
        "device_id": device_id,
        "tenant_id": tenant_id,
        "profile_ids": sorted(set(profile_ids)),
        "scopes": sorted(set(scopes)),
        "channel_profile_ids": {
            str(channel): sorted(set(str(value) for value in values))
            for channel, values in (channel_profile_ids or {}).items()
        },
        "aud": DAEMON_AUDIENCE,
        "type": DAEMON_TOKEN_TYPE,
        "jti": token_id or secrets.token_urlsafe(18),
        "iat": issued,
        "exp": issued + DAEMON_ACCESS_LIFETIME,
    }
    key = private_key_pem.decode() if isinstance(private_key_pem, bytes) else private_key_pem
    return jwt.encode(payload, key, algorithm="RS256", headers={"kid": key_id})


def decode_daemon_access_token(public_key_pem: str | bytes, token: str, *, now: datetime | None = None) -> Mapping[str, object]:
    key = public_key_pem.decode() if isinstance(public_key_pem, bytes) else public_key_pem
    payload = jwt.decode(token, key, algorithms=["RS256"], audience=DAEMON_AUDIENCE)
    if payload.get("type") != DAEMON_TOKEN_TYPE or not payload.get("device_id") or not payload.get("tenant_id"):
        raise ValueError("invalid daemon token purpose")
    issued = datetime.fromtimestamp(int(payload["iat"]), tz=timezone.utc)
    current = now or datetime.now(timezone.utc)
    if issued - MAX_CLOCK_SKEW > current:
        raise ValueError("daemon token issued in the future")
    return payload


@dataclass(frozen=True)
class RefreshRotation:
    family_id: str
    token_hash: str
    expires_at: datetime
    revoked: bool = False


def rotate_refresh_family(
    current: RefreshRotation, presented_token: str, *, family_id: str
) -> tuple[str, RefreshRotation]:
    """Validate a single-use refresh token and return its replacement record."""
    if current.revoked or current.family_id != family_id or current.expires_at <= datetime.now(timezone.utc):
        raise ValueError("refresh family revoked or expired")
    if not constant_time_secret_match(presented_token, current.token_hash):
        raise ValueError("refresh token reuse detected")
    replacement = random_refresh_token()
    return replacement, RefreshRotation(
        family_id=family_id,
        token_hash=hash_secret(replacement),
        expires_at=current.expires_at,
    )


def timestamp_is_fresh(timestamp: int, *, now: datetime | None = None) -> bool:
    current = now or datetime.now(timezone.utc)
    try:
        candidate = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return False
    return abs(current - candidate) <= MAX_CLOCK_SKEW


def new_nonce() -> str:
    return secrets.token_urlsafe(24)


def token_id_without_verification(token: str) -> str:
    """Read only the JWT locator used in the proof; the server still verifies JWT."""
    try:
        payload = json.loads(_unb64(token.split(".")[1]).decode("utf-8"))
        value = payload.get("jti")
        if not isinstance(value, str) or not value:
            raise ValueError
        return value
    except (IndexError, ValueError, UnicodeDecodeError, json.JSONDecodeError, binascii.Error, TypeError) as exc:
        raise ValueError("token has no proof id") from exc
