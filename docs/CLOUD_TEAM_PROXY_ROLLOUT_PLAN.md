# Cloud, Teams, Seats & Managed Proxies — Phased Rollout Plan

Status: planning document  
Owner: product + platform  
Last updated: 2026-11-18  
Companion spec: `docs/CLOUD_TEAM_PROXY_IMPLEMENTATION_SPEC.md` (page map, API surface,
payment/billing, onboarding, team permissions, desktop/cloud, admin, migrations,
analytics, ops, acceptance criteria).

This document is the build plan for turning the current “cloud execution” feature into a
sellable, team-ready, proxy-managed product. It covers the marketing site, the cloud app,
the desktop app, onboarding, pricing, billing, admin operations, data migrations, security,
testing, and rollout.

The plan is deliberately phased. Each phase has a goal, scope, explicit non-goals, a
definition of done, and a rollback path.

---

## 1. Definitions

### 1.1 Execution mode

| Mode | Browser runs on | IP | Proxy | Who pays for infrastructure |
|---|---|---|---|---|
| **Desktop** | The member’s computer (desktop app daemon) | The member’s local IP | **Never** | The member / workspace |
| **Cloud** | `outreach-api` daemon on Scalingo | Managed egress IP | **Required** | The platform |

Desktop and cloud are per **channel account**, not per user and not per workspace. One
workspace can mix desktop and cloud accounts.

### 1.2 Channel account

A channel account is one of:

- one LinkedIn profile
- one WhatsApp number
- one email mailbox

### 1.3 Seat

A seat is a commercial bundle of channel accounts and an execution mode.

Two seat types:

| Seat type | Includes | Proxy | Typical price |
|---|---|---|---|
| **Desktop seat** | 1 LinkedIn **or** 1 WhatsApp + 1 email slot | None (local IP) | Included in team plans |
| **Cloud seat** | 1 LinkedIn **or** 1 WhatsApp + 1 email slot | 1 managed proxy identity group | $299/mo per seat |

A **Cloud Duo** bundle (1 LinkedIn + 1 WhatsApp + 1 email) can use **one** proxy identity
when the LinkedIn account and the WhatsApp number belong to the **same real-world
person/business**. Use two only when the channels belong to unrelated clients, or when
the client explicitly wants separate IPs. The unit of isolation is the **identity**, not
the channel.

Recommended commercial packaging:

- **Cloud Solo** — 1 browser account (LinkedIn or WhatsApp) + 1 email slot: $299/mo.
- **Cloud Duo** — 1 LinkedIn + 1 WhatsApp + 1 email: $299/mo when both channels share
  the same client identity and one proxy; add a second proxy (or a higher usage tier)
  only when the client wants separate IPs or the accounts are unrelated.
- **Extra cloud seat** — $299/mo per additional browser account.
- **Team member login** — free up to 3, then $29/mo; a login alone does not include a
  browser account or a proxy.

The real constraint is **usage**, not proxy count. A shared proxy consumes the combined
LinkedIn + WhatsApp bandwidth. Track usage internally and price the seat as a flat
monthly seat — do **not** expose GB allowances or overage to the customer. Treat the
proxy topology (shared vs separate) as a configuration/risk choice, not a pricing unit.

The commercial model is insurance: some clients use more, some less. Price for the
blended average plus a buffer, monitor outliers internally, and apply a fair-use policy
only when someone is far outside normal usage.

### 1.4 Proxy identity

A proxy identity is the egress IP/session used by one **real-world identity group** —
one person, business, or client. Rules:

- One proxy identity group per client/person/business.
- A LinkedIn account and a WhatsApp number belonging to the **same client** may share
  one proxy identity.
- Two unrelated clients must **never** share a proxy identity.
- Two LinkedIn accounts under the same client should each have their own proxy identity,
  because LinkedIn can link accounts by IP.
- Two WhatsApp numbers under the same client may share, but separate is safer.
- Never recycle a used proxy identity to a different client or LinkedIn account.
- Email does not use a browser proxy. SMTP/IMAP go direct to the provider; the sending
  domain/mailbox reputation is the relevant asset.
- Track usage **per channel and per proxy**. A shared proxy needs per-channel labels
  (for example `-subaccount-<client>-li` and `-subaccount-<client>-wa`) so the Reporting
  API can split usage.

### 1.5 BYO vs managed proxy

**BYO = Bring Your Own.** The customer supplies their own proxy credentials instead of
using the platform-managed Massive proxy.

| | Managed proxy | BYO proxy |
|---|---|---|
| Who provides it | Lengrowth / Massive | The customer |
| Who pays the provider | Lengrowth (included in seat price) | The customer |
| Credentials | Hidden from the client | Entered by the client/admin |
| Region/quality | Controlled by us | Customer’s responsibility |
| Testing | We test and monitor | We test, but support is limited |
| Billing | Included in cloud seat | No proxy charge; seat may be discounted |
| Best for | Standard Cloud customers | Agencies/high-volume clients with their own provider |

Recommended policy: **managed by default**, BYO allowed on request for agencies or
customers who already have a provider. Never mix the two for the same account.

### 1.6 Workspace / organization

A workspace owns billing, seats, members, proxies, and shared campaigns. The current
`User.org_id` field exists but is unused; this plan introduces real organizations.

---

## 2. Current-state audit

### 2.1 What already works

- Cloud plan exists: $299/mo, 1 LinkedIn account, monthly only.
- Cloud add-on exists in the API: $299/mo per cloud profile.
- Per-profile proxy fields exist on `linkedin_profiles`.
- The cloud daemon passes the proxy to Playwright.
- Proxy passwords are encrypted at rest (implementation done; migration pending).
- Proxy test returns the egress IP and latency.
- Stripe checkout, plan change, and cloud add-on subscription items work.
- Admin can set a user’s plan and `cloud_profiles` manually.
- Desktop app can enroll LinkedIn, WhatsApp, and mailbox profiles for local execution.
- Cloud daemon can run WhatsApp sessions when `DAEMON_V2_WHATSAPP_ENABLED` is true.

### 2.2 Critical gaps

