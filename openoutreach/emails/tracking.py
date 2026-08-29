# openoutreach/emails/tracking.py
"""HMAC-signed base64url tokens for email open/click/unsubscribe tracking.

Token format: {base64url_payload}.{base64url_hmac_sha256}
Payload: JSON {"deal_id": str, "campaign_id": str, "event": str, "dest_url": str}

SECRET_KEY is shared with the Cloudflare Worker secret of the same name.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import math
from urllib.parse import urlsplit

TRACKING_BASE_URL = os.environ.get("TRACKING_BASE_URL", "https://track.lengrowth.com")
_TOKEN_TTL_SECONDS = 90 * 24 * 60 * 60
_MAX_ID_LENGTH = 256
_MAX_EVENT_LENGTH = 16
_MAX_DESTINATION_LENGTH = 2048
_MAX_TOKEN_LENGTH = 8192
_VALID_EVENTS = {"open", "click", "unsub"}


def generate_token(
    deal_id: str,
    event: str,
    *,
    dest_url: str = "",
    campaign_id: str = "",
) -> str:
    """Return a signed base64url token for the given event."""
    issued_at = int(time.time())
    payload_bytes = json.dumps(
        {
            "deal_id": deal_id,
            "campaign_id": campaign_id,
            "event": event,
            "dest_url": dest_url,
            "iat": issued_at,
            "exp": issued_at + _TOKEN_TTL_SECONDS,
        },
        separators=(",", ":"),
    ).encode()
    payload_b64 = _b64url(payload_bytes)
    sig_b64 = _b64url(_sign(payload_b64.encode()))
    return f"{payload_b64}.{sig_b64}"


def verify_token(token: str) -> dict | None:
    """Verify signature; return payload dict or None on bad token."""
    if not isinstance(token, str) or len(token) > _MAX_TOKEN_LENGTH:
        return None
    parts = token.split(".", 1)
    if len(parts) != 2:
        return None
    payload_b64, sig_b64 = parts
    expected = _b64url(_sign(payload_b64.encode()))
    if not hmac.compare_digest(expected, sig_b64):
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(_pad(payload_b64)))
        if not isinstance(payload, dict):
            return None
        if (
            not isinstance(payload.get("deal_id"), str)
            or not payload["deal_id"]
            or len(payload["deal_id"]) > _MAX_ID_LENGTH
            or not isinstance(payload.get("campaign_id"), str)
            or len(payload["campaign_id"]) > _MAX_ID_LENGTH
            or not isinstance(payload.get("event"), str)
            or len(payload["event"]) > _MAX_EVENT_LENGTH
            or payload["event"] not in _VALID_EVENTS
            or not isinstance(payload.get("dest_url"), str)
            or len(payload["dest_url"]) > _MAX_DESTINATION_LENGTH
        ):
            return None
        for timestamp_key in ("iat", "exp"):
            timestamp = payload.get(timestamp_key)
            if timestamp is not None and (
                isinstance(timestamp, bool)
                or not isinstance(timestamp, (int, float))
                or not math.isfinite(timestamp)
            ):
                return None
        # Legacy tokens without expiry remain valid during the coordinated
        # rollout; all newly issued tokens are time-bounded.
        expires_at = payload.get("exp")
        if expires_at is not None and (not isinstance(expires_at, (int, float)) or expires_at <= time.time()):
            return None
        return payload
    except Exception:
        return None


def open_pixel_url(deal_id: str, campaign_id: str = "") -> str:
    token = generate_token(deal_id, "open", campaign_id=campaign_id)
    return f"{TRACKING_BASE_URL}/open/{token}.gif"


def click_redirect_url(deal_id: str, dest_url: str, campaign_id: str = "") -> str:
    _validate_destination_url(dest_url)
    token = generate_token(deal_id, "click", dest_url=dest_url, campaign_id=campaign_id)
    return f"{TRACKING_BASE_URL}/click/{token}"


def unsubscribe_url(deal_id: str, campaign_id: str = "") -> str:
    token = generate_token(deal_id, "unsub", campaign_id=campaign_id)
    return f"{TRACKING_BASE_URL}/unsub/{token}"


# ── Internals ─────────────────────────────────────────────────────

def _secret_key() -> bytes:
    key = os.environ.get("SECRET_KEY", "")
    if not key:
        raise RuntimeError("SECRET_KEY env var not set")
    return key.encode()


def _sign(data: bytes) -> bytes:
    return hmac.new(_secret_key(), data, hashlib.sha256).digest()


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _pad(s: str) -> str:
    return s + "=" * (-len(s) % 4)


def _validate_destination_url(dest_url: str) -> None:
    """Reject unsafe destinations before they enter a signed redirect token."""
    if not isinstance(dest_url, str) or len(dest_url) > 2048:
        raise ValueError("tracking destination must be a URL of at most 2048 characters")
    try:
        parsed = urlsplit(dest_url)
        hostname = parsed.hostname
    except ValueError as exc:
        raise ValueError("tracking destination must be a valid URL") from exc
    if parsed.scheme not in {"http", "https"} or not hostname:
        raise ValueError("tracking destination must use HTTP(S)")
    if parsed.username or parsed.password:
        raise ValueError("tracking destination must not contain credentials")
