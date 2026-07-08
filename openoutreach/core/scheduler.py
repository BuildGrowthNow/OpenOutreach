# openoutreach/core/scheduler.py
"""Per-type 24h planner with dynamic task spacing.

The daemon's task queue is *lazy*: each row carries only ``task_type``,
``campaign_id``, and ``scheduled_at``. The handler resolves a concrete
target (lead/deal) at execution time via a single eligibility query.

This module is the only place that creates ``Task`` rows. The pipeline
moves forward in three layers:

1. **Per-type planner** — ``plan_connect_window``,
   ``plan_follow_up_window``, ``plan_check_pending_window``. Each one,
   when no PENDING task of its type exists for a campaign, computes the
   right slot count ``n`` for the next 24h and spaces tasks according
   to ``SiteConfig.velocity`` (actions per hour). When velocity is high
   (aggressive mode), tasks cluster into bursts; when low, they spread
   uniformly via Poisson spacing.

2. **State-transition hook** — ``on_deal_state_entered(deal)`` only
   updates ``deal.next_check_pending_at`` for PENDING transitions. It
   does **not** insert any Task row. CONNECTED and other transitions
   are no-ops.

3. **Reconcile** — ``reconcile(session)``. Recovers stale RUNNING tasks
   and calls each planner per campaign. The daemon invokes it on startup
   and whenever the queue has no ready task.
"""

from __future__ import annotations

import datetime
import logging
import random
from datetime import datetime as Datetime, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

from openoutreach.core.conf import (
    CAMPAIGN_CONFIG,
    CHECK_PENDING_DAILY_CAP,
)
from openoutreach.crm.models import DealState
from openoutreach.core.models import Task

logger = logging.getLogger(__name__)


# ── Working-hours arithmetic ──────────────────────────────────────────


def _get_active_hours_config():
    """Load active hours configuration from SiteConfig DB singleton."""
    from openoutreach.core.models import SiteConfig
    config = SiteConfig.load()
    return {
        'enabled': config.enable_active_hours,
        'start_hour': config.active_start_hour,
        'end_hour': config.active_end_hour,
        'timezone': config.active_timezone,
        'days': set(int(d.strip()) for d in config.active_days.split(",") if d.strip()) if config.active_days else {1,2,3,4,5}
    }


def _working_intervals(start, end) -> list[tuple]:
    """Return ``[(s, e), ...]`` UTC datetimes for the working portions of
    ``[start, end]``. When ``enable_active_hours`` is False the only
    interval is ``[(start, end)]``."""
    cfg = _get_active_hours_config()
    if not cfg['enabled']:
        return [(start, end)]

    tz = ZoneInfo(cfg['timezone'])
    local_start = start.astimezone(tz)
    local_end = end.astimezone(tz)

    intervals: list[tuple] = []
    day = local_start.date()
    last_day = local_end.date()
    while day <= last_day:
        # Check if this day is active (1=Monday, 7=Sunday)
        weekday = day.weekday() + 1
        if weekday not in cfg['days']:
            day = day + timedelta(days=1)
            continue

        day_active_start = Datetime(
            day.year,
            day.month,
            day.day,
            cfg['start_hour'],
            tzinfo=tz,
        )
        day_active_end = Datetime(
            day.year,
            day.month,
            day.day,
            cfg['end_hour'],
            tzinfo=tz,
        )
        s = max(day_active_start, local_start)
        e = min(day_active_end, local_end)
        if e > s:
            intervals.append((s, e))
        day = day + timedelta(days=1)
    return intervals


def working_seconds_in_window(start, end) -> float:
    """Sum of seconds inside active hours between ``start`` and ``end``.
    Returns ``(end - start).total_seconds()`` when active hours are disabled."""
    cfg = _get_active_hours_config()
    if not cfg['enabled']:
        return max(0.0, (end - start).total_seconds())
    return sum((e - s).total_seconds() for s, e in _working_intervals(start, end))


