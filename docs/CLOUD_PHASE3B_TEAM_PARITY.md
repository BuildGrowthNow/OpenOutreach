# Phase 3B — Desktop Parity, Org Channels, and Admin Org Detail

Status: implemented on branch `feature/cloud-phase3a-orgs-team-seats`  
Date: 2026-11-19  
Scope owner: platform

Phase 3B completes the team workspace rollout. Team-member pricing remains an
explicit product decision and was not implemented or changed.

## 1. Desktop enrollment parity

- Enrollment codes are created with the caller's active `org_id`.
- Enrollment authorizes through `profile_authorized_for_tenant`:
  - owner/admin may enroll any desktop profile in the workspace,
  - a member may enroll only a profile assigned to them,
  - cloud LinkedIn profiles are rejected (server-owned),
  - cloud WhatsApp profiles are rejected until Phase 4 proxy support.
- Device rows store `org_id`, `local_ip`, profile/channel bindings, and the
  enrolling `user_id`.
- Owners/admins see every device in the active workspace; members see their own.
- Device revocation is org-scoped and revokes the device's refresh families.
- `POST /api/daemon/v2/devices/heartbeat` records `last_seen_at` and the local
  egress IP for display/support only. It is never used for authorization.
- Desktop devices never receive proxy credentials. The daemon configuration and
  task snapshots remain allowlisted and proxy-free.

## 2. Cloud daemon

- Runs only `execution_mode="cloud"` profiles.
- Requires a valid seat and a proxy; profiles without a proxy are skipped and
  logged instead of using the server IP.
- Enforces the org owner's `1 + cloud_profiles` seat pool across the workspace.

## 3. Org-owned mailboxes and WhatsApp

- `whatsapp_profiles` and `mailboxes` now carry `org_id`, `assigned_user_id`,
  `seat_id`/`managed` (mailboxes), execution mode and proxy placeholders
  (WhatsApp).
- Reads/writes use `channel_access_query` / `can_access_channel_doc`:
  owner/admin see all workspace rows; members see assigned rows; legacy personal
  rows stay visible to their owner.
- New rows set `user_id` to the workspace accounting owner and
  `assigned_user_id` to the creator, so owner-scoped schedulers keep working
  while member visibility stays narrow.
- Desktop WhatsApp is the only supported execution mode; cloud WhatsApp proxy is
  Phase 4.
- The backfill (`backfill_personal_orgs`) now also backfills org/assignee fields
  for WhatsApp profiles and mailboxes.

## 4. Desktop seat assignment

- `POST /api/organizations/{id}/seats/assign-desktop` assigns an org-owned
  desktop profile to an active member.
- Desktop assignment does not consume a cloud seat, does not change the proxy,
  and is audited as `seat.assign` with `seat_type=desktop`.
- Settings → Team shows cloud and desktop profile assignment separately.

## 5. Admin organization detail

`GET /api/admin/organizations/{id}` now returns:

- organization plan/seats/limits,
- active members,
- profiles with execution mode/assignee/proxy flag,
- proxies with provider/status/region/cumulative usage/limit/access/mismatch,
- usage totals per channel and proxy alerts,
- recent audit events.

Seat overrides remain audited and do not change Stripe.

## 6. Marketing and support

- Pricing page adds a team section and desktop vs cloud comparison.
- Team FAQ explains shared billing, assignment, and no proxy on desktop.
- Plan emails soften team claims to “shared team workspace (rollout)” until
  team-member pricing is approved.
- Support runbook: `docs/SUPPORT_TEAM_PROXY_RUNBOOK.md`.

## 7. Team-member pricing

**Decision (2026-11-19): member logins are included in the current plan during
rollout.** A member login does not include a browser account, proxy, or email
slot; those remain seat-priced. There is no per-member charge and no
free-up-to-3 metering in this phase.

No Stripe price, product, subscription item, or customer-facing price was
changed. Revisit this decision before Phase 4 using real workspace usage; any
future per-member price requires explicit product approval and Stripe work.

## 8. Validation

```text
.venv\Scripts\python.exe -m pytest tests -q
# 575 passed, 56 skipped

ruff E9,F63,F7,F82, compileall, pyright
# clean

cd frontend
eslint, tsc --noEmit, next build
# passed
```

Unit tests cover org channel visibility, desktop-only enrollment, cross-tenant
denial, desktop seat assignment without cloud-seat consumption, org device
scope, and org-member task ownership scope. Live desktop builds/signing and
notarization remain a release task outside this branch.

## 9. Known limitations

- One active organization per user.
- Org-member desktop task execution relies on the device/profile binding; task
  ownership remains with the workspace owner for CRM projections.
- WhatsApp cloud proxy and managed email are Phase 4.
- Team-member pricing and Stripe changes are not part of this phase.

## 10. Rollback

- `TEAM_WORKSPACES_ENABLED=false`: hide team surfaces, fall back to personal
  workspaces/billing, keep all org data and device rows.
- `MANAGED_PROXIES_ENABLED=false`: keep proxy fields/records for audit; cloud
  profiles without a proxy do not launch.
- `CLOUD_SEATS_ENABLED=false`: hide seat UI; keep existing assignments.
