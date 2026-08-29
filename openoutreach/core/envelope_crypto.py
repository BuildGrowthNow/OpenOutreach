"""Server-only versioned envelope encryption and migration helpers."""

from __future__ import annotations

import base64
import json
import secrets
from dataclasses import dataclass
from typing import Any, Mapping

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


@dataclass(frozen=True)
class KeyRing:
    """Key IDs and raw keys loaded by the backend secret/KMS integration."""

    active_key_id: str
    keys: Mapping[str, bytes]

    def __post_init__(self) -> None:
        if self.active_key_id not in self.keys:
            raise ValueError("active encryption key is missing")
        if len(self.keys[self.active_key_id]) not in (16, 24, 32):
            raise ValueError("invalid AES key length")


def encrypt_value(value: bytes, *, context: Mapping[str, str], key_ring: KeyRing) -> dict[str, Any]:
    nonce = secrets.token_bytes(12)
    associated_data = json.dumps(dict(sorted(context.items())), separators=(",", ":"), sort_keys=True).encode()
    ciphertext = AESGCM(key_ring.keys[key_ring.active_key_id]).encrypt(nonce, value, associated_data)
    return {
        "version": 1,
        "kid": key_ring.active_key_id,
        "algorithm": "AES-256-GCM",
        "nonce": _b64(nonce),
        "ciphertext": _b64(ciphertext),
        "context": dict(context),
    }


def decrypt_value(envelope: Mapping[str, Any], *, context: Mapping[str, str], key_ring: KeyRing) -> bytes:
    if envelope.get("version") != 1 or envelope.get("algorithm") != "AES-256-GCM":
        raise ValueError("unsupported encryption envelope")
    if dict(envelope.get("context", {})) != dict(context):
        raise ValueError("encryption context mismatch")
    key_id = str(envelope.get("kid", ""))
    key = key_ring.keys.get(key_id)
    if key is None:
        raise ValueError("encryption key unavailable")
    associated_data = json.dumps(dict(sorted(context.items())), separators=(",", ":"), sort_keys=True).encode()
    return AESGCM(key).decrypt(_unb64(str(envelope["nonce"])), _unb64(str(envelope["ciphertext"])), associated_data)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


@dataclass(frozen=True)
class MigrationReport:
    scanned: int
    migrated: int
    skipped: int
    failed: int
    checkpoint: str | None


def migrate_collection_field(
    collection: Any,
    *,
    field: str,
    context_for: Any,
    old_ring: KeyRing,
    new_ring: KeyRing,
    checkpoint: str | None = None,
    batch_size: int = 100,
    dry_run: bool = True,
    retries: int = 3,
) -> MigrationReport:
    """Migrate one encrypted field without printing plaintext or ciphertext."""
    query: dict[str, Any] = {field: {"$exists": True}}
    if checkpoint is not None:
        query["_id"] = {"$gt": checkpoint}
    scanned = migrated = skipped = failed = 0
    last_id = checkpoint
    for document in collection.find(query).sort("_id", 1).limit(batch_size):
        scanned += 1
        last_id = str(document["_id"])
        value = document.get(field)
        if not isinstance(value, dict) or value.get("kid") == new_ring.active_key_id:
            skipped += 1
            continue
        try:
            context = context_for(document)
            plaintext = decrypt_value(value, context=context, key_ring=old_ring)
            replacement = encrypt_value(plaintext, context=context, key_ring=new_ring)
            if not dry_run:
                last_error: Exception | None = None
                for attempt in range(retries):
                    try:
                        collection.update_one({"_id": document["_id"]}, {"$set": {field: replacement}})
                        last_error = None
                        break
                    except Exception as exc:
                        last_error = exc
                        if attempt + 1 < retries:
                            import time
                            time.sleep(2 ** attempt)
                if last_error is not None:
                    raise last_error
            migrated += 1
        except Exception:
            failed += 1
            if not dry_run:
                collection.update_one(
                    {"_id": document["_id"]},
                    {"$set": {"encryption_migration_status": "quarantined", "encryption_migration_field": field}},
                )
    return MigrationReport(scanned, migrated, skipped, failed, last_id)
