"""Small client-side proof primitives with no server or database imports."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from urllib.parse import parse_qsl, urlencode


def canonical_request(
    method: str,
    path: str,
    query: str,
    body: bytes,
    timestamp: int,
    nonce: str,
    access_token_id: str,
) -> bytes:
    """Build the exact proof payload signed by the device key."""
    normalized_query = urlencode(sorted(parse_qsl(query, keep_blank_values=True)))
    return "\n".join(
        (
            method.upper(),
            path or "/",
            normalized_query,
            hashlib.sha256(body).hexdigest(),
            str(timestamp),
            nonce,
            access_token_id,
        )
    ).encode("utf-8")


def token_id_without_verification(token: str) -> str:
    """Read only the JWT id used in a proof; the server verifies the token."""
    try:
        encoded = token.split(".")[1]
        payload = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        value = json.loads(payload.decode("utf-8")).get("jti")
        if not isinstance(value, str) or not value:
            raise ValueError("token has no proof id")
        return value
    except (
        IndexError,
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        binascii.Error,
        TypeError,
    ) as exc:
        raise ValueError("token has no proof id") from exc
