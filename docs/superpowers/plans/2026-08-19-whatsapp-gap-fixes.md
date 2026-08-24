# WhatsApp Gap Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the 4 highest-priority gaps between the WhatsApp and LinkedIn integrations: Task channel isolation, WA message attempt counter, per-channel analytics, and non-one-shot Maps discovery.

**Architecture:** Four independent tasks in priority order. Each touches a small, isolated surface. No cross-task dependencies - they can be reviewed separately. MongoDB schema changes are additive (new fields with defaults); no migrations needed.

**Tech Stack:** Python 3.11+, FastAPI, MongoDB (pymongo), Playwright (WA browser), pytest.

**Spec:** `docs/superpowers/plans/2026-08-19-whatsapp-gap-fixes.md` (this file)

## Global Constraints

- Python env: `.venv/bin/python` (never `python3`).
- Commits: single-line messages, no `Co-Authored-By`.
- After every task: `make lint && make pyright`, fix any errors before committing.
- MongoDB schema: additive only - new fields with defaults, no field removals.
- No subagents. Execute tasks sequentially.
- No comments unless WHY is non-obvious.
- Frontend UI components must use `shadcn@latest`.

---

## Task 1: Add `channel` discriminator to Task model

**Problem:** `Task.linkedin_profile_id` stores both LinkedIn and WhatsApp profile IDs. WA tasks are claimed by the daemon via `claim_next(linkedin_profile_id=wa_profile_id)` - semantically wrong, risks silent cross-claims if UUIDs ever collide, blocks future per-channel filtering.

**Files:**
- Modify: `openoutreach/mongodb/models.py` - add `channel` field to `Task`
- Modify: `openoutreach/core/scheduler.py` - stamp `channel="whatsapp"` on WA tasks; `channel="linkedin"` on LI tasks
- Modify: `openoutreach/core/daemon.py` - filter `claim_next` by `channel="whatsapp"` for WA loop
- Modify: `openoutreach/core/daemon_remote.py` - same for remote daemon WA claim loop
- Test: `tests/test_task_channel.py`

**Interfaces:**
- Produces: `Task.channel: str` (default `"linkedin"`); `claim_next(linkedin_profile_id=..., channel=None)` - backward-compat optional channel filter.

- [ ] **Step 1: Write failing test**

```python
# tests/test_task_channel.py
import pytest
from openoutreach.mongodb.models import Task


def test_task_defaults_to_linkedin_channel():
    t = Task(task_type=Task.TaskType.CONNECT, payload={"campaign_id": "c1"})
    assert t.channel == "linkedin"


def test_task_whatsapp_channel_serialises():
    t = Task(
        task_type=Task.TaskType.WHATSAPP_MESSAGE,
        payload={"campaign_id": "c1"},
        channel="whatsapp",
    )
    d = t.to_dict()
    assert d["channel"] == "whatsapp"


def test_task_roundtrip_channel():
    t = Task(
        task_type=Task.TaskType.WHATSAPP_FOLLOW_UP,
        payload={"campaign_id": "c1"},
        channel="whatsapp",
    )
    d = t.to_dict()
    t2 = Task.from_dict(d)
    assert t2.channel == "whatsapp"


def test_task_from_dict_missing_channel_defaults_linkedin():
    d = {"task_type": "connect", "payload": {"campaign_id": "c1"}}
    t = Task.from_dict(d)
    assert t.channel == "linkedin"
```

- [ ] **Step 2: Run test, verify FAIL**

```bash
.venv/bin/python -m pytest tests/test_task_channel.py -v
```

Expected: `AttributeError: 'Task' object has no attribute 'channel'`

- [ ] **Step 3: Add `channel` field to `Task` in `openoutreach/mongodb/models.py`**

Find the `Task.__init__` signature (around line 4374). Add `channel: str = "linkedin"` parameter:

```python
def __init__(
    self,
    ...
    linkedin_profile_id: Optional[str] = None,
    channel: str = "linkedin",          # <-- add here
    created_at: Optional[datetime] = None,
    ...
):
    ...
    self.linkedin_profile_id = linkedin_profile_id
    self.channel = channel              # <-- add here
```

In `to_dict()`, add:
```python
data["channel"] = self.channel
```

In `from_dict()`, add:
```python
channel=data.get("channel", "linkedin"),
```

- [ ] **Step 4: Update `claim_next` to accept optional `channel` filter**

In `openoutreach/mongodb/models.py`, find `claim_next` (around line 4632):

```python
def claim_next(
    self,
    linkedin_profile_id: Optional[str] = None,
    channel: Optional[str] = None,        # <-- add
) -> Optional["Task"]:
    ...
    query = {"status": Task.STATUS_PENDING, "scheduled_at": {"$lte": now}}
    if linkedin_profile_id:
        query["linkedin_profile_id"] = linkedin_profile_id
    if channel is not None:                # <-- add
        query["channel"] = channel         # <-- add
    ...
```

Also update `seconds_to_next` the same way:

```python
def seconds_to_next(
    self,
    linkedin_profile_id: Optional[str] = None,
    channel: Optional[str] = None,
) -> Optional[float]:
    ...
    query = {"status": Task.STATUS_PENDING}
    if linkedin_profile_id:
        query["linkedin_profile_id"] = linkedin_profile_id
    if channel is not None:
        query["channel"] = channel
    ...
```

- [ ] **Step 5: Stamp `channel` in scheduler WA planners**

In `openoutreach/core/scheduler.py`, find `_plan_slots`. Add `channel="linkedin"` parameter and thread it through to `Task(...)`:

```python
def _plan_slots(
    task_type, campaign_pk, n, velocity,
    *, linkedin_profile_id=None, user_id=None, channel="linkedin",
):
    ...
    # inside the loop where Task is created:
    task = Task(
        task_type=task_type,
        payload={"campaign_id": campaign_pk},
        scheduled_at=scheduled_at,
        linkedin_profile_id=linkedin_profile_id,
        user_id=user_id,
        channel=channel,
    )
```

Then update all three WA planners to pass `channel="whatsapp"`:

```python
# plan_whatsapp_window:
created = _plan_slots(
    Task.TaskType.WHATSAPP_MESSAGE, campaign.pk, n, velocity,
    linkedin_profile_id=whatsapp_profile_id,
    user_id=user_id,
    channel="whatsapp",
)

# plan_whatsapp_follow_up_window:
created = _plan_slots(
    Task.TaskType.WHATSAPP_FOLLOW_UP, campaign.pk, n, velocity,
    linkedin_profile_id=whatsapp_profile_id,
    user_id=user_id,
    channel="whatsapp",
)

# plan_whatsapp_sync_window:
created = _plan_slots(
    Task.TaskType.WHATSAPP_SYNC, campaign.pk, n, velocity,
    linkedin_profile_id=whatsapp_profile_id,
    user_id=user_id,
    channel="whatsapp",
)
```

Also update `_has_pending` to accept and filter by channel:

```python
def _has_pending(task_type, campaign_pk, linkedin_profile_id=None, channel=None):
    query = {
        "task_type": task_type,
        "campaign_id": campaign_pk,
        "status": Task.STATUS_PENDING,
    }
    if linkedin_profile_id:
        query["linkedin_profile_id"] = linkedin_profile_id
    if channel is not None:
        query["channel"] = channel
    ...
```

Update calls to `_has_pending` in all three WA planners:

```python
if _has_pending(Task.TaskType.WHATSAPP_MESSAGE, campaign.pk,
                linkedin_profile_id=whatsapp_profile_id, channel="whatsapp"):
    return 0
```

- [ ] **Step 6: Update daemon WA claim loop to filter by channel**

