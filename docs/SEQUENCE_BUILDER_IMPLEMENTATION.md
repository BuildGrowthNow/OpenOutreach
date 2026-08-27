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

- [x] `openoutreach/api_v2/schemas/lead.py`: add `phone: str = ""` to `LeadResponse`.
- [x] `openoutreach/api_v2/routers/leads.py`: populate `phone` in list/detail serialization.

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

- [x] `openoutreach/api_v2/routers/campaigns.py`: add `POST /campaigns/{id}/leads/import`.
- [x] Parse with `csv.DictReader`. Max 5000 rows; return 400 if exceeded.
- [x] Per row: upsert `Lead` by `linkedin_url` (primary) or `email` (fallback). Create `Deal` in
  `DISCOVERED` state linked to this campaign if it doesn't exist.
- [x] If `email` mapped and `lead.api_email` is empty: write to `lead.api_email`,
  set `lead.phone_source = "csv_import"` (reuse pattern from phone).
- [x] If `phone` mapped and `lead.phone` is empty: write `lead.phone`, `lead.phone_source = "csv_import"`.
- [x] Rows with no `linkedin_url` AND no `email`: skip, append to `errors`.
- [x] Process synchronously (5000 rows < 2s); no background queue needed.

### 1.3 CSV import UI (frontend)

- [x] Campaign leads tab: add "Import CSV" button (secondary, next to existing "Add Lead" if present).
- [x] `frontend/src/components/campaigns/csv-import-modal.tsx` (new): multi-step modal:
  - Step 1: file picker / drag-drop. Show first 5 rows on upload.
  - Step 2: column mapping — auto-detect common header names, allow override via dropdowns.
  - Step 3: confirm (row count, mapped fields summary).
  - Step 4: result (imported/updated/skipped counts, collapsible error list).
- [x] `frontend/src/lib/api/campaigns.ts`: add `importLeadsCSV(campaignId: string, file: File, columnMap: Record<string, string>): Promise<ImportResult>`.

---

## Phase 2 — Data Availability Layer

### 2.1 Per-lead channel flags (backend)

- [x] `openoutreach/api_v2/schemas/lead.py`: add `channel_availability` to `LeadResponse`:
  ```python
  class ChannelAvailability(BaseModel):
      linkedin: bool
      email: bool
      whatsapp: bool
  ```
  - `linkedin`: `True` when `linkedin_url` is non-empty
  - `email`: `True` when `api_email` or `contact_info.get("email")` is non-empty
  - `whatsapp`: `True` when `phone` is non-empty and `phone_on_whatsapp is not False`
- [x] Compute and populate in leads list + detail serializer.

### 2.2 Campaign channel coverage stats (backend)

- [x] `openoutreach/api_v2/routers/campaigns.py`: campaign detail/stats endpoint — add
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

- [x] Leads list table: compact channel badge row per lead using `channel_availability`.
  - LinkedIn `Li` — always green for linked leads
  - Email envelope — green if `email: true`, grey outline if `false`
  - WhatsApp icon — green if `whatsapp: true`, grey if `false`
- [x] Leads list filter bar: add "Missing email" and "Missing phone" filter chips.
- [ ] Lead detail page: show availability badges prominently in header.

### 2.4 Campaign overview coverage widget (frontend)

- [x] Campaign overview / header section: horizontal coverage bars using `channel_coverage`:
  ```
  LinkedIn  ████████████████ 100%
  Email     ████████░░░░░░░░  52%
  WhatsApp  █████░░░░░░░░░░░  31%
  ```

---

## Phase 3 — Sequence Data Model + Builder UI

### 3.1 Sequence fields on Campaign (backend)

- [x] `openoutreach/mongodb/models.py` — add to `Campaign.__init__`, `to_dict`, `from_dict`:
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

- [x] `openoutreach/api_v2/routers/campaigns.py`:
  - `GET /campaigns/{id}/sequence` — returns `{steps, edges, active, coverage_per_step}`
    where `coverage_per_step` is `{step_id: pct}` computed from Lead count satisfying each step's `requires`.
  - `PATCH /campaigns/{id}/sequence` — saves `steps`, `edges`, optionally `active`.

### 3.2 Remove old state machine routes (frontend)

- [x] Delete `frontend/src/app/(dashboard)/state-machine/page.tsx`.
- [x] Delete `frontend/src/app/(dashboard)/campaigns/[id]/state-machine/page.tsx`.
- [x] Delete `frontend/src/app/(dashboard)/state-machine/README.md`.
- [x] Remove `NEXT_PUBLIC_ENABLE_STATE_MACHINE` from all components, sidebar nav, env files.
- [x] Keep `frontend/src/components/state-machine/` — canvas reused below.

### 3.3 Sequence tab in campaign page (frontend)

- [x] `/app/(dashboard)/campaigns/[id]/page.tsx` (or tab router): add `Sequence` tab.
- [x] Always visible — no feature flag.
- [x] Empty state: "No sequence — campaign uses default single-channel behavior." + "Build Sequence" button.

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

- [x] `node.tsx`: render channel icon + label + `requires` badge (e.g., `needs email`).
- [x] Coverage bar below each node: `██████░░ 52%` from `coverage_per_step[step.id]`.
- [x] `edge.tsx`: click edge label → edit modal (condition dropdown + label text field).
- [x] Connection tool: React Flow's native `onConnect` — enable handles on nodes.
- [x] Toolbar: "Add step" dropdown, "Save", "Activate / Deactivate" toggle with confirm guard.

