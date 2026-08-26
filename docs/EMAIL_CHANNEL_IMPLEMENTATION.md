# Email Channel Implementation

Cold-email outreach via user-supplied SMTP credentials. No platform email cost — users
bring their own Gmail / Outlook / custom SMTP. Cloudflare Workers handle open/click
tracking and unsubscribe at the edge.

## What already exists

| File | Status |
|------|--------|
| `openoutreach/emails/smtp.py` | SMTP auth-only verify (`verify_auth`) |
| `openoutreach/emails/sender.py` | `send_email` — MIME, threading headers, STARTTLS, plaintext only |
| `openoutreach/emails/models.py` | `Mailbox` model — host/port/creds/daily_limit, `sent_today`, `headroom_today`, `MailboxManager.least_loaded_under_cap` |
| `openoutreach/emails/icemail.py` | IceMail App-Passwords CSV parser |
| `openoutreach/emails/nudge.py` | Setup nudge (BetterContact + IceMail onboarding) |
| `openoutreach/emails/finder.py` | BetterContact email enrichment (already called at qualification) |

## Reference: eracle/OpenOutSend

Audited https://github.com/eracle/OpenOutSend — incomplete orchestration (no daemon driver),
but 4 lower-level modules are worth porting as pure-Python utilities. Django models/migrations
are incompatible with MongoDB; ignore them.

| Source file | Port to | When | What to take |
|---|---|---|---|
| `emails/delivery_policy.py` | `openoutreach/emails/delivery_policy.py` | Phase 2 | 6 SMTP outcome classes (deferred/quota/blocked/refused/auth-fail/transport-fail) + per-class retry/pause/ignore policy. Replaces our bare 550-only error handling. |
| `emails/threads.py` | `openoutreach/emails/threads.py` | Phase 5 | Union-find thread grouping — handles out-of-order IMAP delivery, merges split threads, idempotent re-processing. Much more robust than basic `Message-ID` matching. |
| `emails/sync.py` | `openoutreach/emails/sync.py` | Phase 5 | IMAP mirror with UID cursor + 4-criteria reply detection (threading headers, from-address, `+unsub` alias, bounce classification). Saves 1–2 days vs rolling our own. |
| `emails/warmth.py` | `openoutreach/emails/warmth.py` | v2 | IMAP Sent-folder scan → 75th-percentile daily volume → auto-reduce on bounce rate. Replaces static `daily_limit` with a dynamic ceiling. |

**Gaps before email can run end-to-end:**
- No generic SMTP import UI (currently IceMail-specific paste format)
- No `email_follow_up` task type or handler
- No email scheduler (`plan_email_follow_up_window`)
- No LLM email writer (subject + body)
- No Deal states for email (EMAIL_SENT / EMAIL_OPENED / EMAIL_REPLIED / EMAIL_BOUNCED)
- `sender.py` sends plain text only — no HTML, no tracking pixel, no List-Unsubscribe
- No Cloudflare Worker for open/click/unsubscribe tracking
- No frontend UI (mailbox settings, campaign toggle, lead email status)

---

## Phase 1 — Generic Mailbox Management + FastAPI

**Goal:** operators can add/test/delete any SMTP mailbox from the Settings UI.

### 1.1 Extend `Mailbox` model

Add `from_name: str = ""` and `user_id: str = ""` fields to `__init__`, `to_dict`, `from_dict`.
Multi-tenant: all mailbox API endpoints filter by `user_id`.

### 1.2 FastAPI endpoints

File: `openoutreach/api_v2/routers/mailboxes.py`

```
GET    /api/mailboxes              → list all for current user_id
POST   /api/mailboxes              → create + verify (calls smtp.verify_auth before saving)
POST   /api/mailboxes/test         → auth-check without saving
DELETE /api/mailboxes/{id}         → delete (own mailboxes only)
```

Request schema (POST create):
```json
{
  "host": "smtp.gmail.com",
  "port": 587,
  "username": "user@gmail.com",
  "password": "app-password-16-chars",
  "from_name": "John Smith",
  "daily_limit": 40
}
```

On POST: call `verify_auth(host, port, username, password)`. Return 400 with the error
message on failure — never save an unverified box. Encrypt `password` via
`openoutreach/mongodb/crypto.py` before storing; never return plaintext in responses.

### 1.3 Frontend — Settings → Email tab

File: `frontend/src/app/(dashboard)/settings/page.tsx`

