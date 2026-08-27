# Multichannel Sequence Builder — Implementation Plan

**Goal**: Visual per-campaign sequence builder that orchestrates LinkedIn, Email, and WhatsApp
across leads with varying data availability. Replaces the phantom state machine feature.

**Channels available**: LinkedIn (always), Email (requires `api_email`), WhatsApp (requires `phone`).

---

## Architecture Summary

- Sequence stored directly on `Campaign` as two arrays: `sequence_steps` + `sequence_edges`
  (React Flow graph state — no separate DB collection needed).
- Deal tracks position via `sequence_position` (step_id) + `sequence_last_step_at` (datetime).
- Daemon reconciler gains `resolve_sequence_tasks()` that walks each deal's position and creates
  existing task types (connect, email_follow_up, whatsapp_message) — no new task types.
- Canvas: reuse `frontend/src/components/state-machine/canvas.tsx`. Replace the top-level
  `/state-machine` route with a `Sequence` tab inside `/campaigns/[id]`.
- Data coverage: per-step % of leads that satisfy `requires` shown inline on each canvas node.

---

## Phase 1 — Lead Data + CSV Import

### 1.1 Phone field exposed in API (backend)

`Lead` already has `phone`, `phone_source`, `phone_on_whatsapp` in `mongodb/models.py`.
Currently not returned by the leads API.

- [ ] `openoutreach/api_v2/schemas/lead.py`: add `phone: str = ""` to `LeadResponse`.
- [ ] `openoutreach/api_v2/routers/leads.py`: populate `phone` in list/detail serialization.

### 1.2 CSV import endpoint (backend)

New endpoint: `POST /api/campaigns/{campaign_id}/leads/import`

Request: `multipart/form-data` — field `file` (CSV) + field `column_map` (JSON string):
```json
{
  "linkedin_url": "LinkedIn URL",
  "first_name": "First Name",
  "last_name": "Last Name",
  "company": "Company",
  "title": "Title",
  "email": "Work Email",
  "phone": "Phone",
  "company_domain": "Domain"
}
```
All keys optional except at least one of `linkedin_url` or `email` must be mapped.

Response:
```json
{"imported": 120, "updated": 34, "skipped": 5, "errors": ["row 42: no linkedin_url or email"]}
```

- [ ] `openoutreach/api_v2/routers/campaigns.py`: add `POST /campaigns/{id}/leads/import`.
- [ ] Parse with `csv.DictReader`. Max 5000 rows; return 400 if exceeded.
- [ ] Per row: upsert `Lead` by `linkedin_url` (primary) or `email` (fallback). Create `Deal` in
  `DISCOVERED` state linked to this campaign if it doesn't exist.
- [ ] If `email` mapped and `lead.api_email` is empty: write to `lead.api_email`,
  set `lead.phone_source = "csv_import"` (reuse pattern from phone).
- [ ] If `phone` mapped and `lead.phone` is empty: write `lead.phone`, `lead.phone_source = "csv_import"`.
- [ ] Rows with no `linkedin_url` AND no `email`: skip, append to `errors`.
- [ ] Process synchronously (5000 rows < 2s); no background queue needed.

### 1.3 CSV import UI (frontend)

- [ ] Campaign leads tab: add "Import CSV" button (secondary, next to existing "Add Lead" if present).
- [ ] `frontend/src/components/campaigns/csv-import-modal.tsx` (new): multi-step modal:
  - Step 1: file picker / drag-drop. Show first 5 rows on upload.
  - Step 2: column mapping — auto-detect common header names, allow override via dropdowns.
  - Step 3: confirm (row count, mapped fields summary).
  - Step 4: result (imported/updated/skipped counts, collapsible error list).
- [ ] `frontend/src/lib/api/campaigns.ts`: add `importLeadsCSV(campaignId: string, file: File, columnMap: Record<string, string>): Promise<ImportResult>`.

---

## Phase 2 — Data Availability Layer

### 2.1 Per-lead channel flags (backend)

- [ ] `openoutreach/api_v2/schemas/lead.py`: add `channel_availability` to `LeadResponse`:
  ```python
  class ChannelAvailability(BaseModel):
      linkedin: bool
      email: bool
      whatsapp: bool
  ```
  - `linkedin`: `True` when `linkedin_url` is non-empty
  - `email`: `True` when `api_email` or `contact_info.get("email")` is non-empty
  - `whatsapp`: `True` when `phone` is non-empty and `phone_on_whatsapp is not False`
