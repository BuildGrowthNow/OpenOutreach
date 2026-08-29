"""Minimal typed daemon gateway boundary.

Only safe compatibility/configuration metadata is exposed here. Work and
channel contracts are added behind this authentication boundary incrementally.
"""

from __future__ import annotations

import secrets
import json
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from openoutreach.api_v2.daemon_security import MIN_SECURE_DAEMON_VERSION, is_secure_version
from openoutreach.api_v2.daemon_auth import (
    canonical_request,
    hash_secret,
    issue_daemon_access_token,
    new_enrollment_code,
    random_refresh_token,
    timestamp_is_fresh,
    verify_request,
)
from openoutreach.api_v2.daemon_v2_auth import get_daemon_context, require_profile
from openoutreach.api_v2.tenant_security import TenantContext
from openoutreach.api_v2.dependencies_v2 import get_current_user
from openoutreach.config import settings
from openoutreach.linkedin.models import LinkedInProfile
from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.api_v2.security_events import append_security_event
from openoutreach.api_v2.daemon_channel_contracts import (
    EmailReceipt, EmailTaskSnapshot, LinkedInActionReceipt, LinkedInObservation,
    LinkedInTaskSnapshot, MailboxGrant, SessionState, WhatsAppState,
    WhatsAppActionReceipt, WhatsAppSyncBatch, WhatsAppTaskSnapshot,
)

router = APIRouter(prefix="/daemon/v2", tags=["daemon-v2"])


class CompatibilityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    minimum_supported: str = MIN_SECURE_DAEMON_VERSION
    minimum_secure: str = MIN_SECURE_DAEMON_VERSION
    force_update: bool = True
    capabilities: list[str] = Field(default_factory=list)


class ConfigurationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str
    active_hours: "ActiveHours"
    rate_limits: "RateLimits"
    channel_policy: "ChannelPolicy"
    task_capabilities: list[str]


class ActiveHours(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    start_hour: int = Field(ge=0, le=23)
    end_hour: int = Field(ge=0, le=23)
    timezone: str = Field(min_length=1, max_length=64)
    days: list[int] = Field(min_length=1, max_length=7)

    @field_validator("days")
    @classmethod
    def valid_days(cls, value: list[int]) -> list[int]:
        if any(day < 0 or day > 6 for day in value) or len(set(value)) != len(value):
            raise ValueError("days must contain unique values from 0 through 6")
        return value


class RateLimits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    velocity: int = Field(ge=0, le=10_000)
    daily_connect_limit: int = Field(ge=0, le=100_000)
    daily_message_limit: int = Field(ge=0, le=100_000)
    cooldown_minutes: int = Field(ge=0, le=1_440)


class ChannelPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    linkedin: bool
    whatsapp: bool
    email: bool


class ClaimRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str
    channel: Literal["linkedin", "whatsapp", "email"]
    supported_task_types: list[str] = Field(default_factory=list, max_length=20)


class LeaseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    lease_id: str
    task_type: str
    channel: str
    attempt: int
    idempotency_key: str
    lease_expires_at: datetime
    snapshot: dict[str, Any]


class LeaseMutation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lease_id: str = Field(min_length=16, max_length=128)


class CompleteRequest(LeaseMutation):
    idempotency_key: str = Field(min_length=16, max_length=128)
    result: dict[str, Any] = Field(default_factory=dict)

    @field_validator("result")
    @classmethod
    def result_must_be_bounded(cls, value: dict[str, Any]) -> dict[str, Any]:
        encoded = json.dumps(value, separators=(",", ":"), default=str).encode("utf-8")
        if len(encoded) > 64 * 1024:
            raise ValueError("result exceeds 64 KiB")
        forbidden = {"password", "cookie", "cookies", "token", "secret", "mongodb_uri", "provider_key", "qr"}
        def walk(item: Any) -> None:
            if isinstance(item, dict):
                for key, child in item.items():
                    if any(word in str(key).lower() for word in forbidden):
                        raise ValueError("result contains a forbidden field")
                    walk(child)
            elif isinstance(item, list):
                for child in item:
                    walk(child)
        walk(value)
        return value


class FailRequest(LeaseMutation):
    category: Literal["retryable", "permanent", "auth", "rate_limited"]
    error: str = Field(default="", max_length=500)
    idempotency_key: str = Field(default="", max_length=128)


class EmailExecutionRequest(LeaseMutation):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1, max_length=256)
    idempotency_key: str = Field(min_length=16, max_length=128)
    operation: Literal["send", "reply_scan"]
    mailbox_grant: MailboxGrant
    recipient: str = Field(default="", max_length=320)
    subject: str = Field(default="", max_length=998)
    body: str = Field(default="", max_length=20_000)
    cursor: str = Field(default="", max_length=256)


class EnrollmentCodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_ids: list[str] = Field(min_length=1, max_length=20)
    channels: list[Literal["linkedin", "whatsapp", "email"]] = Field(min_length=1, max_length=3)
    device_name: str = Field(min_length=1, max_length=100)
    channel_profile_ids: dict[str, list[str]] = Field(default_factory=dict, max_length=3)

    @field_validator("channel_profile_ids")
    @classmethod
    def validate_channel_profile_ids(cls, value: dict[str, list[str]]) -> dict[str, list[str]]:
        allowed = {"linkedin", "whatsapp", "email"}
        if set(value) - allowed or any(not ids or len(ids) > 20 for ids in value.values()):
            raise ValueError("invalid channel profile bindings")
        return {channel: sorted(set(str(profile_id) for profile_id in ids))
                for channel, ids in value.items()}


class EnrollmentCodeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    expires_at: datetime
    profile_ids: list[str]
    channels: list[str]
    channel_profile_ids: dict[str, list[str]] = Field(default_factory=dict)


class DeviceEnrollRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=20, max_length=100)
    public_key: str = Field(min_length=100, max_length=5000)
    version: str = Field(min_length=1, max_length=30)
    platform: Literal["win32", "darwin", "linux"]
    capabilities: list[str] = Field(default_factory=list, max_length=30)


class DeviceEnrollResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str
    refresh_token: str
    profile_ids: list[str]
    channels: list[str]
    channel_profile_ids: dict[str, list[str]] = Field(default_factory=dict)


class TokenExchangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str
    refresh_token: str = Field(min_length=20, max_length=200)
    timestamp: int
    nonce: str = Field(min_length=16, max_length=128)
    signature: str = Field(min_length=32, max_length=2000)


class TokenExchangeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    refresh_token: str
    expires_in: int = 300
    profile_ids: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)
    channel_profile_ids: dict[str, list[str]] = Field(default_factory=dict)


class DeviceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str
    name: str
    platform: str
    version: str
    profile_ids: list[str]
    channels: list[str]
    revoked: bool
    last_seen_at: datetime | None = None


class DaemonEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=16, max_length=128)
    event_type: Literal["linkedin_state", "linkedin_observation", "whatsapp_state", "whatsapp_sync", "email_receipt"]
    profile_id: str
    channel: Literal["linkedin", "whatsapp", "email"]
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("payload")
    @classmethod
    def payload_must_be_bounded(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(value, separators=(",", ":"), default=str).encode("utf-8")) > 32 * 1024:
            raise ValueError("event payload exceeds 32 KiB")
        return value


class EventBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: list[DaemonEvent] = Field(min_length=1, max_length=100)


class EventBatchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: int
    duplicates: int


class TypedEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    accepted: bool = True
    duplicate: bool = False


