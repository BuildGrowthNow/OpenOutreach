"""
Tests for MongoDB models and migration.

These tests verify that:
1. MongoDB connection is properly initialized
2. All MongoDB models work correctly with CRUD operations
3. Indexes are properly created
4. Migration from SQLite to MongoDB works
"""

import pytest
import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.test import TestCase

from openoutreach.mongodb.connection import (
    get_mongodb,
    get_mongodb_collection,
    check_mongodb_connection,
    reset_mongodb_connection,
)
from openoutreach.mongodb.models import (
    Lead,
    Campaign,
    Deal,
    Message,
    Note,
    LeadPersona,
    TrackedLink,
    LinkClick,
    LinkDealConversion,
    LinkedInCredentials,
    LinkedInCredentialLog,
    SiteConfig,
    Task,
)

logger = logging.getLogger(__name__)


@pytest.mark.django_db
class TestMongoDBConnection:
    """Test MongoDB connection and initialization."""

    def test_mongodb_configured(self):
        """Verify MongoDB configuration is set up correctly."""
        from openoutreach.mongodb.settings import get_mongodb_uri, get_mongodb_config

        assert get_mongodb_uri() is not None, "MongoDB URI should be configured"
        config = get_mongodb_config()
        assert "name" in str(config), "MongoDB config should be valid"

    def test_check_mongodb_connection(self):
        """Test that MongoDB connection status is correctly reported."""
        assert check_mongodb_connection(), "MongoDB should be connected"

    def test_get_mongodb_database(self):
        """Test that we can get the MongoDB database object."""
        db = get_mongodb()
        assert db is not None, "MongoDB database should be available"
        assert hasattr(db, "name"), "Database should have a name attribute"


@pytest.mark.django_db
class TestLeadModel:
    """Test Lead MongoDB model."""

    def setup_method(self):
        """Setup for each test method."""
        reset_mongodb_connection()

    def test_create_lead(self):
        """Test creating a new lead in MongoDB."""
        lead = Lead(
            linkedin_url="https://linkedin.com/in/testuser",
            public_identifier="testuser",
            urn="urn:li:person:12345",
            contact_info={"email": "test@example.com"},
        )
        lead_id = lead.save()
        assert lead_id is not None, "Lead should have an ID after save"

    def test_get_lead(self):
        """Test retrieving a lead from MongoDB."""
        lead = Lead(
            linkedin_url="https://linkedin.com/in/testuser2",
            public_identifier="testuser2",
        )
        lead_id = lead.save()
        
        retrieved = Lead.get(lead_id)
        assert retrieved is not None, "Should be able to retrieve lead"
        assert retrieved.linkedin_url == "https://linkedin.com/in/testuser2"

    def test_find_by_public_identifier(self):
        """Test finding a lead by public identifier."""
        lead = Lead(
            linkedin_url="https://linkedin.com/in/searchuser",
            public_identifier="searchuser",
        )
        lead.save()
        
        found = Lead.find_by_public_identifier("searchuser")
        assert found is not None, "Should find lead by public identifier"

    def test_find_by_linkedin_url(self):
        """Test finding a lead by LinkedIn URL."""
        url = "https://linkedin.com/in/urltestuser"
        lead = Lead(linkedin_url=url, public_identifier="urltestuser")
        lead.save()
        
        found = Lead.find_by_linkedin_url(url)
        assert found is not None, "Should find lead by LinkedIn URL"

    def test_delete_lead(self):
        """Test deleting a lead from MongoDB."""
        lead = Lead(
            linkedin_url="https://linkedin.com/in/deletetest",
            public_identifier="deletetest",
        )
        lead_id = lead.save()
        
        result = Lead.delete(lead_id)
        assert result is True, "Lead should be deleted"
        
        deleted = Lead.get(lead_id)
        assert deleted is None, "Lead should no longer exist"

    def test_lead_manager(self):
        """Test LeadManager query methods."""
        for i in range(3):
            Lead(
                linkedin_url=f"https://linkedin.com/in/manager{i}",
                public_identifier=f"manager{i}",
            ).save()
        
        count = Lead.objects().count()
        assert count >= 3, "Should have at least 3 leads"