- [ ] Compute and populate in leads list + detail serializer.

### 2.2 Campaign channel coverage stats (backend)

- [ ] `openoutreach/api_v2/routers/campaigns.py`: campaign detail/stats endpoint — add
  `channel_coverage` to response:
  ```json
  {
    "channel_coverage": {
      "linkedin": {"count": 450, "pct": 100},
      "email":    {"count": 234, "pct": 52},
      "whatsapp": {"count": 139, "pct": 31}
    }
  }
  ```
  Compute with three MongoDB count queries (or one `$facet`) against `leads` for this campaign.

### 2.3 Per-lead channel badges (frontend)

- [ ] Leads list table: compact channel badge row per lead using `channel_availability`.
  - LinkedIn `Li` — always green for linked leads
  - Email envelope — green if `email: true`, grey outline if `false`
  - WhatsApp icon — green if `whatsapp: true`, grey if `false`
- [ ] Leads list filter bar: add "Missing email" and "Missing phone" filter chips.
- [ ] Lead detail page: show availability badges prominently in header.

### 2.4 Campaign overview coverage widget (frontend)

- [ ] Campaign overview / header section: horizontal coverage bars using `channel_coverage`:
  ```
  LinkedIn  ████████████████ 100%
  Email     ████████░░░░░░░░  52%
  WhatsApp  █████░░░░░░░░░░░  31%
  ```

---

## Phase 3 — Sequence Data Model + Builder UI

### 3.1 Sequence fields on Campaign (backend)

- [ ] `openoutreach/mongodb/models.py` — add to `Campaign.__init__`, `to_dict`, `from_dict`:
  ```python
  sequence_steps: list[dict] = []   # React Flow nodes + action config
  sequence_edges: list[dict] = []   # React Flow edges
  sequence_active: bool = False     # daemon executes this sequence when True
  ```

  Step dict schema:
  ```json
  {
    "id": "s1",
    "type": "action",
    "data": {
      "channel": "linkedin",
      "action": "connect",
      "label": "LinkedIn Connect",
      "wait_days": 0,
      "condition": "always",
      "requires": []
    },
    "position": {"x": 200, "y": 100}
  }
  ```
  `type` values: `"action"` | `"wait"` | `"condition"` | `"end"`  
  `channel` values: `"linkedin"` | `"email"` | `"whatsapp"` | `null`  
  `action` values: `"connect"` | `"follow_up"` | `"send_email"` | `"send_whatsapp"`  
  `condition` values: `"always"` | `"no_reply"` | `"no_open"` | `"replied"`  
  `requires` values: subset of `["api_email", "phone"]`

  Edge dict schema (React Flow compatible):
  ```json
  {"id": "e1", "source": "s1", "target": "s2", "label": "no reply 3d", "data": {"condition": "no_reply"}}
  ```

- [ ] `openoutreach/api_v2/routers/campaigns.py`:
  - `GET /campaigns/{id}/sequence` — returns `{steps, edges, active, coverage_per_step}`
    where `coverage_per_step` is `{step_id: pct}` computed from Lead count satisfying each step's `requires`.
  - `PATCH /campaigns/{id}/sequence` — saves `steps`, `edges`, optionally `active`.

### 3.2 Remove old state machine routes (frontend)

- [ ] Delete `frontend/src/app/(dashboard)/state-machine/page.tsx`.
- [ ] Delete `frontend/src/app/(dashboard)/campaigns/[id]/state-machine/page.tsx`.
- [ ] Delete `frontend/src/app/(dashboard)/state-machine/README.md`.
- [ ] Remove `NEXT_PUBLIC_ENABLE_STATE_MACHINE` from all components, sidebar nav, env files.
- [ ] Keep `frontend/src/components/state-machine/` — canvas reused below.

### 3.3 Sequence tab in campaign page (frontend)

- [ ] `/app/(dashboard)/campaigns/[id]/page.tsx` (or tab router): add `Sequence` tab.
- [ ] Always visible — no feature flag.
- [ ] Empty state: "No sequence — campaign uses default single-channel behavior." + "Build Sequence" button.

### 3.4 Sequence canvas (frontend)

