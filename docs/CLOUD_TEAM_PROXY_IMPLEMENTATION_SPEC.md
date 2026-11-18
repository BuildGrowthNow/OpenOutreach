# Cloud, Teams, Seats & Managed Proxies — Implementation Specification

Status: implementation companion to `CLOUD_TEAM_PROXY_ROLLOUT_PLAN.md`  
Audience: product, backend, frontend, desktop, admin, QA, support  
Last updated: 2026-11-18

Read this together with:

1. `AGENTS.md` — production rules, Scalingo, no secrets.
2. `CLAUDE.md` / `ARCHITECTURE.md` — existing architecture.
3. `docs/CLOUD_TEAM_PROXY_ROLLOUT_PLAN.md` — phase strategy and decisions.
4. This document — page map, API surface, payment/billing, onboarding, team,
   desktop/cloud, admin, migrations, analytics, ops, acceptance criteria.

If a detail conflicts with the rollout plan, the rollout plan’s phase gate wins; raise the
conflict before coding.

---

## 1. Product surfaces map

### 1.1 Marketing site

| Page | Purpose | Key content | Phase |
|---|---|---|---|
| `/` | Positioning | Desktop vs Cloud, team, managed proxy | 0–4 |
| `/pricing` | Plans | Seat definitions, Cloud Solo/Duo, team, FAQ | 0–4 |
| `/cloud` (new) | Cloud landing | Managed browser + proxy + AI, region, security | 1 |
| `/teams` (new) | Team landing | Invite members, desktop seats, cloud seats | 3 |
| `/security` (new) | Trust | Encryption, proxy isolation, SOC2/GDPR | 2 |
| `/integrations/massive` (optional) | Trust | Massive network, 195+ countries | 2 |
| `/signup` | Registration | `?plan=cloud`, `?plan=team`, `?plan=desktop` | 0 |
| `/login` | Login | Redirect to intended onboarding step | 0 |
| `/verify-email` | Verification | Then checkout/onboarding | 0 |
| `/terms`, `/privacy` | Legal | Fair use, subprocessors, data retention | 0–4 |
| `/lifetime` | Lifetime deal | Exclude Cloud/team seats | 0 |

Marketing rules:

- Never advertise a feature before its phase ships.
- Never show a GB allowance or overage rate.
- Cloud copy: “flat monthly seat, managed proxy included, fair use.”
- Team copy: “desktop seats included; cloud seats per browser account.”
- FAQ must answer: desktop vs cloud, proxy, region, seats, team, WhatsApp, email,
  cancellation, fair use, data retention.
- Every CTA carries the intended plan/seat parameter.
- Add analytics events to every CTA and form.

### 1.2 Dashboard (cloud app)

| Page | Purpose | Phase |
|---|---|---|
| `/dashboard` | Overview + onboarding checklist | 0 |
| `/settings/billing` | Plan, seats, invoices, payment method | 0 |
| `/settings/plan` | Plan/seat purchase and change | 0 |
| `/settings/linkedin` | LinkedIn accounts, execution mode, region, proxy status | 0 |
| `/settings/whatsapp` | WhatsApp numbers, execution mode, region, QR | 3–4 |
| `/settings/email` | Mailboxes, BYO SMTP/IMAP, seat slot | 0–4 |
| `/settings/team` (new) | Members, invites, roles, seat assignment | 3 |
| `/settings/seats` (new) | Cloud/desktop seat pool and assignments | 3 |
| `/settings/desktop` | Desktop device enrollment/revocation | 0–3 |
| `/settings/security` | Password, sessions, devices | 0 |
| `/campaigns` | Campaigns (existing) | 0 |
| `/leads`, `/inbox`, `/analytics` | Existing | 0 |
| `/onboarding` (new) | Guided setup state machine | 0 |

Dashboard rules:

- Cloud execution card visible when `plan === "cloud"` **or** `cloud_profiles > 0`.
- Region is required for cloud accounts; country first, city/state optional.
- Managed proxy credentials are never shown to the client.
- BYO proxy form only when the workspace is allowed BYO.
- Customer-facing usage is health/status only; no GB meter.
- Seat usage is visible: “2 of 3 cloud seats assigned.”
- Every empty state has a primary action and a help link.

