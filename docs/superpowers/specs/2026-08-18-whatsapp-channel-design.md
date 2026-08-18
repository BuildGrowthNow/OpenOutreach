# WhatsApp Channel Design

**Date:** 2026-08-18
**Status:** Approved — pending implementation
**Approach:** Parallel `openoutreach/whatsapp/` module (Approach B)

---

## Overview

Add WhatsApp as a second outreach channel alongside LinkedIn. Campaigns become multi-channel: a `channel_sequence` setting determines which channel to try first based on what contact data is available for each lead. The same AI follow-up agent, deal states, chat summaries, and messages page serve both channels — WhatsApp is a different transport at the leaf nodes, not a separate system.

Lead phone numbers are sourced from Google Maps, Bing Maps, DuckDuckGo Maps (new scraper), CSV import, and LinkedIn contact info extraction (already implemented). WhatsApp sessions authenticate via QR code (WhatsApp Web, Playwright-based) — desktop shows QR in tray popup, cloud shows QR via inline image API endpoint.

---

## Architecture

### Channel abstraction (convention, not inheritance)
No abstract base class yet (YAGNI — extract when a 3rd channel arrives). LinkedIn and WhatsApp follow the same module pattern:
- `models/profile.py` — session/credential model
- `browser/session.py` — Playwright session wrapper
- `tasks/` — task handlers
- `pipeline/` — lead discovery

### How routing works
1. Campaign defines `channel_sequence: ["whatsapp", "linkedin"]` (or any order)
2. At task planning time, scheduler checks which channels are available per lead (`phone` set → WhatsApp available, `linkedin_url` set → LinkedIn available)
3. First available channel in sequence becomes `Deal.active_channel`
4. If that channel exhausts attempts (max tries reached, FAILED state), scheduler switches `Deal.active_channel` to next available channel and plans new tasks
5. `ChatMessage.channel` records which channel each message was sent/received on

---

## Data Model Changes

### `Lead`
- Add `phone: Optional[str]` — E.164 format (`+15551234567`)
- Add `phone_source: Optional[str]` — `"google_maps" | "bing_maps" | "duckduckgo_maps" | "linkedin_contact" | "csv_import" | "manual"`
- Add sparse unique index on `phone` (like `linkedin_url`) — dedup across all sources

### `Campaign`
- Add `channel_sequence: List[str]` — default `["linkedin"]`; e.g. `["whatsapp", "linkedin"]`
- Add `channel_settings: Dict[str, dict]` — per-channel config:
  ```json
  {
    "whatsapp": {"max_attempts": 3, "message_template": "..."},
    "linkedin": {"max_attempts": 5, "message_template": "..."}
  }
  ```
- Add `whatsapp_profile_id: Optional[ObjectId]` — which WhatsAppProfile executes WA tasks for this campaign

### `Deal`
- Add `active_channel: str` — default `"linkedin"`; updated when channel switches
- No changes to `DealState` — states are channel-agnostic (PENDING = pending on active channel)

### `ChatMessage`
- Add `channel: str` — default `"linkedin"` (existing rows unaffected); `"whatsapp"` for WA messages

### New model: `WhatsAppProfile`
```python
class WhatsAppProfile(MongoModel):
    user_id: str
    phone_number: Optional[str]              # E.164, populated after first successful auth
    display_name: Optional[str]              # WA display name, populated after auth
    session_data_encrypted: Optional[bytes]  # WA Web localStorage+cookies, same crypto as LinkedInProfile
    status: str                              # "connected" | "disconnected" | "banned"
    last_seen: Optional[datetime]
    created_at: datetime
```

---

## Module Structure

```
openoutreach/whatsapp/
├── __init__.py
├── models/
│   └── profile.py           # WhatsAppProfile MongoDB model
├── browser/
│   ├── session.py           # WASession — Playwright wrapper (mirrors AccountSession)
│   ├── launch.py            # launch browser, load stored session, detect QR vs authenticated
│   └── qr.py                # capture QR element as PNG bytes, poll auth status
├── tasks/
│   ├── send_message.py      # initial outreach handler
│   ├── follow_up.py         # follow-up handler (uses existing follow-up agent)
│   └── sync.py              # inbox sync → ChatMessage(channel="whatsapp")
├── pipeline/
│   └── maps_scraper.py      # multi-backend maps scraper → Lead with phone
└── api/
    └── router.py            # QR endpoint, WhatsAppProfile CRUD, session status
```

---

