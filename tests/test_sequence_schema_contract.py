"""Contract tests for the canonical campaign workflow graph."""

from openoutreach.api_v2.routers.campaign_templates import _system_templates
from openoutreach.core.sequence_schema import validate_sequence_graph


def node(node_id, node_type, **data):
    return {"id": node_id, "type": node_type, "data": data}


def edge(source, target, branch=None):
    item = {"id": f"{source}-{target}", "source": source, "target": target}
    if branch:
        item["data"] = {"condition": branch}
    return item


def test_wait_nodes_are_valid_when_connected_to_an_end():
    errors = validate_sequence_graph(
        [node("send", "action", action="connect", channel="linkedin"), node("wait", "wait", wait_days=2), node("end", "end")],
        [edge("send", "wait"), edge("wait", "end")],
        require_launchable=True,
    )
    assert errors == []


def test_link_conditions_require_a_known_campaign_link():
    errors = validate_sequence_graph(
        [
            node("check", "condition", condition="link_clicked", link_key="demo"),
            node("yes", "end"),
            node("no", "end"),
        ],
        [edge("check", "yes", "yes"), edge("check", "no", "no")],
        available_links=set(),
    )
    assert any(error["code"] == "missing_link" for error in errors)


def test_message_actions_require_static_body_or_ai_prompt():
    errors = validate_sequence_graph(
        [node("send", "action", action="send_email", channel="email", message={"content_mode": "static"}), node("end", "end")],
        [edge("send", "end")],
    )
    assert any(error["code"] == "message_required" for error in errors)


def test_unsupported_controls_are_rejected_instead_of_being_silent():
    errors = validate_sequence_graph(
        [node("connect", "action", action="connect", channel="linkedin", prompt="ignored"), node("end", "end")],
        [edge("connect", "end")],
    )
    assert any(error["code"] == "unsupported_option" for error in errors)


def test_legacy_flattened_fallback_fields_are_validated():
    errors = validate_sequence_graph(
        [
            node(
                "send", "action", action="send_email", channel="email",
                content_mode="ai_prompt", prompt="Write a follow-up",
                fallback_mode="static", fallback_body="",
            ),
            node("end", "end"),
        ],
        [edge("send", "end")],
    )
    assert any(error["code"] == "fallback_required" for error in errors)


def test_system_templates_are_canonical_and_validate():
    for template in _system_templates():
        errors = validate_sequence_graph(
            template["sequence_steps"],
            template["sequence_edges"],
            available_links={item["key"] for item in template["link_definitions"]},
            require_launchable=True,
        )
        assert errors == [], template["name"]
