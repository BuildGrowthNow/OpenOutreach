# Daemon & Pipeline Architecture

End-to-end walkthrough of how the daemon runs, discovers leads, qualifies them, connects, and manages conversations — with file references for every step.

---

## 1. Daemon Startup

**Entry:** `openoutreach/core/daemon.py:run_daemon` (line 380)

On start, the daemon:
1. Initializes the MongoDB connection and ensures indexes.
2. Registers task handlers for `connect`, `check_pending`, `follow_up`, `send_manual_message` (lines 28–42).
3. Scans all active `LinkedInProfile` records via `_get_all_active_profiles` (line 352). A profile is included only if it has:
   - `active=True`
   - `cookie_data_encrypted` set (login cookies exist)
   - A linked user whose billing plan allows running tasks (`PlanEnforcer.can_run_tasks`)
4. Builds a **session pool**: one `ProfileSession` per profile (line 395). The pool is re-scanned every 5 minutes (`PROFILE_REFRESH_INTERVAL = 300`, line 349) so new users start automatically and removed profiles are cleaned up.

---

## 2. Main Loop: Round-Robin Task Execution

**File:** `openoutreach/core/daemon.py:run_daemon` (line 434)

```
while True:
    refresh_pool()                      # re-scan for new/removed profiles every 5 min
    for each ProfileSession in pool:
        skip if paused (auth error, challenge, etc.)
        skip if outside user's active hours window
        task = Task.objects.claim_next(linkedin_profile_id=...)   # atomic MongoDB claim
        if no task: skip to next profile
        authenticate lazily             # launch browser + LinkedIn login on first task
        build_qualifiers lazily         # warm-start Bayesian GP model from labeled history
        handler(task, session, qualifiers)
        task.mark_completed()
        _save_cookies(session)          # persist updated session cookies
        periodic health check (every hour)
    if no task was executed across all profiles:
        _reconcile_all(pool)            # plan fresh task slots for next 24h
        sleep up to 60s
```

**Key behaviors:**
- **Active hours guard** (`seconds_until_active`, line 142): reads `SiteConfig.enable_active_hours`, `active_start_hour`, `active_end_hour`, `active_timezone`, `active_days` per user. If outside the window, the profile is paused until it opens. `active_days` is stored as `List[int]` with 1=Monday, 7=Sunday (1-indexed) — both `seconds_until_active` and `_working_intervals` in the scheduler parse this identically.
- **Human rhythm breaks** (`_HumanRhythmBreak`, line 108): after a random burst duration, the daemon takes a multi-minute break, then resets. This mimics a human work session.
- **Qualifier refresh:** `build_qualifiers_for` runs on every task iteration and adds qualifiers for any campaigns added since the daemon started — new campaigns are never silently missing from `ps.qualifiers`.
- **Auth failure handling**: a `CheckpointChallengeError` (LinkedIn CAPTCHA/verification) pauses the profile for 5 minutes and creates a UI notification. An `AuthenticationError` triggers re-authentication; if that also fails, the profile is paused 5 minutes.
- **LLM errors** (`ModelHTTPError`): the task is failed and the profile is paused 10 minutes.

---

## 3. Lazy Authentication: Browser Launch + LinkedIn Login

**File:** `openoutreach/core/daemon.py:ProfileSession.authenticate` (line 289)

Authentication is deferred until the first task executes for a profile. On the first call:
1. `ensure_session()` creates or retrieves the browser session via `get_or_create_session(profile)` in `openoutreach/linkedin/browser/registry.py`.
2. `session.ensure_browser()` launches Playwright + loads the saved cookies from `profile.cookie_data_encrypted`.
3. If login is needed (cookies expired), runs the `authenticate()` flow from `linkedin_cli/auth.py` — the page-state machine navigates the login form.
4. On success, `_sync_credential_username` discovers and saves the LinkedIn username back to the credential record.

After every completed task, cookies are re-saved to MongoDB (`_save_cookies` in `openoutreach/linkedin/browser/launch.py`) to keep the session alive.

---

## 4. Reconciliation: Planning Task Slots

When no tasks are ready to execute, `_reconcile_all` calls `reconcile(session)` in `openoutreach/core/scheduler.py:reconcile` (line 696) for every active profile.

