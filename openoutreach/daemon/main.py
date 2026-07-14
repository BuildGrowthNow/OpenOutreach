# openoutreach/daemon/main.py
"""
Pure Python daemon for OpenOutreach - no Django dependencies.
Replaces openoutreach/core/daemon.py with MongoDB-native implementation.
"""
from __future__ import annotations

import logging
import random
import sys
import time
from datetime import timedelta
from zoneinfo import ZoneInfo
from typing import Optional, Dict, Any
from dataclasses import dataclass

from termcolor import colored
from pydantic_ai.exceptions import ModelHTTPError

from openoutreach.config import settings
from openoutreach.mongodb import models
from openoutreach.mongodb.dal import TaskDAL, CampaignDAL
from openoutreach.mongodb.connection import initialize_mongodb_connection
from openoutreach.mongodb.indexes import ensure_all_indexes

# Import handlers and utils
from linkedin_cli.exceptions import AuthenticationError, CheckpointChallengeError
from openoutreach.core.conf import CAMPAIGN_CONFIG

logger = logging.getLogger(__name__)


@dataclass
class DaemonConfig:
    """Daemon configuration."""
    heartbeat_interval: int = 300  # 5 minutes
    heartbeat_slice: int = 60  # wake every minute during long sleeps
    health_check_interval: int = 3600  # Run health check every hour
    auth_poll_interval: int = 30  # seconds between cookie checks


# Task handlers (these still work with the session object)
_HANDLERS = {}


def _register_handlers():
    """Lazy-load task handlers to avoid circular imports."""
    global _HANDLERS
    if _HANDLERS:
        return

    from openoutreach.linkedin.tasks.check_pending import handle_check_pending
    from openoutreach.linkedin.tasks.connect import handle_connect
    from openoutreach.linkedin.tasks.follow_up import handle_follow_up
    from openoutreach.linkedin.tasks.send_manual_message import handle_send_manual_message

    _HANDLERS = {
        "connect": handle_connect,
        "check_pending": handle_check_pending,
        "follow_up": handle_follow_up,
        "send_manual_message": handle_send_manual_message,
    }


def _notify_auth_required(user_id: str, reason: str) -> None:
    """Create a user notification for authentication required."""
    try:
        from openoutreach.mongodb.dal import NotificationDAL
        NotificationDAL.create_notification(
            recipient_id=user_id,
            notification_type=models.Notification.TYPE_CAMPAIGN_ERROR,
            title="LinkedIn Authentication Required",
            message=f"Authentication failed: {reason}. Please add valid LinkedIn credentials in Settings → LinkedIn Connection.",
        )
    except Exception as e:
        logger.debug("Could not create auth notification: %s", e)


def _notify_checkpoint_challenge(user_id: str, url: str) -> None:
    """Create a user notification for checkpoint challenge."""
    try:
        from openoutreach.mongodb.dal import NotificationDAL
        NotificationDAL.create_notification(
            recipient_id=user_id,
            notification_type=models.Notification.TYPE_CAMPAIGN_ERROR,
            title="LinkedIn Challenge Required",
            message=f"LinkedIn requires additional verification. Complete the challenge at: {url}",
            data={"challenge_url": url, "requires_action": True},
        )
    except Exception as e:
        logger.debug("Could not create checkpoint notification: %s", e)


def _run_health_checks(campaigns: list) -> None:
    """Run health checks for all campaigns."""
    # TODO: Port health monitor to use MongoDB models directly
    logger.debug("Health checks temporarily disabled during migration")
    pass


# ── Cloud promo ──────────────────────────────────────────────────────

_CLOUD_MESSAGES = [
    "Tired of keeping your laptop open? Run your pipeline in the cloud for $49/mo",
    "You already trust the engine. Now let it run without you babysitting your laptop",
    "The AI gets smarter with every lead. Let it run 24/7 on Cloud instead of only when your laptop is open",
    "Miss a day and the pipeline stalls — follow-ups go cold, new candidates don't get discovered. Cloud keeps it running",
    "The tool got good enough that running it locally became a job. Cloud fixes that",
    "☁  OpenOutreach Cloud: same AI, same code, zero ops. One command and you're live",
    "🧠 Your AI sales team, running in the cloud. $49/mo",
    "Smart founders shouldn't be acting like robots. Let the AI handle outreach while you build your product",
    "Your leads are compounding. Your laptop shouldn't be the bottleneck",
    "⚡ Competitors charge $50-100/mo for template bots. Cloud gives you autonomous AI discovery for $49/mo",
]

_CLOUD_COLORS = ["cyan", "green", "yellow", "magenta"]


