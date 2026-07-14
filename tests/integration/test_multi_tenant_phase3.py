"""
Phase 3 Integration Tests - Multi-Tenant Data Isolation

Tests to verify that users can only access their own data and that
team members have appropriate access to shared campaigns.

NOTE: Run with MONGODB_URI environment variable set:
    MONGODB_URI=mongodb://localhost:27017/ pytest tests/integration/test_multi_tenant_phase3.py -v
"""
import pytest
import os

# Skip Django setup - these are FastAPI-only tests
os.environ["SKIP_DJANGO_SETUP"] = "1"

from fastapi.testclient import TestClient
from openoutreach.api_v2.main import app
from openoutreach.mongodb.connection import get_mongodb_collection, mongodb_connection
from openoutreach.mongodb import models

client = TestClient(app)


@pytest.fixture(scope="function", autouse=True)
def clean_database():
    """Clean database before each test."""
    mongodb_connection.ensure_indexes_and_connections()

    collections = [
        "users",
        "linkedin_profiles",
        "campaigns",
        "deals",
        "leads",
        "chat_messages",
        "notifications",
        "tasks",
    ]

    for collection_name in collections:
        collection = get_mongodb_collection(collection_name)
        if collection:
            collection.delete_many({})

    yield

    # Cleanup after test
    for collection_name in collections:
        collection = get_mongodb_collection(collection_name)
        if collection:
            collection.delete_many({})


@pytest.fixture
def user1_token():
    """Register and login user1."""
    # Register
    response = client.post(
        "/api/auth/register/",
        json={
            "email": "user1@test.com",
            "password": "TestPass123!",
            "full_name": "User One"
        }
    )
    assert response.status_code == 201

    # Login
    response = client.post(
        "/api/auth/login/",
        json={
            "email": "user1@test.com",
            "password": "TestPass123!"
        }
    )
    assert response.status_code == 200
    data = response.json()
    return data["access_token"]


@pytest.fixture
def user2_token():
    """Register and login user2."""
    # Register
    response = client.post(
        "/api/auth/register/",
        json={
            "email": "user2@test.com",
            "password": "TestPass123!",
            "full_name": "User Two"
        }
    )
    assert response.status_code == 201

    # Login
    response = client.post(
        "/api/auth/login/",
        json={
            "email": "user2@test.com",
            "password": "TestPass123!"
        }
    )
    assert response.status_code == 200
    data = response.json()
    return data["access_token"]


