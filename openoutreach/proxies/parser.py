"""Bulk proxy paste parser for the admin proxy inventory.

Supported line formats::

    host:port:user:pass
    host:port:user:pass:country
    user:pass@host:port
    http://user:pass@host:port
    socks5://user:pass@host:port

CSV/TSV with a header containing ``host`` and ``port`` is also accepted.
Passwords that contain ``:`` must use CSV/TSV or URL encoding. Error messages
never include the source line, because it may contain credentials.
"""
from __future__ import annotations

import csv
import io
import re
from typing import Any, Optional
from urllib.parse import unquote, urlparse

from openoutreach.proxies.region import RegionError, normalize_country

_ALLOWED_PROTOCOLS = {"http", "https", "socks5", "socks5h"}
_HOST_RE = re.compile(r"^[A-Za-z0-9.\-_:\[\]]+$")
_MAX_PORT = 65535


class ProxyParseError(ValueError):
    """A single import line could not be parsed."""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _parse_port(value: str) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError):
        raise ProxyParseError("Port must be a number")
    if port < 1 or port > _MAX_PORT:
        raise ProxyParseError("Port must be between 1 and 65535")
    return port


def _validate_host(host: str) -> str:
    value = _clean(host).strip("[]")
    if not value or not _HOST_RE.match(value):
        raise ProxyParseError("Host is invalid")
    return value


def _entry(
    *,
    host: str,
    port: str,
    username: str,
    password: str,
    country: Optional[str],
    protocol: str = "http",
    subdivision: Optional[str] = None,
    city: Optional[str] = None,
) -> dict[str, Any]:
    protocol_value = _clean(protocol).lower() or "http"
    if protocol_value not in _ALLOWED_PROTOCOLS:
        raise ProxyParseError("Proxy scheme must be http, https, or socks5")
    username_value = _clean(username)
    password_value = _clean(password)
    if not username_value:
        raise ProxyParseError("Username is required")
    if not password_value:
        raise ProxyParseError("Password is required")
    try:
        country_value = normalize_country(country)
    except RegionError:
        raise ProxyParseError("Country must be a 2-letter code")
    return {
        "protocol": protocol_value,
        "host": _validate_host(host),
        "port": _parse_port(port),
        "username": username_value,
        "password": password_value,
        "country": country_value,
        "subdivision": _clean(subdivision).upper() or None,
        "city": _clean(city) or None,
    }


def _parse_url_line(line: str, default_country: Optional[str]) -> dict[str, Any]:
    parsed = urlparse(line if "://" in line else f"http://{line}")
    try:
        port = parsed.port
    except ValueError:
        raise ProxyParseError("Proxy URL has an invalid port")
    if not parsed.hostname or not port:
        raise ProxyParseError("Proxy URL must include a host and port")
    return _entry(
        protocol=parsed.scheme or "http",
        host=parsed.hostname,
        port=str(port),
        username=unquote(parsed.username or ""),
        password=unquote(parsed.password or ""),
        country=default_country,
    )


def _parse_at_line(line: str, default_country: Optional[str]) -> dict[str, Any]:
    credentials, _, endpoint = line.rpartition("@")
    if not credentials or not endpoint:
        raise ProxyParseError("Expected user:pass@host:port")
    username, sep, password = credentials.partition(":")
    if not sep:
        raise ProxyParseError("Expected user:pass before @")
    host, sep, port = endpoint.rpartition(":")
    if not sep:
        raise ProxyParseError("Expected host:port after @")
    return _entry(
        host=host,
        port=port,
        username=username,
        password=password,
        country=default_country,
    )


def _parse_colon_line(line: str, default_country: Optional[str]) -> dict[str, Any]:
    parts = line.split(":")
    if len(parts) < 4:
        raise ProxyParseError("Expected host:port:user:pass")
    host, port, username = parts[0], parts[1], parts[2]
    remainder = parts[3:]
    country = default_country
    if remainder and re.fullmatch(r"[A-Za-z]{2}", remainder[-1]):
        country = remainder[-1]
        remainder = remainder[:-1]
    password = ":".join(remainder)
    if not password:
        raise ProxyParseError("Password is required")
    return _entry(
        host=host,
        port=port,
        username=username,
        password=password,
        country=country,
    )


def _parse_line(line: str, default_country: Optional[str]) -> dict[str, Any]:
    if "://" in line:
        return _parse_url_line(line, default_country)
    if "@" in line:
        return _parse_at_line(line, default_country)
    return _parse_colon_line(line, default_country)


def _parse_delimited(text: str, default_country: Optional[str]) -> list[dict[str, Any]]:
    delimiter = "\t" if "\t" in text.splitlines()[0] else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        raise ProxyParseError("CSV header is missing")
    fields = {name.strip().lower(): name for name in reader.fieldnames if name}
    if "host" not in fields or "port" not in fields:
        raise ProxyParseError("CSV header must include host and port")

    entries: list[dict[str, Any]] = []
    for row in reader:
        entries.append(
            _entry(
                host=row.get(fields["host"], ""),
                port=row.get(fields["port"], ""),
                username=row.get(fields.get("username", ""), ""),
                password=row.get(fields.get("password", ""), ""),
                country=row.get(fields.get("country", ""), "") or default_country,
                protocol=row.get(fields.get("protocol", ""), "") or "http",
                subdivision=row.get(fields.get("subdivision", ""), ""),
                city=row.get(fields.get("city", ""), ""),
            )
        )
    return entries


def parse_bulk_proxies(
    text: str,
    *,
    default_country: Optional[str] = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse pasted proxy text into entries plus per-line errors.

    Returns ``(entries, errors)`` where each error is ``{"line": n, "error":
    message}``. Duplicate ``(host, port, username)`` entries within the paste
    are skipped and reported as errors so the admin sees them.
    """
    lines = [line.strip() for line in (text or "").splitlines()]
    content = [line for line in lines if line and not line.startswith("#")]
    if not content:
        return [], [{"line": 0, "error": "Paste at least one proxy"}]

    entries: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    seen: set[tuple[str, int, str]] = set()

    first = content[0].lower()
    is_delimited = (
        ("host" in first and "port" in first)
        and ("," in content[0] or "\t" in content[0])
    )

    if is_delimited:
        try:
            parsed_rows = _parse_delimited("\n".join(content), default_country)
        except (ProxyParseError, csv.Error) as exc:
            return [], [{"line": 1, "error": str(exc)}]
        for index, entry in enumerate(parsed_rows, start=2):
            key = (entry["host"].lower(), entry["port"], entry["username"])
            if key in seen:
                errors.append({"line": index, "error": "Duplicate proxy"})
                continue
            seen.add(key)
            entries.append(entry)
        return entries, errors

    for index, line in enumerate(content, start=1):
        try:
            entry = _parse_line(line, default_country)
        except ProxyParseError as exc:
            errors.append({"line": index, "error": str(exc)})
            continue
        key = (entry["host"].lower(), entry["port"], entry["username"])
        if key in seen:
            errors.append({"line": index, "error": "Duplicate proxy"})
            continue
        seen.add(key)
        entries.append(entry)
    return entries, errors
