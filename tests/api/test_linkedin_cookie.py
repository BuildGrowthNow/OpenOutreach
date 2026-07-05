import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from openoutreach.linkedin.models import LinkedInProfile


@pytest.mark.django_db
def test_upload_and_encrypt_cookie(settings):
    # Ensure a deterministic key for test
    settings.SECRET_KEY = "test-secret-key-for-encryption"
    settings.LINKEDIN_VERIFY_COOKIE_ON_UPLOAD = False

    user = User.objects.create_user(username="alice", password="password123")
    profile = LinkedInProfile.objects.create(
        user=user, linkedin_username="alice@example.com", linkedin_password="secret"
    )

    client = APIClient()
    client.force_authenticate(user=user)

    li_at_value = "dummy_li_at_token"
    url = f"/api/linkedin-profiles/{profile.pk}/cookies/"
    response = client.post(url, {"cookie_data": li_at_value}, format="json")

    assert response.status_code == 200, response.content
    data = response.json()
    assert data.get("success") is True

    profile.refresh_from_db()
    cookie_data = profile.cookie_data
    assert cookie_data is not None
    assert isinstance(cookie_data, dict)
    cookies = cookie_data.get("cookies")
    assert cookies and any(
        c.get("name") == "li_at" and c.get("value") == li_at_value for c in cookies
    )

    # Ensure encrypted field exists and is not plaintext
    assert profile.cookie_data_encrypted is not None
    assert "dummy_li_at_token" not in profile.cookie_data_encrypted
