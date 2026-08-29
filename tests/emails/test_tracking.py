"""Tests for signed email tracking links."""

import time
import json

import pytest

from openoutreach.emails.tracking import (
    _b64url,
    _sign,
    click_redirect_url,
    generate_token,
    verify_token,
)


def test_click_token_round_trip(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-tracking-secret")

    url = click_redirect_url("deal-1", "https://example.com/path?q=1", "campaign-1")
    token = url.rsplit("/", 1)[-1]
    payload = verify_token(token)

    assert payload is not None
    assert payload["deal_id"] == "deal-1"
    assert payload["campaign_id"] == "campaign-1"
    assert payload["event"] == "click"
    assert payload["dest_url"] == "https://example.com/path?q=1"
    assert payload["exp"] - payload["iat"] == 90 * 24 * 60 * 60


def test_expired_token_is_rejected(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-tracking-secret")
    clock = iter((1_000_000, 1_000_000 + 90 * 24 * 60 * 60 + 1))
    monkeypatch.setattr(time, "time", lambda: next(clock))

    token = generate_token("deal-1", "open")

    assert verify_token(token) is None


@pytest.mark.parametrize(
    "destination",
    [
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "https://user:password@example.com/",
        "not a URL",
        "https://example.com/" + "x" * 2048,
    ],
)
def test_click_destination_rejects_unsafe_urls(monkeypatch, destination):
    monkeypatch.setenv("SECRET_KEY", "test-tracking-secret")

    with pytest.raises(ValueError):
        click_redirect_url("deal-1", destination)


def test_non_click_tokens_do_not_require_destination_validation(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-tracking-secret")

    payload = verify_token(generate_token("deal-1", "open"))

    assert payload is not None
    assert payload["event"] == "open"


@pytest.mark.parametrize(
    "payload_update",
    [
        {"deal_id": ""},
        {"deal_id": "x" * 257},
        {"event": "other"},
        {"campaign_id": "x" * 257},
        {"dest_url": "x" * 2049},
        {"exp": "not-a-number"},
    ],
)
def test_signed_token_rejects_invalid_payload_shape(monkeypatch, payload_update):
    monkeypatch.setenv("SECRET_KEY", "test-tracking-secret")
    issued_at = int(time.time())
    payload = {
        "deal_id": "deal-1",
        "campaign_id": "campaign-1",
        "event": "open",
        "dest_url": "",
        "iat": issued_at,
        "exp": issued_at + 3600,
    }
    payload.update(payload_update)
    raw = json.dumps(payload, separators=(",", ":")).encode()
    payload_b64 = _b64url(raw)
    token = f"{payload_b64}.{_b64url(_sign(payload_b64.encode()))}"
    assert verify_token(token) is None


def test_signed_token_rejects_oversized_token_before_verification(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-tracking-secret")
    assert verify_token("x" * 8193) is None