In `openoutreach/core/daemon.py`, find the WA claim loop (line ~729):

```python
wa_task = Task.objects.claim_next(linkedin_profile_id=wa_profile_id)
```

Change to:

```python
wa_task = Task.objects.claim_next(linkedin_profile_id=wa_profile_id, channel="whatsapp")
```

- [ ] **Step 7: Update daemon_remote.py WA claim loop**

```bash
grep -n "claim_next" openoutreach/core/daemon_remote.py
```

Find the WA claim call and add `channel="whatsapp"`. LinkedIn claim calls should add `channel="linkedin"`.

- [ ] **Step 8: Run tests**

```bash
.venv/bin/python -m pytest tests/test_task_channel.py -v
```

Expected: all 4 PASS.

- [ ] **Step 9: Lint and type-check**

```bash
make lint && make pyright
```

Fix any errors.

- [ ] **Step 10: Commit**

```bash
git add openoutreach/mongodb/models.py openoutreach/core/scheduler.py openoutreach/core/daemon.py openoutreach/core/daemon_remote.py tests/test_task_channel.py
git commit -m "feat: add channel discriminator to Task model, stamp whatsapp on WA tasks"
```

---

## Task 2: WhatsApp message attempt counter

**Problem:** When `send_message` fails (non-ban), the deal stays QUALIFIED forever. The next reconcile plans another `whatsapp_message` task and the same deal is retried infinitely, clogging the queue.

**Files:**
- Modify: `openoutreach/whatsapp/tasks/send_message.py` - increment `connect_attempts` on failure; FAIL deal after `MAX_WA_MESSAGE_ATTEMPTS`
- Modify: `openoutreach/core/scheduler.py` - exclude exhausted deals from `plan_whatsapp_window`
- Test: `tests/whatsapp/test_send_message_attempts.py`

**Interfaces:**
- Consumes: `Deal.connect_attempts: int`, `Deal.DealState.FAILED`, `Deal.save()`
- Produces: `MAX_WA_MESSAGE_ATTEMPTS = 3` constant in `send_message.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/whatsapp/test_send_message_attempts.py
"""Tests for WhatsApp send_message attempt counter."""
import pytest
from unittest.mock import MagicMock, patch


def _make_deal(connect_attempts=0, state="Qualified"):
    deal = MagicMock()
    deal._id = "deal-001"
    deal.connect_attempts = connect_attempts
    deal.state = state
    deal.user_id = "user-001"
    deal.last_outgoing_at = None
    return deal


def test_failed_send_increments_attempts():
    """Non-ban failure increments connect_attempts."""
    from openoutreach.whatsapp.tasks.send_message import _handle_send_failure
    deal = _make_deal(connect_attempts=0)
    _handle_send_failure(deal, banned=False)
    assert deal.connect_attempts == 1
    deal.save.assert_called_once()


def test_max_attempts_transitions_to_failed():
    """After MAX_WA_MESSAGE_ATTEMPTS failures, deal moves to FAILED."""
    from openoutreach.whatsapp.tasks.send_message import (
        _handle_send_failure,
        MAX_WA_MESSAGE_ATTEMPTS,
    )
    from openoutreach.mongodb.models import Deal
    deal = _make_deal(connect_attempts=MAX_WA_MESSAGE_ATTEMPTS - 1)
    _handle_send_failure(deal, banned=False)
    assert deal.state == Deal.DealState.FAILED
    assert deal.connect_attempts == MAX_WA_MESSAGE_ATTEMPTS


def test_ban_does_not_increment_attempts():
    """Ban detection should NOT increment connect_attempts."""
    from openoutreach.whatsapp.tasks.send_message import _handle_send_failure
    deal = _make_deal(connect_attempts=0)
    _handle_send_failure(deal, banned=True)
    assert deal.connect_attempts == 0
```

- [ ] **Step 2: Run tests, verify FAIL**

