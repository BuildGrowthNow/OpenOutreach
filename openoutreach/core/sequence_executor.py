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
    """Follow outgoing edge from current step.

    Edges from condition nodes carry ``data.condition = "yes"`` or ``"no"``.
    Edges in linear (non-branching) sequences carry no condition or ``"always"``.

    condition_met=True  → take the "yes" edge (or any unlabeled/always edge)
    condition_met=False → take the "no" edge; return None if none exists so
                         the caller marks sequence_done=True.
    """
    outgoing = [e for e in campaign.sequence_edges if e["source"] == current_step_id]
    if not outgoing:
        return None

    # First pass: look for an explicit yes/no branch label.
    for edge in outgoing:
        branch = (edge.get("data") or {}).get("condition", "always")
        if condition_met and branch == "yes":
            return edge["target"]
        if not condition_met and branch == "no":
            return edge["target"]

    # Second pass: fall back to an unlabeled / "always" edge (linear sequence).
    # Only when the condition was met — if condition_met=False and there is no
    # "no" branch, return None so the deal is marked done rather than silently
    # advancing down the wrong path.
    if condition_met:
        for edge in outgoing:
            branch = (edge.get("data") or {}).get("condition", "always")
            if branch in ("always", None, ""):
                return edge["target"]
        # All edges are labeled but none matched — take first as last resort.
        return outgoing[0]["target"]

    return None


def _get_step(campaign: Campaign, step_id: str) -> Optional[dict]:
    for s in campaign.sequence_steps:
        if s["id"] == step_id:
            return s
    return None


def _check_wait(deal: Deal, step: dict) -> bool:
    """True if enough time has elapsed since sequence_last_step_at.

    Supports both wait_days and wait_hours. When both are set they are additive.
    A step with zero/absent wait always passes immediately.
    """
    data = step.get("data") or {}
    wait_days = data.get("wait_days", 0) or 0
    wait_hours = data.get("wait_hours", 0) or 0
    if wait_days <= 0 and wait_hours <= 0:
        return True
    if deal.sequence_last_step_at is None:
        return True
    ref = deal.sequence_last_step_at
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    elapsed = datetime.now(timezone.utc) - ref
    return elapsed >= timedelta(days=wait_days, hours=wait_hours)


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
        # Email open tracking: proceed if email was NOT opened.
        # Deal.email_opened_at is stamped by the tracking worker when the pixel fires.
        # Fall back to treating as not-opened if field absent (pre-tracking deals).
        from openoutreach.mongodb.connection import get_mongodb_collection as _gcol
        deals_col_inner = _gcol("deals")
        if deals_col_inner is None:
            return True
        deal_doc = deals_col_inner.find_one({"_id": deal._id}, projection={"email_opened_at": 1})
        return not (deal_doc or {}).get("email_opened_at")
    return True


def _check_requires(lead_data: dict, step: dict) -> bool:
    """True if all fields in step.requires are non-empty on lead."""
    requires = (step.get("data") or {}).get("requires", [])
    for field in requires:
        if field == "api_email":
            contact = lead_data.get("contact_info")
            overlay_email = contact.get("email") if isinstance(contact, dict) else None
            if not lead_data.get("api_email") and not overlay_email:
                return False
        elif not lead_data.get(field):
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


def _create_task(campaign: Campaign, deal: Deal, task_type: str, step_id: str, user_id: str, tasks_col) -> None:
    """Insert a Task row for this sequence step."""
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
        "payload": {"campaign_id": campaign._id, "deal_id": deal._id, "step_id": step_id},
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
    - First visit to an action step: create Task row, leave position at current step
    - Pending/running task exists: wait for execution before advancing
    - Completed/failed task exists: advance sequence_position to next step
    - Wait not elapsed: leave deal for next reconcile cycle
    - Requires not met: advance past step silently
    Returns count of new tasks created.
    """
    if not campaign.sequence_active or not campaign.sequence_steps:
        return 0

    deals_col = get_mongodb_collection("deals")
    leads_col = get_mongodb_collection("leads")
    tasks_col = get_mongodb_collection("tasks")
    if deals_col is None or leads_col is None or tasks_col is None:
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
            step_label = (step.get("data") or {}).get("label") or current_step_id
            missing = [
                f for f in ((step.get("data") or {}).get("requires") or [])
                if not lead_data.get(f)
            ]
            logger.info(
                "sequence: deal %s skipping step %r — missing required fields: %s",
                deal._id, step_label, ", ".join(missing) or "unknown",
            )
            next_id = _get_next_step_id(campaign, current_step_id, True)
            now = datetime.now(timezone.utc)
            deals_col.update_one(
                {"_id": deal._id},
                {"$set": {"sequence_position": next_id, "sequence_last_step_at": now}},
            )
            continue

        # Check if a task for this deal+step already exists.
        # Pending/running: execution in progress — wait.
        # Completed/failed: task ran — advance position now.
        # No task: first visit — create task, stay at this step until it runs.
        existing = tasks_col.find_one(
            {"payload.deal_id": deal._id, "payload.step_id": current_step_id},
            projection={"status": 1},
        )
        if existing is not None:
            status = existing.get("status")
            if status in (Task.STATUS_PENDING, Task.STATUS_RUNNING):
                continue  # wait for execution
            # Completed or failed: advance to next step
            if status == Task.STATUS_FAILED:
                logger.warning(
                    "sequence: task for deal %s step %s failed — advancing past step",
                    deal._id, current_step_id,
                )
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
            continue

        # No task exists yet for this step — create it. Position stays at current step
        # until the task completes (checked above on the next reconcile cycle).
        _create_task(campaign, deal, task_type, current_step_id, user_id, tasks_col)
        tasks_created += 1

    return tasks_created
