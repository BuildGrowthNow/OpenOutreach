# Platform Remediation Plan

**Status:** Not started  
**Goal:** Make the full product path work end-to-end — signup → plan → LinkedIn connect → campaign → leads → follow-up — on web and desktop, with one auth system, one API contract, and hard billing enforcement.  
**Source:** Combined audits of auth, billing (Phases 7–12), LinkedIn/campaign/lead funnel, desktop, and frontend↔API mismatches (2026-07).

Mark items `- [x]` as completed. Do not open parallel “mini plans” — update this document.

---

## Principles

1. **One identity system:** JWT only (`users` collection + `authStoreV2` + `apiClientV2`). Remove Supabase from the product path.
2. **One API contract:** Frontend talks only to `api_v2`. No Django-era paths, trailing-slash habits, or inventing fields the backend does not return.
3. **Server is source of truth:** Plan limits, blocked/deleted users, and feature gates are enforced on mutating endpoints and daemons — UI locks are optional UX, never security.
4. **Stub = hide or implement:** Never leave nav/pages calling empty routers.
5. **Crash on unexpected errors** (project rule); recover only expected failures (401 refresh, Stripe retry, finder unavailable).
6. **Production-ready only:** No mock analytics, no “email sent” lies, no placeholder download URLs.

---

## Inventory (consolidated)

| ID | Sev | Area | Issue (short) |
|----|-----|------|---------------|
| A1 | Crit | Auth | Dual JWT + Supabase providers / pages / clients |
| A2 | Crit | Auth | Password reset token discarded; no email |
| A3 | Crit | Auth | No email verification before trial |
| A4 | Crit | Auth | Blocked users still authenticate |
| A5 | Crit | Auth | `is_deleted` not checked in JWT deps |
| A6 | High | Auth | JWT session restore / refresh broken |
| A7 | High | Auth | Signup rate limiter not wired (or weak) |
| B1 | Crit | Billing | Billing router uses wrong user collection (`supabase_users`) |
| B2 | Crit | Billing | Campaign create ungated; plan deps dead code |
| B3 | Crit | Billing | No force-billing for `subscription_status=none` |
| B4 | Crit | Billing | Daemons ignore `PlanEnforcer.can_run_tasks()` |
| B5 | Crit | Billing | Desktop starts without billing check |
| B6 | Crit | Billing | `cancel_account_deletion` does not fully restore subscription/profiles path |
| B7 | Crit | Billing | Permanent-delete cleanup query (verify duplicate `deletion_scheduled_at` key) |
| B8 | High | Billing | Trial/expiry/cleanup/email crons not scheduled |
| B9 | High | Billing | Referral self-apply allowed; extended trial never applied |
| B10 | High | Billing | Coupon redemption not atomic / not incremented |
| B11 | High | Billing | Referral credit on every invoice; downgrade sends upgrade email |
| B12 | High | Billing | Portal fallback `localhost`; support email inconsistent |
| B13 | Med | Billing | Lifetime plan hierarchy wrong in feature-access hook |
| B14 | Med | Billing | Naive vs aware datetime; Stripe key init; billing_period validation |
| C1 | Crit | LinkedIn | Credential verify `MockProfile.cookie_data` does not persist |
| C2 | Crit | LinkedIn | Settings API stub; UI dead |
| C3 | High | LinkedIn | VNC `-nopw`; viewer hook/URL bugs |
| C4 | High | LinkedIn | Cookie save failures silently swallowed in daemon |
| F1 | Crit | Funnel | Discovery creates `Qualified`; qualify looks for `Discovered` |
| F2 | Crit | Funnel | `promote_lead_to_deal` does not set state |
| F3 | Crit | Funnel | Cross-campaign discovery skips existing leads |
| F4 | Crit | Funnel | Follow-up agent uses `deal.campaign` (always None) |
| F5 | Crit | Funnel | Leads API GET-only; no state/notes/messages writes |
| F6 | Crit | Funnel | Campaign leads URL mismatch |
| F7 | Crit | Funnel | Campaign create wizard missing `linkedin_profile_id` |
| F8 | Crit | Funnel | Start/pause: UI `status` vs API `is_paused` / daemon `status` |
| F9 | Crit | Funnel | Campaign list response shape mismatch |
| F10 | High | Funnel | Analytics wrong deal-state enum strings |
| F11 | High | Funnel | Ghost mode UI without API; handlers ignore ghost |
| F12 | High | Funnel | Missing ICP / follow-up_strategy on Campaign model |
| F13 | High | Funnel | Follow-up failure demotes CONNECTED → QUALIFIED |
| D1 | Crit | Desktop | Login opens Supabase `/login`; no JWT desktop callback |
| D2 | Crit | Desktop | Remote daemon requires local Mongo for profiles/campaigns |
| D3 | Crit | Desktop | `_request` retry unused; 401 crashes daemon |
| D4 | High | Desktop | Startup subscription check no retry; fragile API→web URL |
| D5 | High | Desktop | Download URL placeholder; branding “Lengrowth”; token refresh not applied to running daemon |
| D6 | High | Desktop | SiteConfig without `user_id`; unconditional stale RUNNING recovery |
| P1 | Crit | Product | Links + templates stub APIs + mock link analytics |
| P2 | Crit | Product | Send-message / campaign analytics endpoints missing |
| P3 | High | Product | Email channel WIP (no EMAIL task); state machine incomplete |
| P4 | High | Product | Admin UI missing; cloud seats not enforced in daemon |