## WhatsApp Session (Playwright)

### Auth flow
1. `RemoteDaemon` creates a `WASession` per `WhatsAppProfile` (desktop and cloud)
2. `launch.py` opens Chromium, navigates to `web.whatsapp.com`
3. `launch.py` checks: stored `session_data_encrypted` present → load it → check if authenticated
4. If not authenticated (or no stored session): call `qr.py` to extract QR PNG
5. QR PNG served at `GET /api/whatsapp/qr/{profile_id}` — frontend polls every 2s
6. User scans QR with phone → WA Web authenticates
7. `launch.py` detects authenticated state, captures `localStorage` + cookies, encrypts and saves to `WhatsAppProfile.session_data_encrypted`
8. `WhatsAppProfile.status` → `"connected"`, `phone_number` and `display_name` extracted from WA Web DOM

### Sending messages
Navigate to `https://web.whatsapp.com/send?phone={e164}&text={encoded}` → wait for chat to load → click send button. No Voyager-style API layer needed — WA Web URL scheme handles routing.

### Reading inbox (sync)
Navigate to each open conversation → extract messages since `last_sync_timestamp` → save as `ChatMessage(channel="whatsapp")`.

### Session storage
Same encryption as `LinkedInProfile.cookie_data_encrypted` via `mongodb/crypto.py`. Desktop keychain not used for WA session (session stored in MongoDB like LinkedIn).

---

## Task Queue Integration

### New task types
- `whatsapp_message` — initial outreach (first contact)
- `whatsapp_follow_up` — subsequent messages / replies
- `whatsapp_sync` — inbox sync, detects new replies (mirrors `check_pending`)

### Scheduler
`core/scheduler.py` gains:
- `plan_whatsapp_window(campaign, whatsapp_profile_id, user_id)` — same structure as `plan_connect_window`
- Channel routing: before planning any task, check `Lead.phone` (WA available) and `Lead.linkedin_url` (LinkedIn available) against `campaign.channel_sequence`

### Daemon
`RemoteDaemon` gains:
- `_whatsapp_sessions: Dict[str, WASession]` pool (keyed by `whatsapp_profile_id`)
- `reconcile()` runs WA session pool alongside LinkedIn session pool
- WA task handlers receive `(task, wa_session)` — same signature pattern as LinkedIn handlers

---

## Maps Scraper

### File: `openoutreach/whatsapp/pipeline/maps_scraper.py`

Three Playwright backends, same interface:

```python
async def scrape(query: str, country_code: str, backend: str) -> List[BusinessListing]
```

`BusinessListing`: `name`, `phone`, `website`, `address`, `category`, `source`

**Backends:**
- `google_maps` — `https://www.google.com/maps/search/{query}` — scroll results, extract listings
- `bing_maps` — `https://www.bing.com/maps?q={query}` — same pattern
- `duckduckgo_maps` — `https://duckduckgo.com/?q={query}&ia=maps&iaxm=maps` — Apple Maps data, different result set

**Pipeline:**
1. Try backends in order (default: Google → Bing → DDG, configurable per campaign)
2. Dedup by phone across all backends before creating Leads
3. `phonenumbers` library normalizes phones to E.164 using `country_code` for inference
4. Creates `Lead(phone=..., phone_source=backend, ...)` — upserts on phone uniqueness

**Campaign config for lead source:**
- `lead_source: "linkedin_search" | "google_maps" | "csv_import"` (existing: `linkedin_search`)
- `maps_query: Optional[str]` — search query for maps backends
- `maps_country_code: Optional[str]` — ISO country code for phone normalization
- `maps_backends: List[str]` — default `["google_maps", "bing_maps", "duckduckgo_maps"]`

---

## AI Follow-up (No Changes Required)

The existing follow-up agent works for WhatsApp without modification:
- `update_chat_summary()` reads all `ChatMessage` rows for the Deal regardless of `channel` field
- `follow_up_agent.j2` template generates message text — channel-agnostic
- `plan_follow_up_window()` in scheduler determines whether to dispatch `linkedin_follow_up` or `whatsapp_follow_up` task based on `Deal.active_channel`
- The WA follow-up handler calls `WASession.send_message()` instead of LinkedIn Voyager — that's the only difference

---

## Frontend

### Settings — new "WhatsApp" tab
- Connected WhatsApp numbers (card list, mirrors LinkedIn credential cards)
- "Connect new number" → POST `/api/whatsapp/profiles` → triggers QR generation
- QR displayed inline (polls `/api/whatsapp/qr/{profile_id}` every 2s, renders `<img>` tag)
- Status badge: Connected / Disconnected / Banned
- Disconnect / delete actions

