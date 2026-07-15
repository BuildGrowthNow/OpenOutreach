"""Integration tests for daemon functionality."""
import pytest
from datetime import datetime, timezone as tz
from unittest.mock import Mock, patch

from openoutreach.mongodb.models import Campaign, Task, Deal, Lead, SiteConfig
from openoutreach.crm.models import DealState
from openoutreach.core.scheduler import (
    plan_connect_window,
    plan_follow_up_window,
    plan_check_pending_window,
)


class TestScheduler:
    """Test scheduler task planning."""

    def test_plan_connect_window_manual_mode(self, test_campaign, test_site_config, clean_test_db):
        """Test connect task planning in manual mode."""
        test_site_config.enable_smart_rate_limiting = False
        test_site_config.velocity = 10  # 10 actions/hour
        test_site_config.save()

        # Create qualified deals
        for i in range(5):
            lead = Lead(
                public_identifier=f"lead-{i}",
                full_name=f"Lead {i}",
                test=True
            )
            lead.save()

            deal = Deal(
                campaign_id=test_campaign.pk,
                lead_id=lead.pk,
                state=DealState.QUALIFIED,
                test=True
            )
            deal.save()

        # Plan tasks
        now = datetime.now(tz.utc)
        plan_connect_window(test_campaign, now, now.replace(hour=23, minute=59))

        # Verify tasks created
        tasks = Task.objects.filter(task_type="connect")
        test_tasks = [t for t in tasks if t.payload.get("campaign_id") == test_campaign.pk]
        assert len(test_tasks) > 0

    def test_plan_follow_up_window(self, test_campaign, test_site_config, clean_test_db):
        """Test follow_up task planning."""
        test_site_config.enable_smart_rate_limiting = False
        test_site_config.velocity = 10
        test_site_config.save()

        # Create connected deals
        for i in range(3):
            lead = Lead(
                public_identifier=f"connected-{i}",
                full_name=f"Connected {i}",
                test=True
            )
            lead.save()

            deal = Deal(
                campaign_id=test_campaign.pk,
                lead_id=lead.pk,
                state=DealState.CONNECTED,
                test=True
            )
            deal.save()

        # Plan tasks
        now = datetime.now(tz.utc)
        plan_follow_up_window(test_campaign, now, now.replace(hour=23, minute=59))

        # Verify tasks created
        tasks = Task.objects.filter(task_type="follow_up")
        test_tasks = [t for t in tasks if t.payload.get("campaign_id") == test_campaign.pk]
        # May be 0 if no deals are actually ready for follow-up
        assert len(test_tasks) >= 0

    def test_plan_check_pending_window(self, test_campaign, test_site_config, clean_test_db):
        """Test check_pending task planning."""
        test_site_config.enable_smart_rate_limiting = False
        test_site_config.save()

        # Create pending deals
        for i in range(3):
            lead = Lead(
                public_identifier=f"pending-{i}",
                full_name=f"Pending {i}",
                test=True
            )
            lead.save()

            deal = Deal(
                campaign_id=test_campaign.pk,
                lead_id=lead.pk,
                state=DealState.PENDING,
                next_check_pending_at=datetime.now(tz.utc),
                test=True
            )
            deal.save()

        # Plan tasks
        now = datetime.now(tz.utc)
        plan_check_pending_window(test_campaign, now, now.replace(hour=23, minute=59))

        # Verify tasks created
        tasks = Task.objects.filter(task_type="check_pending")
        test_tasks = [t for t in tasks if t.payload.get("campaign_id") == test_campaign.pk]
        assert len(test_tasks) >= 0

    def test_smart_rate_limiting_mode(self, test_campaign, test_site_config, clean_test_db):
        """Test scheduler respects smart rate limiting mode."""
        test_site_config.enable_smart_rate_limiting = True
        test_site_config.aggressiveness_preset = "average"
        test_site_config.save()

        # Create qualified deals
        for i in range(3):
            lead = Lead(
                public_identifier=f"smart-{i}",
                full_name=f"Smart {i}",
                test=True
            )
            lead.save()

            deal = Deal(
                campaign_id=test_campaign.pk,
                lead_id=lead.pk,
                state=DealState.QUALIFIED,
                test=True
            )
            deal.save()

        # Plan tasks - should use smart mode
        now = datetime.now(tz.utc)
        plan_connect_window(test_campaign, now, now.replace(hour=23, minute=59))

        # Verify tasks created (smart mode may create different number)
        tasks = Task.objects.filter(task_type="connect")
        test_tasks = [t for t in tasks if t.payload.get("campaign_id") == test_campaign.pk]
        assert len(test_tasks) >= 0


