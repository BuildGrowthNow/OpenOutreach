"""Canonical, versioned campaign sequence contract.

The executor still consumes the backwards-compatible ``sequence_steps`` and
``sequence_edges`` arrays.  This module is the single place where API and
template input is parsed and where graph safety is enforced.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SEQUENCE_SCHEMA_VERSION = 1
NODE_TYPES = {"action", "wait", "condition", "end"}
CHANNELS = {"linkedin", "email", "whatsapp", "internal"}
ACTION_CHANNELS = {
    "connect": "linkedin",
    "follow_up": "linkedin",
    "send_email": "email",
    "send_whatsapp": "whatsapp",
    "notify_internal": "internal",
    "internal_notification": "internal",
}
SUPPORTED_CONDITIONS = {
    "lead_has_email",
    "lead_has_phone",
    "reply_received",
    "email_opened",
    "email_not_opened",
    "link_clicked",
    "link_not_clicked",
}


class MessageConfig(BaseModel):
    """Message content kept reusable and free of recipient-specific URLs."""

    model_config = ConfigDict(extra="forbid")

    content_mode: Literal["ai_prompt", "static"] = "ai_prompt"
    prompt: str = Field(default="", max_length=12000)
    subject: str = Field(default="", max_length=500)
    body: str = Field(default="", max_length=20000)
    link_refs: list[str] = Field(default_factory=list, max_length=20)
    stop_on_reply: bool = True
    fallback_mode: Literal["skip", "static", "continue"] = "continue"
    fallback_body: str = Field(default="", max_length=20000)

    @field_validator("link_refs")
    @classmethod
    def valid_link_keys(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("link_refs must contain unique logical link keys")
        for key in value:
            if not key or len(key) > 80 or not key.replace("_", "").replace("-", "").isalnum():
                raise ValueError("link_refs must contain safe logical link keys")
        return value


class SequenceNodeData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(default="", max_length=200)
    channel: Literal["linkedin", "email", "whatsapp", "internal"] | None = None
    action: str | None = None
    wait_days: float = Field(default=0, ge=0, le=3650)
    wait_hours: float = Field(default=0, ge=0, le=87600)
    condition: str | None = None
    link_key: str | None = None
    link_asset_id: str | None = None
    observation_window_hours: float | None = Field(default=None, ge=0, le=87600)
    requires: list[str] = Field(default_factory=list, max_length=20)
    message: MessageConfig | None = None
    # Read-only compatibility fields for graphs written before ``message``
    # became a nested object. They are normalized by message_config().
    content_mode: Literal["ai_prompt", "static"] | None = None
    prompt: str | None = Field(default=None, max_length=12000)
    subject: str | None = Field(default=None, max_length=500)
    body: str | None = Field(default=None, max_length=20000)
    link_refs: list[str] | None = Field(default=None, max_length=20)
    stop_on_reply: bool | None = None
    fallback_mode: Literal["skip", "static", "continue"] | None = None
    fallback_body: str | None = Field(default=None, max_length=20000)


class SequenceNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=128)
    type: Literal["action", "wait", "condition", "end"]
    data: SequenceNodeData = Field(default_factory=SequenceNodeData)
    position: dict[str, float] | None = None


class SequenceEdgeData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    condition: Literal["yes", "no", "always"] | None = None


class SequenceEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=256)
    source: str = Field(min_length=1, max_length=128)
    target: str = Field(min_length=1, max_length=128)
    data: SequenceEdgeData = Field(default_factory=SequenceEdgeData)


def _error(node_id: str | None, code: str, message: str) -> dict[str, Any]:
    return {"node_id": node_id, "code": code, "message": message}


def parse_sequence(steps: list[dict[str, Any]], edges: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse, normalize and validate a sequence without mutating caller data."""

    errors: list[dict[str, Any]] = []
    parsed_steps: list[dict[str, Any]] = []
    parsed_edges: list[dict[str, Any]] = []
    for raw in steps:
        try:
            parsed_steps.append(SequenceNode.model_validate(raw).model_dump(exclude_none=True))
        except Exception as exc:
            node_id = raw.get("id") if isinstance(raw, dict) else None
            errors.append(_error(str(node_id) if node_id else None, "invalid_node", str(exc)))
    for raw in edges:
        try:
            parsed_edges.append(SequenceEdge.model_validate(raw).model_dump(exclude_none=True))
        except Exception as exc:
            edge_id = raw.get("id") if isinstance(raw, dict) else None
            errors.append(_error(None, "invalid_edge", f"Edge {edge_id or '<missing>'} is invalid: {exc}"))
    return parsed_steps, parsed_edges, errors


