"""Unit tests for daemon v2 token, enrollment, and proof primitives."""

from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from openoutreach.api_v2.daemon_auth import (
    RefreshRotation,
    canonical_request,
    constant_time_secret_match,
    decode_daemon_access_token,
    hash_secret,
    issue_daemon_access_token,
    new_enrollment_code,
    rotate_refresh_family,
    sign_request,
    timestamp_is_fresh,
    verify_request,
)


@pytest.fixture
def key_pair() -> tuple[bytes, bytes]:
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return (
        private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()),
        private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo),
    )


def test_daemon_token_is_asymmetric_and_scoped(key_pair):
    private, public = key_pair
    token = issue_daemon_access_token(private, key_id="k1", device_id="d1", tenant_id="t1", profile_ids=["p1"], scopes=["linkedin"])
    claims = decode_daemon_access_token(public, token)
    assert claims["aud"] == "daemon-gateway"
    assert claims["type"] == "daemon_access"
    assert claims["tenant_id"] == "t1"
    assert claims["profile_ids"] == ["p1"]


def test_wrong_audience_or_modified_token_is_rejected(key_pair):
    private, public = key_pair
    token = issue_daemon_access_token(private, key_id="k1", device_id="d1", tenant_id="t1", profile_ids=[], scopes=[])
    with pytest.raises(Exception):
        decode_daemon_access_token(public, token[:20] + ("a" if token[20] != "a" else "b") + token[21:])


def test_enrollment_code_is_only_stored_as_hash():
    code, stored = new_enrollment_code()
    assert code != stored
    assert constant_time_secret_match(code, stored)
    assert not constant_time_secret_match("wrong", stored)


def test_request_proof_canonicalization_and_signature(key_pair):
    private, public = key_pair
    canonical_a = canonical_request("post", "/api/daemon/v2/tasks/claim", "b=2&a=1", b'{"x":1}', 100, "n1", "j1")
    canonical_b = canonical_request("POST", "/api/daemon/v2/tasks/claim", "a=1&b=2", b'{"x":1}', 100, "n1", "j1")
    assert canonical_a == canonical_b
    signature = sign_request(private, canonical_a)
    assert verify_request(public, canonical_b, signature)
    assert not verify_request(public, canonical_b + b"x", signature)


def test_refresh_rotation_rejects_reuse():
    raw = "refresh-secret"
    current = RefreshRotation("family", hash_secret(raw), datetime.now(timezone.utc) + timedelta(days=1))
    replacement_raw, replacement = rotate_refresh_family(current, raw, family_id="family")
    assert replacement.token_hash != current.token_hash
    assert constant_time_secret_match(replacement_raw, replacement.token_hash)
    with pytest.raises(ValueError, match="reuse"):
        rotate_refresh_family(current, "refresh-secret-2", family_id="family")


def test_proof_timestamp_window():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert timestamp_is_fresh(int(now.timestamp()), now=now)
    assert not timestamp_is_fresh(int((now - timedelta(minutes=3)).timestamp()), now=now)


def test_malformed_proof_and_timestamp_fail_closed(key_pair):
    private, public = key_pair
    canonical = canonical_request("POST", "/api/daemon/v2/tokens/exchange", "", b"{}", 100, "nonce", "device")
    signature = sign_request(private, canonical)
    assert not verify_request(public, canonical, "not-base64")
    assert not timestamp_is_fresh(10**100)
    assert verify_request(public, canonical, signature)
