"""Backfill tenant ownership for daemon-reachable MongoDB documents.

Dry-run is the default. Ambiguous documents are quarantined rather than made
globally visible. This command never prints document bodies or credentials.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

COLLECTIONS = (
    "tasks",
    "campaigns",
    "leads",
    "deals",
    "chat_messages",
    "messages",
    "action_logs",
    "notifications",
    "mailboxes",
    "sequence_events",
)


def _resolve_owner(document: dict[str, Any], profiles: Any, campaigns: Any) -> str | None:
    if document.get("user_id"):
        return str(document["user_id"])
    profile_id = document.get("linkedin_profile_id") or document.get("profile_id")
    if profile_id:
        profile = profiles.find_one({"_id": profile_id}, {"user_id": 1})
        if profile and profile.get("user_id"):
            return str(profile["user_id"])
    campaign_id = document.get("campaign_id") or (document.get("payload") or {}).get("campaign_id")
    if campaign_id:
        campaign = campaigns.find_one({"_id": campaign_id}, {"user_id": 1})
        if campaign and campaign.get("user_id"):
            return str(campaign["user_id"])
    return None


def _retry(operation: Any, *, attempts: int) -> Any:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return operation()
        except Exception as exc:  # Mongo transient errors are intentionally retried without logging details.
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(2 ** attempt)
    assert last_error is not None
    raise last_error


def backfill_collection(db: Any, collection_name: str, *, checkpoint: str | None,
                        apply: bool, batch_size: int = 1000, retries: int = 3) -> dict[str, Any]:
    collection = db[collection_name]
    profiles = db["linkedin_profiles"]
    campaigns = db["campaigns"]
    query: dict[str, Any] = {"user_id": {"$exists": False}, "ownership_status": {"$ne": "quarantined"}}
    if checkpoint is not None:
        query["_id"] = {"$gt": checkpoint}
    scanned = assigned = quarantined = 0
    last_id = checkpoint
    for document in _retry(lambda: collection.find(query).sort("_id", 1).limit(batch_size), attempts=retries):
        scanned += 1
        last_id = str(document["_id"])
        owner = _resolve_owner(document, profiles, campaigns)
        if owner:
            assigned += 1
            if apply:
                _retry(lambda: collection.update_one(
                    {"_id": document["_id"], "user_id": {"$exists": False}},
                    {"$set": {"user_id": owner, "ownership_backfilled_at": datetime.now(timezone.utc)}},
                ), attempts=retries)
        else:
            quarantined += 1
            if apply:
                _retry(lambda: collection.update_one(
                    {"_id": document["_id"], "user_id": {"$exists": False}},
                    {"$set": {"ownership_status": "quarantined", "ownership_quarantined_at": datetime.now(timezone.utc)}},
                ), attempts=retries)
    return {"collection": collection_name, "scanned": scanned, "assigned": assigned, "quarantined": quarantined, "checkpoint": last_id}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill tenant ownership safely")
    parser.add_argument("--collection", choices=COLLECTIONS, action="append")
    parser.add_argument("--checkpoint-file", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--apply", action="store_true", help="Persist assignments/quarantine; default is dry-run")
    parser.add_argument("--confirm", action="store_true", help="Required with --apply")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.apply and not args.confirm:
        raise SystemExit("--apply requires --confirm after scope and backup review")
    if not 1 <= args.batch_size <= 1000 or not 1 <= args.retries <= 5:
        raise SystemExit("batch size must be 1..1000 and retries must be 1..5")
    checkpoint_data = json.loads(args.checkpoint_file.read_text(encoding="utf-8")) if args.checkpoint_file.exists() else {}
    uri = os.environ.get("OPENOUTREACH_MONGODB_URI")
    db_name = os.environ.get("OPENOUTREACH_MONGODB_NAME")
    if not uri or not db_name:
        print(json.dumps({"dry_run": not args.apply, "collections": args.collection or list(COLLECTIONS), "checkpoint": checkpoint_data.get("checkpoint"), "status": "not_run", "reason": "deployment database variables are not configured"}))
        return 0
    from pymongo import MongoClient
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    db = client[db_name]
    reports = []
    for name in args.collection or list(COLLECTIONS):
        report = backfill_collection(db, name, checkpoint=checkpoint_data.get(name), apply=args.apply,
                                     batch_size=args.batch_size, retries=args.retries)
        reports.append(report)
        checkpoint_data[name] = report["checkpoint"]
        args.checkpoint_file.write_text(json.dumps(checkpoint_data, sort_keys=True), encoding="utf-8")
    print(json.dumps({"dry_run": not args.apply, "reports": reports}))
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