def validate_sequence_graph(
    steps: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    *,
    require_launchable: bool = False,
    available_links: set[str] | None = None,
    max_steps: int = 100,
) -> list[dict[str, Any]]:
    """Return structured authoritative graph errors."""

    normalized_steps, normalized_edges, errors = parse_sequence(steps, edges)
    if len(normalized_steps) > max_steps:
        errors.append(_error(None, "step_limit", f"A sequence may contain at most {max_steps} nodes."))
    ids = [str(node.get("id", "")) for node in normalized_steps]
    if len(ids) != len(set(ids)):
        errors.extend(_error(node_id, "duplicate_node_id", "Node IDs must be unique.") for node_id in sorted({x for x in ids if ids.count(x) > 1}))
    known = set(ids)
    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    incoming: dict[str, int] = defaultdict(int)
    seen_edges: set[tuple[str, str, str]] = set()

    for edge in normalized_edges:
        source, target = str(edge.get("source")), str(edge.get("target"))
        branch = str((edge.get("data") or {}).get("condition", "always"))
        if source not in known or target not in known or source == target:
            errors.append(_error(source if source in known else None, "invalid_edge_endpoint", f"Edge {edge.get('id', '<missing>')} references an invalid node."))
            continue
        key = (source, target, branch)
        if key in seen_edges:
            errors.append(_error(source, "duplicate_edge", f"Duplicate edge from {source} to {target}."))
        seen_edges.add(key)
        outgoing[source].append(edge)
        incoming[target] += 1

    roots = [node_id for node_id in ids if incoming[node_id] == 0]
    if len(roots) != 1:
        errors.append(_error(None, "root_count", f"A sequence must have exactly one entry point; found {len(roots)}."))

    if roots:
        reachable: set[str] = set()
        queue: deque[str] = deque([roots[0]])
        while queue:
            current = queue.popleft()
            if current in reachable:
                continue
            reachable.add(current)
            queue.extend(str(edge["target"]) for edge in outgoing.get(current, []))
        for node_id in ids:
            if node_id not in reachable:
                errors.append(_error(node_id, "unreachable_node", f"Node {node_id} is not reachable from the entry point."))

    # DFS cycle check; loops are not supported by the current executor.
    visiting: set[str] = set()
    visited: set[str] = set()
    def visit(node_id: str) -> None:
        if node_id in visiting:
            errors.append(_error(node_id, "cycle", f"Sequence contains a cycle involving node {node_id}."))
            return
        if node_id in visited:
            return
        visiting.add(node_id)
        for edge in outgoing.get(node_id, []):
            visit(str(edge["target"]))
        visiting.remove(node_id)
        visited.add(node_id)
    for node_id in ids:
        visit(node_id)

    for node in normalized_steps:
        node_id = str(node["id"])
        node_type = node["type"]
        data = node.get("data") or {}
        node_out = outgoing.get(node_id, [])
        if node_type != "end" and not node_out:
            errors.append(_error(node_id, "missing_outgoing_edge", f"Node {node_id} must have an outgoing edge."))
        if node_type == "condition":
            condition = data.get("condition")
            if condition not in SUPPORTED_CONDITIONS:
                errors.append(_error(node_id, "unsupported_condition", f"Condition {condition!r} is not supported."))
            if condition in {"link_clicked", "link_not_clicked"} and not (data.get("link_key") or data.get("link_asset_id")):
                errors.append(_error(node_id, "missing_link_reference", "Link conditions require a link key or asset ID."))
            if available_links is not None and data.get("link_key") and data.get("link_key") not in available_links:
                errors.append(_error(node_id, "missing_link", f"Node {node_id} references unknown link {data.get('link_key')!r}."))
            branches = [str((edge.get("data") or {}).get("condition", "")) for edge in node_out]
            if sorted(branches) != ["no", "yes"]:
                errors.append(_error(node_id, "condition_branches", f"Condition node {node_id} must have exactly Yes and No paths (exactly one of each)."))
        elif data.get("observation_window_hours") is not None:
            errors.append(_error(node_id, "unsupported_option", "observation_window_hours is only valid on condition nodes."))
        if node_type == "wait" and float(data.get("wait_days", 0) or 0) + float(data.get("wait_hours", 0) or 0) <= 0:
            errors.append(_error(node_id, "zero_wait", f"Wait node {node_id} must have a positive duration."))
        if node_type == "action":
            action = data.get("action")
            expected_channel = ACTION_CHANNELS.get(str(action))
            if expected_channel is None:
                errors.append(_error(node_id, "unsupported_action", f"Action node {node_id} has an unsupported action."))
            elif data.get("channel") != expected_channel:
                errors.append(_error(node_id, "incompatible_channel", f"Action node {node_id} has an incompatible channel; it requires {expected_channel}."))
            if action == "connect":
                message_fields = ("message", "content_mode", "prompt", "subject", "body", "link_refs", "stop_on_reply", "fallback_mode", "fallback_body")
                if any(data.get(field) not in (None, "", [], {}) for field in message_fields):
                    errors.append(_error(node_id, "unsupported_option", "LinkedIn connect nodes do not support message configuration."))
            if action in {"follow_up", "send_email", "send_whatsapp"}:
                message = data.get("message")
                if not isinstance(message, dict):
                    # Accept the flattened legacy shape while new writes use message.
                    message = {
                        key: data[key]
                        for key in (
                            "content_mode", "prompt", "subject", "body", "link_refs",
                            "stop_on_reply", "fallback_mode", "fallback_body",
                        )
                        if key in data
                    }
                mode = message.get("content_mode", "ai_prompt")
                fallback_mode = message.get("fallback_mode", "continue")
                if mode not in {"ai_prompt", "static"} or (mode == "static" and not str(message.get("body", "")).strip()) or (mode == "ai_prompt" and not str(message.get("prompt", "")).strip() and not str(message.get("body", "")).strip()):
                    errors.append(_error(node_id, "message_required", f"Message action node {node_id} requires static body or AI prompt content."))
                if fallback_mode not in {"skip", "static", "continue"}:
                    errors.append(_error(node_id, "invalid_fallback_mode", f"Message action node {node_id} has an unsupported fallback mode."))
                if fallback_mode == "static" and not str(message.get("fallback_body", "")).strip():
                    errors.append(_error(node_id, "fallback_required", f"Message action node {node_id} needs fallback_body when fallback_mode is static."))
                refs = message.get("link_refs") or []
                if available_links is not None:
                    for ref in refs:
                        if ref not in available_links:
                            errors.append(_error(node_id, "missing_link", f"Node {node_id} references unknown link {ref!r}."))
        if node_type == "end" and node_out:
            errors.append(_error(node_id, "end_has_outgoing", f"End node {node_id} cannot have outgoing edges."))

    if require_launchable:
        if not normalized_steps:
            errors.append(_error(None, "empty_sequence", "Sequence has no nodes."))
        if not any(node.get("type") == "action" for node in normalized_steps):
            errors.append(_error(None, "no_action", "Sequence needs at least one action node."))
        if not any(node.get("type") == "end" for node in normalized_steps):
            errors.append(_error(None, "no_end", "Sequence needs an End node."))
        if sum(1 for node in normalized_steps if node.get("data", {}).get("action") == "send_email") > 3:
            errors.append(_error(None, "email_step_limit", "A sequence supports at most three email actions."))
    return errors


def sequence_to_dicts(steps: list[dict[str, Any]], edges: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Normalize a valid graph for persistence while keeping legacy fields."""
    normalized_steps, normalized_edges, errors = parse_sequence(steps, edges)
    if errors:
        raise ValueError(errors)
    return normalized_steps, normalized_edges
