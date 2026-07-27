"""One-time migration: backfill Lead.connection_degree from cached_profile.

Run with: .venv/bin/python migrate_connection_degree.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from openoutreach.mongodb.connection import get_mongodb_collection


def migrate():
    leads = get_mongodb_collection("leads")
    if leads is None:
        print("ERROR: cannot connect to leads collection")
        sys.exit(1)

    updated = 0
    skipped = 0
    cursor = leads.find({"connection_degree": {"$exists": False}})

    for doc in cursor:
        cp = doc.get("cached_profile") or {}
        degree = cp.get("connection_degree")
        if degree is not None:
            leads.update_one({"_id": doc["_id"]}, {"$set": {"connection_degree": degree}})
            updated += 1
        else:
            skipped += 1

    print(f"Migration complete: {updated} leads updated, {skipped} had no degree in cached_profile")


if __name__ == "__main__":
    migrate()
