"""
Sequence execution engine.

For campaigns with sequence_active=True, resolves which tasks to create for
each active Deal based on its position in the sequence.

Critical constraint: deals with sequence_position=None (not yet started) are
initialized to the first step. Deals in DISCOVERED/QUALIFIED state that belong
to sequence campaigns are owned by the sequence — existing planners exclude them.
"""

import logging
import copy
from datetime import datetime, timedelta, timezone
from typing import Optional

from openoutreach.mongodb.models import Campaign, Deal, Task
from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.crm.models.deal import DealState

logger = logging.getLogger(__name__)


def _record_sequence_event(campaign_id: str, deal_id: str, step_id: str, event: str, reason: str = "") -> None:
    """Best-effort durable audit trail for sequence operations."""
    events = get_mongodb_collection("sequence_events")
    if events is None:
        return
    try:
        if event in {"action_completed", "action_failed", "reply_received", "sequence_stopped"} and events.find_one({
            "campaign_id": str(campaign_id), "deal_id": str(deal_id), "step_id": str(step_id), "event": event,
        }):
            return
        events.insert_one({
            "campaign_id": str(campaign_id), "deal_id": str(deal_id),
            "step_id": str(step_id), "event": event, "reason": reason,
            "created_at": datetime.now(timezone.utc),
        })
    except Exception:
        logger.debug("sequence event write failed", exc_info=True)


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


def _step_message_config(campaign: Campaign, step_id: str) -> dict:
    from openoutreach.core.sequence_message import message_config
    return message_config(_get_step(campaign, step_id))


def _effective_stop_on_reply(campaign: Campaign, step_id: str) -> bool:
    """Resolve the node policy once so every executor (including cloud) agrees."""
    config = _step_message_config(campaign, step_id)
    safety_defaults = getattr(campaign, "safety_defaults", {}) or {}
    return bool(config.get("stop_on_reply", True) or safety_defaults.get("stop_on_reply", False))


def _stop_on_reply_for_step(deal: Deal, step_type: str, message_config: dict, safety_defaults: dict) -> bool:
    """Use the previous send's policy until the next message is delivered."""
    persisted_policy = getattr(deal, "sequence_stop_on_reply", None)
    if persisted_policy is not None and (
        step_type != "action" or getattr(deal, "sequence_last_message_at", None) is not None
    ):
        return bool(persisted_policy)
    return message_config.get("stop_on_reply", safety_defaults.get("stop_on_reply", True)) is not False


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


