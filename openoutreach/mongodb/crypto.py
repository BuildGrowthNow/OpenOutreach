"""
Fernet (AES-256) Encryption Utilities - Django Independent

Uses COOKIE_ENCRYPTION_KEY or derives from SECRET_KEY env var.
This module has NO Django dependencies and can be used in pure Python/FastAPI.
"""

import base64
import hashlib
import os
import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


def get_fernet_key() -> bytes:
    """
    Get Fernet key from environment (no Django dependency).

    Priority:
    1. COOKIE_ENCRYPTION_KEY - explicit encryption key
    2. SECRET_KEY - derive key from Django/app secret

    Raises:
        RuntimeError: If neither key is available
    """
    # Try explicit encryption key first
    key = os.environ.get("COOKIE_ENCRYPTION_KEY")
    if key:
        # Ensure it's bytes
        if isinstance(key, str):
            # Check if it's already base64-encoded (44 chars for Fernet)
            if len(key) == 44:
                try:
                    # Validate it's valid base64
                    base64.urlsafe_b64decode(key.encode("utf-8"))
                    return key.encode("utf-8")
                except Exception:
                    pass

            # Otherwise, it's a raw key - encode it
            return key.encode("utf-8")
        return key

    # Fall back to deriving from SECRET_KEY
    secret = os.environ.get("SECRET_KEY")
    if not secret:
        raise RuntimeError(
            "No COOKIE_ENCRYPTION_KEY or SECRET_KEY in environment. "
            "Set one of these environment variables to enable encryption."
        )

    # Derive a deterministic Fernet key from SECRET_KEY
    h = hashlib.sha256()
    h.update(secret.encode("utf-8"))
    h.update(b"openoutreach-cookie-salt")  # Domain-specific salt
    derived_key = h.digest()

    # Fernet requires base64-encoded 32-byte key
    return base64.urlsafe_b64encode(derived_key)


def encrypt_text(text: str) -> str:
    """
    Encrypt text using Fernet (AES-256).

    Args:
        text: Plain text to encrypt

    Returns:
        Base64-encoded encrypted token

    Raises:
        RuntimeError: If encryption key not available
    """
    if not text:
        return ""

    try:
        key = get_fernet_key()
        f = Fernet(key)
        token = f.encrypt(text.encode("utf-8"))
        return base64.urlsafe_b64encode(token).decode("utf-8")
    except Exception as e:
        logger.error("Failed to encrypt text: %s", type(e).__name__)
        raise


def decrypt_text(encoded_token: str) -> str:
    """
    Decrypt Fernet-encrypted text.

    Args:
        encoded_token: Base64-encoded encrypted token

    Returns:
        Decrypted plain text

    Raises:
        RuntimeError: If encryption key not available
        InvalidToken: If token is invalid or corrupted
    """
    if not encoded_token:
        return ""

    try:
        key = get_fernet_key()
        f = Fernet(key)
        token = base64.urlsafe_b64decode(encoded_token.encode("utf-8"))
        decrypted = f.decrypt(token)
        return decrypted.decode("utf-8")
    except InvalidToken as e:
        logger.error("Invalid encryption token (corrupted or wrong key): %s", type(e).__name__)
        raise
    except Exception as e:
        logger.error("Failed to decrypt text: %s", type(e).__name__)
        raise


def generate_key() -> str:
    """
    Generate a new Fernet key for COOKIE_ENCRYPTION_KEY.

    Returns:
        Base64-encoded 32-byte key suitable for Fernet

    Example:
        >>> key = generate_key()
        >>> print(f"COOKIE_ENCRYPTION_KEY={key}")
        COOKIE_ENCRYPTION_KEY=abcd1234...
    """
    return Fernet.generate_key().decode("utf-8")


