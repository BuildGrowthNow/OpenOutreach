# openoutreach/core/daemon.py
from __future__ import annotations

import logging
import random
import sys
import time
from datetime import datetime, timedelta, timezone as tz
from zoneinfo import ZoneInfo

from pydantic_ai.exceptions import ModelHTTPError

from termcolor import colored

from openoutreach.core.conf import CAMPAIGN_CONFIG
from openoutreach.linkedin.diagnostics import failure_diagnostics
from linkedin_cli.exceptions import AuthenticationError, CheckpointChallengeError
from openoutreach.linkedin.ml.qualifier import BayesianQualifier, KitQualifier
from openoutreach.mongodb.models import Task
from openoutreach.linkedin.tasks.check_pending import handle_check_pending
from openoutreach.linkedin.tasks.connect import handle_connect
from openoutreach.linkedin.tasks.follow_up import handle_follow_up
from openoutreach.linkedin.tasks.send_manual_message import handle_send_manual_message

logger = logging.getLogger(__name__)

_HANDLERS = {
    Task.TaskType.CONNECT: handle_connect,
    Task.TaskType.CHECK_PENDING: handle_check_pending,
    Task.TaskType.FOLLOW_UP: handle_follow_up,
    Task.TaskType.SEND_MANUAL_MESSAGE: handle_send_manual_message,
}


def _notify_auth_required(session, reason: str) -> None:
    """Create a user notification for authentication required."""
    try:
        from openoutreach.mongodb.models import Notification

        user_id = session.linkedin_profile.user_id
        if user_id:
            Notification.create_notification(
                user_id=user_id,
                notification_type="campaign_error",
                title="LinkedIn Authentication Required",
                message=f"Authentication failed: {reason}. Please add valid LinkedIn credentials in Settings → LinkedIn Connection.",
            )
    except Exception as e:
        logger.debug("Could not create auth notification: %s", e)


def _notify_checkpoint_challenge(session, url: str) -> None:
    """Create a user notification for checkpoint challenge."""
    try:
        from openoutreach.mongodb.models import Notification

        user_id = session.linkedin_profile.user_id
        if user_id:
            Notification.create_notification(
                user_id=user_id,
                notification_type="campaign_error",
                title="LinkedIn Challenge Required",
                message=f"LinkedIn requires additional verification. Complete the challenge at: {url}",
                metadata={"challenge_url": url, "requires_action": True},
            )
    except Exception as e:
        logger.debug("Could not create checkpoint notification: %s", e)

HEARTBEAT_INTERVAL = 300  # 5 minutes
HEARTBEAT_SLICE = 60  # wake every minute during long sleeps
HEALTH_CHECK_INTERVAL = 3600  # Run health check every hour


def _run_health_checks(session) -> None:
    """Run health checks for all campaigns in the session."""
    from openoutreach.linkedin.models.health import HealthAlert
    from openoutreach.linkedin.services.health_monitor import CampaignHealthMonitor

    logger.debug("Running health checks for %d campaigns", len(session.campaigns))

    for campaign in session.campaigns:
        try:
            monitor = CampaignHealthMonitor(campaign)
            alerts = monitor.run_health_check()

            for alert in alerts:
                alert.save()
                logger.warning(
                    "ALERT: campaign=%s type=%s severity=%s message=%s",
                    campaign.name,
                    alert.alert_type,
                    alert.severity,
                    alert.message,
                )

                # Auto-remediate low/medium severity alerts
                if alert.severity in [
                    HealthAlert.SEVERITY_LOW,
                    HealthAlert.SEVERITY_MEDIUM,
                ]:
                    if monitor.auto_remediate(alert):
                        logger.info(
                            "Auto-remediation applied for alert: %s", alert.message
                        )
        except Exception as e:
            logger.error(
                "Error running health check for campaign %s: %s", campaign.name, e
            )


# ── Cloud promo ──────────────────────────────────────────────────────

