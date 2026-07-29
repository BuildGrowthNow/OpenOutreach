"""
Remove the demo campaign and all associated data created by seed_demo.py.

Usage:
    python scripts/clean_demo.py
"""

from __future__ import annotations

import sys
import os
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
_env_file = _project_root / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        _k = _k.strip()
        _v = _v.strip().strip('"').strip("'")
        os.environ.setdefault(_k, _v)

if not os.environ.get("MONGODB_URI") and os.environ.get("MONGODB_ATLAS_URI"):
    os.environ["MONGODB_URI"] = os.environ["MONGODB_ATLAS_URI"]

sys.path.insert(0, str(_project_root))

from openoutreach.mongodb.connection import get_mongodb_collection

TARGET_EMAIL = "fern2gue@gmail.com"
DEMO_CAMPAIGN_NAME = "B2B SaaS Outreach - Demo"


def main() -> None:
    users_col = get_mongodb_collection("users")
    if users_col is None:
        print("ERROR: could not connect to MongoDB.")
        sys.exit(1)

    user_doc = users_col.find_one({"email": TARGET_EMAIL})
    if not user_doc:
        print(f"No user found with email {TARGET_EMAIL!r} — nothing to clean.")
        sys.exit(0)
    user_id = str(user_doc["_id"])

    campaigns_col = get_mongodb_collection("campaigns")
    assert campaigns_col is not None
    campaign_doc = campaigns_col.find_one({"name": DEMO_CAMPAIGN_NAME, "user_id": user_id})
    if not campaign_doc:
        print("Demo campaign not found — nothing to clean.")
        sys.exit(0)

    campaign_id = str(campaign_doc["_id"])
    print(f"Found demo campaign {campaign_id}. Cleaning up...")

    # Collect deal IDs first so we can cascade chat messages
    deals_col = get_mongodb_collection("deals")
    assert deals_col is not None
    deal_ids = [str(d["_id"]) for d in deals_col.find({"campaign_id": campaign_id}, {"_id": 1})]

    # Delete chat messages for those deals
    chat_col = get_mongodb_collection("chat_messages")
    assert chat_col is not None
    r = chat_col.delete_many({"deal_id": {"$in": deal_ids}})
    print(f"  Deleted {r.deleted_count} chat messages")

    # Delete leads for this campaign
    lead_ids = [str(d["lead_id"]) for d in deals_col.find({"campaign_id": campaign_id}, {"lead_id": 1})]
    leads_col = get_mongodb_collection("leads")
    assert leads_col is not None
    r = leads_col.delete_many({"_id": {"$in": lead_ids}})
    print(f"  Deleted {r.deleted_count} leads")

    # Also sweep any orphaned demo leads left by incomplete earlier runs
    r2 = leads_col.delete_many({"public_identifier": {"$regex": "-demo$"}, "user_id": user_id})
    if r2.deleted_count:
        print(f"  Cleaned {r2.deleted_count} orphaned demo leads")

    # Delete deals
    r = deals_col.delete_many({"campaign_id": campaign_id})
    print(f"  Deleted {r.deleted_count} deals")

    # Delete tasks
    tasks_col = get_mongodb_collection("tasks")
    assert tasks_col is not None
    r = tasks_col.delete_many({"payload.campaign_id": campaign_id})
    print(f"  Deleted {r.deleted_count} tasks")

    # Delete action logs
    actions_col = get_mongodb_collection("action_logs")
    assert actions_col is not None
    r = actions_col.delete_many({"campaign_id": campaign_id})
    print(f"  Deleted {r.deleted_count} action log entries")

    # Delete campaign
    campaigns_col.delete_one({"_id": campaign_id})
    print(f"  Deleted campaign")

    print("\nDone. Demo data removed.")


if __name__ == "__main__":
    main()