def velocity_slot_times(now, n: int, velocity: int, horizon_hours: float = 24) -> list:
    """Return ``n`` timestamps spaced according to velocity (actions/hour).

    When velocity is high (>= 30 actions/hr, i.e., <= 2min spacing), tasks
    cluster into immediate bursts. When velocity is low, tasks spread uniformly
    via Poisson spacing across the working window.

    Args:
        now: Start time
        n: Number of slots to create
        velocity: Target actions per hour (from SiteConfig)
        horizon_hours: Planning window (default 24h)

    Returns:
        List of strictly-increasing timestamps
    """
    if n <= 0:
        return []

    end = now + timedelta(hours=horizon_hours)
    intervals = _working_intervals(now, end)
    total_seconds = sum((e - s).total_seconds() for s, e in intervals)
    if total_seconds <= 0:
        return []

    # Compute inter-action delay from velocity (actions/hour)
    # velocity = 60 → 1 action/min, velocity = 30 → 1 action/2min, etc.
    target_spacing_seconds = 3600.0 / max(1, velocity) if velocity > 0 else 3600.0

    # Aggressive mode: velocity >= 30/hr (≤ 2min spacing) → burst immediately
    if target_spacing_seconds <= 120:
        # Cluster all tasks with minimal spacing (5-10 seconds human rhythm)
        times = []
        cursor = now
        for i in range(n):
            times.append(cursor)
            cursor = cursor + timedelta(seconds=random.uniform(5, 10))
        return times

    # Conservative mode: spread uniformly via Poisson
    # Mean spacing from Poisson: total_seconds / (n + 1)
    poisson_mean_spacing = total_seconds / (n + 1)

    # Use the MORE AGGRESSIVE of: velocity target or Poisson mean
    # (if velocity allows 5min spacing but Poisson would give 10min, use 5min)
    effective_spacing = min(target_spacing_seconds, poisson_mean_spacing)

    # If effective spacing is still aggressive, use deterministic spacing
    if effective_spacing < poisson_mean_spacing * 0.5:
        # Linear spacing with jitter
        times = []
        cursor_seconds = 0.0
        for i in range(n):
            # Add jitter (±20% of spacing)
            jitter = random.uniform(-0.2, 0.2) * effective_spacing
            cursor_seconds += effective_spacing + jitter
            if cursor_seconds >= total_seconds:
                break
            times.append(_seconds_to_timestamp(cursor_seconds, intervals))
        return times

    # Otherwise fall back to Poisson (uniform order statistics)
    positions = sorted(random.uniform(0, total_seconds) for _ in range(n))
    times: list = []
    cursor_interval = 0
    cursor_offset = 0.0
    for pos in positions:
        while cursor_interval < len(intervals):
            s, e = intervals[cursor_interval]
            dur = (e - s).total_seconds()
            if pos < cursor_offset + dur:
                times.append(s + timedelta(seconds=pos - cursor_offset))
                break
            cursor_offset += dur
            cursor_interval += 1
    return times


def _seconds_to_timestamp(seconds: float, intervals: list[tuple]):
    """Convert working-seconds offset to UTC timestamp within intervals."""
    cursor_offset = 0.0
    for s, e in intervals:
        dur = (e - s).total_seconds()
        if seconds < cursor_offset + dur:
            return s + timedelta(seconds=seconds - cursor_offset)
        cursor_offset += dur
    # Overflow: return end of last interval
    return intervals[-1][1] if intervals else timezone.now()


# ── Per-type planners ─────────────────────────────────────────────────


def _has_pending(task_type: "Task.TaskType", campaign_id: int) -> bool:
    return Task.objects.filter(
        task_type=task_type,
        status=Task.Status.PENDING,
        payload__campaign_id=campaign_id,
    ).exists()


def _create_lazy_slots(
    task_type: "Task.TaskType", campaign_id: int, times: list
) -> int:
    if not times:
        return 0
    Task.objects.bulk_create(
        [
            Task(
                task_type=task_type,
                scheduled_at=t,
                payload={"campaign_id": campaign_id},
            )
            for t in times
        ]
    )
    return len(times)


def _plan_slots(task_type: "Task.TaskType", campaign_id: int, n: int, velocity: int) -> int:
    """Schedule *n* lazy slots spaced according to velocity.

    When velocity is high (>= 30 actions/hr), tasks fire in immediate bursts.
    When velocity is low, tasks spread uniformly across the 24h working window.

    Args:
        task_type: Type of task to create
        campaign_id: Campaign PK
        n: Number of slots to create
        velocity: Actions per hour (from SiteConfig)
    """
    if n <= 0:
        return 0
    now = timezone.now()
    times = velocity_slot_times(now, n, velocity)
    return _create_lazy_slots(task_type, campaign_id, times)


def plan_connect_window(session, campaign) -> int:
    """Plan the next 24h of connect slots for *campaign*. No-op when a
    PENDING connect task already exists for the campaign.

    Only the daily limit is consulted — LinkedIn's own weekly ceiling
    surfaces at the handler boundary via ``ReachedConnectionLimit``.
    """
    if _has_pending(Task.TaskType.CONNECT, campaign.pk):
        return 0

    from openoutreach.core.models import SiteConfig
    config = SiteConfig.load()

    profile = session.linkedin_profile
    n = max(0, profile.connect_daily_limit - profile._daily_count("connect"))

    if campaign.is_freemium:
        n = int(n * campaign.action_fraction)

    velocity = config.velocity if config.velocity > 0 else 20  # Default 20 actions/hr
    created = _plan_slots(Task.TaskType.CONNECT, campaign.pk, n, velocity)
    if created:
        spacing_desc = "burst mode" if velocity >= 30 else f"velocity={velocity}/hr"
        logger.info(
            "[%s] planned %d connect slots over next 24h (%s, daily=%d)",
            campaign,
            created,
            spacing_desc,
            profile.connect_daily_limit,
        )
    return created


