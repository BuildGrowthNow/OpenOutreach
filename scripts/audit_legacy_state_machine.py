"""Read-only audit of legacy state-machine collections.

Prints collection counts and coarse validation counts only. It never prints
documents, secrets, lead data, or mutates/drop collections.
Run with the same environment as the API when a production-shaped audit is
explicitly approved: ``python scripts/audit_legacy_state_machine.py``.
"""

from __future__ import annotations

import json

from openoutreach.mongodb.connection import get_mongodb_collection, initialize_mongodb_connection

LEGACY = {
    "campaign_state_graphs": "campaign_id",
    "state_graphs": "campaign_id",
    "state_nodes": "state_graph_id",
    "state_transitions": "state_graph_id",
    "campaign_states": "deal_id",
    "campaign_execution_logs": "state_machine_id",
}


def audit() -> dict:
    report: dict = {"read_only": True, "collections": {}}
    for name, key in LEGACY.items():
        collection = get_mongodb_collection(name)
        if collection is None:
            report["collections"][name] = {"exists": False, "count": 0}
            continue
        count = collection.count_documents({})
        report["collections"][name] = {
            "exists": True,
            "count": count,
            "missing_identity_count": collection.count_documents({"$or": [{key: {"$exists": False}}, {key: None}]}),
        }
    return report


if __name__ == "__main__":
    if not initialize_mongodb_connection():
        raise SystemExit("MongoDB connection unavailable")
    print(json.dumps(audit(), sort_keys=True))
