"""Smoke tests for daemon - verify it can start without errors."""
import pytest
from unittest.mock import Mock, patch


class TestDaemonSmoke:
    """Smoke tests for daemon startup and basic functionality."""

    def test_run_daemon_imports(self):
        """Test run_daemon function can be imported."""
        from openoutreach.core.daemon import run_daemon
        assert run_daemon is not None
        assert callable(run_daemon)

    def test_task_handlers_import(self):
        """Test all task handlers can be imported."""
        from openoutreach.linkedin.tasks.connect import handle_connect
        from openoutreach.linkedin.tasks.check_pending import handle_check_pending
        from openoutreach.linkedin.tasks.follow_up import handle_follow_up
        from openoutreach.linkedin.tasks.send_manual_message import handle_send_manual_message

        handlers = [
            handle_connect,
            handle_check_pending,
            handle_follow_up,
            handle_send_manual_message,
        ]

        for handler in handlers:
            assert handler is not None
            assert callable(handler)

    def test_scheduler_functions_import(self):
        """Test scheduler functions can be imported."""
        from openoutreach.core.scheduler import (
            plan_connect_window,
            plan_follow_up_window,
            plan_check_pending_window,
        )

        planners = [
            plan_connect_window,
            plan_follow_up_window,
            plan_check_pending_window,
        ]

        for planner in planners:
            assert planner is not None
            assert callable(planner)

    def test_no_django_imports_in_daemon(self):
        """Verify daemon has no Django imports."""
        import inspect
        from openoutreach.core import daemon

        source = inspect.getsource(daemon)
        assert "from django" not in source
        assert "import django" not in source

    def test_no_django_imports_in_scheduler(self):
        """Verify scheduler has no Django imports."""
        import inspect
        from openoutreach.core import scheduler

        source = inspect.getsource(scheduler)
        assert "from django" not in source
        assert "import django" not in source

    def test_no_django_imports_in_task_handlers(self):
        """Verify task handlers have no Django imports."""
        import inspect
        from openoutreach.linkedin.tasks import connect, check_pending, follow_up, send_manual_message

        modules = [connect, check_pending, follow_up, send_manual_message]

        for module in modules:
            source = inspect.getsource(module)
            assert "from django" not in source
            assert "import django" not in source


class TestSiteConfigLoad:
    """Test SiteConfig loading for daemon."""

    def test_site_config_load(self, clean_test_db):
        """Test SiteConfig.load() works."""
        from openoutreach.mongodb.models import SiteConfig

        config = SiteConfig.load()
        assert config is not None
        assert hasattr(config, "velocity")
        assert hasattr(config, "enable_smart_rate_limiting")
        assert hasattr(config, "enable_active_hours")

    def test_site_config_fields(self, clean_test_db):
        """Test SiteConfig has all required fields."""
        from openoutreach.mongodb.models import SiteConfig

        config = SiteConfig.load()

        # Active hours fields
        assert hasattr(config, "enable_active_hours")
        assert hasattr(config, "active_start_hour")
        assert hasattr(config, "active_end_hour")
        assert hasattr(config, "active_timezone")
        assert hasattr(config, "active_days")

        # Rate limiting fields
        assert hasattr(config, "enable_smart_rate_limiting")
        assert hasattr(config, "velocity")

        # Smart rate limiting fields
        if hasattr(config, "aggressiveness_preset"):
            assert config.aggressiveness_preset in [
                "very_slow", "slow", "average", "aggressive", "very_aggressive"
            ] or config.aggressiveness_preset is None


class TestCampaignAccess:
    """Test campaign access for daemon."""

    def test_campaign_all(self, test_campaign, clean_test_db):
        """Test Campaign.objects.all() works."""
        from openoutreach.mongodb.models import Campaign

        campaigns = Campaign.objects.all()
        assert isinstance(campaigns, list)
        assert any(c.pk == test_campaign.pk for c in campaigns)

    def test_campaign_filter(self, test_campaign, clean_test_db):
        """Test Campaign.objects.filter() works."""
        from openoutreach.mongodb.models import Campaign

        campaigns = Campaign.objects.filter(status="active")
        assert isinstance(campaigns, list)


class TestTaskClaiming:
    """Test task claiming for daemon."""

    def test_task_claim_next(self, test_campaign, clean_test_db):
        """Test Task.objects.claim_next() works."""
        from openoutreach.mongodb.models import Task
        from datetime import datetime, timezone as tz

        # Create a pending task
        task = Task(
            task_type="connect",
            payload={"campaign_id": test_campaign.pk},
            status="PENDING",
            scheduled_at=datetime.now(tz.utc),
            test=True
        )
        task.save()

        # Try to claim
        claimed = Task.objects.claim_next("connect")
        if claimed:
            assert claimed.status == "RUNNING"
            assert claimed.task_type == "connect"

    def test_task_pending_query(self, test_campaign, clean_test_db):
        """Test Task.objects.pending() works."""
        from openoutreach.mongodb.models import Task
        from datetime import datetime, timezone as tz

        # Create pending tasks
        task = Task(
            task_type="follow_up",
            payload={"campaign_id": test_campaign.pk},
            status="PENDING",
            scheduled_at=datetime.now(tz.utc),
            test=True
        )
        task.save()

        # Query pending
        pending = Task.objects.pending()
        assert isinstance(pending, list)


class TestDealQueries:
    """Test deal queries for daemon."""

    def test_deal_by_state(self, test_campaign, test_lead, clean_test_db):
        """Test querying deals by state."""
        from openoutreach.mongodb.models import Deal
        from openoutreach.crm.models import DealState

        deal = Deal(
            campaign_id=test_campaign.pk,
            lead_id=test_lead.pk,
            state=DealState.QUALIFIED,
            test=True
        )
        deal.save()

        # Query by state
        deals = Deal.objects.filter(state=DealState.QUALIFIED.value)
        assert isinstance(deals, list)
        assert any(d.pk == deal.pk for d in deals)

    def test_deal_get_by_lead_and_campaign(self, test_campaign, test_lead, clean_test_db):
        """Test Deal.get_by_lead_and_campaign() method."""
        from openoutreach.mongodb.models import Deal
        from openoutreach.crm.models import DealState

        deal = Deal(
            campaign_id=test_campaign.pk,
            lead_id=test_lead.pk,
            state=DealState.QUALIFIED,
            test=True
        )
        deal.save()

        # Get by lead and campaign
        found = Deal.get_by_lead_and_campaign(test_lead.pk, test_campaign.pk)
        assert found is not None
        assert found.pk == deal.pk


class TestActionLog:
    """Test ActionLog for daemon."""

    def test_action_log_creation(self, test_campaign, test_lead, clean_test_db):
        """Test ActionLog can be created."""
        from openoutreach.linkedin.models import ActionLog

        log = ActionLog(
            campaign_id=test_campaign.pk,
            lead_id=test_lead.pk,
            action_type=ActionLog.ActionType.CONNECTION_SENT,
            test=True
        )
        log.save()

        assert log.pk is not None

    def test_action_log_query(self, test_campaign, test_lead, clean_test_db):
        """Test ActionLog can be queried."""
        from openoutreach.linkedin.models import ActionLog

        log = ActionLog(
            campaign_id=test_campaign.pk,
            lead_id=test_lead.pk,
            action_type=ActionLog.ActionType.CONNECTION_SENT,
            test=True
        )
        log.save()

        # Query by campaign
        logs = ActionLog.objects.filter(campaign_id=test_campaign.pk)
        assert isinstance(logs, list)
        assert any(l.pk == log.pk for l in logs)
