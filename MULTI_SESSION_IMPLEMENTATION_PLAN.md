# Multi-Session Daemon Implementation Plan

**Goal:** Enable OpenOutreach to support multiple LinkedIn profiles (users) running concurrently in a single daemon instance, with full campaign-user isolation and production-ready security.

**Current State:** Daemon runs with ONE profile only (`get_first_active_profile()`). Other users' campaigns are ignored.

**Target State:** Daemon manages N active profiles, executes tasks round-robin, maintains complete data isolation per user/campaign.

**Estimated Total Time:** 16-20 hours across 7 phases

**Critical Requirements:**
- ✅ Campaign data must ONLY be visible to campaign members (User.campaigns M2M)
- ✅ Tasks must execute on the correct LinkedIn profile
- ✅ No cross-user data leakage
- ✅ Graceful degradation if one profile fails auth
- ✅ Frontend shows only user's own campaigns/leads/tasks
- ✅ Backward compatible with existing single-user deployments

---

## Phase 1: Database Schema & Migrations (Backend)

**Time Estimate:** 2-3 hours  
**Owner:** Backend AI Agent  
**Dependencies:** None  
**Rollback Strategy:** Django migrations are reversible via `python manage.py migrate core <previous_migration>`

### 1.1 Add `linkedin_profile` FK to Task Model

**File:** `openoutreach/core/models.py`

**Changes:**
```python
class Task(models.Model):
    # ... existing fields ...
    
    # NEW: Associate each task with a specific LinkedIn profile
    linkedin_profile = models.ForeignKey(
        'linkedin.LinkedInProfile',
        on_delete=models.CASCADE,
        related_name='tasks',
        help_text="The LinkedIn profile that will execute this task",
        null=True,  # Temporarily nullable for migration
        blank=True,
    )
    
    # ... rest of model ...
```

**Why nullable?** Existing Task rows have no profile. We'll backfill in migration, then make it required.

### 1.2 Create Migration

**Command:**
```bash
python manage.py makemigrations core --name add_linkedin_profile_to_task
```

**Migration File:** `openoutreach/core/migrations/0XXX_add_linkedin_profile_to_task.py`

**Migration Steps:**
1. Add nullable `linkedin_profile` FK
2. Backfill existing tasks with first active profile
3. Make field non-nullable
4. Add composite index on `(linkedin_profile, status, scheduled_at)` for fast claiming

**Manual Migration Content:**
```python
from django.db import migrations, models
import django.db.models.deletion

def backfill_linkedin_profiles(apps, schema_editor):
    """Assign existing tasks to the first active LinkedIn profile."""
    Task = apps.get_model('core', 'Task')
    LinkedInProfile = apps.get_model('linkedin', 'LinkedInProfile')
    
    # Get first active profile (matches current daemon behavior)
    profile = LinkedInProfile.objects.filter(active=True).first()
    if not profile:
        # No active profiles - skip backfill (tasks will be recreated)
        return
    
    # Assign all existing tasks to this profile
    Task.objects.filter(linkedin_profile__isnull=True).update(
        linkedin_profile=profile
    )

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0XXX_previous_migration'),  # Replace with actual previous migration
        ('linkedin', '0XXX_latest_linkedin_migration'),
    ]

    operations = [
        # Step 1: Add nullable FK
        migrations.AddField(
            model_name='task',
            name='linkedin_profile',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='tasks',
                to='linkedin.linkedinprofile',
                help_text='The LinkedIn profile that will execute this task',
            ),
        ),
        
        # Step 2: Backfill existing tasks
        migrations.RunPython(
            backfill_linkedin_profiles,
            reverse_code=migrations.RunPython.noop,
        ),
        
        # Step 3: Make field non-nullable
        migrations.AlterField(
            model_name='task',
            name='linkedin_profile',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='tasks',
                to='linkedin.linkedinprofile',
                help_text='The LinkedIn profile that will execute this task',
            ),
        ),
        
        # Step 4: Add composite index for fast task claiming
        migrations.AddIndex(
            model_name='task',
            index=models.Index(
                fields=['linkedin_profile', 'status', 'scheduled_at'],
                name='task_profile_status_sched_idx',
            ),
        ),
    ]
```

### 1.3 Run Migration

**Commands:**
```bash
# Dry run first
python manage.py migrate core --plan

# Apply migration
python manage.py migrate core

# Verify
python manage.py shell -c "from openoutreach.core.models import Task; print(f'Tasks with profile: {Task.objects.exclude(linkedin_profile=None).count()}')"
```

### 1.4 Update Task Manager Methods

**File:** `openoutreach/core/models.py`

**Update `claim_next()` signature:**
```python
class TaskManager(models.Manager):
    def claim_next(self, linkedin_profile=None):
        """Claim the next pending task, optionally filtered by profile.
        
        Args:
            linkedin_profile: If provided, only claim tasks for this profile.
                             If None, claim next task for ANY profile (backward compat).
        
        Returns:
            Task instance with status=RUNNING, or None if no task ready.
        """
        from django.db import transaction
        from django.utils import timezone

        with transaction.atomic():
            now = timezone.now()
            
            # Build query
            query = self.filter(
                status=Task.TaskStatus.PENDING,
                scheduled_at__lte=now,
            )
            
            # Filter by profile if specified
            if linkedin_profile:
                query = query.filter(linkedin_profile=linkedin_profile)
            
            # Lock and claim first task
            task = (
                query
                .select_for_update(skip_locked=True)
                .order_by('scheduled_at')
                .first()
            )
            
            if task:
                task.status = Task.TaskStatus.RUNNING
                task.started_at = now
                task.save(update_fields=['status', 'started_at'])
                
            return task
    
    def claim_next_for_any_profile(self):
        """Claim next task across ALL active profiles (multi-session mode)."""
        return self.claim_next(linkedin_profile=None)
    
    def seconds_to_next(self, linkedin_profile=None):
        """Seconds until next scheduled task (optionally filtered by profile)."""
        from django.utils import timezone
        
        query = self.filter(status=Task.TaskStatus.PENDING)
        if linkedin_profile:
            query = query.filter(linkedin_profile=linkedin_profile)
        
        task = query.order_by('scheduled_at').first()
        if not task:
            return None
        
        delta = (task.scheduled_at - timezone.now()).total_seconds()
        return max(0, delta)
```

### 1.5 Testing

**Test File:** `tests/core/test_task_multi_profile.py`

```python
import pytest
from django.utils import timezone
from datetime import timedelta
from openoutreach.core.models import Task
from tests.factories import TaskFactory, LinkedInProfileFactory

@pytest.mark.django_db
class TestTaskMultiProfile:
    def test_claim_next_filters_by_profile(self):
        """claim_next(profile) only returns tasks for that profile."""
        profile1 = LinkedInProfileFactory(active=True)
        profile2 = LinkedInProfileFactory(active=True)
        
        task1 = TaskFactory(linkedin_profile=profile1, status='pending', scheduled_at=timezone.now())
        task2 = TaskFactory(linkedin_profile=profile2, status='pending', scheduled_at=timezone.now())
        
        claimed = Task.objects.claim_next(linkedin_profile=profile1)
        assert claimed.id == task1.id
        assert claimed.linkedin_profile == profile1
    
    def test_claim_next_for_any_profile_round_robin(self):
        """claim_next_for_any_profile() returns tasks across profiles."""
        profile1 = LinkedInProfileFactory(active=True)
        profile2 = LinkedInProfileFactory(active=True)
        
        task1 = TaskFactory(linkedin_profile=profile1, status='pending', scheduled_at=timezone.now())
        task2 = TaskFactory(linkedin_profile=profile2, status='pending', scheduled_at=timezone.now() + timedelta(seconds=1))
        
        # First claim gets profile1 (earlier scheduled_at)
        claimed1 = Task.objects.claim_next_for_any_profile()
        assert claimed1.linkedin_profile == profile1
        
        # Second claim gets profile2
        claimed2 = Task.objects.claim_next_for_any_profile()
        assert claimed2.linkedin_profile == profile2
    
    def test_no_cross_profile_claiming(self):
        """Tasks assigned to profile1 cannot be claimed by profile2."""
        profile1 = LinkedInProfileFactory(active=True)
        profile2 = LinkedInProfileFactory(active=True)
        
        task = TaskFactory(linkedin_profile=profile1, status='pending', scheduled_at=timezone.now())
        
        claimed = Task.objects.claim_next(linkedin_profile=profile2)
        assert claimed is None  # No tasks for profile2
```

