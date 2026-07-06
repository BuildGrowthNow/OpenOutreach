import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from openoutreach.core.models import Campaign
from openoutreach.crm.models import Deal, Lead, Note, Message
from openoutreach.crm.models.deal import DealState

@pytest.mark.django_db
def test_leads_dashboard_and_campaign_cascade():
    user = User.objects.create_user(username="test-user", password="password123")
    campaign = Campaign.objects.create(name="Test Campaign")
    campaign.users.add(user)

    # Lead 1: has a deal with a campaign
    lead1 = Lead.objects.create(
        public_identifier="lead-one",
        linkedin_url="https://www.linkedin.com/in/lead-one/",
    )
    deal1 = Deal.objects.create(lead=lead1, campaign=campaign, state=DealState.QUALIFIED)

    # Attach notes and messages to lead1's deal
    Note.objects.create(deal=deal1, content="Test note", created_by=user)
    Message.objects.create(deal=deal1, content="Test message", is_outgoing=True)

    # Lead 2: has a deal with the same campaign
    lead2 = Lead.objects.create(
        public_identifier="lead-two",
        linkedin_url="https://www.linkedin.com/in/lead-two/",
    )
    deal2 = Deal.objects.create(lead=lead2, campaign=campaign, state=DealState.QUALIFIED)

    client = APIClient()
    client.force_authenticate(user=user)

    # 1. Verify GET /api/leads works with status filter (Bug 1 verification)
    response = client.get("/api/leads?status=QUALIFIED")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 2

    # 2. Verify GET /api/leads/<id>/ works (LeadDetailView details)
    response = client.get(f"/api/leads/{lead1.id}/")
    assert response.status_code == 200
    assert response.json()["deals"][0]["campaignId"] == campaign.id

    # 3. Simulate campaign delete (Bug 3 verification)
    # This will cascade delete deal1 and deal2 because on_delete=models.CASCADE
    campaign.delete()

    # Now verify dashboard leads fetch doesn't crash (Bug 3 / Bug 1 verification post-delete)
    response = client.get("/api/leads?status=QUALIFIED")
    assert response.status_code == 200
    # Because campaign was deleted, both deals are gone, so no leads should match QUALIFIED status
    assert len(response.json()["data"]) == 0

    # Also check /api/leads without status param
    response = client.get("/api/leads")
    assert response.status_code == 200
    # The leads still exist, but they have no deals
    assert len(response.json()["data"]) == 2
    for item in response.json()["data"]:
        assert item["state"] is None
        assert item["campaignId"] is None
        assert item["campaignName"] is None

    # 4. Verify LeadDetailView with None campaign (Bug 2 verification)
    response = client.get(f"/api/leads/{lead1.id}/")
    assert response.status_code == 200
    # Since the campaign/deal were deleted, deals_data is empty
    assert len(response.json()["deals"]) == 0
