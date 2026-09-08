"""Runtime helpers for sequence-node message configuration.

The editor stores the canonical message under ``data.message``.  Older
campaigns stored those fields directly under ``data``; keeping the
normalization here makes all channel handlers agree on the same behavior.
"""

from __future__ import annotations

from typing import Any


DEFAULT_MESSAGE: dict[str, Any] = {
    "content_mode": "ai_prompt",
    "prompt": "",
    "subject": "",
    "body": "",
    "link_refs": [],
    "stop_on_reply": True,
    "fallback_mode": "continue",
    "fallback_body": "",
}


def message_config(step: dict | None) -> dict[str, Any]:
    """Return a detached, backwards-compatible message configuration."""
    data = (step or {}).get("data") or {}
    nested = data.get("message")
    # Merge for mixed-version documents: nested fields win, while legacy
    # fields that were added after the nested object still remain executable.
    source = {**data, **nested} if isinstance(nested, dict) else data
    result = dict(DEFAULT_MESSAGE)
    result.update({key: value for key, value in source.items() if key in DEFAULT_MESSAGE})
    result["link_refs"] = list(result.get("link_refs") or [])
    # Older flattened nodes often carried a body without an explicit
    # content_mode. Treat that shape as static content instead of silently
    # discarding the configured body and invoking an AI agent.
    if result["content_mode"] == "ai_prompt" and not str(result.get("prompt") or "").strip() and str(result.get("body") or "").strip():
        result["content_mode"] = "static"
    return result


def fallback_config(config: dict[str, Any], error: Exception | None = None) -> tuple[str, str]:
    """Return ``(mode, body)`` for an AI-generation failure."""
    mode = str(config.get("fallback_mode") or "continue")
    body = str(config.get("fallback_body") or "").strip()
    if error:
        # Keep the caller's logs useful without exposing prompts or recipient data.
        import logging
        logging.getLogger(__name__).warning("sequence message generation failed (%s)", type(error).__name__)
    return mode, body