_CLOUD_MESSAGES = [
    "Tired of keeping your laptop open? Run your pipeline in the cloud for $49/mo",
    "You already trust the engine. Now let it run without you babysitting your laptop",
    "The AI gets smarter with every lead. Let it run 24/7 on Cloud instead of only when your laptop is open",
    "Miss a day and the pipeline stalls — follow-ups go cold, new candidates don't get discovered. Cloud keeps it running",
    "The tool got good enough that running it locally became a job. Cloud fixes that",
    "\u2601  OpenOutreach Cloud: same AI, same code, zero ops. One command and you're live",
    "\U0001f9e0 Your AI sales team, running in the cloud. $49/mo",
    "Smart founders shouldn't be acting like robots. Let the AI handle outreach while you build your product",
    "Your leads are compounding. Your laptop shouldn't be the bottleneck",
    "\u26a1 Competitors charge $50-100/mo for template bots. Cloud gives you autonomous AI discovery for $49/mo",
    "Other tools need you to build or buy contact lists. OpenOutreach discovers leads autonomously — describe your market and the AI does the rest",
    "Expandi and Waalaxy send templates. OpenOutreach's AI agent reads conversation history and writes personalized follow-ups",
    "Running Docker + VPN yourself? Cloud handles everything — dedicated server, VPN included",
    "Self-hosted setup: 30-60 min. Cloud setup: ~1 min. Same AI, same results",
    "The server costs ~$18/mo. The VPN costs ~$6/mo. You're paying $25/mo for managed ops — if your time is worth more, Cloud pays for itself",
    "Your data never leaves your machine. Cloud is just a disposable execution layer. $49/mo, cancel anytime",
    "mTLS encryption between your machine and the server. The control plane never sees your data",
    "100% open source. Inspect every line of code on GitHub. Cloud runs the exact same codebase — no black box, no lock-in",
    "Switch between self-hosted and Cloud with one command. Download your db.sqlite3 anytime — zero lock-in",
    "No annual commitment. No usage caps. No feature gating. $49/mo, cancel anytime",
    "openoutreach logs — stream live output from your cloud instance. Watch every lead, every message, every decision in real time",
    "openoutreach down saves your DB locally and destroys the server. No orphaned servers, no forgotten bills",
]

_CLOUD_COLORS = ["cyan", "green", "yellow", "magenta"]

_CLOUD_CTAS = [
    "curl -fsSL https://openoutreach.app/install | sh",
    "curl -fsSL https://openoutreach.app/install | sh && openoutreach signup",
    "https://openoutreach.app",
]


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
        cta = random.choice(_CLOUD_CTAS)
        logger.info(
            colored(msg + " \u2192 ", color, attrs=["bold"])
            + colored(cta, "white", attrs=["bold"]),
        )


# ── Heartbeat ────────────────────────────────────────────────────────


class Heartbeat:
    """Logs an ``alive — <context>`` line at most once every *interval* seconds.

    The first call won't log (``_last`` starts at now) — quiet gaps begin
    counting from daemon start, not the Unix epoch.
    """

    def __init__(self, interval: float = HEARTBEAT_INTERVAL):
        self._interval = interval
        self._last = time.monotonic()

    def maybe_log(self, context: str) -> None:
        now = time.monotonic()
        if now - self._last < self._interval:
            return
        self._last = now
        logger.info(colored("alive", "cyan") + " — %s", context)


def sleep_with_heartbeat(seconds: float, heartbeat: Heartbeat, context: str) -> None:
    """``time.sleep(seconds)`` that wakes every ``HEARTBEAT_SLICE`` seconds to
    let *heartbeat* fire. Use for any idle sleep longer than the heartbeat
    interval so the daemon never goes silent for more than 5 minutes.
    """
    end = time.monotonic() + seconds
    while True:
        remaining = end - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(HEARTBEAT_SLICE, remaining))
        heartbeat.maybe_log(context)


# ── Human-rhythm pacing ──────────────────────────────────────────────


