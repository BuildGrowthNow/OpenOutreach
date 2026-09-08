"""Deterministic two-lead dry run through LinkedIn, email, and WhatsApp branches."""

from datetime import datetime, timedelta, timezone

from openoutreach.core.sequence_executor import resolve_sequence_tasks
from openoutreach.mongodb.models import Campaign, Deal


def _value(doc, key):
    for part in key.split("."):
        if not isinstance(doc, dict):
            return None
        doc = doc.get(part)
    return doc


def _matches(doc, query):
    for key, expected in query.items():
        if key == "$or":
            if not any(_matches(doc, item) for item in expected):
                return False
            continue
        actual = _value(doc, key)
        if isinstance(expected, dict):
            if "$in" in expected and actual not in expected["$in"]:
                return False
            if "$ne" in expected and actual == expected["$ne"]:
                return False
            if "$exists" in expected and (actual is not None) != expected["$exists"]:
                return False
            if "$lte" in expected and (actual is None or actual > expected["$lte"]):
                return False
        elif actual != expected:
            return False
    return True


class _Result:
    modified_count = 1


class _Collection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])

    def find(self, query):
        return [dict(doc) for doc in self.docs if _matches(doc, query)]

    def find_one(self, query, projection=None):
        for doc in self.docs:
            if _matches(doc, query):
                return dict(doc)
        return None

    def count_documents(self, query):
        return sum(1 for doc in self.docs if _matches(doc, query))

    def insert_one(self, doc):
        self.docs.append(dict(doc))

    def update_one(self, query, update, upsert=False):
        target = next((doc for doc in self.docs if _matches(doc, query)), None)
        if target is None and upsert:
            target = {key: value for key, value in query.items() if not key.startswith("$")}
            self.docs.append(target)
        if target is None:
            return _Result()
        for key, value in update.get("$set", {}).items():
            cursor = target
            parts = key.split(".")
            for part in parts[:-1]:
                cursor = cursor.setdefault(part, {})
            cursor[parts[-1]] = value
        for key, value in update.get("$setOnInsert", {}).items():
            target.setdefault(key, value)
        for key, value in update.get("$inc", {}).items():
            target[key] = target.get(key, 0) + value
        return _Result()