| # | Gap | Evidence | Impact |
|---|---|---|---|
| 1 | Cloud-plan customers cannot select Cloud execution | `linkedin-credential-form.tsx:75` checks only `cloud_profiles > 0` | A $299 customer gets no cloud option |
| 2 | No direct Cloud signup | `pricing/page.tsx:290,333` links to `/signup`; `auth.py:489` starts a Starter trial | Cloud buyer must manually upgrade |
| 3 | No cloud-seat purchase UI | `updateCloudAddon()` defined but unused | Customers cannot buy extra seats |
| 4 | Cloud plan + extra seats does not raise the LinkedIn limit | `billing.py:619` sets `cloud_profiles` only | Cannot add a second account |
| 5 | Seat entitlement is not enforced for running profiles | `core/daemon.py:597` checks only `can_run_tasks` | Cancelled seats keep running |
| 6 | Webhooks read only `items[0]` and never sync cloud seats | `webhooks.py:425` | Add-on/portal changes drift |
| 7 | No real team/org model | `org_id` unused; `team_members` is a label; `team_member_ids` is campaign-only | No invites, roles, shared billing, or seat assignment |
| 8 | No admin proxy page | Only a read-only host field at `admin/users/[id]/page.tsx:736` | No inventory, bulk import, assignment, health, usage |
| 9 | No region selection or proxy auto-assignment | `LinkedInCredentialCreate` has no region; `linkedin_credentials.py:182` creates cloud profiles without proxies | Customer must paste credentials manually |
| 10 | WhatsApp cloud has no proxy support | `whatsapp/browser/launch.py:74` creates a context without `proxy` | Cloud WhatsApp runs on the server IP |
| 11 | WhatsApp profiles have no execution mode/seat | `whatsapp/models/profile.py` has no `execution_mode` | Cannot distinguish desktop vs cloud WhatsApp |
| 12 | Email is BYO SMTP/IMAP only | `emails/models.py`; no provisioning | “One email” in a seat is undefined |
| 13 | Cloud profiles without a proxy still launch | `linkedin/browser/launch.py:109` warns only | Account-risk exposure |
| 14 | No proxy reuse/retirement policy | No inventory model | Risk of linking accounts |
| 15 | No usage/health alerts | No proxy usage model | No cost control or incident response |
| 16 | No audit trail for proxy changes | No proxy audit log | Cannot investigate incidents |
| 17 | Marketing claims “team members” but no feature exists | `billing/plans.py:65,82`; emails | Trust/compliance issue |
| 18 | Proxy password migration not run | `migrations/encrypt_proxy_passwords.py` | Legacy plaintext remains |

### 2.3 What “works” but is fragile

- The desktop daemon enrollment is per `user_id`, not per organization. Team members
  cannot enroll org-owned profiles.
- The desktop app stores a single user token; there is no workspace switcher.
- Cloud WhatsApp is a global env flag, not a per-profile seat decision.
- Email tasks run through the desktop daemon with a short-lived mailbox grant; there is
  no cloud email worker.

---

## 3. Massive integration — what to use and where keys go

### 3.1 Use the Proxy Resellers API, not the MCP server

Massive’s MCP server (`@joinmassive/mcp-server`) is for the **Web Render API**
(`web_fetch`, `web_search`, `ai_chat_completion`) with country/city targeting. It does
**not** create or manage proxies. Do not use it for proxy provisioning.

The correct integration is:

| Purpose | Massive API | Base URL |
|---|---|---|
| Create/manage sub-accounts | **Proxy Resellers API** | `https://api-network.joinmassive.com/resellers` |
| Usage per sub-account | **Reporting API** | `https://api-network.joinmassive.com/reporting` |
| Region/node availability | **Pool Stats API** | `https://api-network.joinmassive.com/pool-stats` |
| Proxy traffic | Residential/ISP network | `network.joinmassive.com` / `isp.joinmassive.com` |

### 3.2 Where each key goes

All keys are **server-side only**. Never put them in the frontend, `NEXT_PUBLIC_*`,
MongoDB (except encrypted sub-account credentials), logs, or this repository.

| Key | Where it comes from | Where it goes in our system | Used by |
|---|---|---|---|
| Proxy username | Massive dashboard → Profile | `MASSIVE_PARENT_USERNAME` | Proxy credential builder |
| Proxy password / API key | Massive dashboard → Profile | `MASSIVE_PROXY_PASSWORD` | Proxy auth, Reporting API, Reseller API, Pool Stats API |
| Reseller API key | Same account API key; access enabled on 2026-11-18 | Reuse `MASSIVE_PROXY_PASSWORD`; `MASSIVE_RESELLER_API_KEY` is an optional alias | Sub-account create/disable/usage |
| Reporting API key | Same as proxy password (auto-enabled) | `MASSIVE_REPORTING_API_KEY` or reuse `MASSIVE_PROXY_PASSWORD` | Usage sync |
| Pool Stats API key | Same account API key; access enabled on 2026-11-18 | Reuse `MASSIVE_PROXY_PASSWORD`; `MASSIVE_POOL_STATS_API_KEY` is an optional alias | Region availability |
| Web Render / MCP token | Dashboard → Developer → API Keys | `MASSIVE_WEB_RENDER_TOKEN` (optional, separate feature) | Lead enrichment only |

Default endpoint variables:

```text
MASSIVE_PROXY_HOST=network.joinmassive.com
MASSIVE_PROXY_PORT=65534            # HTTP; 65535 HTTPS, 65533 SOCKS5
MASSIVE_ISP_HOST=isp.joinmassive.com
MASSIVE_ISP_PORT=8000               # HTTP; 4080 HTTPS
MASSIVE_RESELLER_BASE_URL=https://api-network.joinmassive.com/resellers
MASSIVE_REPORTING_BASE_URL=https://api-network.joinmassive.com/reporting
MASSIVE_POOL_STATS_BASE_URL=https://api-network.joinmassive.com/pool-stats
```

Deployment: Scalingo project `outreach`, app `outreach-api` environment. Do not create a
staging database. Rotate keys in the Massive dashboard and update Scalingo config; never
commit them.

Admin UI shows only “Massive: configured / missing” and a **Test connection** button.
It never displays the key.

### 3.3 Sub-account model

Create one Reseller sub-account per cloud seat / browser account:

```http
POST /resellers/accounts
x-api-key: <MASSIVE_PROXY_PASSWORD>
Content-Type: application/json

{
  "username": "outreach-org123-li-456",
  "password": "<generated-32+-char-secret>",
  "limit": 50000000000,
  "sync_with_parent": true
}
```

Credentials:

```text
username: <MASSIVE_PARENT_USERNAME>_outreach-org123-li-456
password: <generated-secret>
```

Rules:

- The existing account API key (`MASSIVE_PROXY_PASSWORD`) authenticates the Reseller
  API; no separate key is required. `MASSIVE_RESELLER_API_KEY` is an optional alias.
- Use hyphens in the sub-username, not underscores; the parent/sub separator is `_`.
- Maximum 255 characters; unique within the parent.
- Generate the password server-side; encrypt at rest; never show it to the client.
- `GET /accounts` returns passwords — treat the response as secret; never log it.
- `limit` is a **cumulative lifetime allowance**, not monthly. It can be raised but not
  lowered, so start conservatively and top up. Track monthly usage in our app.
- A `409` on create means the sub-username already exists. Fetch/update the existing
  account instead of retrying the same create.
- Disable on seat cancellation/unassignment; re-enable only for the same LinkedIn
  account. Never assign the same sub-account to a different LinkedIn account.

### 3.4 Proxy username with region and session

```text
<PARENT>_<SUB>-country-US-subdivision-NY-city-New%20York-session-<profile_id>-sessionttl-1440-sessionmode-flex-sessionerr-50-type-common
```

