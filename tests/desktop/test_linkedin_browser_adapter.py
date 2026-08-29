"""Tests for the API-fed local LinkedIn browser adapter."""

from pathlib import Path

import pytest

from openoutreach.desktop.linkedin_browser_adapter import (
    LinkedInBrowserAdapter,
    UnsupportedBrowserAction,
)


def test_adapter_has_no_server_or_database_imports():
    source = (Path(__file__).parents[2] / "openoutreach" / "desktop" / "linkedin_browser_adapter.py").read_text(encoding="utf-8")
    assert "openoutreach.mongodb" not in source
    assert "MONGODB_URI" not in source
    assert "SECRET_KEY" not in source


@pytest.mark.asyncio
async def test_unsupported_task_is_rejected_before_browser_start():
    adapter = LinkedInBrowserAdapter("profile-1")
    try:
        with pytest.raises(UnsupportedBrowserAction):
            await adapter.execute({"task_type": "follow_up", "snapshot": {}})
    finally:
        adapter._executor.shutdown(wait=True, cancel_futures=True)


def test_supported_tasks_are_explicit():
    assert LinkedInBrowserAdapter.SUPPORTED_TASKS == {
        "connect",
        "check_pending",
        "send_manual_message",
    }
    assert "observe" in LinkedInBrowserAdapter.SUPPORTED_V2_TASKS


def test_observe_task_returns_connection_observation(monkeypatch):
    from types import SimpleNamespace

    import linkedin_cli.actions.status as status_actions

    monkeypatch.setattr(status_actions, "get_connection_status",
                        lambda _adapter, _profile: SimpleNamespace(value="connected"))
    adapter = LinkedInBrowserAdapter("profile-1")
    monkeypatch.setattr(adapter, "_ensure_browser", lambda: None)
    try:
        result = adapter._execute_sync({
            "task_id": "task-1",
            "task_type": "observe",
            "snapshot": {
                "target_public_identifier": "person-1",
                "effect_key": "effect-1",
            },
        })
    finally:
        adapter._executor.shutdown(wait=True, cancel_futures=True)
    assert result["outcome"] == "observed"
    assert result["observation"]["observation"] == "connection"
    assert result["observation"]["state"] == "connected"