### 1.3 Admin

| Page | Purpose | Phase |
|---|---|---|
| `/admin` | Dashboard | 0 |
| `/admin/users` | Users | 0 |
| `/admin/users/[id]` | User detail, plan, seats, proxies, audit | 0 |
| `/admin/organizations` (new) | Org list | 3 |
| `/admin/organizations/[id]` (new) | Org detail, members, seats, profiles, proxies | 3 |
| `/admin/proxies` (new) | Inventory, assignments, health, usage, Massive | 0–2 |
| `/admin/seats` (new) | Seat pool and assignment | 3 |
| `/admin/finance` | Revenue, invoices | 0 |
| `/admin/audit` | Audit log | 0 |
| `/admin/platform` | Daemon health | 0 |
| `/admin/reconciliation` (new) | Stripe ↔ Mongo drift, proxy usage | 2–3 |

Admin rules:

- Admin-only middleware on every route and API.
- Passwords/secrets masked; never returned in list responses.
- Every mutation writes an audit event.
- Impersonation is audited and time-limited.
- Bulk actions show a preview and a count before applying.
- Destructive actions require typed confirmation.

### 1.4 Desktop app

| Surface | Purpose | Phase |
|---|---|---|
| Login WebView | Existing login | 0 |
| Tray | Start/stop daemon, show/hide, quit | 0 |
| Desktop connection tab | Enroll LinkedIn/WhatsApp/mailbox | 0 |
| Workspace context (new) | Org switcher, seat type | 3 |
| Assigned profiles (new) | Desktop profiles only | 3 |
| Device list/revocation (new) | Per org | 3 |
| Update prompt | Version gate | 0–3 |

Desktop rules:

- Desktop profiles never receive proxy credentials.
- Desktop accounts show “Local IP · No proxy.”
- Cloud accounts are read-only in the desktop app.
- The desktop daemon claims only enrolled desktop profiles.
- One profile cannot run desktop and cloud simultaneously.
- Device revocation invalidates refresh families.

### 1.5 Emails and notifications

| Event | Email | In-app | Phase |
|---|---|---|---|
| Signup | Verify email | — | 0 |
| Email verified | Welcome + next step | Onboarding checklist | 0 |
| Checkout abandoned | Reminder | Banner | 0 |
| Cloud activated | Welcome + add account | Checklist | 0 |
| Seat purchased | Receipt + assignment link | Toast | 0 |
| Team invite | Invite link | Notification | 3 |
| Member joined | Owner notification | Notification | 3 |
| Proxy assigned | — | Account card status | 1 |
| Proxy test failed | Admin alert | Account card warning | 1 |
| Payment failed | Dunning email | Billing banner | 0 |
| Trial ending | Reminder | Banner | 0 |
| Fair-use review | Customer notice (if needed) | Banner | 2 |
| Desktop download | Download link | Settings page | 0 |

All emails must use the existing email provider abstraction and redact secrets.

---

## 2. Payment and billing specification

### 2.1 Plans and seats

| Plan | Price | LinkedIn | WhatsApp | Cloud seats | Desktop seats | Team members |
|---|---:|---:|---:|---:|---:|---|
| Starter | $19/mo | 1 | 1 | 0 | 1 | 1 |
| Pro | $49/mo | 1 | 1 | 0 | 1 | 1 |
| Business | $99/mo | 3 | 3 | 0 | 3 | 3 |
| Agency | $249/mo | 10 | 10 | 0 | 10 | 10 |
| Cloud | $299/mo | 1 + seats | 1 + seats | 1 included | 0 | 3 included |
| Cloud add-on | $299/mo per seat | — | — | +1 | — | — |
| Lifetime | $149 once | 1 | 1 | 0 | 1 | 1 |

Decisions still open:

- Team member limit per plan.
- Extra team member price ($29/mo recommended).
- Whether Business/Agency include desktop seats or only team logins.
- Whether Cloud Duo is $299 shared or $349–399 separate.

### 2.2 Checkout flows

**A. New Cloud buyer**

