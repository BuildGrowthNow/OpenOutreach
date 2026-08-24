# Billing, Pricing & Admin Implementation Plan

## Pricing Structure (Finalized)

| Tier | Monthly | Annual (17% off) | LinkedIn Accounts | Campaigns | Key Features |
|------|---------|-------------------|-------------------|-----------|--------------|
| Starter | $19/mo | $16/mo | 1 | 3 | AI messages, automated follow-ups, unified inbox, analytics, local desktop execution |
| Pro | $49/mo | $41/mo | 1 | Unlimited | Everything in Starter + voice notes, AI follow-ups, Sales Navigator, API access |
| Business | $99/mo | $82/mo | 3 | Unlimited | Everything in Pro + team member invites, workspace management, priority support |
| Agency | $249/mo | $207/mo | 10 (+$20/ea extra) | Unlimited | Everything in Business + white-label branding, custom domain, unlimited team members |

**Cloud add-on**: +$39/profile/month (not displayed on public site initially, available on request or as upsell inside app)

**Free trial**: 3 days, credit card required, full Pro access, 1 LinkedIn account

**Lifetime deals** (launch promotion, 30 days): $149 one-time for Pro-equivalent forever

## Core Rules

- 1 LinkedIn account is unique globally - cannot be connected to multiple user accounts
- Plan limits enforced server-side (hard block, not soft warnings)
- Downgrade: excess LinkedIn profiles deactivated (user chooses which to keep)
- Trial expiry: immediate block, no grace period (already got 3 free days)
- Admin is a platform-level role, separate from workspace team roles
- Both login paths (web app + desktop app) funnel into the same subscription - one account, one plan
- Cloud add-on is internal/upsell only - not on public pricing page at launch
- No free tier - trial is the only free path, then you pay or lose access
- Lifetime deals are time-limited (30 days from launch), non-refundable, and give Pro-equivalent forever

---

## Phase 1: Foundation - Models, Stripe Setup, Admin Role

**Goal**: Database models for plans/subscriptions, Stripe product/price setup, admin user distinction.

### 1.1 Stripe Dynamic Product Sync
- [x] Define all plans in code as a single source of truth (`billing/plans.py`):
  - All 6 plan tiers (starter/pro/business/agency/cloud_addon/lifetime) defined with prices, limits, features
  - `get_plan()`, `get_all_plans()`, `get_plan_by_display_name()` utility functions
- [x] `sync_stripe_products()` function: creates/updates Stripe products and prices idempotently
  - Matches products and prices by plan_name metadata
  - Creates cloud_addon as metered subscription, lifetime as one-time price
  - Stores Stripe IDs in MongoDB `StripePlan` collection
- [x] CLI command: `openoutreach sync-stripe` to sync all plans to Stripe
- [x] Set up Stripe webhook endpoint signing secret in env (STRIPE_SECRET_KEY, STRIPE_PUBLISHABLE_KEY, STRIPE_WEBHOOK_SECRET)
- [x] `stripe_service.py`: all Stripe API interactions (product sync, checkout, portal, webhooks)

### 1.2 MongoDB Models
- [x] `StripePlan` model: stores Stripe product/price IDs for each plan
  - plan_name, stripe_product_id, monthly_price_id, annual_price_id
  - `get_by_plan()` lookup, `save()` for updates
- [x] `SiteConfig` model: global billing configuration
  - trial_duration_days, lifetime_deal_enabled, lifetime_deal_ends_at
  - `load()` for singleton access with in-memory caching
- [x] `Subscription` fields on User model:
  - stripe_customer_id, stripe_subscription_id
  - plan (starter/pro/business/agency/lifetime), billing_period, subscription_status
  - trial_ends_at, current_period_end, linkedin_account_limit, campaign_limit, cloud_profiles
  - is_admin, admin_role, status (active/blocked)
- [x] User model `to_dict()` and `from_dict()` updated to include all billing fields
- [x] Default values: plan=starter, status=active, subscription_status=none

### 1.3 Environment/Config
- [x] Added to config.py: `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`
- [x] Added to config.py: `TRIAL_DURATION_DAYS`, `LIFETIME_DEAL_ENABLED`, `LIFETIME_DEAL_ENDS_AT`
- [x] Added `stripe>=10.0.0` to requirements/fastapi.txt
- [x] `billing/config.py`: configuration loader with in-memory caching
  - `get_site_config()` for singleton access
  - `load_from_env()` to sync config from environment variables
  - `is_lifetime_deal_active()` helper to check deal status

