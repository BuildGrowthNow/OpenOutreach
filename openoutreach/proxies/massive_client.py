"""Massive fallback proxy credentials and Reporting API usage sync.

Phase 1 uses the parent Massive credentials with a per-profile
``-subaccount-<profile_id>`` suffix. It deliberately does not call the
Reseller API (Phase 2). Keys and passwords stay server-side: they are never
logged and never returned by an API response.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import quote

import httpx

from openoutreach.config import settings
from openoutreach.proxies.models import (
    KIND_RESIDENTIAL,
    PROVIDER_MASSIVE_RESIDENTIAL,
    Proxy,
    ProxyError,
    create_proxy,
)
from openoutreach.proxies.region import normalize_region
from openoutreach.proxies.service import _proxy_for_subuser, record_usage_snapshot

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[^A-Za-z0-9_-]+")
_PARENT_TOKEN_RE = re.compile(r"[^A-Za-z0-9_.@-]+")


def _setting(name: str) -> Any:
    return getattr(settings, name, None)


def _safe_token(value: str, *, limit: int = 120) -> str:
    cleaned = _TOKEN_RE.sub("-", (value or "").strip()).strip("-")
    return cleaned[:limit]


def _safe_parent_token(value: str, *, limit: int = 120) -> str:
    """Keep the parent's email-style characters in the proxy username."""
    cleaned = _PARENT_TOKEN_RE.sub("-", (value or "").strip()).strip("-")
    return cleaned[:limit]


@dataclass(frozen=True)
class MassiveConfig:
    """Server-side Massive fallback configuration."""

    parent_username: str = field(repr=False)
    proxy_password: str = field(repr=False)
    host: str
    port: int
    reporting_base_url: str
    reporting_enabled: bool
    reporting_api_key: Optional[str] = field(default=None, repr=False)

    @classmethod
    def from_settings(cls) -> Optional["MassiveConfig"]:
        parent = str(_setting("MASSIVE_PARENT_USERNAME") or "").strip()
        password = str(_setting("MASSIVE_PROXY_PASSWORD") or "").strip()
        if not parent or not password:
            return None
        reporting_key = (
            str(_setting("MASSIVE_REPORTING_API_KEY") or "").strip() or password
        )
        return cls(
            parent_username=parent,
            proxy_password=password,
            host=str(_setting("MASSIVE_PROXY_HOST") or "network.joinmassive.com").strip(),
            port=int(_setting("MASSIVE_PROXY_PORT") or 65534),
            reporting_api_key=reporting_key,
            reporting_base_url=str(
                _setting("MASSIVE_REPORTING_BASE_URL")
                or "https://api-network.joinmassive.com/reporting"
            ).strip(),
            reporting_enabled=bool(_setting("MASSIVE_REPORTING_ENABLED")),
        )

    @property
    def reporting_ready(self) -> bool:
        return bool(
            self.reporting_enabled
            and self.reporting_api_key
            and self.reporting_base_url
        )


def massive_status() -> dict[str, Any]:
    """Return configuration presence only. Never return a key or password."""
    parent = bool(str(_setting("MASSIVE_PARENT_USERNAME") or "").strip())
    password = bool(str(_setting("MASSIVE_PROXY_PASSWORD") or "").strip())
    reporting_key = bool(
        str(_setting("MASSIVE_REPORTING_API_KEY") or "").strip() or password
    )
    config = MassiveConfig.from_settings()
    return {
        "configured": config is not None,
        "parent_username_set": parent,
        "proxy_password_set": password,
        "reporting_enabled": bool(_setting("MASSIVE_REPORTING_ENABLED")),
        "reporting_key_set": reporting_key,
        "reporting_configured": bool(config and config.reporting_ready),
        "host": str(_setting("MASSIVE_PROXY_HOST") or "network.joinmassive.com"),
        "port": int(_setting("MASSIVE_PROXY_PORT") or 65534),
    }


def build_massive_subuser(profile_id: str, channel: Optional[str] = None) -> str:
    """Return the per-profile subuser label used by the Reporting API.

    ``channel`` adds the Phase 4 ``li``/``wa`` token so separate-IP Duo
    channels get distinct sub-accounts and Reporting rows. Omitting it keeps
    the pre-Phase-4 label for existing proxies and tests.
    """
    token = _safe_token(profile_id)
    if not token:
        raise ProxyError("A profile id is required for a Massive sub-account")
    if channel in {"linkedin", "whatsapp"}:
        prefix = "li" if channel == "linkedin" else "wa"
        return f"subaccount-{prefix}-{token}"
    return f"subaccount-{token}"


def build_massive_username(
    parent_username: str,
    profile_id: str,
    country: str,
    subdivision: Optional[str] = None,
    city: Optional[str] = None,
    *,
    session_id: Optional[str] = None,
    session_ttl: int = 1440,
    session_mode: str = "flex",
    device_type: str = "common",
    channel: Optional[str] = None,
) -> str:
    """Build the fallback proxy username with region and session parameters.

    Format::

        <PARENT>-subaccount-<channel>-<profile>-country-US-session-<profile>
        -sessionttl-1440-sessionmode-flex-type-common

    ``channel`` is ``li`` or ``wa`` for Phase 4 accounts. Omitting it keeps the
    legacy pre-Phase-4 username for existing records.
    """
    parent = _safe_parent_token(parent_username, limit=120)
    token = _safe_token(profile_id)
    if not parent or not token:
        raise ProxyError("Massive parent username and profile id are required")
    country_value, subdivision_value, city_value = normalize_region(
        country, subdivision, city
    )
    session_token = _safe_token(session_id or profile_id)
    if channel in {"linkedin", "whatsapp"}:
        channel_token = "li" if channel == "linkedin" else "wa"
        subaccount = f"subaccount-{channel_token}-{token}"
    else:
        subaccount = f"subaccount-{token}"
    parts = [
        f"{parent}-{subaccount}",
        f"-country-{country_value}",
    ]
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


