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
from datetime import datetime as Datetime, timedelta, timezone as tz
from zoneinfo import ZoneInfo

from openoutreach.core.conf import (
    CAMPAIGN_CONFIG,
    CHECK_PENDING_DAILY_CAP,
)
from openoutreach.crm.models import DealState
from openoutreach.mongodb.models import Task

logger = logging.getLogger(__name__)


# ── Working-hours arithmetic ──────────────────────────────────────────


def _get_active_hours_config(user_id: str | None = None):
    """Load active hours configuration from SiteConfig for the given user."""
    from openoutreach.mongodb.models import SiteConfig
    config = SiteConfig.load(user_id=user_id)
    return {
        'enabled': config.enable_active_hours,
        'start_hour': config.active_start_hour,
        'end_hour': config.active_end_hour,
        'timezone': config.active_timezone,
        'days': (set(int(d.strip()) for d in config.active_days.split(",") if d.strip()) if isinstance(config.active_days, str) else set(config.active_days)) if config.active_days else {1,2,3,4,5}
    }


def _working_intervals(start, end, user_id: str | None = None) -> list[tuple]:
    """Return ``[(s, e), ...]`` UTC datetimes for the working portions of
    ``[start, end]``. When ``enable_active_hours`` is False the only
    interval is ``[(start, end)]``."""
    cfg = _get_active_hours_config(user_id=user_id)
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


def working_seconds_in_window(start, end, user_id: str | None = None) -> float:
    """Sum of seconds inside active hours between ``start`` and ``end``.
    Returns ``(end - start).total_seconds()`` when active hours are disabled."""
    cfg = _get_active_hours_config(user_id=user_id)
    if not cfg['enabled']:
        return max(0.0, (end - start).total_seconds())
    return sum((e - s).total_seconds() for s, e in _working_intervals(start, end, user_id=user_id))


def smart_velocity_slot_times(
    now, n: int, velocity: int, limiter_context=None, time_aware: bool = True, horizon_hours: float = 24,
    user_id: str | None = None,
) -> list:
    """Return ``n`` timestamps spaced with smart rate limiting awareness.

    When time_aware=True and limiter_context is provided:
      - Clusters more tasks during business hours (9am-6pm)
      - Reduces tasks during off-hours (night/weekends)
      - Respects detectability score (spaces out more when suspicious)

    When time_aware=False or no context:
      - Falls back to velocity-based spacing

    Args:
        now: Start time
        n: Number of slots to create
        velocity: Target actions per hour
        limiter_context: SmartRateLimitContext instance (optional)
        time_aware: Whether to use time-of-day weighting
        horizon_hours: Planning window (default 24h)
        user_id: Owner's user_id for per-user active hours config

    Returns:
        List of strictly-increasing timestamps
    """
    if n <= 0:
        return []

    # Ensure now is timezone-aware
    if now.tzinfo is None:
        now = now.replace(tzinfo=tz.utc)

    # Fall back to simple velocity spacing if no smart context
    if not time_aware or limiter_context is None:
        return velocity_slot_times(now, n, velocity, horizon_hours, user_id=user_id)

    end = now + timedelta(hours=horizon_hours)
    intervals = _working_intervals(now, end, user_id=user_id)
    if not intervals:
        return []

    # Apply time-of-day weights (more tasks during business hours)
    weighted_intervals = []
    for start, end_time in intervals:
        hour = start.hour
        if 9 <= hour <= 17:  # Business hours
            weight = limiter_context.time_of_day_limit_multiplier * 1.5
        elif 7 <= hour <= 9 or 17 <= hour <= 20:
            weight = limiter_context.time_of_day_limit_multiplier * 1.0
        else:  # Night/early morning
            weight = limiter_context.time_of_day_limit_multiplier * 0.3

        weighted_intervals.append((start, end_time, max(0.1, weight)))

    # Distribute tasks weighted by time-of-day preference
    times = _distribute_weighted(n, weighted_intervals, velocity)

    # Apply detectability jitter (add randomness when score is high)
    if limiter_context.detectability_score > 60:
        times = _add_detectability_jitter(times, limiter_context.detectability_score)

    return times


