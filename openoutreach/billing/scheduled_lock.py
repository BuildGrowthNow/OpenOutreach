"""MongoDB-backed lock for Scalingo Scheduler jobs.

Scalingo can briefly overlap scheduled one-off containers.  This lock keeps
each billing command single-owner without relying on the ephemeral filesystem.
"""
from __future__ import annotations

import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Iterator

from pymongo.errors import DuplicateKeyError

from openoutreach.mongodb.connection import get_mongodb_collection


@contextmanager
def scheduled_job_lock(name: str, ttl_seconds: int = 3600) -> Iterator[bool]:
    collection = get_mongodb_collection("scheduled_job_locks")
    if collection is None:
        yield False
        return

    now = datetime.now(timezone.utc)
    token = secrets.token_hex(16)
    expires = now + timedelta(seconds=ttl_seconds)
    acquired = False
    try:
        try:
            result = collection.update_one(
                {"_id": name, "$or": [{"expires_at": {"$lte": now}}, {"expires_at": {"$exists": False}}]},
                {"$set": {"owner": token, "expires_at": expires, "acquired_at": now}},
                upsert=True,
            )
        except DuplicateKeyError:
            result = None
        acquired = bool(result and (result.matched_count == 1 or result.upserted_id == name))
        yield acquired
    finally:
        if acquired:
            collection.delete_one({"_id": name, "owner": token})
