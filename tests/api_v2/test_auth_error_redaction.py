from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from openoutreach.api_v2 import dependencies_v2


@pytest.mark.asyncio
async def test_unexpected_authentication_error_is_not_echoed(monkeypatch):
    def fail_decode(*args, **kwargs):
        raise RuntimeError("authorization=super-secret internal-db.example")

    monkeypatch.setattr(dependencies_v2.jwt, "decode", fail_decode)
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="opaque")

    with pytest.raises(HTTPException) as raised:
        await dependencies_v2.get_current_user(credentials)

    assert raised.value.status_code == 401
    assert raised.value.detail == "Invalid authentication"
    assert "super-secret" not in str(raised.value.detail)
    assert "internal-db.example" not in str(raised.value.detail)


def test_account_cancellation_does_not_return_raw_validation_errors():
    source = (
        Path(__file__).parents[2]
        / "openoutreach"
        / "api_v2"
        / "routers"
        / "auth.py"
    ).read_text(encoding="utf-8")

    assert "detail=str(e)" not in source