```bash
.venv/bin/python -m pytest tests/whatsapp/test_send_message_attempts.py -v
```

Expected: `ImportError: cannot import name '_handle_send_failure'`

- [ ] **Step 3: Add `_handle_send_failure` and `MAX_WA_MESSAGE_ATTEMPTS` to `send_message.py`**

At the top of `openoutreach/whatsapp/tasks/send_message.py`, after the imports, add:

```python
MAX_WA_MESSAGE_ATTEMPTS = 3


def _handle_send_failure(deal, *, banned: bool) -> None:
    """Increment attempt counter on non-ban send failure; FAIL deal at max."""
    if banned:
        return
    from openoutreach.mongodb.models import Deal
    deal.connect_attempts += 1
    if deal.connect_attempts >= MAX_WA_MESSAGE_ATTEMPTS:
        deal.state = Deal.DealState.FAILED
        deal.reason = f"WA send failed after {deal.connect_attempts} attempts"
    deal.save()
```

- [ ] **Step 4: Wire `_handle_send_failure` into the failure branch in `handle_whatsapp_message`**

Find the failure branch (around line 94 in `send_message.py`) and replace:

```python
        if not success:
            logger.warning(
                "WA send_message [%s]: send failed for lead %s", campaign, lead.phone
            )
            banned = wa_session.detect_ban()
            if banned:
                from openoutreach.whatsapp.models.profile import STATUS_BANNED
                wa_session.wa_profile.status = STATUS_BANNED
                wa_session.wa_profile.save(update_fields=["status"])
                logger.error(
                    "WA send_message: profile %s appears BANNED - marking and halting",
                    wa_session.wa_profile,
                )
                return
            _handle_send_failure(deal, banned=False)
            if deal.state == Deal.DealState.FAILED:
                logger.warning(
                    "WA send_message [%s]: deal %s exhausted after %d attempts - marking FAILED",
                    campaign, deal._id, deal.connect_attempts,
                )
            return
```

- [ ] **Step 5: Exclude exhausted deals from `plan_whatsapp_window` query**

In `openoutreach/core/scheduler.py`, find `plan_whatsapp_window` (line ~819). Update the `deals_col.count_documents` query to exclude deals that have hit the attempt cap:

```python
    from openoutreach.whatsapp.tasks.send_message import MAX_WA_MESSAGE_ATTEMPTS

    eligible = deals_col.count_documents({
        "campaign_id": campaign.pk,
        "state": "Qualified",
        "active_channel": "whatsapp",
        "$or": [
            {"connect_attempts": {"$exists": False}},
            {"connect_attempts": {"$lt": MAX_WA_MESSAGE_ATTEMPTS}},
        ],
    })
```

- [ ] **Step 6: Run tests**

```bash
.venv/bin/python -m pytest tests/whatsapp/test_send_message_attempts.py -v
```

Expected: all 3 PASS.

- [ ] **Step 7: Lint and type-check**

```bash
make lint && make pyright
```

- [ ] **Step 8: Commit**

```bash
git add openoutreach/whatsapp/tasks/send_message.py openoutreach/core/scheduler.py tests/whatsapp/test_send_message_attempts.py
git commit -m "feat: WA message attempt counter - fail deal after 3 consecutive send failures"
```

---

## Task 3: Per-channel analytics breakdown

**Problem:** Analytics router counts only LinkedIn action types (`connect`, `follow_up`). WA sends (`whatsapp_message`, `whatsapp_follow_up`) are invisible in dashboards. Multi-channel campaigns show zero messages_sent even when WA is active.

**Files:**
- Modify: `openoutreach/api_v2/routers/analytics.py` - add WA action counts to CampaignStats and OverviewStats
- Test: `tests/api_v2/test_analytics_channels.py`

