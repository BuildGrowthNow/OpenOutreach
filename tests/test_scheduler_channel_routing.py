from itertools import permutations
from types import SimpleNamespace

import pytest

from openoutreach.core.scheduler import _route_deal_channels


class _Collection:
    def __init__(self, docs):
        self.docs = docs

    def find(self, query, projection=None):
        return [doc for doc in self.docs if all(
            doc.get(key) == value if not isinstance(value, dict) else
            ("$in" not in value or doc.get(key) in value["$in"])
            for key, value in query.items()
        )]

    def find_one(self, query, projection=None):
        return next((doc for doc in self.docs if all(doc.get(key) == value for key, value in query.items())), None)

    def update_one(self, query, update):
        doc = self.find_one(query)
        if doc:
            doc.update(update.get("$set", {}))


@pytest.mark.parametrize("order", list(permutations(("linkedin", "email", "whatsapp"))))
def test_legacy_channel_routing_respects_configured_order(monkeypatch, order):
    deals = _Collection([{"_id": "deal", "campaign_id": "campaign", "lead_id": "lead", "state": "Qualified", "active_channel": "linkedin"}])
    leads = _Collection([{"_id": "lead", "linkedin_url": "https://linkedin.example/lead", "api_email": "lead@example.com", "phone": "+15550000000"}])
    monkeypatch.setattr("openoutreach.mongodb.connection.get_mongodb_collection", lambda name: {
        "deals": deals, "leads": leads, "whatsapp_profiles": _Collection([{"_id": "wa-profile", "status": "connected"}]),
    }.get(name))
    campaign = SimpleNamespace(pk="campaign", sequence_active=False, channel_sequence=list(order), whatsapp_profile_id="wa-profile")

    _route_deal_channels(campaign)

    expected = order[0]
    assert deals.docs[0]["active_channel"] == expected
    assert deals.docs[0]["state"] == ("email_queued" if expected == "email" else "Qualified")


@pytest.mark.parametrize(
    ("lead", "order", "expected"),
    [
        ({"_id": "lead", "phone": "+15550000000"}, ["email", "linkedin", "whatsapp"], "whatsapp"),
        ({"_id": "lead", "linkedin_url": "https://linkedin.example/lead"}, ["email", "whatsapp", "linkedin"], "linkedin"),
        ({"_id": "lead", "contact_info": {"email": "lead@example.com"}}, ["email", "linkedin"], "email"),
        ({"_id": "lead"}, ["email", "whatsapp", "linkedin"], None),
    ],
)
def test_legacy_routing_skips_channels_without_usable_lead_data(monkeypatch, lead, order, expected):
    deals = _Collection([{"_id": "deal", "campaign_id": "campaign", "lead_id": "lead", "state": "Qualified", "active_channel": "linkedin"}])
    leads = _Collection([lead])
    monkeypatch.setattr("openoutreach.mongodb.connection.get_mongodb_collection", lambda name: {
        "deals": deals, "leads": leads, "whatsapp_profiles": _Collection([{"_id": "wa-profile", "status": "connected"}]),
    }.get(name))
    campaign = SimpleNamespace(pk="campaign", sequence_active=False, channel_sequence=order, whatsapp_profile_id="wa-profile")

    _route_deal_channels(campaign)

    if expected is None:
        assert deals.docs[0]["active_channel"] == "linkedin"
        assert deals.docs[0]["state"] == "Qualified"
    else:
        assert deals.docs[0]["active_channel"] == expected


def test_legacy_routing_leaves_active_visual_sequence_untouched(monkeypatch):
    deals = _Collection([{"_id": "deal", "campaign_id": "campaign", "lead_id": "lead", "state": "Qualified", "active_channel": "linkedin"}])
    leads = _Collection([{"_id": "lead", "api_email": "lead@example.com"}])
    monkeypatch.setattr("openoutreach.mongodb.connection.get_mongodb_collection", lambda name: {"deals": deals, "leads": leads}.get(name))
    campaign = SimpleNamespace(pk="campaign", sequence_active=True, channel_sequence=["email"])

    _route_deal_channels(campaign)

    assert deals.docs[0]["state"] == "Qualified"
    assert deals.docs[0]["active_channel"] == "linkedin"