Add "Email" tab (currently hidden behind no flag — just add the tab). Components:
- `MailboxList` — table: from_address, from_name, daily_limit, headroom today, delete button
- `AddMailboxModal` — form fields: SMTP host, port, username, password, from_name, daily_limit
  - "Test connection" button calls POST /api/mailboxes/test before submitting
  - Show Gmail app-password guide link when host contains `gmail`
- Empty state: "No mailboxes — email outreach is disabled"

### 1.4 Remove IceMail coupling from nudge

`nudge.py` hardcodes IceMail affiliate URL and its CSV paste format. Replace
`_collect_mailboxes` with a note pointing to the Settings UI. Keep `icemail.py` for
operators who still use IceMail boxes (the CSV parser is still useful).

---

## Phase 2 — Deal States + Email Task Handler

**Goal:** email tasks are claimable, executable, and tracked in Deal state.

### 2.1 Add email states to `DealState`

File: `openoutreach/crm/models/deal.py`

```python
EMAIL_QUEUED   = "email_queued"    # api_email resolved; waiting to send
EMAIL_SENT     = "email_sent"      # first email delivered
EMAIL_OPENED   = "email_opened"    # tracking pixel fired
EMAIL_REPLIED  = "email_replied"   # inbound reply detected or manually marked
EMAIL_BOUNCED  = "email_bounced"   # hard bounce — suppress email permanently
```

Add fields to `Deal`:
```python
mailbox_id: Optional[str] = None
email_sent_at: Optional[datetime] = None
email_message_id: Optional[str] = None  # for In-Reply-To threading on follow-ups
email_sequence_step: int = 0            # 0=cold, 1=follow-up 1, 2=follow-up 2
```

Note: `mailbox_id` and `email_sent_at` are already queried by `Mailbox.sent_today()`
(`models.py:256`). Adding them to the schema makes the intent explicit.

### 2.2 `email_follow_up` task handler

File: `openoutreach/emails/tasks/handle_email_follow_up.py`

```python
def handle_email_follow_up(task, session, qualifiers):
    """
    1. Resolve campaign; find next EMAIL_QUEUED deal with Lead.api_email set
    2. Check lead.email_unsubscribed — skip silently if True
    3. Pick Mailbox.objects.least_loaded_under_cap(user_id)
       - If None (all capped): keep task RUNNING, reschedule +24h, return
    4. Generate subject + body via email_agent.generate_email(deal, session, step)
    5. send_email(mailbox, lead.api_email, subject, body, in_reply_to, references)
    6. Set Deal fields: state=EMAIL_SENT, mailbox_id, email_sent_at, message_id, sequence_step+1
    """
```

Error handling:
- SMTP send failure → raise (daemon marks task FAILED, retries next cycle)
- Hard bounce 550 → set Deal.state = EMAIL_BOUNCED; set Lead.email_unsubscribed = True
- All mailboxes at daily cap → reschedule task for midnight + 1h; do not mark FAILED

### 2.3 Wire into scheduler

File: `openoutreach/core/scheduler.py`

Add `plan_email_follow_up_window(campaign, user_id)`:
- Only runs if `has_mailbox()` (from `openoutreach/emails/models.py`) and campaign has
  `"email"` in `channel_sequence`
- Respects `Mailbox.objects.remaining_today(user_id)` — never plans more tasks than
  mailboxes can send today
- Sequence timing: step 0 = immediately on qualification (if Lead.api_email is set),
  step 1 = +3 days after EMAIL_SENT, step 2 = +7 days after EMAIL_SENT
- Respects `SiteConfig.active_hours` — no sends outside active window

Add to `_run_map`:
```python
"email": _run_email,
```

Reconcile: if Deal has api_email, is QUALIFIED, and has no pending email task → create step-0 task.

---

## Phase 3 — LLM Email Writer

**Goal:** personalised subject + body, not generic templates.

### 3.1 `email_agent.j2` template

File: `openoutreach/core/templates/email_agent.j2`

Inputs (mirroring `follow_up_agent.j2` pattern):
- `profile_summary` (JSON fact list from Deal)
- `chat_summary` (empty for cold email; populated for follow-ups if LinkedIn interaction exists)
- `product_pitch`, `campaign_objective`, `booking_link`
- `sequence_step` (0=cold, 1=follow-up 1, 2=last touch)
- `ai_writing_style`, `ai_say_rules`, `ai_avoid_rules` from SiteConfig
- `seller_name`

Output: JSON `{"subject": "...", "body": "..."}`