**Interfaces:**
- Produces: `CampaignStats.wa_messages_sent: int`, `CampaignStats.wa_connections_sent: int`, `OverviewStats.wa_messages_sent: int`, `OverviewStats.wa_connections_sent: int`
- Existing fields (`connections_sent`, `messages_sent`) remain LinkedIn-only - no behavior change for single-channel campaigns.

- [ ] **Step 1: Write failing tests**

```python
# tests/api_v2/test_analytics_channels.py
"""Tests for per-channel analytics breakdown."""
import pytest
from openoutreach.api_v2.routers.analytics import CampaignStats, OverviewStats


def test_campaign_stats_has_wa_fields():
    stats = CampaignStats(wa_messages_sent=5, wa_connections_sent=3)
    assert stats.wa_messages_sent == 5
    assert stats.wa_connections_sent == 3


def test_overview_stats_has_wa_fields():
    stats = OverviewStats(wa_messages_sent=10, wa_connections_sent=7)
    assert stats.wa_messages_sent == 10
    assert stats.wa_connections_sent == 7


def test_campaign_stats_wa_defaults_zero():
    stats = CampaignStats()
    assert stats.wa_messages_sent == 0
    assert stats.wa_connections_sent == 0


def test_campaign_stats_serialises_wa_aliases():
    stats = CampaignStats(wa_messages_sent=2, wa_connections_sent=1)
    d = stats.model_dump(by_alias=True)
    assert d["waMessagesSent"] == 2
    assert d["waConnectionsSent"] == 1
```

- [ ] **Step 2: Run tests, verify FAIL**

```bash
.venv/bin/python -m pytest tests/api_v2/test_analytics_channels.py -v
```

Expected: `ValidationError` or `AttributeError` on unknown fields.

- [ ] **Step 3: Add WA fields to `CampaignStats` and `OverviewStats`**

In `openoutreach/api_v2/routers/analytics.py`, add to `OverviewStats`:

```python
    wa_connections_sent: int = Field(default=0, serialization_alias="waConnectionsSent")
    wa_messages_sent: int = Field(default=0, serialization_alias="waMessagesSent")
```

Add the same two fields to `CampaignStats`.

- [ ] **Step 4: Add helper for multi-type action count**

In `openoutreach/api_v2/routers/analytics.py`, add below `_get_action_logs_count`:

```python
def _get_action_logs_count_multi(
    campaign_id: str, action_types: list[str], since: datetime
) -> int:
    """Count action logs matching any of the given action_types in the time range."""
    action_logs_collection = get_mongodb_collection("action_logs")
    if action_logs_collection is None:
        return 0
    try:
        return action_logs_collection.count_documents({
            "campaign_id": campaign_id,
            "action_type": {"$in": action_types},
            "status": {"$nin": ["failed", "error"]},
            "created_at": {"$gte": since},
        })
    except Exception as e:
        logger.error("Failed to count action logs for types %s: %s", action_types, e)
        return 0
```

- [ ] **Step 5: Compute WA stats per-campaign and in totals**

In the per-campaign loop (after the existing `messages_sent` line), add:

```python
        wa_connections_sent = _get_action_logs_count(campaign._id, "whatsapp_message", since)
        wa_messages_sent = _get_action_logs_count_multi(
            campaign._id, ["whatsapp_message", "whatsapp_follow_up"], since
        )
```

Pass them to `CampaignStats(...)`:

```python
                    wa_connections_sent=wa_connections_sent,
                    wa_messages_sent=wa_messages_sent,
```

For totals (after `total_messages_sent`), add:

```python
    total_wa_connections_sent = action_logs_collection.count_documents({
        "campaign_id": {"$in": campaign_ids},
        "action_type": "whatsapp_message",
        "status": {"$nin": ["failed", "error"]},
        "created_at": {"$gte": since},
    })
    total_wa_messages_sent = action_logs_collection.count_documents({
        "campaign_id": {"$in": campaign_ids},
        "action_type": {"$in": ["whatsapp_message", "whatsapp_follow_up"]},
        "status": {"$nin": ["failed", "error"]},
        "created_at": {"$gte": since},
    })
```