Parameters:

| Key | Values | Notes |
|---|---|---|
| `country` | ISO-2, e.g. `US` | Required whenever any geo parameter is used |
| `subdivision` | e.g. `NY` | Optional; stricter targeting narrows the pool |
| `city` | English GeoNames name, URL-encoded | Optional; case-sensitive |
| `zipcode` | e.g. `10001` | Optional; city is ignored when zipcode is set |
| `session` | unique ID up to 255 chars | One per browser account |
| `sessionttl` | minutes up to 1440 | Static TTL; not extended by requests |
| `sessionmode` | `strict` / `flex` / `norotate` | `flex` recommended for LinkedIn |
| `sessionerr` | 1–100 | Consecutive errors before rotation in flex |
| `type` | `common` / `mobile` / `tv` | `common` for normal, `mobile` for high-risk |
| `asn` | integer | Optional network targeting |

Massive’s Pool Stats API warns that at least **1,000 nodes** are recommended for reliable
geo-targeting. Prefer country-level; use city/state only when the account’s identity
requires it. If the count is too low, show a warning and suggest country-level.

### 3.5 ISP vs residential

| Product | Price | Best for | Caveat |
|---|---|---|---|
| Residential | $4.90–8.00/GB (plans from $80/10GB to $490/100GB) | Global accounts, non-US | Sticky sessions are best-effort; TTL max 1440 min |
| ISP | From $1.80/IP | US accounts, static IP | US/AT&T-oriented; test LinkedIn acceptance before rollout |
| Mobile (`type-mobile`) | Residential bandwidth | High-risk accounts | Smaller pool, slower |

Recommendation:

- US LinkedIn accounts: pilot ISP, keep residential fallback.
- Non-US LinkedIn accounts: residential, country-level.
- WhatsApp: residential/mobile, one identity per number; **not built yet**.
- Email: no proxy; use a reputable sending domain/mailbox.

### 3.6 Fallback if Reseller API access is delayed

Use the parent credentials with the accounting suffix:

```text
<PARENT>-subaccount-<profile_id>-country-US-session-<profile_id>-sessionttl-1440-sessionmode-flex
```

Track usage with the Reporting API:

```http
GET /reporting/v1/usage?group_by=subuser&from=...&to=...
x-api-key: <MASSIVE_PROXY_PASSWORD>
```

This works today, but lacks per-sub-account hard limits and disable. Use it for the first
two test accounts and early clients, then migrate to Reseller sub-accounts.

### 3.7 Reporting API

- `group_by=subaccount` → per Reseller sub-account usage.
- `group_by=subuser` → per `-subaccount-<label>` usage.
- Data is hourly; daily jobs after 00:30 UTC.
- Range max 31 days per request.
- Use it for monthly budgets, invoices, and admin usage charts.

### 3.8 Pool Stats API

- `GET /pool-stats/v1/live?country=US&group_by=country,city` → node counts.
- `GET /pool-stats/v1/regions` → regional endpoint URLs.
- Cache results for 1 hour.
- Warn if a country has fewer than 1,000 nodes; block city-level targeting below a safe
  threshold.

---

## 4. Target architecture

### 4.1 Data model

#### `proxies`

```text
_id
provider: massive_residential | massive_isp | manual
label
protocol: http | https | socks5
host, port
username
password_encrypted
country, subdivision, city
region_mode: fixed | targeted
kind: residential | isp | mobile | datacenter
device_type: common | mobile | tv
status: available | assigned | disabled | error | retired
identity_id                 # the client/person/business this proxy serves
linkedin_profile_id         # at most one LinkedIn account per proxy
assigned_user_id
assigned_org_id
massive_account_id
massive_parent_username
traffic_limit_bytes
used_bytes
limit_reached
last_tested_at
last_test_ip
last_test_country
last_test_latency_ms
last_error
created_at, updated_at, created_by
```

#### `client_identities`

```text
_id
org_id
name                        # client/person/business label
created_at, updated_at
```

#### `proxy_assignments`

```text
_id
proxy_id
identity_id
profile_id
channel: linkedin | whatsapp
seat_id
user_id
org_id
assigned_by
assigned_at
unassigned_at
reason
```

A proxy may have multiple assignments only when they share the same `identity_id`, and
at most one of them may be `channel=linkedin`. This allows one LinkedIn + one WhatsApp
for the same client to share an IP, while preventing two LinkedIn accounts or two
unrelated clients from sharing one.

#### `proxy_health_checks`

```text
_id
proxy_id
checked_at
success
egress_ip
egress_country
egress_city
latency_ms
error_type
```

#### `organizations`

```text
_id
name
owner_user_id
plan
stripe_customer_id
stripe_subscription_id
cloud_seats
desktop_seats
linkedin_account_limit
whatsapp_account_limit
created_at, updated_at
```

#### `organization_members`

```text
_id
org_id
user_id
email
role: owner | admin | member
status: invited | active | removed
invited_by
invited_at
joined_at
```

#### `organization_invites`

```text
_id
org_id
email
role
token_hash
expires_at
accepted_at
```

#### Profile fields

`linkedin_profiles`:

```text
org_id
identity_id
proxy_id
proxy_mode: managed | byo | none
proxy_region_country
proxy_region_subdivision
proxy_region_city
proxy_session_id
```

`whatsapp_profiles`:

```text
org_id
identity_id
execution_mode: desktop | cloud
proxy_id
proxy_mode
proxy_region_country
proxy_region_subdivision
proxy_region_city
proxy_session_id
```

`mailboxes`:

```text
org_id
seat_id (optional)
managed: bool
```

### 4.2 Core services

```text
openoutreach/proxies/
  models.py            # Proxy, ProxyAssignment, ProxyHealthCheck
  service.py           # assign/unassign/test/retire
  massive_client.py    # Reseller, Reporting, Pool Stats
  parser.py            # bulk paste parser
  region.py            # ISO country/city validation and username builder

openoutreach/organizations/
  models.py            # Organization, Member, Invite
  service.py           # create org, invite, accept, roles, seat counts
  enforcement.py       # effective plan/limits for a member

openoutreach/cloud/
  seats.py             # seat pool, channel bundles
  provisioning.py      # create profile -> assign proxy -> test
  usage.py             # monthly usage and budgets
```

### 4.3 Enforcement points

| Point | Rule |
|---|---|
| Add LinkedIn account | Desktop: check `linkedin_account_limit`; Cloud: check cloud seat |
| Add WhatsApp account | Desktop: check `whatsapp_account_limit`; Cloud: check cloud seat + proxy |
| Add mailbox | Check email slot; no proxy |
| Daemon profile selection | Cloud profile: seat + proxy required; desktop profile: proxy ignored |
| Task claim | Desktop device may claim only its enrolled desktop profiles |
| Billing webhook | Sync base plan + add-on quantity; do not treat `cloud_addon` as a plan |
| Proxy assignment | One active proxy per profile; a proxy may serve multiple channels only within the same `identity_id`; at most one LinkedIn account per proxy; no cross-tenant or cross-identity sharing |
| Proxy retirement | Never reassign a used proxy to a different identity or LinkedIn account |

