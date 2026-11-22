# Phase 4 — Cloud Channel Bundles (WhatsApp, Duo, Email BYO)

Status: implemented, tested, deployed, and enabled for the owner's live test
Date: 2026-11-21  
Scope owner: platform + product

Phase 4 completes the cloud channel bundle: unified cloud seat accounting for
LinkedIn and WhatsApp, channel-aware managed proxy provisioning, WhatsApp-only
cloud seats, separate-IP Cloud Duo, per-channel usage attribution, and the BYO
email slot. Prices, Stripe products, DNS, and the tracking Worker are unchanged.

## 1. Product rule

A cloud seat is **one browser account**: one cloud LinkedIn profile **or** one
cloud WhatsApp number, plus one email slot and one proxy identity.

| Bundle | Browser accounts | Email slot | Proxy identities | Seats |
|---|---|---|---|---|
| Cloud Solo | 1 LinkedIn or 1 WhatsApp | 1 BYO SMTP/IMAP | 1 managed | 1 |
| Cloud Duo · Shared IP | 1 LinkedIn + 1 WhatsApp (same identity) | 1 BYO SMTP/IMAP | 1 shared managed | 1 |
| Cloud Duo · Separate IP | 1 LinkedIn + 1 WhatsApp (same identity) | 1 BYO SMTP/IMAP | 2 managed | 1 |
| WhatsApp-only cloud | 1 WhatsApp | 1 BYO SMTP/IMAP | 1 managed | 1 |
| Desktop | 1 LinkedIn or 1 WhatsApp | 1 BYO SMTP/IMAP | Local IP, none | Included in plan |

Rules:

- Count active **and paused** credentialed accounts.
- Release a seat only when the profile/credential is deleted.
- Pausing, seat removal, cancellation, member removal, and payment dunning never
  release a seat.
- A shared-IP Duo WhatsApp number shares the LinkedIn unit; deleting only the
  WhatsApp number does not release the seat. Deleting the LinkedIn profile while
  the WhatsApp number remains also keeps the seat (the WhatsApp number becomes
  its own unit).
- A separate-IP Duo still uses one seat but two proxy sub-accounts.
- Team members count against the workspace owner's pool.
- Cloud profiles never run on the server IP.

## 2. Flags

```text
WHATSAPP_CLOUD_PROXY_ENABLED=true
DAEMON_V2_WHATSAPP_ENABLED=true
CLOUD_SEATS_ENABLED=true
MANAGED_PROXIES_ENABLED=true
TEAM_WORKSPACES_ENABLED=true
MASSIVE_POOL_STATS_ENABLED=true
MASSIVE_REPORTING_ENABLED=true
MASSIVE_RESELLER_ENABLED=false   # first owner live test uses the Phase 1 fallback
```

`WHATSAPP_CLOUD_PROXY_ENABLED` is the product gate; `DAEMON_V2_WHATSAPP_ENABLED`
is the server-WA runtime opt-in. Both are required for cloud WhatsApp creation
and for the cloud daemon to launch a WhatsApp session. Disabling either flag
keeps all data, proxies, and sub-accounts; it never deletes them.

`MASSIVE_RESELLER_ENABLED` gates Reseller provisioning, admin lifecycle
(disable/enable/rotate), and usage sync for Reseller sub-accounts. When it is
off, new profiles use the Phase 1 parent fallback; existing sub-accounts stay
assigned and disabled as needed. Re-enable it only after the owner's real cloud
profile has passed provisioning, assignment, egress, disable/enable, password
rotation, and launch.

## 3. Unified seat accounting

`openoutreach/billing/cloud_seats.py`

- Counter collection: `cloud_seat_usage`, keyed by the accounting owner (the
  organization owner). Personal users use their own user id.
- `reserve_cloud_seat(user_id, limit)` heals the counter upward from real rows,
  then performs one conditional `find_one_and_update` so concurrent requests
  cannot both pass the limit check.
- `release_cloud_seat(user_id)` is called only after a credential/profile
  delete or a failed create rollback.
- `reconcile_cloud_seat_usage(user_id)` rebuilds one counter.
- `python -m openoutreach.migrations.reconcile_cloud_seats` is an idempotent
  dry-run/`--apply` backfill for every accounting owner.
- Unit keys are `li:<profile_id>` for a LinkedIn seat and `wa:<profile_id>` for
  a standalone WhatsApp seat. A WhatsApp number with the same `identity_id` as
  a credentialed cloud LinkedIn profile shares the `li:` unit (Duo).
- The cloud daemon runs only the first `limit` units by creation order when a
  workspace is over its pool; paused accounts still consume their unit.

LinkedIn creation reserves both the existing LinkedIn account counter and the
unified cloud seat, so desktop limits and billing do not regress. WhatsApp-only
cloud creation reserves the unified seat. Duo creation reserves no second seat.

## 4. Channel-aware managed proxies

`openoutreach/proxies/provisioning.py`, `massive_client.py`, `service.py`