@router.get("/compatibility", response_model=CompatibilityResponse)
async def compatibility(version: str | None = None) -> CompatibilityResponse:
    capabilities = ["device-auth", "typed-events"]
    if settings.DAEMON_TASK_CLAIM_ENABLED:
        capabilities.append("task-leases")
    for channel, enabled in (
        ("linkedin", settings.DAEMON_V2_LINKEDIN_ENABLED),
        ("whatsapp", settings.DAEMON_V2_WHATSAPP_ENABLED),
        ("email", settings.DAEMON_V2_EMAIL_ENABLED),
    ):
        if settings.DAEMON_TASK_CLAIM_ENABLED and enabled:
            capabilities.append(f"task:{channel}")
    return CompatibilityResponse(
        force_update=bool(version) and not is_secure_version(version),
        capabilities=capabilities,
    )


@router.post("/enrollment-codes", response_model=EnrollmentCodeResponse)
async def create_enrollment_code(
    request: EnrollmentCodeRequest,
    response: Response,
    user_id: str = Depends(get_current_user),
) -> EnrollmentCodeResponse:
    """Create a short-lived code after human authentication.

    Profile ownership is checked server-side; the requested IDs never become
    authorization authority for later daemon requests.
    """
    channels = sorted(set(request.channels))
    bindings = request.channel_profile_ids or {"linkedin": sorted(set(request.profile_ids))}
    if set(bindings) != set(channels):
        raise HTTPException(422, "Every enrollment channel requires an explicit profile binding")
    for channel in channels:
        channel_ids = bindings[channel]
        if channel == "linkedin":
            valid = all(LinkedInProfile.objects.get(_id=profile_id, user_id=user_id)
                        for profile_id in channel_ids)
        else:
            collection = get_mongodb_collection(
                "whatsapp_profiles" if channel == "whatsapp" else "mailboxes"
            )
            valid = collection is not None and all(
                collection.find_one({"_id": profile_id, "user_id": user_id})
                for profile_id in channel_ids
            )
        if not valid:
            raise HTTPException(404, f"{channel.title()} profile not found")
    profile_ids = sorted({profile_id for ids in bindings.values() for profile_id in ids})
    code, code_hash = new_enrollment_code()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    collection = get_mongodb_collection("daemon_enrollment_codes")
    if collection is None:
        raise HTTPException(503, "Database unavailable")
    collection.insert_one(
        {
            "_id": str(uuid4()),
            "code_hash": code_hash,
            "user_id": user_id,
            "profile_ids": profile_ids,
            "channels": channels,
            "channel_profile_ids": bindings,
            "device_name": request.device_name,
            "created_at": datetime.now(timezone.utc),
            "expires_at": expires_at,
            "used": False,
        }
    )
    append_security_event("daemon_enrollment_code_created", outcome="success", actor_type="human", tenant_id=user_id, metadata={"profile_count": len(profile_ids)})
    response.headers["Cache-Control"] = "no-store"
    return EnrollmentCodeResponse(code=code, expires_at=expires_at,
                                  profile_ids=profile_ids, channels=list(channels),
                                  channel_profile_ids=bindings)


@router.post("/devices/enroll", response_model=DeviceEnrollResponse)
async def enroll_device(request: DeviceEnrollRequest, response: Response) -> DeviceEnrollResponse:
    """Redeem an enrollment code exactly once and issue opaque refresh material."""
    from cryptography.hazmat.primitives import serialization

    if not is_secure_version(request.version):
        raise HTTPException(status.HTTP_426_UPGRADE_REQUIRED, "Desktop update required")

    try:
        serialization.load_pem_public_key(request.public_key.encode())
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, "Invalid device public key") from exc
    codes = get_mongodb_collection("daemon_enrollment_codes")
    devices = get_mongodb_collection("daemon_devices")
    families = get_mongodb_collection("daemon_refresh_families")
    if codes is None or devices is None or families is None:
        raise HTTPException(503, "Database unavailable")
    now = datetime.now(timezone.utc)
    code_doc = codes.find_one_and_update(
        {"code_hash": hash_secret(request.code), "used": False, "expires_at": {"$gt": now}},
        {"$set": {"used": True, "redeemed_at": now}},
        return_document=ReturnDocument.AFTER,
    )
    if not code_doc:
        raise HTTPException(404, "Enrollment code unavailable")
    device_id = str(uuid4())
    refresh = random_refresh_token()
    family_id = str(uuid4())
    devices.insert_one(
        {
            "_id": device_id,
            "user_id": code_doc["user_id"],
            "name": code_doc["device_name"],
            "platform": request.platform,
            "version": request.version,
            "capabilities": request.capabilities,
            "public_key": request.public_key,
            "profile_ids": code_doc["profile_ids"],
            "channels": code_doc["channels"],
            "channel_profile_ids": code_doc.get("channel_profile_ids", {}),
            "revoked": False,
            "created_at": now,
            "last_seen_at": now,
        }
    )
    families.insert_one(
        {
            "_id": str(uuid4()),
            "family_id": family_id,
            "device_id": device_id,
            "user_id": code_doc["user_id"],
            "token_hash": hash_secret(refresh),
            "expires_at": now + timedelta(days=30),
            "used": False,
            "revoked": False,
        }
    )
    append_security_event("daemon_device_enrolled", outcome="success", actor_type="daemon", tenant_id=str(code_doc["user_id"]), device_id=device_id, metadata={"platform": request.platform, "version": request.version})
    response.headers["Cache-Control"] = "no-store"
    return DeviceEnrollResponse(
        device_id=device_id,
        refresh_token=refresh,
        profile_ids=code_doc["profile_ids"],
        channels=code_doc["channels"],
        channel_profile_ids=code_doc.get("channel_profile_ids", {}),
    )


@router.post("/tokens/exchange", response_model=TokenExchangeResponse)
async def exchange_device_token(request: TokenExchangeRequest, response: Response) -> TokenExchangeResponse:
    if not settings.DAEMON_JWT_PRIVATE_KEY or not settings.DAEMON_JWT_KEY_ID:
        raise HTTPException(503, "Daemon authentication unavailable")
    devices = get_mongodb_collection("daemon_devices")
    families = get_mongodb_collection("daemon_refresh_families")
    nonces = get_mongodb_collection("daemon_nonces")
    if devices is None or families is None or nonces is None:
        raise HTTPException(503, "Database unavailable")
    if not timestamp_is_fresh(request.timestamp):
        raise HTTPException(401, "Stale token exchange proof")
    now = datetime.now(timezone.utc)
    device = devices.find_one({"_id": request.device_id, "revoked": False})
    if not device:
        raise HTTPException(401, "Invalid device credentials")
    proof_body = json.dumps({"device_id": request.device_id, "refresh_token": request.refresh_token}, separators=(",", ":"), sort_keys=True).encode()
    canonical = canonical_request("POST", "/api/daemon/v2/tokens/exchange", "", proof_body, request.timestamp, request.nonce, request.device_id)
    if not verify_request(str(device["public_key"]).encode(), canonical, request.signature):
        raise HTTPException(401, "Invalid token exchange proof")
    try:
        nonces.insert_one({"_id": str(uuid4()), "device_id": request.device_id, "nonce": request.nonce, "created_at": now, "expires_at": now + timedelta(minutes=5)})
    except DuplicateKeyError as exc:
        raise HTTPException(401, "Replayed token exchange proof") from exc
    family = families.find_one_and_update(
        {"device_id": request.device_id, "token_hash": hash_secret(request.refresh_token), "used": False, "revoked": False, "expires_at": {"$gt": now}},
        {"$set": {"used": True, "used_at": now}},
        return_document=ReturnDocument.AFTER,
    )
    if not family:
        families.update_many({"device_id": request.device_id}, {"$set": {"revoked": True}})
        devices.update_one({"_id": request.device_id}, {"$set": {"revoked": True}})
        append_security_event("daemon_refresh_reuse_detected", outcome="failure", actor_type="daemon", tenant_id=str(device["user_id"]), device_id=request.device_id)
        raise HTTPException(401, "Invalid device credentials")
    replacement = random_refresh_token()
    families.insert_one(
        {
            "_id": str(uuid4()),
            "family_id": family["family_id"],
            "device_id": request.device_id,
            "user_id": device["user_id"],
            "token_hash": hash_secret(replacement),
            "expires_at": family["expires_at"],
            "used": False,
            "revoked": False,
        }
    )
    access = issue_daemon_access_token(
        settings.DAEMON_JWT_PRIVATE_KEY,
        key_id=settings.DAEMON_JWT_KEY_ID,
        device_id=request.device_id,
        tenant_id=device["user_id"],
        profile_ids=device.get("profile_ids", []),
        scopes=device.get("channels", []),
        channel_profile_ids=device.get("channel_profile_ids", {}),
    )
    devices.update_one({"_id": request.device_id}, {"$set": {"last_seen_at": now}})
    append_security_event("daemon_token_issued", outcome="success", actor_type="daemon", tenant_id=str(device["user_id"]), device_id=request.device_id)
    response.headers["Cache-Control"] = "no-store"
    return TokenExchangeResponse(
        access_token=access,
        refresh_token=replacement,
        profile_ids=[str(value) for value in device.get("profile_ids", [])],
        channels=[str(value) for value in device.get("channels", [])],
        channel_profile_ids={
            str(channel): [str(value) for value in values]
            for channel, values in (device.get("channel_profile_ids") or {}).items()
        },
    )