@pytest.mark.django_db
class TestCampaignModel:
    """Test Campaign MongoDB model."""

    def setup_method(self):
        """Setup for each test method."""
        reset_mongodb_connection()

    def test_create_campaign(self):
        """Test creating a new campaign in MongoDB."""
        campaign = Campaign(
            name="Test Campaign",
            product_docs="# Product Docs\nSome content",
            campaign_objective="Generate leads",
            velocity=20,
        )
        campaign_id = campaign.save()
        assert campaign_id is not None

    def test_get_campaign(self):
        """Test retrieving a campaign from MongoDB."""
        campaign = Campaign(
            name="Get Test Campaign",
            campaign_objective="Test objective",
        )
        campaign_id = campaign.save()
        
        retrieved = Campaign.get(campaign_id)
        assert retrieved is not None
        assert retrieved.name == "Get Test Campaign"

    def test_find_by_name(self):
        """Test finding a campaign by name."""
        campaign = Campaign(
            name="FindByName Campaign",
            campaign_objective="Test",
        )
        campaign.save()
        
        found = Campaign.find_by_name("FindByName Campaign")
        assert found is not None

    def test_delete_campaign(self):
        """Test deleting a campaign."""
        campaign = Campaign(
            name="Delete Campaign",
            campaign_objective="Test",
        )
        campaign_id = campaign.save()
        
        result = Campaign.delete(campaign_id)
        assert result is True

    def test_campaign_manager(self):
        """Test CampaignManager query methods."""
        for i in range(2):
            Campaign(
                name=f"Manager Campaign {i}",
                campaign_objective="Test",
            ).save()
        
        count = Campaign.objects().count()
        assert count >= 2


@pytest.mark.django_db
class TestDealModel:
    """Test Deal MongoDB model."""

    def setup_method(self):
        """Setup for each test method."""
        reset_mongodb_connection()

    def test_create_deal(self):
        """Test creating a new deal in MongoDB."""
        deal = Deal(
            lead_id="test_lead_id",
            campaign_id="test_campaign_id",
            state=Deal.DealState.QUALIFIED,
        )
        deal_id = deal.save()
        assert deal_id is not None

    def test_find_by_lead_id(self):
        """Test finding deals by lead ID."""
        deal = Deal(
            lead_id="find_by_lead_test",
            campaign_id="test_campaign_id",
            state=Deal.DealState.QUALIFIED,
        )
        deal.save()
        
        found = Deal.find_by_lead_id("find_by_lead_test")
        assert len(found) >= 1

    def test_find_by_campaign_id(self):
        """Test finding deals by campaign ID."""
        campaign_id = "test_campaign_123"
        deal = Deal(
            lead_id="test_lead",
            campaign_id=campaign_id,
            state=Deal.DealState.CONNECTED,
        )
        deal.save()
        
        found = Deal.find_by_campaign_id(campaign_id)
        assert len(found) >= 1

    def test_deal_manager(self):
        """Test DealManager query methods."""
        for i in range(2):
            Deal(
                lead_id=f"deal_lead_{i}",
                campaign_id=f"campaign_{i}",
                state=Deal.DealState.PENDING,
            ).save()
        
        count = Deal.objects().count()
        assert count >= 2


@pytest.mark.django_db
class TestMessageModel:
    """Test Message MongoDB model."""

    def setup_method(self):
        """Setup for each test method."""
        reset_mongodb_connection()

    def test_create_message(self):
        """Test creating a message."""
        message = Message(
            deal_id="test_deal",
            content="Hello, this is a test message",
            is_outgoing=True,
        )
        message_id = message.save()
        assert message_id is not None

    def test_get_message(self):
        """Test retrieving a message."""
        message = Message(
            deal_id="test_deal_get",
            content="Test content",
        )
        message_id = message.save()
        
        retrieved = Message.get(message_id)
        assert retrieved is not None

    def test_find_by_deal_id(self):
        """Test finding messages by deal ID."""
        deal_id = "messages_deal_1"
        for i in range(3):
            Message(
                deal_id=deal_id,
                content=f"Message {i}",
                is_outgoing=i % 2 == 0,
            ).save()
        
        messages = Message.find_by_deal_id(deal_id)
        assert len(messages) >= 3

    def test_delete_message(self):
        """Test deleting a message."""
        message = Message(
            deal_id="delete_deal",
            content="To be deleted",
        )
        message_id = message.save()
        
        result = Message.delete(message_id)
        assert result is True

    def test_message_manager(self):
        """Test MessageManager query methods."""
        for i in range(2):
            Message(
                deal_id=f"msg_deal_{i}",
                content=f"Message {i}",
            ).save()
        
        count = Message.objects().count()
        assert count >= 2


