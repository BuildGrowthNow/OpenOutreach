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

TRACKING_BASE_URL = os.environ.get("TRACKING_BASE_URL", "https://track.lengrowth.com")


def generate_token(
    deal_id: str,
    event: str,
    *,
    dest_url: str = "",
    campaign_id: str = "",
) -> str:
    """Return a signed base64url token for the given event."""
    payload_bytes = json.dumps(
        {"deal_id": deal_id, "campaign_id": campaign_id, "event": event, "dest_url": dest_url},
        separators=(",", ":"),
    ).encode()
    payload_b64 = _b64url(payload_bytes)
    sig_b64 = _b64url(_sign(payload_b64.encode()))
    return f"{payload_b64}.{sig_b64}"


def verify_token(token: str) -> dict | None:
    """Verify signature; return payload dict or None on bad token."""
    parts = token.split(".", 1)
    if len(parts) != 2:
        return None
    payload_b64, sig_b64 = parts
    expected = _b64url(_sign(payload_b64.encode()))
    if not hmac.compare_digest(expected, sig_b64):
        return None
    try:
        return json.loads(base64.urlsafe_b64decode(_pad(payload_b64)))
    except Exception:
        return None


def open_pixel_url(deal_id: str, campaign_id: str = "") -> str:
    token = generate_token(deal_id, "open", campaign_id=campaign_id)
    return f"{TRACKING_BASE_URL}/open/{token}.gif"


def click_redirect_url(deal_id: str, dest_url: str, campaign_id: str = "") -> str:
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