def plan_follow_up_window(session, campaign) -> int:
    """Plan the next 24h of follow-up slots for *campaign*. No-op when a
    PENDING follow-up task already exists for the campaign."""
    if _has_pending(Task.TaskType.FOLLOW_UP, campaign.pk):
        return 0

    from openoutreach.core.models import SiteConfig
    config = SiteConfig.load()

    profile = session.linkedin_profile
    daily_remaining = max(
        0, profile.follow_up_daily_limit - profile._daily_count("follow_up")
    )

    velocity = config.velocity if config.velocity > 0 else 20  # Default 20 actions/hr
    created = _plan_slots(Task.TaskType.FOLLOW_UP, campaign.pk, daily_remaining, velocity)
    if created:
        spacing_desc = "burst mode" if velocity >= 30 else f"velocity={velocity}/hr"
        logger.info(
            "[%s] planned %d follow_up slots over next 24h (%s, daily=%d)",
            campaign,
            created,
            spacing_desc,
            profile.follow_up_daily_limit,
        )
    return created


def plan_check_pending_window(session, campaign) -> int:
    """Plan the next 24h of check_pending slots for *campaign*. Slot count
    matches the PENDING deals whose backoff has expired (or expires
    within the horizon), capped by ``CHECK_PENDING_DAILY_CAP``."""
    from openoutreach.crm.models import Deal
    from openoutreach.core.models import SiteConfig

    if _has_pending(Task.TaskType.CHECK_PENDING, campaign.pk):
        return 0

    config = SiteConfig.load()
    now = timezone.now()
    # Only count deals that are due RIGHT NOW (not future deals within 24h)
    # This matches the handler's query in check_pending.py:_next_due_pending_deal
    n_due = Deal.objects.filter(
        campaign_id=campaign.pk,
        state=DealState.PENDING,
        next_check_pending_at__lte=now,
    ).count()
    n = min(n_due, CHECK_PENDING_DAILY_CAP)

    # Don't create tasks if there are no PENDING deals due in the next 24h
    if n == 0:
        return 0

    velocity = config.velocity if config.velocity > 0 else 20  # Default 20 actions/hr
    created = _plan_slots(Task.TaskType.CHECK_PENDING, campaign.pk, n, velocity)
    if created:
        spacing_desc = "burst mode" if velocity >= 30 else f"velocity={velocity}/hr"
        logger.info(
            "[%s] planned %d check_pending slots over next 24h (%s, due=%d, cap=%d)",
            campaign,
            created,
            spacing_desc,
            n_due,
            CHECK_PENDING_DAILY_CAP,
        )
    return created


# ── Delay helpers ─────────────────────────────────────────────────────


def seconds_until_tomorrow() -> float:
    """Seconds until 00:00 local time — used for daily rate-limit waits."""
    now = timezone.now()
    tomorrow = (now + datetime.timedelta(days=1)).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    return (tomorrow - now).total_seconds()


# ── State-transition hook ─────────────────────────────────────────────


def on_deal_state_entered(deal) -> None:
    """PENDING: stamp ``deal.next_check_pending_at = now + backoff_hours``.
    All other transitions are no-ops (CONNECTED tasks are created lazily
    by the planner, never by state changes)."""
    state = DealState(deal.state)
    if state != DealState.PENDING:
        return

    backoff = deal.backoff_hours or CAMPAIGN_CONFIG["check_pending_recheck_after_hours"]
    # Type: backoff should be a number (int or float)
    deal.next_check_pending_at = timezone.now() + timedelta(hours=float(backoff))  # type: ignore
    deal.save(update_fields=["next_check_pending_at"])


# ── Reconciliation ────────────────────────────────────────────────────


def _recover_stale_running_tasks() -> int:
    """Reset RUNNING tasks to PENDING. RUNNING rows can only linger if the
    daemon crashed mid-task, so they are always stale at reconcile time.

    Also logs detailed information about recovered tasks for debugging.
    """
    running_tasks = list(Task.objects.filter(status=Task.Status.RUNNING))
    if not running_tasks:
        return 0

    count = Task.objects.filter(status=Task.Status.RUNNING).update(
        status=Task.Status.PENDING,
    )

    # Log details of recovered tasks for debugging
    for task in running_tasks:
        error_info = ""
        err_msg = task.get_error_message()
        if err_msg:
            error_info = f" (last error: {err_msg[:100]}...)"
        logger.warning(
            "Recovered stale task: %s campaign_id=%s scheduled_at=%s%s",
            task.task_type,
            task.payload.get("campaign_id", "unknown"),
            task.scheduled_at,
            error_info,
        )

    logger.info("Recovered %d stale running tasks from previous daemon crash", count)
    return count


_PLANNERS = (
    plan_connect_window,
    plan_follow_up_window,
    plan_check_pending_window,
)


def reconcile(session) -> None:
    """Recover stale RUNNING tasks, then ensure every (campaign, task_type)
    whose pending queue is empty gets a fresh 24h plan. Runs on daemon
    startup and whenever the queue has no ready task."""
    _recover_stale_running_tasks()
    for campaign in session.campaigns:
        for planner in _PLANNERS:
            planner(session, campaign)

    pending_count = Task.objects.pending().count()
    logger.info("Task queue reconciled: %d pending tasks", pending_count)