Extend existing `canvas.tsx` / `node.tsx` / `edge.tsx`:

**Node config panel** (right drawer, opens on node click):

| Node type | Config fields |
|-----------|--------------|
| LinkedIn Connect | (none) |
| LinkedIn Follow-up | — (uses campaign follow-up agent) |
| Send Email | step number (1st / 2nd / 3rd in sequence) |
| Send WhatsApp | message preview (read-only, from campaign template) |
| Wait | `wait_days` number input |
| Condition | `condition` dropdown: replied / not replied / opened / not opened |
| End | label (converted / unresponsive / etc.) |

- [ ] `node.tsx`: render channel icon + label + `requires` badge (e.g., `needs email`).
- [ ] Coverage bar below each node: `██████░░ 52%` from `coverage_per_step[step.id]`.
- [ ] `edge.tsx`: click edge label → edit modal (condition dropdown + label text field).
- [ ] Connection tool: React Flow's native `onConnect` — enable handles on nodes.
- [ ] Toolbar: "Add step" dropdown, "Save", "Activate / Deactivate" toggle with confirm guard.

### 3.5 Sequence API client (frontend)

- [ ] `frontend/src/lib/api/campaigns.ts`:
  - `getSequence(campaignId): Promise<SequenceResponse>`
  - `saveSequence(campaignId, steps, edges): Promise<void>`
  - `setSequenceActive(campaignId, active: boolean): Promise<void>`

---

## Phase 4 — Sequence Execution Engine

### 4.1 Deal position fields (backend)

- [ ] `openoutreach/mongodb/models.py` — add to `Deal.__init__`, `to_dict`, `from_dict`:
  ```python
  sequence_position: str | None = None       # step_id of current step
  sequence_last_step_at: datetime | None = None
  sequence_done: bool = False                # True on end node reached or any-channel reply
  ```

### 4.2 Sequence executor module (backend)

New: `openoutreach/core/sequence_executor.py`

```python
def resolve_sequence_tasks(campaign, user_id: str) -> int:
    """
    For every active Deal in this campaign (sequence_active=True):
    - Initialize deals with sequence_position=None (start them)
    - Check should_stop (any inbound ChatMessage) → mark sequence_done
    - Check current step conditions (wait_days elapsed, condition met, requires met)
    - If ready: create Task of appropriate type, advance sequence_position
    - If requires not met: skip step (log), advance to next
    Returns count of tasks created.
    """

def _get_next_step_id(campaign, current_step_id: str, condition_met: bool) -> str | None:
    """Follow outgoing edge matching condition; return target step_id or None."""

def _check_wait(deal, step: dict) -> bool:
    """True if wait_days elapsed since sequence_last_step_at."""

def _check_condition(deal, step: dict) -> bool:
    """True if step's condition is satisfied (e.g., no inbound messages since last_step_at)."""

def _check_requires(lead, step: dict) -> bool:
    """True if all fields in step.requires are non-empty on lead."""
```

Task creation per step type:
- `action` + `channel=linkedin` + `action=connect` → `Task(task_type="connect", ...)`
- `action` + `channel=linkedin` + `action=follow_up` → `Task(task_type="follow_up", ...)`
- `action` + `channel=email` → `Task(task_type="email_follow_up", ...)`
- `action` + `channel=whatsapp` → `Task(task_type="whatsapp_message", ...)`
- `wait` / `condition` nodes: no Task created; advance position after `wait_days` passes.

### 4.3 Cloud daemon integration (backend)

- [ ] `openoutreach/core/scheduler.py` `reconcile()`:
  - Call `resolve_sequence_tasks(campaign, user_id)` for campaigns where `sequence_active=True`.
  - In existing planners (`plan_connect_window`, `plan_follow_up_window`, etc.): **exclude** deals
    where `sequence_active=True` AND `sequence_position is not None` — sequence owns those deals.

### 4.4 Desktop daemon integration (backend)

- [ ] `openoutreach/api_v2/routers/daemon.py` `reconcile_tasks` endpoint:
  - Call `resolve_sequence_tasks(campaign, user_id)` for `sequence_active` campaigns.
  - Same pattern as the IMAP scan call added in the email channel session.

---

## Phase 5 — Cross-Channel Intelligence + Polish

### 5.1 Stop on reply (backend)