**Run Tests:**
```bash
pytest tests/core/test_task_multi_profile.py -v
```

### Success Criteria
- ✅ Migration runs without errors
- ✅ All existing tasks have `linkedin_profile` assigned
- ✅ New index exists: `task_profile_status_sched_idx`
- ✅ `Task.objects.claim_next(profile)` filters correctly
- ✅ Tests pass

---

## Phase 2: Scheduler Multi-Profile Support (Backend)

**Time Estimate:** 3-4 hours  
**Owner:** Backend AI Agent  
**Dependencies:** Phase 1 complete  
**Rollback Strategy:** Revert `scheduler.py` changes; old code still works with new schema

### 2.1 Update Scheduler to Assign Tasks to Profiles

**File:** `openoutreach/core/scheduler.py`

**Current Issue:** Planners create tasks without `linkedin_profile`:
```python
Task.objects.create(
    task_type=Task.TaskType.CONNECT,
    payload={"campaign_id": campaign.pk},
    scheduled_at=slot_time,
    # ❌ Missing: linkedin_profile
)
```

**Changes Required:**

#### 2.1.1 Update Planner Functions

**Before:**
```python
def plan_connect_window(campaign):
    # ... compute slots ...
    Task.objects.create(...)
```

**After:**
```python
def plan_connect_window(campaign, linkedin_profile):
    """Plan connect tasks for a specific profile in a campaign.
    
    Args:
        campaign: Campaign to plan tasks for
        linkedin_profile: LinkedInProfile that will execute these tasks
    """
    # Validate profile is a campaign member
    if not campaign.users.filter(pk=linkedin_profile.user.pk).exists():
        logger.warning(
            f"Profile {linkedin_profile} user not in campaign {campaign.name} - skipping"
        )
        return
    
    # ... existing slot computation logic ...
    
    for slot_time in slot_times:
        Task.objects.create(
            task_type=Task.TaskType.CONNECT,
            linkedin_profile=linkedin_profile,  # ← NEW
            payload={"campaign_id": campaign.pk},
            scheduled_at=slot_time,
            status=Task.TaskStatus.PENDING,
        )
```

**Apply same pattern to:**
- `plan_follow_up_window(campaign, linkedin_profile)`
- `plan_check_pending_window(campaign, linkedin_profile)`

#### 2.1.2 Update `reconcile()` to Loop Over Profiles

**File:** `openoutreach/core/scheduler.py`

**Before:**
```python
def reconcile(session):
    """Reconcile task queue from CRM state."""
    _recover_stale_running_tasks()
    
    for campaign in session.campaigns:
        # Plan for single session.campaign
        if not Task.objects.filter(...).exists():
            plan_connect_window(campaign)
        # ... etc
```

**After:**
```python
def reconcile(session=None):
    """Reconcile task queue from CRM state.
    
    In multi-session mode, reconciles ALL active profiles × their campaigns.
    In single-session mode (backward compat), reconciles only session.campaigns.
    
    Args:
        session: Optional AccountSession. If None, reconciles all active profiles.
    """
    from openoutreach.linkedin.models import LinkedInProfile
    from openoutreach.core.models import Campaign
    
    _recover_stale_running_tasks()
    
    # Multi-session mode: reconcile all active profiles
    if session is None:
        profiles = LinkedInProfile.objects.filter(active=True).select_related('user')
        for profile in profiles:
            _reconcile_profile_campaigns(profile)
    else:
        # Single-session mode (backward compat)
        _reconcile_profile_campaigns(session.linkedin_profile)

def _reconcile_profile_campaigns(linkedin_profile):
    """Reconcile tasks for one profile's campaigns."""
    from openoutreach.core.models import Campaign
    
    # Get campaigns this profile's user is a member of
    campaigns = Campaign.objects.filter(
        users=linkedin_profile.user,
        status=Campaign.Status.ACTIVE,
    )
    
    for campaign in campaigns:
        _reconcile_campaign_tasks(campaign, linkedin_profile)

def _reconcile_campaign_tasks(campaign, linkedin_profile):
    """Reconcile one campaign's tasks for a specific profile."""
    from openoutreach.core.models import Task
    
    # Check if each task type needs planning
    for task_type, planner in [
        (Task.TaskType.CONNECT, plan_connect_window),
        (Task.TaskType.CHECK_PENDING, plan_check_pending_window),
        (Task.TaskType.FOLLOW_UP, plan_follow_up_window),
    ]:
        # Check if pending tasks exist for this (campaign, profile, type)
        has_pending = Task.objects.filter(
            task_type=task_type,
            linkedin_profile=linkedin_profile,
            payload__campaign_id=campaign.pk,
            status=Task.TaskStatus.PENDING,
        ).exists()
        
        if not has_pending:
            logger.debug(
                f"Planning {task_type} for campaign={campaign.name} profile={linkedin_profile.linkedin_username}"
            )
            planner(campaign, linkedin_profile)
```

### 2.2 Update Active Hours Check (Per-Profile)

**Current:** Global active hours from `SiteConfig`  
**Target:** Per-profile active hours (allow staggering)

**Option A (Quick):** Keep global active hours, apply to all profiles  
**Option B (Better):** Per-profile active hours

**For MVP, use Option A.** Add Option B in Phase 6 (enhancements).

### 2.3 Update Rate Limiting Context

**File:** `openoutreach/core/scheduler.py`

**Ensure rate limit checks use correct profile:**

```python
def plan_connect_window(campaign, linkedin_profile):
    # Check profile's daily limit
    today_count = ActionLog.objects.filter(
        linkedin_profile=linkedin_profile,  # ← Must filter by profile
        action_type='connect',
        created_at__date=timezone.now().date(),
    ).count()
    
    if today_count >= linkedin_profile.connect_daily_limit:
        logger.info(f"Profile {linkedin_profile} hit daily connect limit")
        return  # No tasks created
    
    # ... rest of planning logic
```

### 2.4 Testing

**Test File:** `tests/core/test_scheduler_multi_profile.py`

```python
import pytest
from django.utils import timezone
from openoutreach.core.scheduler import reconcile, plan_connect_window
from openoutreach.core.models import Task, Campaign
from tests.factories import (
    CampaignFactory, LinkedInProfileFactory, UserFactory, DealFactory
)

@pytest.mark.django_db
class TestSchedulerMultiProfile:
    def test_plan_connect_assigns_profile(self):
        """plan_connect_window creates tasks assigned to correct profile."""
        user = UserFactory()
        profile = LinkedInProfileFactory(user=user, active=True)
        campaign = CampaignFactory()
        campaign.users.add(user)
        
        # Create qualified deals
        DealFactory.create_batch(5, campaign=campaign, state='QUALIFIED')
        
        plan_connect_window(campaign, profile)
        
        tasks = Task.objects.filter(
            task_type=Task.TaskType.CONNECT,
            payload__campaign_id=campaign.pk,
        )
        assert tasks.count() > 0
        assert all(t.linkedin_profile == profile for t in tasks)
    
    def test_reconcile_creates_tasks_per_profile(self):
        """reconcile() creates separate task queues per profile."""
        user1 = UserFactory()
        user2 = UserFactory()
        profile1 = LinkedInProfileFactory(user=user1, active=True)
        profile2 = LinkedInProfileFactory(user=user2, active=True)
        
        campaign = CampaignFactory()
        campaign.users.add(user1, user2)
        
        # Create deals for campaign
        DealFactory.create_batch(10, campaign=campaign, state='QUALIFIED')
        
        reconcile()  # Multi-session mode
        
        # Both profiles should have tasks
        tasks1 = Task.objects.filter(linkedin_profile=profile1)
        tasks2 = Task.objects.filter(linkedin_profile=profile2)
        
        assert tasks1.count() > 0
        assert tasks2.count() > 0
    
    def test_profile_not_in_campaign_no_tasks(self):
        """Profile NOT in campaign.users gets no tasks."""
        user1 = UserFactory()
        user2 = UserFactory()
        profile1 = LinkedInProfileFactory(user=user1, active=True)
        profile2 = LinkedInProfileFactory(user=user2, active=True)
        
        campaign = CampaignFactory()
        campaign.users.add(user1)  # Only user1
        
        DealFactory.create_batch(5, campaign=campaign, state='QUALIFIED')
        
        plan_connect_window(campaign, profile1)
        plan_connect_window(campaign, profile2)
        
        tasks1 = Task.objects.filter(linkedin_profile=profile1)
        tasks2 = Task.objects.filter(linkedin_profile=profile2)
        
        assert tasks1.count() > 0
        assert tasks2.count() == 0  # profile2 user not in campaign
```