@router.get("/devices", response_model=list[DeviceResponse])
async def list_devices(user_id: str = Depends(get_current_user)) -> list[DeviceResponse]:
    collection = get_mongodb_collection("daemon_devices")
    if collection is None:
        raise HTTPException(503, "Database unavailable")
    return [
        DeviceResponse(
            device_id=str(doc["_id"]),
            name=str(doc.get("name", "")),
            platform=str(doc.get("platform", "")),
            version=str(doc.get("version", "")),
            profile_ids=[str(value) for value in doc.get("profile_ids", [])],
            channels=[str(value) for value in doc.get("channels", [])],
            revoked=bool(doc.get("revoked", False)),
            last_seen_at=doc.get("last_seen_at"),
        )
        for doc in collection.find({"user_id": user_id})
    ]


@router.delete("/devices/{device_id}")
async def revoke_device(device_id: str, user_id: str = Depends(get_current_user)) -> dict[str, str]:
    collection = get_mongodb_collection("daemon_devices")
    families = get_mongodb_collection("daemon_refresh_families")
    if collection is None or families is None:
        raise HTTPException(503, "Database unavailable")
    result = collection.update_one({"_id": device_id, "user_id": user_id}, {"$set": {"revoked": True, "revoked_at": datetime.now(timezone.utc)}})
    if result.matched_count == 0:
        raise HTTPException(404, "Device not found")
    families.update_many({"device_id": device_id, "user_id": user_id}, {"$set": {"revoked": True}})
    return {"status": "revoked"}


@router.get("/configuration", response_model=None)
async def configuration(
    request: Request,
    profile_id: str,
    context: TenantContext = Depends(get_daemon_context),
) -> Response | ConfigurationResponse:
    requested_channel = request.query_params.get("channel", "linkedin")
    if requested_channel not in {"linkedin", "whatsapp", "email"}:
        raise HTTPException(422, "Unsupported channel")
    require_profile(context, profile_id, requested_channel)
    configs = get_mongodb_collection("site_config")
    if configs is None:
        raise HTTPException(503, "Database unavailable")
    # Projection is deliberately allowlisted; credentials and LLM settings
    # are never materialized into the daemon response.
    config = configs.find_one(
        {"user_id": context.tenant_id},
        {"_id": 0, "velocity": 1, "daily_connection_limit": 1,
         "daily_follow_up_limit": 1, "cooldown_minutes": 1,
         "enable_active_hours": 1, "active_start_hour": 1,
         "active_end_hour": 1, "active_timezone": 1, "active_days": 1},
    ) or {}
    response = ConfigurationResponse(
        profile_id=profile_id,
        active_hours=ActiveHours(
            enabled=bool(config.get("enable_active_hours", False)),
            start_hour=int(config.get("active_start_hour", 9)),
            end_hour=int(config.get("active_end_hour", 18)),
            timezone=str(config.get("active_timezone", "UTC")),
            days=list(config.get("active_days", [1, 2, 3, 4, 5])),
        ),
        rate_limits=RateLimits(
            velocity=int(config.get("velocity", 20)),
            daily_connect_limit=int(config.get("daily_connection_limit", 20)),
            daily_message_limit=int(config.get("daily_follow_up_limit", 40)),
            cooldown_minutes=int(config.get("cooldown_minutes", 0)),
        ),
        channel_policy=ChannelPolicy(**{
            channel: channel in context.scopes and {
                "linkedin": settings.DAEMON_V2_LINKEDIN_ENABLED,
                "whatsapp": settings.DAEMON_V2_WHATSAPP_ENABLED,
                "email": settings.DAEMON_V2_EMAIL_ENABLED,
            }[channel]
            for channel in ("linkedin", "whatsapp", "email")
        }),
        task_capabilities=(
            (["connect", "check_pending", "follow_up", "send_manual_message"]
             if "linkedin" in context.scopes and settings.DAEMON_V2_LINKEDIN_ENABLED else [])
            + (["whatsapp_follow_up", "whatsapp_message", "whatsapp_sync", "whatsapp_reconnect"]
               if "whatsapp" in context.scopes and settings.DAEMON_V2_WHATSAPP_ENABLED else [])
            + (["email_follow_up", "email_send", "email_reply_scan"]
               if "email" in context.scopes and settings.DAEMON_V2_EMAIL_ENABLED else [])
        ),
    )
    body = response.model_dump_json()
    etag = '"' + hashlib.sha256(body.encode("utf-8")).hexdigest() + '"'
    headers = {"ETag": etag, "Cache-Control": "no-store"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=body, media_type="application/json", headers=headers)


@router.post("/events/batch", response_model=EventBatchResponse)
async def ingest_events_v2(
    request: EventBatchRequest,
    context: TenantContext = Depends(get_daemon_context),
) -> EventBatchResponse:
    """Accept bounded observations; identity and ownership come from context."""
    collection = get_mongodb_collection("daemon_events")
    if collection is None:
        raise HTTPException(503, "Database unavailable")
    # Validate the entire batch before writing anything. A mixed batch must
    # never partially persist tenant-A events before rejecting a tenant-B or
    # unbound profile event later in the same request.
    for event in request.events:
        if event.channel not in context.scopes:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Channel not authorized")
        require_profile(context, event.profile_id, event.channel)
    now = datetime.now(timezone.utc)
    accepted = 0
    duplicates = 0
    for event in request.events:
        try:
            collection.insert_one(
                {
                    "_id": str(uuid4()),
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "user_id": context.tenant_id,
                    "device_id": context.device_id,
                    "profile_id": event.profile_id,
                    "channel": event.channel,
                    "payload": event.payload,
                    "created_at": now,
                }
            )
            accepted += 1
        except DuplicateKeyError:
            duplicates += 1
    append_security_event("daemon_events_ingested", outcome="success", actor_type="daemon", tenant_id=context.tenant_id, device_id=context.device_id, metadata={"accepted": accepted, "duplicates": duplicates})
    return EventBatchResponse(accepted=accepted, duplicates=duplicates)


