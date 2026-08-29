"""Dry-run/resumable envelope-encryption migration entry point.

Production invocation must supply keys through the deployment secret manager;
this command never accepts or prints plaintext credentials or key material.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path


def _write_checkpoint(path: Path, checkpoint: str | None) -> None:
    """Persist resume state atomically; never write encrypted values to logs."""
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps({"checkpoint": checkpoint}, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _encryption_context(document: dict[str, object]) -> dict[str, str]:
    """Derive the stable tenant/profile binding without exposing document data."""
    tenant_id = str(document.get("user_id") or "").strip()
    profile_id = str(
        document.get("linkedin_profile_id")
        or document.get("whatsapp_profile_id")
        or document.get("mailbox_id")
        or document.get("email_profile_id")
        or document.get("profile_id")
        or ""
    ).strip()
    if not tenant_id:
        raise ValueError("document has no tenant binding")
    return {"tenant_id": tenant_id, "profile_id": profile_id}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Migrate encrypted server fields")
    parser.add_argument("--collection", required=True)
    parser.add_argument("--field", required=True)
    parser.add_argument("--checkpoint-file", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--apply", action="store_true", help="Apply changes; default is dry-run")
    parser.add_argument("--confirm", action="store_true", help="Required with --apply")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.apply and not args.confirm:
        raise SystemExit("--apply requires --confirm after scope and backup review")
    if args.batch_size < 1 or args.batch_size > 1000:
        raise SystemExit("batch size must be between 1 and 1000")
    if args.retries < 1 or args.retries > 5:
        raise SystemExit("retries must be between 1 and 5")
    checkpoint = None
    if args.checkpoint_file.exists():
        checkpoint = json.loads(args.checkpoint_file.read_text(encoding="utf-8")).get("checkpoint")
    uri = os.environ.get("OPENOUTREACH_MONGODB_URI")
    db_name = os.environ.get("OPENOUTREACH_MONGODB_NAME")
    old_key = os.environ.get("OPENOUTREACH_ENCRYPTION_OLD_KEY_B64")
    new_key = os.environ.get("OPENOUTREACH_ENCRYPTION_NEW_KEY_B64")
    if not all((uri, db_name, old_key, new_key)):
        print(json.dumps({"collection": args.collection, "field": args.field, "checkpoint": checkpoint, "dry_run": not args.apply, "status": "not_run", "reason": "deployment variables are not configured"}))
        return 0
    assert uri is not None and db_name is not None and old_key is not None and new_key is not None
    from pymongo import MongoClient
    from openoutreach.core.envelope_crypto import KeyRing, migrate_collection_field
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    collection = client[db_name][args.collection]
    old_ring = KeyRing("old", {"old": base64.b64decode(old_key)})
    new_ring = KeyRing("new", {"new": base64.b64decode(new_key)})
    report = migrate_collection_field(collection, field=args.field,
        context_for=_encryption_context,
        old_ring=old_ring, new_ring=new_ring, checkpoint=checkpoint,
        batch_size=args.batch_size, dry_run=not args.apply, retries=args.retries)
    _write_checkpoint(args.checkpoint_file, report.checkpoint)
    print(json.dumps({"collection": args.collection, "field": args.field, "dry_run": not args.apply, "scanned": report.scanned, "migrated": report.migrated, "skipped": report.skipped, "failed": report.failed, "checkpoint": report.checkpoint}))
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
