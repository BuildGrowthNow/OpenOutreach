# openoutreach/core/daemon.py
"""Multi-profile daemon: manages one browser session per active LinkedInProfile,
claims tasks scoped by linkedin_profile_id, and round-robins across all users.
"""
from __future__ import annotations

import logging
import random
import time
from datetime import datetime, timedelta, timezone as tz
from typing import Optional
from zoneinfo import ZoneInfo

from pydantic_ai.exceptions import ModelHTTPError
from termcolor import colored

from openoutreach.core.conf import CAMPAIGN_CONFIG
from openoutreach.linkedin.diagnostics import failure_diagnostics
from linkedin_cli.exceptions import AuthenticationError, CheckpointChallengeError
from openoutreach.linkedin.ml.qualifier import BayesianQualifier
from openoutreach.mongodb.models import Campaign, SiteConfig, Task

logger = logging.getLogger(__name__)

_HANDLERS: dict = {}


def _register_handlers():
    global _HANDLERS
    if _HANDLERS:
        return
    from openoutreach.linkedin.tasks.check_pending import handle_check_pending
    from openoutreach.linkedin.tasks.connect import handle_connect
    from openoutreach.linkedin.tasks.follow_up import handle_follow_up
    from openoutreach.linkedin.tasks.send_manual_message import handle_send_manual_message

    _HANDLERS = {
        Task.TaskType.CONNECT: handle_connect,
        Task.TaskType.CHECK_PENDING: handle_check_pending,
        Task.TaskType.FOLLOW_UP: handle_follow_up,
        Task.TaskType.SEND_MANUAL_MESSAGE: handle_send_manual_message,
    }


# ── Notifications ──────────────────────────────────────────────────────


def _notify_auth_required(user_id: str, reason: str) -> None:
    try:
        from openoutreach.mongodb.models_extended import Notification
        Notification(
            recipient_id=user_id,
            notification_type="campaign_error",
            title="LinkedIn Authentication Required",
            message=f"Authentication failed: {reason}. Please add valid LinkedIn credentials in Settings → LinkedIn Connection.",
        ).save()
    except Exception as e:
        logger.debug("Could not create auth notification: %s", e)


def _notify_checkpoint_challenge(user_id: str, url: str) -> None:
    try:
        from openoutreach.mongodb.models_extended import Notification
        Notification(
            recipient_id=user_id,
            notification_type="campaign_error",
            title="LinkedIn Challenge Required",
            message=f"LinkedIn requires additional verification. Complete the challenge at: {url}",
            data={"challenge_url": url, "requires_action": True},
        ).save()
    except Exception as e:
        logger.debug("Could not create checkpoint notification: %s", e)


# ── Heartbeat ──────────────────────────────────────────────────────────

HEARTBEAT_INTERVAL = 300
HEARTBEAT_SLICE = 60
HEALTH_CHECK_INTERVAL = 3600


class Heartbeat:
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
    end = time.monotonic() + seconds
    while True:
        remaining = end - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(HEARTBEAT_SLICE, remaining))
        heartbeat.maybe_log(context)


# ── Human-rhythm pacing ────────────────────────────────────────────────


class _HumanRhythmBreak:
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
        self._new_burst()

    def maybe_break(self):
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


# ── Active-hours guard ─────────────────────────────────────────────────