def _distribute_weighted(n: int, weighted_intervals: list, velocity: int) -> list:
    """Distribute n tasks across weighted intervals according to velocity."""
    total_weight = sum(w for _, _, w in weighted_intervals)
    if total_weight <= 0:
        # Fallback to uniform distribution
        return velocity_slot_times(
            weighted_intervals[0][0] if weighted_intervals else Datetime.now(tz.utc),
            n,
            velocity
        )

    times = []
    target_spacing_seconds = 3600.0 / max(1, velocity)
    remaining = n

    # Allocate slots proportionally by weight; use round() to avoid integer-truncation loss
    for i, (start, end, weight) in enumerate(weighted_intervals):
        if i == len(weighted_intervals) - 1:
            slot_count = remaining  # give all leftover to the last interval
        else:
            slot_count = round(n * (weight / total_weight))
        slot_count = min(slot_count, remaining)

        cursor = start
        for _ in range(slot_count):
            if cursor >= end:
                break
            times.append(cursor)
            remaining -= 1
            jitter = random.uniform(-0.2, 0.2) * target_spacing_seconds
            cursor = cursor + timedelta(seconds=target_spacing_seconds + jitter)

    # Sort and return up to n times
    times.sort()
    return times[:n]


def _add_detectability_jitter(times: list, detectability_score: int) -> list:
    """Add random jitter to task times when detectability is high."""
    jitter_factor = (detectability_score - 60) / 40.0  # 0.0 at score=60, 1.0 at score=100
    jittered = []

    for t in times:
        max_jitter_seconds = 300 * jitter_factor  # up to 5 min jitter at score=100
        jitter = random.uniform(-max_jitter_seconds, max_jitter_seconds)
        jittered.append(t + timedelta(seconds=jitter))

    jittered.sort()
    return jittered


def velocity_slot_times(now, n: int, velocity: int, horizon_hours: float = 24, user_id: str | None = None) -> list:
    """Return ``n`` timestamps spaced according to velocity (actions/hour).

    When velocity is high (>= 30 actions/hr, i.e., <= 2min spacing), tasks
    cluster into immediate bursts. When velocity is low, tasks spread uniformly
    via Poisson spacing across the working window.

    Args:
        now: Start time
        n: Number of slots to create
        velocity: Target actions per hour (from SiteConfig)
        horizon_hours: Planning window (default 24h)
        user_id: Owner's user_id for per-user active hours config

    Returns:
        List of strictly-increasing timestamps
    """
    if n <= 0:
        return []

    end = now + timedelta(hours=horizon_hours)
    intervals = _working_intervals(now, end, user_id=user_id)
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

    # Always fire the first slot immediately so a freshly-played campaign
    # executes at least one action right away rather than waiting hours.
    first_slot = now

    # If effective spacing is still aggressive, use deterministic spacing
    if effective_spacing < poisson_mean_spacing * 0.5:
        # Linear spacing with jitter — first slot is now, rest follow
        times = [first_slot]
        cursor_seconds = 0.0
        for _ in range(n - 1):
            # Add jitter (±20% of spacing)
            jitter = random.uniform(-0.2, 0.2) * effective_spacing
            cursor_seconds += effective_spacing + jitter
            if cursor_seconds >= total_seconds:
                break
            times.append(_seconds_to_timestamp(cursor_seconds, intervals))
        return times

    # Otherwise fall back to Poisson (uniform order statistics)
    # Generate n-1 random positions for the remaining slots
    positions = sorted(random.uniform(0, total_seconds) for _ in range(n - 1))
    times: list = [first_slot]
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
    return intervals[-1][1] if intervals else Datetime.now(tz.utc)


# ── Per-type planners ─────────────────────────────────────────────────


def _has_pending(task_type: str, campaign_id: str, linkedin_profile_id: str | None = None) -> bool:
    """Return True if a PENDING task of this type already exists for the campaign
    and is scheduled within the next 24 hours.

    Past-due PENDING tasks (from a previous session that died before executing)
    are ignored so the planner re-fills the window. They will still be claimed
    and executed by the task loop — this check only gates new slot creation.
    """
    from openoutreach.mongodb.connection import get_mongodb_collection
    col = get_mongodb_collection("tasks")
    if col is None:
        return False
    now = Datetime.now(tz.utc)
    query: dict = {
        "task_type": task_type,
        "status": Task.Status.PENDING,
        "payload.campaign_id": campaign_id,
        "scheduled_at": {"$gte": now},
    }
    if linkedin_profile_id:
        query["linkedin_profile_id"] = linkedin_profile_id
    return col.count_documents(query, limit=1) > 0


