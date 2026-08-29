"""Acceptance tests for safe, resumable deployment migration helpers."""

from openoutreach.core.envelope_crypto import (
    KeyRing, encrypt_value, migrate_collection_field,
    decrypt_value,
)
from scripts.backfill_tenant_ownership import backfill_collection


class _Cursor:
    def __init__(self, documents):
        self.documents = documents

    def sort(self, *_args, **_kwargs):
        self.documents.sort(key=lambda item: item["_id"])
        return self

    def limit(self, count):
        self.documents = self.documents[:count]
        return self

    def __iter__(self):
        return iter(self.documents)


class _Collection:
    def __init__(self, documents):
        self.documents = documents
        self.updates = []

    def find(self, _query):
        return _Cursor([dict(document) for document in self.documents])

    def find_one(self, query, *_args, **_kwargs):
        for document in self.documents:
            if all(document.get(key) == value for key, value in query.items()):
                return document
        return None

    def update_one(self, query, update):
        self.updates.append((query, update))
        for document in self.documents:
            if all(document.get(key) == value for key, value in query.items()):
                document.update(update.get("$set", {}))
                break


class _Database(dict):
    pass


def test_tenant_backfill_dry_run_and_apply_are_explicit():
    target = _Collection([
        {"_id": "1", "linkedin_profile_id": "profile-a"},
        {"_id": "2", "payload": {"campaign_id": "campaign-a"}},
        {"_id": "3"},
    ])
    db = _Database({
        "tasks": target,
        "linkedin_profiles": _Collection([{"_id": "profile-a", "user_id": "tenant-a"}]),
        "campaigns": _Collection([{"_id": "campaign-a", "user_id": "tenant-a"}]),
    })
    report = backfill_collection(db, "tasks", checkpoint=None, apply=False, batch_size=10)
    assert report == {"collection": "tasks", "scanned": 3, "assigned": 2, "quarantined": 1, "checkpoint": "3"}
    assert target.updates == []

    applied = backfill_collection(db, "tasks", checkpoint=None, apply=True, batch_size=10)
    assert applied["assigned"] == 2
    assert applied["quarantined"] == 1
    assert len(target.updates) == 3


def test_encryption_migration_rekeys_without_logging_or_body_output():
    old = KeyRing("old", {"old": b"o" * 32})
    new = KeyRing("new", {"new": b"n" * 32})
    context = {"tenant_id": "tenant-a", "profile_id": "profile-a"}
    document = {"_id": "1", "user_id": "tenant-a", "linkedin_profile_id": "profile-a"}
    document["secret"] = encrypt_value(b"opaque-value", context=context, key_ring=old)
    collection = _Collection([document])

    dry_run = migrate_collection_field(
        collection, field="secret", context_for=lambda item: context,
        old_ring=old, new_ring=new, dry_run=True, batch_size=1,
    )
    assert dry_run.scanned == 1 and dry_run.migrated == 1 and dry_run.failed == 0
    assert collection.updates == []

    applied = migrate_collection_field(
        collection, field="secret", context_for=lambda item: context,
        old_ring=old, new_ring=new, dry_run=False, batch_size=1,
    )
    assert applied.migrated == 1
    assert collection.documents[0]["secret"]["kid"] == "new"
    assert decrypt_value(collection.documents[0]["secret"], context=context, key_ring=new) == b"opaque-value"