Reconcile does four things per campaign:

| Step | Function | Effect |
|---|---|---|
| Recover stale tasks | `_recover_stale_running_tasks` (line 648) | Tasks stuck in RUNNING > 30 min are reset to PENDING (handles daemon crashes / laptop lid closes) |
| Plan connect slots | `plan_connect_window` (line 401) | Creates N lazy `connect` Task rows for the next 24h |
| Plan follow-up slots | `plan_follow_up_window` (line 465) | Creates N lazy `follow_up` Task rows for the next 24h |
| Plan check-pending slots | `plan_check_pending_window` (line 543) | Creates slots for PENDING deals whose `next_check_pending_at` has arrived |
| Retry NO_EMAIL deals | `_retry_no_email_deals` | Re-runs the email finder on all NO_EMAIL deals; promotes to QUALIFIED on a hit (see §6.4) |

**Slot creation is the ONLY place Task rows are inserted.** Handlers never reschedule themselves.

**Bootstrap note:** `_reconcile_all` calls `ps.ensure_session()` before reconciling, so profiles that have never executed a task (no prior browser session) still get their first task slots planned on startup.

### Pacing Modes

**File:** `openoutreach/core/scheduler.py:velocity_slot_times` (line 232)

- **Manual mode** (default): reads `SiteConfig.velocity` (actions/hr). Velocity ≥ 30/hr → burst immediately with 5–10s spacing. Velocity < 30/hr → Poisson-distributed across the active hours window.
- **Smart mode** (opt-in via `SiteConfig.enable_smart_rate_limiting`): uses `SmartRateLimiter` + `aggressiveness_preset` to cluster tasks during business hours (9–17h), reduce during off-hours, and add jitter when the detectability score is high.

When multiple campaigns are active, the daily budget is split evenly (`connect_cap = remaining_budget // n_campaigns`) so no single campaign starves the others (line 715).

---

## 5. Lead Discovery: Search → Enrich

Discovery is **triggered on-demand** inside the `connect` task handler's candidate-finding chain. It is not a separate task type.

### 5.1 Keyword Generation and People Search

**File:** `openoutreach/linkedin/pipeline/search.py:run_search` (line 14)

1. Checks if any unused `SearchKeyword` rows exist for this campaign.
2. If none: calls `generate_search_keywords` (LLM) using the campaign's `product_pitch`, `campaign_objective`, `icp_titles`. Saves fresh keywords as `SearchKeyword` rows.
3. Takes the next unused keyword, marks it used, and calls `search_people(session, keyword)` from `linkedin_cli`.
4. Passes the resulting profile URLs to `discover_and_enrich`.

### 5.2 Profile Enrichment: URL → Lead + Deal

**File:** `openoutreach/linkedin/db/leads.py:discover_and_enrich` (line 195)

For each new URL (skipping URLs that already have a Lead):
1. Calls `PlaywrightLinkedinAPI.get_profile(url)` to fetch full Voyager profile data.
2. Calls `create_enriched_lead(session, url, profile)` (line 22):
   - Creates a `Lead` row with `cached_profile`, `connection_degree`, `urn`, `linkedin_url`.
   - **Immediately creates a `Deal` row** linking the lead to the campaign at `state=DISCOVERED`.
   - Calls `lead.embed_from_profile(profile)` to generate the 384-dim FastEmbed embedding.
   - Logs a `lead_discovered` action to the activity feed.
3. Sleeps a human-ish random delay between each profile scrape.

**Result:** every discovered lead is immediately visible in the campaign leads list in DISCOVERED state, before AI qualification runs.

---

## 6. AI Qualification: DISCOVERED → QUALIFIED or FAILED

Qualification runs as part of the `connect` task's candidate-finding chain, not as a separate task type.

### 6.1 The Pipeline Chain

**File:** `openoutreach/linkedin/pipeline/pools.py` (lines 100–178)

```
find_candidate(session, qualifier)
    └── ready_source()        # yields READY_TO_CONNECT candidates
            └── qualify_source()   # runs LLM qualification on DISCOVERED leads
                    └── search_source()     # searches LinkedIn for new profiles
```