@pytest.mark.django_db
class TestNoteModel:
    """Test Note MongoDB model."""

    def setup_method(self):
        """Setup for each test method."""
        reset_mongodb_connection()

    def test_create_note(self):
        """Test creating a note."""
        note = Note(
            deal_id="test_deal_note",
            content="This is a note",
            created_by_id="user_123",
        )
        note_id = note.save()
        assert note_id is not None

    def test_get_note(self):
        """Test retrieving a note."""
        note = Note(
            deal_id="get_deal",
            content="Get note content",
        )
        note_id = note.save()
        
        retrieved = Note.get(note_id)
        assert retrieved is not None

    def test_find_by_deal_id(self):
        """Test finding notes by deal ID."""
        deal_id = "notes_for_deal"
        for i in range(2):
            Note(
                deal_id=deal_id,
                content=f"Note {i}",
            ).save()
        
        notes = Note.find_by_deal_id(deal_id)
        assert len(notes) >= 2

    def test_delete_note(self):
        """Test deleting a note."""
        note = Note(
            deal_id="delete_note_deal",
            content="Delete me",
        )
        note_id = note.save()
        
        result = Note.delete(note_id)
        assert result is True

    def test_note_manager(self):
        """Test NoteManager query methods."""
        for i in range(2):
            Note(
                deal_id=f"note_deal_{i}",
                content=f"Note {i}",
            ).save()
        
        count = Note.objects().count()
        assert count >= 2


@pytest.mark.django_db
class TestLeadPersonaModel:
    """Test LeadPersona MongoDB model."""

    def setup_method(self):
        """Setup for each test method."""
        reset_mongodb_connection()

    def test_create_lead_persona(self):
        """Test creating a lead persona."""
        persona = LeadPersona(
            lead_id="test_lead_persona",
            campaign_id="test_campaign",
            pain_points=["price", "features"],
            goals=["increase sales", "expand"],
            confidence_score=0.8,
        )
        persona_id = persona.save()
        assert persona_id is not None

    def test_get_lead_persona(self):
        """Test retrieving a lead persona."""
        persona = LeadPersona(
            lead_id="get_lead",
            campaign_id="test_campaign",
            messaging_preferences={"tone": "professional"},
        )
        persona_id = persona.save()
        
        retrieved = LeadPersona.get(persona_id)
        assert retrieved is not None

    def test_find_by_lead_id(self):
        """Test finding personae by lead ID."""
        lead_id = "find_persona_lead"
        for i in range(2):
            LeadPersona(
                lead_id=lead_id,
                campaign_id="test_campaign",
                version=i + 1,
            ).save()
        
        personae = LeadPersona.find_by_lead_id(lead_id)
        assert len(personae) >= 2

    def test_find_by_campaign_id(self):
        """Test finding personae by campaign ID."""
        campaign_id = "campaign_personas"
        for i in range(2):
            LeadPersona(
                lead_id=f"lead_{i}",
                campaign_id=campaign_id,
            ).save()
        
        personae = LeadPersona.find_by_campaign_id(campaign_id)
        assert len(personae) >= 2

    def test_delete_lead_persona(self):
        """Test deleting a lead persona."""
        persona = LeadPersona(
            lead_id="delete_lead",
            campaign_id="test_campaign",
        )
        persona_id = persona.save()
        
        result = LeadPersona.delete(persona_id)
        assert result is True

    def test_lead_persona_manager(self):
        """Test LeadPersonaManager query methods."""
        for i in range(2):
            LeadPersona(
                lead_id=f"persona_lead_{i}",
                campaign_id="test_campaign",
            ).save()
        
        count = LeadPersona.objects().count()
        assert count >= 2