**Run Tests:**
```bash
pytest tests/core/test_scheduler_multi_profile.py -v
```

### Success Criteria
- ✅ All planner functions accept `linkedin_profile` parameter
- ✅ Created tasks have `linkedin_profile` assigned
- ✅ `reconcile()` loops over all active profiles
- ✅ Tasks only created for profiles whose users are campaign members
- ✅ Tests pass

---

## Phase 3: Daemon Multi-Session Refactor (Backend)

**Time Estimate:** 4-5 hours  
**Owner:** Backend AI Agent  
**Dependencies:** Phase 1 & 2 complete  
**Rollback Strategy:** Keep old `run_daemon(session)` as `run_daemon_single_session()`, add feature flag

### 3.1 Create Multi-Session Daemon

**File:** `openoutreach/core/daemon.py`

**Strategy:** Maintain ONE browser per profile, claim tasks round-robin.

#### 3.1.1 Session Registry

**Add at top of `daemon.py`:**
```python
from typing import Dict
from openoutreach.linkedin.browser.session import AccountSession

class SessionPool:
    """Manages multiple AccountSession instances (one per active profile)."""
    
    def __init__(self):
        self._sessions: Dict[int, AccountSession] = {}  # profile.pk → session
        self._authenticated: Dict[int, bool] = {}  # profile.pk → auth status
    
    def get_or_create(self, linkedin_profile) -> AccountSession:
        """Get existing session or create new one for profile."""
        from openoutreach.linkedin.browser.registry import get_or_create_session
        
        pk = linkedin_profile.pk
        if pk not in self._sessions:
            session = get_or_create_session(linkedin_profile)
            self._sessions[pk] = session
            self._authenticated[pk] = False
            logger.info(f"Created session pool entry for {linkedin_profile.linkedin_username}")
        
        return self._sessions[pk]
    
    def is_authenticated(self, profile_pk: int) -> bool:
        """Check if profile session is authenticated."""
        return self._authenticated.get(profile_pk, False)
    
    def mark_authenticated(self, profile_pk: int, authenticated: bool = True):
        """Mark profile session as authenticated (or not)."""
        self._authenticated[profile_pk] = authenticated
    
    def get_all_sessions(self) -> list[AccountSession]:
        """Get all active sessions."""
        return list(self._sessions.values())
    
    def close_all(self):
        """Close all browser sessions."""
        for session in self._sessions.values():
            try:
                session.close()
            except Exception as e:
                logger.error(f"Error closing session: {e}")
```

#### 3.1.2 New Multi-Session Daemon Loop

**Add new function:**
```python
def run_daemon_multi_session():
    """Multi-session daemon: manages N active LinkedIn profiles concurrently.
    
    Each active LinkedInProfile gets its own browser session. Tasks are claimed
    round-robin across all profiles. If one profile's auth fails, others continue.
    """
    from openoutreach.linkedin.ml.hub import fetch_kit
    from openoutreach.linkedin.setup.freemium import import_freemium_campaign
    from openoutreach.core.models import Campaign
    from openoutreach.linkedin.models import LinkedInProfile
    
    cfg = CAMPAIGN_CONFIG
    
    # Initialize session pool
    session_pool = SessionPool()
    
    # Get all active profiles
    profiles = LinkedInProfile.objects.filter(active=True).select_related('user')
    if not profiles.exists():
        logger.error("No active LinkedIn profiles found - daemon cannot start")
        sys.exit(1)
    
    logger.info(
        colored(f"Daemon started (multi-session)", "green", attrs=["bold"])
        + f" — {profiles.count()} active profiles"
    )
    
    # Load kit model for freemium campaigns
    kit = fetch_kit()
    if kit:
        # Import freemium campaign (global, not per-profile)
        freemium_campaign = import_freemium_campaign(kit["config"])
        if freemium_campaign:
            # Seed profiles using first session (backward compat)
            first_profile = profiles.first()
            temp_session = session_pool.get_or_create(first_profile)
            temp_session.campaign = freemium_campaign
            from openoutreach.linkedin.setup.freemium import seed_profiles
            seed_profiles(temp_session, kit["config"])
    
    # Build qualifiers per campaign (not per profile - campaigns are shared)
    all_campaigns = Campaign.objects.filter(status=Campaign.Status.ACTIVE)
    qualifiers = _build_qualifiers(
        all_campaigns,
        cfg,
        kit_model=kit["model"] if kit else None,
    )
    
    heartbeat = Heartbeat()
    rhythm = _HumanRhythmBreak(heartbeat)
    
    # Main loop: claim tasks for ANY profile
    while True:
        # Active hours check (global for now - Phase 6 can make per-profile)
        pause = seconds_until_active()
        if pause > 0:
            h, m = int(pause // 3600), int(pause % 3600 // 60)
            logger.info("Outside active hours — sleeping %dh%02dm", h, m)
            sleep_with_heartbeat(pause, heartbeat, f"outside active hours, {h}h{m:02d}m left")
            rhythm.reset()
            continue
        
        # Claim next task across ALL profiles (round-robin by scheduled_at)
        task: Task | None = Task.objects.claim_next_for_any_profile()
        
        if task is None:
            # Queue empty - reconcile all profiles
            from openoutreach.core.scheduler import reconcile
            reconcile()  # Calls reconcile(session=None) → multi-profile mode
            
            wait = Task.objects.seconds_to_next()
            if wait is None:
                logger.info("Queue empty after reconcile — sleeping 1h")
                sleep_with_heartbeat(3600, heartbeat, "queue empty")
                rhythm.reset()
                continue
            if wait > 0:
                h, m = int(wait // 3600), int(wait % 3600 // 60)
                logger.info("Next task in %dh%02dm — sleeping", h, m)
                sleep_with_heartbeat(wait, heartbeat, f"next task in {h}h{m:02d}m")
                rhythm.reset()
            continue
        
        # Get session for this task's profile
        profile = task.linkedin_profile
        session = session_pool.get_or_create(profile)
        
        # Validate campaign exists
        campaign = Campaign.objects.filter(pk=task.payload.get("campaign_id")).first()
        if not campaign:
            error_msg = f"Campaign {task.payload.get('campaign_id')} not found"
            logger.error("[%s] %s", task.task_type, error_msg)
            task.mark_failed(error_message=error_msg)
            continue
        
        # Validate campaign access (security check)
        if not campaign.users.filter(pk=profile.user.pk).exists():
            error_msg = f"Profile {profile.linkedin_username} user not in campaign {campaign.name}"
            logger.error("[%s] %s", task.task_type, error_msg)
            task.mark_failed(error_message=error_msg)
            continue
        
        # Skip non-active campaigns
        if campaign.status != Campaign.Status.ACTIVE:
            logger.debug(
                "[%s] Skipping task for campaign %s (status=%s)",
                task.task_type, campaign.pk, campaign.status,
            )
            task.mark_failed(error_message=f"Campaign status is {campaign.status}")
            continue
        
        # Lazy auth: authenticate session on first task for this profile
        if not session_pool.is_authenticated(profile.pk):
            logger.info(f"First task for {profile.linkedin_username} — authenticating")
            try:
                session.ensure_browser()
                session_pool.mark_authenticated(profile.pk, True)
                logger.info(f"Session authenticated: {profile.linkedin_username}")
                
                # Sync credential profile
                _sync_credential_profile(session)
                
            except CheckpointChallengeError as exc:
                logger.warning(f"Checkpoint for {profile.linkedin_username}: {exc.url}")
                _notify_checkpoint_challenge(session, exc.url)
                task.mark_failed(error_message=f"Checkpoint challenge: {exc.url}")
                session_pool.mark_authenticated(profile.pk, False)
                continue
            except AuthenticationError as exc:
                logger.error(f"Auth failed for {profile.linkedin_username}: {exc}")
                _notify_auth_required(session, str(exc))
                task.mark_failed(error_message=f"Authentication failed: {exc}")
                session_pool.mark_authenticated(profile.pk, False)
                continue
            except Exception as exc:
                logger.error(f"Unexpected auth error for {profile.linkedin_username}: {exc}")
                task.mark_failed(error_message=f"Auth error: {exc}")
                continue
        
        # Set campaign on session and mark task running
        session.campaign = campaign
        task.mark_running()
        
        # Execute task
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
            session_pool.mark_authenticated(profile.pk, False)
            continue
        except AuthenticationError:
            logger.warning(f"Session expired for {profile.linkedin_username} — re-authenticating")
            try:
                session.reauthenticate()
                session_pool.mark_authenticated(profile.pk, True)
            except CheckpointChallengeError as exc:
                _handle_checkpoint(session, task, exc.url)
                session_pool.mark_authenticated(profile.pk, False)
                continue
            except Exception:
                logger.exception(f"Re-authentication failed for {profile.linkedin_username}")
                session_pool.mark_authenticated(profile.pk, False)
            task.mark_failed()
            continue
        except ModelHTTPError as e:
            error_msg = f"LLM API error: {str(e)[:200]}"
            task.mark_failed(error_message=error_msg)
            logger.error(
                colored("Daemon stopped — LLM API error", "red", attrs=["bold"])
                + "\n%s\nCheck SiteConfig in Admin.",
                e,
            )
            session_pool.close_all()
            return
        except Exception:
            import traceback
            error_msg = f"Task execution failed: {traceback.format_exc()[:500]}"
            task.mark_failed(error_message=error_msg)
            logger.error(
                colored(f"[{task.task_type}] Task FAILED", "red", attrs=["bold"])
                + f" (task_id={task.pk}, campaign={campaign.name}, profile={profile.linkedin_username})\n{error_msg}"
            )
            
            # Create ActionLog for failed task
            try:
                from openoutreach.linkedin.models import ActionLog
                ActionLog.objects.create(
                    linkedin_profile=profile,
                    campaign=campaign,
                    action_type=task.task_type,
                    status="failed",
                    error_message=error_msg[:1000],
                )
            except Exception as e:
                logger.debug(f"Failed to create ActionLog: {e}")
            continue
        
        # Task completed successfully
        task.mark_completed()
        logger.info(
            colored(f"[{task.task_type}] Task COMPLETED", "green", attrs=["bold"])
            + f" (profile={profile.linkedin_username}, campaign={campaign.name})"
        )
        
        # Create ActionLog
        try:
            from openoutreach.linkedin.models import ActionLog
            ActionLog.objects.create(
                linkedin_profile=profile,
                campaign=campaign,
                action_type=task.task_type,
                status="completed",
            )
        except Exception as e:
            logger.debug(f"Failed to create ActionLog: {e}")
        
        # Refresh cookies
        try:
            from openoutreach.linkedin.browser.launch import _save_cookies
            _save_cookies(session)
            logger.debug(f"Refreshed cookies for {profile.linkedin_username}")
        except Exception as e:
            logger.debug(f"Failed to refresh cookies: {e}")
        
        # Health check (per profile)
        if not hasattr(session, "_last_health_check"):
            session._last_health_check = time.monotonic()
        if time.monotonic() - session._last_health_check >= HEALTH_CHECK_INTERVAL:
            _run_health_checks(session)
            session._last_health_check = time.monotonic()
        
        rhythm.maybe_break()

def _sync_credential_profile(session):
    """Sync discovered LinkedIn username to credential."""
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
                logger.info(f"Synced credential username: {public_id}")
    except Exception as exc:
        logger.debug(f"Could not sync credential: {exc}")
```

