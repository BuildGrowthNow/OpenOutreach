"""Integration tests for MongoDB models."""
import pytest
from datetime import datetime, timezone as tz

from openoutreach.mongodb.models import (
    Campaign, Task, Deal, Lead, SiteConfig, User,
    ActionLog, LinkedInProfile, SearchKeyword, Mailbox, ChatMessage
)
from openoutreach.crm.models import DealState, Outcome


class TestModelManagers:
    """Test that all models have working manager interfaces."""

    def test_campaign_manager(self, test_user, clean_test_db):
        """Test Campaign.objects manager."""
        campaign = Campaign(
            name="Manager Test",
            user_id=test_user.pk,
            status="active",
            test=True
        )
        campaign.save()

        # Test filter
        results = Campaign.objects.filter(name="Manager Test")
        assert len(results) == 1
        assert results[0].name == "Manager Test"

        # Test get
        found = Campaign.objects.get(name="Manager Test")
        assert found is not None
        assert found.pk == campaign.pk

        # Test all
        all_campaigns = Campaign.objects.all()
        assert any(c.pk == campaign.pk for c in all_campaigns)

    def test_deal_manager(self, test_campaign, test_lead, clean_test_db):
        """Test Deal.objects manager."""
        deal = Deal(
            campaign_id=test_campaign.pk,
            lead_id=test_lead.pk,
            state=DealState.QUALIFIED,
            test=True
        )
        deal.save()

        # Test filter
        results = Deal.objects.filter(state=DealState.QUALIFIED.value)
        assert any(d.pk == deal.pk for d in results)

        # Test get
        found = Deal.objects.get(campaign_id=test_campaign.pk, lead_id=test_lead.pk)
        assert found is not None
        assert found.pk == deal.pk

    def test_task_manager(self, test_campaign, clean_test_db):
        """Test Task.objects manager."""
        task = Task(
            task_type="connect",
            payload={"campaign_id": test_campaign.pk},
            status="PENDING",
            test=True
        )
        task.save()

        # Test filter
        results = Task.objects.filter(task_type="connect", status="PENDING")
        assert any(t.pk == task.pk for t in results)

        # Test pending
        pending = Task.objects.pending()
        assert any(t.pk == task.pk for t in pending)

    def test_lead_classmethods(self, clean_test_db):
        """Test Lead direct methods."""
        lead = Lead(
            public_identifier="method-test",
            full_name="Method Test",
            test=True
        )
        lead.save()

        # Test get
        found = Lead.get(lead.pk)
        assert found is not None
        assert found.pk == lead.pk

        # Test get_by_public_identifier
        found_by_pid = Lead.get_by_public_identifier("method-test")
        assert found_by_pid is not None
        assert found_by_pid.pk == lead.pk


class TestModelFields:
    """Test that models have required fields."""

    def test_task_fields(self, test_campaign, clean_test_db):
        """Test Task model fields."""
        task = Task(
            task_type="connect",
            payload={"campaign_id": test_campaign.pk},
            status="PENDING",
            test=True
        )
        task.save()

        assert hasattr(task, "task_type")
        assert hasattr(task, "status")
        assert hasattr(task, "payload")
        assert hasattr(task, "created_at")
        assert hasattr(task, "scheduled_at")
        # Note: Task intentionally does NOT have error_message field

    def test_deal_fields(self, test_campaign, test_lead, clean_test_db):
        """Test Deal model fields."""
        deal = Deal(
            campaign_id=test_campaign.pk,
            lead_id=test_lead.pk,
            state=DealState.QUALIFIED,
            outcome=Outcome.UNKNOWN,
            reason="Test reason",
            test=True
        )
        deal.save()

        assert hasattr(deal, "state")
        assert hasattr(deal, "outcome")
        assert hasattr(deal, "reason")
        assert hasattr(deal, "campaign_id")
        assert hasattr(deal, "lead_id")

    def test_campaign_multi_tenant_fields(self, test_user, clean_test_db):
        """Test Campaign multi-tenant fields."""
        campaign = Campaign(
            name="Multi-tenant Test",
            user_id=test_user.pk,
            linkedin_profile_id="profile123",
            team_member_ids=["user1", "user2"],
            test=True
        )
        campaign.save()

        assert campaign.user_id == test_user.pk
        assert campaign.linkedin_profile_id == "profile123"
        assert "user1" in campaign.team_member_ids
        assert campaign.has_access(test_user.pk)
        assert campaign.has_access("user1")