---

## 5. Phase 0 — Stabilize the current cloud path

**Duration:** ~1 week  
**Goal:** A customer can buy Cloud and actually add a cloud LinkedIn account with a
working proxy.

### 5.1 Scope

Status (2026-11-18): implementation complete on branch
`feature/cloud-phase0-proxy-seats`; review fixes, atomic seat reservation, and the
runtime cloud-seat guard are included. Production deploy and the `--apply` migration
remain gated on two-account E2E validation, a production migration dry-run, and approval.

1. - [x] Fix the Cloud execution selector:
   `hasCloudAccess = plan === "cloud" || cloud_profiles > 0`.
2. - [x] Add `?plan=cloud` to the pricing CTAs and store the intended plan through signup.
3. - [x] Skip the Starter trial for Cloud-intent users; redirect to Cloud checkout after email
   verification.
4. - [x] Add a Cloud seat quantity control in Settings → Billing.
5. - [x] Fix Cloud plan + extra seats: `linkedin_account_limit = 1 + cloud_profiles` for
   `plan === "cloud"`.
6. - [x] Sync `cloud_profiles` from all Stripe subscription items in checkout/updated webhooks.
7. - [x] Add region fields (country required, subdivision/city optional) to the cloud account
   form.
8. - [x] Add a minimal `proxies` collection and admin list/import/assign/test endpoints.
9. - [x] Auto-assign an available proxy matching the region when a cloud account is created.
10. - [x] Block cloud profile launch if no proxy; log and alert instead of using the server IP.
11. - [x] Deploy and run `python -m openoutreach.migrations.encrypt_proxy_passwords --apply`.
    Production deploy completed on 2026-11-18; the production dry-run found no
    plaintext proxy passwords, so the apply step is a no-op.

### 5.2 Non-goals

- No full org/team model.
- No Massive Reseller API integration.
- No WhatsApp cloud proxy.
- No managed email.
- No ISP rollout.

### 5.3 Marketing website

- Cloud CTA → `/signup?plan=cloud`.
- Add “Cloud requires a paid subscription; no cloud trial.”
- Clarify “Cloud $299/mo includes 1 LinkedIn account and 1 managed proxy.”
- Remove or soften “team members” claims until Phase 3.
- Add FAQ: “Do I need a proxy for desktop?” → No.

### 5.4 Cloud app

- Cloud execution card visible for Cloud plan.
- Region step in the add-account wizard.
- Proxy status card: “Managed · US · Healthy · Egress IP …”.
- Seat usage: “1 of 1 cloud seat used”.
- Clear error if no proxy is available.

### 5.5 Desktop app

- No new feature.
- Ensure desktop profiles never receive proxy credentials from the bootstrap endpoint.
- Show “Local IP” on desktop accounts.

### 5.6 Admin

- `/admin/proxies` minimal page: list, bulk paste, test, assign, disable.
- `/admin/users/[id]` shows assigned proxy and seat usage.
- Audit log entries for import/assign/disable.

### 5.7 Definition of done

- New user selects Cloud → verifies email → checks out → adds a LinkedIn account →
  selects region → gets a proxy → test passes → verification starts.
- Cloud plan customer sees the Cloud execution option.
- Extra cloud seat raises the account limit.
- Cancelling a seat pauses the profile.
- Proxy password migration applied; no plaintext remains.

### 5.8 Rollback

- Feature flag `CLOUD_SEATS_ENABLED=false` hides the seat UI.
- Keep manual admin assignment as fallback.
- Revert webhook changes if seat sync misbehaves; do not delete data.

---

## 6. Phase 1 — Managed proxy operations

**Duration:** ~2 weeks  
**Goal:** The admin can run a proxy pool at scale without touching MongoDB.

Status (2026-11-18): deployed to production from commit `3447ea7e` on
`outreach-api` and `outreach-web`; `/api/health` and the web root returned 200,
the postdeploy index hook ran, and both new proxy cron tasks are registered.
Phase 1 includes full inventory filters/pagination, masked CSV export, import
preview and per-line errors, bulk lifecycle actions, assignment history, manual
and scheduled health checks, Massive fallback credentials with Reporting API
`group_by=subuser` sync, admin usage views, audit events, and import/test rate
limits. Marketing region/security copy and the customer managed-proxy health
card are also updated. The Phase 0 proxy-password encryption migration was
verified in production: the dry-run found no plaintext passwords, so the apply
step is a no-op.

### 6.1 Scope

1. Full admin proxy inventory:
   - list/filter by provider, country, status, assignment
   - bulk import with preview and validation
   - test selected/all
   - assign/unassign
   - disable/enable/retire
   - export CSV (masked)
2. Bulk paste formats:
   - `host:port:user:pass`
   - `host:port:user:pass:country`
   - `user:pass@host:port`
   - `http://user:pass@host:port`
   - `socks5://user:pass@host:port`
   - CSV/TSV with header
3. Auto-detect country on test; flag expected vs actual mismatch.
4. Proxy health checks (manual + scheduled daily).
5. Assignment rules:
   - one active proxy per profile
   - a proxy may serve multiple channels only within the same `identity_id`
   - at most one LinkedIn account per proxy
   - no cross-tenant or cross-identity assignment
   - retire on profile deletion
6. Massive fallback:
   - parent credentials + `-subaccount-<profile>` + session/region params
   - Reporting API `group_by=subuser` usage sync
7. Admin usage view: per proxy, per profile, per workspace.

### 6.2 Marketing website

- Add “Managed proxy included” to Cloud.
- Add “Region selection” to the comparison table.
- Add FAQ: “Which country does my LinkedIn account use?”
- Add a security note: “Proxy credentials are encrypted; clients never see them.”

### 6.3 Cloud app

- Read-only managed proxy card with health, region, egress IP, last test.
- “Request proxy change” button (admin approval) instead of credential editing.
- BYO proxy remains available only if the product decides to support it.

### 6.4 Desktop app

- Desktop accounts show “Local IP · No proxy”.
- No proxy UI on desktop.
- If a profile is switched from cloud to desktop, clear/ignore proxy fields and warn
  about the IP change.

### 6.5 Admin

- Full `/admin/proxies` page with tabs: Inventory, Assignments, Health, Usage.
- Bulk import modal with format help and error report.
- Audit log: import, assign, unassign, disable, retire, rotate.

### 6.6 Definition of done

- Admin can paste 100 proxies, preview, import, test, and assign them.
- Every cloud profile has exactly one active proxy.
- A proxy may serve one LinkedIn + one WhatsApp of the same client identity; it may not
  serve two LinkedIn accounts or two unrelated clients.
- Health checks show egress country and latency.
- Usage is visible per proxy, per channel, and per profile.
- No password appears in any list response or log.

### 6.7 Rollback

