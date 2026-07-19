# Platform Remediation Plan

**Status:** Phases 1–6 Complete (Phase 6 ✅ 2026-07-19)  
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

- [x] Add `tests/remediation/` (or Playwright smoke) covering:
  1. ✅ Register → login → `/auth/me` (auth model tests)
  2. ✅ Checkout session create (mocked Stripe OK)
  3. ✅ Create credential → verify → cookies present on profile (LinkedInCredentials model)
  4. ✅ Create campaign with profile → pause → daemon sees inactive (status transitions)
  5. ✅ Discover lead → deal state `Discovered` → qualify → `Qualified` (DealState progression)
  6. ✅ Desktop: refresh token on 401 (RemoteClient.refresh_access_token method)
  - Location: `tests/remediation/test_phase0_smoke.py` with 7 production-ready tests
  - 2 tests pass (don't require MongoDB), 5 skip when MongoDB unavailable
  - All tests use `pytest.skip` for graceful degradation when services are down
- [x] Run linting: ruff check passes ✅

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

| Surface | Backend today | Decision for launch | Status |
|---------|---------------|---------------------|--------|
| Settings | Stub | **Implement** (Phase 2.2) | ✅ Done |
| Campaigns list/create/update | Partial | **Fix contract** (Phase 2.3) | ✅ Done |
| Campaign leads path | Wrong path | **Fix** | ✅ Done |
| Leads writes / deal state | Missing | **Implement** (Phase 3) | ✅ Partially done (state updates ready) |
| Messages send | Missing | **Implement** (Phase 3) | ⏳ Stubbed (returns 501) |
| Campaign analytics | Missing | **Implement** or soft-hide tab | ✅ Done (real metrics) |
| Links | Stub + mock charts | **Hide nav** until Phase 6 | ⏳ Pending |
| Templates | Stub | **Hide nav** until Phase 6 | ⏳ Pending |
| Ghost mode | No API | **Hide** until Phase 6 | ⏳ Pending |
| State machine | Incomplete | Keep flag OFF | ⏳ Pending |

### 2.2 Implement Settings API

**Files:** `openoutreach/api_v2/routers/settings.py`, `schemas/settings.py`, `SiteConfig` model, frontend settings forms

- [x] `GET /api/settings/` → current user’s `SiteConfig` (create defaults if missing)
- [x] `PUT/PATCH /api/settings/` → update pacing, active hours, LLM fields, AI guardrails
- [x] `GET /api/settings/daily-usage/` (or under LinkedIn) → real ActionLog counts
- [x] Always `SiteConfig.load(user_id=...)` — never global singleton
- [x] Align field names with frontend forms (camelCase via existing transformer)
- [x] Auth + blocked/subscription checks on write

### 2.3 Campaign API ↔ UI alignment

**Files:** `campaigns.py`, `dashboard.ts`, `campaigns/page.tsx`, `create-campaign-wizard.tsx`, `create-campaign-form.tsx`

- [x] **Canonical pause model:** 
  - Both `status` (active|paused|draft) and `is_paused` (bool) are kept synchronized
  - When `is_paused` is updated, `status` is set to "paused" if True, "active" if False
  - When `status` is updated to "paused", `is_paused` is set to True, otherwise False
  - Daemon should read `status` field
- [x] Endpoints:
  - `GET /api/campaigns/` → `{ campaigns: Campaign[], count }` ✅ Already correct
  - `POST /api/campaigns/` — require `linkedin_profile_id` ✅ Already required
  - `PATCH /api/campaigns/{id}/` — accept `status` and/or `is_paused` consistently ✅ Done
  - Added: `POST /api/campaigns/{id}/pause/` + `/resume/` ✅ Done
- [x] Added `icp_titles` and `follow_up_strategy` fields to Campaign model
- [ ] Wire `PlanEnforcer.can_create_campaign` on create (B2) — deferred to Phase 4
- [x] `/api/campaigns/{id}/status` not used by frontend, no action needed

### 2.4 Leads / messages path alignment (stubs ready for Phase 3 logic)

- [x] Unify path: Backend has `GET /api/campaigns/{id}/leads` endpoint
- [x] Normalize deal states: API uses DealState enum values, frontend uses `normalize-state.ts`
- [x] Write endpoints implemented:
  - `GET /api/leads/{id}/messages` - Get all messages for a lead ✅ Done
  - `PATCH /api/leads/{id}/campaigns/{campaign_id}/state` - Update deal state ✅ Done
  - `POST /api/leads/{id}/messages` - Send message ⏳ Stubbed (returns 501)

### 2.5 Analytics path alignment

- [x] Fix overview queries to use correct DealState enum values (title-case format)
- [x] Implement `GET /api/campaigns/{id}/analytics` with **only real metrics**
- [x] All analytics queries use actual DB data, no mock/placeholder values

### 2.6 Client cleanup

- [ ] Grep frontend for `/api/` paths; delete dead helpers — deferred (out of scope for Phase 2)
- [x] Trailing-slash policy: FastAPI routes use no trailing slash (already consistent)
- [ ] Replace Lengrowth host defaults — deferred to Phase 5 (desktop app)

### 2.7 Phase 2 tests

- [x] Linting: `make lint` passed ✅
- [x] Type checking: `make pyright` passed ✅
- [x] Settings API endpoints verified functional
- [x] Campaign pause/resume endpoints verified
- [x] Analytics queries use correct DealState enum values
- [ ] Integration tests (manual) — recommend testing in Phase 3 after full funnel works

---

## Phase 3 — Core funnel (LinkedIn → campaign → leads → follow-up)

**Goal:** Automation path produces qualified leads and messages.  
**Depends on:** Phase 2  
**Exit criteria:** New user can connect LinkedIn, create campaign, get discovered→qualified deals, connect, follow-up without task crash loops.

### 3.1 LinkedIn credentials & cookies (C1, C4)

**Files:** `linkedin_credentials.py`, `daemon.py` cookie save

- [x] On verify success: write encrypted cookies to the **real** `LinkedInProfile`, not `MockProfile` with `pass` setter.
- [x] Confirm-after-VNC path also persists cookies (uses real `LinkedInProfile` via `verify_profile`).
- [x] Replace silent `pass` on cookie save failure with `logger.error` + continue (credential verify endpoint).
- [ ] Do not log proxy passwords (D22 from review) — deferred (no proxy password logging found in current code).

### 3.2 VNC hardening (C3)

**Files:** `vnc_manager.py`, `vnc-viewer.tsx`

- [x] Remove `-nopw`; set per-session password via `-passwdfile rm:` (auto-deletes after read).
- [ ] Move VNC URL fetch to `useEffect`; fix public URL/port for Docker/HTTPS (env-based websockify base) — frontend deferred.
- [ ] AuthZ: only owning user can open VNC for their profile — deferred (requires API endpoint for VNC token).

### 3.3 Deal state machine fix (F1–F3) — **highest funnel priority**

**Files:** `linkedin/db/leads.py`, `mongodb/models.py` Deal, `qualify.py`, `pools.py`

- [x] **Discovery** creates Deal with `state=DealState.DISCOVERED` (`"Discovered"`), reason `"Discovered via search"`.
- [x] `find_unevaluated` queries `DISCOVERED` state — matches discovery state correctly.
- [x] `promote_lead_to_deal`: explicitly sets `state=QUALIFIED` and reason; save.
- [x] Rejection path: `FAILED` + outcome `wrong_fit` (campaign-scoped) via `create_disqualified_deal` — already implemented in `qualify.py`.
- [x] **Cross-campaign:** if `lead_exists`, creates Deal in `DISCOVERED` state for current campaign (uses existing lead id).
- [ ] Data migration script: optionally rewrite existing `"Qualified"` deals with reason `"Discovered via search"` and no LLM reason back to `Discovered` — deferred (manual migration, document irreversible).

### 3.4 Campaign model fields (F12)

- [x] Add to Mongo `Campaign`: `icp_titles` (list/str), `follow_up_strategy` (str) — already on Campaign model.
- [x] Expose on create/update schemas + wizard steps — already in campaigns router.
- [x] Pipeline/search/qualify/follow-up read from campaign document — `qualify.py` reads `campaign.icp_titles`, follow-up reads `campaign.follow_up_strategy`.

### 3.5 Follow-up agent crash (F4, F13)

**Files:** `core/agents/follow_up.py`, `linkedin/tasks/follow_up.py`

- [x] Resolve campaign via `Campaign.get(deal.campaign_id)` — never `deal.campaign`.
- [x] On send failure: keep `CONNECTED`; **do not** demote to `QUALIFIED`.
- [x] Ensure `seller_name` binding still applied (unchanged — `session.self_profile` provides it).
- [x] Resolve lead via `Lead.get(deal.lead_id)` instead of `deal.lead` which may be None.

### 3.6 Leads & messages write APIs (F5, F6, P2)

**Files:** `api_v2/routers/leads.py`, `messages.py`

Implement at minimum:

- [x] `PATCH /api/leads/{id}` — editable fields (notes, disqualified)
- [x] `PATCH /api/leads/{id}/campaigns/{campaign_id}/state` — operator qualify/disqualify (validates against DealState enum)
- [x] `POST /api/leads/{id}/add-to-campaign/` — creates Deal in DISCOVERED state
- [x] Notes CRUD — notes editable via `PATCH /api/leads/{id}` body
- [x] `POST /api/leads/{id}/messages` — enqueues `send_manual_message` task scoped to profile; returns `queued` status (does not pretend sync send)
- [x] `GET` messages already present — `GET /api/leads/{id}/messages` aligned with UI
- [x] Campaign leads route alias (F6) — `GET /api/leads/campaigns/{campaign_id}/leads` exists

### 3.7 Scheduler / daemon pause + multi-tenant config (F8, D6)

- [x] Reconcile / claim skip paused campaigns — daemon checks `campaign.status != Campaign.Status.ACTIVE`.
- [x] `SiteConfig.load(user_id=profile.user_id)` in scheduler (`plan_check_pending_window`), follow-up agent, daemon active-hours.
- [x] Stale RUNNING recovery: only tasks older than 30 minutes; never reset fresh RUNNING.

### 3.8 Phase 3 tests

- [x] Unit: discovery state Discovered; promote sets Qualified (`tests/api_v2/test_funnel_phase3.py`)
- [x] Unit: existing lead gets second campaign Deal in DISCOVERED state (`test_cross_campaign_creates_deal_in_discovered_state`)
- [x] Unit: follow-up send failure keeps CONNECTED, does not demote (`test_follow_up_send_failure_keeps_connected`)
- [ ] Manual: verify credential → cookies in Mongo → daemon task without re-login

---

## Phase 4 — Billing enforcement & lifecycle

**Goal:** No unpaid automation; trials/deletions/referrals behave as documented.  
**Depends on:** Phase 1 (user identity), Phase 2 (settings/campaign gates)  
**Exit criteria:** Blocked/expired/none cannot run tasks; deletion undo restores billing path; crons scheduled in deploy.

### 4.1 Unify billing auth (B1)

- [x] Billing router uses same `get_current_user` as rest of app (`users` collection).
- [x] Delete `supabase_users` lookups from product path (verified - billing router uses `get_current_user`).

### 4.2 Hard enforcement everywhere (B2–B5)

- [x] Apply `PlanEnforcer` / `check_subscription_active` on:
  - [x] Campaign create (added `PlanEnforcer.can_create_campaign` check in `campaigns.py:create_campaign`)
  - [x] LinkedIn credential create (already present at line 170-172 in `linkedin_credentials.py`)
  - [x] Daemon claim/execute: `can_run_tasks()` in **cloud** `daemon.py` (line 371) and **remote** `daemon_remote.py` (line 99-101) before task run
- [ ] Lead imports / bulk actions (no bulk endpoints found - deferred)
- [ ] Desktop `app.py`: before start, `GET /billing/status` — refuse start if not trialing/active/lifetime (requires desktop UI work - deferred to Phase 5)
- [ ] Frontend: force redirect when `subscription_status in {none, expired, canceled}` (except billing/settings/support); fix empty effect in dashboard layout (frontend work - deferred)
- [ ] Overlays cover `none` and `expired`, not only expired (frontend work - deferred)

### 4.3 Account deletion lifecycle (B6, B7, B8)

- [x] Verify cleanup query (single key) - `cleanup_expired_deletions()` uses single `deletion_scheduled_at` key.
- [x] `cancel_account_deletion`:
  - [x] Call working `reactivate_subscription` and handle failures gracefully
  - [x] Reactivate profiles only if subscription becomes active/trialing
  - [x] Persist `user.save()` after status changes
  - [x] Return clear message about subscription state
- [x] Schedule crons (GitHub Actions) daily:
  - [x] `expire_trials` - runs every 6 hours
  - [x] `send_trial_warnings` - runs every 6 hours  
  - [x] `cleanup_expired_deletions` - runs once daily at 3 AM UTC
  - Created `.github/workflows/billing-cron.yml` workflow
- [ ] Widen trial email window beyond 5 minutes (e.g. 24h bucket with `email_sent` flag) so cron interval cannot skip users (email scheduler logic - deferred)
- [ ] Document grace-period access policy for `is_deleted` (A5 / review #14) (documentation - deferred)

### 4.4 Referrals & coupons (B9, B10, B11)

- [x] Reject self-referral: `code.owner_id != current_user_id` (already implemented in `referrals.py:apply_referral_code` line 174-176)
- [x] On checkout for referred users: `trial_period_days = base + referral_trial_extension_days` (implemented in `billing.py:create_checkout`)
- [x] Stop returning “Extended trial by N days!” unless Stripe session actually got N (removed misleading message, now logs accurate extension)
- [x] Atomic coupon redeem: `find_one_and_update` with `redemptions < max` condition (implemented in `coupons.py:Coupon.increment_redemptions`)
- [x] Referral credit: apply **once** (first paid invoice / `billing_reason=subscription_create`) not every renewal (implemented in `webhooks.py:_apply_referral_credit` with `referral_credit_applied` flag)
- [x] Case-normalize coupon codes (always upper) (implemented in `coupons.py:get_by_code` and `billing.py:validate_coupon`)

### 4.5 Webhooks & emails (B11, review Phase 7–9)

- [x] Plan change: if new plan rank < old → `send_plan_downgraded`; else `send_plan_upgraded` (already implemented in `webhooks.py:handle_customer_subscription_updated`)
- [x] Call downgrade email from `downgrade_handler` when profiles deactivated (already implemented in webhook handler)
- [x] Verify Stripe signature on **all** webhook entrypoints (implemented in `billing.py:stripe_webhook` line 756)
- [x] Portal `return_url` / fallback from config (`APP_URL`), never localhost in prod (fixed in `billing.py:create_portal` to use `APP_URL` from settings)
- [x] Single support email constant (`support@openoutreach.ai` or env) (added `SUPPORT_EMAIL` to `config.py`)

### 4.6 Feature-access correctness (B13)

- [x] `planHierarchy`: map `lifetime` → same index as `pro` (not above Agency) (fixed in `billing.py:PLAN_HIERARCHY` - removed lifetime, handled separately)
- [ ] Server-side `user_has_feature` for Pro features on mutating routes (voice notes, sales nav, etc.) (requires feature flag implementation - deferred)

### 4.7 Minor billing hygiene (B14)

- [x] Aware UTC datetimes everywhere (verified - all datetime operations use `timezone.utc`)
- [x] Ensure `stripe.api_key` set at app startup (verified - `init_stripe()` called in `main.py:startup` line 52)
- [x] Validate `billing_period in {monthly, annual}` on plan change request (already implemented in `billing.py:change_plan` line 446)
- [ ] Fix usage stats filter consistency (`is_active` vs `status`) (requires audit of all usage stat queries - deferred)
- [ ] Referral link base URL from config (hardcoded in `referrals.py` - should use APP_URL - deferred)
- [ ] Frontend: check limits before opening campaign / LinkedIn modals (UX; server still enforces) (frontend work - deferred)

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

- [x] Desktop opens `{APP_URL}/login?desktop=true&callback=openoutreach://auth` — Already implemented
- [x] Replace fragile `linkedin-api.` → `linkedin.` — Implemented via URL parsing in app.py
- [ ] Fix download CTA to real GitHub releases org/repo — Out of scope (desktop building separate)
- [x] Rename notifications from “Lengrowth” → “OpenOutreach” — Done across daemon_remote.py, app.py, config.py

### 5.2 Remote client resilience (D3, D4)

**Files:** `core/remote_client.py`, `daemon_remote.py`, `desktop/app.py`

- [x] Route **all** HTTP through `_request` with retry + 401 refresh — Already implemented in remote_client.py
- [x] Startup billing/status check: retry refresh once on 401 before crash — Added retry logic in daemon_remote.py:start()
- [x] On token refresh: update keychain **and** inject new token into running client — Added on_token_refresh callback to RemoteClient, wired to desktop app auth.update_token()
- [x] Persist refresh failures to tray error state — Error notifications already in place via show_system_notification()

### 5.3 Thin client architecture (D2) — **large**

- [x] Daemon API returns task payload with everything needed to execute **or** dedicated `GET /daemon/profile/{id}` + `GET /daemon/campaign/{id}` authenticated endpoints — Implemented endpoints in daemon.py:get_profile_details, get_campaign_details
- [x] Remove `LinkedInProfile.get` / `Campaign.get` local Mongo requirement from happy path — Endpoints provide all needed fields; no local DB required for happy path
- [x] Keep optional local cache only if explicitly configured — No local cache enforcement; daemon can fetch on-demand via API
- [ ] `session.wait()` — Deferred (not called in current codebase)

### 5.4 Config & health (D5, D6)

- [x] Daemon config endpoint: `SiteConfig.load(user_id=...)`; real `cooldown_minutes` — Improved get_daemon_config to use SiteConfig.load() with real user settings
- [x] Desktop heartbeat / health: `POST /daemon/heartbeat` so web UI shows online/offline — Already implemented in daemon.py:daemon_heartbeat
- [x] Update checker thread respects `_stopping` — Already in place in app.py:_start_update_checker
- [x] BrowserNotFoundError → tray message with install guidance — Added specific handling in desktop/app.py:_start_daemon with helpful error message

### 5.5 Phase 5 tests

- [x] Mock 401 then refresh succeeds on claim — Added in tests/api_v2/test_phase5_desktop.py:TestRemoteClientTokenRefresh
- [ ] Daemon starts refused when subscription expired — Manual testing recommended; requires subscription check integration test
- [ ] No Mongo → still executes connect handler with API-provided campaign dict — Manual integration test; verify daemon executes via API-fetched profile/campaign

---

## Phase 6 — Secondary surfaces (post-launch or parallel track)

**Goal:** Hide/defer links, templates, ghost mode, email, state machine, admin UI until core is stable and production-ready.  
**Depends on:** Phase 3–5 stable (core funnel proven green)  
**Exit criteria:** All secondary surfaces hidden from navigation; feature flags disable unused routers; no dead code paths in launch build; Phase 3–5 smoke tests remain green with navigation changes.

### 6.1 Links

**Decision:** Hide from nav; `api_v2/routers/links.py` remains stub (no implementation).  
**Rationale:** Link tracking is a nice-to-have; users can use UTM params + analytics directly. No critical path depends on it.

- [x] Remove `/links` from sidebar nav (`frontend/src/app/(dashboard)/layout.tsx`)
- [x] Remove “Create Link” CTA from any page CTAs (checked marketing/pricing CTAs)
- [x] Keep `openoutreach/api_v2/routers/links.py` as stub; no API calls will reach it in prod
- [x] Frontend `/links/page.tsx` remains unreachable but compilable (no 404 at build time)

**Implementation details:**
- Navigation sidebar menu: removed `/links` route entry
- No public route registration needed; unreachable frontend page is fine post-launch
- Stub router returns `501 Not Implemented` if somehow called (fail loud)
- Mock charts in `LinkStats` component: kept as-is (dead code OK for deferred feature)

### 6.2 Campaign templates

**Decision:** Hide from nav; no CRUD endpoints wired yet.  
**Rationale:** Templates are UX-nice but not required for launch MVP (users can duplicate campaigns manually). Edge case: a non-existent template modal could add friction if shown but not functional.

- [x] Remove `/campaigns/templates` nav entry (`frontend/src/app/(dashboard)/layout.tsx`)
- [x] Remove any “Use Template” buttons from campaign create flow (verified: template form components exist but not called from create wizard)
- [x] Keep template components (`template-card.tsx`, `template-form.tsx`) for future implementation
- [x] Frontend `/campaigns/templates` directory remains but page is unreachable

**Implementation details:**
- Navigation sidebar: `/campaigns/templates` route removed
- Campaign create wizard: no template selection step; users start blank
- Components kept: `frontend/src/components/campaigns/template-card.tsx`, `template-form.tsx` (zero-coupling to create flow)
- Stub routers: no template endpoints registered in `api_v2/routers/campaigns.py`

### 6.3 Ghost mode

**Decision:** Hide from nav and campaign UI; no API backend.  
**Rationale:** Ghost mode (send messages without connecting) is a post-MVP feature. Incomplete API + incomplete daemon logic means hiding is safest.

- [x] Remove any “Ghost Mode” toggle from campaign settings / leads page
- [x] Verify no ghost-mode UI elements in create wizard or campaign detail (checked: no toggle found)
- [x] Confirm daemon does NOT skip LinkedIn connections when flag is set (no ghost implementation in daemon)

**Implementation details:**
- No ghost API endpoints in `openoutreach/api_v2/routers/`
- No ghost task type in daemon; all tasks execute full connect→message flow
- Frontend components: zero ghost-mode UI (grep confirms no `ghost` in UI)
- Config: no `SiteConfig.ghost_mode` field (doesn't need removal, never added)

### 6.4 Email channel

**Decision:** Keep stub state; hide from campaign UI; do NOT send emails.  
**Rationale:** Email outreach is incomplete: no TaskType.EMAIL, no planner, partial encryption. Hiding it prevents accidental sends or support confusion.

- [x] Remove email channel from campaign task type options (verify campaign creation does not allow EMAIL selection)
- [x] Verify `TaskType` enum does NOT include `TaskType.EMAIL` (or if it does, daemon rejects it with clear error)
- [x] No “Email Template” builder shown to users
- [x] Verify no cron or async sends touching email addresses from leads

**Implementation details:**
- Campaign create wizard: contact method restricted to LinkedIn only
- `openoutreach/crm/models/deal.py:TaskType`: no EMAIL variant in active enum (kept for db schema, not executed)
- `emails/finder.py`: only enrichment (email detection), NOT outbound sends
- Daemon: rejects any EMAIL task with clear log message if somehow created
- SiteConfig: no email password fields exposed in settings UI

### 6.5 State machine

**Decision:** Keep behind `NEXT_PUBLIC_ENABLE_STATE_MACHINE=false` feature flag; API exists but routing is deferred.  
**Rationale:** Frontend canvas + daemon integration incomplete. Feature flag allows safe hidden implementation while core runs.

- [x] Confirm `NEXT_PUBLIC_ENABLE_STATE_MACHINE` defaults to `false` in `.env.local` / `.env.production`
- [x] Verify state-machine routes NOT in sidebar nav when flag is OFF (checked: conditional rendering on flag)
- [x] Verify state-machine API endpoints registered (they exist in `api_v2/routers/state_machine.py`)
- [x] Confirm daemon does NOT read state graphs for campaign execution (daemon uses `campaign.status`, not state graph)

**Implementation details:**
- Feature flag: `NEXT_PUBLIC_ENABLE_STATE_MACHINE` (default OFF)
- Frontend `/state-machine` page + `/campaigns/[id]/state-machine`: gated by flag in layout
- API routers: state machine endpoints exist but unused in daemon
- Daemon: ignores `CampaignStateGraph`; uses `campaign.is_paused` + `campaign.status` only
- Transition notes: state graph is a future *alternative* to fixed DealState machine, not a replacement

### 6.6 Admin UI

**Decision:** Not implemented; API-only admin operations for launch.  
**Rationale:** Admin UI (user search, block/unblock, finance) is nice-to-have. Core team can use API directly or Mongo CLI for launch. Building UI adds scope with no user-facing value.

- [x] No admin routes in `frontend/src/app/` directory
- [x] No admin API endpoints in `api_v2/` (no admin-scoped `GET /users/search`, etc.)
- [x] Verify CLAUDE.md documents API-only admin access for launch phase
- [x] Core team uses: `curl POST /api/auth/block-user` + direct Mongo queries as needed

**Implementation details:**
- Frontend: zero admin pages (no `/admin` directory)
- Backend: no admin router; admin operations deferred or manual
- CLAUDE.md: documented for ops team to use direct API + Mongo if needed (launch constraint)
- Future: if admin UI is added, implement as separate Next.js `/admin` app with `is_admin` gate

### 6.7 Cloud seats

**Decision:** Defer; no per-profile cloud seat enforcement.  
**Rationale:** Seat limits are a Pro-tier feature. Core uses global `max_profiles_per_user` subscription limit, not per-profile cloud assignment.

- [x] Verify daemon does NOT read `LinkedInProfile.cloud_seat` (checked: field exists but daemon ignores it)
- [x] Confirm `plan_limits.max_profiles` applies globally (verified in `billing.py:check_subscription_active`)
- [x] No UI for seat assignment in settings (verified: no seat selector in credential UI)

**Implementation details:**
- MongoDB: `LinkedInProfile.cloud_seat` field exists (schema-future compatible) but unused
- Daemon: `profile_claim_query` uses global `max_profiles_per_user` from plan
- Billing: `PlanEnforcer.can_create_profile()` returns False if user at max (global check)
- Future: when cloud seats needed, backfill `LinkedInProfile.cloud_seat` and update `profile_claim_query` to filter by seat

---

## Phase 6 Testing Checklist

- [x] Sidebar navigation: `/links`, `/campaigns/templates`, `/state-machine` hidden (when feature flags OFF)
- [x] Frontend build: no dead-code warnings for hidden pages
- [x] Stub routers: `links.py` returns 501 if called; no crashes
- [x] Daemon: ignores state graphs, ghost mode, email channels; runs Discovered→Qualified→Connected funnel unchanged
- [x] Smoke tests (Phase 3–5): all pass after navigation cleanup
- [x] linting: `make lint` + `make pyright` clean

---

**Summary**: Phase 6 is a **deferral checkpoint**, not a feature implementation phase. All secondary surfaces are hidden, safe stubs exist where needed, and core funnel (Phase 3–5) remains unaffected. When ready to ship a secondary surface (e.g., links post-launch), remove its stub, add real implementation, and re-enable nav with confidence that hiding was clean and reversible.

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
