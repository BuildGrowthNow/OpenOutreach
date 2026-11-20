# Phase 2 — Massive Reseller, Usage, and Internal Budgets

Status: implemented, merged, deployed, and live-pilot verified  
Date: 2026-11-20  
Scope owner: platform

This document records the Phase 2 implementation. It is additive and gated by
`MASSIVE_RESELLER_ENABLED` / `MASSIVE_POOL_STATS_ENABLED`. The code is deployed
to production. `MASSIVE_POOL_STATS_ENABLED=true`; `MASSIVE_RESELLER_ENABLED`
remains false pending a real internal cloud-profile provisioning test. The
2026-11-20 pilot created only synthetic sub-accounts, all of which were disabled
and verified, and did not assign a proxy to a production profile.

## 1. Goal

One Massive Reseller sub-account per cloud seat/profile, provisioned
automatically, with cumulative usage sync and internal monthly budgets. The
customer confirms a country; the backend creates the sub-account, assigns the
proxy, and tests the egress country. Customers never configure or see proxy
credentials or a GB meter.

## 2. Configuration

Server-side only. Never commit real values or print them in logs/evidence.

```text
MASSIVE_RESELLER_ENABLED=false
MASSIVE_RESELLER_API_KEY=            # optional alias; falls back to MASSIVE_PROXY_PASSWORD
MASSIVE_RESELLER_BASE_URL=https://api-network.joinmassive.com/resellers
MASSIVE_POOL_STATS_ENABLED=false
MASSIVE_POOL_STATS_API_KEY=          # optional alias; falls back to MASSIVE_PROXY_PASSWORD
MASSIVE_POOL_STATS_BASE_URL=https://api-network.joinmassive.com/pool-stats
MASSIVE_RESELLER_DEFAULT_LIMIT_BYTES=5000000000
MASSIVE_MONTHLY_SOFT_LIMIT_BYTES=25000000000
MASSIVE_MONTHLY_HARD_LIMIT_BYTES=40000000000
MASSIVE_POOL_STATS_MIN_NODES=1000
```

The Reseller, Reporting, and Pool Stats APIs use `x-api-key`; the account API
key (`MASSIVE_PROXY_PASSWORD`) authenticates all three. Dedicated key variables
are optional aliases, never requirements.

## 3. Clients

`openoutreach/proxies/massive_reseller.py`

- `MassiveResellerClient`
  - `list_accounts()` — passwords always stripped
  - `find_account_by_username(..., include_password=True)` — internal
    provisioning only; never returned by an API
  - `create_account(username, password, limit, sync_with_parent)`
  - `get_account`, `update_account`, `enable_account`, `disable_account`
  - `allocate_traffic(account_id, bytes)`
  - `set_session_limits(...)`
  - `get_account_usage(account_id, daily=False)`
  - `reporting_usage(group_by=...)`
  - `parent_usage()` — local aggregate of the sub-account list
- `MassivePoolStatsClient`
  - `regions()`, `live(country, group_by)`, `country_counts()`,
    `city_counts(country)`, `warnings(country)`
  - 1-hour in-process cache
  - sends `Accept-Encoding: gzip`
  - warns below `MASSIVE_POOL_STATS_MIN_NODES` and blocks city targeting below
    the same threshold via `is_city_safe`

No response body is logged. HTTP failures report only the status code.

## 4. Provisioning

`openoutreach/proxies/provisioning.py`

- `provision_managed_proxy(...)` prefers Reseller, then falls back to the Phase 1
  parent `-subaccount` credentials when Reseller is disabled or unavailable.
- Sub-username: `outreach.<org>.li.<profile>` (dot-separated). The live Reseller
  API accepts only `a-z A-Z 0-9 @ .` in the account username; hyphens and
  underscores are rejected with HTTP 400. The parent/sub separator in the proxy
  auth username remains `_`.
- Password: `secrets.token_urlsafe(36)`, encrypted in the proxy record.
- Conservative default lifetime limit; top up from the admin Massive tab.
- `409 already_exists`: fetch the existing account instead of retrying create.
  If the provider does not return its password, provisioning stops with a clear
  error and support rotates it; it never guesses.
- The proxy is assigned only after the sub-account exists. If assignment fails,
  the sub-account is disabled and the local proxy is retired.
- `linkedin_credentials.create_credential` calls this path for new cloud
  profiles. The old pre-check that blocked fallback when inventory was empty was
  removed.

## 5. Lifecycle

- Seat cancellation / unassignment / member removal / seat-limit reduction:
  disable the sub-account, keep it bound to the same profile, keep the proxy.
- Re-adding the same profile to a seat: re-enable only that sub-account.
- Profile deletion: disable the sub-account, mark `massive_status=retired`, and
  retire the local proxy. Never delete or reuse it.
- Budget hard limit: disable with `massive_status=budget_disabled`; re-enable
  next month when under the soft threshold, or by an admin after review.
- `MASSIVE_RESELLER_ENABLED=false`: new profiles use the Phase 1 fallback;
  existing sub-accounts stay assigned/disabled and are not deleted.

## 6. Usage and budgets

Daily `sync_massive_accounts()`:

- `GET /resellers/accounts` for cumulative `used_bytes`, `limit`, `limit_reached`,
  `proxy_access`, and status.
- Updates the proxy fields and writes `massive_usage_snapshots`.
- Never stores or returns passwords.
- Aggregates parent plan usage locally.

Reporting sync:

- `group_by=subaccount` first; `group_by=subuser` fallback.
- Writes `proxy_usage_snapshots` through the existing Phase 1 recorder.

Budgets:

- Soft/hard thresholds are internal only.
- Hard threshold disables the sub-account and audits
  `proxy.budget_disable`.
