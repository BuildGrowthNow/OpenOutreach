import pytest
from fastapi import HTTPException

from openoutreach.api_v2.routers import campaign_templates, links
from openoutreach.api_v2.routers.campaign_templates import CreateCampaignFromTemplate, TemplatePatch


class _Result:
    matched_count = 1
    deleted_count = 0
    upserted_id = None


class _Collection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])

    def find_one(self, query, projection=None):
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in query.items() if not isinstance(value, dict)):
                return dict(doc)
        return None

    def update_one(self, query, update, upsert=False):
        doc = self.find_one(query)
        if doc is None:
            doc = {key: value for key, value in query.items() if not key.startswith("$")}
            self.docs.append(doc)
        doc.update(update.get("$set", {}))
        return _Result()

    def delete_many(self, query):
        return _Result()

    def count_documents(self, query):
        return 1 if query else len(self.docs)


@pytest.mark.asyncio
async def test_shared_template_member_can_read_but_cannot_update(monkeypatch):
    templates = _Collection([{
        "_id": "template-1", "name": "Shared", "owner_user_id": "owner",
        "created_by_id": "owner", "visibility": "team", "team_member_ids": ["member"],
        "sequence_steps": [], "sequence_edges": [], "version": 1,
    }])
    monkeypatch.setattr(campaign_templates, "get_mongodb_collection", lambda name: templates)
    assert campaign_templates._get_template("template-1", "member").name == "Shared"
    with pytest.raises(HTTPException) as error:
        await campaign_templates.update_campaign_template("template-1", TemplatePatch(description="nope"), "member")
    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_template_campaign_copies_user_settings_without_template_members(monkeypatch):
    collections = {"campaigns": _Collection(), "tracked_links": _Collection(), "mailboxes": _Collection()}
    source = {
        "_id": "template-1", "name": "Shared", "owner_user_id": "owner", "created_by_id": "owner",
        "version": 3, "channels": ["whatsapp"], "sequence_schema_version": 1,
        "sequence_steps": [
            {"id": "send", "type": "action", "data": {"action": "send_whatsapp", "channel": "whatsapp", "message": {"content_mode": "static", "body": "hello"}}},
            {"id": "end", "type": "end", "data": {}},
        ],
        "sequence_edges": [{"id": "send-end", "source": "send", "target": "end", "data": {}}],
        "campaign_defaults": {}, "link_definitions": [], "safety_defaults": {"stop_on_reply": True},
    }
    monkeypatch.setattr(campaign_templates, "_get_template", lambda template_id, user_id: source)
    monkeypatch.setattr(campaign_templates, "get_mongodb_collection", lambda name: collections.get(name))
    monkeypatch.setattr("openoutreach.mongodb.models.get_mongodb_collection", lambda name: collections.get(name))

    result = await campaign_templates.create_campaign_from_template(
        "template-1",
        CreateCampaignFromTemplate(
            name="Configured campaign", whatsapp_profile_id="wa-1", lead_source="maps",
            icp_titles=["CEO"], target_company_size="11-50", maps_query="coffee",
            maps_country_code="GE", maps_backends=["google"], maps_location="Tbilisi",
        ),
        "new-owner",
    )
    campaign_doc = collections["campaigns"].docs[0]
    assert campaign_doc["team_member_ids"] == []
    assert campaign_doc["whatsapp_profile_id"] == "wa-1"
    assert campaign_doc["lead_source"] == "maps"
    assert campaign_doc["icp_titles"] == ["CEO"]
    assert campaign_doc["target_company_size"] == "11-50"
    assert campaign_doc["maps_query"] == "coffee"
    assert campaign_doc["maps_country_code"] == "GE"
    assert campaign_doc["maps_backends"] == ["google"]
    assert campaign_doc["maps_location"] == "Tbilisi"
    assert result["campaign"]["_id"] == campaign_doc["_id"]


def test_link_lookup_is_tenant_scoped(monkeypatch):
    class CampaignStub:
        user_id = "owner"

        def has_access(self, user_id):
            return user_id == "owner"

    monkeypatch.setattr(links.Campaign, "get", classmethod(lambda cls, campaign_id: CampaignStub()))
    monkeypatch.setattr(links, "get_mongodb_collection", lambda name: _Collection([{
        "_id": "link-1", "campaign_id": "campaign-1", "user_id": "owner", "key": "demo",
        "name": "Demo", "destination_url": "https://example.com", "is_active": True,
    }]))
    with pytest.raises(HTTPException) as error:
        links._find_link("link-1", "campaign-1", "other-tenant")
    assert error.value.status_code == 404