def test_two_lead_sequence_dry_run_takes_yes_and_no_channel_branches(monkeypatch):
    now = datetime.now(timezone.utc)
    steps = [
        {"id": "linkedin", "type": "action", "data": {"action": "follow_up", "channel": "linkedin", "message": {"content_mode": "static", "body": "Hi from LinkedIn"}}},
        {"id": "check", "type": "condition", "data": {"condition": "link_clicked", "link_key": "demo", "observation_window_hours": 2}},
        {"id": "email", "type": "action", "data": {"action": "send_email", "channel": "email", "message": {"content_mode": "static", "subject": "Next step", "body": "Email branch"}}},
        {"id": "whatsapp", "type": "action", "data": {"action": "send_whatsapp", "channel": "whatsapp", "message": {"content_mode": "static", "body": "WhatsApp branch"}}},
        {"id": "yes_end", "type": "end", "data": {}},
        {"id": "no_end", "type": "end", "data": {}},
    ]
    edges = [
        {"id": "linkedin-check", "source": "linkedin", "target": "check", "data": {}},
        {"id": "check-email", "source": "check", "target": "email", "data": {"condition": "yes"}},
        {"id": "check-whatsapp", "source": "check", "target": "whatsapp", "data": {"condition": "no"}},
        {"id": "email-end", "source": "email", "target": "yes_end", "data": {}},
        {"id": "whatsapp-end", "source": "whatsapp", "target": "no_end", "data": {}},
    ]
    campaign = Campaign(_id="campaign-1", user_id="owner", sequence_active=True, sequence_steps=steps, sequence_edges=edges, channel_sequence=["linkedin", "email", "whatsapp"])
    deals = _Collection([
        Deal(_id="deal-yes", lead_id="lead-yes", campaign_id="campaign-1", user_id="owner", state=Deal.DealState.DISCOVERED).to_dict(),
        Deal(_id="deal-no", lead_id="lead-no", campaign_id="campaign-1", user_id="owner", state=Deal.DealState.DISCOVERED).to_dict(),
    ])
    leads = _Collection([
        {"_id": "lead-yes", "api_email": "yes@example.com", "phone": "+111"},
        {"_id": "lead-no", "api_email": "no@example.com", "phone": "+222"},
    ])
    tasks = _Collection()
    tracking_events = _Collection()
    sequence_events = _Collection()
    collections = {"deals": deals, "leads": leads, "tasks": tasks, "tracking_events": tracking_events, "sequence_events": sequence_events, "chat_messages": _Collection(), "tracked_links": _Collection([{"_id": "link-1", "campaign_id": "campaign-1", "key": "demo"}])}
    monkeypatch.setattr("openoutreach.core.sequence_executor.get_mongodb_collection", lambda name: collections.get(name))

    def unlock():
        for deal in deals.docs:
            deal.pop("sequence_lock_until", None)

    assert resolve_sequence_tasks(campaign, "owner") == 2
    assert {task["payload"]["step_id"] for task in tasks.docs} == {"linkedin"}
    for task in tasks.docs:
        task["status"] = "completed"
    for deal in deals.docs:
        deal["sequence_last_message_at"] = now
        deal["sequence_last_step_id"] = "linkedin"

    tracking_events.insert_one({"deal_id": "deal-yes", "event": "click", "tracked_link_id": "link-1", "created_at": now + timedelta(minutes=5)})
    unlock()
    assert resolve_sequence_tasks(campaign, "owner") == 0
    assert {doc.get("sequence_position") for doc in deals.docs} == {"check"}
    deals.update_one({"_id": "deal-no"}, {"$set": {"sequence_last_message_at": now - timedelta(hours=3)}})
    unlock()
    assert resolve_sequence_tasks(campaign, "owner") == 0

    positions = {doc["_id"]: doc.get("sequence_position") for doc in deals.docs}
    assert positions == {"deal-yes": "email", "deal-no": "whatsapp"}

    unlock()
    assert resolve_sequence_tasks(campaign, "owner") == 2
    branch_tasks = {(task["payload"]["deal_id"], task["payload"]["step_id"]): task["channel"] for task in tasks.docs if task["payload"]["step_id"] != "linkedin"}
    assert branch_tasks == {("deal-yes", "email"): "email", ("deal-no", "whatsapp"): "whatsapp"}


def test_reactivation_requeues_cancelled_sequence_task_without_advancing(monkeypatch):
    steps = [
        {"id": "linkedin", "type": "action", "data": {"action": "follow_up", "channel": "linkedin", "message": {"content_mode": "static", "body": "Hello"}}},
        {"id": "end", "type": "end", "data": {}},
    ]
    campaign = Campaign(
        _id="campaign-reactivate", user_id="owner", sequence_active=True,
        sequence_steps=steps,
        sequence_edges=[{"id": "linkedin-end", "source": "linkedin", "target": "end", "data": {}}],
    )
    deals = _Collection([
        Deal(_id="deal-reactivate", lead_id="lead-reactivate", campaign_id=campaign._id, user_id="owner", state=Deal.DealState.DISCOVERED).to_dict(),
    ])
    tasks = _Collection()
    collections = {
        "deals": deals,
        "leads": _Collection([{"_id": "lead-reactivate"}]),
        "tasks": tasks,
        "sequence_events": _Collection(),
        "chat_messages": _Collection(),
    }
    monkeypatch.setattr("openoutreach.core.sequence_executor.get_mongodb_collection", lambda name: collections.get(name))

    assert resolve_sequence_tasks(campaign, "owner") == 1
    tasks.docs[0]["status"] = "cancelled"
    deals.docs[0].pop("sequence_lock_until", None)

    assert resolve_sequence_tasks(campaign, "owner") == 0
    assert tasks.docs[0]["status"] == "pending"
    assert deals.docs[0].get("sequence_position") is None
