# openoutreach/emails/tracking.py
"""Tracking URLs and server-side attribution for email/link events.

New click URLs use a short opaque token resolved by the tracking Worker. The
signed base64url format remains as a rollout fallback and for open/unsubscribe
links.

SECRET_KEY is shared with the Cloudflare Worker secret of the same name.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import math
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_BASE_URL = os.environ.get("TRACKING_BASE_URL", "https://track.lengrowth.com")
_TOKEN_TTL_SECONDS = 90 * 24 * 60 * 60
_MAX_ID_LENGTH = 256
_MAX_EVENT_LENGTH = 16
_MAX_DESTINATION_LENGTH = 2048
_MAX_SHORT_CODE_LENGTH = 128
_MAX_TOKEN_LENGTH = 8192
_VALID_EVENTS = {"open", "click", "unsub"}


def generate_token(
    deal_id: str,
    event: str,
    *,
    dest_url: str = "",
    campaign_id: str = "",
    tracked_link_id: str = "",
    lead_id: str = "",
    step_id: str = "",
    message_id: str = "",
    channel: str = "email",
    short_code: str = "",
) -> str:
    """Return a signed base64url token for the given event."""
    issued_at = int(time.time())
    payload_bytes = json.dumps(
        {
            "deal_id": deal_id,
            "campaign_id": campaign_id,
            "event": event,
            "dest_url": dest_url,
            "short_code": short_code,
            "tracked_link_id": tracked_link_id,
            "lead_id": lead_id,
            "step_id": step_id,
            "message_id": message_id,
            "channel": channel,
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
            or not isinstance(payload.get("dest_url", ""), str)
            or len(payload.get("dest_url", "")) > _MAX_DESTINATION_LENGTH
            or (not isinstance(payload.get("short_code", ""), str) or len(payload.get("short_code", "")) > _MAX_SHORT_CODE_LENGTH)
            or (
                payload.get("event") == "click"
                and not payload.get("dest_url")
                and not isinstance(payload.get("short_code"), str)
            )
            or (
                payload.get("event") == "click"
                and not payload.get("dest_url")
                and not payload.get("short_code")
            )
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


def render_link_placeholders(
    body: str,
    *,
    deal_id: str,
    campaign_id: str,
    lead_id: str = "",
    step_id: str = "",
    message_id: str = "",
    channel: str = "email",
) -> str:
    """Resolve logical ``{{link.key}}`` references immediately before send."""
    import re
    from openoutreach.mongodb.connection import get_mongodb_collection

    links = get_mongodb_collection("tracked_links")
    if links is None:
        return body
    docs = {str(doc.get("key")): doc for doc in links.find({"campaign_id": campaign_id, "is_active": True})}
    pattern = re.compile(r"\{\{link\.([A-Za-z0-9_-]+)\}\}")

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        link = docs.get(key)
        if not link:
            return match.group(0)
        destination = _merge_utm(link.get("destination_url") or link.get("original_url", ""), link.get("default_utm") or {}, channel=channel, campaign_id=campaign_id, step_id=step_id)
        return click_redirect_url_for_recipient(
            deal_id, destination, campaign_id=campaign_id, tracked_link_id=str(link.get("_id", "")),
            lead_id=lead_id, step_id=step_id, message_id=message_id, channel=channel,
            short_code=str(link.get("short_code") or ""),
        )

    return pattern.sub(replace, body)


def click_redirect_url_for_recipient(
    deal_id: str,
    dest_url: str,
    *,
    campaign_id: str = "",
    tracked_link_id: str = "",
    lead_id: str = "",
    step_id: str = "",
    message_id: str = "",
    channel: str = "email",
    short_code: str = "",
) -> str:
    _validate_destination_url(dest_url)
    if short_code:
        opaque_id = _store_opaque_click_token(
            deal_id=deal_id,
            destination_url=dest_url,
            campaign_id=campaign_id,
            tracked_link_id=tracked_link_id,
            lead_id=lead_id,
            step_id=step_id,
            message_id=message_id,
            channel=channel,
            short_code=short_code,
        )
        if not opaque_id:
            raise RuntimeError("compact tracking token storage is unavailable")
        return f"{TRACKING_BASE_URL}/click/{short_code}/{opaque_id}"
    token = generate_token(
        deal_id,
        "click",
        dest_url="" if short_code else dest_url,
        campaign_id=campaign_id,
        tracked_link_id=tracked_link_id,
        lead_id=lead_id,
        step_id=step_id,
        message_id=message_id,
        channel=channel,
        short_code=short_code,
    )
    if short_code:
        return f"{TRACKING_BASE_URL}/click/{short_code}/{token}"
    return f"{TRACKING_BASE_URL}/click/{token}"


def _store_opaque_click_token(**fields: str) -> str | None:
    """Store attribution server-side and return a short random URL token."""
    from openoutreach.mongodb.connection import get_mongodb_collection

    tokens = get_mongodb_collection("tracking_link_tokens")
    if tokens is None:
        return None
    token_id = secrets.token_urlsafe(12)
    now = datetime.now(timezone.utc)
    try:
        tokens.insert_one({
            "_id": token_id,
            **fields,
            "event": "click",
            "created_at": now,
            "expires_at": now + timedelta(seconds=_TOKEN_TTL_SECONDS),
        })
    except Exception:
        # Keep message delivery working during a partial rollout; the signed
        # token fallback remains compatible with the existing Worker.
        return None
    return token_id


def _merge_utm(destination: str, defaults: dict, *, channel: str, campaign_id: str, step_id: str) -> str:
    _validate_destination_url(destination)
    parsed = urlsplit(destination)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    values = {"channel": channel, "campaign_id": campaign_id, "step_id": step_id}
    for key, value in defaults.items():
        if not key.startswith("utm_"):
            key = f"utm_{key}"
        rendered = str(value)
        for token, replacement in values.items():
            rendered = rendered.replace("{{" + token + "}}", replacement)
        query[key] = rendered
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))


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