@pytest.fixture
def user1_profile(user1_token):
    """Create LinkedIn profile for user1."""
    response = client.post(
        "/api/linkedin-profiles",
        json={
            "linkedin_username": "user1.linkedin",
            "connect_daily_limit": 20,
            "follow_up_daily_limit": 25
        },
        headers={"Authorization": f"Bearer {user1_token}"}
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def user2_profile(user2_token):
    """Create LinkedIn profile for user2."""
    response = client.post(
        "/api/linkedin-profiles",
        json={
            "linkedin_username": "user2.linkedin",
            "connect_daily_limit": 20,
            "follow_up_daily_limit": 25
        },
        headers={"Authorization": f"Bearer {user2_token}"}
    )
    assert response.status_code == 201
    return response.json()


# ===== PROFILE ISOLATION TESTS =====

def test_user_can_list_own_profiles(user1_token, user1_profile):
    """Test that user can list their own profiles."""
    response = client.get(
        "/api/linkedin-profiles",
        headers={"Authorization": f"Bearer {user1_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["profiles"]) == 1
    assert data["profiles"][0]["linkedin_username"] == "user1.linkedin"


def test_user_cannot_see_other_user_profiles(user1_token, user1_profile, user2_profile):
    """Test that users cannot see each other's profiles."""
    response = client.get(
        "/api/linkedin-profiles",
        headers={"Authorization": f"Bearer {user1_token}"}
    )
    assert response.status_code == 200
    data = response.json()

    # User 1 should only see their own profile
    assert len(data["profiles"]) == 1
    assert data["profiles"][0]["linkedin_username"] == "user1.linkedin"


def test_user_cannot_access_other_user_profile_detail(user1_token, user2_token, user2_profile):
    """Test that user cannot access another user's profile details."""
    profile_id = user2_profile["id"]

    response = client.get(
        f"/api/linkedin-profiles/{profile_id}",
        headers={"Authorization": f"Bearer {user1_token}"}
    )
    assert response.status_code == 403


def test_user_cannot_delete_other_user_profile(user1_token, user2_token, user2_profile):
    """Test that user cannot delete another user's profile."""
    profile_id = user2_profile["id"]

    response = client.delete(
        f"/api/linkedin-profiles/{profile_id}",
        headers={"Authorization": f"Bearer {user1_token}"}
    )
    assert response.status_code == 403


# ===== CAMPAIGN ISOLATION TESTS =====

def test_user_can_create_campaign_with_own_profile(user1_token, user1_profile):
    """Test that user can create campaign with their own profile."""
    response = client.post(
        "/api/campaigns",
        json={
            "name": "Test Campaign",
            "product_pitch": "Test pitch",
            "campaign_objective": "Test objective",
            "linkedin_profile_id": user1_profile["id"],
            "velocity": 20
        },
        headers={"Authorization": f"Bearer {user1_token}"}
    )
    assert response.status_code == 201


def test_user_cannot_create_campaign_with_other_user_profile(user1_token, user2_profile):
    """Test that user cannot create campaign with another user's profile."""
    response = client.post(
        "/api/campaigns",
        json={
            "name": "Test Campaign",
            "product_pitch": "Test pitch",
            "campaign_objective": "Test objective",
            "linkedin_profile_id": user2_profile["id"],
            "velocity": 20
        },
        headers={"Authorization": f"Bearer {user1_token}"}
    )
    assert response.status_code == 403


def test_user_cannot_see_other_user_campaigns(user1_token, user2_token, user1_profile, user2_profile):
    """Test that users cannot see each other's campaigns."""
    # User1 creates a campaign
    response = client.post(
        "/api/campaigns",
        json={
            "name": "User1 Campaign",
            "product_pitch": "Test pitch",
            "campaign_objective": "Test objective",
            "linkedin_profile_id": user1_profile["id"],
            "velocity": 20
        },
        headers={"Authorization": f"Bearer {user1_token}"}
    )
    assert response.status_code == 201

    # User2 should not see it
    response = client.get(
        "/api/campaigns",
        headers={"Authorization": f"Bearer {user2_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert all(c["name"] != "User1 Campaign" for c in data.get("campaigns", []))


def test_user_cannot_access_other_user_campaign_detail(user1_token, user2_token, user1_profile):
    """Test that user cannot access another user's campaign details."""
    # User1 creates campaign
    response = client.post(
        "/api/campaigns",
        json={
            "name": "User1 Campaign",
            "product_pitch": "Test pitch",
            "campaign_objective": "Test objective",
            "linkedin_profile_id": user1_profile["id"],
            "velocity": 20
        },
        headers={"Authorization": f"Bearer {user1_token}"}
    )
    campaign_id = response.json()["id"]

    # User2 cannot access it
    response = client.get(
        f"/api/campaigns/{campaign_id}",
        headers={"Authorization": f"Bearer {user2_token}"}
    )
    assert response.status_code == 403


# ===== TEAM ACCESS TESTS =====

def test_team_member_can_access_shared_campaign(user1_token, user2_token, user1_profile):
    """Test that team members can access campaigns shared with them."""
    # Get user2's ID
    response = client.get(
        "/api/auth/me/",
        headers={"Authorization": f"Bearer {user2_token}"}
    )
    user2_id = response.json()["id"]

    # User1 creates campaign with user2 as team member
    response = client.post(
        "/api/campaigns",
        json={
            "name": "Shared Campaign",
            "product_pitch": "Test pitch",
            "campaign_objective": "Test objective",
            "linkedin_profile_id": user1_profile["id"],
            "team_member_ids": [user2_id],
            "velocity": 20
        },
        headers={"Authorization": f"Bearer {user1_token}"}
    )
    assert response.status_code == 201
    campaign_id = response.json()["id"]

    # User2 CAN access it
    response = client.get(
        f"/api/campaigns/{campaign_id}",
        headers={"Authorization": f"Bearer {user2_token}"}
    )
    assert response.status_code == 200


def test_only_owner_can_delete_campaign(user1_token, user2_token, user1_profile):
    """Test that only campaign owner can delete it."""
    # Get user2's ID
    response = client.get(
        "/api/auth/me/",
        headers={"Authorization": f"Bearer {user2_token}"}
    )
    user2_id = response.json()["id"]

    # User1 creates campaign with user2 as team member
    response = client.post(
        "/api/campaigns",
        json={
            "name": "Shared Campaign",
            "product_pitch": "Test pitch",
            "campaign_objective": "Test objective",
            "linkedin_profile_id": user1_profile["id"],
            "team_member_ids": [user2_id],
            "velocity": 20
        },
        headers={"Authorization": f"Bearer {user1_token}"}
    )
    campaign_id = response.json()["id"]

    # User2 (team member) CANNOT delete it
    response = client.delete(
        f"/api/campaigns/{campaign_id}",
        headers={"Authorization": f"Bearer {user2_token}"}
    )
    assert response.status_code == 403


# ===== NOTIFICATION ISOLATION TESTS =====

def test_notifications_are_isolated(user1_token, user2_token):
    """Test that users only see their own notifications."""
    # Get user1's notifications
    response = client.get(
        "/api/notifications/",
        headers={"Authorization": f"Bearer {user1_token}"}
    )
    user1_notifs = response.json()

    # Get user2's notifications
    response = client.get(
        "/api/notifications/",
        headers={"Authorization": f"Bearer {user2_token}"}
    )
    user2_notifs = response.json()

    # No overlap in notification IDs
    user1_ids = {n["_id"] for n in user1_notifs.get("notifications", [])}
    user2_ids = {n["_id"] for n in user2_notifs.get("notifications", [])}
    assert user1_ids.isdisjoint(user2_ids)


# ===== LEADS/MESSAGES ISOLATION TESTS =====

def test_leads_accessible_via_campaign(user1_token, user2_token, user1_profile):
    """Test that leads are only accessible via campaigns user has access to."""
    # User1 creates a campaign
    response = client.post(
        "/api/campaigns",
        json={
            "name": "User1 Campaign",
            "product_pitch": "Test pitch",
            "campaign_objective": "Test objective",
            "linkedin_profile_id": user1_profile["id"],
            "velocity": 20
        },
        headers={"Authorization": f"Bearer {user1_token}"}
    )
    campaign_id = response.json()["id"]

    # User1 can access leads for their campaign
    response = client.get(
        f"/api/leads?campaign_id={campaign_id}",
        headers={"Authorization": f"Bearer {user1_token}"}
    )
    assert response.status_code == 200

    # User2 CANNOT access leads for user1's campaign
    response = client.get(
        f"/api/leads?campaign_id={campaign_id}",
        headers={"Authorization": f"Bearer {user2_token}"}
    )
    assert response.status_code == 403


def test_messages_accessible_via_campaign(user1_token, user2_token, user1_profile):
    """Test that messages are only accessible via campaigns user has access to."""
    # User1 creates a campaign
    response = client.post(
        "/api/campaigns",
        json={
            "name": "User1 Campaign",
            "product_pitch": "Test pitch",
            "campaign_objective": "Test objective",
            "linkedin_profile_id": user1_profile["id"],
            "velocity": 20
        },
        headers={"Authorization": f"Bearer {user1_token}"}
    )
    campaign_id = response.json()["id"]

    # User1 can access messages for their campaign
    response = client.get(
        f"/api/messages?campaign_id={campaign_id}",
        headers={"Authorization": f"Bearer {user1_token}"}
    )
    assert response.status_code == 200

    # User2 CANNOT access messages for user1's campaign
    response = client.get(
        f"/api/messages?campaign_id={campaign_id}",
        headers={"Authorization": f"Bearer {user2_token}"}
    )
    assert response.status_code == 403