- Disable `MANAGED_PROXIES_ENABLED`.
- Keep existing per-profile proxy fields as the source of truth.
- Proxy records remain for audit.

---

## 7. Phase 2 — Massive Reseller API and usage control

**Duration:** ~2 weeks  
**Goal:** Provision and revoke Massive sub-accounts automatically, with usage and cost
control.

Status (2026-11-19): **implemented** on branch
`feature/cloud-phase3a-orgs-team-seats` behind `MASSIVE_RESELLER_ENABLED` and
`MASSIVE_POOL_STATS_ENABLED` (both default off). It covers the Reseller/Pool Stats
clients, automatic sub-account provisioning with Phase 1 fallback, lifecycle
disable/enable/retire, cumulative and Reporting usage sync, internal soft/hard
budgets, admin Massive tab, and customer region-safety copy. No live Massive
mutation or production deploy was performed. See
`docs/CLOUD_PHASE2_MASSIVE_RESELLER.md`.

### 7.1 Prerequisite

Reseller and Pool Stats API access was enabled on 2026-11-18. The existing account API
key (`MASSIVE_PROXY_PASSWORD`) authenticates both APIs through the `x-api-key` header;
no separate key is required. `MASSIVE_RESELLER_API_KEY` and
`MASSIVE_POOL_STATS_API_KEY` remain optional aliases for deployments that prefer
separate names. Sub-accounts have no count cap and draw from the parent plan’s
bandwidth.

### 7.2 Scope

1. `MassiveResellerClient`:
   - create/update/enable/disable sub-account
   - allocate traffic
   - set per-session limits
   - list accounts and usage
2. One sub-account per cloud seat/browser account.
3. Store `massive_account_id`, parent username, encrypted password.
4. Build region/session username; test egress country.
5. Sync usage daily:
   - `GET /accounts` for cumulative usage/limit/proxy_access
   - Reporting API for monthly/daily breakdown
6. Monthly budget enforcement:
   - track usage per seat
   - disable sub-account when over budget
   - re-enable next month
   - alert admin
7. Disable on seat cancellation/unassignment; re-enable only for the same LinkedIn
   account.
8. Pool Stats region availability:
   - cache country node counts
   - warn below 1,000 nodes
   - block city-level below safe threshold
9. Admin “Massive” tab:
   - connection status
   - parent plan usage
   - sub-account table
   - Sync now
   - Provision for profile
   - Disable/rotate

### 7.3 Marketing website

- Add “Powered by Massive residential network” (optional).
- Add “195+ countries” and “region selection”.
- Add “US static ISP option” only after the pilot passes.
- Add FAQ: “What happens if my proxy changes IP?” → sticky session + TTL explanation.

### 7.4 Cloud app

- Region change flow with warning: “Changing region changes the egress IP and may
  trigger a LinkedIn challenge.”
- Customer-facing usage: health/status only (“Managed · Healthy · US”), no GB meter.
  GB usage stays in the admin/cost dashboard.
- Health status and last check.
- No credentials.

### 7.5 Desktop app

- No proxy.
- If a member has both desktop and cloud accounts, show the execution mode clearly.
- Ensure the desktop daemon never claims cloud profiles.

### 7.6 Admin

- Massive sync, usage, disable/enable, rotate password.
- Parent plan usage and projected internal cost (not customer billing).
- Alerts for `limit_reached`, `proxy_access=false`, country mismatch, repeated failures.

### 7.7 Definition of done

- A new cloud seat creates a Massive sub-account automatically.
- The proxy test returns the expected country.
- Usage sync works and monthly budgets are enforced.
- Cancelling a seat disables the sub-account.
- Admin can see parent plan usage and per-seat usage.

### 7.8 Rollback

- Disable `MASSIVE_RESELLER_ENABLED`; fall back to manual/fallback credentials.
- Keep sub-accounts disabled, not deleted.
- Revert to `-subaccount` suffix mode if the Reseller API fails.

---

## 8. Phase 3 — Teams, seats, and desktop parity

**Duration:** ~3 weeks  
**Goal:** A workspace owner can invite members, buy seats, and let each member use
desktop or cloud execution under one billing relationship.

Status (2026-11-19): **Phase 3A and 3B implemented** on branch
`feature/cloud-phase3a-orgs-team-seats` behind `TEAM_WORKSPACES_ENABLED`
(default off). Phase 3A covers organizations, personal-org backfill, invites,
roles, effective plan/seat inheritance, cloud seat assignment, org-aware profile/
campaign/proxy/daemon authorization, audit events, a minimal admin org view, and
the Settings → Team + org switcher UI. Phase 3B adds org-owned desktop/WhatsApp/
mailbox assignment, desktop-only enrollment, org device list/revocation, local-IP
reporting, admin org proxies/usage, and the support runbook. Team-member pricing
remains an explicit product decision and was not changed. See
`docs/CLOUD_PHASE3A_ORGS_TEAMS.md` and
`docs/SUPPORT_TEAM_PROXY_RUNBOOK.md`. No production deploy or migration has been
run.

### 8.1 Scope

1. Organizations, members, invites, roles.
2. Personal org auto-created for every user; backfill existing users.
3. Effective plan/limits resolution:
   - member inherits the org owner’s plan/seat pool
   - personal users keep their own plan
4. Seat types:
   - desktop seat: local IP, no proxy, included in team plans
   - cloud seat: managed proxy, billed monthly
5. Seat assignment:
   - owner/admin assigns a cloud seat to a profile/member
   - desktop seat assignment is per device/channel
6. Desktop enrollment:
   - org-owned profiles/mailboxes/WhatsApp numbers visible to owner/admin
   - member can enroll only assigned desktop profiles
   - enrollment endpoint authorizes org membership, not just `user_id`
7. Cloud daemon:
   - runs only cloud profiles with a valid seat + proxy
   - pauses profiles over the seat limit
8. Desktop daemon:
   - runs only enrolled desktop profiles
   - never receives proxy credentials
   - reports local IP
9. Billing:
   - org owner pays
   - cloud seats sync from Stripe
   - desktop seats included per plan
   - seat removal pauses the profile and disables the proxy
10. Admin:
    - org view: members, seats, profiles, proxies
    - impersonation remains audited

### 8.2 Marketing website

- Add a Team section: “Invite your team. They can run desktop for free or cloud seats
  managed by us.”
- Update plan cards:
  - Business/Agency: desktop seats included
  - Cloud: cloud seats
- Add comparison table: desktop seat vs cloud seat.
- Add FAQ:
  - “Can my team use the desktop app?” → Yes.
  - “Do desktop seats need a proxy?” → No.
  - “Can we mix desktop and cloud?” → Yes, per account.
  - “What happens when a member leaves?” → Reassign the seat; the proxy is not reused
    for a different LinkedIn account.
- Update transactional emails to match the actual feature set.

### 8.3 Cloud app