### Campaign creation — new "Channels" step
- Channel checkboxes: `[x] LinkedIn  [x] WhatsApp`
- Drag to reorder → sets `channel_sequence`
- Per-channel accordion: message template, max attempts before escalating to next channel
- WhatsApp requires selecting a connected `WhatsAppProfile`
- Lead source selector: LinkedIn Search / Google Maps / CSV Import
- Google Maps selected → show query field + country selector + backend checkboxes

### Leads table
- New "Channels" column: LinkedIn icon (if `linkedin_url` set) + WhatsApp icon (if `phone` set)
- Active channel badge on Deal row (shows current `Deal.active_channel`)

### Messages page
- Channel filter pill: All / LinkedIn / WhatsApp
- Channel icon on each conversation card in sidebar
- Message bubbles show channel badge when thread is mixed-channel
- No structural changes to conversation view — chronological order, unified thread per Deal

### Desktop tray app
- New tray menu section: "WhatsApp — Connected" or "WhatsApp — Scan QR"
- "Scan QR" → opens pywebview popup displaying QR image (polls same API endpoint)

---

## Phased Implementation

### Phase 1 — Foundation (data models + WhatsApp profile)
- [ ] Add `phone`, `phone_source` to `Lead` model + sparse unique index
- [ ] Add `channel_sequence`, `channel_settings`, `whatsapp_profile_id` to `Campaign`
- [ ] Add `active_channel` to `Deal`
- [ ] Add `channel` field to `ChatMessage` (default `"linkedin"`, no migration needed)
- [ ] Create `WhatsAppProfile` model (`openoutreach/whatsapp/models/profile.py`)
- [ ] FastAPI CRUD endpoints for `WhatsAppProfile` (`/api/whatsapp/profiles`)

### Phase 2 — WhatsApp session + QR auth
- [ ] `openoutreach/whatsapp/browser/launch.py` — Playwright launch, session load/save
- [ ] `openoutreach/whatsapp/browser/qr.py` — QR PNG capture, auth detection
- [ ] `openoutreach/whatsapp/browser/session.py` — `WASession` wrapper (`send_message`, `check_inbox`)
- [ ] `GET /api/whatsapp/qr/{profile_id}` endpoint
- [ ] `RemoteDaemon` gains `_whatsapp_sessions` pool
- [ ] Frontend: WhatsApp tab in Settings with QR display + connection status

### Phase 3 — Messaging tasks + AI follow-up
- [ ] `openoutreach/whatsapp/tasks/send_message.py` — initial outreach handler
- [ ] `openoutreach/whatsapp/tasks/follow_up.py` — follow-up handler (reuses follow-up agent)
- [ ] `openoutreach/whatsapp/tasks/sync.py` — inbox sync → `ChatMessage(channel="whatsapp")`
- [ ] `core/scheduler.py` — `plan_whatsapp_window()`, channel routing logic
- [ ] `RemoteDaemon` — wire WA task handlers into reconcile loop
- [ ] Messages page: channel filter + channel badges on message bubbles

### Phase 4 — Multi-channel campaign config
- [ ] Campaign creation UI — Channels step (checkboxes, drag reorder, per-channel templates)
- [ ] Scheduler channel routing: check lead availability, switch `Deal.active_channel` on exhaustion
- [ ] Leads table: channel availability icons + active channel badge

### Phase 5 — Maps scraper
- [ ] `openoutreach/whatsapp/pipeline/maps_scraper.py` — Google + Bing + DDG backends
- [ ] `phonenumbers` added to `requirements/base.txt`
- [ ] Campaign creation UI — Lead Source selector + Google Maps config fields
- [ ] CSV import: map `phone` column → `Lead.phone`
- [ ] LinkedIn contact capture: write `Lead.phone` when phone found in contact overlay

### Phase 6 — Desktop tray WhatsApp
- [ ] Tray menu: WhatsApp status + "Scan QR" option
- [ ] pywebview QR popup for desktop QR scanning

---

## Out of Scope (this spec)
- WhatsApp Business API (Meta-verified) — personal WA Web only
- Instagram channel — future spec, same module pattern
- Email channel — existing stub, separate spec
- WhatsApp group messaging — 1:1 only
- Media attachments in WA messages — text only for initial implementation
