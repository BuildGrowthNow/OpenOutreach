import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from openoutreach.crm.models import LinkedInCredentialLog, LinkedInCredentials
from openoutreach.linkedin.models import LinkedInProfile


def _create_credentials(
    *, profile: LinkedInProfile, email: str, password: str, status: str
):
    credentials = LinkedInCredentials(
        linkedin_profile=profile,
        username=profile.linkedin_username,
        status=status,
        last_verified=timezone.now(),
    )
    credentials.set_email(email)
    credentials.set_password(password)
    credentials.save()
    return credentials


@pytest.mark.django_db
def test_linkedin_credentials_list_is_scoped_to_authenticated_user():
    user = User.objects.create_user(username="alice", password="password123")
    other_user = User.objects.create_user(username="bob", password="password123")

    profile = LinkedInProfile.objects.create(
        user=user,
        linkedin_username="alice@example.com",
        linkedin_password="secret",
    )
    other_profile = LinkedInProfile.objects.create(
        user=other_user,
        linkedin_username="bob@example.com",
        linkedin_password="secret",
    )

    own_credentials = _create_credentials(
        profile=profile,
        email="alice@example.com",
        password="secret",
        status=LinkedInCredentials.STATUS_ACTIVE,
    )
    _create_credentials(
        profile=other_profile,
        email="bob@example.com",
        password="secret",
        status=LinkedInCredentials.STATUS_INVALID,
    )

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get("/api/linkedin-credentials/")

    assert response.status_code == 200, response.content
    payload = response.json()
    assert payload["count"] == 1
    assert [item["id"] for item in payload["credentials"]] == [own_credentials.pk]


@pytest.mark.django_db
def test_linkedin_profile_health_returns_profile_error_details():
    user = User.objects.create_user(username="carol", password="password123")
    profile = LinkedInProfile.objects.create(
        user=user,
        linkedin_username="carol@example.com",
        linkedin_password="secret",
        active=True,
    )
    credentials = _create_credentials(
        profile=profile,
        email="carol@example.com",
        password="secret",
        status=LinkedInCredentials.STATUS_INVALID,
    )
    LinkedInCredentialLog.objects.create(
        credentials=credentials,
        action=LinkedInCredentialLog.ACTION_FAILED,
        details={"reason": "Invalid password"},
    )

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get("/api/linkedin-profile-health/")

    assert response.status_code == 200, response.content
    payload = response.json()
    assert payload["count"] == 1
    assert payload["needs_attention_count"] == 1
    assert payload["profiles"][0]["linkedin_username"] == "carol@example.com"
    assert (
        payload["profiles"][0]["credentials_status"]
        == LinkedInCredentials.STATUS_INVALID
    )
    assert payload["profiles"][0]["last_error"] == "Invalid password"
