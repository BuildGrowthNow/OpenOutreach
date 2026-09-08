import importlib


class _Cursor(list):
    def sort(self, key, direction):
        return _Cursor(sorted(self, key=lambda item: item.get(key, 0), reverse=direction < 0))


class _Collection:
    def __init__(self, docs):
        self.docs = docs
        self.updates = []

    def find(self, query, projection=None):
        def matches(doc):
            for key, value in query.items():
                actual = doc.get(key)
                if isinstance(value, dict) and "$ne" in value and actual == value["$ne"]:
                    return False
                if actual != value and not isinstance(value, dict):
                    return False
            return True
        return _Cursor([dict(doc) for doc in self.docs if matches(doc)])

    def find_one(self, query, projection=None):
        found = self.find(query)
        return found[0] if found else None

    def update_one(self, query, update):
        self.updates.append((query, update))


def test_migration_runs_with_realistic_collection_objects(monkeypatch):
    migration = importlib.import_module("scripts.migrate_legacy_state_machine")
    collections = {
        "campaign_state_graphs": _Collection([{"_id": "graph-1", "campaign_id": "campaign-1"}]),
        "state_nodes": _Collection([
            {"_id": "start", "state_graph_id": "graph-1", "node_type": "start", "x": 0, "is_active": True},
            {"_id": "end", "state_graph_id": "graph-1", "node_type": "end", "x": 1, "is_active": True},
        ]),
        "state_transitions": _Collection([{"_id": "start-end", "state_graph_id": "graph-1", "source_node_id": "start", "target_node_id": "end", "order": 1, "is_active": True}]),
        "campaigns": _Collection([{"_id": "campaign-1", "sequence_steps": []}]),
    }
    monkeypatch.setattr(migration, "get_mongodb_collection", lambda name: collections[name])

    dry_run = migration.migrate(apply=False)
    assert dry_run["migrated"] == 1
    assert dry_run["failures"] == []
    assert collections["campaigns"].updates == []

    applied = migration.migrate(apply=True)
    assert applied["migrated"] == 1
    assert len(collections["campaigns"].updates) == 1