def _store_typed_event(context: TenantContext, event_type: str, profile_id: str,
                       channel: str, payload: dict[str, Any], event_id: str) -> TypedEventResponse:
    require_profile(context, profile_id, channel)
    collection = get_mongodb_collection("daemon_events")
    if collection is None:
        raise HTTPException(503, "Database unavailable")
    try:
        collection.insert_one({"_id": str(uuid4()), "event_id": event_id,
                               "event_type": event_type, "user_id": context.tenant_id,
                               "device_id": context.device_id, "profile_id": profile_id,
                               "channel": channel, "payload": payload,
                               "created_at": datetime.now(timezone.utc)})
    except DuplicateKeyError:
        return TypedEventResponse(duplicate=True)
    return TypedEventResponse()


@router.post("/linkedin/{profile_id}/observations", response_model=TypedEventResponse)
async def linkedin_observation_v2(profile_id: str, observation: LinkedInObservation,
                                  context: TenantContext = Depends(get_daemon_context)) -> TypedEventResponse:
    if observation.profile_id != profile_id:
        raise HTTPException(422, "Profile mismatch")
    return _store_typed_event(context, "linkedin_observation", profile_id, "linkedin",
                              observation.model_dump(mode="json"), observation.target_key)


@router.post("/linkedin/{profile_id}/receipts", response_model=TypedEventResponse)
async def linkedin_receipt_v2(profile_id: str, receipt: LinkedInActionReceipt,
                              context: TenantContext = Depends(get_daemon_context)) -> TypedEventResponse:
    return _store_typed_event(context, "linkedin_receipt", profile_id, "linkedin",
                              receipt.model_dump(mode="json"), receipt.effect_key)


@router.post("/whatsapp/{profile_id}/state", response_model=TypedEventResponse)
async def whatsapp_state_v2(profile_id: str, state: WhatsAppState,
                            context: TenantContext = Depends(get_daemon_context)) -> TypedEventResponse:
    return _store_typed_event(context, "whatsapp_state", profile_id, "whatsapp",
                              state.model_dump(mode="json"), f"{profile_id}:{state.state}:{state.observed_at.isoformat()}")


@router.post("/whatsapp/{profile_id}/sync", response_model=TypedEventResponse)
async def whatsapp_sync_v2(profile_id: str, sync: WhatsAppSyncBatch,
                           context: TenantContext = Depends(get_daemon_context)) -> TypedEventResponse:
    if sync.profile_id != profile_id:
        raise HTTPException(422, "Profile mismatch")
    return _store_typed_event(context, "whatsapp_sync", profile_id, "whatsapp",
                              sync.model_dump(mode="json"), f"{profile_id}:{sync.cursor}")


@router.post("/whatsapp/{profile_id}/receipts", response_model=TypedEventResponse)
async def whatsapp_receipt_v2(profile_id: str, receipt: WhatsAppActionReceipt,
                              context: TenantContext = Depends(get_daemon_context)) -> TypedEventResponse:
    return _store_typed_event(context, "whatsapp_receipt", profile_id, "whatsapp",
                              receipt.model_dump(mode="json"), receipt.effect_key)


@router.post("/email/{profile_id}/receipts", response_model=TypedEventResponse)
async def email_receipt_v2(profile_id: str, receipt: EmailReceipt,
                           context: TenantContext = Depends(get_daemon_context)) -> TypedEventResponse:
    return _store_typed_event(context, "email_receipt", profile_id, "email",
                              receipt.model_dump(mode="json"), receipt.effect_key)


@router.post("/email/{profile_id}/execute")
async def execute_email_v2(
    profile_id: str,
    request: EmailExecutionRequest,
    context: TenantContext = Depends(get_daemon_context),
) -> dict[str, Any]:
    """Execute an email operation with credentials retained on the backend.

    The desktop receives only a short-lived mailbox grant. SMTP/IMAP
    credentials are loaded and used here, under the task lease and tenant
    ownership predicates, and never cross the daemon boundary.
    """
    require_profile(context, profile_id, "email")
    tasks = get_mongodb_collection("tasks")
    effects = get_mongodb_collection("daemon_effects")
    if tasks is None or effects is None:
        raise HTTPException(503, "Email execution unavailable")
    now = datetime.now(timezone.utc)
    task = tasks.find_one({**_lease_query(context, request.task_id, request.lease_id),
                           "lease_expires_at": {"$gt": now}})
    if not task:
        raise HTTPException(status.HTTP_410_GONE, "Lease expired or no longer owned")
    expected_key = str(task.get("idempotency_key") or _snapshot(task).get("effect_key") or "")
    if request.idempotency_key != expected_key:
        raise HTTPException(422, "Idempotency key does not match task effect")
    if request.mailbox_grant.task_id != request.task_id or request.mailbox_grant.mailbox_id != profile_id:
        raise HTTPException(422, "Mailbox grant is not bound to this task")
    if request.operation == "send":
        materialized = _snapshot(task)
        if any(request_data != materialized.get(field, "") for field, request_data in (
            ("recipient", request.recipient), ("subject", request.subject), ("body", request.body),
        )):
            raise HTTPException(422, "Email payload does not match the materialized task")
        existing = effects.find_one({"user_id": context.tenant_id, "effect_key": expected_key})
        if existing and existing.get("provider_state") == "sent":
            return {"status": "already_sent", "message_id": str(existing.get("message_id", ""))[:256]}
        if existing and existing.get("provider_state") == "sending":
            raise HTTPException(409, "Email send outcome is still being reconciled")
        mailbox_collection = get_mongodb_collection("mailboxes")
        mailbox_doc = mailbox_collection.find_one({"_id": profile_id, "user_id": context.tenant_id}) if mailbox_collection is not None else None
        if not mailbox_doc:
            raise HTTPException(404, "Mailbox not found")
        try:
            from openoutreach.emails.models import Mailbox
            from openoutreach.emails.sender import send_email
            mailbox = Mailbox.from_dict(mailbox_doc)
            if mailbox.paused:
                append_security_event("daemon_email_suppressed", outcome="denied",
                                      actor_type="daemon", tenant_id=context.tenant_id,
                                      device_id=context.device_id,
                                      metadata={"reason": "mailbox_paused"})
                return {"status": "suppressed", "reason": "mailbox_paused"}
            if mailbox.sent_today() >= mailbox.daily_limit:
                append_security_event("daemon_email_rate_limited", outcome="denied",
                                      actor_type="daemon", tenant_id=context.tenant_id,
                                      device_id=context.device_id,
                                      metadata={"reason": "mailbox_daily_limit"})
                return {"status": "rate_limited", "reason": "mailbox_daily_limit"}
            deal_id = str((task.get("payload") or {}).get("deal_id", ""))
            campaign_id = str((task.get("payload") or {}).get("campaign_id", ""))
            deals = get_mongodb_collection("deals")
            deal_doc = deals.find_one(
                {"_id": deal_id, "user_id": context.tenant_id},
                {"lead_id": 1, "email_message_id": 1, "email_first_message_id": 1,
                 "email_sequence_step": 1, "sequence_last_step_id": 1},
            ) if deal_id and deals is not None else None
            if deal_id:
                leads = get_mongodb_collection("leads")
                lead_doc = leads.find_one(
                    {"_id": deal_doc.get("lead_id"), "user_id": context.tenant_id},
                    {"email_unsubscribed": 1, "email_bounced": 1},
                ) if leads is not None and deal_doc and deal_doc.get("lead_id") else None
                if lead_doc and (lead_doc.get("email_unsubscribed") or lead_doc.get("email_bounced")):
                    append_security_event("daemon_email_suppressed", outcome="denied",
                                          actor_type="daemon", tenant_id=context.tenant_id,
                                          device_id=context.device_id,
                                          metadata={"reason": "recipient_suppressed"})
                    return {"status": "suppressed", "reason": "recipient_suppressed"}
            effects.update_one(
                {"user_id": context.tenant_id, "effect_key": expected_key},
                {"$set": {"task_id": request.task_id, "provider_state": "sending", "updated_at": now},
                 "$setOnInsert": {"_id": str(uuid4()), "created_at": now}},
                upsert=True,
            )
            in_reply_to = str((deal_doc or {}).get("email_message_id") or "") or None
            references = " ".join(str(value) for value in (
                (deal_doc or {}).get("email_first_message_id"),
                (deal_doc or {}).get("email_message_id"),
            ) if value) or in_reply_to
            message_id = send_email(
                mailbox, request.recipient, request.subject, request.body,
                in_reply_to=in_reply_to, references=references,
                deal_id=deal_id, campaign_id=campaign_id,
            )
        except Exception as exc:
            effects.update_one({"user_id": context.tenant_id, "effect_key": expected_key},
                               {"$set": {"provider_state": "failed", "updated_at": now}})
            raise HTTPException(503, "Email provider rejected the send") from exc
        effects.update_one({"user_id": context.tenant_id, "effect_key": expected_key},
                           {"$set": {"provider_state": "sent", "message_id": str(message_id)[:256], "updated_at": now}})
        if deal_id and deals is not None:
            current_step = int((deal_doc or {}).get("email_sequence_step", 0) or 0)
            update_fields: dict[str, Any] = {
                "state": "email_sent", "mailbox_id": profile_id,
                "email_sent_at": now, "email_message_id": str(message_id)[:256],
                "email_sequence_step": current_step + 1,
            }
            if current_step == 0:
                update_fields["email_first_message_id"] = str(message_id)[:256]
                update_fields["email_first_sent_at"] = now
            deals.update_one(
                {"_id": deal_id, "user_id": context.tenant_id,
                 "state": {"$nin": ["email_replied", "email_bounced"]}},
                {"$set": update_fields},
            )
        append_security_event("daemon_email_sent", outcome="success",
                              actor_type="daemon", tenant_id=context.tenant_id,
                              device_id=context.device_id,
                              metadata={"task_id": request.task_id})
        return {"status": "sent", "message_id": str(message_id)[:256]}
    materialized = _snapshot(task)
    if request.mailbox_grant.purpose != "reply_scan":
        raise HTTPException(422, "Mailbox grant purpose mismatch")
    deal_id = str((task.get("payload") or {}).get("deal_id", ""))
    deals = get_mongodb_collection("deals")
    deal = deals.find_one({"_id": deal_id, "user_id": context.tenant_id},
                          {"email_message_id": 1, "email_first_message_id": 1}) if deals is not None and deal_id else None
    if not deal:
        return {"status": "none", "replies": []}
    from openoutreach.emails.imap_checker import find_reply
    from openoutreach.emails.models import Mailbox
    mailbox = Mailbox.get(profile_id)
    if mailbox is None or mailbox.user_id != context.tenant_id:
        raise HTTPException(404, "Mailbox not found")
    result = find_reply(mailbox, [str(value) for value in (
        deal.get("email_message_id"), deal.get("email_first_message_id")) if value])
    if result is None:
        return {"status": "none", "replies": []}
    text, received_at = result
    if deals is not None:
        changed = deals.update_one(
            {"_id": deal_id, "user_id": context.tenant_id,
             "state": {"$in": ["email_sent", "email_opened"]}},
            {"$set": {"state": "email_replied"}},
        )
        if changed.modified_count:
            try:
                from openoutreach.mongodb.models_extended import ChatMessage
                ChatMessage(
                    deal_id=deal_id, content=text[:2000], is_outgoing=False,
                    channel="email", user_id=context.tenant_id,
                    creation_date=received_at,
                ).save()
            except Exception:
                # Reply state is authoritative; a chat projection failure is
                # observable in server logs and must not expose IMAP details.
                pass
    append_security_event("daemon_email_reply_observed", outcome="success",
                          actor_type="daemon", tenant_id=context.tenant_id,
                          device_id=context.device_id,
                          metadata={"task_id": request.task_id})
    return {"status": "replied", "replies": [{"body": text[:2000], "received_at": received_at.isoformat()}]}


