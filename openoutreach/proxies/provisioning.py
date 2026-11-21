"""Massive Reseller provisioning, lifecycle, usage sync, and budgets (Phase 2).

The public entry point used by account creation is :func:`provision_managed_proxy`.
It prefers a Reseller sub-account, falls back to the Phase 1 parent
``-subaccount`` credentials, and never leaves a cloud profile without a proxy.

All functions are server-side. Sub-account passwords are encrypted in the proxy
record and never appear in logs, API responses, audit metadata, or test output.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

from openoutreach.config import settings
from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.mongodb.crypto import safe_encrypt
from openoutreach.organizations.audit import record_org_audit
from openoutreach.proxies.massive_reseller import (
    MassivePoolStatsClient,
    MassiveResellerClient,
    MassiveResellerConfig,
    MassiveResellerError,
    generate_subaccount_password,
    reseller_status,
)
from openoutreach.proxies.models import (
    KIND_RESIDENTIAL,
    PROVIDER_MASSIVE_RESIDENTIAL,
    STATUS_ASSIGNED,
    STATUS_DISABLED,
    STATUS_ERROR,
    STATUS_RETIRED,
    Proxy,
    ProxyError,
    ProxyUnavailableError,
    create_proxy,
)
from openoutreach.proxies.region import normalize_region
from openoutreach.proxies.service import (
    assign_proxy_for_new_profile,
    assign_proxy_to_profile,
    retire_proxy,
    validate_proxy_host,
)

logger = logging.getLogger(__name__)

_PROXIES = "proxies"
_PROFILES = "linkedin_profiles"
_SNAPSHOTS = "massive_usage_snapshots"
_REPORTING_SNAPSHOTS = "proxy_usage_snapshots"

MASSIVE_STATUS_UNMANAGED = "unmanaged"
MASSIVE_STATUS_ACTIVE = "active"
MASSIVE_STATUS_DISABLED = "disabled"
MASSIVE_STATUS_BUDGET_DISABLED = "budget_disabled"
MASSIVE_STATUS_RETIRED = "retired"
MASSIVE_STATUS_ERROR = "error"

_USERNAME_RE = re.compile(r"[^A-Za-z0-9-]+")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_token(value: str, *, limit: int = 120) -> str:
    cleaned = _USERNAME_RE.sub("-", (value or "").strip()).strip("-")
    return cleaned[:limit]


def _collection(name: str):
    return get_mongodb_collection(name)


def _profile_collection(channel: str):
    return _collection("whatsapp_profiles" if channel == "whatsapp" else _PROFILES)


def _assign_proxy_to_channel(
    proxy_id: str,
    profile_id: str,
    user_id: str,
    channel: str,
    *,
    assigned_by: Optional[str] = None,
) -> Proxy:
    from openoutreach.proxies.service import (
        assign_proxy_to_profile,
        assign_proxy_to_whatsapp,
    )

    if channel == "whatsapp":
        return assign_proxy_to_whatsapp(
            proxy_id, profile_id, user_id, assigned_by=assigned_by
        )
    return assign_proxy_to_profile(
        proxy_id, profile_id, user_id, assigned_by=assigned_by
    )


def reseller_enabled() -> bool:
    return bool(getattr(settings, "MASSIVE_RESELLER_ENABLED", False))


def reseller_available() -> bool:
    return reseller_enabled() and MassiveResellerConfig.from_settings() is not None


_RESELLER_USERNAME_RE = re.compile(r"[^A-Za-z0-9.@]+")


def _reseller_username_token(value: str, *, limit: int) -> str:
    """Sanitize a token to the Reseller API's allowed username characters.

    The live Reseller API accepts only ``a-z A-Z 0-9 @ .`` in the account
    username. Underscores and hyphens are rejected, so replace any other
    character with a dot and collapse repeated dots.
    """
    cleaned = _RESELLER_USERNAME_RE.sub(".", (value or "").strip())
    cleaned = re.sub(r"\.{2,}", ".", cleaned).strip(".")
    return cleaned[:limit].strip(".")


def build_reseller_username(
    org_id: Optional[str], profile_id: str, channel: str = "linkedin"
) -> str:
    """Build the unique sub-username using only Reseller-allowed characters."""
    org_token = _reseller_username_token(org_id or "personal", limit=60)
    profile_token = _reseller_username_token(profile_id, limit=80)
    if not profile_token:
        raise ProxyError("A profile id is required for a Massive sub-account")
    channel_token = "wa" if channel == "whatsapp" else "li"
    username = f"outreach.{org_token}.{channel_token}.{profile_token}"
    if len(username) > 255:
        raise ProxyError("Massive sub-account username exceeds 255 characters")
    return username


def full_massive_username(parent_username: str, subuser: str) -> str:
    # The parent may legitimately contain underscores, dots, or @; only the
    # separator between parent and sub-account is significant. The sub-account
    # itself must keep the Reseller API's allowed characters.
    parent = re.sub(
        r"[^A-Za-z0-9_.@-]+", ".", (parent_username or "").strip()
    ).strip(".")[:120]
    sub = _reseller_username_token(subuser, limit=120)
    if not parent or not sub:
        raise ProxyError("Massive parent username and sub-account are required")
    return f"{parent}_{sub}"


def build_reseller_proxy_username(
    parent_username: str,
    subuser: str,
    country: str,
    subdivision: Optional[str] = None,
    city: Optional[str] = None,
    *,
    session_id: Optional[str] = None,
    session_ttl: int = 1440,
    session_mode: str = "flex",
    device_type: str = "common",
) -> str:
    """Build the full proxy auth username for a Reseller sub-account.

    The stable prefix remains ``<PARENT>_<SUB>``; region/session parameters are
    appended in the same format as the Phase 1 fallback username.
    """
    from urllib.parse import quote

    from openoutreach.proxies.region import normalize_region

    country_value, subdivision_value, city_value = normalize_region(
        country, subdivision, city
    )
    base = full_massive_username(parent_username, subuser)
    session_token = _safe_token(session_id or subuser, limit=120)
    parts = [base, f"-country-{country_value}"]
    if subdivision_value:
        parts.append(f"-subdivision-{subdivision_value}")
    if city_value:
        parts.append(f"-city-{quote(city_value, safe='')}")
    parts.append(f"-session-{session_token}")
    parts.append(f"-sessionttl-{max(1, min(int(session_ttl), 1440))}")
    parts.append(f"-sessionmode-{_safe_token(session_mode) or 'flex'}")
    parts.append(f"-type-{_safe_token(device_type) or 'common'}")
    username = "".join(parts)
    if len(username) > 255:
        raise ProxyError("Massive proxy username exceeds 255 characters")
    return username


def _account_username_candidates(proxy: Proxy) -> set[str]:
    values = {
        str(proxy.massive_subuser or "").strip().lower(),
        str(proxy.username or "").strip().lower(),
        str(proxy.massive_account_id or "").strip().lower(),
        str(proxy.linkedin_profile_id or "").strip().lower(),
        str(proxy.whatsapp_profile_id or "").strip().lower(),
    }
    parent = str(proxy.massive_parent_username or "").strip().lower()
    if parent and proxy.massive_subuser:
        values.add(f"{parent}_{proxy.massive_subuser}".lower())
    return {value for value in values if value}


def _match_account(proxy: Proxy, accounts: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    candidates = _account_username_candidates(proxy)
    account_id = str(proxy.massive_account_id or "").strip().lower()
    for account in accounts:
        if account_id and str(account.get("account_id") or "").lower() == account_id:
            return account
    for account in accounts:
        username = str(account.get("username") or "").strip().lower()
        if not username:
            continue
        if username in candidates:
            return account
        # Reporting/sub-account lists may omit the parent prefix.
        if "_" in username and username.split("_", 1)[1] in candidates:
            return account
    return None


def _apply_account_state(proxy: Proxy, account: dict[str, Any]) -> dict[str, Any]:
    """Copy normalized account state onto the proxy, mirroring legacy fields."""
    now = _now()
    updates: dict[str, Any] = {
        "massive_account_id": account.get("account_id") or proxy.massive_account_id,
        "massive_status": proxy.massive_status,
        "massive_last_sync_at": now,
        "massive_last_error": None,
    }
    if account.get("username"):
        subuser = str(account["username"])
        parent = str(proxy.massive_parent_username or "").strip()
        if parent and subuser.lower().startswith(f"{parent.lower()}_"):
            subuser = subuser[len(parent) + 1 :]
        updates["massive_subuser"] = subuser
    if account.get("limit_bytes") is not None:
        updates["massive_limit_bytes"] = int(account["limit_bytes"])
        updates["traffic_limit_bytes"] = int(account["limit_bytes"])
    if account.get("used_bytes") is not None:
        updates["massive_used_bytes"] = int(account["used_bytes"])
        updates["used_bytes"] = int(account["used_bytes"])
    if account.get("limit_reached") is not None:
        updates["massive_limit_reached"] = bool(account["limit_reached"])
        updates["limit_reached"] = bool(account["limit_reached"])
    if account.get("proxy_access") is not None:
        updates["massive_proxy_access"] = bool(account["proxy_access"])
    status = str(account.get("status") or "").lower()
    # Local lifecycle state wins over the provider's state. A seat-disabled,
    # budget-disabled, or retired sub-account must not be silently reactivated
    # by a usage sync just because the provider still reports it active.
    if proxy.massive_status in {
        MASSIVE_STATUS_DISABLED,
        MASSIVE_STATUS_BUDGET_DISABLED,
        MASSIVE_STATUS_RETIRED,
    }:
        pass
    elif status in {"disabled", "inactive", "suspended"}:
        updates["massive_status"] = MASSIVE_STATUS_DISABLED
    elif status in {"active", "enabled", "running"}:
        updates["massive_status"] = MASSIVE_STATUS_ACTIVE
    return updates


def _store_snapshot(proxy: Proxy, account: dict[str, Any]) -> None:
    collection = _collection(_SNAPSHOTS)
    if collection is None:
        return
    try:
        collection.insert_one(
            {
                "_id": f"{proxy._id}:{int(_now().timestamp())}",
                "proxy_id": proxy._id,
                "massive_account_id": account.get("account_id")
                or proxy.massive_account_id,
                "account_username": account.get("username") or proxy.massive_subuser,
                "org_id": proxy.assigned_org_id or proxy.last_assigned_org_id,
                "profile_id": proxy.linkedin_profile_id
                or proxy.last_assigned_profile_id
                or proxy.whatsapp_profile_id
                or proxy.last_assigned_whatsapp_profile_id,
                "channel": proxy.channel,
                "whatsapp_profile_id": proxy.whatsapp_profile_id
                or proxy.last_assigned_whatsapp_profile_id,
                "used_bytes": int(account.get("used_bytes") or 0),
                "limit_bytes": account.get("limit_bytes"),
                "limit_reached": bool(account.get("limit_reached")),
                "proxy_access": account.get("proxy_access"),
                "status": account.get("status"),
                "captured_at": _now(),
            }
        )
    except Exception as exc:  # pragma: no cover - snapshot is best effort
        logger.warning(
            "massive_usage_snapshot_failed proxy_id=%s exception_type=%s",
            proxy._id,
            type(exc).__name__,
        )


def _audit_proxy(
    event: str,
    proxy: Proxy,
    *,
    actor_user_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    org_id = proxy.assigned_org_id or proxy.last_assigned_org_id
    if not org_id:
        return
    record_org_audit(
        event,
        org_id=org_id,
        actor_user_id=actor_user_id,
        target_user_id=proxy.assigned_user_id or proxy.last_assigned_user_id,
        metadata={
            "proxy_id": proxy._id,
            "profile_id": proxy.linkedin_profile_id
            or proxy.last_assigned_profile_id,
            **(metadata or {}),
        },
    )


def provision_reseller_proxy(
    profile_id: str,
    user_id: str,
    org_id: Optional[str],
    country: str,
    subdivision: Optional[str] = None,
    city: Optional[str] = None,
    *,
    created_by: Optional[str] = None,
    channel: str = "linkedin",
) -> Proxy:
    """Create (or adopt) a Reseller sub-account, store its proxy, and assign it."""
    config = MassiveResellerConfig.from_settings()
    if config is None:
        raise MassiveResellerError("Massive Reseller is not configured")
    client = MassiveResellerClient(config)
    country_value, subdivision_value, city_value = normalize_region(
        country, subdivision, city
    )
    # Idempotency: a profile may already have a proxy (for example a retried
    # request). Never create a second sub-account or disable the active one.
    profiles_collection = _profile_collection(channel)
    if profiles_collection is not None:
        profile_doc = profiles_collection.find_one(
            {"_id": profile_id}, {"proxy_id": 1, "proxy_server": 1}
        )
        if profile_doc and (profile_doc.get("proxy_id") or profile_doc.get("proxy_server")):
            existing_proxy_id = profile_doc.get("proxy_id")
            existing_proxy = Proxy.get(existing_proxy_id) if existing_proxy_id else None
            if existing_proxy is not None:
                return existing_proxy
            raise ProxyError("This profile already has a proxy")
    subuser = build_reseller_username(org_id, profile_id, channel)
    password = generate_subaccount_password()
    limit_bytes = int(
        getattr(settings, "MASSIVE_RESELLER_DEFAULT_LIMIT_BYTES", 5_000_000_000)
        or 5_000_000_000
    )

    existing_password: Optional[str] = None
    try:
        account = client.create_account(
            subuser, password, limit_bytes, sync_with_parent=True
        )
    except MassiveResellerError as exc:
        if exc.code != "already_exists":
            raise
        existing = client.find_account_by_username(subuser, include_password=True)
        if not existing:
            raise MassiveResellerError(
                "Massive reports that the sub-account exists but it could not be loaded"
            )
        account = existing
        existing_password = str(existing.get("password") or "") or None
        if not existing_password:
            raise MassiveResellerError(
                "Existing Massive sub-account has no readable password; rotate it from the admin Massive tab"
            )

    account_id = account.get("account_id")
    if not account_id:
        raise MassiveResellerError("Massive did not return a sub-account id")
    proxy_password = existing_password or password

    proxies_collection = _collection(_PROXIES)
    if proxies_collection is not None:
        existing_doc = proxies_collection.find_one(
            {
                "$or": [
                    {"massive_account_id": str(account_id)},
                    {"massive_subuser": subuser},
                ]
            }
        )
        if existing_doc:
            existing_proxy = Proxy.from_dict(existing_doc)
            try:
                return _assign_proxy_to_channel(
                    existing_proxy._id,
                    profile_id,
                    user_id,
                    channel,
                    assigned_by=created_by,
                )
            except ProxyError:
                # Already assigned to this same profile is fine.
                if (
                    existing_proxy.linkedin_profile_id == profile_id
                    or existing_proxy.whatsapp_profile_id == profile_id
                ):
                    return existing_proxy
                raise

    host = str(getattr(settings, "MASSIVE_PROXY_HOST", None) or "network.joinmassive.com")
    port = int(getattr(settings, "MASSIVE_PROXY_PORT", None) or 65534)
    validate_proxy_host(host)
    proxy = create_proxy(
        host=host,
        port=port,
        username=build_reseller_proxy_username(
            config.parent_username,
            subuser,
            country_value,
            subdivision_value,
            city_value,
            session_id=profile_id,
        ),
        password=proxy_password,
        country=country_value,
        subdivision=subdivision_value,
        city=city_value,
        provider=PROVIDER_MASSIVE_RESIDENTIAL,
        kind=KIND_RESIDENTIAL,
        label=f"massive-{_safe_token(profile_id, limit=8)}",
        channel="whatsapp" if channel == "whatsapp" else "linkedin",
        massive_parent_username=config.parent_username,
        massive_subuser=subuser,
        massive_account_id=str(account_id),
        massive_status=MASSIVE_STATUS_ACTIVE,
        massive_limit_bytes=account.get("limit_bytes") or limit_bytes,
        massive_used_bytes=int(account.get("used_bytes") or 0),
        massive_limit_reached=bool(account.get("limit_reached")),
        massive_proxy_access=account.get("proxy_access"),
        massive_provisioned_at=_now(),
        created_by=created_by,
    )
    try:
        assigned = _assign_proxy_to_channel(
            proxy._id,
            profile_id,
            user_id,
            channel,
            assigned_by=created_by,
        )
    except ProxyError:
        # Do not leave a paid sub-account enabled for an unassigned proxy.
        try:
            client.disable_account(str(account_id))
        except MassiveResellerError:
            pass
        try:
            retire_proxy(proxy._id, reason="reseller_assignment_failed")
        except ProxyError:
            pass
        raise
    _audit_proxy(
        "proxy.provision",
        assigned,
        actor_user_id=created_by,
        metadata={"massive_account_id": str(account_id), "subuser": subuser},
    )
    logger.info(
        "massive_reseller_provisioned proxy_id=%s profile_id=%s account_id=%s",
        assigned._id,
        profile_id,
        account_id,
    )
    return assigned


def validate_city_pool(country: str, city: Optional[str]) -> None:
    """Block city-level targeting when Pool Stats reports too few nodes."""
    if not city:
        return
    client = pool_stats_client()
    if client is None:
        return
    try:
        safe = client.is_city_safe(country, city)
    except Exception as exc:  # pragma: no cover - stats outage must not block
        logger.warning(
            "pool_stats_city_check_failed country=%s exception_type=%s",
            country,
            type(exc).__name__,
        )
        return
    if not safe:
        raise ProxyError(
            f"City-level targeting for {city}, {country.upper()} has too few nodes; "
            "use country-level targeting instead."
        )


def provision_managed_proxy(
    profile_id: str,
    user_id: str,
    org_id: Optional[str],
    country: str,
    subdivision: Optional[str] = None,
    city: Optional[str] = None,
    *,
    created_by: Optional[str] = None,
    channel: str = "linkedin",
) -> Proxy:
    """Provision a managed proxy: Reseller first, Phase 1 fallback second."""
    validate_city_pool(country, city)
    if reseller_available():
        try:
            return provision_reseller_proxy(
                profile_id,
                user_id,
                org_id,
                country,
                subdivision,
                city,
                created_by=created_by,
                channel=channel,
            )
        except ProxyError as exc:
            logger.warning(
                "massive_reseller_provision_failed profile_id=%s channel=%s status=%s code=%s exception_type=%s",
                profile_id,
                channel,
                getattr(exc, "status_code", None),
                getattr(exc, "code", None),
                type(exc).__name__,
            )
    return assign_proxy_for_new_profile(
        profile_id,
        user_id,
        country,
        subdivision,
        city,
        channel=channel,
    )


def disable_massive_proxy(
    proxy: Proxy,
    *,
    reason: str = "seat_cancelled",
    actor_user_id: Optional[str] = None,
) -> bool:
    """Disable a sub-account while keeping it bound to the same profile."""
    if not proxy.massive_account_id:
        return False
    config = MassiveResellerConfig.from_settings()
    if config is None:
        return False
    try:
        MassiveResellerClient(config).disable_account(proxy.massive_account_id)
    except MassiveResellerError as exc:
        _mark_massive_error(proxy, exc)
        return False
    proxy.massive_status = MASSIVE_STATUS_DISABLED
    proxy.massive_last_error = None
    proxy.massive_last_sync_at = _now()
    proxy.save()
    _audit_proxy(
        "proxy.massive_disable",
        proxy,
        actor_user_id=actor_user_id,
        metadata={"reason": reason},
    )
    return True


def enable_massive_proxy(
    proxy: Proxy,
    *,
    actor_user_id: Optional[str] = None,
    reason: str = "seat_assigned",
) -> bool:
    """Re-enable a sub-account for the same LinkedIn profile only."""
    if not proxy.massive_account_id:
        return False
    config = MassiveResellerConfig.from_settings()
    if config is None:
        return False
    try:
        MassiveResellerClient(config).enable_account(proxy.massive_account_id)
    except MassiveResellerError as exc:
        _mark_massive_error(proxy, exc)
        return False
    proxy.massive_status = MASSIVE_STATUS_ACTIVE
    proxy.massive_last_error = None
    proxy.massive_last_sync_at = _now()
    proxy.massive_budget_disabled_at = None
    proxy.save()
    _audit_proxy(
        "proxy.massive_enable",
        proxy,
        actor_user_id=actor_user_id,
        metadata={"reason": reason},
    )
    return True


def _proxy_shared_with_cloud_whatsapp(proxy: Proxy) -> bool:
    """A Cloud Duo proxy must outlive a LinkedIn-only profile deletion."""
    if proxy.whatsapp_profile_id:
        return True
    collection = _collection("whatsapp_profiles")
    if collection is None:
        return False
    try:
        return (
            collection.find_one(
                {"proxy_id": proxy._id, "execution_mode": "cloud"},
                {"_id": 1},
            )
            is not None
        )
    except Exception:
        return False


def _proxy_shared_with_linkedin(proxy: Proxy) -> bool:
    """A shared Duo proxy must outlive a WhatsApp-only deletion."""
    if proxy.linkedin_profile_id:
        return True
    collection = _collection(_PROFILES)
    if collection is None:
        return False
    try:
        return (
            collection.find_one(
                {"proxy_id": proxy._id, "execution_mode": "cloud"},
                {"_id": 1},
            )
            is not None
        )
    except Exception:
        return False


def _proxy_for_profile(profile_id: str, channel: str = "linkedin") -> Optional[Proxy]:
    collection = _collection(_PROXIES)
    if collection is None:
        return None
    field = "whatsapp_profile_id" if channel == "whatsapp" else "linkedin_profile_id"
    doc = collection.find_one({field: profile_id})
    if doc:
        return Proxy.from_dict(doc)
    # A paused/unassigned profile keeps the proxy reservation through the
    # last-assigned field.
    last_field = (
        "last_assigned_whatsapp_profile_id"
        if channel == "whatsapp"
        else "last_assigned_profile_id"
    )
    doc = collection.find_one({last_field: profile_id})
    return Proxy.from_dict(doc) if doc else None


def disable_massive_for_profile(
    profile_id: str,
    *,
    actor_user_id: Optional[str] = None,
    reason: str = "seat_cancelled",
    channel: str = "linkedin",
) -> bool:
    """Best-effort seat cancellation hook. Never raises to the caller."""
    try:
        proxy = _proxy_for_profile(profile_id, channel)
        if proxy is None or proxy.massive_status == MASSIVE_STATUS_RETIRED:
            return False
        if channel == "whatsapp" and proxy.linkedin_profile_id:
            # A shared-IP Duo uses the LinkedIn sub-account. Pausing the
            # WhatsApp channel alone must not disable the LinkedIn proxy.
            return False
        return disable_massive_proxy(
            proxy, reason=reason, actor_user_id=actor_user_id
        )
    except Exception as exc:  # pragma: no cover - lifecycle must not block pause
        logger.warning(
            "massive_disable_for_profile_failed profile_id=%s channel=%s exception_type=%s",
            profile_id,
            channel,
            type(exc).__name__,
        )
        return False


def enable_massive_for_profile(
    profile_id: str,
    *,
    actor_user_id: Optional[str] = None,
    reason: str = "seat_assigned",
    channel: str = "linkedin",
) -> bool:
    """Re-enable only a seat-disabled sub-account for the same profile."""
    try:
        proxy = _proxy_for_profile(profile_id, channel)
        if proxy is None or proxy.massive_status != MASSIVE_STATUS_DISABLED:
            return False
        if channel == "whatsapp" and proxy.linkedin_profile_id:
            # Shared-IP Duo lifecycle follows the LinkedIn seat.
            return False
        return enable_massive_proxy(
            proxy, actor_user_id=actor_user_id, reason=reason
        )
    except Exception as exc:  # pragma: no cover
        logger.warning(
            "massive_enable_for_profile_failed profile_id=%s channel=%s exception_type=%s",
            profile_id,
            channel,
            type(exc).__name__,
        )
        return False


def retire_massive_for_profile(
    profile_id: str,
    *,
    actor_user_id: Optional[str] = None,
    channel: str = "linkedin",
) -> bool:
    try:
        proxy = _proxy_for_profile(profile_id, channel)
        if proxy is None:
            return False
        if channel == "whatsapp" and _proxy_shared_with_linkedin(proxy):
            logger.warning(
                "Skipping Massive retirement for proxy %s; shared with a LinkedIn profile",
                proxy._id,
            )
            return False
        if channel != "whatsapp" and _proxy_shared_with_cloud_whatsapp(proxy):
            logger.warning(
                "Skipping Massive retirement for proxy %s; shared with a cloud WhatsApp profile",
                proxy._id,
            )
            return False
        return retire_massive_proxy(proxy, actor_user_id=actor_user_id)
    except Exception as exc:  # pragma: no cover
        logger.warning(
            "massive_retire_for_profile_failed profile_id=%s channel=%s exception_type=%s",
            profile_id,
            channel,
            type(exc).__name__,
        )
        return False


def retire_massive_proxy(proxy: Proxy, *, actor_user_id: Optional[str] = None) -> bool:
    """Retire a sub-account by disabling it. Never delete or reuse it."""
    if not proxy.massive_account_id:
        return False
    config = MassiveResellerConfig.from_settings()
    if config is not None:
        try:
            MassiveResellerClient(config).disable_account(proxy.massive_account_id)
        except MassiveResellerError as exc:
            # Keep the error visible so the admin alert and a later retry can
            # find the still-billable sub-account. Do not report success.
            _mark_massive_error(proxy, exc)
            return False
    proxy.massive_status = MASSIVE_STATUS_RETIRED
    proxy.massive_last_error = None
    proxy.save()
    _audit_proxy(
        "proxy.massive_retire",
        proxy,
        actor_user_id=actor_user_id,
        metadata={"reason": "profile_deleted"},
    )
    return True


def rotate_massive_password(
    proxy: Proxy, *, actor_user_id: Optional[str] = None
) -> Proxy:
    """Rotate the sub-account password and update the local proxy/profile."""
    if not proxy.massive_account_id:
        raise MassiveResellerError("This proxy is not a Reseller sub-account")
    config = MassiveResellerConfig.from_settings()
    if config is None:
        raise MassiveResellerError("Massive Reseller is not configured")
    password = generate_subaccount_password()
    MassiveResellerClient(config).update_account(
        proxy.massive_account_id, password=password
    )
    encrypted = safe_encrypt(password)
    if not encrypted:
        raise MassiveResellerError("Failed to encrypt the new sub-account password")
    proxy.password_encrypted = encrypted
    proxy.massive_status = MASSIVE_STATUS_ACTIVE
    proxy.massive_last_error = None
    proxy.massive_last_sync_at = _now()
    proxy.save()
    if proxy.linkedin_profile_id:
        profiles = _collection(_PROFILES)
        if profiles is not None:
            profiles.update_one(
                {"_id": proxy.linkedin_profile_id, "proxy_id": proxy._id},
                {"$set": {"proxy_password_encrypted": encrypted, "updated_at": _now()}},
            )
    if proxy.whatsapp_profile_id:
        # The WhatsApp browser reads the password from the proxy record, so
        # there is no separate profile copy to update.
        logger.info(
            "massive_rotate_whatsapp_proxy proxy_id=%s profile_id=%s",
            proxy._id,
            proxy.whatsapp_profile_id,
        )
    _audit_proxy(
        "proxy.massive_rotate",
        proxy,
        actor_user_id=actor_user_id,
        metadata={"massive_account_id": proxy.massive_account_id},
    )
    return proxy


def _mark_massive_error(proxy: Proxy, exc: MassiveResellerError) -> None:
    proxy.massive_status = MASSIVE_STATUS_ERROR
    proxy.massive_last_error = str(exc)[:300]
    proxy.massive_last_sync_at = _now()
    try:
        proxy.save()
    except Exception:  # pragma: no cover - error state must not raise
        pass


def _month_start(value: Optional[datetime] = None) -> datetime:
    moment = value or _now()
    return moment.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _parse_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def sync_massive_accounts(
    *, actor_user_id: Optional[str] = None, apply_budgets: bool = True
) -> dict[str, Any]:
    """Daily cumulative usage sync from ``GET /resellers/accounts``.

    ``apply_budgets=False`` updates usage fields and snapshots but only
    previews the internal budget actions. It never disables or re-enables a
    provider sub-account, which makes a production threshold review safe.
    """
    config = MassiveResellerConfig.from_settings()
    if config is None:
        raise MassiveResellerError("Massive Reseller is not configured")
    client = MassiveResellerClient(config)
    accounts = client.list_accounts()
    proxies_collection = _collection(_PROXIES)
    if proxies_collection is None:
        raise MassiveResellerError("Proxy storage is unavailable")

    matched = 0
    unmatched = 0
    updated = 0
    for account in accounts:
        matched_proxy: Optional[Proxy] = None
        account_id = str(account.get("account_id") or "").strip()
        if account_id:
            doc = proxies_collection.find_one({"massive_account_id": account_id})
            if doc:
                matched_proxy = Proxy.from_dict(doc)
        if matched_proxy is None:
            for doc in proxies_collection.find({"massive_account_id": {"$ne": None}}):
                candidate = Proxy.from_dict(doc)
                if _match_account(candidate, [account]):
                    matched_proxy = candidate
                    break
        if matched_proxy is None:
            unmatched += 1
            continue
        matched += 1
        updates = _apply_account_state(matched_proxy, account)
        proxies_collection.update_one({"_id": matched_proxy._id}, {"$set": updates})
        _store_snapshot(matched_proxy, account)
        updated += 1
        if updates.get("massive_limit_reached") or updates.get("massive_proxy_access") is False:
            refreshed = Proxy.from_dict(
                proxies_collection.find_one({"_id": matched_proxy._id}) or {}
            )
            _audit_proxy(
                "proxy.massive_alert",
                refreshed,
                actor_user_id=actor_user_id,
                metadata={
                    "limit_reached": bool(updates.get("massive_limit_reached")),
                    "proxy_access": updates.get("massive_proxy_access"),
                },
            )

    if apply_budgets:
        budget = enforce_massive_budgets(actor_user_id=actor_user_id)
    else:
        budget = preview_massive_budgets()
    parent = client.parent_usage()
    logger.info(
        "massive_reseller_sync accounts=%s matched=%s updated=%s unmatched=%s",
        len(accounts),
        matched,
        updated,
        unmatched,
    )
    return {
        "accounts": len(accounts),
        "matched": matched,
        "updated": updated,
        "unmatched": unmatched,
        "parent": parent,
        "budget": budget,
    }


def sync_massive_reporting(
    from_date: str, to_date: str, *, actor_user_id: Optional[str] = None
) -> dict[str, Any]:
    """Reporting sync: ``group_by=subaccount`` with ``subuser`` fallback."""
    config = MassiveResellerConfig.from_settings()
    if config is None:
        raise MassiveResellerError("Massive Reseller is not configured")
    client = MassiveResellerClient(config)
    rows: list[dict[str, Any]] = []
    group_by = "subaccount"
    try:
        rows = client.reporting_usage(
            group_by="subaccount", from_date=from_date, to_date=to_date
        )
    except MassiveResellerError:
        rows = []
    if not rows:
        group_by = "subuser"
        rows = client.reporting_usage(
            group_by="subuser", from_date=from_date, to_date=to_date
        )
    proxies_collection = _collection(_PROXIES)
    if proxies_collection is None:
        raise MassiveResellerError("Proxy storage is unavailable")
    all_proxies = [
        Proxy.from_dict(doc)
        for doc in proxies_collection.find(
            {
                "$or": [
                    {"massive_account_id": {"$ne": None}},
                    {"massive_subuser": {"$ne": None}},
                ]
            }
        )
    ]
    matched = 0
    skipped = 0
    total_bytes = 0
    for row in rows:
        label = str(row.get("subaccount") or "").strip()
        label_base = label.split("-country-", 1)[0].split("-session-", 1)[0]
        proxy = next(
            (
                candidate
                for candidate in all_proxies
                if label.lower() in _account_username_candidates(candidate)
                or label_base.lower() in _account_username_candidates(candidate)
                or label.lower().split("_")[-1]
                in _account_username_candidates(candidate)
            ),
            None,
        )
        if proxy is None:
            skipped += 1
            continue
        from openoutreach.proxies.service import record_usage_snapshot

        record_usage_snapshot(
            proxy=proxy,
            subuser=label or (proxy.massive_subuser or proxy._id),
            bytes_used=int(row.get("bytes") or 0),
            period_start=str(row.get("period_start") or from_date),
            period_end=str(row.get("period_end") or to_date),
            channel=proxy.channel or "linkedin",
        )
        matched += 1
        total_bytes += int(row.get("bytes") or 0)
    logger.info(
        "massive_reporting_sync group_by=%s matched=%s skipped=%s",
        group_by,
        matched,
        skipped,
    )
    return {
        "group_by": group_by,
        "matched": matched,
        "skipped": skipped,
        "total_bytes": total_bytes,
        "period_start": from_date,
        "period_end": to_date,
    }


def _monthly_usage_by_proxy() -> dict[str, int]:
    collection = _collection(_REPORTING_SNAPSHOTS)
    if collection is None:
        return {}
    start = _month_start()
    usage: dict[str, int] = {}
    try:
        docs = collection.find({"period_start": {"$gte": start.isoformat()}})
    except Exception:
        return {}
    for doc in docs:
        proxy_id = str(doc.get("proxy_id") or "")
        if not proxy_id:
            continue
        usage[proxy_id] = usage.get(proxy_id, 0) + int(doc.get("bytes") or 0)
    return usage


def _budget_decision(
    proxy: Proxy,
    used_bytes: int,
    *,
    soft_limit_bytes: int,
    hard_limit_bytes: int,
    month_start: datetime,
) -> Optional[str]:
    """Return the internal budget action for one proxy, if any."""
    if used_bytes >= hard_limit_bytes and proxy.massive_status == MASSIVE_STATUS_ACTIVE:
        return "disable"
    if soft_limit_bytes <= used_bytes < hard_limit_bytes:
        return "soft_alert"
    if (
        proxy.massive_status == MASSIVE_STATUS_BUDGET_DISABLED
        and proxy.massive_budget_disabled_at is not None
    ):
        disabled_at = _parse_datetime(proxy.massive_budget_disabled_at)
        if (
            disabled_at is not None
            and disabled_at < month_start
            and used_bytes < soft_limit_bytes
        ):
            return "re_enable"
    return None


def preview_massive_budgets() -> dict[str, Any]:
    """Report internal budget actions without changing provider state.

    Uses the same monthly Reporting snapshots and thresholds as
    :func:`enforce_massive_budgets`, but never disables, re-enables, or audits.
    This is the safe production review path for soft/hard thresholds.
    """
    collection = _collection(_PROXIES)
    soft = int(getattr(settings, "MASSIVE_MONTHLY_SOFT_LIMIT_BYTES", 25_000_000_000))
    hard = int(getattr(settings, "MASSIVE_MONTHLY_HARD_LIMIT_BYTES", 40_000_000_000))
    month_start = _month_start()
    result: dict[str, Any] = {
        "mode": "dry_run",
        "soft_limit_bytes": soft,
        "hard_limit_bytes": hard,
        "month_start": month_start.isoformat(),
        "proxies": 0,
        "counts": {"disable": 0, "soft_alert": 0, "re_enable": 0, "none": 0},
        "actions": [],
    }
    if collection is None:
        return result
    usage = _monthly_usage_by_proxy()
    for doc in collection.find({"massive_account_id": {"$ne": None}}):
        proxy = Proxy.from_dict(doc)
        used = usage.get(proxy._id, 0)
        action = _budget_decision(
            proxy,
            used,
            soft_limit_bytes=soft,
            hard_limit_bytes=hard,
            month_start=month_start,
        )
        result["proxies"] += 1
        result["counts"][action or "none"] += 1
        if action:
            result["actions"].append(
                {
                    "proxy_id": proxy._id,
                    "profile_id": proxy.linkedin_profile_id
                    or proxy.last_assigned_profile_id,
                    "org_id": proxy.assigned_org_id or proxy.last_assigned_org_id,
                    "massive_status": proxy.massive_status,
                    "used_bytes": used,
                    "soft_limit_bytes": soft,
                    "hard_limit_bytes": hard,
                    "action": action,
                }
            )
    return result


def enforce_massive_budgets(*, actor_user_id: Optional[str] = None) -> dict[str, int]:
    """Apply internal monthly soft/hard thresholds. No customer-facing meter."""
    collection = _collection(_PROXIES)
    if collection is None:
        return {"disabled": 0, "re_enabled": 0, "soft_alerts": 0}
    soft = int(getattr(settings, "MASSIVE_MONTHLY_SOFT_LIMIT_BYTES", 25_000_000_000))
    hard = int(getattr(settings, "MASSIVE_MONTHLY_HARD_LIMIT_BYTES", 40_000_000_000))
    usage = _monthly_usage_by_proxy()
    month_start = _month_start()
    disabled = 0
    re_enabled = 0
    soft_alerts = 0
    for doc in collection.find({"massive_account_id": {"$ne": None}}):
        proxy = Proxy.from_dict(doc)
        used = usage.get(proxy._id, 0)
        action = _budget_decision(
            proxy,
            used,
            soft_limit_bytes=soft,
            hard_limit_bytes=hard,
            month_start=month_start,
        )
        if action == "disable":
            if disable_massive_proxy(
                proxy, reason="budget_hard_limit", actor_user_id=actor_user_id
            ):
                proxy.massive_status = MASSIVE_STATUS_BUDGET_DISABLED
                proxy.massive_budget_disabled_at = _now()
                proxy.save()
                _audit_proxy(
                    "proxy.budget_disable",
                    proxy,
                    actor_user_id=actor_user_id,
                    metadata={"used_bytes": used, "hard_limit_bytes": hard},
                )
                disabled += 1
        elif action == "soft_alert":
            _audit_proxy(
                "proxy.budget_soft",
                proxy,
                actor_user_id=actor_user_id,
                metadata={"used_bytes": used, "soft_limit_bytes": soft},
            )
            soft_alerts += 1
        elif action == "re_enable":
            if enable_massive_proxy(
                proxy, actor_user_id=actor_user_id, reason="budget_new_month"
            ):
                _audit_proxy(
                    "proxy.budget_enable",
                    proxy,
                    actor_user_id=actor_user_id,
                    metadata={"used_bytes": used},
                )
                re_enabled += 1
    return {
        "disabled": disabled,
        "re_enabled": re_enabled,
        "soft_alerts": soft_alerts,
    }


def massive_alerts() -> list[dict[str, Any]]:
    """Internal alerts for limit, proxy access, country mismatch, and errors."""
    collection = _collection(_PROXIES)
    if collection is None:
        return []
    alerts: list[dict[str, Any]] = []
    for doc in collection.find(
        {
            "$or": [
                {"massive_account_id": {"$ne": None}},
                {"channel": {"$in": ["whatsapp", "duo"]}},
            ]
        }
    ):
        proxy = Proxy.from_dict(doc)
        reasons: list[str] = []
        if proxy.massive_limit_reached:
            reasons.append("limit_reached")
        if proxy.massive_proxy_access is False:
            reasons.append("proxy_access_revoked")
        if proxy.country_mismatch:
            reasons.append("country_mismatch")
        if proxy.massive_status == MASSIVE_STATUS_ERROR:
            reasons.append("repeated_failures")
        if proxy.massive_status == MASSIVE_STATUS_BUDGET_DISABLED:
            reasons.append("budget_disabled")
        if proxy.status in {STATUS_DISABLED, STATUS_ERROR}:
            reasons.append("proxy_disabled")
        if proxy.last_error:
            reasons.append("proxy_error")
        if (
            proxy.whatsapp_profile_id
            and proxy.massive_status
            in {MASSIVE_STATUS_DISABLED, MASSIVE_STATUS_ERROR}
        ):
            reasons.append("whatsapp_proxy_unavailable")
        if reasons:
            alerts.append(
                {
                    "proxy_id": proxy._id,
                    "profile_id": proxy.linkedin_profile_id,
                    "whatsapp_profile_id": proxy.whatsapp_profile_id,
                    "channel": proxy.channel,
                    "org_id": proxy.assigned_org_id,
                    "massive_account_id": proxy.massive_account_id,
                    "massive_subuser": proxy.massive_subuser,
                    "status": proxy.massive_status,
                    "reasons": reasons,
                    "last_error": proxy.massive_last_error,
                }
            )
    return alerts


def list_massive_subaccounts() -> list[dict[str, Any]]:
    """Admin table rows. Passwords and keys are never included."""
    proxies_collection = _collection(_PROXIES)
    if proxies_collection is None:
        return []
    profiles_collection = _collection(_PROFILES)
    whatsapp_collection = _collection("whatsapp_profiles")
    rows: list[dict[str, Any]] = []
    for doc in proxies_collection.find({"massive_account_id": {"$ne": None}}):
        proxy = Proxy.from_dict(doc)
        profile = None
        whatsapp_profile = None
        if profiles_collection is not None and proxy.linkedin_profile_id:
            profile = profiles_collection.find_one(
                {"_id": proxy.linkedin_profile_id},
                {"linkedin_username": 1, "execution_mode": 1, "assigned_user_id": 1},
            )
        if whatsapp_collection is not None and proxy.whatsapp_profile_id:
            whatsapp_profile = whatsapp_collection.find_one(
                {"_id": proxy.whatsapp_profile_id},
                {"phone_number": 1, "display_name": 1, "execution_mode": 1, "assigned_user_id": 1},
            )
        rows.append(
            {
                "proxy_id": proxy._id,
                "massive_account_id": proxy.massive_account_id,
                "massive_subuser": proxy.massive_subuser,
                "massive_status": proxy.massive_status,
                "channel": proxy.channel,
                "profile_id": proxy.linkedin_profile_id,
                "linkedin_username": (profile or {}).get("linkedin_username"),
                "whatsapp_profile_id": proxy.whatsapp_profile_id,
                "whatsapp_number": (whatsapp_profile or {}).get("phone_number")
                or (whatsapp_profile or {}).get("display_name"),
                "org_id": proxy.assigned_org_id,
                "assigned_user_id": proxy.assigned_user_id,
                "used_bytes": proxy.massive_used_bytes or proxy.used_bytes,
                "limit_bytes": proxy.massive_limit_bytes
                or proxy.traffic_limit_bytes,
                "limit_reached": proxy.massive_limit_reached
                or proxy.limit_reached,
                "proxy_access": proxy.massive_proxy_access,
                "country": proxy.country,
                "last_sync_at": proxy.massive_last_sync_at.isoformat()
                if proxy.massive_last_sync_at
                else None,
                "last_error": proxy.massive_last_error,
            }
        )
    return rows


def pool_stats_client() -> Optional[MassivePoolStatsClient]:
    try:
        return MassivePoolStatsClient()
    except MassiveResellerError:
        return None


def pool_stats_summary(country: Optional[str] = None) -> dict[str, Any]:
    client = pool_stats_client()
    if client is None:
        return {
            "configured": False,
            "warnings": [],
            "country_counts": {},
        }
    try:
        counts = client.country_counts()
    except MassiveResellerError as exc:
        logger.warning(
            "pool_stats_country_counts_failed exception_type=%s", type(exc).__name__
        )
        counts = {}
    try:
        warnings = client.warnings(country) if country else []
    except MassiveResellerError as exc:
        logger.warning(
            "pool_stats_warnings_failed exception_type=%s", type(exc).__name__
        )
        warnings = []
    return {
        "configured": True,
        "warnings": warnings,
        "country_counts": counts,
        "min_nodes": client.config.min_nodes,
    }


def massive_admin_status() -> dict[str, Any]:
    from openoutreach.proxies.massive_client import massive_status

    base = massive_status()
    from openoutreach.billing.cloud_seats import cloud_seat_alerts

    try:
        seat_alerts = cloud_seat_alerts()
    except Exception as exc:  # pragma: no cover - admin status must not fail
        logger.warning(
            "cloud_seat_alerts_failed exception_type=%s", type(exc).__name__
        )
        seat_alerts = []
    return {
        **base,
        "reseller": reseller_status(),
        "pool_stats": {
            "enabled": bool(getattr(settings, "MASSIVE_POOL_STATS_ENABLED", False)),
        },
        "alerts": massive_alerts(),
        "seat_alerts": seat_alerts,
    }


__all__ = [
    "MASSIVE_STATUS_ACTIVE",
    "MASSIVE_STATUS_BUDGET_DISABLED",
    "MASSIVE_STATUS_DISABLED",
    "MASSIVE_STATUS_ERROR",
    "MASSIVE_STATUS_RETIRED",
    "build_reseller_proxy_username",
    "build_reseller_username",
    "disable_massive_for_profile",
    "disable_massive_proxy",
    "enable_massive_for_profile",
    "enable_massive_proxy",
    "enforce_massive_budgets",
    "full_massive_username",
    "list_massive_subaccounts",
    "massive_admin_status",
    "massive_alerts",
    "pool_stats_summary",
    "preview_massive_budgets",
    "provision_managed_proxy",
    "provision_reseller_proxy",
    "reseller_available",
    "reseller_enabled",
    "retire_massive_for_profile",
    "retire_massive_proxy",
    "rotate_massive_password",
    "sync_massive_accounts",
    "sync_massive_reporting",
    "validate_city_pool",
]