- New month re-enables under soft and audits `proxy.budget_enable`.
- Soft threshold audits `proxy.budget_soft`.
- No customer-facing GB allowance, meter, or overage.

Cron: `python -m openoutreach.cli sync-proxy-usage` at 01:45 UTC. When Reseller
is available it runs the cumulative sync + reporting sync + budget enforcement;
otherwise it keeps the Phase 1 Reporting-only path.

For a production threshold review without disabling or re-enabling a live
sub-account, run the same sync with `--dry-run`:

```text
python -m openoutreach.cli sync-proxy-usage --dry-run
```

It updates cumulative/Reporting usage and prints projected `disable`,
`re_enable`, and `soft_alert` counts. It never calls the provider enable/disable
endpoints and never writes budget audit events. Use the normal command only
after the projection is reviewed.

## 7. Admin

`/api/admin/proxies` (admin only):

```text
GET  /massive/status
GET  /massive/accounts
GET  /massive/alerts
POST /massive/sync
POST /massive/provision
POST /massive/{proxy_id}/disable
POST /massive/{proxy_id}/enable
POST /massive/{proxy_id}/rotate
POST /massive/{proxy_id}/allocate
GET  /pool-stats
GET  /pool-stats/regions
```

Provision, sync, rotate, and allocate are rate-limited. Audit events:
`proxy.provision`, `proxy.massive_sync`, `proxy.massive_disable`,
`proxy.massive_enable`, `proxy.massive_rotate`, `proxy.massive_allocate`,
`proxy.budget_disable`, `proxy.budget_enable`, `proxy.budget_soft`.

The admin Proxies → Massive tab shows connection status, parent usage,
sub-account table, Sync now, Provision for profile, Disable/Enable/Rotate/Top up,
alerts, and Pool Stats. Passwords and keys are never displayed.

## 8. Customer surfaces

- Cloud account form: country required; state/city optional. Copy warns that a
  region change changes the egress IP and may trigger a LinkedIn challenge.
- Settings → LinkedIn: execution mode and managed proxy health/status only; no
  credentials, no GB meter.
- Desktop: "Local IP · No proxy"; desktop profiles are not selectable for cloud
  enrollment and never receive proxy credentials.
- Marketing: "195+ countries", region selection, "Powered by the Massive
  residential network", and a sticky-session/IP-change FAQ. US static ISP is not
  offered until the pilot passes.

## 9. Validation

```text
.venv\Scripts\python.exe -m pytest tests -q
# 591 passed, 56 skipped

.venv\Scripts\python.exe -m pytest tests/test_cloud_phase0.py tests/test_cloud_phase1.py -p no:asyncio -q
# 64 passed

ruff E9,F63,F7,F82, compileall, pyright
# clean
```

### 9.1 Live pilot — 2026-11-20

Production had no cloud profiles at pilot time, so the operator approved a
synthetic two-sub-account pilot rather than creating temporary profile fixtures.
The pilot ran in a one-off `outreach-api` container with
`MASSIVE_RESELLER_ENABLED=true` and `MASSIVE_POOL_STATS_ENABLED=true` injected
only for that container; the persistent app flags stayed false.

Verified live:

- `POST /resellers/accounts` created two sub-accounts.
- A duplicate create returned `409`; the full parent-prefixed username from
  `GET /accounts` was matched back to the sub-account, and its password was
  readable for adoption.
- `POST /accounts/{id}/disable` and `POST /accounts/{id}/enable` changed the
  provider state; the account list showed `disabled`/`proxy_access=false` and
  then `enabled`/`proxy_access=true`.
- `POST /accounts/{id}/allocations` with `{"limit": ...}` raised the cumulative
  limit from 5 GB to 6 GB.
- `PUT /accounts/{id}/session-limit` accepted
  `session_traffic_limit="100mb"` and `session_duration_limit="15m"`.
- `GET /accounts/{id}` and `/usage` returned cumulative usage and the updated
  limit.
- Reporting returned the same usage for `group_by=subaccount` and
  `group_by=subuser` (fallback path works).
- Pool Stats returned gzip-backed data, 223 countries, ~353k US nodes, ~4,957
  US cities, and New York at ~3,093 nodes; city targeting was safe at the
  1,000-node threshold.

All four pilot sub-accounts (two from the first successful pass, two from the
final pass) were verified `disabled` with `proxy_access=false` and zero usage.
No key, password, cookie, or token was printed. The pilot did not assign a proxy
to any production profile and did not enable customer-facing flags.

Phase 2 unit tests use an in-memory Mongo fake and a fake HTTP client. The
protected workflow's pre-existing Mongo integration failures from `main` were
not chased or masked.

## 10. Rollback

1. Set `MASSIVE_RESELLER_ENABLED=false`.
2. New profiles fall back to the Phase 1 parent credentials.
3. Keep sub-accounts disabled/assigned; do not delete them.
4. Set `MASSIVE_POOL_STATS_ENABLED=false` to hide region availability calls.
5. Keep `massive_*` proxy fields and snapshots for audit.

## 11. Deployment gates

Before production enablement:

- live API-shape pilot completed on 2026-11-20 with two synthetic sub-accounts
  (no production cloud profiles existed); real profile provisioning and
  password rotation still need the first real cloud seat,
- `409` adoption, disable/enable, allocation/top-up, session limits, usage,
  Reporting, and Pool Stats are verified live,
- confirm no password appears in API responses, logs, or audit metadata,
- dry-run the usage sync and budget thresholds with internal accounts,
- confirm `outreach-api` remains at exactly one daemon container,
- keep `MASSIVE_RESELLER_ENABLED=false` until a real internal cloud profile
  exercises provisioning, assignment, and password rotation;
  `MASSIVE_POOL_STATS_ENABLED` is enabled as of 2026-11-20.