- Workspace switcher.
- Settings → Team: members, roles, invites, seat assignment.
- Settings → Billing: plan, cloud seats, desktop seats, invoices.
- Settings → LinkedIn: owner/member, execution mode, region, proxy status.
- Role-based UI:
  - owner/admin: billing, team, proxies
  - member: own/assigned profiles and campaigns
- Invite acceptance flow that skips plan checkout and joins the org.

### 8.4 Desktop app

- Org-aware login and workspace context.
- Show assigned desktop profiles and devices.
- Enrollment for org-owned profiles (owner/admin creates code; member redeems).
- Device list and revocation per org.
- Clear “Local IP” badge; no proxy settings.
- Version bump and force-update gate if the API contract changes.
- Windows/macOS build, sign, notarize, release.

### 8.5 Admin

- Organization detail page: plan, seats, members, profiles, proxies, usage.
- Seat overrides and audit.
- Proxy assignment per org.
- Support runbook for “member cannot see profile”, “desktop enrollment fails”, “seat
  limit reached”.

### 8.6 Definition of done

- Owner invites a member; member accepts and sees the org.
- Owner assigns a desktop profile; member enrolls their desktop and runs it on local IP.
- Owner assigns a cloud seat; member sees the cloud profile and cannot edit proxy
  credentials.
- Billing shows the correct seat count.
- Removing a member/seat pauses the right profiles and disables the right proxy.
- No cross-tenant data or proxy access.

### 8.7 Rollback

- Disable `TEAM_WORKSPACES_ENABLED`.
- Keep personal orgs; members fall back to personal billing.
- Do not delete org data; mark inactive.

---

## 9. Phase 4 — Channel bundles, WhatsApp cloud, email, pricing

**Duration:** ~2 weeks  
**Goal:** Deliver the “one LinkedIn + one WhatsApp + one email” bundle safely and price
it correctly.

### 9.1 WhatsApp cloud proxy

Current gap: `whatsapp/browser/launch.py` creates a context without a proxy. Required:

1. Add `execution_mode`, `identity_id`, `proxy_id`, `proxy_mode`, `proxy_region_*` to
   `WhatsAppProfile`.
2. Pass the proxy to `browser.new_context(proxy=...)` exactly like LinkedIn.
3. One proxy identity per WhatsApp number by default. It may share the same client’s
   LinkedIn proxy when both channels belong to the same identity and the client accepts
   the shared-IP trade-off.
4. Country should match the phone number’s country.
5. Add seat enforcement and proxy auto-assignment.
6. Add a QR/VNC flow for cloud WhatsApp (currently the QR is stored in DB; the cloud
   daemon runs headless, so verify the QR path works without a local browser).
7. Test WhatsApp Web acceptance on residential/mobile; never use a datacenter IP.

### 9.2 Email

Current state: BYO SMTP/IMAP, no proxy, no provisioning.

Decide:

- **BYO mailbox** (recommended for Phase 4): the seat includes an email slot; the
  customer connects their own SMTP/IMAP. No proxy, no managed mailbox cost.
- **Managed mailbox** (later): provision Google Workspace/Microsoft 365/SMTP provider
  accounts, manage domains, warmup, and billing. This is a separate product with
  deliverability/compliance work.

If “one email” means a managed mailbox, add:

- mailbox provisioning integration
- domain/DNS setup
- warmup schedule
- bounce/complaint handling
- per-seat sending limits
- data retention/compliance

### 9.3 Pricing

Recommended:

| Product | Price | Includes |
|---|---|---|
| Cloud Solo | $299/mo | 1 browser account (LinkedIn or WhatsApp) + 1 email slot + 1 proxy identity |
| Cloud Duo (shared IP) | $299/mo | 1 LinkedIn + 1 WhatsApp + 1 email + 1 shared proxy identity, same client |
| Cloud Duo (separate IPs) | $349–399/mo | 1 LinkedIn + 1 WhatsApp + 1 email + 2 proxy identities |
| Extra cloud seat | $299/mo | 1 additional browser account + proxy identity |
| Team member login | Free up to 3; $29/mo after | No browser account/proxy |
| Desktop seat | Included in Business/Agency | Local IP, no proxy |

Customer-facing pricing is **flat per seat**. Do not publish GB allowances, overage
rates, or “included bandwidth.” The seat includes the managed proxy, browser, AI, and
email slot under a fair-use policy.

Cost math (internal):

- Residential LinkedIn: ~$25–80/mo per account at 5–10 GB optimized.
- Residential WhatsApp: similar; mobile may cost more.
- Shared proxy: one bandwidth bucket for both channels; usage is additive.
- ISP US: $1.80/IP/mo.
- Blended planning average: ~15 GB per active seat.
- Cloud Solo margin: ~$225–261 at $2.50/GB, ~$176–226 at $4.90/GB.
- Cloud Duo shared margin: similar; separate IPs at $349–399 add ~$25–80 of proxy cost.

Do not price by “number of proxies” or “number of GB” in the customer-facing plan. Price
by seat; treat proxy topology and bandwidth as internal cost/risk decisions.

Internal guardrails (never shown to the customer):

| Seat | Soft review | Hard review | Action |
|---|---:|---:|---|
| Cloud Solo | 25 GB/mo | 40 GB/mo | Alert admin; review account activity |
| Cloud Duo shared | 30 GB/mo | 50 GB/mo | Alert admin; check WhatsApp media |
| Cloud Duo separate | 35 GB/mo | 60 GB/mo | Alert admin; review proxy topology |

At the hard threshold, throttle non-essential resources or contact the client — do not
send a surprise bill. Publish a fair-use clause, not a GB number.

### 9.4 Marketing website

- “What’s in a seat?” table.
- “Cloud vs Desktop” table.
- “Managed proxy included” and “Region selection”.
- WhatsApp cloud availability and limitations.
- Email BYO vs managed.
- FAQ: “Can LinkedIn and WhatsApp share a proxy?” → Yes, when they belong to the same
  client identity; separate IPs are available for clients who want them.
- FAQ: “What counts as a seat?” → One browser account + one email slot. Pricing is flat
  per seat under a fair-use policy; no GB meter.
- Pricing page: Cloud Solo / Cloud Duo (shared or separate IP) / Team.
- Signup: plan/seat selection.

### 9.5 Cloud app

- Channel bundle onboarding:
  1. LinkedIn (cloud/desktop, region, proxy)
  2. WhatsApp (cloud/desktop, region, proxy, QR)
  3. Email (BYO/managed)
- Seat usage per channel.
- Health per channel.
- Clear warnings if a channel is missing a seat/proxy.

### 9.6 Desktop app

- Show the same channel bundle for desktop seats.
- WhatsApp and email run locally; no proxy.
- Enrollment binds LinkedIn/WhatsApp/mailbox as it does today, but org-aware.

### 9.7 Definition of done

- A Cloud Duo seat provisions one shared proxy when LinkedIn and WhatsApp belong to the
  same client identity, or two proxies when the client chooses separate IPs.
