"""
Phase 3 Funnel Tests - Deal State Machine & Follow-up

Tests for:
- Discovery creates deals in DISCOVERED state
- promote_lead_to_deal sets QUALIFIED state
- Cross-campaign: existing lead gets new Deal in current campaign
- Follow-up send failure keeps CONNECTED (does not demote)
"""
from unittest.mock import MagicMock, patch

from openoutreach.crm.models.deal import DealState


class TestDealStateMachine:
    """Test deal state transitions during discovery and qualification."""

    def test_promote_lead_sets_qualified_state(self):
        """promote_lead_to_deal should set state to QUALIFIED."""
        from openoutreach.linkedin.db.leads import promote_lead_to_deal
        from openoutreach.mongodb.models import Deal, Lead

        session = MagicMock()
        session.campaign.pk = "campaign-123"

        mock_lead = MagicMock()
        mock_lead.pk = "lead-id-1"

        mock_deal = MagicMock()
        mock_deal.state = DealState.DISCOVERED
        mock_deal.reason = "Discovered via search"

        with patch.object(Lead, "get_by_public_id", return_value=mock_lead), \
             patch.object(Deal, "get_by_lead_and_campaign", return_value=mock_deal):

            promote_lead_to_deal(session, "john-doe", reason="Good ICP fit")

            assert mock_deal.state == DealState.QUALIFIED
            assert mock_deal.reason == "Good ICP fit"
            mock_deal.save.assert_called_once()

    def test_cross_campaign_creates_deal_in_discovered_state(self):
        """Existing lead in another campaign should get a new Deal in DISCOVERED state."""
        from openoutreach.linkedin.db.leads import create_enriched_lead
        from openoutreach.mongodb.models import Deal, Lead

        session = MagicMock()
        session.campaign.pk = "campaign-456"
        session.linkedin_profile.pk = "profile-123"

        existing_lead = MagicMock()
        existing_lead.pk = "lead-existing"

        created_deals = []
        original_init = Deal.__init__

        def capture_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            created_deals.append(self)

        with patch.object(Lead, "get_by_public_id", return_value=existing_lead), \
             patch.object(Deal, "get_by_lead_and_campaign", return_value=None), \
             patch.object(Deal, "__init__", capture_init), \
             patch.object(Deal, "save", return_value="deal-new"):

            profile = {"public_identifier": "existing-user"}
            result = create_enriched_lead(
                session, "https://linkedin.com/in/existing-user", profile
            )

        assert result == "lead-existing"
        assert len(created_deals) == 1
        assert created_deals[0].state == DealState.DISCOVERED
        assert created_deals[0].campaign_id == "campaign-456"
        assert created_deals[0].lead_id == "lead-existing"


class TestFollowUpNoDemotion:
    """Test follow-up send failure does not demote CONNECTED → QUALIFIED."""

    def test_follow_up_send_failure_keeps_connected(self):
        """On send failure, deal should stay CONNECTED (not demoted to QUALIFIED)."""
        from openoutreach.linkedin.tasks.follow_up import handle_follow_up
        from openoutreach.mongodb.models import Lead

        task = MagicMock()
        session = MagicMock()
        campaign = MagicMock()
        campaign._id = "campaign-123"
        session.campaign = campaign
        session.linkedin_profile.pk = "profile-123"

        qualifiers = {}

        mock_deal = MagicMock()
        mock_deal._id = "deal-123"
        mock_deal.lead_id = "lead-123"
        mock_deal.state = DealState.CONNECTED
        mock_deal.campaign_id = "campaign-123"

        mock_lead = MagicMock()
        mock_lead.public_identifier = "target-person"
        mock_lead.urn = "urn:li:member:999"
        mock_lead.cached_profile = None

        mock_decision = MagicMock()
        mock_decision.action = "send_message"
        mock_decision.message = "Hey there!"

        with patch("openoutreach.linkedin.tasks.follow_up.smart_can_execute", return_value=True), \
             patch("openoutreach.linkedin.tasks.follow_up._next_followup_deal", return_value=mock_deal), \
             patch.object(Lead, "get", return_value=mock_lead), \
             patch("openoutreach.linkedin.tasks.follow_up.materialize_profile_summary_if_missing"), \
             patch("openoutreach.linkedin.tasks.follow_up.run_follow_up_agent", return_value=mock_decision), \
             patch("openoutreach.linkedin.tasks.follow_up.send_raw_message", return_value=False), \
             patch("openoutreach.linkedin.tasks.follow_up.set_profile_state") as mock_set_state:

            handle_follow_up(task, session, qualifiers)

            # set_profile_state should NOT be called (no demotion)
            mock_set_state.assert_not_called()
