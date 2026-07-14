from __future__ import annotations

import base64
import hashlib
from typing import Optional

from cryptography.fernet import Fernet
from openoutreach.config import settings


def _derive_key_from_secret(
    secret: Optional[str], salt: str = "openoutreach-cookie-salt"
) -> bytes:
    """Derive a 32-byte key for Fernet from Django SECRET_KEY using SHA256."""
    if not secret:
        raise RuntimeError("SECRET_KEY is required for cookie encryption")
    # PBKDF2 could be used; simple SHA256 of secret+salt then base64-url encode is acceptable here
    h = hashlib.sha256()
    h.update(secret.encode("utf-8"))
    h.update(salt.encode("utf-8"))
    key_bytes = h.digest()
    return base64.urlsafe_b64encode(key_bytes)


def get_fernet_key() -> bytes:
    """Return a Fernet-compatible key.

    Priority:
    - settings.cookie_encryption_key (raw base64 urlsafe key)
    - derive from settings.secret_key
    """
    key = getattr(settings, "cookie_encryption_key", None)
    if key:
        if isinstance(key, str):
            return key.encode("utf-8")
        return key
    # Derive from SECRET_KEY
    secret = getattr(settings, "secret_key", None)
    if not secret:
        raise RuntimeError(
            "No cookie_encryption_key or secret_key configured for encryption"
        )
    return _derive_key_from_secret(secret)


def encrypt_bytes(data: bytes) -> bytes:
    f = Fernet(get_fernet_key())
    return f.encrypt(data)


def decrypt_bytes(token: bytes) -> bytes:
    f = Fernet(get_fernet_key())
    return f.decrypt(token)


def encrypt_text(text: str) -> str:
    token = encrypt_bytes(text.encode("utf-8"))
    return base64.urlsafe_b64encode(token).decode("utf-8")


def decrypt_text(encoded_token: str) -> str:
    token = base64.urlsafe_b64decode(encoded_token.encode("utf-8"))
    return decrypt_bytes(token).decode("utf-8")