Each layer pulls from the one below only when empty. Each `qualify_source` iteration qualifies exactly one lead and shifts the GP model — preventing the "search forever without qualifying" bug.

### 6.2 Selecting Who to Qualify

**File:** `openoutreach/linkedin/pipeline/qualify.py:run_qualification` (line 44)

1. **Backlog cap check**: if the QUALIFIED+READY_TO_CONNECT backlog is already ≥ `daily_connect_limit × 3`, pauses qualification until the connect queue drains. Prevents accumulating thousands of qualified leads that can't be reached in time.
2. **Candidate selection via BALD**: calls `qualifier.acquisition_scores` to pick the most informative candidate to label next:
   - **Explore mode** (n_negatives ≤ n_positives): picks the lead with highest GP uncertainty — builds a balanced dataset.
   - **Exploit mode**: picks the lead most likely to be a good fit (highest predicted positive probability).

### 6.3 LLM Qualification Decision

**File:** `openoutreach/linkedin/pipeline/qualify.py:run_qualification` (line 138)

1. Fetches full profile text via Voyager (cached in `Lead.cached_profile`).
2. Calls `qualify_with_llm` in `openoutreach/linkedin/ml/qualifier.py` with:
   - Campaign's `product_pitch`, `campaign_objective`, `icp_titles`, `target_company_size`
   - Full profile text (headline, experience, education, etc.)
3. LLM returns `(label, reason)` — label is 1 (qualified) or 0 (rejected).

### 6.4 Saving the Qualification Result

**File:** `openoutreach/linkedin/pipeline/qualify.py:_save_qualification_result` (line 152)

- **Qualified (label=1):**
  - Calls `promote_lead_to_deal`: updates the existing DISCOVERED Deal to `state=QUALIFIED` with the LLM's reason.
  - Runs `lead.resolve_api_email()` — if the BetterContact email finder returns `False` (no email found), calls `set_profile_state(NO_EMAIL)` to park the deal out of the connect pool.
  - Updates the GP model with the positive label.
- **Rejected (label=0):**
  - Calls `create_disqualified_deal`: sets `Deal.state=FAILED`, `outcome=wrong_fit`, records the LLM reason.
  - This is **campaign-scoped** — the same lead can be FAILED in campaign A and QUALIFIED in campaign B.
  - Updates the GP model with the negative label.

**NO_EMAIL retry:** `_retry_no_email_deals` (called from `reconcile`) re-runs `lead.resolve_api_email()` on every NO_EMAIL deal each reconcile cycle. On a hit (`True`), the deal is promoted back to QUALIFIED and re-enters the connect pool. BetterContact bills only on usable hits, so retrying misses is free. Deals stay in NO_EMAIL until a hit lands or are manually overridden via the UI.

---

## 7. QUALIFIED → READY_TO_CONNECT

**File:** `openoutreach/linkedin/pipeline/ready_pool.py:promote_to_ready` (line 21)

After LLM qualification, leads sit at QUALIFIED. Before they can be connected, the GP confidence gate runs:

- **1st-degree leads**: skip READY_TO_CONNECT entirely → go straight to CONNECTED (line 38–43). No connection request needed.
- **Cold start** (GP model has no labels yet): promotes all QUALIFIED leads immediately so the campaign starts without waiting (line 48–58).
- **Normal mode**: scores each QUALIFIED lead's embedding with `qualifier.predict_probs`. Leads above `min_ready_to_connect_prob` threshold → promoted to READY_TO_CONNECT.
- **Pool-drained bypass**: if the READY_TO_CONNECT pool is empty, promotes the single best candidate even if it's below threshold (prevents the connect queue from stalling).

---

## 8. Connect Task: Sending the Connection Request

**File:** `openoutreach/linkedin/tasks/connect.py:handle_connect` (line 70)

1. Calls `strategy.find_candidate(session)` → runs the full pool chain (search → qualify → ready) to get the top-ranked candidate.
2. Checks `campaign.target_degrees` — skips leads whose `connection_degree` doesn't match.
3. Calls `get_connection_status(session, profile)` via `linkedin_cli` to observe the actual LinkedIn UI:
   - **Already CONNECTED** → `set_profile_state(CONNECTED)` immediately.
   - **Already PENDING** → `set_profile_state(PENDING)` (stamps `next_check_pending_at`).
   - **1st-degree** → `set_profile_state(CONNECTED)` (no request sent, goes straight to messaging).