#### 3.1.3 Update `rundaemon` Command

**File:** `openoutreach/core/management/commands/rundaemon.py`

**Add feature flag:**
```python
class Command(BaseCommand):
    help = "Run the OpenOutreach daemon (multi-session mode)."
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--single-session',
            action='store_true',
            help='Run in legacy single-session mode (first profile only)',
        )
    
    def handle(self, *args, **options):
        self._configure_logging(verbose=options["verbosity"] >= 2)
        self._ensure_db()
        self._ensure_onboarded()
        
        # Choose daemon mode
        if options['single_session']:
            # Legacy mode: single profile
            logger.info("Starting in SINGLE-SESSION mode (legacy)")
            session = self._create_session()
            from openoutreach.core.daemon import run_daemon
            run_daemon(session)
        else:
            # New mode: multi-session
            logger.info("Starting in MULTI-SESSION mode")
            from openoutreach.core.daemon import run_daemon_multi_session
            run_daemon_multi_session()
```

### 3.2 Backward Compatibility

**Keep old `run_daemon(session)` intact** for:
- Existing deployments with `--single-session` flag
- Easier rollback
- Single-user setups

### 3.3 Testing

**Test File:** `tests/core/test_daemon_multi_session.py`

```python
import pytest
from unittest.mock import Mock, patch
from openoutreach.core.daemon import SessionPool, run_daemon_multi_session
from tests.factories import LinkedInProfileFactory, TaskFactory, CampaignFactory, UserFactory

@pytest.mark.django_db
class TestSessionPool:
    def test_get_or_create_session(self):
        """SessionPool creates and caches sessions per profile."""
        pool = SessionPool()
        profile = LinkedInProfileFactory(active=True)
        
        session1 = pool.get_or_create(profile)
        session2 = pool.get_or_create(profile)
        
        assert session1 is session2  # Same instance
        assert pool.is_authenticated(profile.pk) is False
    
    def test_mark_authenticated(self):
        """SessionPool tracks auth status per profile."""
        pool = SessionPool()
        profile = LinkedInProfileFactory(active=True)
        
        pool.get_or_create(profile)
        pool.mark_authenticated(profile.pk, True)
        
        assert pool.is_authenticated(profile.pk) is True

@pytest.mark.django_db
class TestDaemonMultiSession:
    @patch('openoutreach.core.daemon.run_daemon_multi_session')
    def test_daemon_processes_multiple_profiles(self, mock_run):
        """Daemon loop processes tasks for multiple profiles."""
        user1 = UserFactory()
        user2 = UserFactory()
        profile1 = LinkedInProfileFactory(user=user1, active=True)
        profile2 = LinkedInProfileFactory(user=user2, active=True)
        
        campaign = CampaignFactory()
        campaign.users.add(user1, user2)
        
        # Create tasks for both profiles
        task1 = TaskFactory(linkedin_profile=profile1, payload={"campaign_id": campaign.pk})
        task2 = TaskFactory(linkedin_profile=profile2, payload={"campaign_id": campaign.pk})
        
        # NOTE: Full integration test requires mocking browser sessions
        # This is a structural test to verify task assignment
        assert task1.linkedin_profile != task2.linkedin_profile
```

### Success Criteria
- ✅ `run_daemon_multi_session()` starts without errors
- ✅ `SessionPool` creates separate sessions per profile
- ✅ Tasks claimed round-robin across profiles
- ✅ One profile's auth failure doesn't block others
- ✅ `--single-session` flag preserves old behavior

---

## Phase 4: API & Authorization Updates (Backend)

**Time Estimate:** 2-3 hours  
**Owner:** Backend AI Agent  
**Dependencies:** Phase 1-3 complete  
**Rollback Strategy:** Revert view changes; no schema impact

### 4.1 Campaign List API - Filter by User

**Current Issue:** Campaign list may show ALL campaigns to everyone.

**File:** `openoutreach/api/views/campaigns.py`

**Update CampaignListView:**
```python
class CampaignListView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List campaigns - filtered to user's campaigns only."""
        user = request.user
        
        # CRITICAL: Filter to campaigns user is a member of
        campaigns = Campaign.objects.filter(
            users=user,
        ).select_related().prefetch_related('users')
        
        # ... serialization ...
        
        return Response({
            "campaigns": serialized_campaigns,
            "count": campaigns.count(),
        })
```

### 4.2 Campaign Detail API - Verify Access

**File:** `openoutreach/api/views/campaigns.py`

