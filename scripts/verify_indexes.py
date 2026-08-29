"""Read-only verification of required tenant/lease indexes.

The command reports index names and whether they exist; it never creates or
drops indexes and never prints connection values or document contents.
"""
from __future__ import annotations

import argparse
import json
import os
from typing import Any

REQUIRED = {
    "tasks": {
        "daemon_v2_task_claim_idx", "daemon_v2_task_whatsapp_claim_idx",
        "daemon_v2_task_mailbox_claim_idx", "daemon_v2_task_email_profile_claim_idx",
        "daemon_v2_task_lease_idx",
    },
    "daemon_devices": {"daemon_device_user_status_idx"},
    "daemon_refresh_families": {"daemon_refresh_device_hash_unique"},
    "daemon_enrollment_codes": {"daemon_enrollment_code_hash_unique"},
    "daemon_events": {"daemon_event_dedupe_unique"},
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify production indexes (read-only)")
    parser.add_argument("--collection", action="append", choices=sorted(REQUIRED))
    args = parser.parse_args()
    names = args.collection or list(REQUIRED)
    uri = os.environ.get("OPENOUTREACH_MONGODB_URI")
    db_name = os.environ.get("OPENOUTREACH_MONGODB_NAME")
    if not uri or not db_name:
        print(json.dumps({"status": "not_run", "reason": "deployment variables are not configured", "collections": names}))
        return 0
    from pymongo import MongoClient
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    try:
        db = client[db_name]
        report: list[dict[str, Any]] = []
        for name in names:
            present = set(db[name].index_information())
            required = REQUIRED[name]
            report.append({"collection": name, "required": sorted(required),
                           "present": sorted(required & present),
                           "missing": sorted(required - present)})
        print(json.dumps({"status": "ok", "report": report}))
        return 0 if all(not row["missing"] for row in report) else 2
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