@router.post("/sessions/{profile_id}/state", response_model=TypedEventResponse)
async def session_state_v2(profile_id: str, state: SessionState,
                           context: TenantContext = Depends(get_daemon_context)) -> TypedEventResponse:
    if state.profile_id != profile_id:
        raise HTTPException(422, "Profile mismatch")
    channel = "linkedin" if "linkedin" in context.scopes else next(iter(context.scopes), "linkedin")
    return _store_typed_event(context, "session_state", profile_id, channel,
                              state.model_dump(mode="json"), f"{profile_id}:{state.observed_at.isoformat()}")


def _task_profile_id(document: dict[str, Any]) -> str:
    """Return the server-owned profile binding for a task's channel.

    The legacy task schema stores WhatsApp's profile in
    ``linkedin_profile_id`` for historical reasons.  Campaign-backed tasks
    also carry the canonical WhatsApp binding, so prefer that value whenever
    present and never let a snapshot field choose the execution profile.
    """
    channel = str(document.get("channel", ""))
    if channel == "whatsapp":
        return str(document.get("whatsapp_profile_id") or document.get("linkedin_profile_id") or "")
    if channel == "email":
        return str(document.get("mailbox_id") or document.get("email_profile_id")
                   or document.get("linkedin_profile_id") or "")
    return str(document.get("linkedin_profile_id") or "")