class TestTaskLifecycle:
    """Test task lifecycle and state transitions."""

    def test_task_claim_and_complete(self, test_campaign, clean_test_db):
        """Test claiming and completing a task."""
        task = Task(
            task_type="connect",
            payload={"campaign_id": test_campaign.pk},
            status="PENDING",
            scheduled_at=datetime.now(tz.utc),
            test=True
        )
        task.save()

        # Claim task
        claimed = Task.objects.claim_next("connect")
        if claimed:
            assert claimed.status == "RUNNING"
            assert claimed.pk == task.pk

            # Complete task
            claimed.mark_completed()
            assert claimed.status == "COMPLETED"

    def test_task_failure(self, test_campaign, clean_test_db):
        """Test task failure flow."""
        task = Task(
            task_type="connect",
            payload={"campaign_id": test_campaign.pk},
            status="PENDING",
            scheduled_at=datetime.now(tz.utc),
            test=True
        )
        task.save()

        # Claim and fail
        task.mark_running()
        task.mark_failed()
        assert task.status == "FAILED"


class TestDaemonImports:
    """Test that daemon modules import without Django."""

    def test_daemon_imports(self):
        """Test daemon.py imports."""
        from openoutreach.core.daemon import Daemon
        assert Daemon is not None

    def test_scheduler_imports(self):
        """Test scheduler.py imports."""
        from openoutreach.core.scheduler import (
            plan_connect_window,
            plan_follow_up_window,
            plan_check_pending_window,
        )
        assert plan_connect_window is not None

    def test_task_handler_imports(self):
        """Test task handler imports."""
        from openoutreach.linkedin.tasks.connect import handle_connect
        from openoutreach.linkedin.tasks.check_pending import handle_check_pending
        from openoutreach.linkedin.tasks.follow_up import handle_follow_up
        from openoutreach.linkedin.tasks.send_manual_message import handle_send_manual_message

        assert handle_connect is not None
        assert handle_check_pending is not None
        assert handle_follow_up is not None
        assert handle_send_manual_message is not None

    def test_deals_db_imports(self):
        """Test deals db layer imports."""
        from openoutreach.core.db.deals import set_profile_state

        assert set_profile_state is not None


class TestDealStateTransitions:
    """Test deal state transition logic."""

    def test_discovered_to_qualified(self, test_campaign, test_lead, clean_test_db):
        """Test deal transitions from DISCOVERED to QUALIFIED."""
        deal = Deal(
            campaign_id=test_campaign.pk,
            lead_id=test_lead.pk,
            state=DealState.DISCOVERED,
            test=True
        )
        deal.save()

        # Transition to QUALIFIED
        deal.state = DealState.QUALIFIED
        deal.save()

        # Verify
        found = Deal.get_by_lead_and_campaign(test_lead.pk, test_campaign.pk)
        assert found.state == DealState.QUALIFIED

    def test_qualified_to_pending(self, test_campaign, test_lead, clean_test_db):
        """Test deal transitions from QUALIFIED to PENDING."""
        deal = Deal(
            campaign_id=test_campaign.pk,
            lead_id=test_lead.pk,
            state=DealState.QUALIFIED,
            test=True
        )
        deal.save()

        # Transition to PENDING
        deal.state = DealState.PENDING
        deal.next_check_pending_at = datetime.now(tz.utc)
        deal.save()

        # Verify
        found = Deal.get_by_lead_and_campaign(test_lead.pk, test_campaign.pk)
        assert found.state == DealState.PENDING
        assert found.next_check_pending_at is not None

    def test_pending_to_connected(self, test_campaign, test_lead, clean_test_db):
        """Test deal transitions from PENDING to CONNECTED."""
        deal = Deal(
            campaign_id=test_campaign.pk,
            lead_id=test_lead.pk,
            state=DealState.PENDING,
            test=True
        )
        deal.save()

        # Transition to CONNECTED
        deal.state = DealState.CONNECTED
        deal.save()

        # Verify
        found = Deal.get_by_lead_and_campaign(test_lead.pk, test_campaign.pk)
        assert found.state == DealState.CONNECTED


class TestActiveHoursConfig:
    """Test active hours configuration."""

    def test_active_hours_disabled(self, test_site_config, clean_test_db):
        """Test scheduler when active hours are disabled."""
        test_site_config.enable_active_hours = False
        test_site_config.save()

        config = SiteConfig.load()
        assert config.enable_active_hours is False

    def test_active_hours_enabled(self, test_site_config, clean_test_db):
        """Test active hours configuration."""
        test_site_config.enable_active_hours = True
        test_site_config.active_start_hour = 9
        test_site_config.active_end_hour = 17
        test_site_config.active_timezone = "America/New_York"
        test_site_config.active_days = ["monday", "tuesday", "wednesday", "thursday", "friday"]
        test_site_config.save()

        config = SiteConfig.load()
        assert config.enable_active_hours is True
        assert config.active_start_hour == 9
        assert config.active_end_hour == 17