def _create_lazy_slots(
    task_type: str, campaign_id: str, times: list,
    linkedin_profile_id: str | None = None,
    user_id: str | None = None,
) -> int:
    if not times:
        return 0
    tasks = [
        Task(
            task_type=task_type,
            scheduled_at=t,
            payload={"campaign_id": campaign_id},
            linkedin_profile_id=linkedin_profile_id,
            user_id=user_id,
        )
        for t in times
    ]
    for task in tasks:
        task.save()
    return len(tasks)


def _plan_slots(
    task_type: str,
    campaign_id: str,
    n: int,
    velocity: int,
    limiter_context=None,
    time_aware: bool = False,
    linkedin_profile_id: str | None = None,
    user_id: str | None = None,
) -> int:
    """Schedule *n* lazy slots spaced according to velocity and smart context."""
    if n <= 0:
        return 0
    now = Datetime.now(tz.utc)

    if time_aware and limiter_context:
        times = smart_velocity_slot_times(now, n, velocity, limiter_context, time_aware=True, user_id=user_id)
    else:
        times = velocity_slot_times(now, n, velocity, user_id=user_id)

    return _create_lazy_slots(
        task_type, campaign_id, times,
        linkedin_profile_id=linkedin_profile_id,
        user_id=user_id,
    )


def plan_connect_window(session, campaign, *, connect_cap: int | None = None) -> int:
    """Plan the next 24h of connect slots for *campaign*. No-op when a
    PENDING connect task already exists for the campaign.

    Only the daily limit is consulted — LinkedIn's own weekly ceiling
    surfaces at the handler boundary via ``ReachedConnectionLimit``.

    ``connect_cap``: when multiple campaigns are active, reconcile() passes
    ``floor(remaining_budget / n_campaigns)`` so the daily budget is shared
    evenly instead of every campaign racing for the same pool.
    """
    profile = session.linkedin_profile

    if _has_pending(Task.TaskType.CONNECT, campaign.pk, linkedin_profile_id=profile.pk):
        return 0

    from openoutreach.mongodb.models import SiteConfig
    from openoutreach.core.rate_limit_presets import get_preset
    config = SiteConfig.load(user_id=profile.user_id)
    n = max(0, profile.connect_daily_limit - profile._daily_count("connect"))
    if connect_cap is not None:
        n = min(n, connect_cap)

    profile_id = profile.pk
    user_id = profile.user_id

    if config.enable_smart_rate_limiting:
        from openoutreach.linkedin.services.smart_rate_limits import SmartRateLimiter
        limiter = SmartRateLimiter(profile)

        preset = get_preset(config.aggressiveness_preset)
        velocity = preset["velocity"]
        time_aware = preset["time_aware"]

        smart_effective = limiter.context.get_effective_limit('connect', campaign)
        n = min(n, int(smart_effective * preset["detectability_multiplier"]))

        created = _plan_slots(
            Task.TaskType.CONNECT, campaign.pk, n, velocity,
            limiter_context=limiter.context, time_aware=time_aware,
            linkedin_profile_id=profile_id, user_id=user_id,
        )
        if created:
            logger.info(
                "[%s] planned %d connect slots (smart: %s, daily=%d)",
                campaign, created, config.aggressiveness_preset,
                profile.connect_daily_limit,
            )
    else:
        velocity = config.velocity if config.velocity > 0 else 20
        created = _plan_slots(
            Task.TaskType.CONNECT, campaign.pk, n, velocity,
            linkedin_profile_id=profile_id, user_id=user_id,
        )
        if created:
            spacing_desc = "burst mode" if velocity >= 30 else f"velocity={velocity}/hr"
            logger.info(
                "[%s] planned %d connect slots (manual: %s, daily=%d)",
                campaign, created, spacing_desc, profile.connect_daily_limit,
            )

    return created