def seconds_until_active(user_id: Optional[str] = None) -> float:
    """Return seconds to wait before the next active window, or 0 if active now.
    Reads config from the user's SiteConfig."""
    config = SiteConfig.load(user_id=user_id)
    if not config.enable_active_hours:
        return 0.0

    zone = ZoneInfo(config.active_timezone)
    now = datetime.now(tz.utc).astimezone(zone)

    try:
        raw_days = config.active_days
        if isinstance(raw_days, str):
            active_days = set(int(d.strip()) for d in raw_days.split(",") if d.strip())
        elif isinstance(raw_days, list):
            active_days = set(int(d) + 1 for d in raw_days)
        else:
            active_days = {1, 2, 3, 4, 5}
    except (ValueError, AttributeError):
        active_days = {1, 2, 3, 4, 5}

    current_weekday = now.weekday() + 1
    if current_weekday not in active_days:
        days_ahead = 1
        while days_ahead <= 7:
            next_day = (current_weekday + days_ahead - 1) % 7 + 1
            if next_day in active_days:
                candidate = now.replace(
                    hour=config.active_start_hour, minute=0, second=0, microsecond=0,
                ) + timedelta(days=days_ahead)
                return (candidate - now).total_seconds()
            days_ahead += 1
        candidate = now.replace(
            hour=config.active_start_hour, minute=0, second=0, microsecond=0,
        ) + timedelta(days=1)
        return (candidate - now).total_seconds()

    if config.active_start_hour <= now.hour < config.active_end_hour:
        return 0.0

    candidate = now.replace(
        hour=config.active_start_hour, minute=0, second=0, microsecond=0,
    )
    if candidate <= now:
        days_ahead = 1
        while days_ahead <= 7:
            next_day = (current_weekday + days_ahead - 1) % 7 + 1
            if next_day in active_days:
                candidate = now.replace(
                    hour=config.active_start_hour, minute=0, second=0, microsecond=0,
                ) + timedelta(days=days_ahead)
                break
            days_ahead += 1
    return (candidate - now).total_seconds()


# ── Qualifiers ─────────────────────────────────────────────────────────


def _build_qualifiers(campaigns, cfg):
    from openoutreach.crm.models import Lead

    qualifiers: dict = {}
    for campaign in campaigns:
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
                + " on %d samples (%d+, %d-) for %s",
                len(y), int((y == 1).sum()), int((y == 0).sum()), campaign,
            )
        qualifiers[campaign.pk] = q

    return qualifiers


# ── Health checks ──────────────────────────────────────────────────────


def _run_health_checks(session) -> None:
    from openoutreach.linkedin.models.health import HealthAlert
    from openoutreach.linkedin.services.health_monitor import CampaignHealthMonitor

    for campaign in session.campaigns:
        try:
            monitor = CampaignHealthMonitor(campaign)
            alerts = monitor.run_health_check()
            for alert in alerts:
                alert.save()
                if alert.severity in [HealthAlert.SEVERITY_LOW, HealthAlert.SEVERITY_MEDIUM]:
                    monitor.auto_remediate(alert)
        except Exception as e:
            logger.error("Health check error for %s: %s", campaign.name, e)


# ── Session pool ───────────────────────────────────────────────────────


class ProfileSession:
    """Tracks state for a single LinkedIn profile within the daemon."""

    def __init__(self, profile):
        self.profile = profile
        self.session = None
        self.authenticated = False
        self.paused_until: Optional[float] = None
        self.qualifiers: dict = {}
        self.last_health_check: float = 0.0
        self.vnc_session = None  # VNC session for this profile

    @property
    def profile_id(self) -> str:
        return self.profile.pk

    @property
    def user_id(self) -> str:
        return self.profile.user_id or ""

    def is_paused(self) -> bool:
        if self.paused_until is None:
            return False
        if time.monotonic() >= self.paused_until:
            self.paused_until = None
            return False
        return True

    def pause(self, seconds: float) -> None:
        self.paused_until = time.monotonic() + seconds

    def ensure_session(self):
        if self.session is None:
            from openoutreach.linkedin.browser.registry import get_or_create_session
            from openoutreach.core.vnc_manager import get_or_create_vnc_session

            # Start VNC session for this profile
            if self.vnc_session is None:
                self.vnc_session = get_or_create_vnc_session(self.profile_id)

            self.session = get_or_create_session(self.profile)
        return self.session

    def authenticate(self) -> bool:
        """Lazy authenticate: launch browser + login. Returns True on success."""
        if self.authenticated:
            return True
        session = self.ensure_session()
        try:
            session.ensure_browser()
            self.authenticated = True
            logger.info(
                colored("Authenticated", "green") + " profile %s",
                self.profile.linkedin_username,
            )
            self._sync_credential_username(session)
            return True
        except CheckpointChallengeError as exc:
            logger.warning("Checkpoint for %s: %s", self.profile.linkedin_username, exc.url)
            _notify_checkpoint_challenge(self.user_id, exc.url)
            self.pause(300)
            return False
        except AuthenticationError as exc:
            logger.error("Auth failed for %s: %s", self.profile.linkedin_username, exc)
            _notify_auth_required(self.user_id, str(exc))
            self.pause(300)
            return False
        except Exception as exc:
            logger.error("Unexpected auth error for %s: %s", self.profile.linkedin_username, exc)
            self.pause(120)
            return False

    def _sync_credential_username(self, session):
        try:
            profile_data = session.self_profile
            public_id = profile_data.get("public_identifier", "")
            if public_id:
                from openoutreach.mongodb.models import LinkedInCredentials
                from openoutreach.mongodb.connection import get_mongodb_collection
                collection = get_mongodb_collection("linkedin_credentials")
                if collection is not None:
                    cred_doc = collection.find_one({"linkedin_profile_id": self.profile_id})
                    if cred_doc:
                        cred = LinkedInCredentials.from_dict(cred_doc)
                        if cred.username != public_id:
                            cred.username = public_id
                            cred.save()
        except Exception as exc:
            logger.debug("Could not sync credential profile: %s", exc)

    def close(self):
        if self.session:
            self.session.close()
            self.session = None
        if self.vnc_session:
            from openoutreach.core.vnc_manager import stop_vnc_session
            stop_vnc_session(self.profile_id)
            self.vnc_session = None
        self.authenticated = False


