"""Proxy passwords must be encrypted at rest and readable by the daemon."""

import pytest
from cryptography.fernet import Fernet

from openoutreach.linkedin.models import LinkedInProfile
from openoutreach.mongodb.crypto import (
    decrypt_text,
    encrypt_text,
    is_encrypted,
    safe_decrypt,
    safe_encrypt,
)


@pytest.fixture(autouse=True)
def encryption_key(monkeypatch):
    monkeypatch.setenv("COOKIE_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.delenv("SECRET_KEY", raising=False)


def test_safe_encrypt_recognizes_and_does_not_double_encrypt():
    encrypted = encrypt_text("super-secret")

    assert is_encrypted(encrypted) is True
    assert safe_encrypt(encrypted) == encrypted
    assert safe_decrypt(encrypted) == "super-secret"


def test_proxy_password_is_encrypted_at_rest():
    profile = LinkedInProfile(
        user_id="user-1",
        linkedin_username="person@example.com",
        proxy_server="http://proxy.example.com:8080",
        proxy_username="proxy-user",
        proxy_password="super-secret",
    )

    document = profile.to_dict()

    assert document["proxy_password"] is None
    assert document["proxy_password_encrypted"]
    assert document["proxy_password_encrypted"] != "super-secret"
    assert decrypt_text(document["proxy_password_encrypted"]) == "super-secret"
    assert profile.proxy_password == "super-secret"


def test_from_dict_decrypts_encrypted_proxy_password():
    profile = LinkedInProfile.from_dict(
        {
            "_id": "profile-1",
            "user_id": "user-1",
            "proxy_password_encrypted": encrypt_text("super-secret"),
        }
    )

    assert profile.proxy_password == "super-secret"
    assert profile.to_dict()["proxy_password"] is None


def test_from_dict_upgrades_legacy_plaintext_in_memory():
    profile = LinkedInProfile.from_dict(
        {
            "_id": "profile-1",
            "user_id": "user-1",
            "proxy_password": "legacy-secret",
        }
    )

    assert profile.proxy_password == "legacy-secret"
    document = profile.to_dict()
    assert document["proxy_password"] is None
    assert decrypt_text(document["proxy_password_encrypted"]) == "legacy-secret"


def test_clearing_proxy_password_clears_the_encrypted_value():
    profile = LinkedInProfile(proxy_password="super-secret")

    profile.proxy_password = None

    assert profile.proxy_password is None
    assert profile.to_dict()["proxy_password_encrypted"] is None


class _ProfileCollection:
    def __init__(self, document):
        self.document = document

    def find_one(self, _query):
        return dict(self.document)


def test_refresh_from_db_loads_the_encrypted_proxy_password(monkeypatch):
    from openoutreach.linkedin import models as models_module

    collection = _ProfileCollection(
        {
            "_id": "profile-1",
            "proxy_password_encrypted": encrypt_text("super-secret"),
        }
    )
    monkeypatch.setattr(
        models_module, "get_mongodb_collection", lambda _name: collection
    )

    profile = LinkedInProfile(_id="profile-1", proxy_password="super-secret")
    profile._proxy_password_encrypted = None

    profile.refresh_from_db(fields=["proxy_password_encrypted"])
    assert profile.proxy_password == "super-secret"

    profile._proxy_password_encrypted = None
    profile.refresh_from_db()
    assert profile.proxy_password == "super-secret"


class _Cursor:
    def __init__(self, documents):
        self.documents = documents

    def __iter__(self):
        return iter(self.documents)


class _Collection:
    def __init__(self, documents):
        self.documents = documents
        self.updates = []

    def count_documents(self, query):
        return sum(
            1
            for document in self.documents
            if document.get("proxy_password") not in (None, "")
        )

    def find(self, query, projection=None):
        return _Cursor(
            [
                dict(document)
                for document in self.documents
                if document.get("proxy_password") not in (None, "")
            ]
        )

    def update_one(self, query, update):
        self.updates.append((query, update))
        for document in self.documents:
            if document["_id"] != query["_id"]:
                continue
            document.update(update.get("$set", {}))
            for key in update.get("$unset", {}):
                document.pop(key, None)


def test_migration_encrypts_plaintext_and_removes_the_column(monkeypatch):
    from openoutreach.migrations import encrypt_proxy_passwords as migration

    already_encrypted = encrypt_text("already-encrypted")
    collection = _Collection(
        [
            {
                "_id": "profile-1",
                "user_id": "user-1",
                "proxy_password": "legacy-secret",
            },
            {
                "_id": "profile-2",
                "user_id": "user-2",
                "proxy_password_encrypted": already_encrypted,
            },
        ]
    )

    monkeypatch.setattr(migration, "initialize_mongodb_connection", lambda: True)
    monkeypatch.setattr(
        migration, "get_mongodb_collection", lambda _name: collection
    )

    assert migration.migrate_proxy_passwords(dry_run=False) is True

    first, second = collection.documents
    assert "proxy_password" not in first
    assert decrypt_text(first["proxy_password_encrypted"]) == "legacy-secret"
    assert second["proxy_password_encrypted"] == already_encrypted
    assert len(collection.updates) == 1


def test_migration_replaces_plaintext_in_encrypted_column(monkeypatch):
    from openoutreach.migrations import encrypt_proxy_passwords as migration

    collection = _Collection(
        [
            {
                "_id": "profile-1",
                "user_id": "user-1",
                "proxy_password": "legacy-secret",
                "proxy_password_encrypted": "also-plaintext",
            }
        ]
    )

    monkeypatch.setattr(migration, "initialize_mongodb_connection", lambda: True)
    monkeypatch.setattr(
        migration, "get_mongodb_collection", lambda _name: collection
    )

    assert migration.migrate_proxy_passwords(dry_run=False) is True

    document = collection.documents[0]
    assert "proxy_password" not in document
    assert decrypt_text(document["proxy_password_encrypted"]) == "legacy-secret"


def test_migration_dry_run_does_not_write(monkeypatch):
    from openoutreach.migrations import encrypt_proxy_passwords as migration

    collection = _Collection(
        [{"_id": "profile-1", "user_id": "user-1", "proxy_password": "legacy-secret"}]
    )

    monkeypatch.setattr(migration, "initialize_mongodb_connection", lambda: True)
    monkeypatch.setattr(
        migration, "get_mongodb_collection", lambda _name: collection
    )

    assert migration.migrate_proxy_passwords(dry_run=True) is True
    assert collection.updates == []
    assert collection.documents[0]["proxy_password"] == "legacy-secret"