### 1.4 Admin User Seeding & Auth
- [x] CLI command: `openoutreach create-admin --email <email> --role <role>` to promote users to admin
- [x] FastAPI dependencies: `get_admin_user()`, `check_subscription_active()`, `check_linkedin_account_limit()`, `check_campaign_limit()`
- [x] Plan enforcement via `billing/enforcement.py`:
  - `PlanEnforcer.can_create_linkedin_account()`, `.can_create_campaign()`, `.can_run_tasks()`
  - `PlanEnforcer.has_feature()` for feature gates
  - `PlanEnforcer.get_usage_stats()` for user quota information

### 1.5 MongoDB Indexes & API Foundation
- [x] Added indexes for billing collections:
  - `stripe_plans`: plan_name (unique)
  - `site_config`: _id (unique)
- [x] FastAPI Billing Router (`api_v2/routers/billing.py`):
  - `GET /api/billing/plans` - list all available plans
  - `GET /api/billing/lifetime-deal-active` - check if lifetime deal active
  - `GET /api/billing/status` - current user's billing status
  - `GET /api/billing/usage` - current usage vs limits
  - `POST /api/billing/checkout` - create Stripe checkout session
  - `POST /api/billing/portal` - create Stripe customer portal session
- [x] App initialization: Stripe setup on startup, config loading from environment

---

## Phase 2: Stripe Integration - Checkout, Webhooks, Portal

**Goal**: Users can subscribe, Stripe events update our DB, users manage billing via portal.

### 2.1 Checkout Flow
- [x] `POST /api/billing/checkout` - creates Stripe Checkout Session:
  - Input: `plan_name`, `billing_period` (monthly/annual/lifetime)
  - Looks up correct Stripe price ID from `StripePlan` collection (dynamic, never hardcoded)
  - Sets `trial_period_days: 3` for new users (requires card)
  - Sets `customer_email` from authenticated user
  - Creates Stripe Customer if not exists, stores `stripe_customer_id`
  - Returns `checkout_url` for redirect
  - `success_url` → `/settings/billing?success=true`
  - `cancel_url` → `/settings/billing?canceled=true`
- [x] `POST /api/billing/portal` - creates Stripe Customer Portal Session:
  - Returns portal URL for managing subscription (cancel, switch plan, update card)
- [x] `GET /api/billing/status` - returns current plan, status, limits, period end, trial info
- [x] `GET /api/billing/invoices` - returns list of recent invoices with details

### 2.2 Webhook Handler
- [x] `POST /api/billing/webhooks/stripe` - verify signature, handle events:
  - [x] `checkout.session.completed` → activate subscription, set plan fields, handle lifetime deals
  - [x] `customer.subscription.created` → set subscription status, sync plan limits
  - [x] `customer.subscription.updated` → update plan/status/period_end, enforce account limits on downgrade
  - [x] `customer.subscription.deleted` → set status=canceled, deactivate all profiles
  - [x] `invoice.payment_succeeded` → update current_period_end
  - [x] `invoice.payment_failed` → set status=past_due
  - [ ] `customer.subscription.trial_will_end` → (optional) send email 1 day before
- [x] Idempotent processing (track processed event IDs in MongoDB to prevent duplicates)
- [x] Webhook retry handling (events are safely re-processed if duplicated)

### 2.3 Plan Change Logic
- [x] `POST /api/billing/plan-change` - change subscription plan:
  - [x] Upgrade: immediate (prorated via Stripe with `proration_behavior: create_prorations`)
  - [x] Downgrade: at end of current period (Stripe `proration_behavior: none`)
  - [x] On downgrade activation: if user has more LinkedIn accounts than new limit, deactivate excess (mark `is_active=False` on LinkedInProfile, oldest first)
  - [x] Validates plan exists and billing_period is valid
  - [x] Syncs plan limits from plan definition to user on change
- [x] Lifetime deal: one-time checkout, no subscription - set `plan=lifetime`, `billing_period=lifetime`, no `current_period_end`

### 2.4 Cloud Add-on
- [x] `POST /api/billing/cloud-addon` - update cloud profile seats count:
  - Input: `quantity` (integer >= 0)
  - Updates `user.cloud_profiles` field
  - Returns updated cloud_profiles count