# ── Main daemon ────────────────────────────────────────────────────────

PROFILE_REFRESH_INTERVAL = 300  # Re-scan for new/removed profiles every 5 min


def _get_all_active_profiles() -> list:
    """Return all active LinkedIn profiles with valid cookie data.
    Profiles must be active and not plan-deactivated to run.
    """
    from openoutreach.linkedin.models import LinkedInProfile
    from openoutreach.billing.enforcement import PlanEnforcer

    active_profiles = LinkedInProfile.objects.filter(active=True)
    result = []
    for p in active_profiles:
        if not p.cookie_data_encrypted:
            continue
        if not p.is_active:
            continue

        user = p.user
        if not user:
            continue

        can_run, _ = PlanEnforcer.can_run_tasks(user)
        if not can_run:
            continue

        result.append(p)

    return result


def run_daemon():
    """Multi-profile daemon entry point. Manages sessions for all active
    LinkedIn profiles and processes tasks scoped to each profile."""
    from openoutreach.mongodb.connection import initialize_mongodb_connection
    from openoutreach.mongodb.indexes import ensure_all_indexes

    initialize_mongodb_connection()
    ensure_all_indexes()
    _register_handlers()

    cfg = CAMPAIGN_CONFIG
    heartbeat = Heartbeat()
    rhythm = _HumanRhythmBreak(heartbeat)

    # Session pool: profile_id -> ProfileSession
    pool: dict[str, ProfileSession] = {}
    last_profile_refresh = 0.0

    def refresh_pool():
        nonlocal last_profile_refresh
        now = time.monotonic()
        if now - last_profile_refresh < PROFILE_REFRESH_INTERVAL and pool:
            return
        last_profile_refresh = now

        active_profiles = _get_all_active_profiles()
        active_ids = {p.pk for p in active_profiles}

        # Add new profiles
        for profile in active_profiles:
            if profile.pk not in pool:
                ps = ProfileSession(profile)
                pool[profile.pk] = ps
                logger.info(
                    colored("Profile added to pool", "cyan") + ": %s (user=%s)",
                    profile.linkedin_username, profile.user_id or "unknown",
                )

        # Remove deactivated profiles
        for pid in list(pool.keys()):
            if pid not in active_ids:
                pool[pid].close()
                del pool[pid]
                logger.info("Profile removed from pool: %s", pid)

    def build_qualifiers_for(ps: ProfileSession):
        if ps.qualifiers:
            return
        session = ps.ensure_session()
        campaigns = session.campaigns
        ps.qualifiers = _build_qualifiers(campaigns, cfg)

    logger.info(colored("Daemon starting", "green", attrs=["bold"]) + " — multi-profile mode")

    while True:
        refresh_pool()

        if not pool:
            logger.info("No active profiles with credentials — sleeping 60s")
            sleep_with_heartbeat(60, heartbeat, "no profiles")
            continue

        # Round-robin across profiles: try to claim one task from any profile
        task_executed = False

        for ps in list(pool.values()):
            if ps.is_paused():
                continue

            # Check active hours for this user
            pause = seconds_until_active(user_id=ps.user_id)
            if pause > 0:
                ps.pause(min(pause, 3600))
                continue

            # Claim next task for this profile
            task = Task.objects.claim_next(linkedin_profile_id=ps.profile_id)
            if task is None:
                continue

            # Validate campaign
            campaign_id = task.payload.get("campaign_id")
            if not campaign_id:
                task.mark_failed()
                continue

            campaign = Campaign.get(campaign_id)
            if not campaign or campaign.status != Campaign.Status.ACTIVE:
                task.mark_failed()
                continue

            # Authenticate lazily on first task
            if not ps.authenticate():
                task.mark_failed()
                continue

            # Build qualifiers lazily
            build_qualifiers_for(ps)

            session = ps.ensure_session()
            session.campaign = campaign
            task.mark_running()

            handler = _HANDLERS.get(task.task_type)
            if handler is None:
                logger.error("Unknown task type: %s", task.task_type)
                task.mark_failed()
                continue

            try:
                with failure_diagnostics(session):
                    handler(task, session, ps.qualifiers)
            except CheckpointChallengeError as exc:
                _notify_checkpoint_challenge(ps.user_id, exc.url)
                task.mark_failed()
                ps.close()
                ps.pause(300)
                continue
            except AuthenticationError:
                logger.warning("Session expired for %s — re-authenticating",
                               ps.profile.linkedin_username)
                try:
                    session.reauthenticate()
                except CheckpointChallengeError as exc:
                    _notify_checkpoint_challenge(ps.user_id, exc.url)
                    ps.close()
                    ps.pause(300)
                except Exception:
                    logger.exception("Re-auth failed for %s", ps.profile.linkedin_username)
                task.mark_failed()
                continue
            except ModelHTTPError as e:
                task.mark_failed()
                logger.error(
                    colored("LLM API error", "red", attrs=["bold"])
                    + " for %s\n%s\nCheck SiteConfig LLM settings.",
                    ps.profile.linkedin_username, e,
                )
                ps.pause(600)
                continue
            except Exception:
                import traceback
                task.mark_failed()
                logger.error(
                    colored("[%s] Task FAILED", "red", attrs=["bold"])
                    + " (task=%s, campaign=%s, profile=%s)\n%s",
                    task.task_type, task.pk, campaign_id,
                    ps.profile.linkedin_username, traceback.format_exc()[:500],
                )
                continue

            task.mark_completed()
            logger.info(
                colored("[%s] COMPLETED", "green", attrs=["bold"])
                + " (profile=%s, campaign=%s)",
                task.task_type, ps.profile.linkedin_username, campaign_id,
            )

            # Refresh cookies to keep session warm
            try:
                from openoutreach.linkedin.browser.launch import _save_cookies
                _save_cookies(session)
            except Exception:
                pass

            # Periodic health check
            if time.monotonic() - ps.last_health_check >= HEALTH_CHECK_INTERVAL:
                _run_health_checks(session)
                ps.last_health_check = time.monotonic()

            task_executed = True
            rhythm.maybe_break()
            break  # After executing one task, restart the round-robin

        if not task_executed:
            _reconcile_all(pool)

            min_wait = _min_wait_across_profiles(pool)
            if min_wait is None or min_wait > 3600:
                min_wait = 3600

            if min_wait > 60:
                h, m = int(min_wait // 3600), int(min_wait % 3600 // 60)
                logger.info("No tasks ready — sleeping %dh%02dm", h, m)
            sleep_with_heartbeat(min(min_wait, 60), heartbeat, "idle")
            rhythm.reset()


def _reconcile_all(pool: dict[str, ProfileSession]) -> None:
    """Run reconcile for every active profile's campaigns."""
    from openoutreach.core.scheduler import reconcile

    for ps in pool.values():
        if ps.is_paused() or not ps.session:
            continue
        try:
            reconcile(ps.session)
        except Exception as e:
            logger.error("Reconcile error for %s: %s", ps.profile.linkedin_username, e)


def _min_wait_across_profiles(pool: dict[str, ProfileSession]) -> Optional[float]:
    """Return shortest seconds_to_next across all profile queues."""
    min_wait = None
    for ps in pool.values():
        if ps.is_paused():
            continue
        wait = Task.objects.seconds_to_next(linkedin_profile_id=ps.profile_id)
        if wait is not None:
            if min_wait is None or wait < min_wait:
                min_wait = wait
    return min_wait