### 3.5 Sequence API client (frontend)

- [x] `frontend/src/lib/api/campaigns.ts`:
  - `getSequence(campaignId): Promise<SequenceResponse>`
  - `saveSequence(campaignId, steps, edges): Promise<void>`
  - `setSequenceActive(campaignId, active: boolean): Promise<void>`

---

## Phase 4 — Sequence Execution Engine

### 4.1 Deal position fields (backend)

- [x] `openoutreach/mongodb/models.py` — add to `Deal.__init__`, `to_dict`, `from_dict`:
  ```python
  sequence_position: str | None = None       # step_id of current step
  sequence_last_step_at: datetime | None = None
  sequence_done: bool = False                # True on end node reached or any-channel reply
  ```

### 4.2 Sequence executor module (backend)

- [x] New: `openoutreach/core/sequence_executor.py` — step resolution, task creation, stop-on-reply.

### 4.3 Cloud daemon integration (backend)

- [x] `openoutreach/core/scheduler.py` `reconcile()`:
  - Call `resolve_sequence_tasks(campaign, user_id)` for campaigns where `sequence_active=True`.
  - In existing planners: skip when `sequence_active=True`.

### 4.4 Desktop daemon integration (backend)

- [x] `openoutreach/api_v2/routers/daemon.py` `reconcile_tasks` endpoint:
  - Call `resolve_sequence_tasks(campaign, user_id)` for `sequence_active` campaigns.

---

## Phase 5 — Cross-Channel Intelligence + Polish

### 5.1 Stop on reply (backend)

- [x] `sequence_executor.py`: at start of each deal's resolution, check for any inbound
  `ChatMessage`. If found → `deal.sequence_done = True`.

### 5.2 Sequence timeline on lead detail (frontend)

- [x] Backend: `GET /api/campaigns/{id}/leads/{lead_id}/sequence-timeline` returning step history.
- [x] Lead detail page Campaigns tab: per-deal `LeadSequenceTimeline` component showing step progress
  as a horizontal stepper (completed / active / pending states).

### 5.3 Sequence templates (frontend)

- [x] Hardcoded step/edge arrays per template. "Use template" populates canvas.
  - LinkedIn Only, LinkedIn + Email, Full Multichannel templates implemented.

### 5.4 Activation safety guard (frontend + backend)

- [x] Backend `PATCH /campaigns/{id}/sequence` with `active: true`: validate sequence has
  ≥1 action step, ≥1 end node, no disconnected nodes. Return 400 with error list if invalid.
- [x] Frontend: confirm modal when activating — handled via `window.confirm` in sequence builder.

---

## Files Reference

### Backend

| File | Change |
|------|--------|
| `openoutreach/mongodb/models.py` | `Campaign`: `sequence_steps`, `sequence_edges`, `sequence_active`; `Deal`: `sequence_position`, `sequence_last_step_at`, `sequence_done` |
| `openoutreach/core/sequence_executor.py` | **New** — step resolution, task creation, stop-on-reply |
| `openoutreach/core/scheduler.py` | Call `resolve_sequence_tasks`; exclude sequence-owned deals from existing planners |
| `openoutreach/api_v2/routers/campaigns.py` | `POST .../leads/import`; `GET/PATCH .../sequence`; `GET .../leads/{lead_id}/sequence-timeline` |
| `openoutreach/api_v2/routers/daemon.py` | Call `resolve_sequence_tasks` in reconcile endpoint |
| `openoutreach/api_v2/schemas/lead.py` | Add `phone`, `channel_availability` |

### Frontend

| File | Change |
|------|--------|
| `frontend/src/app/(dashboard)/state-machine/page.tsx` | **Deleted** |
| `frontend/src/app/(dashboard)/campaigns/[id]/state-machine/page.tsx` | **Deleted** |
| `frontend/src/app/(dashboard)/state-machine/README.md` | **Deleted** |
| `frontend/src/app/(dashboard)/campaigns/[id]/page.tsx` | Add Sequence tab, CoverageBars, CsvImportModal |
| `frontend/src/components/campaigns/sequence-builder.tsx` | **New** — full sequence builder with templates |
| `frontend/src/components/campaigns/csv-import-modal.tsx` | **New** — CSV import flow |
| `frontend/src/components/campaigns/coverage-bars.tsx` | **New** — channel coverage progress bars |
| `frontend/src/components/campaigns/lead-sequence-timeline.tsx` | **New** — per-deal timeline in lead detail |
| `frontend/src/lib/api/campaigns.ts` | Add sequence endpoints, CSV import, coverage, timeline |

---

## Build Order

1. **Phase 1** — CSV import + phone in API (unblocks WhatsApp leads immediately)
2. **Phase 2** — Coverage stats + per-lead badges (users understand data gaps before building)
3. **Phase 3.1** Campaign model → **3.2** delete old routes → **3.3–3.5** UI
4. **Phase 4** Execution engine (cloud + desktop daemon)
5. **Phase 5** Templates, timeline, activation guard

Do not enable `sequence_active` in production until Phase 4 is complete and tested end-to-end
on a real campaign with all three channels.