- [x] Track `cloud_profiles` count on user
- [ ] Enforce in daemon profile assignment (Phase 11)

---

## Phase 3: Plan Enforcement - Limits & Blocks

**Goal**: Server-side enforcement of plan limits across all operations.

### 3.1 LinkedIn Account Uniqueness
- [x] Unique index on `LinkedInProfile.linkedin_username` (globally unique)
- [x] On credential create/verify: check if LinkedIn account is already connected to another user
  - If yes: reject with clear error "This LinkedIn account is already connected to another OpenOutreach account"
- [x] On account deletion: release the LinkedIn username lock

### 3.2 Plan Limit Middleware
- [x] FastAPI dependency `enforce_plan_limits` that checks:
  - Subscription status is `active` or `trialing` (else block all automation)
  - LinkedIn account count vs `linkedin_account_limit`
  - Campaign count vs `campaign_limit`
- [x] Apply to relevant endpoints:
  - `POST /api/linkedin-credentials` → check LinkedIn account limit
  - `POST /api/campaigns` → check campaign limit
  - Task creation endpoints → check subscription active

### 3.3 Feature Gating
- [x] `user_has_feature(user, feature_name)` utility function
- [x] Gates per plan:
  - `ai_messages`: all plans (Starter+)
  - `voice_notes`: Pro+
  - `ai_follow_ups`: Pro+
  - `sales_navigator`: Pro+
  - `api_access`: Pro+
  - `team_members`: Business+
  - `white_label`: Agency
  - `custom_domain`: Agency
- [x] Return 403 with `upgrade_required` payload when feature not available

### 3.4 Trial Expiry
- [x] Cron/scheduler job: check users where `trial_ends_at < now()` and `subscription_status == 'trialing'`
- [x] On expiry without conversion: set `subscription_status = 'expired'`
- [x] Expired users: block all automation, show upgrade banner, allow read-only access to data

### 3.5 Blocked Users
- [x] Admin can set `user.status = 'blocked'`
- [x] Blocked users: cannot login, API returns 403, daemon stops their profiles

---

## Phase 4: User-Facing Pages - Billing & Plan Management

**Goal**: Settings pages for users to view/manage their subscription.

### 4.1 Billing Settings Tab (`/settings/billing`)
- [x] Current plan card: plan name, price, billing period, next renewal date
- [x] Plan status badge: Active / Trialing (X days left) / Past Due / Canceled
- [x] "Manage Subscription" button → Stripe Customer Portal (update card, cancel)
- [x] Payment history section (fetch from Stripe API: last 10 invoices with status, amount, date, PDF link)
- [x] "Change Plan" button → opens plan comparison modal or redirects to upgrade page

### 4.2 Plan/Upgrade Page (`/settings/plan`)
- [x] Plan comparison cards (same as pricing page but in-app)
- [x] Current plan highlighted
- [x] Upgrade/downgrade buttons with confirmation:
  - Upgrade: "You'll be charged the prorated difference immediately"
  - Downgrade: "Your plan will change at the end of your billing period on [date]"
- [x] Cloud add-on toggle with quantity selector
- [x] Annual/monthly toggle with savings callout

### 4.3 Usage Indicators
- [x] In sidebar or settings: "1/1 LinkedIn accounts used", "2/3 campaigns used"
- [x] Warning state when at limit (amber)
- [x] Block state with upgrade CTA when over limit

### 4.4 Trial Banner
- [x] Global banner (top of app) during trial: "Your trial ends in X days. [Choose a plan]"
- [x] Last day urgency: "Your trial ends today. Add a plan to keep your campaigns running."
- [x] Post-expiry: full-page overlay "Your trial has ended. Choose a plan to continue."

---

## Phase 5: Admin Panel

**Goal**: Platform admins can manage users, view finance, approve/block accounts.

### 5.1 Admin Routes & Auth
- [x] `GET /api/admin/users` - paginated user list with filters (status, plan, search)
- [x] `GET /api/admin/users/:id` - full user detail (plan, subscription, LinkedIn profiles, campaigns, activity)
- [x] `PATCH /api/admin/users/:id` - update status (block/unblock), update plan override, add notes
- [x] `GET /api/admin/finance` - revenue dashboard data (MRR, churn, trial conversions)
- [x] `GET /api/admin/finance/invoices` - all platform invoices (Stripe API aggregate)
- [x] Admin auth: middleware checks `user.is_admin` + `admin_role` permissions