Rules embedded in template:
- Step 0 (cold): ≤5 sentences, no "I wanted to reach out", one specific hook from profile
- Step 1+: reference prior touch ("Following up on my note about X"), one new angle only
- Subject: specific, lowercase preferred, no spam triggers (FREE / !!!)
- Body ends with single soft CTA — meeting link OR reply question, never both
- Plain text only in `body` — no markdown, no HTML tags

### 3.2 `email_agent.py`

File: `openoutreach/emails/email_agent.py`

```python
def generate_email(deal, session, sequence_step: int) -> tuple[str, str]:
    """Return (subject, body). Raises on LLM failure."""
```

Pattern: render Jinja2 template → call `openoutreach/core/llm.py` → parse JSON response.
Same as `follow_up_agent.py`.

---

## Phase 4 — Cloudflare Worker (Tracking Layer)

**Goal:** open pixel, click redirect, unsubscribe at edge — zero EC2 load.

### 4.1 Worker

File: `workers/email-tracking/src/index.ts`

Routes:
```
GET  /open/:token.gif   → 1×1 transparent GIF; log open event to KV; POST webhook to backend
GET  /click/:token      → decode destination URL from token; log click to KV; 302 redirect
GET  /unsub/:token      → render one-click unsubscribe confirmation page
POST /unsub/:token      → add email to EMAIL_SUPPRESSED KV; POST webhook to backend
```

Token format: `base64url(JSON{deal_id, campaign_id, event, dest_url})` signed with
HMAC-SHA256 using `SECRET_KEY` Worker secret. Unsigned tokens return 400.

KV namespaces:
```toml
[[kv_namespaces]]
binding = "EMAIL_EVENTS"
id = "<from wrangler kv namespace create>"

[[kv_namespaces]]
binding = "EMAIL_SUPPRESSED"
id = "<from wrangler kv namespace create>"
```

Worker secrets: `SECRET_KEY`, `WORKER_WEBHOOK_SECRET`, `BACKEND_URL`.

### 4.2 Backend webhook endpoint

File: `openoutreach/api_v2/routers/email_tracking.py`

```
POST /api/email-tracking/event
```

Request (from Worker, authenticated by `WORKER_WEBHOOK_SECRET` in header):
```json
{"deal_id": "...", "event": "open|click|unsub", "ts": 1234567890}
```

Handler logic:
- `open` / `click` → promote Deal to EMAIL_OPENED if currently EMAIL_SENT
- `unsub` → set `Lead.email_unsubscribed = True`; cancel all pending email tasks for this lead

### 4.3 `sender.py` upgrades

Current `sender.py` is plaintext only. Additions:

**1. Tracking token utility**

File: `openoutreach/emails/tracking.py`

```python
def generate_token(deal_id: str, event: str, dest_url: str = "") -> str:
    """HMAC-signed base64url token for tracking pixel / click / unsubscribe."""
```

**2. Multipart email with tracking pixel**

`_build_message` becomes `multipart/alternative`:
- `text/plain` part — plain body, no pixel
- `text/html` part — `<pre>`-wrapped body + 1×1 pixel in footer:
  ```html
  <img src="https://track.lengrowth.com/open/{token}.gif" width="1" height="1"
       style="display:none" alt="" />
  ```

**3. Link rewriting in HTML part**

Scan body for `https://` URLs; replace in HTML part only:
```
https://track.lengrowth.com/click/{token_with_dest_url}
```

**4. List-Unsubscribe headers** (required by Gmail/Yahoo for bulk senders)

```
List-Unsubscribe: <https://track.lengrowth.com/unsub/{token}>
List-Unsubscribe-Post: List-Unsubscribe=One-Click
```

### 4.4 Cloudflare setup commands

```bash
# Create KV namespaces (run once)
npx wrangler kv namespace create EMAIL_EVENTS --remote
npx wrangler kv namespace create EMAIL_SUPPRESSED --remote

# Deploy Worker
cd workers/email-tracking
npx wrangler deploy --env production

# Set secrets
npx wrangler secret put SECRET_KEY
npx wrangler secret put WORKER_WEBHOOK_SECRET
npx wrangler secret put BACKEND_URL   # https://api.lengrowth.com

# Add custom domain route in Cloudflare dashboard:
# track.lengrowth.com/* → email-tracking Worker
```

---

## Phase 5 — Multi-Step Sequence + Reply Detection

