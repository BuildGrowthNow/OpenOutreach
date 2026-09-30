import asyncio
from types import SimpleNamespace

from openoutreach.api_v2.routers import campaigns


class _Collection:
    def __init__(self, docs):
        self.docs = docs

    def find_one(self, query, projection=None):
        return next((doc for doc in self.docs if all(doc.get(key) == value for key, value in query.items())), None)

    def find(self, query, projection=None):
        return [doc for doc in self.docs if all(
            (doc.get(key) in value["$in"] if "$in" in value else doc.get(key) != value["$ne"])
            if isinstance(value, dict) and ("$in" in value or "$ne" in value)
            else doc.get(key) == value
            for key, value in query.items()
        )]

    def count_documents(self, query):
        return len(self.find(query))


def test_sequence_readiness_reports_coverage_and_disabled_whatsapp_cloud(monkeypatch):
    campaign = SimpleNamespace(
        sequence_steps=[{"id": "send-wa", "type": "action", "data": {"channel": "whatsapp", "label": "WhatsApp touch", "requires": ["phone"]}}],
        sequence_edges=[],
        sequence_active=False,
        whatsapp_profile_id="wa-1",
        channel_settings={"whatsapp": {"message_template": "Hello"}},
        linkedin_profile_id=None,
        has_access=lambda user_id: True,
    )
    monkeypatch.setattr(campaigns.models.Campaign, "get", lambda campaign_id: campaign)
    from openoutreach.config import settings
    monkeypatch.setattr(settings, "DAEMON_V2_WHATSAPP_ENABLED", False)
    deals = _Collection([{"_id": "deal-1", "campaign_id": "campaign-1", "lead_id": "lead-1", "state": "Qualified", "sequence_done": False}])
    collections = {
        "deals": deals,
        "leads": _Collection([{"_id": "lead-1", "phone": "+15550000000"}]),
        "whatsapp_profiles": _Collection([{"_id": "wa-1", "user_id": "owner", "status": "connected"}]),
    }
    monkeypatch.setattr(campaigns, "get_mongodb_collection", lambda name: collections.get(name))

    result = asyncio.run(campaigns.get_sequence_readiness("campaign-1", user_id="owner"))

    assert result["channels"]["whatsapp"] == {
        "configured": True, "healthy": True, "execution_enabled": False, "status": "Ready",
    }
    assert result["step_coverage"] == [{"step_id": "send-wa", "label": "WhatsApp touch", "count": 1, "total": 1, "pct": 100}]
    assert result["affected_deals"] == 1
    assert any("cloud execution is disabled" in warning for warning in result["warnings"])
