# Phase 3A — Organizations, Team Roles, and Cloud Seats

Status: implemented, merged, and deployed; `TEAM_WORKSPACES_ENABLED=true`
in production since 2026-11-20  
Date: 2026-11-20  
Scope owner: platform + product

This document records the Phase 3A implementation of the Cloud/Teams rollout.
It deliberately excludes team-member pricing, desktop enrollment parity, and
Phase 4 channel bundles.

## 1. Goal and scope

A workspace owner can:

- invite members by email,
- assign owner/admin/member roles,
- share one billing relationship and one cloud seat pool,
- assign a cloud LinkedIn profile/seat to a member,
- remove a member or seat without deleting profile data or recycling proxies.

A member:

- inherits the owner's plan and seat pool,
- sees only the profiles and campaigns assigned to them,
- cannot view or edit managed proxy credentials,
- cannot manage billing.

## 2. Feature flag

`TEAM_WORKSPACES_ENABLED` (default `false`)

- Backend gates team APIs and resolves effective billing through the personal
  organization when disabled.
- Frontend hides the Team navigation, Team settings tab, org switcher, and
  team management controls when the capability response reports `false`.
- Disabling never deletes organizations, memberships, invites, profiles, or
  audit data.

Related settings:

```text
ORGANIZATION_INVITE_EXPIRY_DAYS=7
ORGANIZATION_INVITE_RATE_LIMIT=30
ORGANIZATION_INVITE_RATE_WINDOW_SECONDS=3600
ORGANIZATION_ACCEPT_RATE_LIMIT=30
ORGANIZATION_ACCEPT_RATE_WINDOW_SECONDS=3600
```

`CLOUD_SEATS_ENABLED` and `MANAGED_PROXIES_ENABLED` remain the backend gates for
seat purchase UI and proxy operations.

## 3. Data model

New collections:

- `organizations`
- `organization_members`
- `organization_invites`
- `organization_audit_logs`
- `organization_rate_limit_events`

New fields:

- `users.org_id` (active organization; already existed, now populated)
- `users.pending_org_invite_hash` (new-user invite acceptance after email verification)
- `linkedin_profiles.org_id`
- `linkedin_profiles.assigned_user_id`
- `campaigns.org_id`

Indexes are added in `openoutreach/mongodb/indexes.py` for organization ownership,
membership uniqueness, invite token hash, audit queries, rate limits, profile
org/assignee lookups, and campaign org lookups.

## 4. Personal organizations and backfill

Every user receives a personal organization:

- created at registration,
- healed at login and `/api/auth/me`,
- backfilled for existing users by
  `python -m openoutreach.migrations.backfill_personal_orgs` (dry-run by default;
  `--apply` to persist).

The migration is additive and idempotent. It:

1. creates one personal org per user,
2. sets `User.org_id` only when missing or invalid (never steals an active team org),
3. creates the owner membership,
4. backfills `linkedin_profiles.org_id` and `assigned_user_id`,
5. backfills `campaigns.org_id`.

## 5. Roles and permissions

| Capability | Owner | Admin | Member |
|---|---|---|---|
| View billing | yes | yes | no |
| Change plan/seats | yes | no | no |
| Invite/remove members | yes | yes | no |
| Change roles | yes | no | no |
| Assign seats | yes | yes | no |
| Manage proxies | yes | yes | no |
| View all org profiles/campaigns | yes | yes | no |
| Create/edit assigned profiles | yes | yes | assigned only |
| Delete profiles | yes | yes | no |
| Create/edit own campaigns | yes | yes | yes |

## 6. Invite flow

- Owner/admin creates an invite by email with role `member` or `admin`.
- Token: `secrets.token_urlsafe(32)`, stored only as SHA-256.
- Expiry: 7 days by default.
- One active invite per email/org; older pending invites are revoked.
- Acceptance consumes the token atomically and verifies the signed-in email.
- Existing users join immediately.
- New users can register with `invite_token`; the invite is consumed after
  email verification via `pending_org_invite_hash`.
- Creation and acceptance are rate-limited.
- Audit events: `org.invite`, `org.accept`.

## 7. Effective plan and seat accounting

- `openoutreach/organizations/enforcement.py` resolves the active org and returns
  the owner's plan, cloud seat pool, LinkedIn/WhatsApp limits, campaign limit,
  subscription state, and billing owner.
- `openoutreach/billing/seats.py` keys the `linkedin_seat_usage` counter by the
  accounting owner (the org owner). Personal users keep their existing counter id.
- Counts include every credentialed profile, active or paused.
- Reservation remains a single conditional MongoDB update and heals upward from
  real credentialed counts.
- A seat is released only when the profile/credential is deleted.
- The cloud daemon groups active cloud profiles by billing owner and enforces
  `1 + cloud_profiles` per workspace.

## 8. Seat assignment and removal

- Only cloud LinkedIn profiles can be assigned to a cloud seat.
- Only active members of the same org can receive a seat.
- Assignment is org-scoped and audited (`seat.assign`).
- Unassign/remove pauses the profile, clears `assigned_user_id`, and keeps the
  proxy assigned (`seat.unassign`, `seat.remove`).
- Removing a member pauses their assigned profiles, keeps proxies, returns the
  member to their personal org, and audits `org.remove` plus `seat.remove`.
- Profile deletion retires the proxy through the existing Phase 1 path.

## 9. API surface

User/team:

```text
GET    /api/organizations
GET    /api/organizations/current
POST   /api/organizations/{id}/activate
PATCH  /api/organizations/{id}
GET    /api/organizations/{id}/members
GET    /api/organizations/{id}/invites
POST   /api/organizations/{id}/invites
DELETE /api/organizations/{id}/invites/{invite_id}
GET    /api/organizations/invites/{token}
POST   /api/organizations/invites/{token}/accept
PATCH  /api/organizations/{id}/members/{user_id}
DELETE /api/organizations/{id}/members/{user_id}
GET    /api/organizations/{id}/seats
POST   /api/organizations/{id}/seats/assign
POST   /api/organizations/{id}/seats/unassign
POST   /api/organizations/{id}/seats/remove
GET    /api/organizations/{id}/profiles
GET    /api/organizations/{id}/audit
```

Admin:

```text
GET   /api/admin/organizations
GET   /api/admin/organizations/{id}
PATCH /api/admin/organizations/{id}/seats
```

## 10. Frontend

- `Settings → Team` page: members, invites, roles, seat assignment, recent audit.
- `Team` sidebar item and Settings tab appear only when the capability flag is on.
- Workspace switcher in the header (personal org + shared workspaces).
- Billing page hides checkout/portal/seat controls for members and explains that
  the owner pays.
- Invite acceptance page at `/team/accept?token=...`.
- Signup supports `invite_token` and prefilled invited email.
- Admin → Organizations page: owner, plan, members, seats, profiles, audit, and
  audited seat override.

## 11. Security and tenant isolation

- Profile list/get/update/delete/cookies/proxy endpoints use org-scoped queries.
- Credential list/get/update/delete/verify/confirm/rotate/health/logs authorize
  through the credential's profile and org membership.
- Campaign list/read/update/delete use org-aware access helpers; team sharing is
  limited to active workspace members.
- VNC and rate-limit profile endpoints use org-scoped profile access.
- Daemon v2 enrollment requires an existing profile in the caller's scope;
  task claims and lease mutations re-check that the profile is still assigned.
- Managed proxy credentials remain masked/read-only; members cannot edit or test
  proxies.
- Invite tokens are hashed, single-use, expiring, and never logged.
- Audit metadata drops secret-bearing keys.
- Admin organization routes require `get_admin_user`; seat overrides are audited.

## 12. Validation performed

```text
.venv\Scripts\python.exe -m pytest tests -q
# 575 passed, 56 skipped (includes Phase 2 and Phase 3B tests)

.venv\Scripts\python.exe -m pytest tests/test_cloud_phase0.py tests/test_cloud_phase1.py -p no:asyncio -q
# 64 passed

.venv\Scripts\python.exe -m ruff check --select E9,F63,F7,F82 openoutreach linkedin_cli scripts tests
# All checks passed

.venv\Scripts\python.exe -m compileall -q openoutreach
# passed

.venv\Scripts\python.exe -m pyright <Phase 3A modules>
# 0 errors

cd frontend
.\node_modules\.bin\eslint.cmd <Phase 3A files>
.\node_modules\.bin\tsc.cmd --noEmit
.\node_modules\.bin\next.cmd build
# passed
```

The 56 skips are the existing Mongo integration tests that require a database
whose name ends in `_test`. The ten pre-existing Mongo integration failures from
`main` were not masked or modified.

## 13. What is mocked vs live

Live (real code paths):

- MongoDB persistence and queries for all organization/invite/seat operations.
- Stripe billing fields are read from the owner's existing user record; no new
  prices, products, or subscription items were added.
- Proxy assignment/retention uses the existing Phase 1 managed-proxy service.
- Invite email uses the existing email provider abstraction.

Mocked/test-only:

- Unit tests use an in-memory Mongo fake (`tests/fake_mongo.py`).
- No live Stripe checkout or webhook was executed for Phase 3A.
- No live Massive Reseller provisioning was exercised during Phase 3A; the
  later synthetic Phase 2 pilot did not assign a proxy to a profile.
- Production deployment and the additive personal-org backfill were completed
  on 2026-11-20. `TEAM_WORKSPACES_ENABLED=true`.
- Desktop enrollment parity is covered by Phase 3B.

## 14. Known limitations (Phase 3A)

- One active organization per user. The owner's personal organization becomes
  the shared workspace; there is no separate "create organization" endpoint yet.
- Switching to a personal organization hides team-assigned profiles but does not
  migrate them. A member's own personal profiles stay in their personal org.
- Admin seat overrides change the workspace entitlement only; they do not mutate
  Stripe and will appear as reconciliation drift until billing is aligned.
- Desktop enrollment/device revocation and org-owned mailbox/WhatsApp ownership
  are completed in Phase 3B; see `docs/CLOUD_PHASE3B_TEAM_PARITY.md`.
- Invite email delivery depends on the configured email provider. In local/dev
  (`DEBUG=true`) the invite URL is returned for testing; production never returns
  the raw token.

## 15. Explicitly out of scope

- Team-member pricing (free up to 3, then $29/mo) and any price change.
- Desktop enrollment, device list/revocation, desktop daemon parity.
- Org ownership of mailboxes and WhatsApp profiles.
- WhatsApp cloud proxy, managed email, Phase 4 pricing.
- Massive Reseller sub-account provisioning.
- Additional agency/client sub-workspaces.

## 16. Rollback

1. Set `TEAM_WORKSPACES_ENABLED=false`.
2. Team APIs return disabled; effective billing falls back to each user's personal
   organization and own plan.
3. Team UI disappears; personal orgs remain.
4. Do not delete organization, membership, invite, seat, profile, proxy, or audit
   data.
5. Re-enable the flag to restore the previous workspace view.

## 17. Deployment gates

Before production enablement:

- review the migration dry-run against production,
- `TEAM_WORKSPACES_ENABLED` was enabled on 2026-11-20 after approval,
- run the two-account cloud E2E flow with one owner + one member (still
  recommended before inviting external customers),
- verify no cross-tenant access in logs/audit,
- confirm the protected deploy workflow's pre-existing Mongo failures are
  understood and not caused by Phase 3A.