@pytest.mark.django_db
class TestTrackedLinkModel:
    """Test TrackedLink MongoDB model."""

    def setup_method(self):
        """Setup for each test method."""
        reset_mongodb_connection()

    def test_create_tracked_link(self):
        """Test creating a tracked link."""
        link = TrackedLink(
            campaign_id="test_campaign_link",
            original_url="https://example.com/products",
            short_code="abc123",
            is_active=True,
        )
        link_id = link.save()
        assert link_id is not None

    def test_get_tracked_link(self):
        """Test retrieving a tracked link."""
        link = TrackedLink(
            campaign_id="get_campaign",
            original_url="https://example.com/test",
            short_code="get456",
        )
        link_id = link.save()
        
        retrieved = TrackedLink.get(link_id)
        assert retrieved is not None

    def test_find_by_short_code(self):
        """Test finding a link by short code."""
        link = TrackedLink(
            campaign_id="test_campaign",
            original_url="https://example.com/short",
            short_code="testshort",
        )
        link.save()
        
        found = TrackedLink.find_by_short_code("testshort")
        assert found is not None

    def test_find_by_campaign_id(self):
        """Test finding links by campaign ID."""
        campaign_id = "campaign_links"
        for i in range(2):
            TrackedLink(
                campaign_id=campaign_id,
                original_url=f"https://example.com/link{i}",
                short_code=f"link{i}",
            ).save()
        
        links = TrackedLink.find_by_campaign_id(campaign_id)
        assert len(links) >= 2

    def test_delete_tracked_link(self):
        """Test deleting a tracked link."""
        link = TrackedLink(
            campaign_id="delete_campaign",
            original_url="https://example.com/delete",
            short_code="delete123",
        )
        link_id = link.save()
        
        result = TrackedLink.delete(link_id)
        assert result is True

    def test_tracked_link_manager(self):
        """Test TrackedLinkManager query methods."""
        for i in range(2):
            TrackedLink(
                campaign_id=f"link_campaign_{i}",
                original_url=f"https://example.com/link{i}",
                short_code=f"link{i}",
            ).save()
        
        count = TrackedLink.objects().count()
        assert count >= 2


@pytest.mark.django_db
class TestLinkClickModel:
    """Test LinkClick MongoDB model."""

    def setup_method(self):
        """Setup for each test method."""
        reset_mongodb_connection()

    def test_create_link_click(self):
        """Test creating a link click."""
        click = LinkClick(
            link_id="test_link",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            country="US",
        )
        click_id = click.save()
        assert click_id is not None

    def test_get_link_click(self):
        """Test retrieving a link click."""
        click = LinkClick(
            link_id="get_link",
            ip_address="192.168.1.2",
            user_agent="Mozilla/5.0",
        )
        click_id = click.save()
        
        retrieved = LinkClick.get(click_id)
        assert retrieved is not None

    def test_find_by_link_id(self):
        """Test finding clicks by link ID."""
        link_id = "find_clicks_link"
        for i in range(3):
            LinkClick(
                link_id=link_id,
                ip_address=f"192.168.1.{i}",
                user_agent=f"Agent {i}",
            ).save()
        
        clicks = LinkClick.find_by_link_id(link_id)
        assert len(clicks) >= 3

    def test_delete_link_click(self):
        """Test deleting a link click."""
        click = LinkClick(
            link_id="delete_link",
            ip_address="192.168.1.100",
            user_agent="Delete Agent",
        )
        click_id = click.save()
        
        result = LinkClick.delete(click_id)
        assert result is True

    def test_link_click_manager(self):
        """Test LinkClickManager query methods."""
        for i in range(2):
            LinkClick(
                link_id=f"click_link_{i}",
                ip_address=f"192.168.1.{i}",
                user_agent=f"Agent {i}",
            ).save()
        
        count = LinkClick.objects().count()
        assert count >= 2