4. For all other cases: calls `send_connection_request(session, profile)` via `linkedin_cli`.
5. Records in `ActionLog` and the smart rate limiter.

**Error cases:**
- `ReachedConnectionLimit` → marks this profile's connect quota as exhausted for today.
- `ProfileInaccessibleError` → marks the deal FAILED.
- No Connect button found `MAX_CONNECT_ATTEMPTS = 3` times → permanently disqualifies the lead (`Lead.disqualified = True`) and marks the deal FAILED.

**State after connect:** deal moves to PENDING. The scheduler hook `on_deal_state_entered` stamps `deal.next_check_pending_at = now + backoff_hours` (`openoutreach/core/scheduler.py`, line 628).

---

## 9. Check-Pending Task: Did They Accept?

**File:** `openoutreach/linkedin/tasks/check_pending.py:handle_check_pending` (line 62)

This task fires when `deal.next_check_pending_at` arrives (scheduled by the planner).

1. Finds the oldest-due PENDING deal for this campaign (`_next_due_pending_deal`, line 27).
2. Calls `get_connection_status(session, profile)` to observe the current state on LinkedIn.
3. **If CONNECTED:** calls `set_profile_state(CONNECTED)` → see Section 10.
4. **If still PENDING:** calls `_double_backoff(deal)` (line 49) — doubles the wait, capped at `MAX_BACKOFF_HOURS = 48`. Then re-stamps `next_check_pending_at` by calling `set_profile_state(PENDING)` again.

The planner re-creates `check_pending` slots on the next reconcile cycle for any PENDING deals with `next_check_pending_at ≤ now`.

---

## 10. Connection Accepted: PENDING → CONNECTED

**File:** `openoutreach/core/db/deals.py:set_profile_state` (line 141)

When a deal transitions to CONNECTED (from either `handle_check_pending` or directly from `handle_connect` for 1st-degree leads), two side effects fire automatically (lines 194–197):

1. **Contact info capture** (`_capture_contact_info`, line 89): best-effort scrape of the LinkedIn contact-info overlay (email/phone). LinkedIn only exposes this for 1st-degree connections, so this is the first opportunity to capture it. Failures are swallowed — the transition never rolls back.

2. **Immediate follow-up task enqueue** (`_enqueue_immediate_follow_up`, line 108): schedules a `follow_up` task for `scheduled_at = now`. This ensures the first outreach message fires on the very next task loop iteration, not hours later when the planner next runs.

---

## 11. Follow-Up: AI-Driven Conversation Management

**File:** `openoutreach/linkedin/tasks/follow_up.py:handle_follow_up` (line 283)

### 11.1 Choosing Which Lead to Message

`_close_stale_deals` auto-fails CONNECTED deals that were never messaged and whose last conversation is older than `STALE_CONVERSATION_DAYS = 30` days.

`_next_followup_deal` (line 275) returns the oldest CONNECTED deal that passes the nudge cooldown check.

**Nudge cooldown logic** (`_too_soon_to_nudge`, line 107):

| Guard | Condition | Effect |
|---|---|---|
| Persistent post-send lock | `deal.last_outgoing_at` < 5 min ago | Skip — survives restarts |
| In-memory lock | `_last_send_times[deal_id]` < 5 min ago | Skip — belt-and-suspenders |
| Stale conversation | Last message (either direction) > 30 days old | Skip |
| Lead replied | Last message is incoming | **No cooldown — follow up immediately** |
| Unanswered nudges | N outgoing messages since last reply | Wait `N × 3 days` before next nudge |

So: 1 unanswered message = wait 3 days. 2 = wait 6 days. 3 = wait 9 days.

### 11.2 Profile Summary (First Touch Only)

**File:** `openoutreach/core/db/summaries.py:materialize_profile_summary_if_missing`

On the first ever follow-up for a deal, the system does a fresh Voyager scrape and builds `deal.profile_summary` — a JSON fact list about the lead (title, company, experience, education). This is a one-time operation per `(lead, campaign)` pair.