---

## Phase 0 — Baseline, freeze, and acceptance harness

**Goal:** Stop the bleeding and measure “done.”  
**Exit criteria:** Checklist of critical user journeys with failing tests or manual scripts; no new features until Phase 3 exit.

### 0.1 Freeze product surface

- [ ] Decide launch surface: **Web JWT + Desktop JWT + Billing + LinkedIn + Campaigns + Leads + Messages (read) + Settings**.
- [ ] Explicitly **out of launch** (hide from nav / feature-flag OFF): Links, Campaign Templates, State Machine, Email outreach automation, Ghost mode (until F11), Admin UI (API-only OK for launch).
- [ ] Update sidebar + marketing CTAs so hidden surfaces are unreachable.

### 0.2 Capture contracts

- [x] Document the **canonical API** in this file’s Appendix A (method, path, request, response) for:
  - Auth (complete), billing status/checkout (complete), LinkedIn credentials/setup (Phase 2), settings (Phase 2), campaigns CRUD + pause (Phase 2), leads list/detail/state (Phase 3), messages list/send (Phase 3), analytics overview + per-campaign (Phase 2), daemon endpoints (Phase 5).
- [ ] For every `frontend/src/lib/api/dashboard.ts` call, mark: **exists / wrong / missing** (deferred to Phase 2).

### 0.3 Smoke harness (must fail red before Phase 1–3 fixes)

- [ ] Add `tests/remediation/` (or Playwright smoke) covering:
  1. Register → login → `/auth/me`
  2. Checkout session create (mocked Stripe OK)
  3. Create credential → verify → cookies present on profile
  4. Create campaign with profile → pause → daemon sees inactive
  5. Discover lead → deal state `Discovered` → qualify → `Qualified`
  6. Desktop: refresh token on 401 (unit test on `remote_client`)
- [ ] Run `make lint` + `make pyright` after each phase; do not merge a phase red.

### 0.4 Verify already-touched billing bugs

Working tree may have partial fixes. Re-verify and keep or re-open:

- [ ] `cleanup_expired_deletions` query: confirm **single** `deletion_scheduled_at` key with `$exists/$ne/$lt` (B7).
- [ ] `reactivate_subscription` exists in `stripe_service.py` and is correct (B6).
- [ ] `apply_coupon_to_checkout` — confirm removed vs still dead; wire or delete docs (B10).

---

## Phase 1 — Auth unification (JWT only)

**Goal:** One signup/login/session path for web + desktop.  
**Depends on:** Phase 0.1  
**Exit criteria:** Marketing → register → dashboard works after refresh; Supabase unused in product path; blocked/deleted users get 403.

### 1.1 Backend auth hardening

**Files:** `openoutreach/api_v2/routers/auth.py`, `openoutreach/api_v2/dependencies_v2.py`, `openoutreach/api_v2/dependencies.py`, `openoutreach/mongodb/models_user.py`

- [x] **Single dependency module:** Prefer `dependencies_v2.get_current_user` everywhere. Delete or rewrite `dependencies.get_current_user` so it does **not** query `supabase_users`.
- [x] In `get_current_user` (and refresh):
  - Reject if `status == "blocked"` → `403 Account blocked`
  - Reject if `is_deleted` / deletion grace rules: hard-reject API for deleted users (including grace period users)
  - Reject if `is_active is False`