1. `/pricing` → `/signup?plan=cloud`.
2. Register; store `intended_plan=cloud` on the user.
3. Verify email.
4. Login → `/settings/plan?plan=cloud`.
5. Create Stripe Checkout session for the Cloud monthly price.
6. No Starter trial for Cloud intent.
7. `checkout.session.completed` → set plan, status, limits, cloud seat.
8. Redirect to `/onboarding?plan=cloud`.

**B. Existing desktop user upgrading**

1. `/settings/plan` → select Cloud.
2. If `stripe_subscription_id` exists → `plan-change` with proration.
3. Else → Checkout session.
4. Webhook syncs plan + seats.
5. Show “Cloud activated” and the add-account CTA.

**C. Buying an extra cloud seat**

1. `/settings/billing` → “Add cloud seat.”
2. `POST /api/billing/cloud-addon` with `quantity`.
3. Stripe subscription item create/modify with proration.
4. Webhook and/or response sync `cloud_profiles`.
5. `linkedin_account_limit` for Cloud plan = `1 + cloud_profiles`.
6. Show seat pool and assignment CTA.

**D. Removing a seat**

1. Select seat → “Remove.”
2. Warn: assigned profile pauses, proxy disables, data retained.
3. Remove at period end by default; immediate only with admin override.
4. Stripe subscription item decrement.
5. Webhook syncs; enforcement pauses profiles over the limit.

**E. Team invite**

1. Owner buys plan/seats.
2. `/settings/team` → invite email.
3. Invite token (hashed, expires 7 days).
4. Accept → create/login user → join org.
5. No checkout for the invited member.
6. Owner assigns seats/profiles.

### 2.3 Trial policy

- Starter trial only; 7 days by default.
- No Cloud trial.
- Cloud checkout requires email verification.
- A Cloud-intent user who abandons checkout may fall back to a Starter trial only if the
  product explicitly allows it; default is no trial.
- Trial users cannot create cloud profiles.

### 2.4 Proration and changes

- Upgrades: immediate, prorated.
- Downgrades: at period end.
- Seat additions: immediate, prorated.
- Seat removals: period end; profiles pause then.
- Annual plans: Cloud is monthly only.
- Currency: USD; tax via Stripe Tax.
- Coupons: apply to first invoice; define whether they apply to add-on seats.
- Referral credits: apply to invoice; never negative balance.

### 2.5 Invoices, tax, refunds

- Invoices from Stripe; list + PDF in `/settings/billing`.
- Billing email from Stripe; app notification for failures.
- Tax: Stripe Tax; store tax IDs.
- Refunds: admin-only; audit; no automatic refunds.
- Chargebacks: admin workflow; suspend cloud profiles.

### 2.6 Failed payments and dunning

- Stripe smart retries.
- `invoice.payment_failed` → email + banner.
- Grace period: 3 days for Cloud.
- After grace: pause cloud profiles, disable proxies, keep data.
- Reactivation: re-enable profiles/proxies after payment.

### 2.7 Webhooks and reconciliation

Required events:

- `checkout.session.completed`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.paid`
- `invoice.payment_failed`
- `customer.subscription.trial_will_end`

Rules:

- Parse **all** subscription items, not just `items[0]`.
- Identify base plan and add-on quantity by Stripe price ID/metadata.
- Never treat `cloud_addon` as a plan.
- Sync `cloud_profiles` from the add-on item quantity.
- Set `linkedin_account_limit` for Cloud = `1 + cloud_profiles`.
- Store `stripe_subscription_id`, `current_period_end`, `billing_period`.
- Reconciliation job compares Stripe items to Mongo entitlements; reports drift.
- Admin override writes an audit event and a reconciliation note.

### 2.8 Metadata

Stripe customer metadata:

```text
user_id
org_id
```

Subscription metadata:

```text
plan_name
seat_type
```

Price metadata:

```text
plan_name
billing_period
seat_type
```

### 2.9 Admin billing overrides

- Set plan, `cloud_profiles`, `linkedin_account_limit`, `whatsapp_account_limit`.
- Reason required; audit event.
- Do not silently diverge from Stripe; reconciliation flags it.
- Impersonation cannot change billing without admin role.

---

## 3. Onboarding state machine

### 3.1 Cloud buyer

```text
signup(plan=cloud)
  -> verify_email
  -> login
  -> checkout_cloud
  -> cloud_activated
  -> create_workspace
  -> add_linkedin
  -> choose_region
  -> assign_proxy
  -> test_proxy
  -> verify_linkedin
  -> add_whatsapp (optional)
  -> add_email (optional)
  -> first_campaign
  -> invite_team (optional)