def plan_follow_up_window(session, campaign, *, follow_up_cap: int | None = None) -> int:
    """Plan the next 24h of follow-up slots for *campaign*. No-op when a
    PENDING follow-up task already exists or there are no CONNECTED deals.

    ``follow_up_cap``: when multiple campaigns are active, reconcile() passes
    ``floor(remaining_budget / n_campaigns)`` so the daily budget is shared
    evenly instead of every campaign racing for the same pool.
    """
    profile = session.linkedin_profile

    if _has_pending(Task.TaskType.FOLLOW_UP, campaign.pk, linkedin_profile_id=profile.pk):
        return 0

    from openoutreach.mongodb.connection import get_mongodb_collection
    from openoutreach.crm.models import DealState
    deals_col = get_mongodb_collection("deals")
    if deals_col is not None:
        connected_count = deals_col.count_documents({
            "campaign_id": campaign.pk,
            "state": DealState.CONNECTED,
        })
        if connected_count == 0:
            return 0

    from openoutreach.mongodb.models import SiteConfig
    from openoutreach.core.rate_limit_presets import get_preset

    config = SiteConfig.load(user_id=profile.user_id)
    n = max(0, profile.follow_up_daily_limit - profile._daily_count("follow_up"))
    if follow_up_cap is not None:
        n = min(n, follow_up_cap)

    profile_id = profile.pk
    user_id = profile.user_id

    if config.enable_smart_rate_limiting:
        from openoutreach.linkedin.services.smart_rate_limits import SmartRateLimiter
        limiter = SmartRateLimiter(profile)

        preset = get_preset(config.aggressiveness_preset)
        velocity = preset["velocity"]
        time_aware = preset["time_aware"]

        smart_effective = limiter.context.get_effective_limit('follow_up', campaign)
        n = min(n, int(smart_effective * preset["detectability_multiplier"]))

        created = _plan_slots(
            Task.TaskType.FOLLOW_UP, campaign.pk, n, velocity,
            limiter_context=limiter.context, time_aware=time_aware,
            linkedin_profile_id=profile_id, user_id=user_id,
        )
        if created:
            logger.info(
                "[%s] planned %d follow_up slots (smart: %s, daily=%d)",
                campaign, created, config.aggressiveness_preset,
                profile.follow_up_daily_limit,
            )
    else:
        velocity = config.velocity if config.velocity > 0 else 20
        created = _plan_slots(
            Task.TaskType.FOLLOW_UP, campaign.pk, n, velocity,
            linkedin_profile_id=profile_id, user_id=user_id,
        )
        if created:
            spacing_desc = "burst mode" if velocity >= 30 else f"velocity={velocity}/hr"
            logger.info(
                "[%s] planned %d follow_up slots (manual: %s, daily=%d)",
                campaign, created, spacing_desc, profile.follow_up_daily_limit,
            )

    return created


def plan_check_pending_window(session, campaign) -> int:
    """Plan the next 24h of check_pending slots for *campaign*. Slot count
    matches the PENDING deals whose backoff has expired (or expires
    within the horizon), capped by ``CHECK_PENDING_DAILY_CAP``."""
    from openoutreach.mongodb.models import SiteConfig
    from openoutreach.core.rate_limit_presets import get_preset

    profile = session.linkedin_profile

    if _has_pending(Task.TaskType.CHECK_PENDING, campaign.pk, linkedin_profile_id=profile.pk):
        return 0
    config = SiteConfig.load(user_id=profile.user_id)
    now = Datetime.now(tz.utc)

    from openoutreach.mongodb.connection import get_mongodb_collection
    deals_collection = get_mongodb_collection("deals")
    if deals_collection is None:
        return 0

    n_due = deals_collection.count_documents({
        "campaign_id": campaign.pk,
        "state": DealState.PENDING.value,
        "next_check_pending_at": {"$lte": now},
    })
    n = min(n_due, CHECK_PENDING_DAILY_CAP)

    if n == 0:
        return 0

    profile_id = profile.pk
    user_id = profile.user_id

    if config.enable_smart_rate_limiting:
        from openoutreach.linkedin.services.smart_rate_limits import SmartRateLimiter
        limiter = SmartRateLimiter(profile)

        preset = get_preset(config.aggressiveness_preset)
        velocity = preset["velocity"]
        time_aware = preset["time_aware"]

        created = _plan_slots(
            Task.TaskType.CHECK_PENDING, campaign.pk, n, velocity,
            limiter_context=limiter.context, time_aware=time_aware,
            linkedin_profile_id=profile_id, user_id=user_id,
        )
        if created:
            logger.info(
                "[%s] planned %d check_pending slots (smart: %s, due=%d, cap=%d)",
                campaign, created, config.aggressiveness_preset,
                n_due, CHECK_PENDING_DAILY_CAP,
            )
    else:
        velocity = config.velocity if config.velocity > 0 else 20
        created = _plan_slots(
            Task.TaskType.CHECK_PENDING, campaign.pk, n, velocity,
            linkedin_profile_id=profile_id, user_id=user_id,
        )
        if created:
            spacing_desc = "burst mode" if velocity >= 30 else f"velocity={velocity}/hr"
            logger.info(
                "[%s] planned %d check_pending slots (manual: %s, due=%d, cap=%d)",
                campaign, created, spacing_desc, n_due, CHECK_PENDING_DAILY_CAP,
            )

    return created