Pass to `OverviewStats(...)`:

```python
    stats = OverviewStats(
        ...existing fields...,
        wa_connections_sent=total_wa_connections_sent,
        wa_messages_sent=total_wa_messages_sent,
    )
```

- [ ] **Step 6: Run tests**

```bash
.venv/bin/python -m pytest tests/api_v2/test_analytics_channels.py -v
```

Expected: all 4 PASS.

- [ ] **Step 7: Lint and type-check**

```bash
make lint && make pyright
```

- [ ] **Step 8: Commit**

```bash
git add openoutreach/api_v2/routers/analytics.py tests/api_v2/test_analytics_channels.py
git commit -m "feat: per-channel analytics - expose WA connections_sent and messages_sent in overview and campaign stats"
```

---

## Task 4: Non-one-shot Maps discovery (re-trigger when leads run low)

**Problem:** `_maybe_trigger_maps_scrape` only runs when the campaign has zero deals. Once any lead is created, scraping stops forever - even if all QUALIFIED leads are exhausted. WA campaigns run out of leads with no way to refill.

**Files:**
- Modify: `openoutreach/core/scheduler.py` - change guard from "no deals" to "fewer than threshold active WA leads"; add `MAPS_REFILL_THRESHOLD` constant
- Test: `tests/test_scheduler_maps_refill.py`

**Interfaces:**
- Produces: `MAPS_REFILL_THRESHOLD: int = 20` (module-level constant, exported)

- [ ] **Step 1: Write failing tests**

```python
# tests/test_scheduler_maps_refill.py
"""Tests for Maps discovery refill trigger."""
import pytest
from unittest.mock import MagicMock, patch


def _make_campaign(lead_source="google_maps", maps_query="plumbers NYC"):
    c = MagicMock()
    c.pk = "camp-001"
    c.lead_source = lead_source
    c.maps_query = maps_query
    c.maps_country_code = "US"
    c.maps_backends = None
    return c


def test_scrape_triggers_when_active_leads_below_threshold(monkeypatch):
    """Scrape must trigger when QUALIFIED+PENDING WA count < MAPS_REFILL_THRESHOLD."""
    from openoutreach.core import scheduler
    from openoutreach.core.scheduler import MAPS_REFILL_THRESHOLD

    campaign = _make_campaign()
    mock_col = MagicMock()
    mock_col.count_documents.return_value = 5  # below threshold

    monkeypatch.setattr(
        "openoutreach.core.scheduler.get_mongodb_collection",
        lambda name: mock_col if name == "deals" else None,
    )

    started = []

    def fake_thread_init(self, target=None, daemon=None, name=None):
        self._target = target

    def fake_thread_start(self):
        started.append(True)

    monkeypatch.setattr("threading.Thread.__init__", fake_thread_init)
    monkeypatch.setattr("threading.Thread.start", fake_thread_start)

    scheduler._maybe_trigger_maps_scrape(campaign, "user-001")
    assert len(started) == 1


def test_scrape_suppressed_when_active_leads_above_threshold(monkeypatch):
    """Scrape must NOT trigger when QUALIFIED+PENDING WA count >= MAPS_REFILL_THRESHOLD."""
    from openoutreach.core import scheduler
    from openoutreach.core.scheduler import MAPS_REFILL_THRESHOLD

    campaign = _make_campaign()
    mock_col = MagicMock()
    mock_col.count_documents.return_value = MAPS_REFILL_THRESHOLD + 5

    monkeypatch.setattr(
        "openoutreach.core.scheduler.get_mongodb_collection",
        lambda name: mock_col if name == "deals" else None,
    )

    started = []

    def fake_thread_init(self, target=None, daemon=None, name=None):
        self._target = target

    def fake_thread_start(self):
        started.append(True)

    monkeypatch.setattr("threading.Thread.__init__", fake_thread_init)
    monkeypatch.setattr("threading.Thread.start", fake_thread_start)

    scheduler._maybe_trigger_maps_scrape(campaign, "user-001")
    assert len(started) == 0


def test_scrape_suppressed_when_already_running(monkeypatch):
    """Concurrent scrape for same campaign must be blocked."""
    from openoutreach.core import scheduler

    campaign = _make_campaign()
    scheduler._maps_scraping.add(campaign.pk)
    mock_col = MagicMock()
    mock_col.count_documents.return_value = 0

    monkeypatch.setattr(
        "openoutreach.core.scheduler.get_mongodb_collection",
        lambda name: mock_col,
    )

    started = []

    def fake_thread_init(self, target=None, daemon=None, name=None):
        self._target = target

    def fake_thread_start(self):
        started.append(True)

    monkeypatch.setattr("threading.Thread.__init__", fake_thread_init)
    monkeypatch.setattr("threading.Thread.start", fake_thread_start)

    scheduler._maybe_trigger_maps_scrape(campaign, "user-001")
    assert len(started) == 0
    scheduler._maps_scraping.discard(campaign.pk)
```

