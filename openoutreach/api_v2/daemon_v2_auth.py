"""FastAPI authentication for daemon v2 requests."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pymongo.errors import DuplicateKeyError

from openoutreach.api_v2.daemon_auth import canonical_request, decode_daemon_access_token, timestamp_is_fresh, token_id_without_verification, verify_request
from openoutreach.api_v2.daemon_security import is_secure_version
from openoutreach.api_v2.security_events import append_security_event
from openoutreach.api_v2.tenant_security import TenantContext
from openoutreach.config import settings
from openoutreach.mongodb.connection import get_mongodb_collection

_bearer = HTTPBearer()


def _audit_auth_failure(request: Request, event: str, *, tenant_id: str | None = None,
                        device_id: str | None = None) -> None:
    append_security_event(
        event,
        outcome="failure",
        actor_type="daemon",
        tenant_id=tenant_id,
        device_id=device_id,
        request_id=request.headers.get("x-request-id"),
    )


async def get_daemon_context(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> TenantContext:
    """Validate audience/purpose and bind request context to token claims."""
    if not is_secure_version(request.headers.get("x-daemon-version")):
        _audit_auth_failure(request, "daemon_auth_unsupported_version")
        raise HTTPException(status_code=426, detail="Desktop security update required")
    if not settings.DAEMON_JWT_PUBLIC_KEY:
        _audit_auth_failure(request, "daemon_auth_unavailable")
        raise HTTPException(status_code=503, detail="Daemon authentication unavailable")
    try:
        claims = decode_daemon_access_token(settings.DAEMON_JWT_PUBLIC_KEY, credentials.credentials)
    except Exception as exc:
        _audit_auth_failure(request, "daemon_auth_token_rejected")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid daemon token") from exc
    profile_ids = claims.get("profile_ids", [])
    scopes = claims.get("scopes", [])
    channel_profile_ids = claims.get("channel_profile_ids", {})
    if not isinstance(profile_ids, list) or not isinstance(scopes, list) or not isinstance(channel_profile_ids, dict):
        _audit_auth_failure(request, "daemon_auth_claims_rejected")
        raise HTTPException(status_code=401, detail="Invalid daemon token claims")
    devices = get_mongodb_collection("daemon_devices")
    if devices is None:
        _audit_auth_failure(request, "daemon_auth_unavailable", tenant_id=str(claims.get("tenant_id")), device_id=str(claims.get("device_id")))
        raise HTTPException(status_code=503, detail="Daemon authentication unavailable")
    device = devices.find_one(
        {"_id": str(claims["device_id"]), "user_id": str(claims["tenant_id"]), "revoked": False},
        {"profile_ids": 1, "channels": 1, "channel_profile_ids": 1,
         "version": 1, "public_key": 1},
    )
    if not device or not is_secure_version(str(device.get("version", ""))):
        _audit_auth_failure(request, "daemon_auth_device_rejected", tenant_id=str(claims.get("tenant_id")), device_id=str(claims.get("device_id")))
        raise HTTPException(status_code=401, detail="Device revoked or unsupported")
    try:
        timestamp = int(request.headers.get("x-daemon-timestamp", ""))
        nonce = request.headers["x-daemon-nonce"]
        signature = request.headers["x-daemon-signature"]
        if not timestamp_is_fresh(timestamp):
            raise ValueError("stale proof")
        body = await request.body()
        proof = canonical_request(request.method, request.url.path, request.url.query, body, timestamp, nonce, token_id_without_verification(credentials.credentials))
        if not verify_request(str(device["public_key"]).encode(), proof, signature):
            raise ValueError("invalid proof")
        nonces = get_mongodb_collection("daemon_nonces")
        if nonces is None:
            raise ValueError("nonce store unavailable")
        from datetime import datetime, timedelta, timezone
        from uuid import uuid4
        nonces.insert_one({"_id": str(uuid4()), "device_id": str(claims["device_id"]), "nonce": nonce,
                           "created_at": datetime.now(timezone.utc),
                           "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5)})
    except (KeyError, ValueError, TypeError, DuplicateKeyError) as exc:
        _audit_auth_failure(
            request,
            "daemon_auth_nonce_replay" if isinstance(exc, DuplicateKeyError) else "daemon_auth_proof_rejected",
            tenant_id=str(claims.get("tenant_id")),
            device_id=str(claims.get("device_id")),
        )
        raise HTTPException(status_code=401, detail="Invalid daemon request proof") from exc
    # Intersect claims with current server bindings so unbinding takes effect
    # without waiting for an access token to expire.
    profile_ids = [value for value in profile_ids if value in device.get("profile_ids", [])]
    scopes = [value for value in scopes if value in device.get("channels", [])]
    device_bindings = device.get("channel_profile_ids") or {}
    claimed_bindings = channel_profile_ids or device_bindings
    bindings: dict[str, frozenset[str]] = {}
    for channel, values in claimed_bindings.items():
        if not isinstance(values, list):
            _audit_auth_failure(request, "daemon_auth_claims_rejected", tenant_id=str(claims.get("tenant_id")), device_id=str(claims.get("device_id")))
            raise HTTPException(status_code=401, detail="Invalid channel profile claims")
        allowed = device_bindings.get(channel, values)
        bindings[str(channel)] = frozenset(
            str(value) for value in values if value in allowed and value in profile_ids
        )
    return TenantContext(
        tenant_id=str(claims["tenant_id"]),
        actor_type="daemon",
        subject_id=str(claims["device_id"]),
        device_id=str(claims["device_id"]),
        profile_ids=frozenset(str(value) for value in profile_ids),
        scopes=frozenset(str(value) for value in scopes),
        channel_profile_ids=bindings,
    )


def require_profile(context: TenantContext, profile_id: str, channel: str) -> None:
    channel_profiles = (context.channel_profile_ids or {}).get(channel)
    profile_allowed = profile_id in channel_profiles if channel_profiles is not None else profile_id in context.profile_ids
    if not profile_allowed or channel not in context.scopes:
        raise HTTPException(status_code=404, detail="Resource not found")
