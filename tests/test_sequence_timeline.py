import asyncio
from types import SimpleNamespace

from openoutreach.api_v2.routers import campaigns


class _Collection:
    def __init__(self, docs):
        self.docs = docs

    def find_one(self, query, projection=None):
        return next((doc for doc in self.docs if all(doc.get(key) == value for key, value in query.items())), None)

    def find(self, query, projection=None):
        return [doc for doc in self.docs if all(doc.get(key) == value for key, value in query.items())]


def _run_timeline(monkeypatch, deal, current_steps, current_edges, events):
    graph_steps = [
        {"id": "start", "type": "action", "data": {"channel": "email", "label": "Saved email"}},
        {"id": "branch", "type": "condition", "data": {"condition": "reply_received", "label": "Did they reply?"}},
        {"id": "yes", "type": "end", "data": {"label": "Replied"}},
        {"id": "no", "type": "end", "data": {"label": "No reply"}},
    ]
    graph_edges = [
        {"source": "start", "target": "branch", "data": {}},
        {"source": "branch", "target": "yes", "data": {"condition": "yes"}},
        {"source": "branch", "target": "no", "data": {"condition": "no"}},
    ]
    campaign = SimpleNamespace(
        sequence_steps=current_steps,
        sequence_edges=current_edges,
        sequence_active=True,
        has_access=lambda user_id: True,
    )
    monkeypatch.setattr(campaigns.models.Campaign, "get", lambda campaign_id: campaign)
    collections = {
        "deals": _Collection([{
            "_id": "deal-id", "lead_id": "lead-id", "campaign_id": "campaign-id",
            "sequence_position": deal.get("sequence_position"), "sequence_done": False,
            "sequence_graph_snapshot": {"steps": graph_steps, "edges": graph_edges, "revision": 2},
        }]),
        "sequence_events": _Collection(events),
        "tasks": _Collection([]),
    }
    monkeypatch.setattr(campaigns, "get_mongodb_collection", lambda name: collections.get(name))
    return asyncio.run(campaigns.get_lead_sequence_timeline("campaign-id", "lead-id", user_id="owner"))


def test_timeline_uses_deal_graph_snapshot_and_leaves_future_branch_unresolved(monkeypatch):
    # The campaign graph has changed and no longer contains the saved IDs.
    result = _run_timeline(
        monkeypatch,
        {"sequence_position": "branch"},
        [{"id": "new", "type": "end", "data": {"label": "Current graph"}}],
        [],
        [],
    )

    assert [entry["stepId"] for entry in result["timeline"]] == ["start", "branch"]
    assert result["timeline"][-1]["branchStatus"] == "unresolved"


def test_timeline_follows_recorded_condition_outcome(monkeypatch):
    result = _run_timeline(
        monkeypatch,
        {"sequence_position": "yes"},
        [],
        [],
        [{"campaign_id": "campaign-id", "deal_id": "deal-id", "event": "condition_evaluated", "step_id": "branch", "reason": "reply_received:yes"}],
    )

    ids = [entry["stepId"] for entry in result["timeline"]]
    assert ids == ["start", "branch", "yes"]
    assert "no" not in ids
    assert result["timeline"][1]["branchStatus"] == "resolved"