# ── Delay helpers ─────────────────────────────────────────────────────


def seconds_until_tomorrow() -> float:
    """Seconds until 00:00 local time — used for daily rate-limit waits."""
    now = Datetime.now(tz.utc)
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
    deal.next_check_pending_at = Datetime.now(tz.utc) + timedelta(hours=float(backoff))  # type: ignore
    deal.save()


# ── Reconciliation ────────────────────────────────────────────────────


STALE_RUNNING_THRESHOLD_MINUTES = 30


def _recover_stale_running_tasks(linkedin_profile_id: str | None = None) -> int:
    """Reset RUNNING tasks older than 30 minutes to PENDING.

    Only tasks that have been RUNNING longer than the threshold are considered
    stale (daemon crash or laptop lid close). Fresh RUNNING tasks are left alone.

    When ``linkedin_profile_id`` is provided only that profile's tasks are
    considered — used by the desktop daemon's API reconcile path so each user's
    reconnect cleans up their own stale tasks without touching others.
    """
    if linkedin_profile_id:
        running_tasks = list(Task.objects.filter(
            status=Task.Status.RUNNING,
            linkedin_profile_id=linkedin_profile_id,
        ))
    else:
        running_tasks = list(Task.objects.filter(status=Task.Status.RUNNING))

    if not running_tasks:
        return 0

    now = Datetime.now(tz.utc)
    threshold = now - timedelta(minutes=STALE_RUNNING_THRESHOLD_MINUTES)

    count = 0
    for task in running_tasks:
        started = task.started_at or task.scheduled_at or task.created_at
        if started and started.tzinfo is None:
            started = started.replace(tzinfo=tz.utc)
        if started and started > threshold:
            continue  # Still fresh — do not reset

        task.status = Task.Status.PENDING
        task.save()
        count += 1

        logger.warning(
            "Recovered stale task: %s campaign_id=%s scheduled_at=%s",
            task.task_type,
            task.payload.get("campaign_id", "unknown"),
            task.scheduled_at,
        )

    if count:
        logger.info("Recovered %d stale running tasks (>%dm old)", count, STALE_RUNNING_THRESHOLD_MINUTES)
    return count


def reconcile(session) -> None:
    """Recover stale RUNNING tasks, then ensure every (campaign, task_type)
    whose pending queue is empty gets a fresh 24h plan. Runs on daemon
    startup and whenever the queue has no ready task.

    When multiple campaigns are active the remaining daily budget for each
    action type is divided evenly so no single campaign can starve the rest.
    """
    _recover_stale_running_tasks()

    campaigns = session.campaigns
    n_campaigns = max(1, len(campaigns))
    profile = session.linkedin_profile

    # Remaining budget across ALL campaigns today
    connect_remaining = max(0, profile.connect_daily_limit - profile._daily_count("connect"))
    follow_up_remaining = max(0, profile.follow_up_daily_limit - profile._daily_count("follow_up"))

    # Each campaign's fair share — floor division so we never exceed the budget
    connect_cap = connect_remaining // n_campaigns
    follow_up_cap = follow_up_remaining // n_campaigns

    if n_campaigns > 1:
        logger.info(
            "Budget split across %d campaigns: connect %d/ea (total %d), follow_up %d/ea (total %d)",
            n_campaigns, connect_cap, connect_remaining, follow_up_cap, follow_up_remaining,
        )

    for campaign in campaigns:
        plan_connect_window(session, campaign, connect_cap=connect_cap)
        plan_follow_up_window(session, campaign, follow_up_cap=follow_up_cap)
        plan_check_pending_window(session, campaign)

    pending_count = Task.objects.pending().count()
    logger.info("Task queue reconciled: %d pending tasks", pending_count)