### 11.3 The Follow-Up Agent

**File:** `openoutreach/core/agents/follow_up.py:run_follow_up_agent` (line 239)

1. Calls `sync_conversation(session, public_id)` to pull the latest LinkedIn messages into `ChatMessage` rows. This also folds any new **incoming** messages into `deal.chat_summary` via mem0-style incremental fact reconciliation — facts about the lead accumulate over time, old facts get updated or deleted.

2. Loads the last 6 `ChatMessage` rows as a verbatim recency window.

3. Renders the `follow_up_agent.j2` Jinja2 prompt with full context:
   - `profile_summary` + `chat_summary` (fact bullet lists)
   - Lead persona (pain points, goals, messaging preferences, buy signals)
   - Last 6 messages verbatim with timestamps
   - Campaign's `product_pitch`, `campaign_objective`, `booking_link`, `follow_up_strategy`
   - Account-level guardrails from `SiteConfig`: `ai_writing_style`, `ai_say_rules`, `ai_avoid_rules`
   - Days since last outgoing message + count of unanswered outgoing messages

4. Makes a **single LLM call** via `pydantic_ai` with structured output:

```python
class FollowUpDecision:
    action: Literal["send_message", "mark_completed", "wait"]
    message: str | None        # required when action=send_message
    outcome: str | None        # required when action=mark_completed
                               # options: converted, not_interested, wrong_fit,
                               #          no_budget, has_solution, bad_timing, unresponsive
    follow_up_hours: float     # agent decides when to follow up next
```

### 11.4 Executing the Decision

Back in `handle_follow_up` (line 283):

**`action = "send_message"`:**
- Calls `_replace_placeholders` to substitute any `[First Name]` / `[Company Name]` patterns the LLM generated despite instructions.
- Strips em-dashes (replace with hyphens).
- Calls `send_raw_message(session, profile, message)` via `linkedin_cli`.
- On success:
  - Stamps `deal.last_outgoing_at = now` and `deal.follow_up_cycled_at = now` **immediately** (before sync, before any code that could throw — so the guard survives exceptions and daemon restarts).
  - Sets `_last_send_times[deal_id] = now` in-memory.
  - Records in `ActionLog` and smart rate limiter.
  - Calls `sync_conversation` post-send (best-effort — failure is logged, not raised).

**`action = "mark_completed"`:**
- **Safety guard**: if the agent tries to close a deal before any message was ever sent (`never_messaged = not deal.last_outgoing_at`), the decision is rejected — the deal stays CONNECTED and a `campaign_warning` Notification is created so the operator sees it in the UI without needing to tail logs (line 345–350).
- Otherwise: `set_profile_state(CONNECTED → COMPLETED, outcome=...)`.

**`action = "wait"`:**
- Bumps `deal.follow_up_cycled_at = now` so the follow-up queue cycles to a different deal next time (this deal moves to the back of the sorted queue).

---

## 12. Reply Handling: When a Lead Responds

There is **no dedicated "reply received" task or webhook.** Replies are detected passively at the start of every follow-up run:

1. `sync_conversation` (called at the top of every `follow_up` run) pulls all new LinkedIn messages for this conversation into `ChatMessage` rows.
2. `update_chat_summary` folds new **incoming** messages (only) into `deal.chat_summary` via the mem0 UPDATE prompt. Outgoing seller messages are filtered out — the chat summary contains facts about the lead, not the seller's pitch.
3. The follow-up agent sees the reply in both the verbatim recency window and the updated fact list.
4. `_too_soon_to_nudge` returns `False` when the last message is incoming → the deal is eligible immediately.

**Timing of reply response:**
- A reply is processed whenever the next scheduled `follow_up` task fires for that campaign.
- The `follow_up_cycled_at` sort ensures the deal that received a reply is the oldest in the queue (most overdue for attention).
- In practice: the next follow-up slot (which may be scheduled within minutes at aggressive velocity, or within hours at conservative velocity) picks this deal, syncs the conversation, and the agent composes a reply.

---

## 13. Complete Deal State Machine

All state transitions go through `set_profile_state` in `openoutreach/core/db/deals.py` (line 141), which fires the scheduler hook `on_deal_state_entered` on every call.