Reseller sub-usernames:

```text
LinkedIn:  outreach.<org>.li.<profile>
WhatsApp:  outreach.<org>.wa.<profile>
```

Phase 1 fallback usernames:

```text
LinkedIn:  <parent>-subaccount-li-<profile>-country-US-session-...
WhatsApp:  <parent>-subaccount-wa-<profile>-country-US-session-...
```

Rules enforced in code:

- One active proxy per profile.
- At most one LinkedIn account per proxy.
- At most one WhatsApp number per proxy.
- A proxy may serve one LinkedIn + one WhatsApp only when they share the same
  `identity_id` (Cloud Duo shared IP).
- Never assign a used proxy to a different identity, LinkedIn account, or
  WhatsApp number.
- Store the proxy on the correct collection (`linkedin_profiles` or
  `whatsapp_profiles`).
- Disable on seat cancellation/unassignment; keep the sub-account bound to the
  same profile through `last_assigned_*` fields; retire only on profile
  deletion.
- Shared Duo proxy deletion: deleting the LinkedIn profile detaches the
  LinkedIn link but keeps the proxy for WhatsApp; deleting the WhatsApp number
  detaches the WhatsApp link but keeps the proxy for LinkedIn.
- Passwords are encrypted at rest and never returned by an API or written to a
  log.

Admin endpoints support both channels:

```text
GET  /api/admin/proxies/whatsapp-profiles
POST /api/admin/proxies/{proxy_id}/assign          {profile_id, channel}
POST /api/admin/proxies/{proxy_id}/unassign
POST /api/admin/proxies/{proxy_id}/disable|enable|retire|rotate
POST /api/admin/proxies/massive/provision          {profile_id, channel}
```

## 5. WhatsApp-only cloud seats

`POST /api/whatsapp/profiles` accepts:

```json
{
  "display_name": "Acme WhatsApp",
  "execution_mode": "cloud",
  "cloud_mode": "whatsapp_only",
  "proxy_region_country": "US",
  "proxy_region_subdivision": "NY",
  "proxy_region_city": "New York"
}
```

- Creates a cloud WhatsApp profile with no LinkedIn account.
- Consumes one unified cloud seat.
- Provisions its own managed WhatsApp proxy and sub-account.
- The QR is stored in the DB and served by the API; the headless cloud daemon
  uses it.
- The cloud daemon runs it only when the seat is within the workspace pool and
  the proxy is healthy.
- The server IP is never used. A missing/disabled proxy raises
  `WhatsAppCloudProxyError` and the browser is closed.
- Desktop WhatsApp remains local-IP with no proxy.

## 6. Separate-IP Cloud Duo

`cloud_mode: "duo_separate"` with `duo_linkedin_profile_id`:

- Same identity, same seat, two proxy identities.
- LinkedIn keeps its existing proxy; WhatsApp gets its own proxy/sub-account.
- One seat, two proxies.
- Per-channel usage is separate because each channel has its own sub-account.
- Customer-facing price remains **$299/seat**. Separate IP is a
  support/configuration choice, not a price change. No Stripe product or price
  was created or changed.

## 7. Per-channel usage attribution

- `proxies.channel` is `linkedin`, `whatsapp`, or `duo` (shared).
- Reporting/cumulative sync records the proxy's channel.
- Separate-IP Duo and WhatsApp-only have distinct sub-accounts, so
  `group_by=subaccount` shows each channel separately.
- Shared-IP Duo has one sub-account by definition. Its usage is recorded as
  `duo` and shown as **combined Duo usage**. The UI never claims a per-channel
  split that the provider cannot supply.
- Admin → Proxies → Usage shows per proxy, per profile, per workspace, per
  channel, and per workspace/channel.
- Admin → Organizations shows per-channel usage and unified seat usage.
- Usage remains internal. There is no customer-facing GB meter, allowance,
  overage rate, or "included bandwidth" claim.

## 8. Email BYO slot

Phase 4 email is BYO SMTP/IMAP, not managed email.

- One email slot per seat, org-scoped and assigned to a member.
- Email never uses a browser proxy.
- No managed mailbox provisioning, domain purchase, warmup, or deliverability
  service.
- The slot limit is `cloud_seat_limit` for the Cloud plan, otherwise the larger
  of the LinkedIn/WhatsApp desktop allowances and any granted cloud seats.
- `POST /api/mailboxes` enforces the limit and writes `seat_id` plus
  `managed=false`.
- Settings → Email shows `used of limit` slots and the copy: "Connect your own
  SMTP/IMAP mailbox; no proxy."
- Existing mailbox verification (SMTP auth plus optional IMAP auth) is
  unchanged.

## 9. Frontend and onboarding

- Settings → WhatsApp: Desktop, Cloud Duo · Shared IP, Cloud Duo · Separate IP,
  WhatsApp-only cloud. Region inputs appear for WhatsApp-only and separate IP.
