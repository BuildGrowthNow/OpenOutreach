"""Unit coverage for deterministic sequence execution helpers."""

from datetime import datetime, timedelta, timezone

from openoutreach.core.sequence_executor import _check_wait, _get_next_step_id, _task_type_for_step
from openoutreach.mongodb.models import Deal, Task


def test_branch_resolution_is_explicit():
    campaign = type("C", (), {"sequence_edges": [
        {"source": "c", "target": "yes", "data": {"condition": "yes"}},
        {"source": "c", "target": "no", "data": {"condition": "no"}},
    ]})()
    assert _get_next_step_id(campaign, "c", True) == "yes"
    assert _get_next_step_id(campaign, "c", False) == "no"


def test_action_mapping_and_wait_expiration():
    assert _task_type_for_step({"type": "action", "data": {"channel": "email", "action": "send_email"}}) == Task.TaskType.EMAIL_FOLLOW_UP
    deal = Deal(sequence_last_step_at=datetime.now(timezone.utc) - timedelta(hours=2))
    assert _check_wait(deal, {"type": "wait", "data": {"wait_hours": 1}})
    assert not _check_wait(deal, {"type": "wait", "data": {"wait_days": 1}})