def _check_condition(deal: Deal, step: dict, lead_data: Optional[dict] = None) -> str:
    """Return ``yes``, ``no`` or ``waiting`` for a condition node."""
    step_data = step.get("data") or {}
    condition = step_data.get("condition")
    if condition in (None, "always"):
        return "yes"
    # An event may happen after the action sends but before reconciliation
    # advances the graph. Prefer the actual message timestamp for the window.
    since = deal.sequence_last_message_at or deal.sequence_last_step_at
    if since and since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    observation_end = None
    if since and step_data.get("observation_window_hours"):
        observation_end = since + timedelta(hours=float(step_data["observation_window_hours"]))

    if lead_data is None:
        leads = get_mongodb_collection("leads")
        lead_data = leads.find_one({"_id": deal.lead_id}) if leads is not None else {}
    if not isinstance(lead_data, dict):
        lead_data = {}
    contact = lead_data.get("contact_info") if isinstance(lead_data, dict) else {}
    has_email = bool(lead_data.get("api_email") or (contact or {}).get("email"))
    has_phone = bool(lead_data.get("phone") or (contact or {}).get("phone"))
    if condition == "lead_has_email":
        return "yes" if has_email else "no"
    if condition == "lead_has_phone":
        return "yes" if has_phone else "no"

    messages_col = get_mongodb_collection("chat_messages")
    reply_query: dict = {"deal_id": deal._id, "is_outgoing": False}
    if since:
        reply_query["creation_date"] = {"$gte": since}
    if observation_end:
        reply_query["creation_date"]["$lte"] = observation_end
    has_reply = bool(messages_col and messages_col.count_documents(reply_query) > 0)
    # Keep old persisted graphs executable while new writes use the explicit
    # condition names. They are intentionally not accepted by the validator.
    if condition in {"replied", "reply_received"}:
        if has_reply:
            return "yes"
        return "waiting" if observation_end and now < observation_end else "no"
    if condition == "no_reply":
        if has_reply:
            return "no"
        return "waiting" if observation_end and now < observation_end else "yes"

    events = get_mongodb_collection("tracking_events")
    event_query: dict = {"deal_id": str(deal._id)}
    if since:
        event_query["created_at"] = {"$gte": since}
    if observation_end:
        event_query["created_at"]["$lte"] = observation_end
    event_query["event"] = "open"
    has_open = bool(events and events.count_documents(event_query) > 0)
    if not has_open:
        deals = get_mongodb_collection("deals")
        current = deals.find_one({"_id": deal._id}, {"email_opened_at": 1}) if deals is not None else None
        opened_at = (current or {}).get("email_opened_at")
        has_open = bool(
            opened_at
            and (not since or opened_at >= since)
            and (not observation_end or opened_at <= observation_end)
        )
    if condition == "email_opened":
        if has_open:
            return "yes"
        return "waiting" if observation_end and now < observation_end else "no"
    if condition == "email_not_opened":
        if has_open:
            return "no"
        return "waiting" if observation_end and now < observation_end else "yes"
    if condition == "no_open":
        return "no" if has_open else "yes"

    link_key = (step.get("data") or {}).get("link_key")
    link_id = (step.get("data") or {}).get("link_asset_id")
    links = get_mongodb_collection("tracked_links")
    if not link_id and link_key and links is not None:
        link = links.find_one({"campaign_id": deal.campaign_id, "key": link_key}, {"_id": 1})
        link_id = (link or {}).get("_id")
    click_query: dict = {"deal_id": str(deal._id), "event": "click"}
    if link_id:
        click_query["tracked_link_id"] = str(link_id)
    if since:
        click_query["created_at"] = {"$gte": since}
    if observation_end:
        click_query["created_at"]["$lte"] = observation_end
    has_click = bool(events and events.count_documents(click_query) > 0)
    if condition == "link_clicked":
        if has_click:
            return "yes"
        return "waiting" if observation_end and now < observation_end else "no"
    if condition == "link_not_clicked":
        if has_click:
            return "no"
        return "waiting" if observation_end and now < observation_end else "yes"
    # Invalid conditions are rejected before activation; fail closed at runtime.
    return "no"


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
    # Deterministic IDs make reconciliation idempotent even if two daemon
    # workers race between the existence check and creation.
    task_id = f"sequence:{campaign._id}:{deal._id}:{step_id}"
    stop_on_reply = _effective_stop_on_reply(campaign, step_id)
    tasks_col.update_one({"_id": task_id}, {"$setOnInsert": {
        "_id": task_id,
        "task_type": task_type,
        "status": Task.STATUS_PENDING,
        "scheduled_at": now,
        "payload": {
            "campaign_id": campaign._id,
            "deal_id": deal._id,
            "step_id": step_id,
            "message": _step_message_config(campaign, step_id),
            "stop_on_reply": stop_on_reply,
        },
        "user_id": user_id,
        # Task.claim_next uses this field as the session owner.  WhatsApp
        # sessions are keyed by whatsapp_profile_id (not the LinkedIn profile
        # attached to the campaign), so sequence WA tasks must carry that ID.
        "linkedin_profile_id": (
            campaign.whatsapp_profile_id
            if channel == "whatsapp"
            else campaign.linkedin_profile_id
        ),
        "channel": channel,
        "created_at": now,
    }}, upsert=True)