### 5.2 Admin Frontend Pages
- [ ] `/admin` - dashboard: active users, MRR, trials expiring soon, recent signups
- [ ] `/admin/users` - user table: name, email, plan, status, signup date, last active, actions
- [ ] `/admin/users/:id` - user detail: subscription info, LinkedIn profiles, campaigns, logs, action buttons
- [ ] `/admin/finance` - revenue metrics: MRR, ARR, churn rate, LTV, trial→paid conversion rate
- [ ] `/admin/finance/invoices` - invoice list with status, filterable

### 5.3 Admin Actions
- [x] Block user: sets status=blocked, stops daemon, returns 403 on next API call
- [x] Unblock user: sets status=active, resumes normal operation
- [x] Force plan change: admin can override user's plan (e.g., gift an upgrade, handle disputes)
- [ ] Approve user: (if approval flow needed later)
- [x] Add internal notes to user record
- [ ] Impersonate user: admin can view app as user (read-only, for support)

### 5.4 Admin Notifications
- [ ] Slack/email alert on: new signup, trial expiry without conversion, payment failure, user approaching limits
- [ ] Daily digest: new users, revenue, churn events

---

## Phase 6: Public Marketing Pages - Pricing, Terms, Privacy

**Goal**: Public-facing pages for the marketing site.

### 6.1 Pricing Page (`/pricing`)
- [x] Monthly/Annual toggle (annual shows per-month price with "save 17%" badge)
- [x] 4 tier cards: Starter, Pro, Business, Agency
- [x] Feature comparison table (expandable)
- [x] "Start free trial" CTA on each card → sign up → checkout
- [x] FAQ section: trial details, what happens after trial, can I switch plans, refund policy
- [x] Enterprise/custom section: "Need more? Contact us"