```

States and UI:

| State | UI | Failure/empty |
|---|---|---|
| `signup` | Form, plan badge | Validation errors |
| `verify_email` | Check email | Resend |
| `checkout_cloud` | Stripe redirect | Cancel → retry |
| `cloud_activated` | Success + CTA | Webhook delay → poll |
| `create_workspace` | Name + country | Default name |
| `add_linkedin` | Email/password, execution=cloud | Duplicate account |
| `choose_region` | Country required, state/city optional | No nodes → country fallback |
| `assign_proxy` | “Provisioning…” | No proxy → support CTA |
| `test_proxy` | Egress IP/country/latency | 407/521 → retry/support |
| `verify_linkedin` | VNC if challenge | Challenge timeout |
| `add_whatsapp` | QR, region | QR expired |
| `add_email` | SMTP/IMAP | Auth failure |
| `first_campaign` | Campaign wizard | No profile → back |
| `invite_team` | Email invites | Seat limit |

### 3.2 Desktop buyer

```text
signup
  -> verify_email
  -> starter_trial
  -> download_desktop
  -> login_desktop
  -> enroll_device
  -> add_linkedin/whatsapp/email
  -> run_daemon
  -> first_campaign
```

### 3.3 Team owner

```text
cloud_or_business_plan
  -> create_workspace
  -> buy_seats
  -> invite_members
  -> assign_seats
  -> members_accept
  -> members_add_accounts
```

### 3.4 Invited member

```text
invite_email
  -> accept
  -> create_or_login
  -> join_org
  -> see_assigned_seats
  -> desktop_enroll or cloud_access