**Goal:** 3-touch sequence; sequence stops automatically on reply.

### 5.1 Sequence logic (in scheduler)

Scheduler creates tasks on a timer anchored to `deal.email_sent_at`:
- Step 0: immediately on EMAIL_QUEUED
- Step 1: +3 days after step 0 `email_sent_at`, only if Deal is EMAIL_SENT or EMAIL_OPENED
- Step 2: +7 days after step 0, only if not EMAIL_REPLIED or EMAIL_BOUNCED

Task handler checks `deal.email_sequence_step` before sending. If deal has advanced
past expected state (lead replied between task creation and execution), skip silently.

Configurable delays (`SiteConfig` fields): `email_followup_day1: int = 3`, `email_followup_day2: int = 7`.

### 5.2 Reply detection via IMAP (v2 — after Phase 5.1 ships)

File: `openoutreach/emails/inbox.py`

Poll IMAP inbox at daemon idle cycle. Match inbound messages by `In-Reply-To` or
`References` header against `deal.email_message_id`. On match: promote Deal to
EMAIL_REPLIED, cancel remaining email tasks for lead.

Add optional fields to `Mailbox`: `imap_host: str = ""`, `imap_port: int = 993`.
Skip inbox polling when `imap_host` is blank (SMTP-only mode stays valid).

---

## Phase 6 — Frontend Campaign Integration

**Goal:** operators enable email per campaign and see email status on leads.

### 6.1 Campaign wizard — channels step

File: `frontend/src/components/campaigns/create-campaign-wizard.tsx`

- Add "Email" channel option (shown only when `GET /api/mailboxes` returns ≥1 result)
- When selected: add `"email"` to `channel_sequence` payload
- No extra query field needed — email uses `Lead.api_email` resolved by BetterContact

### 6.2 Leads list — email status column

File: `frontend/src/app/(dashboard)/campaigns/[id]/leads/page.tsx`

Add "Email" column with icon per state:
- `EMAIL_QUEUED` → clock icon
- `EMAIL_SENT` → envelope icon
- `EMAIL_OPENED` → envelope-open icon
- `EMAIL_REPLIED` → reply icon (green)
- `EMAIL_BOUNCED` → x icon (red)

Tooltip: last sent date + sequence step (e.g. "Step 2 of 3 · Sent Aug 15").

### 6.3 Settings → Email tab (extended from Phase 1)

Add sequence configuration section:
- Follow-up day 1 delay (default: 3 days)
- Follow-up day 2 delay (default: 7 days)
- Max sequence steps (default: 3, range 1–5)

---

## Data model summary

### `mailboxes` collection (extend existing)
```json
{
  "_id": "uuid",
  "user_id": "user123",
  "host": "smtp.gmail.com",
  "port": 587,
  "username": "sender@domain.com",
  "password": "<encrypted>",
  "from_name": "John Smith",
  "from_address": "sender@domain.com",
  "daily_limit": 40,
  "imap_host": "imap.gmail.com",
  "imap_port": 993,
  "created_at": "..."
}
```

### `deals` collection (add email fields)
```json
{
  "mailbox_id": null,
  "email_sent_at": null,
  "email_message_id": null,
  "email_sequence_step": 0
}
```

### `leads` collection (add suppression flag)
```json
{
  "email_unsubscribed": false
}
```

---

## Build order

| Phase | Effort | Unblocks |
|-------|--------|---------|
| 1 — Generic mailbox CRUD + Settings UI | 1 day | All phases |
| 2 — Deal states + task handler + scheduler | 1 day | End-to-end send |
| 3 — LLM email writer | 0.5 day | Personalisation |
| 4 — Cloudflare Worker tracking | 1 day | Open/click/unsub events |
| 5 — Multi-step sequence | 0.5 day | Full 3-touch funnel |
| 6 — Frontend campaign + leads UI | 1 day | Operator experience |

**Total: ~5 days**

---

## Implementation progress

- [x] Phase 1 — Generic mailbox management + FastAPI endpoints + Settings UI
- [ ] Phase 2 — Deal states + email task handler + scheduler integration
- [ ] Phase 3 — LLM email writer (`email_agent.py` + `email_agent.j2`)
- [ ] Phase 4 — Cloudflare Worker (tracking pixel, click redirect, unsubscribe, backend webhook)
- [ ] Phase 5 — Multi-step sequence + IMAP reply detection (v2)
- [ ] Phase 6 — Frontend: campaign wizard, leads list email column, Settings email tab