class _CloudPromoRotator:
    """Logs a Cloud promo message at most once every *interval* seconds."""

    def __init__(self, interval: float = 120):
        self._interval = interval
        self._last = 0.0

    def maybe_log(self):
        now = time.monotonic()
        if now - self._last < self._interval:
            return
        self._last = now
        msg = random.choice(_CLOUD_MESSAGES)
        color = random.choice(_CLOUD_COLORS)
        logger.info(colored(msg, color, attrs=["bold"]))


# ── Heartbeat ────────────────────────────────────────────────────────


class Heartbeat:
    """Logs an ``alive — <context>`` line at most once every *interval* seconds."""

    def __init__(self, interval: float = 300):
        self._interval = interval
        self._last = time.monotonic()

    def maybe_log(self, context: str) -> None:
        now = time.monotonic()
        if now - self._last < self._interval:
            return
        self._last = now
        logger.info(colored("alive", "cyan") + " — %s", context)


def sleep_with_heartbeat(seconds: float, heartbeat: Heartbeat, context: str) -> None:
    """Sleep with periodic heartbeat logs."""
    end = time.monotonic() + seconds
    while True:
        remaining = end - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(60, remaining))  # Wake every minute
        heartbeat.maybe_log(context)


# ── Human-rhythm pacing ──────────────────────────────────────────────


