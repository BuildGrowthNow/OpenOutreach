import os
from unittest.mock import patch
from asgiref.sync import sync_to_async

# Setup Django before other imports
import django
import numpy as np
import pytest

# Set Django settings module before Django setup
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "openoutreach.settings.development")
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

# Initialize Django
django.setup()

from openoutreach.core.management.setup_crm import setup_crm
from tests.factories import UserFactory


@pytest.fixture(scope="session", autouse=True)
def _setup_mongodb_connection():
    """Initialize MongoDB connection once per test session.
    
    This ensures the MongoDB connection is available for all tests
    and persists across test classes.
    
    Note: We don't call reset_mongodb_connection() here because that would
    close the connection. The test_mongodb_models.py file handles resetting
    between tests as needed.
    """
    try:
        from openoutreach.mongodb.connection import (
            initialize_mongodb_connection,
            get_mongodb,
            _is_mongodb_enabled,
        )
        
        if _is_mongodb_enabled():
            # Check if already initialized
            db = get_mongodb()
            if db is None:
                # Only initialize if no connection exists
                if initialize_mongodb_connection():
                    print("MongoDB connection initialized successfully for test session")
                else:
                    print("Warning: MongoDB initialization returned False")
            else:
                print("MongoDB connection already exists")
        else:
            print("MongoDB is disabled - skipping connection")
    except Exception as e:
        print(f"Warning: Failed to initialize MongoDB connection: {e}")


@pytest.fixture(autouse=True)
def _mock_embeddings(request):
    """Stub fastembed so tests don't need the ONNX model."""
    if "no_embed_mock" in request.keywords:
        yield
    else:
        with patch("openoutreach.linkedin.ml.embeddings.embed_text", return_value=np.ones(384)):
            yield


@pytest.fixture(autouse=True)
def _mock_contact_capture(request):
    """Stub the LinkedIn contact-info scrape so CONNECTED transitions don't hit a
    live browser. Opt out with the `no_contact_capture_mock` marker — the dedicated
    capture tests mock the lower linkedin_cli boundary to exercise the real method."""
    if "no_contact_capture_mock" in request.keywords:
        yield
    else:
        with patch("openoutreach.crm.models.lead.Lead.capture_contact_info", return_value=None):
            yield


@pytest.fixture(scope="session", autouse=True)
def _django_db_setup(django_db_setup, django_db_blocker):
    """Ensure the Django database is properly set up with CRM data for all tests.
    
    This fixture runs once per session and ensures migrations are applied
    and CRM data is set up before any tests run.
    """
    with django_db_blocker.unblock():
        setup_crm()


@pytest.fixture
def db(request, django_db_setup, django_db_blocker):
    """Provide a database fixture for tests that need it.
    
    This fixture ensures CRM data is set up before tests that need database access.
    """
    if "mongodb" not in str(request.path):
        with django_db_blocker.unblock():
            setup_crm()


@pytest.fixture
def deal_with_lead(db, fake_session):
    """Create a deal for use in summary tests."""
    from openoutreach.core.models import Campaign
    from openoutreach.crm.models import Lead, Deal
    from datetime import datetime
    
    campaign = Campaign.objects.first()
    if not campaign:
        campaign = Campaign.objects.create(name="Test Campaign")
    
    lead = Lead.objects.create(
        linkedin_url="https://www.linkedin.com/in/testuser/",
        public_identifier="testuser",
    )
    
    deal = Deal.objects.create(
        lead=lead,
        campaign=campaign,
    )
    
    return deal


class FakeAccountSession:
    """Minimal stand-in for AccountSession — exposes django_user + campaign."""

    class MockContext:
        """Mock context object for linkedin_cli.api.client compatibility."""
        def cookies(self):
            return {}

    def __init__(self, django_user, linkedin_profile, campaign):
        self.django_user = django_user
        self.linkedin_profile = linkedin_profile
        self.campaign = campaign
        self.self_profile = {
            "first_name": "Diego",
            "last_name": "Ramirez",
            "urn": "urn:li:fsd_profile:TEST",
        }
        self.page = None  # For compatibility with linkedin_cli.api.client
        self.context = self.MockContext()  # For compatibility with linkedin_cli.api.client

    @property
    def campaigns(self):
        from openoutreach.core.models import Campaign
        return Campaign.objects.filter(users=self.django_user)

    def ensure_browser(self):
        pass


@pytest.fixture
def fake_session(db):
    """An AccountSession-like object backed by the Django test DB."""
    from openoutreach.core.models import Campaign
    from openoutreach.linkedin.models import LinkedInProfile

    user = UserFactory(username="testuser")

    campaign = Campaign.objects.first()
    if campaign is None:
        campaign = Campaign.objects.create(name="LinkedIn Outreach")
    campaign.users.add(user)

    linkedin_profile, _ = LinkedInProfile.objects.get_or_create(
        user=user,
        defaults={
            "linkedin_username": "testuser@example.com",
            "linkedin_password": "testpass",
        },
    )

    return FakeAccountSession(django_user=user, linkedin_profile=linkedin_profile, campaign=campaign)