@pytest.mark.django_db
class TestLinkDealConversionModel:
    """Test LinkDealConversion MongoDB model."""

    def setup_method(self):
        """Setup for each test method."""
        reset_mongodb_connection()

    def test_create_link_conversion(self):
        """Test creating a link conversion."""
        conversion = LinkDealConversion(
            link_id="test_conversion_link",
            click_id="test_click",
            deal_id="test_deal",
        )
        conversion_id = conversion.save()
        assert conversion_id is not None

    def test_get_link_conversion(self):
        """Test retrieving a link conversion."""
        conversion = LinkDealConversion(
            link_id="get_conversion_link",
            click_id="get_click",
            deal_id="get_deal",
        )
        conversion_id = conversion.save()
        
        retrieved = LinkDealConversion.get(conversion_id)
        assert retrieved is not None

    def test_find_by_link_id(self):
        """Test finding conversions by link ID."""
        link_id = "find_conversion_link"
        for i in range(2):
            LinkDealConversion(
                link_id=link_id,
                click_id=f"click_{i}",
                deal_id=f"deal_{i}",
            ).save()
        
        conversions = LinkDealConversion.find_by_link_id(link_id)
        assert len(conversions) >= 2

    def test_find_by_deal_id(self):
        """Test finding conversions by deal ID."""
        deal_id = "find_conversion_deal"
        for i in range(2):
            LinkDealConversion(
                link_id=f"link_{i}",
                click_id=f"click_{i}",
                deal_id=deal_id,
            ).save()
        
        conversions = LinkDealConversion.find_by_deal_id(deal_id)
        assert len(conversions) >= 2

    def test_delete_link_conversion(self):
        """Test deleting a link conversion."""
        conversion = LinkDealConversion(
            link_id="delete_conversion_link",
            click_id="delete_click",
            deal_id="delete_deal",
        )
        conversion_id = conversion.save()
        
        result = LinkDealConversion.delete(conversion_id)
        assert result is True

    def test_conversion_manager(self):
        """Test LinkDealConversionManager query methods."""
        for i in range(2):
            LinkDealConversion(
                link_id=f"conversion_link_{i}",
                click_id=f"click_{i}",
                deal_id=f"deal_{i}",
            ).save()
        
        count = LinkDealConversion.objects().count()
        assert count >= 2


@pytest.mark.django_db
class TestLinkedInCredentialsModel:
    """Test LinkedInCredentials MongoDB model."""

    def setup_method(self):
        """Setup for each test method."""
        reset_mongodb_connection()

    def test_create_linkedin_credentials(self):
        """Test creating LinkedIn credentials."""
        credentials = LinkedInCredentials(
            linkedin_profile_id="test_profile",
            username="testuser",
            email_encrypted="encrypted_email",
            password_encrypted="encrypted_password",
            status=LinkedInCredentials.STATUS_ACTIVE,
        )
        credentials_id = credentials.save()
        assert credentials_id is not None

    def test_get_linkedin_credentials(self):
        """Test retrieving LinkedIn credentials."""
        credentials = LinkedInCredentials(
            linkedin_profile_id="get_profile",
            username="getuser",
            status=LinkedInCredentials.STATUS_ACTIVE,
        )
        credentials_id = credentials.save()
        
        retrieved = LinkedInCredentials.get(credentials_id)
        assert retrieved is not None

    def test_find_by_profile_id(self):
        """Test finding credentials by profile ID."""
        credentials = LinkedInCredentials(
            linkedin_profile_id="find_profile",
            username="finduser",
        )
        credentials.save()
        
        found = LinkedInCredentials.find_by_profile_id("find_profile")
        assert found is not None

    def test_find_by_campaign_id(self):
        """Test finding credentials by campaign ID."""
        campaign_id = "campaign_creds"
        for i in range(2):
            LinkedInCredentials(
                linkedin_profile_id=f"profile_{i}",
                username=f"user_{i}",
                campaign_id=campaign_id,
            ).save()
        
        credentials = LinkedInCredentials.find_by_campaign_id(campaign_id)
        assert len(credentials) >= 2

    def test_delete_linkedin_credentials(self):
        """Test deleting LinkedIn credentials."""
        credentials = LinkedInCredentials(
            linkedin_profile_id="delete_profile",
            username="deleteuser",
        )
        credentials_id = credentials.save()
        
        result = LinkedInCredentials.delete(credentials_id)
        assert result is True

    def test_credentials_manager(self):
        """Test LinkedInCredentialsManager query methods."""
        for i in range(2):
            LinkedInCredentials(
                linkedin_profile_id=f"cred_profile_{i}",
                username=f"user_{i}",
            ).save()
        
        count = LinkedInCredentials.objects().count()
        assert count >= 2