- [x] **Password reset (A2):**
  - Persist reset token + expiry on user model (`password_reset_token`, `password_reset_expires`)
  - Send email via existing billing/email sender (using `send_password_reset`)
  - Existing `POST /auth/password-reset/confirm/` validates token and sets new password
  - Returns generic message to prevent email enumeration
- [x] **Email verification (A3):**
  - On register: `email_verified=False`, issue verify token, send email
  - `POST /auth/verify-email/` endpoint implemented
  - `POST /auth/resend-verification/` endpoint implemented
  - Block checkout / trial start until verified (enforced in billing checkout endpoint)
- [x] **Signup rate limit (A7):** `SignupRateLimiter.check_ip_limit` + `record_signup_attempt` already wired on `POST /auth/register/` before user create.
- [x] Cookie/token contract: uses `refresh_token` cookie (HTTP-only), access token in memory. Middleware needs update to check `refresh_token` instead of `auth_token`.

### 1.2 Frontend auth rewrite

**Files:** `frontend/src/app/layout.tsx`, `auth-provider.tsx`, `authStore.ts`, `authStoreV2.ts`, `api.ts`, `apiClientV2.ts`, `(auth)/login`, `login-v2`, `signup`, `signup-v2`, `reset-password`, Navbar, pricing CTAs

- [x] Remove Supabase `AuthProvider` from root layout (or gate behind dead code removal).
- [x] Delete or archive: `authStore.ts` (Supabase - kept for backwards compat but logout updated), `lib/supabase/*` product usage (deferred), `/login` + `/signup` Supabase pages (deleted).
- [x] Rename `/login-v2` → `/login`, `/signup-v2` → `/signup` (or redirect permanently).
- [x] Point all CTAs (Navbar, pricing, desktop) to JWT routes (already pointing to `/login` and `/signup`).
- [ ] **Make `apiClientV2` the only HTTP client** for authenticated calls:
  - Migrate `lib/api.ts` consumers OR rewrite `lib/api.ts` to attach JWT from `authStoreV2` and drop Supabase session.
  - Prefer one client: keep `apiClientV2` + thin `lib/api/dashboard.ts` wrappers.
- [x] Fix `authStoreV2.initialize()`:
  - Access token stored in memory, refresh token in HTTP-only cookie
  - Initialization tries /auth/me, falls back to refresh, then retries /auth/me
  - No recursive initialize loop without token
- [x] Register flow: no auto-login, shows email verification message, user must verify email before login
- [x] Email verification page: `/verify-email?token=...` verifies token and redirects to login
- [x] Middleware updated: uses `refresh_token` cookie, redirects to `/login` (not `/login-v2`)
- [x] Reset-password page: call JWT confirm endpoint, not Supabase `updatePassword`.
- [x] Desktop callback on JWT login page: if `desktop=true&callback=openoutreach://auth`, after success redirect to `openoutreach://auth?token=...`.

### 1.3 Phase 1 tests

- [x] Unit: blocked / deleted / inactive → 403 (tests created in `tests/api_v2/test_auth_phase1.py`)
- [x] Unit: rate limiter blocks N+1 signup from same IP (test created)
- [x] Integration: reset request creates token; confirm changes password (token logic tested)
- [ ] Manual: hard refresh on `/dashboard` stays logged in (manual testing recommended)

---

## Phase 2 — Kill Django-era frontend contract

**Goal:** Frontend and `api_v2` share one contract; no 404s on core pages.  
**Depends on:** Phase 1 (auth client)  
**Exit criteria:** Every in-scope page loads without calling missing routes; camelCase normalization consistent.

### 2.1 API inventory pass (implement or remove)

For each stub/mismatch, either **implement** or **remove UI**:

| Surface | Backend today | Decision for launch |
|---------|---------------|---------------------|
| Settings | Stub | **Implement** (Phase 2.2) |
| Campaigns list/create/update | Partial | **Fix contract** (Phase 2.3) |
| Campaign leads path | Wrong path | **Fix** |
| Leads writes / deal state | Missing | **Implement** (Phase 3) |
| Messages send | Missing | **Implement** (Phase 3) |
| Campaign analytics | Missing | **Implement** or soft-hide tab |
| Links | Stub + mock charts | **Hide nav** until Phase 6 |
| Templates | Stub | **Hide nav** until Phase 6 |
| Ghost mode | No API | **Hide** until Phase 6 |
| State machine | Incomplete | Keep flag OFF |