### 6.2 Terms of Service (`/terms`)
- [x] Acceptance of terms
- [x] Service description
- [x] User obligations (LinkedIn TOS compliance, no spam, no fake accounts)
- [x] Payment terms (auto-renewal, cancellation, refunds - none after 14 days)
- [x] Limitation of liability (LinkedIn account restrictions are user's risk)
- [x] Termination (we can terminate for abuse, user can cancel anytime)
- [x] Data handling (reference privacy policy)
- [x] Intellectual property
- [x] Governing law

### 6.3 Privacy Policy (`/privacy`)
- [x] What data we collect (LinkedIn credentials encrypted at rest, profile data, campaign data, usage analytics)
- [x] How data is used (provide service, improve product, never sold)
- [x] Data storage (MongoDB Atlas, encrypted, region)
- [x] Third parties (Stripe for payments, LLM providers for AI messages)
- [x] User rights (export data, delete account, GDPR if applicable)
- [x] Cookie policy
- [x] Data retention (deleted on account closure, 30-day grace period)
- [x] Security measures

### 6.4 Lifetime Deal Page (temporary, launch only)
- [x] `/lifetime` or modal on pricing page
- [x] Countdown timer (30 days from launch)
- [x] Limited quantity indicator
- [x] What's included (Pro-equivalent forever)
- [x] One-time payment CTA → Stripe Checkout

---

## Phase 7: Stripe Emails & Notifications

**Goal**: Automated emails for billing lifecycle events.

### 7.1 Stripe-Managed Emails (configure in Stripe Dashboard)
- [x] Payment receipt (on successful charge) - via Stripe dashboard configuration
- [x] Payment failed (retry warning) - via Stripe dashboard configuration
- [x] Subscription canceled confirmation - via Stripe dashboard configuration
- [x] Upcoming renewal reminder (3 days before) - via Stripe dashboard configuration

### 7.2 App-Managed Emails (via SendGrid/Resend/SES)
- [x] Welcome email on signup (with trial info, getting started guide)
- [x] Trial ending soon (1 day before expiry): "Your trial ends tomorrow - choose a plan"
- [x] Trial expired: "Your trial has ended. Your campaigns are paused."
- [x] Plan upgraded: confirmation + new limits
- [x] Plan downgraded: effective date + what changes
- [x] Account blocked by admin: reason + appeal instructions
- [x] Lifetime deal purchase: thank you + what's included

### 7.3 Email Infrastructure
- [x] Choose provider: Resend (simple, cheap) or SES (if scale needed) - Resend + SMTP + SES backends implemented
- [x] Transactional email templates (HTML + plain text) - 7 email templates with full HTML + text
- [x] Unsubscribe handling for marketing emails (required by law) - managed by email provider (Resend/SES)
- [x] Email sending utility in `openoutreach/billing/emails.py` - complete email service with pluggable providers

---

## Phase 8: Profile Activation & Security

**Goal**: Ensure plan integrity can't be bypassed.

### 8.1 LinkedIn Profile Activation Control
- [x] `LinkedInProfile.is_active` field (boolean, default True)
- [x] Daemon only runs profiles where `is_active=True` AND user subscription is active
- [x] On plan downgrade below current count: prompt user to choose which profiles to deactivate
- [x] On subscription cancel/expire: all profiles set `is_active=False`, daemon stops

### 8.2 Anti-Abuse
- [x] Rate limit on account creation (IP-based, 3 accounts per IP per day)
- [x] LinkedIn uniqueness enforcement (Phase 3.1) prevents multi-account abuse
- [x] Email verification required before trial starts (prevent throwaway signups)
- [x] Stripe radar for card fraud detection (built-in)
- [x] Webhook signature verification (prevent fake events)

### 8.3 API Security
- [x] All billing endpoints require authenticated user
- [x] Admin endpoints require `is_admin=True`
- [x] Plan enforcement cannot be bypassed by direct API calls
- [x] Webhook endpoint validates Stripe signature, rejects otherwise
- [x] No plan data in JWT (always fetch fresh from DB to prevent stale tokens)

### 8.4 Data Isolation
- [x] Users cannot access other users' data (existing multi-tenant auth)
- [x] Admin impersonation is read-only (no write actions as another user)
- [x] Stripe customer IDs are private (never exposed in API responses to non-owner)

---

## Phase 9: Banners, Blocks & UX Polish

**Goal**: Clear communication to users about their plan state.

### 9.1 In-App Banners
- [x] Trial banner (global, dismissible daily): countdown + CTA
- [x] Past-due banner (global, non-dismissible): "Payment failed. Update your card to avoid service interruption."
- [x] Approaching limit banner (contextual): "You've used 3/3 campaigns. Upgrade for unlimited."
- [x] Feature-locked state: grayed out UI + tooltip "Available on Pro plan" + upgrade link

### 9.2 Blocking Overlays
- [x] Trial expired: full-page overlay, only billing settings accessible
- [x] Account blocked: full-page overlay with reason + support contact
- [x] Subscription canceled: full-page overlay after current_period_end, read-only data access for 30 days

### 9.3 Contextual Upgrade Prompts
- [x] "Create Campaign" button shows limit if at max
- [x] "Connect LinkedIn" shows limit if at max
- [x] Feature buttons (voice notes, API) show "Pro" badge if locked
- [x] Smooth in-app upgrade flow (comparison → Stripe Checkout → return)

---

## Phase 10: Account Lifecycle & Data

**Goal**: Handle the full user lifecycle - signup, trial, subscription, cancellation, deletion.

### 10.1 Signup Flow Changes
- [x] Signup creates user with `status=active`, `subscription_status=none`
- [x] After signup, redirect to plan selection / checkout (credit card required)
- [x] On checkout complete: set `subscription_status=trialing`, `trial_ends_at=now+3days`
- [x] User cannot access dashboard until checkout is complete (force billing page)
- [x] Desktop app login: same flow - after auth callback, check if subscription exists, redirect to billing if not

### 10.2 Account Deletion
- [x] User can request account deletion from settings
- [x] Deletion process: cancel Stripe subscription → deactivate all profiles → 30-day soft delete → permanent delete
- [x] During 30-day window: user can reactivate by logging in + subscribing
- [x] Permanent delete: remove all user data, LinkedIn credentials, campaigns, leads (GDPR compliance)
- [x] Release LinkedIn username lock on permanent delete

### 10.3 Subscription Recovery
- [x] Past-due: 3 retry attempts by Stripe (days 1, 3, 5)
- [x] After all retries fail: cancel subscription, block account
- [x] "Reactivate" flow: user goes to billing → redirected to new checkout
- [x] Preserve all data on reactivation (campaigns, leads, analytics)

### 10.4 Plan Migration (for existing users at launch)
- [x] Existing users (pre-billing) get grandfathered into Pro plan free until they're notified
- [x] Or: existing users get a 30-day window to choose a plan before enforcement kicks in
- [x] Migration script to set `subscription_status=active` and plan for grandfathered users
- [x] Email notification to existing users about new billing (2 weeks before enforcement)

---

## Phase 11: Desktop App Billing Integration

**Goal**: Desktop app respects plan limits and subscription status.

### 11.1 Desktop Daemon Plan Checks
- [x] Remote daemon checks subscription status on startup and every config refresh cycle
- [x] If subscription expired/canceled: daemon stops gracefully with user notification
- [x] If trial ended: daemon stops, shows system tray notification "Trial ended - subscribe to continue"
- [x] If user blocked by admin: daemon stops, shows reason

### 11.2 Desktop App Plan UI
- [x] System tray tooltip shows current plan and status
- [x] Menu item "Manage Subscription" → opens browser to `/settings/billing`
- [x] Notification when trial is ending (1 day before)
- [x] Notification on payment failure

### 11.3 Desktop vs Web Licensing
- [x] Both desktop and web use same account/subscription
- [x] Desktop execution is included in all plans (it's the default/safe mode)
- [x] Cloud execution is the add-on (web-triggered, uses our infrastructure)
- [x] A user can run desktop AND have cloud profiles simultaneously (different LinkedIn accounts)

---

## Phase 12: Referral & Promotional System (Post-Launch)

**Goal**: Growth mechanics for marketing campaigns.

### 12.1 Referral Program
- [x] Each user gets a unique referral code/link (auto-generated on first request)
- [x] Referred user: extended trial (4 days configurable in SiteConfig)
- [x] Referrer: $19 credit ($19-49 depending on plan) on referred user's first payment
- [x] Track referral chain in DB (referrer_id on User model)
- [x] Referral dashboard in settings (link, count, credits earned) via API

### 12.2 Coupon System
- [x] Admin can create Stripe coupons (% off or $ off, duration) via CLI
- [x] Coupon field on checkout page (optional coupon_code parameter)
- [x] Coupon validation API endpoint
- [x] Stripe coupon integration (automatic creation and tracking in MongoDB)

### 12.3 Usage-Based Upgrade Nudges
- [x] Track referral credits earned when referred user makes first payment
- [x] Coupon tracking with usage limits and expiration dates

---

## Implementation Order & Dependencies

```
Phase 1  (Foundation)            → Week 1-2
Phase 2  (Stripe Integration)    → Week 2-3   [depends on Phase 1]
Phase 3  (Plan Enforcement)      → Week 3-4   [depends on Phase 1]
Phase 6  (Marketing Pages)       → Week 3-4   [independent, can parallel]
Phase 4  (User Pages)            → Week 4-5   [depends on Phase 2]
Phase 5  (Admin Panel)           → Week 5-6   [depends on Phase 1]
Phase 7  (Emails)                → Week 6     [depends on Phase 2]
Phase 8  (Security)              → Week 6-7   [depends on Phase 3]
Phase 9  (UX Polish)             → Week 7-8   [depends on Phase 4]
Phase 10 (Account Lifecycle)     → Week 7-8   [depends on Phase 2, 3]
Phase 11 (Desktop Integration)   → Week 8-9   [depends on Phase 3, 10]
Phase 12 (Referrals/Promos)      → Post-launch [depends on Phase 2]
```

**Launch checklist** (before going live):
- [ ] Stripe test mode fully working (checkout, webhooks, portal)
- [ ] Switch to Stripe live keys
- [ ] Terms and Privacy pages live
- [ ] Pricing page live
- [ ] Lifetime deal page ready
- [ ] Admin user created for platform owner
- [ ] Email templates tested
- [ ] Webhook endpoint accessible from Stripe (public URL)
- [ ] LinkedIn uniqueness index deployed
- [ ] Trial flow tested end-to-end (signup → trial → expiry → block → subscribe → unblock)
- [ ] Desktop app checks subscription on startup (no bypass)
- [ ] Existing users migration plan communicated
- [ ] Cookie/session invalidation works on block/cancel
- [ ] Stripe Customer Portal configured (cancel, plan change, card update)
- [ ] Legal review of Terms and Privacy (even if brief)
- [ ] GDPR: data export and deletion flows work
- [ ] Rate limiting on signup/checkout endpoints (anti-abuse)
- [ ] Monitoring/alerting on webhook failures

---

## Edge Cases & Gotchas (Don't Forget)

### Billing Edge Cases
- [ ] What if Stripe webhook is delayed? (user completes checkout but webhook hasn't fired yet) → Poll Stripe on `/billing/status` as fallback
- [ ] What if user creates account but never completes checkout? → Cleanup job: delete users with no subscription after 24h
- [ ] What if user's card is stolen/disputed? (Stripe chargeback) → Auto-block account, admin notified
- [ ] What if user subscribes, immediately cancels, and re-subscribes within same period? → Stripe handles this, just track status
- [ ] Currency handling → USD only at launch, Stripe handles conversion for non-US cards
- [ ] Tax/VAT → Enable Stripe Tax (automatic collection based on location) or defer to post-launch
- [ ] What if admin force-changes plan mid-billing? → Use Stripe subscription update API, not just DB

### LinkedIn Uniqueness Edge Cases
- [ ] User A connects LinkedIn, then deletes account → LinkedIn released, User B can now use it
- [ ] User changes LinkedIn username → Match on persistent LinkedIn member ID, not vanity URL
- [ ] User tries to connect same LinkedIn that's on their other account → Clear error with instructions to delete from other account first

### Desktop App Edge Cases
- [ ] Desktop app running while subscription expires → Daemon must check on every cycle, not just startup
- [ ] Desktop app offline when subscription changes → On reconnect, re-validate subscription immediately
- [ ] User uninstalls desktop app → No server-side action needed, subscription continues

### Multi-Seat (Business/Agency) Edge Cases
- [ ] Team member invited → What plan do they inherit? → They use the workspace owner's plan, no separate subscription
- [ ] Workspace owner downgrades → Team members beyond new limit get read-only access
- [ ] Team member leaves → Their campaigns/leads stay in workspace

### Migration Edge Cases
- [ ] User already has 5 LinkedIn profiles connected (pre-billing) → Grandfathered until they acknowledge, then must choose which to keep
- [ ] Active campaigns on profiles that get deactivated → Campaigns paused, tasks stop being created

---

## Technical Notes

### Stripe Product/Price Management
```
# No hardcoded price IDs - everything is dynamic:
# 1. Plans defined in billing/plans.py (source of truth)
# 2. sync_stripe_products() creates/updates products+prices on Stripe
# 3. Resulting Stripe IDs stored in MongoDB StripePlan collection
# 4. Checkout/portal code reads IDs from DB at runtime
#
# To change a price: update billing/plans.py → run sync → new price created, old archived
# To add a plan: add to PLANS list → run sync → product+prices auto-created
#
# Only env vars needed:
STRIPE_SECRET_KEY=sk_xxx
STRIPE_PUBLISHABLE_KEY=pk_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx
```

### File Structure (new files)
```
openoutreach/
  billing/
    __init__.py
    models.py          # Plan definitions, subscription helpers
    stripe_service.py  # Stripe API calls (checkout, portal, customer)
    webhooks.py        # Webhook event handlers
    enforcement.py     # Plan limit checks, feature gates
    email.py           # Transactional email sending
  api_v2/routers/
    billing.py         # User billing endpoints
    admin.py           # Admin panel endpoints
    webhooks.py        # Stripe webhook receiver

frontend/src/
  app/(dashboard)/settings/billing/page.tsx
  app/(dashboard)/settings/plan/page.tsx
  app/(dashboard)/admin/page.tsx
  app/(dashboard)/admin/users/page.tsx
  app/(dashboard)/admin/finance/page.tsx
  app/(marketing)/pricing/page.tsx
  app/(marketing)/terms/page.tsx
  app/(marketing)/privacy/page.tsx
  components/billing/
    plan-card.tsx
    trial-banner.tsx
    usage-indicator.tsx
    upgrade-modal.tsx
    billing-status.tsx
  components/admin/
    user-table.tsx
    finance-dashboard.tsx
    user-detail.tsx
  lib/api/billing.ts   # Billing API client
  lib/api/admin.ts     # Admin API client
```

### Key Dependencies
- `stripe` (Python SDK) - backend
- No new frontend deps needed (use existing shadcn/ui components)
- Email: `resend` Python SDK (or `boto3` for SES)