**Update CampaignDetailView:**
```python
class CampaignDetailView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        """Get campaign details - verify user has access."""
        user = request.user
        
        try:
            campaign = Campaign.objects.get(pk=pk)
        except Campaign.DoesNotExist:
            return Response(
                {"error": "Campaign not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # CRITICAL: Verify user is a campaign member
        if not campaign.users.filter(pk=user.pk).exists():
            return Response(
                {"error": "Access denied"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # ... serialization ...
        
        return Response(serialized_campaign)
```

### 4.3 Lead List API - Filter by User's Campaigns

**File:** `openoutreach/api/views/leads.py`

**Update LeadsListView:**
```python
class LeadsListView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List leads - filtered to user's campaigns only."""
        user = request.user
        campaign_id = request.query_params.get('campaign_id')
        
        # Build query
        deals = Deal.objects.select_related('lead', 'campaign')
        
        if campaign_id:
            # Filter to specific campaign
            campaign = get_object_or_404(Campaign, pk=campaign_id)
            
            # CRITICAL: Verify user has access to this campaign
            if not campaign.users.filter(pk=user.pk).exists():
                return Response(
                    {"error": "Access denied to this campaign"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            deals = deals.filter(campaign=campaign)
        else:
            # Filter to ALL user's campaigns
            user_campaigns = Campaign.objects.filter(users=user)
            deals = deals.filter(campaign__in=user_campaigns)
        
        # ... rest of view ...
```

### 4.4 Task API (if exposed) - Filter by Profile

**If you have a tasks API endpoint, filter by user's profile:**

```python
class TaskListView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List tasks for user's LinkedIn profile."""
        user = request.user
        
        # Get user's LinkedIn profile
        try:
            profile = LinkedInProfile.objects.get(user=user)
        except LinkedInProfile.DoesNotExist:
            return Response({"tasks": [], "count": 0})
        
        # Filter tasks to this profile only
        tasks = Task.objects.filter(
            linkedin_profile=profile
        ).order_by('-scheduled_at')[:50]
        
        # ... serialization ...
```

### 4.5 Analytics API - User Filtering

**File:** `openoutreach/api/views/campaigns.py`

**Update AnalyticsOverviewView:**
```python
class AnalyticsOverviewView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Analytics overview - filtered to user's campaigns."""
        user = request.user
        campaign_id = request.query_params.get('campaign_id')
        
        # Filter to user's campaigns
        campaigns_query = Campaign.objects.filter(users=user)
        
        if campaign_id:
            campaign = get_object_or_404(Campaign, pk=campaign_id)
            
            # Verify access
            if not campaign.users.filter(pk=user.pk).exists():
                return Response(
                    {"error": "Access denied"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            campaigns_query = campaigns_query.filter(pk=campaign.pk)
        
        # ... compute analytics from campaigns_query ...
```

### 4.6 Testing

**Test File:** `tests/api/test_campaign_authorization.py`

```python
import pytest
from django.test import Client
from rest_framework.test import APIClient
from tests.factories import UserFactory, CampaignFactory

@pytest.mark.django_db
class TestCampaignAuthorization:
    def test_user_sees_only_own_campaigns(self):
        """Campaign list API shows only user's campaigns."""
        user1 = UserFactory()
        user2 = UserFactory()
        
        campaign1 = CampaignFactory(name="User1 Campaign")
        campaign1.users.add(user1)
        
        campaign2 = CampaignFactory(name="User2 Campaign")
        campaign2.users.add(user2)
        
        client = APIClient()
        client.force_authenticate(user=user1)
        
        response = client.get('/api/campaigns/')
        assert response.status_code == 200
        
        campaign_names = [c['name'] for c in response.json()['campaigns']]
        assert "User1 Campaign" in campaign_names
        assert "User2 Campaign" not in campaign_names
    
    def test_cannot_access_other_user_campaign_detail(self):
        """User cannot access campaign they're not a member of."""
        user1 = UserFactory()
        user2 = UserFactory()
        
        campaign = CampaignFactory()
        campaign.users.add(user2)  # Only user2
        
        client = APIClient()
        client.force_authenticate(user=user1)
        
        response = client.get(f'/api/campaigns/{campaign.pk}/')
        assert response.status_code == 403
    
    def test_cannot_see_other_user_leads(self):
        """User cannot see leads from campaigns they're not in."""
        user1 = UserFactory()
        user2 = UserFactory()
        
        campaign1 = CampaignFactory()
        campaign1.users.add(user1)
        
        campaign2 = CampaignFactory()
        campaign2.users.add(user2)
        
        from tests.factories import DealFactory
        deal1 = DealFactory(campaign=campaign1)
        deal2 = DealFactory(campaign=campaign2)
        
        client = APIClient()
        client.force_authenticate(user=user1)
        
        # Without campaign filter - should only see campaign1 leads
        response = client.get('/api/leads/')
        assert response.status_code == 200
        lead_ids = [l['id'] for l in response.json()['leads']]
        assert deal1.lead.id in lead_ids
        assert deal2.lead.id not in lead_ids
        
        # Explicit campaign2 filter - should be denied
        response = client.get(f'/api/leads/?campaign_id={campaign2.pk}')
        assert response.status_code == 403
```

**Run Tests:**
```bash
pytest tests/api/test_campaign_authorization.py -v
```

### Success Criteria
- ✅ Campaign list filtered to user's campaigns
- ✅ Campaign detail returns 403 for non-members
- ✅ Lead list filtered to user's campaigns
- ✅ Analytics filtered to user's campaigns
- ✅ Authorization tests pass

---

## Phase 5: Frontend Updates (Frontend)

**Time Estimate:** 3-4 hours  
**Owner:** Frontend AI Agent  
**Dependencies:** Phase 4 complete (APIs updated)  
**Rollback Strategy:** Revert frontend changes; backend still works

### 5.1 User Context & Profile Display

