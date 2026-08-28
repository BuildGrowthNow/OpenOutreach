from openoutreach.api_v2.daemon_auth import canonical_request, verify_request
from openoutreach.desktop import device_identity
from openoutreach.desktop.device_identity import DeviceIdentity


class FakeKeyring:
    def __init__(self):
        self.values = {}

    def get_password(self, service, key):
        return self.values.get((service, key))

    def set_password(self, service, key, value):
        self.values[(service, key)] = value

    def delete_password(self, service, key):
        self.values.pop((service, key), None)


def test_ed25519_identity_signs_canonical_request(monkeypatch):
    fake = FakeKeyring()
    monkeypatch.setattr(device_identity, "keyring", fake)
    identity = DeviceIdentity.load_or_create()
    canonical = canonical_request("POST", "/api/daemon/v2/tasks/x/complete", "", b"{}", 1, "n", "t")
    assert verify_request(identity.public_key_pem, canonical, identity.sign(canonical))
    assert fake.values


def test_identity_device_binding_can_be_cleared(monkeypatch):
    monkeypatch.setattr(device_identity, "keyring", FakeKeyring())
    identity = DeviceIdentity.load_or_create()
    identity.remember_device("device-1")
    identity.forget_device()
    assert identity.device_id is None