class _HumanRhythmBreak:
    """Wall-clock burst timer that injects a random break between bursts.

    Call ``reset()`` after idle sleeps (active-hours pause, waiting for
    the next scheduled task) so the burst timer tracks real work, not
    wall-clock. Call ``maybe_break()`` after each successful task —
    it sleeps a random break duration when the current burst is done.
    """

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


def _build_qualifiers(campaigns, cfg, kit_model=None):
    """Create a qualifier for every campaign, keyed by campaign PK."""
    from openoutreach.crm.models import Lead

    qualifiers: dict[int, BayesianQualifier | KitQualifier] = {}
    n_regular = 0
    for campaign in campaigns:
        if campaign.is_freemium:
            if kit_model is None:
                continue
            qualifiers[campaign.pk] = KitQualifier(kit_model)
        else:
            q = BayesianQualifier(
                seed=42,
                n_mc_samples=cfg["qualification_n_mc_samples"],
                campaign=campaign,
            )
            X, y = Lead.get_labeled_arrays(campaign)
            if len(X) > 0:
                q.warm_start(X, y)
                logger.info(
                    colored("GP qualifier warm-started", "cyan")
                    + " on %d labelled samples (%d positive, %d negative)"
                    + " for campaign %s",
                    len(y),
                    int((y == 1).sum()),
                    int((y == 0).sum()),
                    campaign,
                )
            qualifiers[campaign.pk] = q
            n_regular += 1

    return qualifiers


# ------------------------------------------------------------------
# Active-hours schedule guard
# ------------------------------------------------------------------


def seconds_until_active() -> float:
    """Return seconds to wait before the next active window, or 0 if active now.

    Reads configuration from SiteConfig (enable_active_hours, active_start_hour,
    active_end_hour, active_timezone, active_days). Active days filter by weekday.
    """
    from openoutreach.mongodb.models import SiteConfig

    config = SiteConfig.load()
    if not config.enable_active_hours:
        return 0.0

    zone = ZoneInfo(config.active_timezone)
    now = datetime.now(tz.utc).astimezone(zone)

    # Parse active days (comma-separated: 1=Monday, 7=Sunday)
    try:
        active_days = set(int(d.strip()) for d in config.active_days.split(",") if d.strip())
    except (ValueError, AttributeError):
        active_days = {1, 2, 3, 4, 5}  # Default to weekdays

    # Check if today is an active day (Python: 0=Monday, 6=Sunday; our format: 1=Monday, 7=Sunday)
    current_weekday = now.weekday() + 1  # Convert to 1-7 format
    if current_weekday not in active_days:
        # Find next active day
        days_ahead = 1
        while days_ahead <= 7:
            next_day = (current_weekday + days_ahead - 1) % 7 + 1
            if next_day in active_days:
                # Jump to start of next active day
                candidate = now.replace(
                    hour=config.active_start_hour,
                    minute=0,
                    second=0,
                    microsecond=0,
                ) + timedelta(days=days_ahead)
                return (candidate - now).total_seconds()
            days_ahead += 1
        # All days inactive (shouldn't happen, but fallback to tomorrow)
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
# Checkpoint exit
# ------------------------------------------------------------------


def _handle_checkpoint(session, task, url: str) -> None:
    """Handle checkpoint challenge by notifying user and marking task failed.

    Called when LinkedIn flags the account with a security checkpoint.
    We do NOT retry or reauthenticate — every retry hardens the block.
    The user clears the challenge via the frontend modal, then daemon continues.
    """
    logger.warning(
        colored(
            f"CHECKPOINT CHALLENGE — {session.linkedin_profile.linkedin_username}",
            "yellow",
            attrs=["bold"],
        )
    )
    logger.warning("Challenge URL: %s", url)
    logger.warning("User must complete challenge via frontend before tasks resume")

    _notify_checkpoint_challenge(session, url)
    task.mark_failed(error_message=f"Checkpoint challenge required: {url}")
    session.close()


# ------------------------------------------------------------------
# Task queue worker
# ------------------------------------------------------------------


