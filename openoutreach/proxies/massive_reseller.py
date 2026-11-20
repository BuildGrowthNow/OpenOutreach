"""Massive Reseller and Pool Stats clients (Phase 2).

All calls are server-side. The Reseller API returns sub-account passwords, so
response bodies are never logged and public helpers strip secret fields. Keys
are read from settings and are never returned by an API response or audit
metadata.
"""
from __future__ import annotations

import logging
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from openoutreach.config import settings
from openoutreach.proxies.models import ProxyError

logger = logging.getLogger(__name__)

# Fields that must never leave this module in a public result.
_SECRET_FIELDS = {
    "password",
    "pass",
    "proxy_password",
    "secret",
    "api_key",
    "x-api-key",
}

_POOL_STATS_CACHE_SECONDS = 3600
_POOL_STATS_CACHE: dict[str, tuple[float, Any]] = {}
_POOL_STATS_LOCK = threading.Lock()


def _setting(name: str) -> Any:
    return getattr(settings, name, None)


def _as_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "enabled", "active"}:
            return True
        if normalized in {"false", "0", "no", "disabled", "inactive"}:
            return False
    return None


def _as_int(value: Any) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return max(0, int(float(value)))
    except (TypeError, ValueError):
        return None


def _first(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
    return None


def _strip_secrets(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in row.items()
        if not any(term in str(key).lower() for term in _SECRET_FIELDS)
    }


class MassiveResellerError(ProxyError):
    """Reseller/Pool Stats call failed without exposing the response body."""

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        code: Optional[str] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


@dataclass(frozen=True)
class MassiveResellerConfig:
    """Server-side Reseller configuration. Secrets are excluded from repr."""

    api_key: str = field(repr=False)
    parent_username: str
    base_url: str
    enabled: bool
    timeout_seconds: float = 30.0

    @classmethod
    def from_settings(cls) -> Optional["MassiveResellerConfig"]:
        enabled = bool(_setting("MASSIVE_RESELLER_ENABLED"))
        parent = str(_setting("MASSIVE_PARENT_USERNAME") or "").strip()
        proxy_password = str(_setting("MASSIVE_PROXY_PASSWORD") or "").strip()
        api_key = (
            str(_setting("MASSIVE_RESELLER_API_KEY") or "").strip()
            or proxy_password
        )
        base_url = str(
            _setting("MASSIVE_RESELLER_BASE_URL")
            or "https://api-network.joinmassive.com/resellers"
        ).strip()
        if not enabled or not parent or not api_key or not base_url:
            return None
        return cls(
            api_key=api_key,
            parent_username=parent,
            base_url=base_url,
            enabled=True,
        )

    @property
    def ready(self) -> bool:
        return bool(self.enabled and self.api_key and self.parent_username and self.base_url)


@dataclass(frozen=True)
class MassivePoolStatsConfig:
    """Server-side Pool Stats configuration. Secrets are excluded from repr."""

    api_key: str = field(repr=False)
    base_url: str
    enabled: bool
    min_nodes: int = 1000
    timeout_seconds: float = 30.0

    @classmethod
    def from_settings(cls) -> Optional["MassivePoolStatsConfig"]:
        enabled = bool(_setting("MASSIVE_POOL_STATS_ENABLED"))
        proxy_password = str(_setting("MASSIVE_PROXY_PASSWORD") or "").strip()
        api_key = (
            str(_setting("MASSIVE_POOL_STATS_API_KEY") or "").strip()
            or proxy_password
        )
        base_url = str(
            _setting("MASSIVE_POOL_STATS_BASE_URL")
            or "https://api-network.joinmassive.com/pool-stats"
        ).strip()
        if not enabled or not api_key or not base_url:
            return None
        return cls(
            api_key=api_key,
            base_url=base_url,
            enabled=True,
            min_nodes=max(1, int(_setting("MASSIVE_POOL_STATS_MIN_NODES") or 1000)),
        )

    @property
    def ready(self) -> bool:
        return bool(self.enabled and self.api_key and self.base_url)


def reseller_status() -> dict[str, Any]:
    """Return configuration presence only. Never return a key or password."""
    config = MassiveResellerConfig.from_settings()
    return {
        "enabled": bool(_setting("MASSIVE_RESELLER_ENABLED")),
        "configured": config is not None,
        "parent_username_set": bool(str(_setting("MASSIVE_PARENT_USERNAME") or "").strip()),
        "api_key_set": bool(
            str(_setting("MASSIVE_RESELLER_API_KEY") or "").strip()
            or str(_setting("MASSIVE_PROXY_PASSWORD") or "").strip()
        ),
        "default_limit_bytes": int(
            _setting("MASSIVE_RESELLER_DEFAULT_LIMIT_BYTES") or 5_000_000_000
        ),
        "monthly_soft_limit_bytes": int(
            _setting("MASSIVE_MONTHLY_SOFT_LIMIT_BYTES") or 25_000_000_000
        ),
        "monthly_hard_limit_bytes": int(
            _setting("MASSIVE_MONTHLY_HARD_LIMIT_BYTES") or 40_000_000_000
        ),
    }


def pool_stats_status() -> dict[str, Any]:
    config = MassivePoolStatsConfig.from_settings()
    return {
        "enabled": bool(_setting("MASSIVE_POOL_STATS_ENABLED")),
        "configured": config is not None,
        "api_key_set": bool(
            str(_setting("MASSIVE_POOL_STATS_API_KEY") or "").strip()
            or str(_setting("MASSIVE_PROXY_PASSWORD") or "").strip()
        ),
        "min_nodes": int(_setting("MASSIVE_POOL_STATS_MIN_NODES") or 1000),
    }


def generate_subaccount_password() -> str:
    """Generate a 32+ character sub-account secret."""
    return secrets.token_urlsafe(36)


def _response_rows(payload: Any, keys: tuple[str, ...]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    return []


def _response_object(payload: Any, keys: tuple[str, ...]) -> dict[str, Any]:
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, dict):
                return value
        return payload
    return {}


def _normalize_account(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Reseller account row without exposing its password."""
    username = _first(row, ("username", "subuser", "sub_username", "name", "login"))
    account_id = _first(row, ("id", "account_id", "_id", "uuid"))
    status_value = _first(row, ("status", "state", "account_status"))
    enabled = _as_bool(_first(row, ("enabled", "active", "is_active")))
    if status_value is None:
        status_value = "active" if enabled is not False else "disabled"
    used_bytes = _as_int(
        _first(
            row,
            (
                "used_bytes",
                "used",
                "usage_bytes",
                "traffic_used_bytes",
                "bytes_used",
                "usage",
            ),
        )
    )
    limit_bytes = _as_int(
        _first(
            row,
            (
                "limit",
                "limit_bytes",
                "traffic_limit",
                "traffic_limit_bytes",
                "bandwidth_limit",
                "quota_bytes",
                "allowance_bytes",
            ),
        )
    )
    limit_reached = _as_bool(
        _first(row, ("limit_reached", "is_limit_reached", "quota_reached"))
    )
    proxy_access = _as_bool(
        _first(row, ("proxy_access", "has_proxy_access", "proxy_access_enabled"))
    )
    normalized = {
        "account_id": str(account_id) if account_id is not None else None,
        "username": str(username) if username is not None else None,
        "status": str(status_value).lower() if status_value is not None else "unknown",
        "enabled": enabled,
        "used_bytes": used_bytes,
        "limit_bytes": limit_bytes,
        "limit_reached": bool(limit_reached) if limit_reached is not None else False,
        "proxy_access": proxy_access,
        "created_at": _first(row, ("created_at", "created", "createdAt")),
        "last_updated_at": _first(row, ("updated_at", "updated", "last_updated_at")),
    }
    return normalized


class MassiveResellerClient:
    """Thin, secret-safe client for the Massive Proxy Resellers API."""

    def __init__(self, config: Optional[MassiveResellerConfig] = None):
        resolved = config or MassiveResellerConfig.from_settings()
        if resolved is None or not resolved.ready:
            raise MassiveResellerError("Massive Reseller is not configured")
        self.config: MassiveResellerConfig = resolved

    def _url(self, path: str) -> str:
        base = self.config.base_url.rstrip("/")
        return f"{base}/{path.lstrip('/')}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> Any:
        headers = {
            "x-api-key": self.config.api_key,
            "Accept": "application/json",
        }
        try:
            with httpx.Client(timeout=self.config.timeout_seconds) as client:
                response = client.request(
                    method,
                    self._url(path),
                    headers=headers,
                    json=json_body,
                    params=params,
                )
        except httpx.TimeoutException:
            raise MassiveResellerError("Massive Reseller request timed out")
        except httpx.HTTPError:
            raise MassiveResellerError("Massive Reseller request failed")
        if response.status_code == 409:
            raise MassiveResellerError(
                "Massive sub-account already exists",
                status_code=409,
                code="already_exists",
            )
        if response.status_code >= 400:
            # Never include the body: Reseller responses can contain passwords.
            raise MassiveResellerError(
                f"Massive Reseller request failed (HTTP {response.status_code})",
                status_code=response.status_code,
            )
        try:
            return response.json()
        except ValueError:
            raise MassiveResellerError("Massive Reseller returned an invalid response")

    def _list_raw(self) -> list[dict[str, Any]]:
        payload = self._request("GET", "/accounts")
        rows = _response_rows(
            payload, ("accounts", "data", "results", "items", "subaccounts")
        )
        if not rows and isinstance(payload, dict):
            rows = _response_rows(payload.get("data"), ("accounts", "items"))
        return rows

    def list_accounts(self) -> list[dict[str, Any]]:
        """Return normalized sub-accounts. Passwords are always removed."""
        return [_normalize_account(_strip_secrets(row)) for row in self._list_raw()]

    def find_account_by_username(
        self, username: str, *, include_password: bool = False
    ) -> Optional[dict[str, Any]]:
        """Find one sub-account by username.

        ``include_password`` is only for the provisioning path that must build
        the proxy credential. The password is never logged or returned by an
        API route.
        """
        target = (username or "").strip().lower()
        for row in self._list_raw():
            row_username = str(
                _first(row, ("username", "subuser", "sub_username", "name", "login"))
                or ""
            ).lower()
            if row_username != target:
                continue
            normalized = _normalize_account(row)
            if include_password:
                password = _first(row, ("password", "pass", "proxy_password"))
                normalized["password"] = password
            return normalized
        return None

    def create_account(
        self,
        username: str,
        password: str,
        limit_bytes: int,
        *,
        sync_with_parent: bool = True,
    ) -> dict[str, Any]:
        """Create a sub-account. A 409 is surfaced as ``already_exists``."""
        payload = self._request(
            "POST",
            "/accounts",
            json_body={
                "username": username,
                "password": password,
                "limit": max(0, int(limit_bytes)),
                "sync_with_parent": bool(sync_with_parent),
            },
        )
        row = _response_object(payload, ("account", "data", "result"))
        normalized = _normalize_account(row)
        if not normalized.get("username"):
            normalized["username"] = username
        return normalized

    def get_account(self, account_id: str) -> dict[str, Any]:
        payload = self._request("GET", f"/accounts/{account_id}")
        return _normalize_account(
            _strip_secrets(_response_object(payload, ("account", "data", "result")))
        )

    def update_account(self, account_id: str, **fields: Any) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if "limit_bytes" in fields:
            body["limit"] = max(0, int(fields.pop("limit_bytes") or 0))
        if "sync_with_parent" in fields:
            body["sync_with_parent"] = bool(fields.pop("sync_with_parent"))
        body.update({key: value for key, value in fields.items() if value is not None})
        payload = self._request("PUT", f"/accounts/{account_id}", json_body=body)
        return _normalize_account(
            _strip_secrets(_response_object(payload, ("account", "data", "result")))
        )

    def set_account_status(self, account_id: str, enabled: bool) -> dict[str, Any]:
        """Enable/disable a sub-account. Both status and boolean are sent for API compatibility."""
        payload = self._request(
            "PUT",
            f"/accounts/{account_id}",
            json_body={
                "status": "active" if enabled else "disabled",
                "enabled": bool(enabled),
            },
        )
        return _normalize_account(
            _strip_secrets(_response_object(payload, ("account", "data", "result")))
        )

    def enable_account(self, account_id: str) -> dict[str, Any]:
        return self.set_account_status(account_id, True)

    def disable_account(self, account_id: str) -> dict[str, Any]:
        return self.set_account_status(account_id, False)

    def allocate_traffic(self, account_id: str, bytes_: int) -> dict[str, Any]:
        """Top up a sub-account's cumulative lifetime allowance."""
        payload = self._request(
            "POST",
            f"/accounts/{account_id}/allocations",
            json_body={"bytes": max(0, int(bytes_))},
        )
        return _normalize_account(
            _strip_secrets(_response_object(payload, ("account", "data", "result")))
        )

    def set_session_limits(
        self,
        account_id: str,
        *,
        max_sessions: Optional[int] = None,
        bytes_per_session: Optional[int] = None,
    ) -> dict[str, Any]:
        """Set optional per-session limits for a sub-account."""
        body: dict[str, Any] = {}
        if max_sessions is not None:
            body["max_sessions"] = max(0, int(max_sessions))
        if bytes_per_session is not None:
            body["bytes_per_session"] = max(0, int(bytes_per_session))
        payload = self._request(
            "PUT", f"/accounts/{account_id}/session-limits", json_body=body
        )
        return _normalize_account(
            _strip_secrets(_response_object(payload, ("account", "data", "result")))
        )

    def get_account_usage(
        self, account_id: str, *, daily: bool = False
    ) -> dict[str, Any]:
        path = f"/accounts/{account_id}/usage/daily" if daily else f"/accounts/{account_id}/usage"
        payload = self._request("GET", path)
        row = _response_object(payload, ("usage", "data", "result"))
        normalized = _normalize_account(row)
        return {
            "account_id": account_id,
            "used_bytes": normalized.get("used_bytes"),
            "limit_bytes": normalized.get("limit_bytes"),
            "limit_reached": normalized.get("limit_reached", False),
            "proxy_access": normalized.get("proxy_access"),
        }

    def reporting_usage(
        self,
        *,
        group_by: str = "subaccount",
        from_date: str,
        to_date: str,
    ) -> list[dict[str, Any]]:
        """Fetch Reporting API usage. Falls back to ``subuser`` at the caller."""
        reporting_key = (
            str(_setting("MASSIVE_REPORTING_API_KEY") or "").strip()
            or str(_setting("MASSIVE_PROXY_PASSWORD") or "").strip()
        )
        base_url = str(
            _setting("MASSIVE_REPORTING_BASE_URL")
            or "https://api-network.joinmassive.com/reporting"
        ).strip()
        if not reporting_key or not base_url:
            raise MassiveResellerError("Massive Reporting is not configured")
        try:
            with httpx.Client(timeout=self.config.timeout_seconds) as client:
                response = client.get(
                    f"{base_url.rstrip('/')}/v1/usage",
                    params={
                        "group_by": group_by,
                        "from": from_date,
                        "to": to_date,
                    },
                    headers={
                        "x-api-key": reporting_key,
                        "Accept": "application/json",
                    },
                )
        except httpx.TimeoutException:
            raise MassiveResellerError("Massive Reporting request timed out")
        except httpx.HTTPError:
            raise MassiveResellerError("Massive Reporting request failed")
        if response.status_code >= 400:
            raise MassiveResellerError(
                f"Massive Reporting request failed (HTTP {response.status_code})",
                status_code=response.status_code,
            )
        try:
            payload = response.json()
        except ValueError:
            raise MassiveResellerError("Massive Reporting returned an invalid response")
        rows = _response_rows(payload, ("data", "results", "usage", "items"))
        normalized: list[dict[str, Any]] = []
        for row in rows:
            subaccount = _first(
                row,
                (
                    "subaccount",
                    "sub_account",
                    "subuser",
                    "sub_user",
                    "username",
                    "label",
                ),
            )
            used = _as_int(
                _first(row, ("bytes", "used_bytes", "total_bytes", "usage_bytes"))
            )
            if used is None:
                usage = _first(row, ("usage", "gb", "usage_gb"))
                if usage is not None:
                    unit = str(_first(row, ("unit", "units")) or "bytes").lower()
                    try:
                        used = int(
                            float(usage) * (1_000_000_000 if unit.startswith("g") else 1)
                        )
                    except (TypeError, ValueError):
                        used = None
            if not subaccount or used is None:
                continue
            normalized.append(
                {
                    "subaccount": str(subaccount),
                    "bytes": max(0, used),
                    "period_start": str(
                        _first(row, ("from", "period_start", "start")) or from_date
                    ),
                    "period_end": str(
                        _first(row, ("to", "period_end", "end")) or to_date
                    ),
                }
            )
        return normalized

    def parent_usage(self) -> dict[str, Any]:
        """Aggregate parent plan usage from the sub-account list."""
        accounts = self.list_accounts()
        used = sum(int(account.get("used_bytes") or 0) for account in accounts)
        limit = sum(int(account.get("limit_bytes") or 0) for account in accounts)
        limit_reached = sum(1 for account in accounts if account.get("limit_reached"))
        proxy_access_revoked = sum(
            1 for account in accounts if account.get("proxy_access") is False
        )
        return {
            "accounts": len(accounts),
            "used_bytes": used,
            "limit_bytes": limit,
            "limit_reached": limit_reached,
            "proxy_access_revoked": proxy_access_revoked,
        }


class MassivePoolStatsClient:
    """Cached Pool Stats client for region availability warnings."""

    def __init__(self, config: Optional[MassivePoolStatsConfig] = None):
        resolved = config or MassivePoolStatsConfig.from_settings()
        if resolved is None or not resolved.ready:
            raise MassiveResellerError("Massive Pool Stats is not configured")
        self.config: MassivePoolStatsConfig = resolved

    def _cache_key(self, path: str, params: Optional[dict[str, Any]]) -> str:
        return f"{path}|{sorted((params or {}).items())}"

    def _cached(self, key: str) -> Any:
        with _POOL_STATS_LOCK:
            entry = _POOL_STATS_CACHE.get(key)
            if entry and (time.time() - entry[0]) < _POOL_STATS_CACHE_SECONDS:
                return entry[1]
        return None

    def _store(self, key: str, value: Any) -> None:
        with _POOL_STATS_LOCK:
            _POOL_STATS_CACHE[key] = (time.time(), value)

    def _get(self, path: str, params: Optional[dict[str, Any]] = None) -> Any:
        key = self._cache_key(path, params)
        cached = self._cached(key)
        if cached is not None:
            return cached
        headers = {
            "x-api-key": self.config.api_key,
            "Accept": "application/json",
            # The Pool Stats API documents gzip support; httpx decompresses it.
            "Accept-Encoding": "gzip",
        }
        try:
            with httpx.Client(timeout=self.config.timeout_seconds) as client:
                response = client.get(
                    f"{self.config.base_url.rstrip('/')}/{path.lstrip('/')}",
                    params=params,
                    headers=headers,
                )
        except httpx.TimeoutException:
            raise MassiveResellerError("Massive Pool Stats request timed out")
        except httpx.HTTPError:
            raise MassiveResellerError("Massive Pool Stats request failed")
        if response.status_code >= 400:
            raise MassiveResellerError(
                f"Massive Pool Stats request failed (HTTP {response.status_code})",
                status_code=response.status_code,
            )
        try:
            payload = response.json()
        except ValueError:
            raise MassiveResellerError("Massive Pool Stats returned an invalid response")
        self._store(key, payload)
        return payload

    def regions(self) -> Any:
        return self._get("/v1/regions")

    def live(
        self,
        *,
        country: Optional[str] = None,
        group_by: str = "country,city",
    ) -> Any:
        params: dict[str, Any] = {"group_by": group_by}
        if country:
            params["country"] = country.upper()
        return self._get("/v1/live", params)

    def _count_rows(self, payload: Any) -> list[dict[str, Any]]:
        rows = _response_rows(
            payload, ("data", "results", "nodes", "pool", "countries", "cities")
        )
        if rows:
            return rows
        if isinstance(payload, dict):
            for value in payload.values():
                if isinstance(value, list) and value and isinstance(value[0], dict):
                    return [row for row in value if isinstance(row, dict)]
        return []

    @staticmethod
    def _count(row: dict[str, Any]) -> int:
        for key in ("count", "nodes", "node_count", "available", "total"):
            value = _as_int(row.get(key))
            if value is not None:
                return value
        return 0

    def country_counts(self) -> dict[str, int]:
        payload = self.live(group_by="country")
        counts: dict[str, int] = {}
        for row in self._count_rows(payload):
            country = str(_first(row, ("country", "country_code", "code")) or "").upper()
            if country:
                counts[country] = counts.get(country, 0) + self._count(row)
        return counts

    def city_counts(self, country: str) -> dict[str, int]:
        payload = self.live(country=country, group_by="country,city")
        counts: dict[str, int] = {}
        for row in self._count_rows(payload):
            city = str(_first(row, ("city", "city_name")) or "").strip()
            if city:
                counts[city] = counts.get(city, 0) + self._count(row)
        return counts

    def country_count(self, country: str) -> Optional[int]:
        counts = self.country_counts()
        return counts.get((country or "").upper())

    def is_country_safe(self, country: str) -> bool:
        count = self.country_count(country)
        return count is not None and count >= self.config.min_nodes

    def is_city_safe(self, country: str, city: str) -> bool:
        count = self.city_counts(country).get(city)
        return count is not None and count >= self.config.min_nodes

    def warnings(self, country: str) -> list[str]:
        messages: list[str] = []
        count = self.country_count(country)
        if count is None:
            messages.append(
                f"No pool statistics are available for {country.upper()}; use country-level targeting."
            )
        elif count < self.config.min_nodes:
            messages.append(
                f"{country.upper()} has {count} nodes, below the recommended "
                f"{self.config.min_nodes}; use country-level targeting."
            )
        return messages


def utc_day(value: Optional[datetime] = None) -> str:
    moment = value or datetime.now(timezone.utc)
    return moment.date().isoformat()


def current_month_start(value: Optional[datetime] = None) -> str:
    moment = value or datetime.now(timezone.utc)
    return moment.replace(day=1).date().isoformat()