- [ ] **Step 2: Run tests, verify FAIL**

```bash
.venv/bin/python -m pytest tests/test_scheduler_maps_refill.py -v
```

Expected: `test_scrape_triggers_when_active_leads_below_threshold` FAIL (old guard blocks on >0 deals).

- [ ] **Step 3: Add `MAPS_REFILL_THRESHOLD` constant and replace guard**

At the top of `openoutreach/core/scheduler.py` (near other constants), add:

```python
MAPS_REFILL_THRESHOLD = 20
```

Then in `_maybe_trigger_maps_scrape`, replace the existing "has any deals" guard block:

Old code to remove:
```python
    existing = deals_col.count_documents({"campaign_id": campaign.pk}, limit=1)
    if existing > 0:
        return
```

New code:
```python
    active_wa_count = deals_col.count_documents({
        "campaign_id": campaign.pk,
        "state": {"$in": ["Qualified", "Pending"]},
        "active_channel": "whatsapp",
    })
    if active_wa_count >= MAPS_REFILL_THRESHOLD:
        return
```

Note: Look at the exact guard code in the file - it may read slightly differently. Replace only the guard, not the thread-start code below it.

- [ ] **Step 4: Run tests**

```bash
.venv/bin/python -m pytest tests/test_scheduler_maps_refill.py -v
```

Expected: all 3 PASS.

- [ ] **Step 5: Lint and type-check**

```bash
make lint && make pyright
```

- [ ] **Step 6: Commit**

```bash
git add openoutreach/core/scheduler.py tests/test_scheduler_maps_refill.py
git commit -m "feat: re-trigger Maps scrape when active WA leads fall below MAPS_REFILL_THRESHOLD=20"
```

---

## Self-Review Checklist

- [x] Task 1 covers: Task field naming collision (channel discriminator)
- [x] Task 2 covers: WA attempt counter + deal FAIL gate + scheduler exclusion
- [x] Task 3 covers: per-channel analytics (WA sends visible in dashboard)
- [x] Task 4 covers: non-one-shot Maps discovery (refill trigger)
- [x] No placeholder steps - all code shown
- [x] No new abbreviations in prose
- [x] All type names consistent across tasks
- [x] `_handle_send_failure` defined in Task 2 before used in same task
- [x] `MAPS_REFILL_THRESHOLD` exported from scheduler so tests can import it
- [x] WA `active_channel="whatsapp"` filter in Task 4 scopes count to WA-only deals correctly

**Deferred (low priority, not in this plan):**
- Smart rate limiting with detectability for WA
- Saved `WhatsAppSearch` model / multi-query per campaign (next phase)
- Manual WA message task
- WA disqualification pipeline
