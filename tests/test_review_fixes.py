"""Regression tests for review findings on the Phase 2/3 rollout branch.

These cover the security and billing issues found during the pre-merge review:
proxy credential reuse, campaign tenant isolation, encryption heuristics,
invite HTML escaping, cancellation cleanup, and the Cloud add-on plan guard.
"""
from __future__ import annotations

import asyncio
import random
import string
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException

from openoutreach.api_v2.routers import billing as billing_router
from openoutreach.api_v2.routers import linkedin_profiles as profiles_router
from openoutreach.billing import emails as billing_emails
from openoutreach.billing import webhooks
from openoutreach.linkedin.models import LinkedInProfile
from openoutreach.mongodb.crypto import encrypt_text, is_encrypted, safe_decrypt
from openoutreach.mongodb.models_user import User
from openoutreach.proxies.region import normalize_region


@pytest.fixture(autouse=True)
def encryption_key(monkeypatch):
    monkeypatch.setenv("COOKIE_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.delenv("SECRET_KEY", raising=False)


def test_is_encrypted_does_not_misclassify_random_passwords():
    rng = random.Random(42)
    alphabet = string.ascii_letters + string.digits + "-_"
    for _ in range(1000):
        token = "".join(rng.choice(alphabet) for _ in range(48))
        assert is_encrypted(token) is False

    encrypted = encrypt_text("super-secret")
    assert is_encrypted(encrypted) is True
    assert safe_decrypt(encrypted) == "super-secret"


def test_org_invite_email_escapes_workspace_and_inviter_names(monkeypatch):
    captured: dict[str, str] = {}

    def fake_send(user, subject, html, text):
        captured["subject"] = subject
        captured["html"] = html
        captured["text"] = text
        return True

    monkeypatch.setattr(billing_emails, "_send_billing_email", fake_send)

    billing_emails.send_organization_invite(
        "invitee@example.com",
        '<img src=x onerror="alert(1)">',
        "<b>Mallory</b>",
        "member",
        "https://example.com/team/accept?token=abc",
    )

    assert "<img" not in captured["html"]
    assert "&lt;img" in captured["html"]
    assert "<b>Mallory</b>" not in captured["html"]
    assert "&lt;b&gt;Mallory&lt;/b&gt;" in captured["html"]
    assert "\n" not in captured["subject"]


def test_proxy_host_change_clears_previous_credentials():
    collection = MagicMock()
    collection.find_one.side_effect = [
        {
            "_id": "profile-1",
            "user_id": "u1",
            "proxy_mode": "byo",
            "proxy_server": "http://8.8.8.8:8080",
            "proxy_username": "old-user",
            "proxy_password_encrypted": "old-encrypted",
        },
        {
            "_id": "profile-1",
            "user_id": "u1",
            "proxy_mode": "byo",
            "proxy_server": "http://1.1.1.1:8080",
            "proxy_username": None,
            "proxy_password_encrypted": None,
        },
    ]

    with (
        patch.object(profiles_router, "get_mongodb_collection", return_value=collection),
        patch.object(profiles_router, "profile_access_query", return_value={"user_id": "u1"}),
        patch.object(
            profiles_router,
            "resolve_org_context",
            return_value=SimpleNamespace(role="owner"),
        ),
        patch.object(profiles_router.User, "get", return_value=SimpleNamespace(_id="u1")),
    ):
        asyncio.run(
            profiles_router.update_proxy_config(
                "profile-1",
                proxy_server="http://1.1.1.1:8080",
                proxy_username=None,
                proxy_password=None,
                user_id="u1",
            )
        )

    updates = collection.update_one.call_args.args[1]["$set"]
    assert updates["proxy_password_encrypted"] is None
    assert updates["proxy_username"] is None


def test_proxy_test_does_not_reuse_stored_password_for_a_new_host():
    collection = MagicMock()
    collection.find_one.return_value = {
        "_id": "profile-1",
        "user_id": "u1",
        "proxy_server": "http://8.8.8.8:8080",
        "proxy_username": "old-user",
        "proxy_password_encrypted": encrypt_text("old-secret"),
    }

    with (
        patch.object(profiles_router, "get_mongodb_collection", return_value=collection),
        patch.object(profiles_router, "profile_access_query", return_value={"user_id": "u1"}),
        patch.object(
            profiles_router,
            "resolve_org_context",
            return_value=SimpleNamespace(role="owner"),
        ),
        patch.object(profiles_router.User, "get", return_value=SimpleNamespace(_id="u1")),
        patch(
            "openoutreach.proxies.service.check_proxy_connection",
            new_callable=AsyncMock,
        ) as check,
    ):
        check.return_value = {"success": True}
        asyncio.run(
            profiles_router.test_proxy(
                "profile-1",
                proxy_server="http://1.1.1.1:8080",
                proxy_username=None,
                proxy_password=None,
                user_id="u1",
            )
        )

    check.assert_awaited_once()
    assert check.await_args.args[0] == "http://1.1.1.1:8080"
    assert check.await_args.args[2] is None


def test_proxy_url_rejects_embedded_userinfo():
    with pytest.raises(HTTPException) as error:
        profiles_router._normalize_proxy_server("http://user:secret@8.8.8.8:8080")
    assert error.value.status_code == 400


def test_region_rejects_subdivision_parameter_injection():
    with pytest.raises(ValueError):
        normalize_region("US", "NY-session-x")


def test_refresh_from_db_tolerates_missing_password_field():
    profile = LinkedInProfile(_id="profile-1", user_id="u1")
    collection = MagicMock()
    collection.find_one.return_value = {"_id": "profile-1", "user_id": "u1"}

    with patch(
        "openoutreach.linkedin.models.get_mongodb_collection",
        return_value=collection,
    ):
        profile.refresh_from_db(fields=["proxy_password_encrypted"])

    assert profile._proxy_password_encrypted is None


def test_cloud_plan_change_requires_removing_addon_seats():
    user = User(
        _id="u1",
        email="user@example.com",
        plan="cloud",
        cloud_profiles=2,
        stripe_subscription_id="sub-1",
    )

    with (
        patch.object(billing_router.User, "get", return_value=user),
        patch.object(billing_router, "_require_billing_owner"),
    ):
        with pytest.raises(HTTPException) as error:
            asyncio.run(
                billing_router.change_plan(
                    billing_router.PlanChangeRequest(
                        plan_name="business", billing_period="monthly"
                    ),
                    user_id="u1",
                )
            )

    assert error.value.status_code == 400
    assert "Remove all cloud seats" in error.value.detail


def test_cancellation_deactivates_and_disables_owned_profiles_only():
    collection = MagicMock()
    collection.find.return_value = [{"_id": "p1"}]

    with (
        patch.object(webhooks, "get_mongodb_collection", return_value=collection),
        patch("openoutreach.billing.seats.org_ids_owned_by", return_value=["org-1"]),
        patch(
            "openoutreach.organizations.service.team_workspaces_enabled",
            return_value=True,
        ),
        patch(
            "openoutreach.proxies.provisioning.disable_massive_for_profile"
        ) as disable,
    ):
        webhooks._deactivate_user_profiles("u1")

    query = collection.find.call_args.args[0]
    clauses = query["$or"]
    assert {"org_id": {"$in": ["org-1"]}} in clauses
    assert {"user_id": "u1"} not in clauses

    updates = collection.update_many.call_args.args[1]["$set"]
    assert updates["active"] is False
    assert updates["is_active"] is False
    assert updates["daemon_status"] == "seat_required"
    disable.assert_called_once_with("p1", reason="subscription_canceled")
