from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from openoutreach.chat.models import ChatMessage
from openoutreach.core.models import Campaign
from openoutreach.crm.models import Deal, Lead
from openoutreach.crm.models.deal import DealState
from openoutreach.linkedin.models import ActionLog, LinkedInProfile


@pytest.mark.django_db
def test_campaign_list_stats_use_real_activity_counts():
    user = User.objects.create_user(username="analytics-user", password="password123")
    campaign = Campaign.objects.create(name="Analytics Campaign")
    campaign.users.add(user)

    profile = LinkedInProfile.objects.create(
        user=user,
        linkedin_username="analytics@example.com",
        linkedin_password="secret",
    )

    states = [
        DealState.QUALIFIED,
        DealState.READY_TO_CONNECT,
        DealState.PENDING,
        DealState.CONNECTED,
        DealState.COMPLETED,
        DealState.FAILED,
        DealState.NO_EMAIL,
    ]
    deals = []
    for index, state in enumerate(states):
        lead = Lead.objects.create(
            public_identifier=f"analytics-lead-{index}",
            linkedin_url=f"https://www.linkedin.com/in/analytics-lead-{index}/",
        )
        deals.append(Deal.objects.create(lead=lead, campaign=campaign, state=state))

    ActionLog.objects.create(
        linkedin_profile=profile,
        campaign=campaign,
        action_type=ActionLog.ActionType.CONNECT,
    )
    ActionLog.objects.create(
        linkedin_profile=profile,
        campaign=campaign,
        action_type=ActionLog.ActionType.CONNECT,
    )
    ActionLog.objects.create(
        linkedin_profile=profile,
        campaign=campaign,
        action_type=ActionLog.ActionType.FOLLOW_UP,
    )

    ChatMessage.objects.create(
        deal=deals[3],
        owner=user,
        linkedin_urn="urn:li:msg:analytics-1",
        is_outgoing=False,
        content="Thanks for reaching out",
    )

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get("/api/campaigns/")

    assert response.status_code == 200, response.content
    payload = response.json()
    stats = payload["data"][0]["stats"]

    assert stats["totalLeads"] == 7
    assert stats["activeLeads"] == 4
    assert stats["connectionsSent"] == 2
    assert stats["connectionsAccepted"] == 1
    assert stats["messagesSent"] == 1
    assert stats["messagesReplied"] == 1
    assert stats["responses"] == 1
    assert stats["connectionAcceptRate"] == 50.0
    assert stats["responseRate"] == 100.0
    assert stats["conversionRate"] == 100.0


@pytest.mark.django_db
def test_analytics_overview_filters_by_campaign_and_period():
    user = User.objects.create_user(username="overview-user", password="password123")
    included_campaign = Campaign.objects.create(name="Included Campaign")
    excluded_campaign = Campaign.objects.create(name="Excluded Campaign")
    included_campaign.users.add(user)
    excluded_campaign.users.add(user)

    profile = LinkedInProfile.objects.create(
        user=user,
        linkedin_username="overview@example.com",
        linkedin_password="secret",
    )

    included_lead = Lead.objects.create(
        public_identifier="overview-included",
        linkedin_url="https://www.linkedin.com/in/overview-included/",
    )
    excluded_lead = Lead.objects.create(
        public_identifier="overview-excluded",
        linkedin_url="https://www.linkedin.com/in/overview-excluded/",
    )

    Deal.objects.create(
        lead=included_lead,
        campaign=included_campaign,
        state=DealState.CONNECTED,
        creation_date=timezone.now() - timedelta(days=1),
    )
    Deal.objects.create(
        lead=excluded_lead,
        campaign=excluded_campaign,
        state=DealState.CONNECTED,
        creation_date=timezone.now() - timedelta(days=1),
    )

    recent_connect = ActionLog.objects.create(
        linkedin_profile=profile,
        campaign=included_campaign,
        action_type=ActionLog.ActionType.CONNECT,
    )
    ActionLog.objects.filter(pk=recent_connect.pk).update(
        created_at=timezone.now() - timedelta(days=1)
    )

    old_connect = ActionLog.objects.create(
        linkedin_profile=profile,
        campaign=included_campaign,
        action_type=ActionLog.ActionType.CONNECT,
    )
    ActionLog.objects.filter(pk=old_connect.pk).update(
        created_at=timezone.now() - timedelta(days=40)
    )

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get(
        f"/api/analytics/overview/?campaign_id={included_campaign.pk}&period=30d"
    )

    assert response.status_code == 200, response.content
    payload = response.json()
    assert payload["stats"]["connectionsSent"] == 1
    assert payload["stats"]["connectionsAccepted"] == 1
    assert payload["stats"]["connectionAcceptRate"] == 100.0
    assert payload["campaigns"][0]["id"] == str(included_campaign.pk)
    assert len(payload["campaigns"]) == 1


@pytest.mark.django_db
def test_campaign_analytics_counts_recent_replies_without_fake_rate():
    user = User.objects.create_user(
        username="analytics-api-user", password="password123"
    )
    campaign = Campaign.objects.create(name="Analytics API Campaign")
    campaign.users.add(user)

    lead = Lead.objects.create(
        public_identifier="analytics-api-lead",
        linkedin_url="https://www.linkedin.com/in/analytics-api-lead/",
    )
    old_deal = Deal.objects.create(
        lead=lead,
        campaign=campaign,
        state=DealState.QUALIFIED,
        creation_date=timezone.now() - timedelta(days=45),
    )

    ChatMessage.objects.create(
        deal=old_deal,
        owner=user,
        linkedin_urn="urn:li:msg:analytics-api-1",
        is_outgoing=False,
        content="Recent reply on an older deal",
        creation_date=timezone.now() - timedelta(days=1),
    )

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get(f"/api/campaigns/{campaign.pk}/analytics/?period=30d")

    assert response.status_code == 200, response.content
    payload = response.json()
    stats = payload["stats"]

    assert stats["connections_sent"] == 0
    assert stats["connections_accepted"] == 0
    assert stats["messages_replied"] == 1
    assert stats["responses"] == 1
    assert stats["response_rate"] == 0
    assert stats["conversion_rate"] == 0