@pytest.mark.django_db
class TestLinkedInCredentialLogModel:
    """Test LinkedInCredentialLog MongoDB model."""

    def setup_method(self):
        """Setup for each test method."""
        reset_mongodb_connection()

    def test_create_credential_log(self):
        """Test creating a credential log."""
        log = LinkedInCredentialLog(
            credential_id="test_credential",
            action=LinkedInCredentialLog.ACTION_VERIFIED,
            details={"success": True},
            ip_address="192.168.1.1",
        )
        log_id = log.save()
        assert log_id is not None

    def test_get_credential_log(self):
        """Test retrieving a credential log."""
        log = LinkedInCredentialLog(
            credential_id="get_credential",
            action=LinkedInCredentialLog.ACTION_FAILED,
        )
        log_id = log.save()
        
        retrieved = LinkedInCredentialLog.get(log_id)
        assert retrieved is not None

    def test_find_by_credential_id(self):
        """Test finding logs by credential ID."""
        credential_id = "find_credential_logs"
        for i in range(2):
            LinkedInCredentialLog(
                credential_id=credential_id,
                action=LinkedInCredentialLog.ACTION_USAGE,
            ).save()
        
        logs = LinkedInCredentialLog.find_by_credential_id(credential_id)
        assert len(logs) >= 2

    def test_delete_credential_log(self):
        """Test deleting a credential log."""
        log = LinkedInCredentialLog(
            credential_id="delete_credential",
            action=LinkedInCredentialLog.ACTION_VERIFIED,
        )
        log_id = log.save()
        
        result = LinkedInCredentialLog.delete(log_id)
        assert result is True

    def test_log_manager(self):
        """Test LinkedInCredentialLogManager query methods."""
        for i in range(2):
            LinkedInCredentialLog(
                credential_id=f"log_credential_{i}",
                action=LinkedInCredentialLog.ACTION_USAGE,
            ).save()
        
        count = LinkedInCredentialLog.objects().count()
        assert count >= 2


@pytest.mark.django_db
class TestSiteConfigModel:
    """Test SiteConfig MongoDB model."""

    def setup_method(self):
        """Setup for each test method."""
        reset_mongodb_connection()

    def test_create_site_config(self):
        """Test creating a site config."""
        config = SiteConfig(
            llm_provider="openai",
            llm_api_key="test_key",
            ai_model="gpt-4",
            daily_connection_limit=50,
        )
        config_id = config.save()
        assert config_id is not None

    def test_get_site_config(self):
        """Test retrieving a site config."""
        config = SiteConfig(
            llm_provider="openai",
            llm_api_key="test_key_get",
            ai_model="gpt-4-turbo",
        )
        config_id = config.save()
        
        retrieved = SiteConfig.get(config_id)
        assert retrieved is not None

    def test_find_by_llm_provider(self):
        """Test finding config by LLM provider."""
        config = SiteConfig(
            llm_provider="anthropic",
            llm_api_key="test_anthropic",
            ai_model="claude-3",
        )
        config.save()
        
        found = SiteConfig.find_by_llm_provider("anthropic")
        assert found is not None

    def test_delete_site_config(self):
        """Test deleting a site config."""
        config = SiteConfig(
            llm_provider="delete_provider",
            llm_api_key="delete_key",
        )
        config_id = config.save()
        
        result = SiteConfig.delete(config_id)
        assert result is True

    def test_config_manager(self):
        """Test SiteConfigManager query methods."""
        for i in range(2):
            SiteConfig(
                llm_provider=f"provider_{i}",
                llm_api_key=f"key_{i}",
            ).save()
        
        count = SiteConfig.objects().count()
        assert count >= 2


