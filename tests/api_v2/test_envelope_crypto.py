"""Tests for versioned server-side envelope encryption."""

import pytest

from openoutreach.core.envelope_crypto import KeyRing, decrypt_value, encrypt_value


def test_envelope_binds_context_and_key_id():
    ring = KeyRing("new", {"old": b"o" * 32, "new": b"n" * 32})
    envelope = encrypt_value(b"credential", context={"tenant": "t1", "profile": "p1"}, key_ring=ring)
    assert envelope["kid"] == "new"
    assert decrypt_value(envelope, context={"tenant": "t1", "profile": "p1"}, key_ring=ring) == b"credential"
    with pytest.raises(ValueError, match="context"):
        decrypt_value(envelope, context={"tenant": "t2", "profile": "p1"}, key_ring=ring)


def test_old_key_can_be_dual_read_but_new_writes_use_active_key():
    old = KeyRing("old", {"old": b"o" * 32})
    new = KeyRing("new", {"old": b"o" * 32, "new": b"n" * 32})
    context = {"tenant": "t1", "profile": "p1"}
    old_envelope = encrypt_value(b"state", context=context, key_ring=old)
    assert decrypt_value(old_envelope, context=context, key_ring=new) == b"state"
    assert encrypt_value(b"state", context=context, key_ring=new)["kid"] == "new"