- [ ] `sequence_executor.py`: at start of each deal's resolution, check for any inbound
  `ChatMessage` with `channel` in `[linkedin, email, whatsapp]` since sequence started.
  If found → `deal.sequence_done = True`. Log which channel triggered the stop.

### 5.2 Sequence timeline on lead detail (frontend)

- [ ] Lead detail page: "Sequence" section showing each step as a timeline row:
  - ✅ Completed — timestamp
  - ⏭ Skipped — reason (e.g., "no email address")
  - ⏳ Pending — "fires in N days"
  - 🔴 Stopped — "replied via email on [date]"
- [ ] Backend: `GET /api/campaigns/{id}/leads/{lead_id}/sequence-timeline` returning step history.
  Source: `Deal.sequence_position`, `sequence_last_step_at`, ActionLog for completed steps.

### 5.3 Sequence templates (frontend)

Empty-state "Start from template" cards:

| Template | Steps |
|----------|-------|
| LinkedIn Only | Connect → wait 3d → Follow-up → wait 7d → Follow-up → End |
| LinkedIn + Email | Connect → wait 3d → [no reply] → Email → wait 5d → Follow-up → End |
| Full Multichannel | Connect → wait 3d → [no reply] → Email → wait 5d → [no reply] → WhatsApp → End |

- [ ] Hardcoded step/edge arrays per template. "Use template" populates canvas.

### 5.4 Activation safety guard (frontend + backend)

- [ ] Backend `PATCH /campaigns/{id}/sequence` with `active: true`: validate sequence has
  ≥1 action step, ≥1 end node, no disconnected nodes. Return 400 with error list if invalid.
- [ ] Frontend: confirm modal when activating — "This pauses the default automation for this campaign.
  In-progress deals will continue their current state before entering the sequence."

---

## Files Reference

### Backend

| File | Change |
|------|--------|
| `openoutreach/mongodb/models.py` | `Campaign`: `sequence_steps`, `sequence_edges`, `sequence_active`; `Deal`: `sequence_position`, `sequence_last_step_at`, `sequence_done` |
| `openoutreach/core/sequence_executor.py` | **New** — step resolution, task creation, stop-on-reply |
| `openoutreach/core/scheduler.py` | Call `resolve_sequence_tasks`; exclude sequence-owned deals from existing planners |
| `openoutreach/api_v2/routers/campaigns.py` | `POST .../leads/import`; `GET/PATCH .../sequence` |
| `openoutreach/api_v2/routers/daemon.py` | Call `resolve_sequence_tasks` in reconcile endpoint |
| `openoutreach/api_v2/schemas/lead.py` | Add `phone`, `channel_availability` |
| `openoutreach/api_v2/schemas/campaigns.py` | Add `channel_coverage`, sequence fields |

### Frontend

| File | Change |
|------|--------|
| `frontend/src/app/(dashboard)/state-machine/page.tsx` | **Delete** |
| `frontend/src/app/(dashboard)/campaigns/[id]/state-machine/page.tsx` | **Delete** |
| `frontend/src/app/(dashboard)/state-machine/README.md` | **Delete** |
| `frontend/src/app/(dashboard)/campaigns/[id]/page.tsx` | Add Sequence tab |
| `frontend/src/components/campaigns/sequence-tab.tsx` | **New** — tab wrapper + empty state |
| `frontend/src/components/campaigns/csv-import-modal.tsx` | **New** — CSV import flow |
| `frontend/src/components/state-machine/canvas.tsx` | Extend — coverage bars, connection handles |
| `frontend/src/components/state-machine/node.tsx` | Extend — channel icons, requires badge, config panel |
| `frontend/src/components/state-machine/edge.tsx` | Extend — click-to-edit modal |
| `frontend/src/lib/api/campaigns.ts` | Add sequence endpoints + CSV import |

---

## Build Order

1. **Phase 1** — CSV import + phone in API (unblocks WhatsApp leads immediately)
2. **Phase 2** — Coverage stats + per-lead badges (users understand data gaps before building)
3. **Phase 3.1** Campaign model → **3.2** delete old routes → **3.3–3.5** UI
4. **Phase 4** Execution engine (cloud + desktop daemon)
5. **Phase 5** Templates, timeline, activation guard

Do not enable `sequence_active` in production until Phase 4 is complete and tested end-to-end
on a real campaign with all three channels.