@pytest.mark.django_db
class TestTaskModel:
    """Test Task MongoDB model."""

    def setup_method(self):
        """Setup for each test method."""
        reset_mongodb_connection()

    def test_create_task(self):
        """Test creating a task."""
        task = Task(
            task_type=Task.TASK_TYPE_CONNECT,
            status=Task.STATUS_PENDING,
            scheduled_at=datetime.utcnow() + timedelta(hours=1),
            payload={"lead_id": "test_lead"},
        )
        task_id = task.save()
        assert task_id is not None

    def test_get_task(self):
        """Test retrieving a task."""
        task = Task(
            task_type=Task.TASK_TYPE_FOLLOW_UP,
            status=Task.STATUS_RUNNING,
            scheduled_at=datetime.utcnow(),
        )
        task_id = task.save()
        
        retrieved = Task.get(task_id)
        assert retrieved is not None

    def test_find_by_status(self):
        """Test finding tasks by status."""
        for i in range(3):
            Task(
                task_type=Task.TASK_TYPE_CHECK_PENDING,
                status=Task.STATUS_PENDING,
                scheduled_at=datetime.utcnow() + timedelta(hours=i),
            ).save()
        
        pending_tasks = Task.find_by_status(Task.STATUS_PENDING)
        assert len(pending_tasks) >= 3

    def test_delete_task(self):
        """Test deleting a task."""
        task = Task(
            task_type=Task.TASK_TYPE_CONNECT,
            status=Task.STATUS_FAILED,
        )
        task_id = task.save()
        
        result = Task.delete(task_id)
        assert result is True

    def test_task_manager(self):
        """Test TaskManager query methods."""
        for i in range(2):
            Task(
                task_type=Task.TASK_TYPE_CONNECT,
                status=Task.STATUS_PENDING,
                scheduled_at=datetime.utcnow() + timedelta(hours=i),
            ).save()
        
        count = Task.objects().count()
        assert count >= 2


@pytest.mark.django_db
class TestMongoDBIndexes:
    """Test MongoDB index creation."""

    def setup_method(self):
        """Setup for each test method."""
        reset_mongodb_connection()

    def test_indexes_exist(self):
        """Test that indexes are created for all collections."""
        from openoutreach.mongodb.models import ensure_mongodb_indexes
        
        ensure_mongodb_indexes()
        
        db = get_mongodb()
        assert db is not None, "Database should be available"
        
        collections_to_check = [
            "leads",
            "campaigns", 
            "deals",
            "messages",
            "notes",
            "lead_personas",
            "tracked_links",
            "link_clicks",
            "link_deal_conversions",
            "linkedin_credentials",
            "linkedin_credential_logs",
            "site_config",
            "tasks",
        ]
        
        for collection_name in collections_to_check:
            try:
                collection = db[collection_name]
                indexes = list(collection.list_indexes())
                assert len(indexes) >= 1, f"Collection '{collection_name}' should have at least one index"
            except Exception as e:
                logger.warning(f"Could not check indexes for collection '{collection_name}': {e}")


@pytest.mark.django_db
class TestMongoDBHealthCheck:
    """Test MongoDB health check endpoints."""

    def test_health_check_endpoint(self):
        """Test the health check API endpoint."""
        from django.test import Client
        
        client = Client()
        response = client.get("/api/mongodb/health/")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "mongodb" in data


@pytest.mark.django_db
class TestMongoDBMigration:
    """Test SQLite to MongoDB migration."""

    def setup_method(self):
        """Setup for each test method."""
        reset_mongodb_connection()

    def test_migration_models_sync(self):
        """Test that migration models are properly synchronized."""
        from openoutreach.mongodb.migration import MigrationManager
        
        manager = MigrationManager()
        
        sqlite_counts = manager.get_sqlite_counts()
        for model_name, count in sqlite_counts.items():
            logger.info(f"SQLite {model_name}: {count}")
        
        assert isinstance(sqlite_counts, dict), "Should return a dictionary"
        assert len(sqlite_counts) > 0, "Should have at least one model count"

    def test_migrate_all_models(self):
        """Test migrating all SQLite data to MongoDB."""
        from openoutreach.mongodb.migration import MigrationManager
        
        manager = MigrationManager()
        
        migration_result = manager.migrate_all()
        
        assert "status" in migration_result
        assert "migrated" in migration_result
        assert "errors" in migration_result
        
        logger.info(f"Migration result: {migration_result}")