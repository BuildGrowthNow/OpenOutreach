"""Local daemon identity backed by the operating-system credential store.

The private key never leaves the desktop keychain.  This is not a claim that a
customer-controlled host is trusted: a local administrator can still use the
key, so server-side scopes and revocation remain authoritative.
"""

from __future__ import annotations

import base64
try:
    import keyring
except ModuleNotFoundError:  # Desktop builds declare keyring; server tests may not.
    keyring = None  # type: ignore[assignment]
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

SERVICE_NAME = "Lengrowth daemon v2"
_PRIVATE_KEY = "device_private_key"
_DEVICE_ID = "device_id"


class DeviceIdentity:
    def __init__(self, private_key_pem: bytes, device_id: str | None = None) -> None:
        self._private_key = serialization.load_pem_private_key(private_key_pem, password=None)
        if not isinstance(self._private_key, Ed25519PrivateKey):
            raise ValueError("unsupported daemon device key")
        self.device_id = device_id

    @classmethod
    def load_or_create(cls) -> "DeviceIdentity":
        if keyring is None:
            raise RuntimeError("OS keychain support is unavailable")
        stored = keyring.get_password(SERVICE_NAME, _PRIVATE_KEY)
        device_id = keyring.get_password(SERVICE_NAME, _DEVICE_ID)
        if stored:
            return cls(stored.encode("ascii"), device_id)
        identity = cls._new()
        keyring.set_password(SERVICE_NAME, _PRIVATE_KEY, identity.private_key_pem.decode("ascii"))
        return identity

    @classmethod
    def _new(cls) -> "DeviceIdentity":
        key = Ed25519PrivateKey.generate()
        pem = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        return cls(pem)

    @property
    def private_key_pem(self) -> bytes:
        return self._private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )

    @property
    def public_key_pem(self) -> bytes:
        return self._private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )

    def sign(self, payload: bytes) -> str:
        return base64.urlsafe_b64encode(self._private_key.sign(payload)).rstrip(b"=").decode("ascii")

    def remember_device(self, device_id: str) -> None:
        if not device_id:
            raise ValueError("device id is required")
        if keyring is None:
            raise RuntimeError("OS keychain support is unavailable")
        keyring.set_password(SERVICE_NAME, _DEVICE_ID, device_id)
        self.device_id = device_id

    def forget_device(self) -> None:
        if keyring is None:
            self.device_id = None
            return
        try:
            keyring.delete_password(SERVICE_NAME, _DEVICE_ID)
        except Exception:
            pass
        self.device_id = None