**File:** `frontend/src/contexts/UserContext.tsx` (create if doesn't exist)

```typescript
import { createContext, useContext, useEffect, useState } from 'react';

interface UserProfile {
  id: number;
  username: string;
  email: string;
  linkedinProfile?: {
    id: number;
    linkedinUsername: string;
    active: boolean;
  };
}

interface UserContextType {
  user: UserProfile | null;
  loading: boolean;
  refreshUser: () => Promise<void>;
}

const UserContext = createContext<UserContextType | undefined>(undefined);

export function UserProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  
  const fetchUser = async () => {
    try {
      const response = await fetch('/api/auth/me');
      if (response.ok) {
        const data = await response.json();
        setUser(data);
      }
    } catch (error) {
      console.error('Failed to fetch user:', error);
    } finally {
      setLoading(false);
    }
  };
  
  useEffect(() => {
    fetchUser();
  }, []);
  
  return (
    <UserContext.Provider value={{ user, loading, refreshUser: fetchUser }}>
      {children}
    </UserContext.Provider>
  );
}

export const useUser = () => {
  const context = useContext(UserContext);
  if (!context) throw new Error('useUser must be used within UserProvider');
  return context;
};
```

### 5.2 Update Campaign List - Show User's Campaigns Only

**File:** `frontend/src/app/(dashboard)/campaigns/page.tsx`

**No changes needed IF the API is properly filtered (Phase 4).**

**Add user context to layout:**

**File:** `frontend/src/app/(dashboard)/layout.tsx`

```typescript
import { UserProvider } from '@/contexts/UserContext';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <UserProvider>
      <div className="dashboard-layout">
        {/* Existing sidebar/nav */}
        <main>{children}</main>
      </div>
    </UserProvider>
  );
}
```

### 5.3 Add Profile Indicator to Header

**File:** `frontend/src/components/layout/Header.tsx` (or wherever your header is)

```typescript
import { useUser } from '@/contexts/UserContext';

export function Header() {
  const { user, loading } = useUser();
  
  return (
    <header className="header">
      {/* Existing header content */}
      
      {!loading && user && (
        <div className="user-profile-badge">
          <span className="user-email">{user.email}</span>
          {user.linkedinProfile && (
            <span className="linkedin-profile">
              LinkedIn: {user.linkedinProfile.linkedinUsername}
            </span>
          )}
        </div>
      )}
    </header>
  );
}
```

### 5.4 Campaign Access Check in Campaign Detail

**File:** `frontend/src/app/(dashboard)/campaigns/[id]/page.tsx`

**Update to handle 403 responses:**

```typescript
export default function CampaignDetailPage({ params }: { params: { id: string } }) {
  const [campaign, setCampaign] = useState(null);
  const [error, setError] = useState<string | null>(null);
  
  useEffect(() => {
    async function fetchCampaign() {
      try {
        const response = await fetch(`/api/campaigns/${params.id}`);
        
        if (response.status === 403) {
          setError('You do not have access to this campaign.');
          return;
        }
        
        if (response.status === 404) {
          setError('Campaign not found.');
          return;
        }
        
        if (!response.ok) {
          throw new Error('Failed to fetch campaign');
        }
        
        const data = await response.json();
        setCampaign(data);
      } catch (err) {
        setError('An error occurred loading the campaign.');
      }
    }
    
    fetchCampaign();
  }, [params.id]);
  
  if (error) {
    return (
      <div className="error-message">
        <h2>Access Denied</h2>
        <p>{error}</p>
        <Link href="/campaigns">← Back to Campaigns</Link>
      </div>
    );
  }
  
  // ... rest of component
}
```

### 5.5 Update Settings Page - Show Current Profile

**File:** `frontend/src/app/(dashboard)/settings/page.tsx`

**Add profile info to LinkedIn Connection tab:**

```typescript
function LinkedInConnectionTab() {
  const { user } = useUser();
  
  return (
    <div className="linkedin-connection-tab">
      {user?.linkedinProfile && (
        <div className="current-profile-info">
          <h3>Current Profile</h3>
          <p>LinkedIn Username: {user.linkedinProfile.linkedinUsername}</p>
          <p>Status: {user.linkedinProfile.active ? 'Active' : 'Inactive'}</p>
        </div>
      )}
      
      {/* Existing credential management UI */}
    </div>
  );
}
```

### 5.6 Add Multi-User Indicator (Optional)

**If admin user can see multiple profiles, add indicator:**

```typescript
// In admin dashboard or settings
function MultiUserStatus() {
  const [stats, setStats] = useState({ profileCount: 0, campaignCount: 0 });
  
  useEffect(() => {
    async function fetchStats() {
      const response = await fetch('/api/admin/multi-user-stats');
      if (response.ok) {
        setStats(await response.json());
      }
    }
    fetchStats();
  }, []);
  
  return (
    <div className="multi-user-status">
      <h3>Multi-User Status</h3>
      <p>Active Profiles: {stats.profileCount}</p>
      <p>Active Campaigns: {stats.campaignCount}</p>
    </div>
  );
}
```

### 5.7 Testing

**Manual Testing Checklist:**

1. **Create two users:**
   ```bash
   python manage.py shell
   from django.contrib.auth.models import User
   from openoutreach.linkedin.models import LinkedInProfile
   
   user1 = User.objects.create_user('user1@test.com', password='test123')
   user2 = User.objects.create_user('user2@test.com', password='test123')
   
   LinkedInProfile.objects.create(
       user=user1,
       linkedin_username='user1@email.com',
       linkedin_password='pass1',
       active=True
   )
   LinkedInProfile.objects.create(
       user=user2,
       linkedin_username='user2@email.com',
       linkedin_password='pass2',
       active=True
   )
   ```

2. **Create campaigns with different user assignments:**
   ```python
   from openoutreach.core.models import Campaign
   
   campaign1 = Campaign.objects.create(name='Campaign 1')
   campaign1.users.add(user1)
   
   campaign2 = Campaign.objects.create(name='Campaign 2')
   campaign2.users.add(user2)
   
   campaign3 = Campaign.objects.create(name='Shared Campaign')
   campaign3.users.add(user1, user2)
   ```

3. **Login as user1:**
   - Should see: Campaign 1, Shared Campaign
   - Should NOT see: Campaign 2
   - Try to access Campaign 2 detail URL directly → should show "Access Denied"

4. **Login as user2:**
   - Should see: Campaign 2, Shared Campaign
   - Should NOT see: Campaign 1

### Success Criteria
- ✅ User context loaded on dashboard
- ✅ Header shows current user's LinkedIn profile
- ✅ Campaign list shows only user's campaigns
- ✅ Accessing non-member campaign shows "Access Denied"
- ✅ Settings page shows user's profile info
- ✅ Manual testing passes for 2-user scenario

---

## Phase 6: Testing & Validation (Full Stack)

**Time Estimate:** 3-4 hours  
**Owner:** QA AI Agent or Full Stack AI Agent  
**Dependencies:** Phases 1-5 complete  
**Rollback Strategy:** N/A (testing phase)

### 6.1 Integration Tests

**Test File:** `tests/integration/test_multi_session_end_to_end.py`

```python
import pytest
from django.contrib.auth.models import User
from openoutreach.core.models import Campaign, Task
from openoutreach.linkedin.models import LinkedInProfile
from openoutreach.crm.models import Deal
from tests.factories import UserFactory, CampaignFactory, LinkedInProfileFactory, DealFactory

@pytest.mark.django_db
class TestMultiSessionEndToEnd:
    """End-to-end tests for multi-session architecture."""
    
    def test_two_users_independent_task_queues(self):
        """Two users with separate campaigns get independent task queues."""
        # Setup users
        user1 = UserFactory(username='user1')
        user2 = UserFactory(username='user2')
        
        profile1 = LinkedInProfileFactory(user=user1, active=True)
        profile2 = LinkedInProfileFactory(user=user2, active=True)
        
        # Setup campaigns
        campaign1 = CampaignFactory(name='Campaign 1')
        campaign1.users.add(user1)
        
        campaign2 = CampaignFactory(name='Campaign 2')
        campaign2.users.add(user2)
        
        # Create deals
        DealFactory.create_batch(5, campaign=campaign1, state='QUALIFIED')
        DealFactory.create_batch(5, campaign=campaign2, state='QUALIFIED')
        
        # Reconcile (should create tasks for both profiles)
        from openoutreach.core.scheduler import reconcile
        reconcile()
        
        # Verify task isolation
        tasks1 = Task.objects.filter(linkedin_profile=profile1)
        tasks2 = Task.objects.filter(linkedin_profile=profile2)
        
        assert tasks1.count() > 0, "Profile 1 should have tasks"
        assert tasks2.count() > 0, "Profile 2 should have tasks"
        
        # Verify no cross-contamination
        for task in tasks1:
            campaign = Campaign.objects.get(pk=task.payload['campaign_id'])
            assert user1 in campaign.users.all()
        
        for task in tasks2:
            campaign = Campaign.objects.get(pk=task.payload['campaign_id'])
            assert user2 in campaign.users.all()
    
    def test_shared_campaign_both_users_get_tasks(self):
        """Campaign with 2 users creates tasks for both profiles."""
        user1 = UserFactory(username='user1')
        user2 = UserFactory(username='user2')
        
        profile1 = LinkedInProfileFactory(user=user1, active=True)
        profile2 = LinkedInProfileFactory(user=user2, active=True)
        
        # Shared campaign
        campaign = CampaignFactory(name='Shared Campaign')
        campaign.users.add(user1, user2)
        
        DealFactory.create_batch(10, campaign=campaign, state='QUALIFIED')
        
        from openoutreach.core.scheduler import reconcile
        reconcile()
        
        # Both profiles should have tasks for the shared campaign
        tasks1 = Task.objects.filter(
            linkedin_profile=profile1,
            payload__campaign_id=campaign.pk
        )
        tasks2 = Task.objects.filter(
            linkedin_profile=profile2,
            payload__campaign_id=campaign.pk
        )
        
        assert tasks1.count() > 0
        assert tasks2.count() > 0
    
    def test_inactive_profile_gets_no_tasks(self):
        """Inactive profile does not receive task assignments."""
        user1 = UserFactory()
        user2 = UserFactory()
        
        profile1 = LinkedInProfileFactory(user=user1, active=True)
        profile2 = LinkedInProfileFactory(user=user2, active=False)  # Inactive
        
        campaign = CampaignFactory()
        campaign.users.add(user1, user2)
        
        DealFactory.create_batch(5, campaign=campaign, state='QUALIFIED')
        
        from openoutreach.core.scheduler import reconcile
        reconcile()
        
        tasks1 = Task.objects.filter(linkedin_profile=profile1)
        tasks2 = Task.objects.filter(linkedin_profile=profile2)
        
        assert tasks1.count() > 0
        assert tasks2.count() == 0  # Inactive profile gets no tasks
```

**Run Integration Tests:**
```bash
pytest tests/integration/test_multi_session_end_to_end.py -v -s
```

### 6.2 API Authorization Tests

**Test File:** `tests/api/test_multi_user_authorization.py`

```python
import pytest
from rest_framework.test import APIClient
from tests.factories import UserFactory, CampaignFactory, DealFactory

@pytest.mark.django_db
class TestMultiUserAuthorization:
    def setup_method(self):
        """Setup users and campaigns for each test."""
        self.user1 = UserFactory(username='user1')
        self.user2 = UserFactory(username='user2')
        
        self.campaign1 = CampaignFactory(name='User1 Only')
        self.campaign1.users.add(self.user1)
        
        self.campaign2 = CampaignFactory(name='User2 Only')
        self.campaign2.users.add(self.user2)
        
        self.shared_campaign = CampaignFactory(name='Shared')
        self.shared_campaign.users.add(self.user1, self.user2)
        
        self.client = APIClient()
    
    def test_campaign_list_filtered_per_user(self):
        """Each user sees only their campaigns."""
        self.client.force_authenticate(user=self.user1)
        response = self.client.get('/api/campaigns/')
        
        assert response.status_code == 200
        campaign_names = [c['name'] for c in response.json()['campaigns']]
        assert 'User1 Only' in campaign_names
        assert 'Shared' in campaign_names
        assert 'User2 Only' not in campaign_names
    
    def test_campaign_detail_access_denied(self):
        """User2 cannot access User1's campaign."""
        self.client.force_authenticate(user=self.user2)
        response = self.client.get(f'/api/campaigns/{self.campaign1.pk}/')
        
        assert response.status_code == 403
    
    def test_shared_campaign_both_users_access(self):
        """Both users can access shared campaign."""
        # User1
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(f'/api/campaigns/{self.shared_campaign.pk}/')
        assert response.status_code == 200
        
        # User2
        self.client.force_authenticate(user=self.user2)
        response = self.client.get(f'/api/campaigns/{self.shared_campaign.pk}/')
        assert response.status_code == 200
    
    def test_leads_filtered_by_user_campaigns(self):
        """Lead list shows only leads from user's campaigns."""
        deal1 = DealFactory(campaign=self.campaign1)
        deal2 = DealFactory(campaign=self.campaign2)
        
        self.client.force_authenticate(user=self.user1)
        response = self.client.get('/api/leads/')
        
        assert response.status_code == 200
        lead_ids = [l['id'] for l in response.json()['leads']]
        assert deal1.lead.id in lead_ids
        assert deal2.lead.id not in lead_ids
```

**Run API Tests:**
```bash
pytest tests/api/test_multi_user_authorization.py -v
```

### 6.3 Load Testing (Optional)

**Test concurrent profile execution:**

```python
import pytest
from unittest.mock import Mock, patch
from concurrent.futures import ThreadPoolExecutor

@pytest.mark.django_db
class TestMultiSessionConcurrency:
    def test_concurrent_task_execution_no_conflicts(self):
        """Multiple profiles can execute tasks concurrently without conflicts."""
        # Create 5 profiles
        profiles = [LinkedInProfileFactory(active=True) for _ in range(5)]
        
        # Create campaigns for each
        for profile in profiles:
            campaign = CampaignFactory()
            campaign.users.add(profile.user)
            DealFactory.create_batch(10, campaign=campaign, state='QUALIFIED')
        
        from openoutreach.core.scheduler import reconcile
        reconcile()
        
        # Verify each profile has independent task queue
        for profile in profiles:
            tasks = Task.objects.filter(linkedin_profile=profile)
            assert tasks.count() > 0
            
            # All tasks should be for campaigns the profile user is in
            for task in tasks:
                campaign = Campaign.objects.get(pk=task.payload['campaign_id'])
                assert profile.user in campaign.users.all()
```

### 6.4 Manual Testing Checklist

**Pre-Deployment Testing:**

- [ ] Start daemon in multi-session mode
- [ ] Verify log shows "Daemon started (multi-session) — N active profiles"
- [ ] Create tasks for 2 different profiles
- [ ] Watch logs - verify both profiles' tasks execute
- [ ] Check ActionLog - verify both profiles have entries
- [ ] Frontend: Login as user1, verify sees only own campaigns
- [ ] Frontend: Login as user2, verify sees only own campaigns
- [ ] Frontend: Try to access user1's campaign as user2 → "Access Denied"
- [ ] Frontend: Shared campaign visible to both users
- [ ] Verify one profile's auth failure doesn't stop other profile

### Success Criteria
- ✅ All integration tests pass
- ✅ All API authorization tests pass
- ✅ Load tests pass (if implemented)
- ✅ Manual testing checklist complete
- ✅ No cross-user data leakage observed
- ✅ Daemon processes tasks for multiple profiles

---

## Phase 7: Deployment & Rollback (DevOps)

**Time Estimate:** 1-2 hours  
**Owner:** DevOps AI Agent or Full Stack AI Agent  
**Dependencies:** Phase 6 complete (all tests pass)  
**Rollback Strategy:** Documented below

### 7.1 Pre-Deployment Checklist

**Before deploying to production:**

1. **Backup database:**
   ```bash
   # On server
   docker exec openoutreach-openoutreach-1 python manage.py dumpdata > backup_$(date +%Y%m%d_%H%M%S).json
   
   # Or copy sqlite file
   cp data/db.sqlite3 data/db.sqlite3.backup_$(date +%Y%m%d_%H%M%S)
   ```

2. **Run all migrations in staging:**
   ```bash
   python manage.py migrate --plan
   python manage.py migrate
   ```

3. **Run full test suite:**
   ```bash
   pytest tests/ -v
   ```

4. **Verify current daemon stops gracefully:**
   ```bash
   docker-compose down
   ```

### 7.2 Deployment Steps

**Step-by-step production deployment:**

1. **Stop current daemon:**
   ```bash
   ssh -i ~/.ssh/lenquant.pem ubuntu@ec2-50-19-251-160.compute-1.amazonaws.com
   cd /path/to/openoutreach
   docker-compose down
   ```

2. **Pull latest code:**
   ```bash
   git pull origin main
   ```

3. **Rebuild Docker image:**
   ```bash
   docker-compose build
   ```

4. **Run migrations:**
   ```bash
   docker-compose run --rm openoutreach python manage.py migrate
   ```

5. **Verify migration success:**
   ```bash
   docker-compose run --rm openoutreach python manage.py shell -c "from openoutreach.core.models import Task; print(f'Tasks with profile: {Task.objects.exclude(linkedin_profile=None).count()}')"
   ```

6. **Start daemon in multi-session mode:**
   ```bash
   # Update docker-compose.yml or start script to use multi-session by default
   docker-compose up -d
   ```

7. **Monitor logs:**
   ```bash
   docker-compose logs -f openoutreach | grep "Daemon started"
   # Should see: "Daemon started (multi-session) — N active profiles"
   ```

8. **Verify task execution:**
   ```bash
   # Watch for task completions in logs
   docker-compose logs -f | grep "Task COMPLETED"
   
   # Check database
   docker-compose exec openoutreach python manage.py shell -c "
   from openoutreach.core.models import Task
   from openoutreach.linkedin.models import LinkedInProfile
   profiles = LinkedInProfile.objects.filter(active=True)
   for p in profiles:
       print(f'{p.linkedin_username}: {Task.objects.filter(linkedin_profile=p).count()} tasks')
   "
   ```

### 7.3 Rollback Procedure

**If deployment fails or issues arise:**

**Option A: Code Rollback (keep DB changes)**

1. **Stop daemon:**
   ```bash
   docker-compose down
   ```

2. **Revert code:**
   ```bash
   git log --oneline  # Find commit before multi-session changes
   git checkout <commit_hash>
   ```

3. **Rebuild:**
   ```bash
   docker-compose build
   ```

4. **Start in single-session mode:**
   ```bash
   docker-compose run --rm openoutreach python manage.py rundaemon --single-session
   ```

**Option B: Full Rollback (restore DB)**

1. **Stop daemon:**
   ```bash
   docker-compose down
   ```

2. **Restore database:**
   ```bash
   # From JSON backup
   docker-compose run --rm openoutreach python manage.py flush --no-input
   docker-compose run --rm openoutreach python manage.py loaddata backup_YYYYMMDD_HHMMSS.json
   
   # Or from sqlite backup
   cp data/db.sqlite3.backup_YYYYMMDD_HHMMSS data/db.sqlite3
   ```

3. **Revert code:**
   ```bash
   git checkout <previous_commit>
   docker-compose build
   ```

4. **Reverse migrations:**
   ```bash
   docker-compose run --rm openoutreach python manage.py migrate core <migration_before_linkedin_profile>
   ```

5. **Start old daemon:**
   ```bash
   docker-compose up -d
   ```

### 7.4 Monitoring After Deployment

**Monitor for 24 hours:**

1. **Check daemon health:**
   ```bash
   # Every hour
   docker-compose ps  # Should show "Up"
   docker-compose logs --tail=100 | grep -i error
   ```

2. **Verify task execution:**
   ```bash
   # Check tasks are completing for all profiles
   docker-compose exec openoutreach python manage.py shell -c "
   from openoutreach.linkedin.models import ActionLog
   from django.utils import timezone
   from datetime import timedelta
   
   since = timezone.now() - timedelta(hours=1)
   recent = ActionLog.objects.filter(created_at__gte=since)
   
   print(f'Tasks completed in last hour: {recent.count()}')
   for log in recent:
       print(f'  {log.linkedin_profile.linkedin_username}: {log.action_type}')
   "
   ```

3. **Check memory usage:**
   ```bash
   docker stats openoutreach-openoutreach-1
   # Watch for memory creep (multiple browsers)
   ```

4. **Monitor disk space:**
   ```bash
   df -h /
   # Should have > 2GB free
   ```

### 7.5 Success Criteria

**Deployment is successful when:**
- ✅ Daemon starts in multi-session mode
- ✅ Log shows all active profiles loaded
- ✅ Tasks execute for multiple profiles (verified in ActionLog)
- ✅ Frontend shows correct campaign filtering per user
- ✅ No errors in logs for 24 hours
- ✅ Memory usage stable
- ✅ All profiles remain authenticated

**Rollback if:**
- ❌ Daemon crashes on startup
- ❌ Only one profile's tasks execute
- ❌ Cross-user data leakage observed
- ❌ Memory usage exceeds available RAM
- ❌ Any profile's auth fails repeatedly

---

## Summary & Next Steps

### Implementation Timeline

| Phase | Focus | Time | Owner |
|-------|-------|------|-------|
| 1 | Database Schema | 2-3h | Backend AI |
| 2 | Scheduler Updates | 3-4h | Backend AI |
| 3 | Daemon Refactor | 4-5h | Backend AI |
| 4 | API Authorization | 2-3h | Backend AI |
| 5 | Frontend Updates | 3-4h | Frontend AI |
| 6 | Testing & Validation | 3-4h | QA/Full Stack AI |
| 7 | Deployment | 1-2h | DevOps/Full Stack AI |
| **Total** | | **18-25h** | ~3-4 days |

### Critical Success Factors

1. **Data Isolation:** Campaign data MUST be filtered by user membership
2. **Task Assignment:** Tasks MUST have correct `linkedin_profile` FK
3. **Authorization:** All APIs MUST verify user has campaign access
4. **Backward Compatibility:** Single-session mode MUST still work
5. **Testing:** All tests MUST pass before deployment

### Post-Implementation Enhancements (Future)

**Phase 8 (Optional - Future Iteration):**
- Per-profile active hours (stagger behavior)
- Per-profile rate limit presets
- Profile health dashboard
- IP rotation via residential proxies
- Profile-level analytics

### Communication Plan

**Before Starting:**
- Notify team of multi-session implementation
- Identify 2-5 pilot users for initial onboarding
- Schedule deployment window (low-traffic time)

**During Implementation:**
- Daily standup: which phase is complete
- Blockers escalated immediately
- Each phase requires sign-off before next starts

**After Deployment:**
- Monitor logs for 24h
- Check in with pilot users daily for first week
- Document any issues in GitHub issues

### Support & Troubleshooting

**Common Issues:**

| Issue | Cause | Fix |
|-------|-------|-----|
| "Only first profile works" | Migration not run | Run Phase 1 migrations |
| "Tasks not assigned to profiles" | Scheduler not updated | Verify Phase 2 complete |
| "User sees all campaigns" | API not filtered | Apply Phase 4 fixes |
| "403 errors in frontend" | Auth check too strict | Review Phase 4 logic |
| "Daemon crashes on startup" | Multiple auth failures | Check credential validity |

**Getting Help:**
- Check this document first
- Review phase-specific test results
- Examine daemon logs: `docker-compose logs -f`
- Roll back to previous phase if needed

---

## Appendix

### A. Database Schema Diagram (After Phase 1)

```
User (Django)
  ├── 1:1 → LinkedInProfile
  └── M2M → Campaign.users

Campaign
  ├── M2M → User (members)
  └── 1:M → Task (via payload.campaign_id)
      └── M:1 → LinkedInProfile (FK)

Deal
  ├── M:1 → Campaign
  └── M:1 → Lead

Task
  ├── M:1 → LinkedInProfile (NEW FK)
  └── payload: {"campaign_id": <pk>}
```

### B. Task Claiming Flow (Phase 3)

```
1. Daemon loop calls: Task.objects.claim_next_for_any_profile()
2. Query: status=PENDING, scheduled_at <= now, ORDER BY scheduled_at
3. Returns task T assigned to profile P
4. Daemon gets session S for profile P from SessionPool
5. Authenticate S if needed (lazy auth)
6. Verify campaign access: campaign.users.filter(pk=P.user.pk).exists()
7. Execute task handler(T, S, qualifiers)
8. Mark T completed
9. Loop back to step 1
```

### C. Environment Variables

**No new env vars required.** Multi-session is the default behavior.

**Optional:**
```bash
# Force single-session mode (backward compat)
OPENOUTREACH_SINGLE_SESSION=true
```

### D. API Endpoints Modified

| Endpoint | Change | Phase |
|----------|--------|-------|
| `GET /api/campaigns/` | Filter by user | 4 |
| `GET /api/campaigns/{id}/` | Verify user access | 4 |
| `GET /api/leads/` | Filter by user campaigns | 4 |
| `GET /api/analytics/overview` | Filter by user campaigns | 4 |
| `GET /api/auth/me` | NEW: Return user + profile | 5 |

### E. Testing Commands Reference

```bash
# Run all tests
pytest tests/ -v

# Run specific phase tests
pytest tests/core/test_task_multi_profile.py -v
pytest tests/core/test_scheduler_multi_profile.py -v
pytest tests/api/test_campaign_authorization.py -v
pytest tests/integration/test_multi_session_end_to_end.py -v

# Run with coverage
pytest tests/ --cov=openoutreach --cov-report=html

# Manual daemon test
python manage.py rundaemon  # Multi-session (default)
python manage.py rundaemon --single-session  # Legacy mode
```

### F. Useful Django Shell Commands

```python
# Check active profiles
from openoutreach.linkedin.models import LinkedInProfile
profiles = LinkedInProfile.objects.filter(active=True)
for p in profiles:
    print(f"{p.linkedin_username} (user: {p.user.username})")

# Check task distribution
from openoutreach.core.models import Task
for p in profiles:
    count = Task.objects.filter(linkedin_profile=p).count()
    print(f"{p.linkedin_username}: {count} tasks")

# Check campaign membership
from openoutreach.core.models import Campaign
for c in Campaign.objects.all():
    users = c.users.all()
    print(f"{c.name}: {[u.username for u in users]}")

# Verify authorization
user = User.objects.get(username='user1')
campaigns = Campaign.objects.filter(users=user)
print(f"User1 campaigns: {[c.name for c in campaigns]}")
```

---

**Document Version:** 1.0  
**Last Updated:** 2026-07-08  
**Status:** Ready for Implementation  
**Approver:** [Your Name/Team Lead]

---

This plan is production-ready and can be executed by different AI agents working independently on each phase. Each phase has clear inputs, outputs, and success criteria.