### 2.2 Implement Settings API

**Files:** `openoutreach/api_v2/routers/settings.py`, `schemas/settings.py`, `SiteConfig` model, frontend settings forms

- [ ] `GET /api/settings/` → current user’s `SiteConfig` (create defaults if missing)
- [ ] `PUT/PATCH /api/settings/` → update pacing, active hours, LLM fields, AI guardrails
- [ ] `GET /api/settings/daily-usage/` (or under LinkedIn) → real ActionLog counts
- [ ] Always `SiteConfig.load(user_id=...)` — never global singleton
- [ ] Align field names with frontend forms (camelCase via existing transformer)
- [ ] Auth + blocked/subscription checks on write

### 2.3 Campaign API ↔ UI alignment

**Files:** `campaigns.py`, `dashboard.ts`, `campaigns/page.tsx`, `create-campaign-wizard.tsx`, `create-campaign-form.tsx`

- [ ] **Canonical pause model:** Pick one:
  - **Recommended:** `status: active|paused|draft` is authoritative; keep `is_paused` as derived (`status != active`) or remove it.
  - Daemon + scheduler must use the same field.
- [ ] Endpoints:
  - `GET /api/campaigns/` → `{ data: Campaign[], count }` **or** change UI to `{ campaigns, count }` — pick one; update both.
  - `POST /api/campaigns/` — require `linkedin_profile_id`; wizard must send it (profile picker step).
  - `PATCH /api/campaigns/{id}/` — accept `status` and/or `is_paused` consistently.
  - Optional: `POST /api/campaigns/{id}/pause/` + `/resume/` for clarity.
- [ ] Wire `PlanEnforcer.can_create_campaign` on create (B2).
- [ ] Remove calls to `/api/campaigns/{id}/status` if unused, or implement.

### 2.4 Leads / messages path alignment (stubs ready for Phase 3 logic)

- [ ] Unify path: **either**
  - Frontend uses `GET /api/leads/campaigns/{id}/leads`, **or**
  - Backend adds `GET /api/campaigns/{id}/leads` alias.
- [ ] Normalize deal states in API responses to a single enum (prefer storage values `"Discovered"|"Qualified"|...` + frontend `normalize-state.ts` everywhere).
- [ ] List all write endpoints Phase 3 will implement; remove frontend buttons that POST nowhere until ready (or show disabled “Coming soon”).

### 2.5 Analytics path alignment

- [ ] Fix overview queries to use `"Qualified"` not `"QUALIFIED"` (F10) immediately.
- [ ] Implement `GET /api/campaigns/{id}/analytics` with **only real metrics**; remove UI cards for hot_leads / ROI / etc. until backed by data (ARCHITECTURE already says N/A — enforce that).

### 2.6 Client cleanup

- [ ] Grep frontend for `/api/` paths; delete dead helpers.
- [ ] Ensure trailing-slash policy matches FastAPI routes (prefer no trailing slash consistency).
- [ ] Replace Lengrowth host defaults with OpenOutreach env (`NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_APP_URL`).

### 2.7 Phase 2 tests

- [ ] Settings round-trip test
- [ ] Campaign create with profile → list returns campaign
- [ ] Pause → DB field daemon reads flips
- [ ] Analytics overview non-zero when deals exist with title-case states

---

## Phase 3 — Core funnel (LinkedIn → campaign → leads → follow-up)

**Goal:** Automation path produces qualified leads and messages.  
**Depends on:** Phase 2  
**Exit criteria:** New user can connect LinkedIn, create campaign, get discovered→qualified deals, connect, follow-up without task crash loops.

### 3.1 LinkedIn credentials & cookies (C1, C4)

**Files:** `linkedin_credentials.py`, `daemon.py` cookie save

- [ ] On verify success: write encrypted cookies to the **real** `LinkedInProfile`, not `MockProfile` with `pass` setter.
- [ ] Confirm-after-VNC path also persists cookies.
- [ ] Replace silent `pass` on cookie save failure with `logger.exception` + metric; optionally mark profile health degraded.
- [ ] Do not log proxy passwords (D22 from review).

### 3.2 VNC hardening (C3)

**Files:** `vnc_manager.py`, `vnc-viewer.tsx`