def run_daemon(session):
    from openoutreach.linkedin.ml.hub import fetch_kit
    from openoutreach.linkedin.setup.freemium import import_freemium_campaign
    from openoutreach.mongodb.models import Campaign

    cfg = CAMPAIGN_CONFIG

    # Track whether session has been authenticated
    _authenticated = False

    # Load kit model for freemium campaigns
    kit = fetch_kit()
    if kit:
        freemium_campaign = import_freemium_campaign(kit["config"])
        if freemium_campaign:
            prev_campaign = session.campaign
            session.campaign = freemium_campaign
            from openoutreach.linkedin.setup.freemium import seed_profiles

            seed_profiles(session, kit["config"])
            session.campaign = prev_campaign

    qualifiers = _build_qualifiers(
        session.campaigns,
        cfg,
        kit_model=kit["model"] if kit else None,
    )

    campaigns = session.campaigns
    if not campaigns:
        logger.warning("No campaigns found — daemon will idle until a campaign is created")
        # Continue running in idle mode - campaigns can be created via frontend
    else:
        logger.info(
            colored("Daemon started", "green", attrs=["bold"])
            + " — %d campaigns, task queue worker (lazy auth)",
            len(campaigns),
        )

    # cloud_promo = _CloudPromoRotator(interval=60)  # tmp disabled — see below
    heartbeat = Heartbeat()
    rhythm = _HumanRhythmBreak(heartbeat)

    # Single-threaded: one task at a time, no concurrent enqueuing,
    # so sleeping until the next scheduled_at is safe.
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

        task: Task | None = Task.objects.claim_next()  # type: ignore[union-attr]
        if task is None:
            # Nothing ready — reconcile the queue from CRM state. Any deal
            # stuck without a pending task (e.g. because a prior handler
            # crashed) gets a fresh task here; this is the retry mechanism.
            from openoutreach.core.scheduler import reconcile

            reconcile(session)

            wait = Task.objects.seconds_to_next()  # type: ignore[union-attr]
            if wait is None:
                logger.info("Queue empty after reconcile — sleeping 1h")
                sleep_with_heartbeat(3600, heartbeat, "queue empty")
                rhythm.reset()
                continue
            if wait > 0:
                h, m = int(wait // 3600), int(wait % 3600 // 60)
                logger.info("Next task in %dh%02dm — sleeping", h, m)
                sleep_with_heartbeat(
                    wait,
                    heartbeat,
                    f"next task in {h}h{m:02d}m",
                )
                rhythm.reset()
            continue

        campaign = Campaign.objects.filter(pk=task.payload.get("campaign_id")).first()
        if not campaign:
            error_msg = f"Campaign {task.payload.get('campaign_id')} not found - task cannot be executed"
            logger.error("[%s] %s", task.task_type, error_msg)
            task.mark_failed(error_message=error_msg)
            continue

        # Skip tasks for non-active campaigns
        if campaign.status != Campaign.Status.ACTIVE:
            logger.debug(
                "[%s] Skipping task for campaign %s (status=%s)",
                task.task_type,
                campaign.pk,
                campaign.status,
            )
            task.mark_failed(error_message=f"Campaign status is {campaign.status}, not active")
            continue

        # Lazy auth: authenticate session on first task claim
        if not _authenticated:
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
                        from openoutreach.crm.models import LinkedInCredentials
                        cred = LinkedInCredentials.objects.filter(
                            linkedin_profile=session.linkedin_profile
                        ).first()
                        if cred and cred.username != public_id:
                            cred.username = public_id
                            cred.save(update_fields=["username"])
                            logger.info("Synced credential username: %s", public_id)
                except Exception as exc:
                    logger.debug("Could not sync credential profile: %s", exc)

            except CheckpointChallengeError as exc:
                # Notify user about challenge, but don't exit - just skip tasks
                logger.warning(
                    "LinkedIn checkpoint detected at %s — notifying user", exc.url
                )
                _notify_checkpoint_challenge(session, exc.url)
                task.mark_failed(error_message=f"Checkpoint challenge required: {exc.url}")
                # Don't set _authenticated = True, so we retry auth on next task
                continue
            except AuthenticationError as exc:
                logger.error("Authentication failed: %s — notifying user", exc)
                _notify_auth_required(session, str(exc))
                task.mark_failed(error_message=f"Authentication required: {exc}")
                continue
            except Exception as exc:
                logger.error("Unexpected error during authentication: %s", exc)
                task.mark_failed(error_message=f"Auth error: {exc}")
                continue

        session.campaign = campaign
        task.mark_running()

        handler = _HANDLERS.get(task.task_type)
        if handler is None:
            error_msg = f"Unknown task type: {task.task_type}"
            logger.error("[%s] %s", task.task_type, error_msg)
            task.mark_failed(error_message=error_msg)
            continue

        try:
            with failure_diagnostics(session):
                handler(task, session, qualifiers)
        except CheckpointChallengeError as exc:
            _handle_checkpoint(session, task, exc.url)
            _authenticated = False  # Reset auth flag to retry on next task
            continue
        except AuthenticationError:
            logger.warning("Session expired during %s — re-authenticating", task)
            try:
                session.reauthenticate()
            except CheckpointChallengeError as exc:
                _handle_checkpoint(session, task, exc.url)
                _authenticated = False  # Reset auth flag to retry on next task
                continue
            except Exception:
                logger.exception("Re-authentication failed for %s", task)
            # Either way, mark this task FAILED; reconcile will re-create a
            # fresh task for the deal on the next idle cycle.
            task.mark_failed()
            continue
        except ModelHTTPError as e:
            error_msg = f"LLM API error: {str(e)[:200]}"
            task.mark_failed(error_message=error_msg)
            logger.error(
                colored("Daemon stopped — LLM API error", "red", attrs=["bold"])
                + "\n%s\nCheck llm_provider, ai_model, llm_api_key, and llm_api_base in Admin → Site Configuration.",
                e,
            )
            return
        except Exception:
            import traceback

            error_msg = f"Task execution failed: {traceback.format_exc()[:500]}"
            task.mark_failed(error_message=error_msg)
            logger.error(
                colored("[%s] Task FAILED", "red", attrs=["bold"])
                + " (task_id=%s, campaign_id=%s)\n%s",
                task.task_type,
                task.pk,
                task.payload.get("campaign_id", "unknown"),
                error_msg,
            )
            # NOTE: Task handlers are responsible for creating ActionLog entries
            # when appropriate. The daemon does not create entries for exceptions.
            continue

        task.mark_completed()
        logger.info(
            colored("[%s] Task COMPLETED", "green", attrs=["bold"])
            + " (task_id=%s, campaign_id=%s)",
            task.task_type,
            task.pk,
            task.payload.get("campaign_id", "unknown"),
        )

        # NOTE: ActionLog entries are created by task handlers themselves when
        # actions are actually executed. The daemon does not create entries here
        # to avoid duplicates and to ensure skipped tasks don't count toward rate limits.

        # Refresh cookies after every successful task to keep session warm
        try:
            from openoutreach.linkedin.browser.launch import _save_cookies
            _save_cookies(session)
            logger.debug("Refreshed session cookies after task completion")
        except Exception as e:
            logger.debug("Failed to refresh cookies: %s", e)

        # Health check: run every HEALTH_CHECK_INTERVAL seconds
        if hasattr(session, "_last_health_check"):
            if time.monotonic() - session._last_health_check >= HEALTH_CHECK_INTERVAL:
                _run_health_checks(session)
                session._last_health_check = time.monotonic()
        else:
            session._last_health_check = time.monotonic()
            _run_health_checks(session)

        # TODO(tmp): Cloud/CLI promo disabled — still advertises the retired
        # openoutreach CLI (GH issue). Re-enable with email-first messaging.
        # cloud_promo.maybe_log()
        rhythm.maybe_break()