def provision_massive_fallback(
    profile_id: str,
    country: str,
    subdivision: Optional[str] = None,
    city: Optional[str] = None,
    *,
    created_by: Optional[str] = None,
    channel: Optional[str] = None,
) -> Proxy:
    """Create a proxy record that uses the Massive parent fallback credentials."""
    config = MassiveConfig.from_settings()
    if config is None:
        raise ProxyError("Massive fallback is not configured")
    country_value, subdivision_value, city_value = normalize_region(
        country, subdivision, city
    )
    username = build_massive_username(
        config.parent_username,
        profile_id,
        country_value,
        subdivision_value,
        city_value,
        channel=channel,
    )
    label = f"massive-{_safe_token(profile_id, limit=8)}"
    return create_proxy(
        host=config.host,
        port=config.port,
        username=username,
        password=config.proxy_password,
        country=country_value,
        subdivision=subdivision_value,
        city=city_value,
        provider=PROVIDER_MASSIVE_RESIDENTIAL,
        kind=KIND_RESIDENTIAL,
        label=label,
        channel=channel if channel in {"linkedin", "whatsapp"} else "linkedin",
        massive_parent_username=config.parent_username,
        massive_subuser=build_massive_subuser(profile_id, channel),
        created_by=created_by,
    )


def _first_value(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
    return None


def _usage_bytes(row: dict[str, Any]) -> Optional[int]:
    raw = _first_value(
        row,
        (
            "bytes",
            "total_bytes",
            "usage_bytes",
            "traffic_bytes",
            "used_bytes",
        ),
    )
    unit = str(_first_value(row, ("unit", "units")) or "").strip().lower()
    if raw is None:
        usage = row.get("usage")
        if usage is not None and unit in {"byte", "bytes", "b"}:
            raw = usage
        elif usage is not None and unit in {"gb", "gigabyte", "gigabytes"}:
            try:
                return max(0, int(float(usage) * 1_000_000_000))
            except (TypeError, ValueError):
                return None
    if raw is not None:
        try:
            return max(0, int(float(raw)))
        except (TypeError, ValueError):
            return None
    gb = _first_value(row, ("usage_gb", "gb", "gigabytes"))
    if gb is not None:
        try:
            return max(0, int(float(gb) * 1_000_000_000))
        except (TypeError, ValueError):
            return None
    return None


async def fetch_massive_usage(
    from_date: str,
    to_date: str,
) -> list[dict[str, Any]]:
    """Fetch per-subuser usage from the Massive Reporting API.

    The response body is never logged. Only normalized rows leave this
    function.
    """
    config = MassiveConfig.from_settings()
    if config is None or not config.reporting_ready:
        raise ProxyError("Massive reporting is not configured")
    url = f"{config.reporting_base_url.rstrip('/')}/v1/usage"
    params = {
        "group_by": "subuser",
        "from": from_date,
        "to": to_date,
    }
    headers = {"x-api-key": config.reporting_api_key or ""}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params, headers=headers)
    except httpx.TimeoutException:
        raise ProxyError("Massive reporting request timed out")
    except httpx.HTTPError:
        raise ProxyError("Massive reporting request failed")
    if response.status_code != 200:
        raise ProxyError(
            f"Massive reporting request failed (HTTP {response.status_code})"
        )
    try:
        payload = response.json()
    except ValueError:
        raise ProxyError("Massive reporting returned an invalid response")

    rows: Any = payload
    if isinstance(payload, dict):
        for key in ("data", "results", "usage", "items"):
            if isinstance(payload.get(key), list):
                rows = payload[key]
                break
    if not isinstance(rows, list):
        return []

    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        subuser = _first_value(
            row,
            ("subuser", "sub_user", "subaccount", "sub_account", "username", "label"),
        )
        bytes_used = _usage_bytes(row)
        if not subuser or bytes_used is None:
            continue
        normalized.append({
            "subuser": str(subuser),
            "bytes": bytes_used,
            "period_start": str(
                _first_value(row, ("from", "period_start", "start")) or from_date
            ),
            "period_end": str(
                _first_value(row, ("to", "period_end", "end")) or to_date
            ),
        })
    return normalized


async def sync_massive_usage(
    from_date: str,
    to_date: str,
) -> dict[str, Any]:
    """Fetch Massive usage and store one snapshot per matched proxy."""
    rows = await fetch_massive_usage(from_date, to_date)
    matched = 0
    skipped = 0
    total_bytes = 0
    for row in rows:
        proxy = _proxy_for_subuser(row["subuser"])
        if proxy is None:
            skipped += 1
            continue
        record_usage_snapshot(
            proxy=proxy,
            subuser=row["subuser"],
            bytes_used=row["bytes"],
            period_start=row["period_start"],
            period_end=row["period_end"],
            channel=proxy.channel or "linkedin",
        )
        matched += 1
        total_bytes += row["bytes"]
    logger.info(
        "massive_usage_sync matched=%s skipped=%s total_bytes=%s",
        matched,
        skipped,
        total_bytes,
    )
    return {
        "matched": matched,
        "skipped": skipped,
        "total_bytes": total_bytes,
        "period_start": from_date,
        "period_end": to_date,
    }


def default_usage_period() -> tuple[str, str]:
    """Return yesterday through today in UTC, suitable for a daily sync."""
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)
    return yesterday.date().isoformat(), today.date().isoformat()