def _snapshot(document: dict[str, Any]) -> dict[str, Any]:
    """Return only the fields a browser adapter needs for one action."""
    payload = document.get("payload") or {}
    allowed = {
        "campaign_id",
        "deal_id",
        "step_id",
        "message_id",
        "mailbox_id",
        "message",
        "target_public_identifier",
        "target_urn",
        "target_url",
        "target_phone",
        "recipient",
        "subject",
        "body",
        "mailbox_grant",
        "action",
    }
    snapshot = {key: payload[key] for key in allowed if key in payload}
    # Lazy slots historically contain only campaign/deal/message IDs. Resolve
    # the minimum browser inputs server-side; never send credentials, cookies,
    # campaign internals, or arbitrary model fields to the desktop.
    deal_id = snapshot.get("deal_id")
    owner_id = str(document.get("user_id", ""))
    profile_id = _task_profile_id(document)
    channel = str(document.get("channel", "linkedin"))
    # Client-controlled task payloads are not authorization. Target identity
    # is always re-derived from the owned deal/lead below.
    for key in ("target_public_identifier", "target_urn", "target_phone", "recipient"):
        snapshot.pop(key, None)
    snapshot["profile_id"] = profile_id
    if owner_id and snapshot.get("campaign_id"):
        campaigns = get_mongodb_collection("campaigns")
        campaign = campaigns.find_one(
            {"_id": snapshot["campaign_id"], "user_id": owner_id},
            {"linkedin_profile_id": 1, "whatsapp_profile_id": 1,
             "channel_sequence": 1},
        ) if campaigns is not None else None
        if channel == "email":
            campaign_binding_valid = bool(campaign and "email" in (campaign.get("channel_sequence") or []))
        else:
            bound_campaign_profile = (campaign or {}).get(
                "whatsapp_profile_id" if channel == "whatsapp" else "linkedin_profile_id"
            )
            campaign_binding_valid = bool(campaign and str(bound_campaign_profile or "") == profile_id)
        if not campaign_binding_valid:
            # Leave the task unmaterializable; claim-time logic releases it.
            snapshot.pop("campaign_id", None)
            snapshot.pop("deal_id", None)
    if not deal_id:
        # Legacy scheduler slots carry only campaign_id. Resolve one eligible
        # deal while the task is leased, always under the task owner/profile.
        deals = get_mongodb_collection("deals")
        if deals is not None and owner_id and snapshot.get("campaign_id"):
            state_by_type = {
                "connect": "READY_TO_CONNECT", "check_pending": "PENDING",
                "follow_up": "Connected", "whatsapp_follow_up": "Connected",
                "whatsapp_message": {"$in": ["Qualified", "Pending", "Connected"]},
                "email_follow_up": {"$in": ["Connected", "Pending", "Qualified", "email_queued", "email_sent", "email_opened"]},
            }
            candidate = deals.find_one(
                {"user_id": owner_id, "campaign_id": snapshot["campaign_id"],
                 "active_channel": channel,
                 "state": state_by_type.get(str(document.get("task_type", "")), {"$exists": True})},
                {"_id": 1, "lead_id": 1},
            )
            if candidate:
                deal_id = str(candidate["_id"])
                snapshot["deal_id"] = deal_id
    if deal_id and not snapshot.get("target_public_identifier"):
        deals = get_mongodb_collection("deals")
        leads = get_mongodb_collection("leads")
        deal = deals.find_one({"_id": deal_id, "user_id": owner_id,
                               "campaign_id": snapshot.get("campaign_id"),
                               "active_channel": channel},
                              {"lead_id": 1, "user_id": 1}) if deals is not None and owner_id else None
        lead = leads.find_one({"_id": deal.get("lead_id"), "user_id": owner_id},
                              {"public_identifier": 1, "urn": 1, "phone": 1,
                               "api_email": 1, "contact_info.email": 1}) if deal and leads is not None else None
        if lead:
            if lead.get("public_identifier"):
                snapshot["target_public_identifier"] = str(lead["public_identifier"])
            if lead.get("urn"):
                snapshot["target_urn"] = str(lead["urn"])
            contact = lead.get("contact_info") or {}
            if lead.get("phone"):
                snapshot["target_phone"] = str(lead["phone"])
            elif contact.get("phone"):
                snapshot["target_phone"] = str(contact["phone"])
            if lead.get("api_email"):
                snapshot["recipient"] = str(lead["api_email"])
            elif contact.get("email"):
                snapshot["recipient"] = str(contact["email"])
    message_id = payload.get("message_id")
    if message_id and not snapshot.get("message"):
        messages = get_mongodb_collection("messages")
        message = messages.find_one({"_id": message_id, "user_id": owner_id}, {"content": 1}) if messages is not None and owner_id else None
        if message and message.get("content"):
            snapshot["message"] = str(message["content"])
    if channel == "email" and isinstance(snapshot.get("mailbox_grant"), dict):
        try:
            grant = MailboxGrant.model_validate(snapshot["mailbox_grant"])
            if str(grant.task_id) != str(document.get("_id")):
                snapshot.pop("mailbox_grant", None)
            else:
                snapshot["mailbox_grant"] = grant.model_dump(mode="json")
        except Exception:
            snapshot.pop("mailbox_grant", None)
    if channel == "email" and "mailbox_grant" not in snapshot and owner_id and profile_id:
        mailboxes = get_mongodb_collection("mailboxes")
        mailbox = mailboxes.find_one({"_id": profile_id, "user_id": owner_id}, {"_id": 1}) if mailboxes is not None else None
        if mailbox:
            purpose = "reply_scan" if str(document.get("task_type", "")) == "email_reply_scan" else "send"
            snapshot["mailbox_grant"] = MailboxGrant(
                task_id=str(document.get("_id", "")), mailbox_id=profile_id,
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=45),
                purpose=purpose,
            ).model_dump(mode="json")
    # Effect identity is server-owned and stable across lease retries.  It is
    # intentionally based only on bounded task identity, not message bodies.
    effect_material = ":".join(str(snapshot.get(key, "")) for key in
                                ("deal_id", "step_id", "campaign_id", "action"))
    snapshot["effect_key"] = hashlib.sha256(
        f"{owner_id}:{profile_id}:{channel}:{document.get('task_type', '')}:"
        f"{document.get('_id', '')}:{effect_material}".encode()
    ).hexdigest()
    return snapshot


def _typed_snapshot(document: dict[str, Any]) -> dict[str, Any] | None:
    """Materialize and validate the exact channel contract returned to a daemon."""
    channel = str(document.get("channel", ""))
    task_type = str(document.get("task_type", ""))
    raw = _snapshot(document)
    try:
        if channel == "linkedin":
            snapshot = LinkedInTaskSnapshot.model_validate({
                key: raw[key] for key in
                ("profile_id", "target_public_identifier", "target_urn", "message", "effect_key")
                if key in raw
            })
        elif channel == "whatsapp":
            snapshot = WhatsAppTaskSnapshot.model_validate({
                key: raw[key] for key in
                ("profile_id", "target_phone", "message", "cursor", "effect_key")
                if key in raw
            })
        elif channel == "email":
            snapshot = EmailTaskSnapshot.model_validate({
                key: raw[key] for key in
                ("profile_id", "recipient", "subject", "body", "mailbox_grant", "cursor", "effect_key")
                if key in raw
            })
        else:
            return None
    except Exception:
        return None
    if task_type not in {
        "connect", "check_pending", "follow_up", "send_manual_message",
        "whatsapp_follow_up", "whatsapp_message", "whatsapp_sync", "whatsapp_reconnect",
        "email_follow_up", "email_send", "email_reply_scan",
    }:
        return None
    return snapshot.model_dump(mode="json")


def _snapshot_is_executable(snapshot: dict[str, Any], task_type: str, channel: str) -> bool:
    if channel == "linkedin":
        if task_type in {"connect", "check_pending"}:
            return bool(snapshot.get("target_public_identifier"))
        return bool(snapshot.get("target_public_identifier") and snapshot.get("message"))
    if channel == "whatsapp":
        return task_type in {"whatsapp_sync", "whatsapp_reconnect"} or bool(snapshot.get("target_phone") and snapshot.get("message"))
    if channel == "email":
        return task_type == "email_reply_scan" or bool(snapshot.get("recipient") and snapshot.get("subject") and snapshot.get("body") and snapshot.get("mailbox_grant"))
    return False


def _lease_query(context: TenantContext, task_id: str, lease_id: str) -> dict[str, Any]:
    return {
        "_id": task_id,
        "user_id": context.tenant_id,
        "leased_by_device_id": context.device_id,
        "lease_id": lease_id,
        "status": "running",
    }


def _require_task_binding(context: TenantContext, document: dict[str, Any]) -> None:
    """Re-check the current device/channel binding for every lease mutation."""
    channel = str(document.get("channel", ""))
    profile_id = _task_profile_id(document)
    if channel not in {"linkedin", "whatsapp", "email"} or not profile_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    require_profile(context, profile_id, channel)


