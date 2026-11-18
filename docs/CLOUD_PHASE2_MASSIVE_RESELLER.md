# Phase 2 — Massive Reseller, Usage, and Internal Budgets

Status: implemented on branch `feature/cloud-phase3a-orgs-team-seats`  
Date: 2026-11-19  
Scope owner: platform

This document records the Phase 2 implementation. It is additive and gated by
`MASSIVE_RESELLER_ENABLED` / `MASSIVE_POOL_STATS_ENABLED`. No production
sub-account was created and no production deploy was performed.

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
- Sub-username: `outreach-<org>-li-<profile>` (hyphens only; the parent/sub
  separator is `_`).
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
# 574 passed, 56 skipped

.venv\Scripts\python.exe -m pytest tests/test_cloud_phase0.py tests/test_cloud_phase1.py -p no:asyncio -q
# 64 passed

ruff E9,F63,F7,F82, compileall, pyright
# clean
```

Phase 2 unit tests use an in-memory Mongo fake and a fake HTTP client. No live
Massive call was made. The protected workflow's pre-existing Mongo integration
failures from `main` were not chased or masked.

## 10. Rollback

1. Set `MASSIVE_RESELLER_ENABLED=false`.
2. New profiles fall back to the Phase 1 parent credentials.
3. Keep sub-accounts disabled/assigned; do not delete them.
4. Set `MASSIVE_POOL_STATS_ENABLED=false` to hide region availability calls.
5. Keep `massive_*` proxy fields and snapshots for audit.

## 11. Deployment gates

Before production enablement:

- approve a live Reseller pilot with two internal cloud profiles,
- verify `409` adoption, disable/enable, rotate, and top-up on the live API,
- confirm no password appears in API responses, logs, or audit metadata,
- dry-run the usage sync and budget thresholds with internal accounts,
- confirm `outreach-api` remains at exactly one daemon container,
- keep both Massive flags false until the pilot and explicit approval.
