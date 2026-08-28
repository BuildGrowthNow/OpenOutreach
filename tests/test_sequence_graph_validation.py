"""Pure validation tests for campaign visual-editor graphs."""

from openoutreach.api_v2.routers.campaigns import _validate_sequence_graph


def step(step_id, step_type="action", action="connect", channel="linkedin"):
    return {
        "id": step_id,
        "type": step_type,
        "data": {"action": action, "channel": channel, "label": step_id},
    }


def edge(source, target, condition=None):
    item = {"id": f"{source}-{target}", "source": source, "target": target}
    if condition:
        item["data"] = {"condition": condition}
    return item


def test_rejects_dangling_edges_and_multiple_roots():
    errors = _validate_sequence_graph(
        [step("a"), step("b"), step("end", "end", None, None)],
        [edge("a", "end"), edge("missing", "b")],
    )
    assert any("invalid node" in error for error in errors)
    assert any("entry point" in error for error in errors)


def test_rejects_invalid_action_channel_and_unreachable_node():
    errors = _validate_sequence_graph(
        [step("a", action="send_email", channel="linkedin"), step("end", "end", None, None), step("orphan")],
        [edge("a", "end")],
        require_launchable=True,
    )
    assert any("incompatible channel" in error for error in errors)
    assert any("reachable" in error for error in errors)


def test_condition_requires_yes_and_no_paths():
    errors = _validate_sequence_graph(
        [step("a", "condition", None, None), step("end", "end", None, None)],
        [edge("a", "end", "yes")],
        require_launchable=True,
    )
    assert any("exactly Yes and No" in error for error in errors)


def test_accepts_valid_launchable_linear_graph():
    assert _validate_sequence_graph(
        [step("a"), step("end", "end", None, None)],
        [edge("a", "end")],
        require_launchable=True,
    ) == []


def test_rejects_cycles_and_zero_duration_waits_on_launch():
    errors = _validate_sequence_graph(
        [step("a"), step("wait", "wait", None, None), step("end", "end", None, None)],
        [edge("a", "wait"), edge("wait", "a"), edge("wait", "end")],
        require_launchable=True,
    )
    assert any("cycle" in error for error in errors)
    assert any("positive duration" in error for error in errors)