def _project_channel_effect(context: TenantContext, task: dict[str, Any],
                            result: dict[str, Any], effect_key: str,
                            now: datetime) -> None:
    """Project a successful local-channel effect into tenant-owned CRM state.

    The durable effect record remains the idempotency authority. These
    projections use deterministic IDs and ``$setOnInsert`` so a provider
    success followed by a lost completion response can be reconciled without
    duplicating messages or activity logs. Email has its own backend writer
    and is intentionally excluded here.
    """
    channel = str(task.get("channel", ""))
    if channel not in {"linkedin", "whatsapp"}:
        return
    raw_payload = task.get("payload")
    payload: dict[str, Any] = raw_payload if isinstance(raw_payload, dict) else {}
    raw_snapshot = task.get("snapshot")
    snapshot: dict[str, Any] = raw_snapshot if isinstance(raw_snapshot, dict) else {}
    deal_id = str(payload.get("deal_id") or snapshot.get("deal_id") or "")
    campaign_id = str(payload.get("campaign_id") or snapshot.get("campaign_id") or "")
    if not deal_id:
        # Connect/session/sync tasks can be valid without a CRM deal.
        return
    deals = get_mongodb_collection("deals")
    if deals is None:
        raise HTTPException(503, "Channel effect projection unavailable")
    deal = deals.find_one({"_id": deal_id, "user_id": context.tenant_id},
                          {"lead_id": 1, "state": 1})
    if not deal:
        raise HTTPException(404, "Deal not found")

    task_type = str(task.get("task_type", ""))
    raw_receipt = result.get("receipt")
    receipt: dict[str, Any] = raw_receipt if isinstance(raw_receipt, dict) else result
    action = str(receipt.get("action") or "")
    if channel == "linkedin":
        action_type = {
            "connect": "connect",
            "pending_check": "check_pending",
            "follow_up": "follow_up",
            "manual_send": "send_manual_message",
        }.get(action, task_type)
        if action_type == "check_pending":
            return
        message_channel = "linkedin"
    else:
        action_type = "whatsapp_message" if action == "send" or task_type in {
            "whatsapp_message", "whatsapp_follow_up"
        } else task_type
        if action_type not in {"whatsapp_message"}:
            return
        message_channel = "whatsapp"

    profile_id = _task_profile_id(task)
    target_key = str(receipt.get("target_key") or "")[:256]
    message = str(snapshot.get("message") or payload.get("message") or "")[:20000]
    logs = get_mongodb_collection("action_logs")
    if logs is None:
        raise HTTPException(503, "Channel activity projection unavailable")
    logs.update_one(
        {"_id": f"daemon-effect:{effect_key}", "user_id": context.tenant_id},
        {"$setOnInsert": {
            "_id": f"daemon-effect:{effect_key}",
            "linkedin_profile_id": profile_id,
            "campaign_id": campaign_id,
            "action_type": action_type,
            "created_at": now,
            "details": {"deal_id": deal_id, "task_id": str(task.get("_id", "")),
                         "effect_key": effect_key, "target_key": target_key},
            "status": "completed",
            "error_message": "",
            "duration_ms": None,
            "user_id": context.tenant_id,
        }},
        upsert=True,
    )

    if message:
        messages = get_mongodb_collection("chat_messages")
        if messages is None:
            raise HTTPException(503, "Channel message projection unavailable")
        message_doc: dict[str, Any] = {
            "_id": f"daemon-message:{effect_key}",
            "deal_id": deal_id,
            "content": message,
            "owner_id": context.tenant_id,
            "linkedin_urn": target_key if message_channel == "linkedin" else "",
            "is_outgoing": True,
            "creation_date": now,
            "user_id": context.tenant_id,
            "channel": message_channel,
        }
        if message_channel == "whatsapp":
            message_doc["wa_msg_hash"] = hashlib.sha256(
                f"{deal_id}|True|{message}|{effect_key}".encode()
            ).hexdigest()
            message_doc["wa_delivery_status"] = "sent"
        messages.update_one(
            {"_id": message_doc["_id"], "user_id": context.tenant_id},
            {"$setOnInsert": message_doc}, upsert=True,
        )

    deal_update: dict[str, Any] = {"last_outgoing_at": now}
    if action_type == "connect":
        deal_update["state"] = "Pending"
    deals.update_one(
        {"_id": deal_id, "user_id": context.tenant_id,
         "state": {"$nin": ["email_replied", "email_bounced"]}},
        {"$set": deal_update},
    )


@router.post("/tasks/claim", response_model=LeaseResponse | None)
async def claim_task_v2(
    request: ClaimRequest,
    context: TenantContext = Depends(get_daemon_context),
) -> LeaseResponse | None:
    channel_flags = {"linkedin": settings.DAEMON_V2_LINKEDIN_ENABLED,
                     "whatsapp": settings.DAEMON_V2_WHATSAPP_ENABLED,
                     "email": settings.DAEMON_V2_EMAIL_ENABLED}
    if not settings.DAEMON_TASK_CLAIM_ENABLED or not channel_flags[request.channel]:
        return None
    require_profile(context, request.profile_id, request.channel)
    collection = get_mongodb_collection("tasks")
    if collection is None:
        raise HTTPException(503, "Database unavailable")
    now = datetime.now(timezone.utc)
    lease_id = secrets.token_urlsafe(24)
    profile_predicate: Any = {"linkedin_profile_id": request.profile_id}
    if request.channel == "whatsapp":
        # New tasks may use the canonical field while older scheduler rows
        # retain WhatsApp's historical alias in linkedin_profile_id.
        profile_predicate = {"$or": [
            {"linkedin_profile_id": request.profile_id},
            {"whatsapp_profile_id": request.profile_id},
        ]}
    elif request.channel == "email":
        # Support historical scheduler rows and canonical mailbox-backed rows.
        profile_predicate = {"$or": [
            {"linkedin_profile_id": request.profile_id},
            {"mailbox_id": request.profile_id},
            {"email_profile_id": request.profile_id},
        ]}
    query: dict[str, Any] = {
        "user_id": context.tenant_id,
        **profile_predicate,
        "channel": request.channel,
        "status": "pending",
        "scheduled_at": {"$lte": now},
    }
    supported_by_channel = {
        "linkedin": {"connect", "check_pending", "follow_up", "send_manual_message"},
        "whatsapp": {"whatsapp_follow_up", "whatsapp_message", "whatsapp_sync", "whatsapp_reconnect"},
        "email": {"email_follow_up", "email_send", "email_reply_scan"},
    }
    if request.supported_task_types:
        requested = set(request.supported_task_types)
        allowed = requested & supported_by_channel[request.channel]
        if not allowed:
            return None
        query["task_type"] = {"$in": sorted(allowed)}
    document = collection.find_one_and_update(
        query,
        {
            "$set": {
                "status": "running",
                "started_at": now,
                "leased_by_device_id": context.device_id,
                "lease_id": lease_id,
                "lease_expires_at": now + timedelta(minutes=5),
            },
            "$inc": {"attempt": 1},
        },
        sort=[("scheduled_at", 1)],
        return_document=ReturnDocument.AFTER,
    )
    if not document:
        return None
    snapshot = _typed_snapshot(document)
    if snapshot is None:
        collection.update_one(
            {"_id": document["_id"], "user_id": context.tenant_id,
             "leased_by_device_id": context.device_id, "lease_id": lease_id,
             "status": "running"},
            {"$set": {"status": "pending", "lease_id": None,
                       "lease_expires_at": None}, "$unset": {"leased_by_device_id": ""}},
        )
        return None
    if not _snapshot_is_executable(snapshot, str(document.get("task_type", "")), request.channel):
        # Never hand a lazy/unmaterializable slot to an untrusted desktop.
        collection.update_one({"_id": document["_id"], "lease_id": lease_id,
                                "leased_by_device_id": context.device_id, "status": "running"},
                               {"$set": {"status": "pending", "started_at": None,
                                         "lease_id": None, "leased_by_device_id": None},
                                "$unset": {"lease_expires_at": ""}})
        append_security_event("daemon_task_not_materialized", outcome="denied", actor_type="daemon", tenant_id=context.tenant_id, device_id=context.device_id)
        return None
    collection.update_one({"_id": document["_id"], "lease_id": lease_id,
                           "leased_by_device_id": context.device_id},
                          {"$set": {"idempotency_key": str(snapshot.get("effect_key") or lease_id)}})
    return LeaseResponse(
        task_id=str(document["_id"]),
        lease_id=lease_id,
        task_type=str(document.get("task_type", "")),
        channel=request.channel,
        attempt=int(document.get("attempt", 1)),
        idempotency_key=str(snapshot.get("effect_key") or document.get("idempotency_key") or lease_id),
        lease_expires_at=document["lease_expires_at"],
        snapshot=snapshot,
    )