- Country checks pass for every browser channel.
- Usage is tracked per channel even when the proxy is shared.
- Email slot works with BYO SMTP/IMAP.
- Pricing/marketing match the actual bundle.
- No channel runs on a datacenter IP in cloud.

### 9.8 Rollback

- Disable `WHATSAPP_CLOUD_PROXY_ENABLED`; fall back to desktop WhatsApp.
- Keep Cloud Solo pricing; hide Cloud Duo.
- Do not migrate existing accounts to the bundle without consent.

---

## 10. Phase 5 — Scale and optimize

**Duration:** ongoing

1. ISP proxy pilot for US accounts; compare challenge rates vs residential.
2. Mobile proxy tier for high-risk accounts.
3. Internal usage monitoring and fair-use review (no customer-facing GB billing).
4. Agency/client sub-workspaces.
5. Automated proxy rotation on failure (with account-safety rules).
6. Cost dashboards: revenue per seat vs proxy/AI/infra cost.
7. Support tooling: one-click proxy reassignment, health replay, region change.
8. Compliance: data residency, retention, audit exports.

---

## 11. Cross-phase workstreams

### 11.1 Marketing website checklist

- [ ] Pricing page matches the current phase’s actual features.
- [x] Cloud CTA carries `?plan=cloud`.
- [ ] Cloud vs Desktop comparison.
- [ ] “What’s in a seat?” table.
- [x] Proxy/region FAQ.
- [ ] Team/seat FAQ.
- [x] Security/encryption note.
- [ ] No claims for features not shipped.
- [ ] Signup → checkout → onboarding path tested.
- [ ] SEO pages for cloud execution, managed proxy, team outreach.
- [ ] Transactional emails updated.

### 11.2 Desktop app checklist

- [x] Desktop profiles never receive proxy credentials.
- [ ] Local IP badge.
- [ ] Cloud vs desktop account display.
- [ ] Org-aware login/workspace.
- [ ] Org-owned profile enrollment.
- [ ] Device list/revocation per org.
- [ ] Seat type display.
- [ ] Version bump/force update.
- [ ] Windows/macOS build, sign, notarize.
- [ ] E2E: invite → enroll → run task on local IP.

### 11.3 Cloud app checklist

- [x] Cloud execution selector.
- [x] Region selection.
- [x] Managed proxy status.
- [x] Seat usage.
- [x] Team/org pages (Phase 3A: Settings → Team, org switcher).
- [x] Billing seat management.
- [ ] Channel bundle onboarding.
- [x] Role-based UI (Phase 3A).
- [ ] Health/usage alerts.
- [x] No credentials exposed.

### 11.4 Admin checklist

- [x] Proxy inventory.
- [x] Bulk import/preview.
- [x] Test/assign/unassign/disable/retire.
- [ ] Massive sync/usage.
- [x] Org/seat view (Phase 3A minimal admin org page + audited seat override).
- [x] Audit log.
- [ ] Alerts.
- [ ] Support runbook.

### 11.5 Onboarding checklist

- [x] Signup with intended plan.
- [x] Email verification.
- [ ] Checkout.
- [ ] Workspace creation.
- [ ] Team invite (optional).
- [ ] Add channel accounts.
- [x] Choose desktop/cloud.
- [x] Choose region for cloud.
- [ ] Proxy auto-provision/test.
- [ ] Verify account (VNC/QR).
- [ ] Create first campaign.
- [ ] Progress checklist and emails.

### 11.6 Security checklist

- [ ] Proxy passwords encrypted at rest.
- [ ] Massive keys server-only.
- [x] Admin-only proxy routes.
- [x] Tenant isolation on assignment.
- [x] No secrets in logs/responses.
- [x] Audit log.
- [x] Rate limits on import/test.
- [x] SSRF validation for proxy URLs.
- [ ] Device revocation.
- [x] No proxy reuse across LinkedIn accounts.

### 11.7 Testing checklist

- [x] Unit: seat enforcement, region builder, parser, encryption.
- [x] Unit: proxy assignment rules, lifecycle, masked export, usage aggregation.
- [x] Unit: Phase 3A personal-org backfill, invite lifecycle, role matrix, effective plan, org seat accounting, cross-tenant denial, seat-removal retention, feature-flag rollback.
- [ ] Integration: checkout/webhooks, seat sync, proxy assignment.
- [ ] E2E cloud: signup → checkout → add account → region → proxy → verify → campaign.
- [ ] E2E desktop: org invite → enroll → local IP → task.
- [x] E2E team (service/API level): invite → accept → seat assignment → member visibility → removal pause/proxy retention.
- [x] Security: cross-tenant access, admin auth, secret redaction.
- [ ] Migration: dry-run, idempotency, rollback.
- [ ] Load: bulk import 1,000 proxies, usage sync.

### 11.8 Rollout checklist

- [ ] Feature flags per phase.
- [ ] Internal accounts first.
- [ ] Two test accounts.
- [ ] 10% canary.
- [ ] 100%.
- [ ] Monitor proxy success, country mismatch, seat errors, checkout conversion.
- [ ] Support runbook and on-call.
- [ ] Rollback tested.

---

## 12. Feature flags

```text
CLOUD_SEATS_ENABLED
MANAGED_PROXIES_ENABLED
MASSIVE_RESELLER_ENABLED
MASSIVE_REPORTING_ENABLED
TEAM_WORKSPACES_ENABLED
WHATSAPP_CLOUD_PROXY_ENABLED
MANAGED_EMAIL_ENABLED
```

Flags live in the API environment, not the frontend. The frontend reads a capability
response, not the raw flag values.

---

## 13. Open product decisions

1. **Seat bundle:** one browser account per seat, or LinkedIn + WhatsApp + email per
   seat? **Resolved for Phase 0:** one browser account per seat; Cloud seats are a
   Cloud-plan entitlement only. A Cloud Duo bundle may share one proxy identity when both
   channels belong to the same client. Price flat per seat, not by proxy count or GB.
2. **Team member pricing:** **Resolved for the Phase 3 rollout:** member logins
   are included in the current plan; a login alone does not include a browser
   account or proxy. No per-member charge or free-up-to-3 metering was added.
   Revisit before Phase 4 with real workspace usage.
3. **Managed-only vs BYO:** do Cloud customers get a managed proxy only, or can they
   bring their own? **Resolved for Phase 0:** managed by default; managed proxies are
   read-only in the client; BYO remains available only on profiles without a managed
   proxy. Replacing a managed proxy requires support.
4. **US ISP pilot:** test 5–10 accounts before offering it broadly. Phase 2.
5. **Email:** BYO mailbox for Phase 4; managed mailbox later.
6. **WhatsApp cloud:** sharing the same client’s LinkedIn proxy is allowed; two unrelated
   clients must never share. Do not launch WhatsApp cloud without proxy support. Phase 4.
