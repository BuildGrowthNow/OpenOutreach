"""
Sequence execution engine.

For campaigns with sequence_active=True, resolves which tasks to create for
each active Deal based on its position in the sequence.

Critical constraint: deals with sequence_position=None (not yet started) are
initialized to the first step. Deals in DISCOVERED/QUALIFIED state that belong
to sequence campaigns are owned by the sequence — existing planners exclude them.
"""

import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from typing import Optional

from openoutreach.mongodb.models import Campaign, Deal, Task
from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.crm.models.deal import DealState

logger = logging.getLogger(__name__)


def _get_first_step_id(campaign: Campaign) -> Optional[str]:
    """Return id of first step with no incoming edges (root node)."""
    steps = campaign.sequence_steps
    if not steps:
        return None
    edge_targets = {e["target"] for e in campaign.sequence_edges}
    for step in steps:
        if step["id"] not in edge_targets:
            return step["id"]
    return steps[0]["id"]


def _get_next_step_id(campaign: Campaign, current_step_id: str, condition_met: bool) -> Optional[str]:
    """Follow outgoing edge from current step. Prefers condition-matching edge."""
    outgoing = [e for e in campaign.sequence_edges if e["source"] == current_step_id]
    if not outgoing:
        return None
    for edge in outgoing:
        edge_condition = (edge.get("data") or {}).get("condition", "always")
        if condition_met and edge_condition in ("always", "no_reply", "no_open"):
            return edge["target"]
        if not condition_met and edge_condition == "replied":
            return edge["target"]
    return outgoing[0]["target"]


def _get_step(campaign: Campaign, step_id: str) -> Optional[dict]:
    for s in campaign.sequence_steps:
        if s["id"] == step_id:
            return s
    return None


def _check_wait(deal: Deal, step: dict) -> bool:
    """True if enough days have elapsed since sequence_last_step_at."""
    wait_days = (step.get("data") or {}).get("wait_days", 0)
    if wait_days <= 0:
        return True
    if deal.sequence_last_step_at is None:
        return True
    ref = deal.sequence_last_step_at
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    elapsed = datetime.now(timezone.utc) - ref
    return elapsed >= timedelta(days=wait_days)


def _check_condition(deal: Deal, step: dict) -> bool:
    """True if step's condition is satisfied."""
    condition = (step.get("data") or {}).get("condition", "always")
    if condition == "always":
        return True
    messages_col = get_mongodb_collection("chat_messages")
    if messages_col is None:
        return True
    since = deal.sequence_last_step_at
    query: dict = {"deal_id": deal._id, "is_outgoing": False}
    if since:
        ts = since if since.tzinfo else since.replace(tzinfo=timezone.utc)
        query["creation_date"] = {"$gt": ts}
    has_reply = messages_col.count_documents(query) > 0
    if condition == "no_reply":
        return not has_reply
    if condition == "replied":
        return has_reply
    if condition == "no_open":
        return not has_reply
    return True


def _check_requires(lead_data: dict, step: dict) -> bool:
    """True if all fields in step.requires are non-empty on lead."""
    requires = (step.get("data") or {}).get("requires", [])
    for field in requires:
        if not lead_data.get(field):
            return False
    return True


def _has_inbound_reply(deal: Deal) -> bool:
    """True if any inbound message exists for this deal (stop-on-reply)."""
    messages_col = get_mongodb_collection("chat_messages")
    if messages_col is None:
        return False
    return messages_col.count_documents({"deal_id": deal._id, "is_outgoing": False}) > 0


def _task_type_for_step(step: dict) -> Optional[str]:
    """Map sequence step to Task.TaskType string. None for wait/condition/end nodes."""
    step_type = step.get("type")
    data = step.get("data") or {}
    channel = data.get("channel")
    action = data.get("action")

    if step_type in ("wait", "end", "condition"):
        return None
    if step_type == "action":
        if channel == "linkedin" and action == "connect":
            return Task.TaskType.CONNECT
        if channel == "linkedin" and action == "follow_up":
            return Task.TaskType.FOLLOW_UP
        if channel == "email":
            return Task.TaskType.EMAIL_FOLLOW_UP
        if channel == "whatsapp":
            return Task.TaskType.WHATSAPP_MESSAGE
    return None