@router.post("/tasks/{task_id}/renew", response_model=LeaseResponse)
async def renew_task_v2(
    task_id: str,
    request: LeaseMutation,
    context: TenantContext = Depends(get_daemon_context),
) -> LeaseResponse:
    collection = get_mongodb_collection("tasks")
    if collection is None:
        raise HTTPException(503, "Database unavailable")
    now = datetime.now(timezone.utc)
    current = collection.find_one(
        {**_lease_query(context, task_id, request.lease_id),
         "lease_expires_at": {"$gt": now}}
    )
    if not current:
        raise HTTPException(status.HTTP_410_GONE, "Lease expired")
    _require_task_binding(context, current)
    document = collection.find_one_and_update(
        {**_lease_query(context, task_id, request.lease_id), "lease_expires_at": {"$gt": now}},
        {"$set": {"lease_expires_at": now + timedelta(minutes=5)}},
        return_document=ReturnDocument.AFTER,
    )
    if not document:
        raise HTTPException(status.HTTP_410_GONE, "Lease expired")
    channel = str(document.get("channel", ""))
    _require_task_binding(context, document)
    snapshot = _typed_snapshot(document)
    if snapshot is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Task snapshot is no longer executable")
    return LeaseResponse(
        task_id=str(document["_id"]),
        lease_id=request.lease_id,
        task_type=str(document.get("task_type", "")),
        channel=channel,
        attempt=int(document.get("attempt", 1)),
        idempotency_key=str(snapshot.get("effect_key") or document.get("idempotency_key") or request.lease_id),
        lease_expires_at=document["lease_expires_at"],
        snapshot=snapshot,
    )


@router.post("/tasks/{task_id}/complete")
async def complete_task_v2(
    task_id: str,
    request: CompleteRequest,
    context: TenantContext = Depends(get_daemon_context),
) -> dict[str, str]:
    collection = get_mongodb_collection("tasks")
    if collection is None:
        raise HTTPException(503, "Database unavailable")
    now = datetime.now(timezone.utc)
    prior = collection.find_one({"_id": task_id, "user_id": context.tenant_id})
    if prior:
        _require_task_binding(context, prior)
        expected_key = str(prior.get("idempotency_key") or _snapshot(prior).get("effect_key") or "")
        if expected_key and request.idempotency_key != expected_key:
            raise HTTPException(422, "Idempotency key does not match task effect")
        result_effect = request.result.get("effect_key")
        if result_effect is not None and str(result_effect) != expected_key:
            raise HTTPException(422, "Receipt effect does not match task effect")
    if prior and prior.get("status") == "completed":
        if prior.get("result_idempotency_key") == request.idempotency_key:
            return {"status": "completed", "replayed": "true"}
        raise HTTPException(status.HTTP_409_CONFLICT, "Task already completed")
    # Validate the lease before creating a durable effect record.  This keeps
    # expired, revoked, or wrong-device requests from reserving an idempotency
    # key that a later legitimate attempt can never use.
    current = collection.find_one({**_lease_query(context, task_id, request.lease_id),
                                   "lease_expires_at": {"$gt": now}})
    if not current:
        raise HTTPException(status.HTTP_410_GONE, "Lease expired or no longer owned")
    _require_task_binding(context, current)
    effects = get_mongodb_collection("daemon_effects")
    if effects is None:
        raise HTTPException(503, "Effect reconciliation unavailable")
    projection_task: dict[str, Any] = prior if isinstance(prior, dict) else current
    effect_document = {
        "_id": str(uuid4()), "user_id": context.tenant_id,
        "effect_key": request.idempotency_key, "task_id": task_id,
        "result": request.result, "created_at": now,
    }
    try:
        effects.insert_one(effect_document)
    except DuplicateKeyError:
        # Provider success may have been followed by a lost response. The
        # unique tenant/effect key makes a retry converge without reapplying
        # the provider action, but only for this exact task.
        existing = effects.find_one({"user_id": context.tenant_id,
                                     "effect_key": request.idempotency_key},
                                    {"task_id": 1})
        if existing and str(existing.get("task_id")) == task_id:
            _project_channel_effect(context, projection_task, request.result,
                                    request.idempotency_key, now)
            result = collection.update_one(
                {**_lease_query(context, task_id, request.lease_id),
                 "lease_expires_at": {"$gt": now}},
                {"$set": {"status": "completed", "completed_at": now,
                          "result_idempotency_key": request.idempotency_key}},
            )
            if result.matched_count == 0:
                raise HTTPException(status.HTTP_410_GONE, "Lease expired or no longer owned")
            return {"status": "completed", "reconciled": "true"}
        raise HTTPException(status.HTTP_409_CONFLICT, "Effect already belongs to another task")
    _project_channel_effect(context, projection_task, request.result,
                            request.idempotency_key, now)
    result = collection.update_one(
        {**_lease_query(context, task_id, request.lease_id), "lease_expires_at": {"$gt": now}},
        {"$set": {"status": "completed", "completed_at": now, "result": request.result, "result_idempotency_key": request.idempotency_key}},
    )
    if result.matched_count == 0:
        raise HTTPException(status.HTTP_410_GONE, "Lease expired or no longer owned")
    append_security_event("daemon_task_completed", outcome="success", actor_type="daemon", tenant_id=context.tenant_id, device_id=context.device_id, metadata={"task_id": task_id})
    return {"status": "completed"}


@router.post("/tasks/{task_id}/fail")
async def fail_task_v2(
    task_id: str,
    request: FailRequest,
    context: TenantContext = Depends(get_daemon_context),
) -> dict[str, str]:
    collection = get_mongodb_collection("tasks")
    if collection is None:
        raise HTTPException(503, "Database unavailable")
    now = datetime.now(timezone.utc)
    prior = collection.find_one({"_id": task_id, "user_id": context.tenant_id,
                                 "leased_by_device_id": context.device_id})
    if prior:
        _require_task_binding(context, prior)
    if prior and prior.get("status") == "failed" and request.idempotency_key and prior.get("failure_idempotency_key") == request.idempotency_key:
        return {"status": "failed", "replayed": "true"}
    current = collection.find_one(
        {**_lease_query(context, task_id, request.lease_id),
         "lease_expires_at": {"$gt": now}}
    )
    if not current:
        raise HTTPException(status.HTTP_410_GONE, "Lease expired or no longer owned")
    _require_task_binding(context, current)
    result = collection.update_one(
        {**_lease_query(context, task_id, request.lease_id), "lease_expires_at": {"$gt": now}},
        {"$set": {"status": "failed", "completed_at": now, "failure_category": request.category, "error_message": request.error, "failure_idempotency_key": request.idempotency_key}},
    )
    if result.matched_count == 0:
        raise HTTPException(status.HTTP_410_GONE, "Lease expired or no longer owned")
    append_security_event("daemon_task_failed", outcome="success", actor_type="daemon", tenant_id=context.tenant_id, device_id=context.device_id, metadata={"task_id": task_id, "category": request.category})
    return {"status": "failed"}


@router.post("/tasks/{task_id}/cancel-ack")
async def cancel_ack_task_v2(
    task_id: str,
    request: LeaseMutation,
    context: TenantContext = Depends(get_daemon_context),
) -> dict[str, str]:
    collection = get_mongodb_collection("tasks")
    if collection is None:
        raise HTTPException(503, "Database unavailable")
    current = collection.find_one({**_lease_query(context, task_id, request.lease_id),
                                   "cancel_requested": True})
    if not current:
        raise HTTPException(404, "Task not found")
    _require_task_binding(context, current)
    result = collection.update_one(
        {**_lease_query(context, task_id, request.lease_id), "cancel_requested": True},
        {"$set": {"status": "cancelled", "completed_at": datetime.now(timezone.utc)}},
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Task not found")
    return {"status": "cancelled"}