7. **Agency workspaces:** single org with members now; client sub-workspaces later. Phase 3.
8. **Proxy sharing default:** one proxy identity per client/person/business; separate IPs
   per channel are an opt-in configuration, not the default. Phase 3–4.
9. **Fair-use policy:** **Resolved:** flat per-seat pricing; internal soft/hard review
   thresholds only. No customer-facing GB allowance, meter, or overage charge.
10. **Seat accounting:** **Resolved for Phase 0:** a seat is consumed by an existing
    credentialed account, active or paused; deleting the account releases it. New accounts
    reserve a seat atomically. Pausing an account does not free its seat.
11. **Proxy on pause/cancel:** **Resolved for Phase 0:** seat removal and cancellation
    pause profiles but keep their proxies assigned so the same identity can resume if the
    seat is re-added. Only profile deletion retires the proxy; a used proxy is never
    recycled to a different LinkedIn account.

---

## 14. Immediate next actions

1. Approve the seat definition and bundle pricing.
2. Apply for Massive Reseller + Pool Stats API access.
3. Implement Phase 0 fixes (Cloud selector, signup, seat limits, region, minimal proxy
   admin).
4. Run the proxy password encryption migration after deploy.
5. Test two cloud accounts end-to-end with two Massive sessions.
6. Start Phase 1 admin proxy inventory and bulk import.
7. Schedule Phase 3 team/desktop design review before building org billing.

---

## 15. Internal bandwidth and unit economics (working estimate)

This is an internal cost model, not a customer-facing allowance. Measure the first two
cloud accounts for two weeks before locking the internal thresholds.

### 15.1 Assumptions

**LinkedIn**

- The browser already blocks images/media/fonts/stylesheet for non-LinkedIn domains
  (`linkedin_cli/browser/login.py`), a ~60–70% reduction.
- Raw page load estimate: 2.5 MB.
- Optimized page load: ~0.875 MB.
- Default account limits: 20 connects + 25 follow-ups per day = 45 actions/day.
- Add ~8 `check_pending` page loads/day.
- 16 active hours/day.
- Add 10% for TLS, retries, and redirects.

**WhatsApp**

- No resource blocking today. Add it before launch; it can cut 50–70%.
- Default daily limit: 20 messages/day.
- Warmup ceiling: 150 messages/day after 30 days.
- The browser stays open; background sync and websocket traffic are continuous.
- Text-only campaigns are much lighter than media-heavy chats.

**Email**

- SMTP/IMAP, no proxy.
- Default 30 emails/day.
- Text-only: ~50–150 MB/month including IMAP sync.
- No proxy GB. Count it as platform bandwidth, not Massive bandwidth.

### 15.2 Estimate table

| Scenario | LinkedIn GB/mo | WhatsApp GB/mo | Email proxy GB | Total proxy GB | Cost @ $2.50/GB | Cost @ $4.90/GB |
|---|---:|---:|---:|---:|---:|---:|
| Conservative (default limits, 20 WA/day, text-only) | 1.5–2.5 | 1–2 | 0 | **2.5–4.5** | $6–11 | $12–22 |
| Average (LinkedIn average preset, 60 WA/day) | 4–8 | 2–4 | 0 | **6–12** | $15–30 | $29–59 |
| Aggressive (LinkedIn 40/h, 150 WA/day) | 10–17 | 5–10 | 0 | **15–27** | $38–68 | $74–132 |
| Very aggressive / media-heavy | 18–25 | 10–20 | 0 | **28–45** | $70–113 | $137–221 |
| Email only | 0 | 0 | 0 | **0** | $0 | $0 |

Notes:

- The high-end LinkedIn figures assume 320–960 page loads/day. The code’s default
  20 connect + 25 follow-up limits are much lower; the high-end is a planning ceiling for
  accounts with many campaigns and enough leads.
- WhatsApp without resource blocking can be the largest line item. Add resource blocking
  before selling WhatsApp cloud.
- Media (images/video) in WhatsApp can multiply usage. Text-only campaigns are the
  target.
- Massive bills decimal GB (10⁹ bytes), not GiB.
- $4.90/GB is the 100 GB Pro tier ($490/100 GB). At 10 GB the list price is $8/GB; at
  30 GB it is $7.50/GB. The negotiated $2.50/GB changes the math significantly.

### 15.3 Internal cost guardrails (not customer-facing)

| Seat | Planning average | Soft review | Hard review |
|---|---:|---:|---:|
| Cloud Solo (1 browser + email slot) | 10–15 GB/mo | 25 GB/mo | 40 GB/mo |
| Cloud Duo shared (LinkedIn + WhatsApp, same identity) | 15–20 GB/mo | 30 GB/mo | 50 GB/mo |
| Cloud Duo separate IPs | 18–25 GB/mo | 35 GB/mo | 60 GB/mo |
| Extra cloud seat | 10–15 GB/mo | 25 GB/mo | 40 GB/mo |

At $2.50/GB, a 15 GB average costs $37.50; at $4.90/GB, $73.50. A $299 seat leaves
**$225–261** or **$176–226** before AI/infra. At the 30 GB soft review, cost is $75–147,
leaving **$152–224**.

If a client runs “full force” at 45 GB, proxy cost is $112.50–220.50; the $299 seat still
works, but the margin narrows. At the 60 GB hard review, cost is $150–294 — still
break-even to positive at $2.50/GB, thin at $4.90/GB. That is why the hard review exists.

The guardrails are **internal**: alert the admin, inspect the account, throttle
non-essential resources, or contact the client. Never expose a GB meter or a per-GB
overage charge.

### 15.4 How to reduce bandwidth

1. Add WhatsApp resource blocking (third-party images/media/fonts; keep WhatsApp assets
   and QR rendering).
2. Keep LinkedIn resource blocking; verify it is active in cloud.
3. Avoid loading the LinkedIn feed; navigate directly to profile/messaging URLs.
4. Keep the WhatsApp browser open instead of restarting it; each restart reloads the app.
5. Use text-only WhatsApp campaigns; avoid media.
6. Use `domcontentloaded`, not `load` (already done for LinkedIn).
7. Use country-level targeting, not city/ZIP; fewer retries and 521 errors.
8. Add a 10% buffer for TLS/retries.
9. Meter per channel with `-subaccount-<client>-li` / `-wa` labels.
10. Measure the first two accounts for two weeks and replace these estimates with real
    `used_bytes` from Massive.

### 15.5 Pricing implication

Price seats flat, with a **fair-use policy** — not a GB allowance. The customer buys a
seat, not a proxy or a bandwidth bucket; the proxy topology (shared vs separate) is an
internal risk/cost decision.

Use the internal soft/hard review thresholds to catch outliers. If a client consistently
exceeds the hard threshold, the options are:

1. reduce WhatsApp media / add resource blocking,
2. move them to a higher-touch plan or custom pricing,
3. ask them to use a BYO proxy,
4. or throttle non-essential resources under the fair-use clause.

Review the internal averages after the first 10 paying seats and adjust the seat price or
the thresholds — not the customer-facing model.
