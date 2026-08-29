"""Fail-closed tenant context and ownership predicates.

Identifiers supplied by a client are locators only. These helpers make the
server-derived tenant the mandatory ownership predicate for repository calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class TenantContext:
    """Authenticated server context used by tenant-aware repositories."""

    tenant_id: str
    actor_type: str = "human"
    subject_id: str | None = None
    device_id: str | None = None
    profile_ids: frozenset[str] = frozenset()
    scopes: frozenset[str] = frozenset()
    channel_profile_ids: Mapping[str, frozenset[str]] | None = None

    def __post_init__(self) -> None:
        if not self.tenant_id or not self.tenant_id.strip():
            raise ValueError("tenant context requires a tenant id")


def owned_predicate(context: TenantContext, *, resource_id: str | None = None, **fields: Any) -> dict[str, Any]:
    """Build an ownership predicate without allowing client ownership fields."""
    query: dict[str, Any] = {"user_id": context.tenant_id}
    if resource_id is not None:
        query["_id"] = resource_id
    for name, value in fields.items():
        if name in {"user_id", "tenant_id", "owner_id"}:
            raise ValueError("ownership fields must come from authenticated context")
        if value is not None:
            query[name] = value
    return query


def require_owned_document(document: Mapping[str, Any] | None, context: TenantContext) -> Mapping[str, Any]:
    """Reject missing or differently-owned documents without an oracle."""
    if not document or document.get("user_id") != context.tenant_id:
        raise LookupError("resource not found")
    return document