class _HumanRhythmBreak:
    """Wall-clock burst timer that injects a random break between bursts."""

    def __init__(self, heartbeat: Heartbeat):
        self._heartbeat = heartbeat
        self._new_burst()

    def _new_burst(self):
        self._burst_start = time.monotonic()
        self._burst_duration = random.uniform(
            CAMPAIGN_CONFIG["burst_min_seconds"],
            CAMPAIGN_CONFIG["burst_max_seconds"],
        )

    def reset(self):
        """Start a fresh burst without taking a break. Use after idle gaps."""
        self._new_burst()

    def maybe_break(self):
        """Sleep a random break and start a new burst if the current one is done."""
        if time.monotonic() - self._burst_start < self._burst_duration:
            return
        break_seconds = random.uniform(
            CAMPAIGN_CONFIG["break_min_seconds"],
            CAMPAIGN_CONFIG["break_max_seconds"],
        )
        logger.info("Taking a %dm break", int(break_seconds // 60))
        sleep_with_heartbeat(
            break_seconds,
            self._heartbeat,
            f"on break, {int(break_seconds // 60)}m total",
        )
        self._new_burst()


# ------------------------------------------------------------------
# Active-hours schedule guard
# ------------------------------------------------------------------


def seconds_until_active() -> float:
    """Return seconds to wait before the next active window, or 0 if active now."""
    config = models.SiteConfig.load(user_id="default")  # TODO: Multi-tenant support
    if not config.enable_active_hours:
        return 0.0

    tz = ZoneInfo(config.active_timezone)
    from datetime import datetime
    now = datetime.now(tz)

    # Parse active days (comma-separated: 1=Monday, 7=Sunday)
    try:
        active_days = set(int(d.strip()) for d in config.active_days.split(",") if d.strip())
    except (ValueError, AttributeError):
        active_days = {1, 2, 3, 4, 5}  # Default to weekdays

    # Check if today is an active day
    current_weekday = now.weekday() + 1
    if current_weekday not in active_days:
        # Find next active day
        days_ahead = 1
        while days_ahead <= 7:
            next_day = (current_weekday + days_ahead - 1) % 7 + 1
            if next_day in active_days:
                candidate = now.replace(
                    hour=config.active_start_hour,
                    minute=0,
                    second=0,
                    microsecond=0,
                ) + timedelta(days=days_ahead)
                return (candidate - now).total_seconds()
            days_ahead += 1
        # Fallback
        candidate = now.replace(
            hour=config.active_start_hour,
            minute=0,
            second=0,
            microsecond=0,
        ) + timedelta(days=1)
        return (candidate - now).total_seconds()

    # Today is active - check if we're within hours
    if config.active_start_hour <= now.hour < config.active_end_hour:
        return 0.0

    # Outside active hours today - wait until start hour
    candidate = now.replace(
        hour=config.active_start_hour,
        minute=0,
        second=0,
        microsecond=0,
    )
    if candidate <= now:
        # Past today's window - jump to next active day
        days_ahead = 1
        while days_ahead <= 7:
            next_day = (current_weekday + days_ahead - 1) % 7 + 1
            if next_day in active_days:
                candidate = now.replace(
                    hour=config.active_start_hour,
                    minute=0,
                    second=0,
                    microsecond=0,
                ) + timedelta(days=days_ahead)
                break
            days_ahead += 1
    return (candidate - now).total_seconds()


# ------------------------------------------------------------------
# Checkpoint handling
# ------------------------------------------------------------------


def _handle_checkpoint(user_id: str, task: models.Task, url: str) -> None:
    """Handle checkpoint challenge by notifying user and marking task failed."""
    logger.warning(
        colored(
            f"CHECKPOINT CHALLENGE — user {user_id}",
            "yellow",
            attrs=["bold"],
        )
    )
    logger.warning("Challenge URL: %s", url)
    logger.warning("User must complete challenge via frontend before tasks resume")

    _notify_checkpoint_challenge(user_id, url)
    TaskDAL.mark_task_failed(task._id, error_message=f"Checkpoint challenge required: {url}")


# ------------------------------------------------------------------
# Qualifiers builder
# ------------------------------------------------------------------


def _build_qualifiers(campaigns, cfg, kit_model=None):
    """Create a qualifier for every campaign, keyed by campaign ID."""
    from openoutreach.linkedin.ml.qualifier import BayesianQualifier, KitQualifier

    qualifiers: Dict[str, Any] = {}
    for campaign in campaigns:
        if campaign.is_freemium:
            if kit_model is None:
                continue
            qualifiers[campaign._id] = KitQualifier(kit_model)
        else:
            q = BayesianQualifier(
                seed=42,
                n_mc_samples=cfg["qualification_n_mc_samples"],
                campaign=campaign,
            )
            # TODO: Load labeled arrays from MongoDB
            # X, y = Lead.get_labeled_arrays(campaign)
            # if len(X) > 0:
            #     q.warm_start(X, y)
            qualifiers[campaign._id] = q

    return qualifiers


# ------------------------------------------------------------------
# Main daemon loop
# ------------------------------------------------------------------


def run_daemon(session=None, config: Optional[DaemonConfig] = None):
    """Run the OpenOutreach daemon - pure Python, no Django.

    Args:
        session: AccountSession instance (passed from legacy launcher)
        config: DaemonConfig instance (defaults to production values)
    """
    if config is None:
        config = DaemonConfig()

    # Initialize MongoDB
    initialize_mongodb_connection()
    ensure_all_indexes()

    # Register task handlers
    _register_handlers()

    # Load configuration
    cfg = CAMPAIGN_CONFIG

    # Track authentication state
    _authenticated = False

    # Get user's campaigns (for now, use first user - TODO: multi-tenant)
    campaigns = CampaignDAL.get_active_campaigns(user_id=None)

    if not campaigns:
        logger.warning("No campaigns found — daemon will idle until a campaign is created")
    else:
        logger.info(
            colored("Daemon started", "green", attrs=["bold"])
            + " — %d campaigns, task queue worker (lazy auth)",
            len(campaigns),
        )

    # Load kit model for freemium campaigns
    kit = None
    try:
        from openoutreach.linkedin.ml.hub import fetch_kit
        kit = fetch_kit()
    except Exception as e:
        logger.debug("Could not load kit model: %s", e)

    qualifiers = _build_qualifiers(campaigns, cfg, kit_model=kit["model"] if kit else None)

    heartbeat = Heartbeat(interval=config.heartbeat_interval)
    rhythm = _HumanRhythmBreak(heartbeat)

    # Main daemon loop
    while True:
        pause = seconds_until_active()
        if pause > 0:
            h, m = int(pause // 3600), int(pause % 3600 // 60)
            logger.info("Outside active hours — sleeping %dh%02dm", h, m)
            sleep_with_heartbeat(
                pause,
                heartbeat,
                f"outside active hours, {h}h{m:02d}m left",
            )
            rhythm.reset()
            continue

        # Claim next task atomically
        task = TaskDAL.claim_next_task()
        if task is None:
            # Nothing ready — reconcile the queue
            from openoutreach.core.scheduler import reconcile
            if session:
                reconcile(session)

            # Check seconds to next task
            pending_count = TaskDAL.get_pending_tasks_count()
            if pending_count == 0:
                logger.info("Queue empty after reconcile — sleeping 1h")
                sleep_with_heartbeat(3600, heartbeat, "queue empty")
                rhythm.reset()
                continue

            # Sleep until next task
            logger.info("Next task pending — sleeping 60s")
            sleep_with_heartbeat(60, heartbeat, "waiting for next task")
            rhythm.reset()
            continue

        # Get campaign for this task
        campaign = models.Campaign.get(task.payload.get("campaign_id"))
        if not campaign:
            error_msg = f"Campaign {task.payload.get('campaign_id')} not found"
            logger.error("[%s] %s", task.task_type, error_msg)
            TaskDAL.mark_task_failed(task._id, error_message=error_msg)
            continue

        # Skip tasks for non-active campaigns
        if campaign.status != models.Campaign.Status.ACTIVE:
            logger.debug(
                "[%s] Skipping task for campaign %s (status=%s)",
                task.task_type,
                campaign._id,
                campaign.status,
            )
            TaskDAL.mark_task_failed(
                task._id,
                error_message=f"Campaign status is {campaign.status}, not active"
            )
            continue

        # Lazy auth: authenticate session on first task claim
        if not _authenticated and session:
            logger.info("First task claimed — authenticating session")
            try:
                session.ensure_browser()
                _authenticated = True
                logger.info("Session authenticated successfully")

                # Sync credential profile after successful auth
                try:
                    profile_data = session.self_profile
                    public_id = profile_data.get("public_identifier", "")
                    if public_id:
                        # TODO: Update LinkedInCredentials in MongoDB
                        logger.info("Synced credential username: %s", public_id)
                except Exception as exc:
                    logger.debug("Could not sync credential profile: %s", exc)

            except CheckpointChallengeError as exc:
                logger.warning("LinkedIn checkpoint detected at %s", exc.url)
                _notify_checkpoint_challenge(campaign.user_id, exc.url)
                TaskDAL.mark_task_failed(task._id, f"Checkpoint challenge: {exc.url}")
                continue
            except AuthenticationError as exc:
                logger.error("Authentication failed: %s", exc)
                _notify_auth_required(campaign.user_id, str(exc))
                TaskDAL.mark_task_failed(task._id, f"Authentication required: {exc}")
                continue

        # Execute task
        handler = _HANDLERS.get(task.task_type)
        if handler is None:
            error_msg = f"Unknown task type: {task.task_type}"
            logger.error("[%s] %s", task.task_type, error_msg)
            TaskDAL.mark_task_failed(task._id, error_message=error_msg)
            continue

        try:
            if session:
                session.campaign = campaign
                from openoutreach.linkedin.diagnostics import failure_diagnostics
                with failure_diagnostics(session):
                    handler(task, session, qualifiers)
            else:
                error_msg = "Session not available - cannot execute task"
                logger.error("[%s] %s", task.task_type, error_msg)
                TaskDAL.mark_task_failed(task._id, error_message=error_msg)
                continue

        except CheckpointChallengeError as exc:
            _handle_checkpoint(campaign.user_id, task, exc.url)
            _authenticated = False
            continue
        except AuthenticationError:
            logger.warning("Session expired during %s — re-authenticating", task)
            if session:
                try:
                    session.reauthenticate()
                except CheckpointChallengeError as exc:
                    _handle_checkpoint(campaign.user_id, task, exc.url)
                    _authenticated = False
                    continue
                except Exception:
                    logger.exception("Re-authentication failed for %s", task)
            TaskDAL.mark_task_failed(task._id)
            continue
        except ModelHTTPError as e:
            error_msg = f"LLM API error: {str(e)[:200]}"
            TaskDAL.mark_task_failed(task._id, error_message=error_msg)
            logger.error(
                colored("Daemon stopped — LLM API error", "red", attrs=["bold"])
                + "\n%s\nCheck llm_provider, ai_model, llm_api_key in SiteConfig.",
                e,
            )
            return
        except Exception as e:
            import traceback
            error_msg = f"Task execution failed: {traceback.format_exc()[:500]}"
            TaskDAL.mark_task_failed(task._id, error_message=error_msg)
            logger.error(
                colored("[%s] Task FAILED", "red", attrs=["bold"])
                + " (task_id=%s, campaign_id=%s)\n%s",
                task.task_type,
                task._id,
                task.payload.get("campaign_id", "unknown"),
                error_msg,
            )
            continue

        # Mark task completed
        TaskDAL.mark_task_completed(task._id)
        logger.info(
            colored("[%s] Task COMPLETED", "green", attrs=["bold"])
            + " (task_id=%s, campaign_id=%s)",
            task.task_type,
            task._id,
            task.payload.get("campaign_id", "unknown"),
        )

        # Refresh cookies after successful task
        if session:
            try:
                from openoutreach.linkedin.browser.launch import _save_cookies
                _save_cookies(session)
                logger.debug("Refreshed session cookies after task completion")
            except Exception as e:
                logger.debug("Failed to refresh cookies: %s", e)

        # Health checks
        # TODO: Port health checks to MongoDB
        # _run_health_checks(campaigns)

        rhythm.maybe_break()