def _create_task(campaign: Campaign, deal: Deal, task_type: str, user_id: str) -> None:
    """Insert a Task row for this sequence step."""
    tasks_col = get_mongodb_collection("tasks")
    if tasks_col is None:
        return
    now = datetime.now(timezone.utc)
    if task_type in (Task.TaskType.CONNECT, Task.TaskType.FOLLOW_UP):
        channel = "linkedin"
    elif task_type == Task.TaskType.EMAIL_FOLLOW_UP:
        channel = "email"
    else:
        channel = "whatsapp"
    tasks_col.insert_one({
        "_id": str(uuid4()),
        "task_type": task_type,
        "status": Task.STATUS_PENDING,
        "scheduled_at": now,
        "payload": {"campaign_id": campaign._id, "deal_id": deal._id},
        "user_id": user_id,
        "linkedin_profile_id": campaign.linkedin_profile_id,
        "channel": channel,
        "created_at": now,
    })


def resolve_sequence_tasks(campaign: Campaign, user_id: str) -> int:
    """
    For every active Deal in this campaign (sequence_active=True):
    - Initialize deals with sequence_position=None at the first step
    - Stop-on-reply: mark sequence_done=True
    - Check wait/condition/requires for current step
    - If ready: create Task row, advance sequence_position
    - If wait not elapsed: leave deal for next reconcile cycle
    - If requires not met: advance past step silently
    Returns count of tasks created.
    """
    if not campaign.sequence_active or not campaign.sequence_steps:
        return 0

    deals_col = get_mongodb_collection("deals")
    leads_col = get_mongodb_collection("leads")
    if deals_col is None or leads_col is None:
        return 0

    active_states = [
        DealState.DISCOVERED,
        DealState.QUALIFIED,
        DealState.READY_TO_CONNECT,
        DealState.PENDING,
        DealState.CONNECTED,
    ]

    deal_docs = list(deals_col.find({
        "campaign_id": campaign._id,
        "state": {"$in": active_states},
        "sequence_done": {"$ne": True},
    }))

    first_step_id = _get_first_step_id(campaign)
    if not first_step_id:
        return 0

    tasks_created = 0

    for doc in deal_docs:
        deal = Deal.from_dict(doc)
        lead_data = leads_col.find_one({"_id": deal.lead_id}) or {}

        if _has_inbound_reply(deal):
            deals_col.update_one(
                {"_id": deal._id},
                {"$set": {"sequence_done": True}},
            )
            logger.debug("sequence: deal %s stopped on reply", deal._id)
            continue

        current_step_id = deal.sequence_position or first_step_id
        step = _get_step(campaign, current_step_id)
        if step is None:
            logger.warning("sequence: step %s not found in campaign %s", current_step_id, campaign._id)
            continue

        step_type = step.get("type")

        if step_type == "end":
            deals_col.update_one({"_id": deal._id}, {"$set": {"sequence_done": True}})
            continue

        if step_type in ("wait", "condition"):
            if not _check_wait(deal, step):
                continue
            condition_met = _check_condition(deal, step)
            next_id = _get_next_step_id(campaign, current_step_id, condition_met)
            now = datetime.now(timezone.utc)
            deals_col.update_one(
                {"_id": deal._id},
                {"$set": {
                    "sequence_position": next_id,
                    "sequence_last_step_at": now,
                    "sequence_done": next_id is None,
                }},
            )
            continue

        task_type = _task_type_for_step(step)
        if task_type is None:
            next_id = _get_next_step_id(campaign, current_step_id, True)
            deals_col.update_one({"_id": deal._id}, {"$set": {"sequence_position": next_id}})
            continue

        if not _check_wait(deal, step):
            continue

        if not _check_requires(lead_data, step):
            logger.debug(
                "sequence: deal %s skipping step %s (requires not met)",
                deal._id, current_step_id,
            )
            next_id = _get_next_step_id(campaign, current_step_id, True)
            now = datetime.now(timezone.utc)
            deals_col.update_one(
                {"_id": deal._id},
                {"$set": {"sequence_position": next_id, "sequence_last_step_at": now}},
            )
            continue

        _create_task(campaign, deal, task_type, user_id)
        next_id = _get_next_step_id(campaign, current_step_id, True)
        now = datetime.now(timezone.utc)
        deals_col.update_one(
            {"_id": deal._id},
            {"$set": {
                "sequence_position": next_id,
                "sequence_last_step_at": now,
                "sequence_done": next_id is None,
            }},
        )
        tasks_created += 1

    return tasks_created