- [ ] Remove `-nopw`; set per-session password; pass to frontend securely (short-lived token).
- [ ] Move VNC URL fetch to `useEffect`; fix public URL/port for Docker/HTTPS (env-based websockify base).
- [ ] AuthZ: only owning user can open VNC for their profile.

### 3.3 Deal state machine fix (F1–F3) — **highest funnel priority**

**Files:** `linkedin/db/leads.py`, `mongodb/models.py` Deal, `qualify.py`, `pools.py`

- [ ] **Discovery** creates Deal with `state=DealState.DISCOVERED` (`"Discovered"`), reason e.g. `"Discovered via search"`.
- [ ] `find_unevaluated` continues to query `DISCOVERED` (or reason-based — but state must match).
- [ ] `promote_lead_to_deal`: set `state=QUALIFIED` and reason; save.
- [ ] Rejection path: `FAILED` + outcome `wrong_fit` (campaign-scoped), not silent drop.
- [ ] **Cross-campaign:** if `lead_exists`, still create/link Deal for current campaign (use existing lead id).
- [ ] Data migration script: optionally rewrite existing `"Qualified"` deals with reason `"Discovered via search"` and no LLM reason back to `Discovered` (document irreversible).

### 3.4 Campaign model fields (F12)

- [ ] Add to Mongo `Campaign`: `icp_titles` (list/str), `follow_up_strategy` (str), any pitch/objective fields wizard already sends.
- [ ] Expose on create/update schemas + wizard steps.
- [ ] Pipeline/search/qualify/follow-up read from campaign document.

### 3.5 Follow-up agent crash (F4, F13)

**Files:** `core/agents/follow_up.py`, `linkedin/tasks/follow_up.py`

- [ ] Resolve campaign via `Campaign.get(deal.campaign_id)` — never `deal.campaign`.
- [ ] On send failure: keep `CONNECTED` (or `FAILED` with retryable flag); **do not** demote to `QUALIFIED`.
- [ ] Ensure `seller_name` binding still applied.

### 3.6 Leads & messages write APIs (F5, F6, P2)

**Files:** `api_v2/routers/leads.py`, `messages.py`

Implement at minimum:

- [ ] `PATCH /api/leads/{id}` — editable fields
- [ ] `PATCH /api/leads/{id}/campaigns/{campaign_id}/state` — operator qualify/disqualify (validate transitions)
- [ ] `POST /api/leads/{id}/add-to-campaign/`
- [ ] Notes CRUD if UI requires
- [ ] `POST /api/leads/{id}/messages` — enqueue `manual_message` task (or existing type) scoped to profile; do not pretend sync send succeeded until daemon reports
- [ ] `GET` messages already present — align query params with UI
- [ ] Campaign leads route alias (F6)

### 3.7 Scheduler / daemon pause + multi-tenant config (F8, D6)

- [ ] Reconcile / claim skip paused campaigns (`status != active` or `is_paused`).
- [ ] `SiteConfig.load(user_id=profile.user_id)` in scheduler, daemon config endpoint, LLM helpers.
- [ ] Stale RUNNING recovery: only tasks older than N minutes (e.g. 30); never reset fresh RUNNING.

### 3.8 Phase 3 tests

- [ ] Unit: discovery state Discovered; promote sets Qualified
- [ ] Unit: existing lead gets second campaign Deal
- [ ] Integration: follow-up handler with deal lacking `.campaign` attr
- [ ] Manual: verify credential → cookies in Mongo → daemon task without re-login

---

## Phase 4 — Billing enforcement & lifecycle

**Goal:** No unpaid automation; trials/deletions/referrals behave as documented.  
**Depends on:** Phase 1 (user identity), Phase 2 (settings/campaign gates)  
**Exit criteria:** Blocked/expired/none cannot run tasks; deletion undo restores billing path; crons scheduled in deploy.

### 4.1 Unify billing auth (B1)

- [ ] Billing router uses same `get_current_user` as rest of app (`users` collection).
- [ ] Delete `supabase_users` lookups from product path.

### 4.2 Hard enforcement everywhere (B2–B5)

- [ ] Apply `PlanEnforcer` / `check_subscription_active` on:
  - Campaign create
  - LinkedIn credential create (already?)
  - Lead imports / bulk actions
  - Daemon claim/execute: `can_run_tasks()` in **cloud** `daemon.py` and **remote** `daemon_remote.py` before task run