```

### 3.5 Onboarding emails

- Welcome.
- “Finish your Cloud setup.”
- “Your proxy is ready.”
- “Your LinkedIn account needs verification.”
- “Invite your team.”
- “Your desktop is ready.”
- “Payment failed.”
- “Trial ending.”

### 3.6 Analytics events

See §10.

---

## 4. Team and permissions

### 4.1 Organization model

- Every user gets a personal org on first login (migration).
- An org owns billing, seats, members, proxies, and shared campaigns.
- `User.org_id` points to the active org.
- A user can belong to multiple orgs (future); MVP one active org.

### 4.2 Roles matrix

| Capability | Owner | Admin | Member | Platform admin |
|---|---|---|---|---|
| View billing | ✅ | ✅ | — | ✅ |
| Change plan/seats | ✅ | — | — | ✅ |
| Invite/remove members | ✅ | ✅ | — | ✅ |
| Assign seats | ✅ | ✅ | — | ✅ |
| Manage proxies | ✅ | ✅ | — | ✅ |
| Create/edit profiles | ✅ | ✅ | ✅ assigned | ✅ |
| Create/edit campaigns | ✅ | ✅ | ✅ assigned | ✅ |
| View all org data | ✅ | ✅ | — | ✅ |
| Delete org | ✅ | — | — | ✅ |
| Impersonate | — | — | — | ✅ audited |

### 4.3 Invites

- Email + role.
- Token hashed in DB; expires 7 days.
- One active invite per email/org.
- Accept: existing user joins; new user registers and joins.
- Resend/revoke.
- Audit: invited, accepted, revoked.

### 4.4 Seat assignment

- Cloud seat = one browser account + email slot.
- Desktop seat = one device/channel binding + email slot.
- Owner/admin assigns a seat to a profile/member.
- A seat cannot be assigned twice.
- Unassign pauses the profile; proxy is disabled/retired per policy.
- Transfer requires unassign + assign; never reuse a used proxy across LinkedIn accounts.

### 4.5 Member removal

- Revoke org access.
- Revoke desktop devices.
- Reassign cloud seats.
- Pause profiles owned by the member if no seat.
- Keep data for retention period.
- Audit.

### 4.6 Agency/client workspaces

MVP: one org with members and roles.
Future: client sub-workspaces with separate visibility, billing allocation, and branding.
Do not mix unrelated clients in one workspace if they can see each other’s data.

---

## 5. Desktop × Cloud execution

### 5.1 Matrix

| Channel | Desktop | Cloud |
|---|---|---|
| LinkedIn | Local browser, local IP, no proxy | Server browser, managed proxy |
| WhatsApp | Local browser, local IP, no proxy | Server browser, managed proxy (to build) |
| Email | SMTP/IMAP via desktop daemon grant | SMTP/IMAP from server, no proxy |

### 5.2 Rules

- One channel account has one execution mode.
- Cloud requires a seat + proxy.
- Desktop requires a desktop seat/enrollment.
- Switching cloud → desktop: clear proxy, warn IP change, re-enroll device.
- Switching desktop → cloud: assign seat/proxy, revoke desktop binding for that profile.
- The cloud daemon selects only `execution_mode="cloud"`.
- The desktop daemon selects only enrolled desktop profiles.
- Desktop bootstrap returns `proxy_server: None` for desktop profiles.
- Desktop accounts show “Local IP · No proxy.”
- Cloud accounts show “Managed · region · health.”
- One profile cannot run in both modes simultaneously.

### 5.3 Enrollment

- Owner/admin creates a one-time code for org-owned desktop profiles.
- Member redeems code in the desktop app.
- Code binds device to profile IDs and channels.
- Code expires 10 minutes; one use.
- Device revocation invalidates refresh families.
- Enrollment endpoint authorizes org membership, not just `user_id`.

### 5.4 Version gating

- API returns `force_update` below the minimum secure desktop version.
- Desktop app prompts update; blocks daemon start if too old.
- Release notes + staged rollout.

---

## 6. Admin specification

### 6.1 Proxy inventory page

Tabs:

1. **Inventory** — all proxies.
2. **Assignments** — active/historical.
3. **Health** — test results, country mismatch, failures.
4. **Usage** — per proxy/channel/seat.
5. **Massive** — connection, parent usage, sub-accounts.

Inventory columns:

```text
label, provider, endpoint, country, city, type, status,
assigned to (org/profile/channel), usage, last test, actions
```

Actions:

```text
test, assign, unassign, disable, enable, retire, rotate password, delete
```

Filters:

```text
provider, country, status, assigned/unassigned, identity, org
```

### 6.2 Bulk import UX

1. Paste text or upload CSV/TSV.
2. Choose/auto-detect format.
3. Preview parsed rows with masked passwords.
4. Show per-line errors and duplicates.
5. Choose defaults: provider, type, country, region mode.
6. Import; report created/skipped/failed.
7. Optional: test imported proxies asynchronously.

Formats:

```text
host:port:user:pass
host:port:user:pass:country
user:pass@host:port
http://user:pass@host:port
socks5://user:pass@host:port
```

CSV/TSV header:

```csv
label,host,port,username,password,country,subdivision,city,type,provider
```

Validation:

- scheme in `http|https|socks5`
- host non-empty
- port 1–65535
- username/password non-empty for auth proxies
- country ISO-2
- type in `residential|isp|mobile|manual`
- dedupe by `(host, port, username)`
- passwords with `:`/`@` require CSV/TSV or URL-encoding.

### 6.3 Assignment rules

- One active proxy per profile.
- A proxy may serve multiple channels only within one `identity_id`.
- At most one LinkedIn account per proxy.
- No cross-tenant/cross-identity assignment.
- Retire on profile deletion.
- Never recycle a used proxy to a different LinkedIn account.

### 6.4 Massive tab

- Connection status: Reseller key, Reporting key, parent username.
- Parent plan usage.
- Sub-account table: username, status, assigned profile, used/limit, limit_reached,
  proxy_access, last sync.
- Actions: sync, provision for profile, disable, enable, rotate.
- Alerts: limit reached, proxy access revoked, country mismatch.

### 6.5 Org/seat admin

- Org detail: plan, seats, members, profiles, proxies, usage, billing.
- Override seat count/plan with reason + audit.
- Reassign seats/proxies.
- Impersonate owner (audited).
- Suspend org.

### 6.6 Audit events

```text
proxy.import, proxy.test, proxy.assign, proxy.unassign,
proxy.disable, proxy.enable, proxy.retire, proxy.rotate,
seat.purchase, seat.assign, seat.unassign, seat.remove,
org.invite, org.accept, org.remove, org.role_change,
billing.override, reconciliation.fix, impersonate.start
```

Never log passwords, keys, or raw import text.

### 6.7 Support runbook

- “No proxy available for region” → check Pool Stats, add inventory, or use country fallback.
- “407” → wrong credentials, re-enter/rotate.
- “521” → region too narrow, switch to country.
- “Country mismatch” → test, replace proxy, check targeting.
- “Seat limit reached” → buy seat or unassign.
- “Desktop enrollment fails” → code expired, device revoked, version old.
- “Member can’t see profile” → seat assignment/role.
- “Payment failed” → dunning, grace period, reactivate.

---

## 7. API surface

### 7.1 Billing

```text
GET  /api/billing/plans
GET  /api/billing/status
GET  /api/billing/usage
POST /api/billing/checkout
POST /api/billing/plan-change
POST /api/billing/cloud-addon
POST /api/billing/portal
GET  /api/billing/invoices
POST /api/billing/cancel-subscription
POST /api/billing/reactivate-subscription
```

### 7.2 Organizations / team / seats

```text
GET  /api/organizations/current
POST /api/organizations
PATCH /api/organizations/{id}
GET  /api/organizations/{id}/members
POST /api/organizations/{id}/invites
DELETE /api/organizations/{id}/invites/{invite_id}
POST /api/organizations/invites/{token}/accept
PATCH /api/organizations/{id}/members/{user_id}
GET  /api/organizations/{id}/seats
POST /api/organizations/{id}/seats/assign
POST /api/organizations/{id}/seats/unassign
```

### 7.3 Proxies (user)

```text
GET  /api/linkedin-profiles/{id}/proxy
PUT  /api/linkedin-profiles/{id}/proxy
POST /api/linkedin-profiles/{id}/proxy/test
```

### 7.4 Proxies (admin)

```text
GET  /api/admin/proxies
POST /api/admin/proxies/parse
POST /api/admin/proxies/import
POST /api/admin/proxies/{id}/test
POST /api/admin/proxies/{id}/assign
POST /api/admin/proxies/{id}/unassign
POST /api/admin/proxies/{id}/disable
POST /api/admin/proxies/{id}/enable
POST /api/admin/proxies/{id}/retire
POST /api/admin/proxies/{id}/rotate
POST /api/admin/proxies/sync-massive
GET  /api/admin/proxies/usage
```

### 7.5 Channels

```text
POST /api/linkedin-credentials   (add region fields)
POST /api/whatsapp/profiles      (add execution_mode/region)
POST /api/mailboxes              (add org/seat fields)
```

### 7.6 Daemon

```text
POST /api/daemon/v2/enrollment-codes
POST /api/daemon/v2/devices/enroll
GET  /api/daemon/v2/devices
DELETE /api/daemon/v2/devices/{device_id}
GET  /api/daemon/v2/claim
POST /api/daemon/v2/result
```

### 7.7 Admin

```text
GET/PATCH /api/admin/users/{id}
GET/PATCH /api/admin/users/{id}/linkedin-profiles
GET/PATCH /api/admin/organizations/{id}
GET/PATCH /api/admin/organizations/{id}/seats
POST /api/admin/billing/reconcile
GET /api/admin/audit-logs
```

All admin routes require `get_admin_user`; all mutations write audit events.

---

## 8. Data model and migrations

### 8.1 New collections

- `proxies`
- `proxy_assignments`
- `proxy_health_checks`
- `client_identities`
- `organizations`
- `organization_members`
- `organization_invites`
- `seat_assignments`
- `usage_snapshots`

### 8.2 New fields

`users`:

```text
org_id, org_role, intended_plan, onboarding_state
```

`linkedin_profiles`:

```text
org_id, identity_id, proxy_id, proxy_mode,
proxy_region_country, proxy_region_subdivision, proxy_region_city,
proxy_session_id
```

`whatsapp_profiles`:

```text
org_id, identity_id, execution_mode, proxy_id, proxy_mode,
proxy_region_country, proxy_region_subdivision, proxy_region_city,
proxy_session_id
```

`mailboxes`:

```text
org_id, seat_id, managed
```

### 8.3 Indexes

```text
proxies: (status), (assigned_org_id), (identity_id), (massive_account_id)
proxy_assignments: (proxy_id, unassigned_at), (profile_id, unassigned_at)
organizations: (owner_user_id)
organization_members: (org_id, user_id), (email)
organization_invites: (token_hash), (org_id, email)
linkedin_profiles: (org_id), (proxy_id), (identity_id)
whatsapp_profiles: (org_id), (proxy_id), (identity_id)
usage_snapshots: (org_id, period), (proxy_id, period)
```

### 8.4 Migration order

1. Add fields (additive, nullable).
2. Create collections/indexes.
3. Backfill personal orgs for existing users.
4. Backfill `org_id` on profiles/campaigns/mailboxes/WhatsApp.
5. Backfill `execution_mode` (already desktop default).
6. Backfill `proxy_mode` for existing proxy profiles.
7. Encrypt legacy proxy passwords.
8. Dual-read/write for one release.
9. Remove legacy fields after verification.

### 8.5 Rollback

- Keep additive fields; no destructive migrations until a later release.
- Feature flags gate new behavior.
- Reconciliation script can rebuild entitlements from Stripe.
- Proxy records remain for audit; disable, don’t delete.

---

## 9. Security and compliance

- All proxy passwords encrypted at rest; `COOKIE_ENCRYPTION_KEY` or `SECRET_KEY`.
- Massive keys server-side only; never in frontend/logs.
- Admin proxy routes require admin role; rate-limited.
- Tenant isolation on every proxy/seat/profile query.
- No cross-tenant proxy assignment.
- SSRF validation for proxy URLs.
- No secrets in error messages; generic client errors.
- Audit every admin mutation.
- Desktop keychain for tokens; no proxy credentials on desktop.
- VNC access scoped to the owning user/org; short-lived.
- Fair-use clause in ToS; no GB numbers.
- GDPR/CCPA: data retention, deletion, subprocessors (Massive), DPA.
- Data retention: profiles/campaigns retained 30/90 days after cancellation; configurable.
- Incident response: proxy leak, key leak, cross-tenant access, payment fraud.

---

## 10. Analytics and event taxonomy

Events:

```text
signup_started, signup_completed, email_verified,
checkout_started, checkout_completed, checkout_abandoned,
plan_activated, plan_changed, seat_purchased, seat_removed,
invite_sent, invite_accepted, member_removed,
account_added, region_selected, proxy_assigned, proxy_test_passed,
proxy_test_failed, cloud_verification_started, cloud_verification_completed,
desktop_downloaded, desktop_enrolled, desktop_task_completed,
first_campaign_created, fair_use_review_opened
```

Properties:

```text
user_id, org_id, plan, seat_type, channel, execution_mode,
country, provider, proxy_id (opaque), success, error_code
```

Funnels:

- Signup → verify → checkout → cloud activated.
- Cloud activated → account added → proxy assigned → verified → first campaign.
- Invite sent → accepted → seat assigned → desktop enrolled.
- Seat purchased → assigned → active.

Dashboards:

- Conversion, activation, seat utilization, proxy health, churn, cost per seat,
  support tickets per 100 seats.

---

## 11. Observability and operations

Metrics:

```text
proxy_test_success_rate
proxy_country_mismatch_rate
proxy_latency_p95
proxy_limit_reached_count
seat_limit_errors
checkout_failures
webhook_failures
reconciliation_drift
daemon_heartbeat_missing
cloud_task_failure_rate
```

Alerts:

- Proxy down > 3 consecutive checks.
- Country mismatch.
- Massive `limit_reached` or `proxy_access=false`.
- Payment failed / webhook failure.
- Seat over limit.
- Daemon offline > 10 min.
- Cloud task failure spike.
- Reconciliation drift.

Logs:

- Structured JSON.
- Redact proxy passwords, API keys, cookies, tokens.
- Correlation ID per request/task.

Incident runbook:

- Proxy provider outage → fallback provider/pool; pause cloud profiles.
- Key leak → rotate Massive keys, disable sub-accounts, audit.
- Cross-tenant access → contain, audit, notify.
- Payment webhook outage → replay, reconcile.

---

## 12. Acceptance criteria and test matrix

### Phase 0

- [ ] Cloud plan customer sees Cloud execution.
- [ ] `/signup?plan=cloud` → verify → checkout → Cloud activated.
- [ ] Extra cloud seat raises LinkedIn limit.
- [ ] Stripe webhook syncs plan + cloud seats.
- [ ] Cloud account requires region; proxy auto-assigned.
- [ ] Proxy test shows egress IP/country.
- [ ] Cloud profile without proxy does not launch.
- [ ] Admin can paste/import/assign a proxy.
- [ ] Desktop profile never receives proxy credentials.
- [ ] Proxy password migration applied.

### Phase 1

- [ ] Bulk import 100 proxies with preview/validation.
- [ ] Test/assign/unassign/disable/retire.
- [ ] One proxy per profile; shared only within identity; one LinkedIn per proxy.
- [ ] Health/usage visible.
- [ ] No secret in responses/logs.

### Phase 2

- [ ] Massive sub-account created per cloud seat.
- [ ] Region/session username correct.
- [ ] Usage sync and monthly thresholds.
- [ ] Disable on cancellation.
- [ ] Pool Stats warnings.

### Phase 3

- [ ] Owner invites member; member joins org.
- [ ] Seat assignment cloud/desktop.
- [ ] Desktop enrollment for org-owned profiles.
- [ ] Cloud/desktop daemon filtering.
- [ ] Member removal reassigns seats and revokes devices.
- [ ] No cross-tenant access.

### Phase 4

- [ ] Cloud Duo shared/separate IPs.
- [ ] WhatsApp cloud proxy works.
- [ ] Email BYO slot works.
- [ ] Pricing/marketing match.
- [ ] No datacenter IP in cloud.

### E2E scenarios

1. New Cloud buyer end-to-end.
2. Existing desktop user upgrades to Cloud.
3. Owner buys 3 seats, invites 2 members, assigns cloud + desktop.
4. Member leaves; seat reassigned; proxy retired.
5. Payment fails; grace period; profiles pause; reactivation.
6. Proxy fails; profile pauses; admin replaces; profile resumes.
7. Region change; warning; new egress IP.
8. Desktop enrollment; local IP; task completes.
9. Bulk import with bad lines; only valid rows imported.
10. Massive API outage; fallback pool; no account runs direct.

### Security tests

- Cross-tenant proxy access denied.
- Admin route requires admin.
- Proxy password never returned.
- Bulk import does not log secrets.
- Desktop bootstrap omits proxy for desktop.
- VNC scoped.

---

## 13. Release and rollout

Feature flags:

```text
CLOUD_SEATS_ENABLED
MANAGED_PROXIES_ENABLED
MASSIVE_RESELLER_ENABLED
MASSIVE_REPORTING_ENABLED
TEAM_WORKSPACES_ENABLED
WHATSAPP_CLOUD_PROXY_ENABLED
MANAGED_EMAIL_ENABLED
```

Rollout:

1. Internal accounts.
2. Two test accounts.
3. 10% canary.
4. 50%.
5. 100%.

Gates:

- Proxy success > 95%.
- Country match > 98%.
- No cross-tenant incidents.
- Checkout conversion not worse.
- Support tickets per 100 seats stable.

Rollback:

- Disable flag.
- Keep data/proxies; disable sub-accounts.
- Revert webhook/limits if needed.
- Communicate to affected customers.

---

## 14. Open decisions

1. Team member limit and price.
2. Cloud Duo shared vs separate IP default.
3. Business/Agency desktop seat counts.
4. Managed-only vs BYO default.
5. Email BYO vs managed.
6. WhatsApp cloud launch timing.
7. Agency sub-workspaces.
8. Fair-use wording and thresholds.
9. Data retention after cancellation.
10. US ISP pilot scope.