- Cards show `Desktop · Local IP · No proxy`, `Cloud Duo · Shared IP · Managed
  proxy · US`, `Cloud Duo · Separate IP · Managed proxy · US`, or
  `WhatsApp-only cloud · Managed proxy · US`.
- Dashboard channel bundle card shows LinkedIn → WhatsApp → email, cloud seats
  used, and email slots used.
- Settings → Email shows the BYO slot and no-proxy copy.
- Settings → Team assigns cloud LinkedIn and WhatsApp accounts with channel
  badges.
- Marketing `/pricing`, `/cloud`, and `/teams` describe the shipped bundles,
  the "What's in a seat?" table, Shared vs Separate IP, WhatsApp-only cloud,
  BYO email, and the no-GB-meter policy.
- Desktop is a webview and inherits these pages. Desktop WhatsApp and email run
  locally with the local IP and no proxy. Desktop profiles never receive proxy
  credentials. The API changes are additive; desktop 2.1.8 remains compatible,
  so no version bump or force-update gate was needed.

## 10. Admin and support

- Admin → Proxies: channel filter/column, LinkedIn and WhatsApp assignment,
  lifecycle, health, per-channel usage, Reseller sub-accounts with channel, and
  internal alerts.
- Admin → Organizations: unified seats, channel bundles (LinkedIn, Duo,
  WhatsApp-only), members, profiles, proxies, per-channel usage, audit, and
  seat-over-limit alerts.
- Alerts include WhatsApp proxy unavailable, disabled proxies, country
  mismatch, `limit_reached`, `proxy_access=false`, and seat over-limit.
- No password, key, cookie, or token is displayed.

## 11. Validation

```text
.venv\Scripts\python.exe -m pytest tests -q
# 641 passed, 56 skipped

.venv\Scripts\python.exe -m pytest tests/test_cloud_phase4_complete.py -q
# 37 passed

ruff E9,F63,F7,F82; compileall; pyright on changed modules
# clean

cd frontend
eslint; tsc --noEmit; next build
# passed
```

Tests cover:

- unified seat units for Solo, shared Duo, separate Duo, WhatsApp-only;
- paused accounts, deletion, member removal, reconciliation, and over-limit
  daemon filtering;
- atomic reservation and org-scoped member accounting;
- channel-aware Reseller/fallback usernames;
- WhatsApp proxy assignment, one-WA-per-proxy, shared-identity rules, unassign
  retention, and deletion retirement;
- WhatsApp-only, shared Duo, and separate Duo creation;
- launch guards and daemon readiness for WhatsApp-only/shared Duo;
- per-channel vs combined usage;
- email slot limits and BYO/no-proxy storage;
- no credentials in public proxy or WhatsApp responses.

The 56 skips are the pre-existing Mongo integration tests that require a
database whose name ends in `_test`. The protected workflow's pre-existing
Mongo failures were not masked.

## 12. Rollout

1. Deploy the API and web with `WHATSAPP_CLOUD_PROXY_ENABLED=false` and
   `DAEMON_V2_WHATSAPP_ENABLED=false`.
2. Validate `/api/health`, the web root, `/cloud`, `/teams`, `/pricing`, and
   `scalingo ps` (exactly one `daemon` and one `web` on `outreach-api`).
3. Enable both WhatsApp flags, plus `TEAM_WORKSPACES_ENABLED`,
   `MASSIVE_POOL_STATS_ENABLED`, `MASSIVE_REPORTING_ENABLED`,
   `CLOUD_SEATS_ENABLED`, and `MANAGED_PROXIES_ENABLED`.
4. Keep `MASSIVE_RESELLER_ENABLED=false` for the owner's first cloud profile;
   the Phase 1 fallback works for the first LinkedIn + WhatsApp test.
5. After the owner's real cloud profile passes provisioning, assignment,
   egress, disable/enable, password rotation, and launch, enable Reseller with
   the owner's confirmation.
6. Run the live checklist in the handoff message.

## 13. Rollback

1. Set `WHATSAPP_CLOUD_PROXY_ENABLED=false` to hide cloud WhatsApp and stop
   cloud WhatsApp sessions. Desktop WhatsApp remains available.
2. Set `DAEMON_V2_WHATSAPP_ENABLED=false` to stop server WhatsApp sessions.
3. Keep `CLOUD_SEATS_ENABLED` / `MANAGED_PROXIES_ENABLED` off to hide seat and
   proxy operations; existing assignments and data remain.
4. Do not delete profiles, proxies, sub-accounts, or counters. Disable, do not
   delete.
5. Re-enable the flags to restore the previous view.

## 14. Explicitly not in this phase

- Managed email provisioning, domain purchase, warmup, or deliverability.
- A second WhatsApp number per Duo seat.
- Customer-facing GB meters, allowances, overage, or bandwidth pricing.
- Stripe price/product changes; Cloud Duo remains $299/seat.
- Team-member pricing changes; member logins remain included during rollout.
- DNS, tracking Worker, staging database, or Phase 5 work.