def encrypt_dict(data: dict, keys_to_encrypt: list) -> dict:
    """
    Encrypt specific keys in a dictionary.

    Args:
        data: Dictionary with data
        keys_to_encrypt: List of keys to encrypt

    Returns:
        Dictionary with specified keys encrypted

    Example:
        >>> data = {"email": "user@example.com", "password": "secret", "name": "John"}
        >>> encrypted = encrypt_dict(data, ["email", "password"])
        >>> # email and password are now encrypted, name is unchanged
    """
    result = data.copy()
    for key in keys_to_encrypt:
        if key in result and result[key]:
            result[key] = encrypt_text(str(result[key]))
    return result


def decrypt_dict(data: dict, keys_to_decrypt: list) -> dict:
    """
    Decrypt specific keys in a dictionary.

    Args:
        data: Dictionary with encrypted data
        keys_to_decrypt: List of keys to decrypt

    Returns:
        Dictionary with specified keys decrypted

    Example:
        >>> decrypted = decrypt_dict(encrypted_data, ["email", "password"])
    """
    result = data.copy()
    for key in keys_to_decrypt:
        if key in result and result[key]:
            try:
                result[key] = decrypt_text(result[key])
            except (InvalidToken, Exception) as e:
                logger.warning("Failed to decrypt key '%s': %s", key, type(e).__name__)
                result[key] = None
    return result


def is_encrypted(text: str) -> bool:
    """
    Check if text appears to be encrypted.

    This is a heuristic check - not 100% accurate but useful for
    avoiding double-encryption.

    Args:
        text: Text to check

    Returns:
        True if text looks encrypted, False otherwise
    """
    if not text:
        return False

    try:
        # Encrypted text should be base64-encoded
        # Try to decode and check if it's valid Fernet token format
        decoded = base64.urlsafe_b64decode(text.encode("utf-8"))

        # Fernet tokens start with specific version bytes
        # Version 0x80 (128) is current
        if len(decoded) > 0 and decoded[0] == 0x80:
            return True

        return False
    except Exception:
        return False


def safe_encrypt(text: str) -> str:
    """
    Safely encrypt text, avoiding double-encryption.

    Args:
        text: Text to encrypt

    Returns:
        Encrypted text (or original if already encrypted)
    """
    if not text:
        return ""

    if is_encrypted(text):
        logger.debug("Text appears already encrypted, skipping")
        return text

    return encrypt_text(text)


def safe_decrypt(text: str) -> str:
    """
    Safely decrypt text, returning original if not encrypted.

    Args:
        text: Text to decrypt

    Returns:
        Decrypted text (or original if not encrypted)
    """
    if not text:
        return ""

    if not is_encrypted(text):
        logger.debug("Text does not appear encrypted, returning as-is")
        return text

    try:
        return decrypt_text(text)
    except Exception as e:
        logger.warning("Failed to decrypt text: %s. Returning original.", type(e).__name__)
        return text


class EncryptedField:
    """
    Descriptor for auto-encrypting/decrypting model fields.

    Usage in a model:
        class MyModel:
            password = EncryptedField()

            def __init__(self, password=""):
                self._password = None
                self.password = password  # Auto-encrypts

        # When reading password, it's auto-decrypted
        # When writing password, it's auto-encrypted
    """

    def __init__(self, field_name: Optional[str] = None):
        self.field_name = field_name

    def __set_name__(self, owner, name):
        if self.field_name is None:
            self.field_name = f"_{name}"

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self

        field_name = self.field_name
        if field_name is None:
            return ""
        encrypted_value = getattr(obj, field_name, None)
        if not encrypted_value:
            return ""

        return safe_decrypt(encrypted_value)

    def __set__(self, obj, value):
        field_name = self.field_name
        if field_name is None:
            return
        if not value:
            setattr(obj, field_name, "")
            return

        encrypted = safe_encrypt(value)
        setattr(obj, field_name, encrypted)


__all__ = [
    'get_fernet_key',
    'encrypt_text',
    'decrypt_text',
    'generate_key',
    'encrypt_dict',
    'decrypt_dict',
    'is_encrypted',
    'safe_encrypt',
    'safe_decrypt',
    'EncryptedField',
]
