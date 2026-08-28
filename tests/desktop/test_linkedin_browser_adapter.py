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
