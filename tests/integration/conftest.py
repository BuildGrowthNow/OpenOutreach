"""Shared fixtures for integration tests."""
import os
import pytest
from datetime import datetime, timezone
from typing import Generator

from openoutreach.mongodb.connection import get_mongodb_collection, check_mongodb_connection
from openoutreach.mongodb.models import Campaign, Task, Deal, Lead, SiteConfig, User
from openoutreach.crm.models import DealState, Outcome


@pytest.fixture(scope="session")
def mongodb_available() -> bool:
    """Check if MongoDB is available for testing."""
    try:
        return check_mongodb_connection()
    except Exception:
        return False


@pytest.fixture(scope="function")
def clean_test_db(mongodb_available):
    """Clean test collections before and after each test."""
    if not mongodb_available:
        pytest.skip("MongoDB not available")

    collections = ["campaigns", "tasks", "deals", "leads", "users", "site_config"]

    # Clean before test
    for collection_name in collections:
        collection = get_mongodb_collection(collection_name)
        collection.delete_many({"test": True})

    yield

    # Clean after test
    for collection_name in collections:
        collection = get_mongodb_collection(collection_name)
        collection.delete_many({"test": True})


@pytest.fixture
def test_user(clean_test_db) -> User:
    """Create a test user."""
    user = User(
        email="test@example.com",
        password_hash="$2b$12$dummyhash",  # Not a real hash, just for testing
        is_active=True,
        test=True
    )
    user.save()
    return user


@pytest.fixture
def test_campaign(test_user, clean_test_db) -> Campaign:
    """Create a test campaign."""
    campaign = Campaign(
        name="Test Campaign",
        user_id=test_user.pk,
        status="active",
        test=True
    )
    campaign.save()
    return campaign


@pytest.fixture
def test_lead(clean_test_db) -> Lead:
    """Create a test lead."""
    lead = Lead(
        public_identifier="test-lead",
        full_name="Test Lead",
        headline="Test Headline",
        test=True
    )
    lead.save()
    return lead


@pytest.fixture
def test_deal(test_campaign, test_lead, clean_test_db) -> Deal:
    """Create a test deal."""
    deal = Deal(
        campaign_id=test_campaign.pk,
        lead_id=test_lead.pk,
        state=DealState.QUALIFIED,
        test=True
    )
    deal.save()
    return deal


@pytest.fixture
def test_site_config(clean_test_db) -> SiteConfig:
    """Create test site config."""
    config = SiteConfig(
        enable_active_hours=False,
        velocity=10,
        enable_smart_rate_limiting=False,
        test=True
    )
    config.save()
    return config