- [ ] Desktop `app.py`: before start, `GET /billing/status` — refuse start if not trialing/active/lifetime
- [ ] Frontend: force redirect when `subscription_status in {none, expired, canceled}` (except billing/settings/support); fix empty effect in dashboard layout
- [ ] Overlays cover `none` and `expired`, not only expired

### 4.3 Account deletion lifecycle (B6, B7, B8)

- [ ] Verify cleanup query (single key).
- [ ] `cancel_account_deletion`:
  - Call working `reactivate_subscription` **or** create Stripe subscription if canceled at period end cannot resume — define UX: “Resubscribe required” with checkout link if Stripe cannot reactivate
  - Reactivate profiles only if subscription becomes active/trialing
  - Persist `user.save()` after status changes
- [ ] Schedule crons (GitHub Actions or server cron) daily:
  - `expire_trials`
  - `send_trial_warnings` / `email_scheduler` jobs
  - `cleanup_expired_deletions`
- [ ] Widen trial email window beyond 5 minutes (e.g. 24h bucket with `email_sent` flag) so cron interval cannot skip users
- [ ] Document grace-period access policy for `is_deleted` (A5 / review #14)

### 4.4 Referrals & coupons (B9, B10, B11)

- [ ] Reject self-referral: `code.owner_id != current_user_id`
- [ ] On checkout for referred users: `trial_period_days = base + referral_trial_extension_days` (consume config)
- [ ] Stop returning “Extended trial by N days!” unless Stripe session actually got N
- [ ] Atomic coupon redeem: `find_one_and_update` with `redemptions < max` condition; call `increment_redemptions` when checkout completes (webhook `checkout.session.completed`) — not only validate
- [ ] Referral credit: apply **once** (first paid invoice / `billing_reason=subscription_create`) not every renewal
- [ ] Case-normalize coupon codes (always upper)

### 4.5 Webhooks & emails (B11, review Phase 7–9)

- [ ] Plan change: if new plan rank < old → `send_plan_downgraded`; else `send_plan_upgraded`
- [ ] Call downgrade email from `downgrade_handler` when profiles deactivated
- [ ] Verify Stripe signature on **all** webhook entrypoints
- [ ] Portal `return_url` / fallback from config (`APP_URL`), never localhost in prod
- [ ] Single support email constant (`support@openoutreach.ai` or env)

### 4.6 Feature-access correctness (B13)

- [ ] `planHierarchy`: map `lifetime` → same index as `pro` (not above Agency)
- [ ] Server-side `user_has_feature` for Pro features on mutating routes (voice notes, sales nav, etc.)

### 4.7 Minor billing hygiene (B14)

- [ ] Aware UTC datetimes everywhere
- [ ] Ensure `stripe.api_key` set at app startup
- [ ] Validate `billing_period in {monthly, annual}` on plan change request
- [ ] Fix usage stats filter consistency (`is_active` vs `status`)
- [ ] Referral link base URL from config
- [ ] Frontend: check limits before opening campaign / LinkedIn modals (UX; server still enforces)

### 4.8 Phase 4 tests

- [ ] Expired trial cannot claim tasks (daemon unit)
- [ ] Self-referral 400
- [ ] Coupon max_redemptions under concurrency
- [ ] Webhook plan downgrade sends correct email (mock)
- [ ] Deletion cancel restores or forces checkout as designed

---

## Phase 5 — Desktop & remote daemon reliability

**Goal:** Desktop is a thin client on residential IP; auth and billing work.  
**Depends on:** Phase 1 (JWT callback), Phase 4 (billing check)  
**Exit criteria:** Install → login → start → claim task without local Mongo requirement for profile/campaign payloads.

### 5.1 Auth & URL construction (D1, D4, D5)

- [ ] Desktop opens `{APP_URL}/login?desktop=true&callback=openoutreach://auth`
- [ ] Replace fragile `linkedin-api.` → `linkedin.` with explicit `DESKTOP_WEB_URL` / `NEXT_PUBLIC_APP_URL`
- [ ] Fix download CTA to real GitHub releases org/repo
- [ ] Rename notifications from “Lengrowth” → “OpenOutreach”

### 5.2 Remote client resilience (D3, D4)

**Files:** `core/remote_client.py`, `daemon_remote.py`, `desktop/app.py`

- [ ] Route **all** HTTP through `_request` with retry + 401 refresh
- [ ] Startup billing/status check: retry refresh once on 401 before crash
- [ ] On token refresh: update keychain **and** inject new token into running client (callback already partial — finish)
- [ ] Persist refresh failures to tray error state

### 5.3 Thin client architecture (D2) — **large**

- [ ] Daemon API returns task payload with everything needed to execute (campaign pitch, strategy, profile proxy fields, cookies) **or** dedicated `GET /daemon/profile/{id}` + `GET /daemon/campaign/{id}` authenticated endpoints
- [ ] Remove `LinkedInProfile.get` / `Campaign.get` local Mongo requirement from happy path
- [ ] Keep optional local cache only if explicitly configured
- [ ] `session.wait()` — implement or remove call sites

### 5.4 Config & health (D5, D6)

- [ ] Daemon config endpoint: `SiteConfig.load(user_id=...)`; real `cooldown_minutes`
- [ ] Desktop heartbeat / health: `POST /daemon/heartbeat` so web UI shows online/offline
- [ ] Update checker thread respects `_stopping`
- [ ] BrowserNotFoundError → tray message with install guidance

### 5.5 Phase 5 tests

- [ ] Mock 401 then refresh succeeds on claim
- [ ] Daemon starts refused when subscription expired
- [ ] No Mongo → still executes connect handler with API-provided campaign dict (integration)

---

## Phase 6 — Secondary surfaces (post-launch or parallel track)

**Goal:** Links, templates, ghost mode, email, state machine, admin UI — only after core green.  
**Depends on:** Phase 3–5 stable

### 6.1 Links

- [ ] Implement `api_v2/routers/links.py` or remove product
- [ ] Delete mock hourly/device charts; use real aggregates or omit
- [ ] Wire create form handlers

### 6.2 Campaign templates

- [ ] Implement CRUD + “create campaign from template”
- [ ] Or keep hidden

### 6.3 Ghost mode

- [ ] Implement API + handlers that skip LinkedIn side effects
- [ ] Or remove UI

### 6.4 Email channel

- [ ] Encrypt mailbox passwords at rest
- [ ] Add `TaskType.EMAIL` + planner + handler **or** document as manual-only
- [ ] Hide marketing claims until send works

### 6.5 State machine

- [ ] Align frontend paths with `api_v2/routers/state_machine.py`
- [ ] Replace stub engine; daemon integration
- [ ] Keep behind `NEXT_PUBLIC_ENABLE_STATE_MACHINE` until done

### 6.6 Admin UI

- [ ] Minimal Next.js admin: user search, block/unblock, plan override, finance summary
- [ ] Gate with `is_admin`

### 6.7 Cloud seats

- [ ] Enforce `cloud_profiles` in cloud daemon profile assignment

---

## Phase 7 — Hardening, GDPR, polish

**Goal:** Production ops quality.

- [ ] Cascade delete: maintain registry of user-scoped collections; test orphan scan
- [ ] Indexes: confirm `user_id` (+ campaign_id, lead_id) in `mongodb/indexes.py` for hot paths
- [ ] Finder API: exponential backoff on transient errors
- [ ] Remove production `console.log` noise from sensitive paths (or eslint rule)
- [ ] Webhook test matrix for all Stripe event types used
- [ ] Cookie refresh before task if session age > threshold (optional)
- [ ] Zero-division audit on all analytics percentage helpers
- [ ] Deal summary seller-identity cleanup job (optional batch)
- [ ] Update `CLAUDE.md` + `ARCHITECTURE.md` to match final auth/API/billing/desktop behavior
- [ ] Update `docs/BILLING_IMPLEMENTATION.md` checkboxes for cron, enforcement, referrals
- [ ] Update `docs/DESKTOP_APP.md` Phase 9 testing checklist

---

## Suggested calendar (aggressive)

| Week | Phase | Focus |
|------|-------|--------|
| 1 | 0 + 1 | Freeze surface, JWT-only auth, reset/verify |
| 2 | 2 | Settings + campaign contract + analytics enum |
| 3 | 3 | Funnel state machine + leads writes + cookies |
| 4 | 4 | Billing enforcement + crons + referrals/coupons |
| 5 | 5 | Desktop thin client + retry |
| 6+ | 6–7 | Secondary features + hardening |

---

## Definition of Done (whole plan)

A new user can:

1. Sign up (rate-limited) → verify email → checkout → trial active  
2. Log in on web (survives refresh) and desktop (protocol callback)  
3. Save LinkedIn credentials → verify → cookies stored → optional VNC with auth  
4. Configure LLM + rate limits in Settings (persisted per user)  
5. Create campaign with profile → start/pause actually controls daemon  
6. Discovery creates Discovered deals → LLM qualifies → connect → follow-up message  
7. Operator can change deal state and send a message from UI (task enqueued)  
8. Expired/blocked/deleted users cannot use API or run daemons  
9. No mock analytics on in-scope pages; no stub APIs in nav  
10. `make lint` + `make pyright` + remediation smoke tests green  

---

## Appendix A — Canonical API

### Auth
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| POST | `/api/auth/register/` | `{email, password, full_name}` | `UserResponse` | Rate limit: 3/IP/24h. Sets `email_verified=false`, sends verification email. Returns 201 on success. |
| POST | `/api/auth/login/` | `{email, password}` | `TokenResponse` | Returns access token + sets `refresh_token` HTTP-only cookie. Checks `is_active`, `status != blocked`, `!is_deleted`. |
| POST | `/api/auth/refresh/` | (cookie: `refresh_token`) | `TokenResponse` | Returns new access token. |
| GET | `/api/auth/me/` | Bearer token | `UserResponse` | Returns current user info. |
| POST | `/api/auth/verify-email/` | `{token}` | `{status, message}` | Verifies email, sets `email_verified=true`. |
| POST | `/api/auth/resend-verification/` | `{email}` | `{status, message}` | Resends verification email. Generic response to prevent enumeration. |
| POST | `/api/auth/password-reset/request/` | `{email}` | `{status, message}` | Sends password reset email. Generic response to prevent enumeration. |
| POST | `/api/auth/password-reset/confirm/` | `{token, new_password}` | `{status, message}` | Sets new password using reset token. |
| POST | `/api/auth/update-password/` | `{old_password, new_password}` | `{status, message}` | Authenticated endpoint to change password. |
| POST | `/api/auth/logout/` | Bearer token | `{status, message}` | Clears refresh token cookie. |
| POST | `/api/auth/account/request-deletion/` | Bearer token | Deletion schedule | Schedules account deletion (30-day grace). |
| POST | `/api/auth/account/cancel-deletion/` | Bearer token | Account status | Cancels scheduled deletion. |
| GET | `/api/auth/account/export-data/` | Bearer token | JSON export | GDPR data export. |

### Billing
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| GET | `/api/billing/status` | Bearer token | Billing status | Returns subscription status, plan, limits, trial info. |
| GET | `/api/billing/usage` | Bearer token | Usage stats | Returns current usage vs limits. |
| GET | `/api/billing/plans` | - | Plan list | Returns all available plans. |
| GET | `/api/billing/lifetime-deal-active` | - | `{active: bool}` | Checks if lifetime deal is active. |
| POST | `/api/billing/checkout` | `{plan, billing_period, referral_code?, coupon_code?}` | Checkout session | Creates Stripe checkout. Applies referral trial extension + coupon. |
| POST | `/api/billing/portal` | Bearer token | Portal session | Creates Stripe customer portal session. |
| POST | `/api/webhooks/stripe` | Stripe signature | - | Stripe webhook handler. |

### Campaigns / Leads / Settings / Daemon
_To be documented in Phase 2._

---

## Appendix B — Explicit non-goals (until Phase 6+)

- Rebuilding state machine editor UX  
- Full email sequencing product  
- White-label admin theming  
- Preserving Supabase compatibility  
- Preserving Django URL habits  

---

## Appendix C — File ownership map (quick)

| Concern | Primary files |
|---------|----------------|
| Auth FE | `authStoreV2.ts`, `apiClientV2.ts`, `app/layout.tsx`, `(auth)/*` |
| Auth BE | `api_v2/routers/auth.py`, `dependencies_v2.py` |
| Billing | `billing/*`, `api_v2/routers/billing.py`, `webhooks.py` |
| Settings | `api_v2/routers/settings.py`, `SiteConfig` |
| Funnel | `linkedin/db/leads.py`, `qualify.py`, `tasks/*`, `agents/follow_up.py` |
| Campaigns FE/BE | `campaigns.py`, `dashboard.ts`, `campaigns/**` |
| Desktop | `desktop/app.py`, `remote_client.py`, `daemon_remote.py` |

---

*Last updated: 2026-07-19*