def _run_internal_action(campaign: Campaign, deal: Deal, step: dict, user_id: str) -> bool:
    """Deliver an internal notification exactly once per recipient and step."""
    notifications = get_mongodb_collection("notifications")
    if notifications is None:
        return False
    from openoutreach.mongodb.dal import NotificationDAL
    from openoutreach.mongodb.models_extended import Notification

    data = step.get("data") or {}
    message = data.get("message") or data
    action_key = f"sequence:{campaign._id}:{deal._id}:{data.get('step_id') or step.get('id')}"
    body = str(message.get("body") or message.get("prompt") or data.get("label") or "Campaign workflow notification")
    title = str(data.get("label") or "Campaign workflow notification")
    for recipient_id in campaign.get_all_user_ids() or [user_id]:
        if notifications.find_one({"recipient_id": recipient_id, "data.sequence_action_key": action_key}):
            continue
        NotificationDAL.create_notification(
            recipient_id=recipient_id,
            notification_type=Notification.TYPE_SYSTEM_ANNOUNCEMENT,
            title=title,
            message=body,
            campaign_id=campaign._id,
            deal_id=deal._id,
            data={"sequence_action_key": action_key},
        )
    return True


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
        # Sequence position is independent of the legacy funnel state.  Email
        # actions move deals into these states and must not strand later nodes.
        DealState.EMAIL_QUEUED,
        DealState.EMAIL_SENT,
        DealState.EMAIL_OPENED,
        DealState.EMAIL_REPLIED,
        DealState.EMAIL_BOUNCED,
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
        # Short lease prevents two daemon instances from advancing the same
        # deal concurrently. Expiry makes crashes self-healing.
        lock_until = datetime.now(timezone.utc) + timedelta(seconds=45)
        claimed = deals_col.update_one(
            {"_id": doc["_id"], "$or": [
                {"sequence_lock_until": {"$exists": False}},
                {"sequence_lock_until": {"$lte": datetime.now(timezone.utc)}},
            ]},
            {"$set": {"sequence_lock_until": lock_until}},
        )
        if getattr(claimed, "modified_count", 0) != 1:
            continue
        deal = Deal.from_dict(deals_col.find_one({"_id": doc["_id"]}) or doc)
        lead_data = leads_col.find_one({"_id": deal.lead_id}) or {}

        # A lead keeps the graph revision it entered. Campaign edits therefore
        # affect new leads without orphaning an in-flight lead on a changed
        # node or edge.
        deal_campaign = copy.copy(campaign)
        if deal.sequence_graph_snapshot:
            deal_campaign.sequence_steps = deal.sequence_graph_snapshot.get("steps", [])
            deal_campaign.sequence_edges = deal.sequence_graph_snapshot.get("edges", [])
        else:
            snapshot = {
                "steps": copy.deepcopy(campaign.sequence_steps),
                "edges": copy.deepcopy(campaign.sequence_edges),
                "revision": getattr(campaign, "sequence_revision", 1),
            }
            deals_col.update_one(
                {"_id": deal._id},
                {"$set": {"sequence_graph_snapshot": snapshot, "sequence_revision": snapshot["revision"]}},
            )
            deal.sequence_graph_snapshot = snapshot
            deal.sequence_revision = snapshot["revision"]

        if deal.state in (DealState.EMAIL_REPLIED, DealState.EMAIL_BOUNCED):
            _record_sequence_event(campaign._id, deal._id, deal.sequence_position or "", "sequence_stopped", str(deal.state.value))
            deals_col.update_one(
                {"_id": deal._id},
                {"$set": {"sequence_done": True, "sequence_terminal_reason": str(deal.state.value)}},
            )
            continue

        if lead_data.get("email_unsubscribed"):
            _record_sequence_event(campaign._id, deal._id, deal.sequence_position or "", "sequence_stopped", "unsubscribe")
            deals_col.update_one(
                {"_id": deal._id},
                {"$set": {"sequence_done": True, "sequence_terminal_reason": "unsubscribe"}},
            )
            continue

        first_step_id = _get_first_step_id(deal_campaign)
        current_step_id = str(deal.sequence_position or first_step_id or "")
        if not current_step_id:
            logger.warning("sequence: campaign %s has no entry step", campaign._id)
            continue
        step = _get_step(deal_campaign, current_step_id)
        if step is None:
            logger.warning("sequence: step %s not found in campaign %s", current_step_id, campaign._id)
            continue

        step_type = str(step.get("type") or "")
        _record_sequence_event(campaign._id, deal._id, current_step_id, "node_entered")

        # Give reply/no-reply condition nodes a chance to route first. The
        # stop policy belongs to the sending action that created the current
        # observation window, not to this wait/condition node.
        inbound_reply = _has_inbound_reply(deal)
        step_data = step.get("data") or {}
        message_config = step_data.get("message") or step_data
        safety_defaults = getattr(campaign, "safety_defaults", {}) or {}
        stop_on_reply = _stop_on_reply_for_step(deal, step_type, message_config, safety_defaults)
        reply_condition = step_type == "condition" and step_data.get("condition") in (
            "replied", "no_reply", "reply_received"
        )
        if inbound_reply:
            _record_sequence_event(campaign._id, deal._id, current_step_id, "reply_received")
        if inbound_reply and stop_on_reply and not reply_condition:
            _record_sequence_event(campaign._id, deal._id, current_step_id, "sequence_stopped", "reply_received")
            deals_col.update_one(
                {"_id": deal._id},
                {"$set": {"sequence_done": True}},
            )
            logger.debug("sequence: deal %s stopped on reply", deal._id)
            continue

        if step_type == "end":
            _record_sequence_event(campaign._id, deal._id, current_step_id, "sequence_stopped", "end_node")
            deals_col.update_one({"_id": deal._id}, {"$set": {"sequence_done": True}})
            continue

        if step_type == "wait":
            if not _check_wait(deal, step):
                continue
            # A wait is always linear. Any stray legacy condition field on a
            # wait node must not turn a timing node into an implicit branch.
            next_id = _get_next_step_id(deal_campaign, current_step_id, True)
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

        if step_type == "condition":
            if not _check_wait(deal, step):
                continue
            condition_result = _check_condition(deal, step, lead_data)
            if condition_result == "waiting":
                _record_sequence_event(
                    campaign._id, deal._id, current_step_id, "condition_waiting",
                    str((step.get("data") or {}).get("condition")),
                )
                continue
            condition_met = condition_result == "yes"
            _record_sequence_event(
                campaign._id, deal._id, current_step_id, "condition_evaluated",
                f"{(step.get('data') or {}).get('condition')}:{condition_result}",
            )
            next_id = _get_next_step_id(deal_campaign, current_step_id, condition_met)
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
            if step_type == "action" and step_data.get("action") in {"notify_internal", "internal_notification"}:
                _record_sequence_event(campaign._id, deal._id, current_step_id, "action_scheduled", "internal_notification")
                try:
                    completed = _run_internal_action(deal_campaign, deal, step, user_id)
                except Exception:
                    logger.exception("sequence: internal action failed for deal %s step %s", deal._id, current_step_id)
                    completed = False
                if not completed:
                    _record_sequence_event(campaign._id, deal._id, current_step_id, "action_failed", "internal_notification")
                    continue
                _record_sequence_event(campaign._id, deal._id, current_step_id, "action_completed", "internal_notification")
            next_id = _get_next_step_id(deal_campaign, current_step_id, True)
            deals_col.update_one({"_id": deal._id}, {"$set": {"sequence_position": next_id, "sequence_last_step_at": datetime.now(timezone.utc), "sequence_done": next_id is None}})
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
            _record_sequence_event(campaign._id, deal._id, current_step_id, "skipped", "missing_required_data")
            next_id = _get_next_step_id(deal_campaign, current_step_id, True)
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
            projection={"status": 1, "retry_count": 1},
        )
        if existing is not None:
            status = existing.get("status")
            if status in (Task.STATUS_PENDING, Task.STATUS_RUNNING):
                continue  # wait for execution
            if status == Task.STATUS_CANCELLED:
                # Deactivation cancels pending sequence work so it cannot run
                # while the graph is being edited.  Cancellation is not a
                # completed outreach action: when the sequence is activated
                # again, put the deterministic task back in the queue and
                # leave the lead on this node.
                tasks_col.update_one(
                    {"_id": existing.get("_id")},
                    {"$set": {
                        "status": Task.STATUS_PENDING,
                        "scheduled_at": datetime.now(timezone.utc),
                        "cancel_reason": "",
                    }},
                )
                _record_sequence_event(campaign._id, deal._id, current_step_id, "action_requeued", "sequence_reactivated")
                continue
            if status == Task.STATUS_FAILED:
                retries = int(existing.get("retry_count", 0) or 0)
                if retries < 3:
                    _record_sequence_event(campaign._id, deal._id, current_step_id, "action_failed", "retry_pending")
                    tasks_col.update_one(
                        {"_id": existing.get("_id")},
                        {"$set": {"status": Task.STATUS_PENDING, "scheduled_at": datetime.now(timezone.utc)}, "$inc": {"retry_count": 1}},
                    )
                    logger.warning("sequence: retrying failed task for deal %s step %s (%d/3)", deal._id, current_step_id, retries + 1)
                    continue
                logger.error("sequence: task for deal %s step %s exhausted retries", deal._id, current_step_id)
                _record_sequence_event(campaign._id, deal._id, current_step_id, "action_failed", "retries_exhausted")
                _record_sequence_event(campaign._id, deal._id, current_step_id, "sequence_stopped", "task_retries_exhausted")
                deals_col.update_one({"_id": deal._id}, {"$set": {"sequence_done": True, "sequence_error": "task_retries_exhausted"}})
                continue
            # Completed: advance to next step.
            _record_sequence_event(campaign._id, deal._id, current_step_id, "action_completed", task_type)
            next_id = _get_next_step_id(deal_campaign, current_step_id, True)
            now = datetime.now(timezone.utc)
            # Senders stamp the real delivery time. Falling back to now keeps
            # old tasks executable while avoiding a narrowed click window.
            transition_at = getattr(deal, "sequence_last_message_at", None) or now
            deals_col.update_one(
                {"_id": deal._id},
                {"$set": {
                    "sequence_position": next_id,
                    "sequence_last_step_at": transition_at,
                    "sequence_done": next_id is None,
                }},
            )
            continue

        # No task exists yet for this step — create it. Position stays at current step
        # until the task completes (checked above on the next reconcile cycle).
        _create_task(deal_campaign, deal, task_type, current_step_id, user_id, tasks_col)
        _record_sequence_event(campaign._id, deal._id, current_step_id, "task_created", task_type)
        _record_sequence_event(campaign._id, deal._id, current_step_id, "action_scheduled", task_type)
        tasks_created += 1

    return tasks_created