```
DISCOVERED (visible in UI immediately on discovery)
    │
    ├── LLM label=1 (qualified) ─────────────────────────► QUALIFIED
    │                                                           │
    │                                              email finder miss ──► NO_EMAIL
    │                                              (held out of connect pool; remains visible)
    │                                                           │
    │                                              GP confidence ≥ threshold ──► READY_TO_CONNECT
    │                                              (or cold-start bypass)           │
    │                                                                         connect task fires
    ├── LLM label=0 (rejected) ────────────────────────────► FAILED          │
    │   (outcome=wrong_fit, campaign-scoped only)                             │
    │                                                              ┌─────────┴─────────────────┐
    │                                                              │                           │
    │                                                              │ 2nd/3rd degree:            │ 1st degree:
    │                                                              │ send connect request       │ already connected
    │                                                              │         │                  │
    │                                                              │       PENDING ◄────────────┘
    │                                                              │         │
    │                                                              │   check_pending task fires when
    │                                                              │   next_check_pending_at arrives
    │                                                              │         │
    │                                                              │   still pending? → double backoff (max 48h)
    │                                                              │         │
    │                                                              │   accepted? ──────────────────► CONNECTED
    │                                                              │                                     │
    │                                                              │         ◄── 1st-degree fast-path ───┘
    │                                                              │
    │                                                              │ On CONNECTED: capture email/phone (best-effort)
    │                                                              │             + enqueue immediate follow_up task
    │                                                              │
    │                                                        follow_up task fires
    │                                                              │
    │                                                    ┌─────────┴──────────────────────────┐
    │                                                    │                                    │
    │                                              send_message                         mark_completed
    │                                               (AI-written)                         (AI decision)
    │                                                    │                                    │
    │                                             lead replies?                          COMPLETED
    │                                          → no cooldown, agent                  (outcome: converted /
    │                                            replies on next slot                  not_interested / etc.)
    │                                                    │
    │                                             no reply?
    │                                          → wait N × 3 days,
    │                                            then nudge again
    │
    └── unreachable after 3 connect attempts ──────────────────► FAILED
        Lead.disqualified = True (account-level, all campaigns)
```

**State scoping:**
- `Lead.disqualified = True` → account-level permanent exclusion. Lead never appears in any campaign.
- `Deal.state = FAILED` → campaign-scoped only. Same lead can be FAILED in campaign A and QUALIFIED in campaign B.
- `NO_EMAIL` → hold state. Lead is qualified but email finder found nothing. Connect pool skips these; they remain visible in the UI for manual override.

---

## 14. Key Files Quick Reference

| Concern | File |
|---|---|
| Daemon main loop, session pool | `openoutreach/core/daemon.py` |
| Task slot planning, reconcile, pacing | `openoutreach/core/scheduler.py` |
| Connect task handler | `openoutreach/linkedin/tasks/connect.py` |
| Check-pending handler | `openoutreach/linkedin/tasks/check_pending.py` |
| Follow-up handler | `openoutreach/linkedin/tasks/follow_up.py` |
| Follow-up AI agent (LLM call) | `openoutreach/core/agents/follow_up.py` |
| Deal state transitions + side effects | `openoutreach/core/db/deals.py` |
| Lead discovery + enrichment | `openoutreach/linkedin/db/leads.py` |
| LinkedIn People search | `openoutreach/linkedin/pipeline/search.py` |
| LLM qualification + GP update | `openoutreach/linkedin/pipeline/qualify.py` |
| Pipeline candidate chain | `openoutreach/linkedin/pipeline/pools.py` |
| READY_TO_CONNECT GP gate | `openoutreach/linkedin/pipeline/ready_pool.py` |
| Conversation sync + chat summary | `openoutreach/linkedin/db/chat.py` |
| Profile/chat fact summaries (mem0) | `openoutreach/core/db/summaries.py` |
| Deal state enum | `openoutreach/crm/models/__init__.py` |
| Rate limit presets (smart mode) | `openoutreach/core/rate_limit_presets.py` |
| Browser launch + cookie persistence | `openoutreach/linkedin/browser/launch.py` |