class TestModelMethods:
    """Test critical model methods."""

    def test_task_lifecycle(self, test_campaign, clean_test_db):
        """Test Task state transitions."""
        task = Task(
            task_type="connect",
            payload={"campaign_id": test_campaign.pk},
            status="PENDING",
            test=True
        )
        task.save()

        # Mark running
        task.mark_running()
        assert task.status == "RUNNING"

        # Mark completed
        task.mark_completed()
        assert task.status == "COMPLETED"

        # Create new task for failure test
        task2 = Task(
            task_type="connect",
            payload={"campaign_id": test_campaign.pk},
            status="PENDING",
            test=True
        )
        task2.save()
        task2.mark_running()

        # Mark failed (no error_message parameter by design)
        task2.mark_failed()
        assert task2.status == "FAILED"

    def test_deal_get_by_lead_and_campaign(self, test_campaign, test_lead, clean_test_db):
        """Test Deal.get_by_lead_and_campaign method."""
        deal = Deal(
            campaign_id=test_campaign.pk,
            lead_id=test_lead.pk,
            state=DealState.QUALIFIED,
            test=True
        )
        deal.save()

        found = Deal.get_by_lead_and_campaign(test_lead.pk, test_campaign.pk)
        assert found is not None
        assert found.pk == deal.pk

    def test_lead_get_methods(self, clean_test_db):
        """Test Lead.get and Lead.get_by_public_id."""
        lead = Lead(
            public_identifier="get-test",
            full_name="Get Test",
            test=True
        )
        lead.save()

        # Test get by ID
        found = Lead.get(lead.pk)
        assert found is not None
        assert found.pk == lead.pk

        # Test get by public_identifier
        found_by_pid = Lead.get_by_public_identifier("get-test")
        assert found_by_pid is not None
        assert found_by_pid.pk == lead.pk

    def test_site_config_singleton(self, clean_test_db):
        """Test SiteConfig.load singleton pattern."""
        # First load creates default
        config1 = SiteConfig.load()
        assert config1 is not None

        # Second load returns same config
        config2 = SiteConfig.load()
        assert config2.pk == config1.pk


class TestActionLogEnums:
    """Test ActionLog.ActionType constants."""

    def test_action_type_exists(self):
        """Test that ActionLog.ActionType has required constants."""
        assert hasattr(ActionLog, "ActionType")
        assert hasattr(ActionLog.ActionType, "CONNECTION_SENT")
        assert hasattr(ActionLog.ActionType, "CONNECTION_ACCEPTED")
        assert hasattr(ActionLog.ActionType, "MESSAGE_SENT")
        assert hasattr(ActionLog.ActionType, "MESSAGE_RECEIVED")


class TestDealStateEnum:
    """Test DealState enum values."""

    def test_deal_states(self):
        """Test all DealState values exist."""
        states = [
            DealState.DISCOVERED,
            DealState.QUALIFIED,
            DealState.NO_EMAIL,
            DealState.READY_TO_CONNECT,
            DealState.PENDING,
            DealState.CONNECTED,
            DealState.COMPLETED,
            DealState.FAILED,
        ]
        for state in states:
            assert state.value is not None


class TestOutcomeEnum:
    """Test Outcome enum values."""

    def test_outcomes(self):
        """Test all Outcome values exist."""
        outcomes = [
            Outcome.CONVERTED,
            Outcome.NOT_INTERESTED,
            Outcome.WRONG_FIT,
            Outcome.NO_BUDGET,
            Outcome.HAS_SOLUTION,
            Outcome.BAD_TIMING,
            Outcome.UNRESPONSIVE,
            Outcome.UNKNOWN,
        ]
        for outcome in outcomes:
            assert outcome.value is not None
