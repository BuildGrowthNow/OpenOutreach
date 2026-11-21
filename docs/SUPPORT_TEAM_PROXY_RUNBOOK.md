# Support Runbook — Team Workspaces and Managed Proxies

Status: Phase 3B operations reference  
Audience: support, platform on-call  
Related: `docs/CLOUD_TEAM_PROXY_ROLLOUT_PLAN.md`,
`docs/CLOUD_TEAM_PROXY_IMPLEMENTATION_SPEC.md`,
`docs/CLOUD_PHASE3A_ORGS_TEAMS.md`

Never ask a customer for proxy passwords, `MASSIVE_*` keys, cookies, or
tokens. Never paste them into a ticket, chat, log, or audit note.

## 1. "A member cannot see a LinkedIn profile"

1. Confirm the member accepted the invite and is in the workspace:
   Admin → Organizations → select the workspace → Members.
2. Confirm the profile is cloud or desktop and is assigned to that member:
   - Cloud: Settings → Team → Cloud seats, or Admin → Organizations → Proxies.
   - Desktop: the member must enroll the assigned desktop profile on their device.
3. Confirm the profile belongs to the same `org_id`. A profile created in the
   member's personal workspace is not visible in the shared workspace until it
   is moved by an owner/admin.
4. If the member was removed and re-added, reassign the profile. Removal pauses
   the profile and clears `assigned_user_id`; it does not delete the proxy.
5. If `TEAM_WORKSPACES_ENABLED=false`, team surfaces are intentionally hidden and
   everyone falls back to their personal workspace. Do not delete org data.

## 2. "Desktop enrollment fails"

| Symptom | Check | Action |
|---|---|---|
| Code expired | Codes expire after 10 minutes | Create a new code |
| Code already used | Codes are single-use | Create a new code |
| Profile not found | Profile must exist, be desktop, and be assigned to the member | Reassign or create a desktop profile |
| Cloud profile rejected | Cloud profiles are server-owned and never enroll on desktop | Use the cloud seat flow |
| Device revoked | Device list shows `revoked` | Re-enroll the device |
| Version rejected | API returns `426 Upgrade Required` | Update the desktop app to the minimum secure version |
| Device list empty for owner | Device was created before org scope existed | Ask engineering to backfill `org_id`, or have the member re-enroll |

Desktop devices report their local egress IP for display/support only. The API
never sends proxy credentials to a desktop device.

## 3. "Seat limit reached"

1. Settings → Billing shows the workspace plan and cloud seat count.
2. Settings → Team shows `used / limit` cloud seats. Paused and active
   credentialed accounts both consume a seat.
3. Resolve by:
   - buying another cloud seat (owner only),
   - unassigning/removing a seat (owner/admin; pauses the profile and keeps its
     proxy), or
   - deleting the profile (owner/admin; retires the proxy and releases the seat).
4. Do not delete a profile merely to free a seat if the customer wants to keep
   the LinkedIn identity. Unassign first.
5. Admin seat overrides are audited and do not change Stripe. Use only with an
   approved support reason.

## 4. "Proxy is unhealthy / country mismatch"

1. Admin → Proxies → Health: filter failures or country mismatch.
2. Test the proxy. A `407` means bad credentials; rotate or replace it.
3. A `521`/timeout usually means the region is too narrow. Switch to
   country-level targeting.
4. Admin → Proxies → Massive: check `limit_reached`, `proxy_access`, and the
   last sync. Pool Stats warns below 1,000 nodes; use country-level targeting.
5. Never move a used proxy to a different LinkedIn account. Retire it on profile
   deletion.

## 5. "Massive sub-account is disabled"

- `disabled`: seat cancellation/unassignment. Reassign the same profile to a
  seat to re-enable it. Do not create a new sub-account for the same identity.
- `budget_disabled`: internal monthly hard threshold. Review usage in Admin →
  Proxies → Usage. It re-enables automatically next month when under the soft
  threshold, or an admin can enable it after review.
- `retired`: profile deleted. Never reuse.
- `error`: check `last_error` and the admin alerts. Fix credentials/region and
  retry; rotate only when the provider password is the problem.

## 5a. Budget threshold review

Before a real usage sync can disable a sub-account, preview the internal monthly
budget actions:

```text
python -m openoutreach.cli sync-proxy-usage --dry-run
```

The dry-run syncs cumulative and Reporting usage, then reports how many
sub-accounts would be disabled, re-enabled, or flagged as soft alerts. It does
not call the provider enable/disable endpoints and does not write budget audit
events. Review the projection with the platform owner, then run the normal
`sync-proxy-usage` only if the actions are expected.

## 6. "Massive is down / Reseller unavailable"

1. Set `MASSIVE_RESELLER_ENABLED=false` (backend gate). New profiles fall back
   to the Phase 1 parent `-subaccount` credentials.
2. Existing sub-accounts stay assigned and disabled as needed; do not delete
   them.
3. Re-enable the flag after the provider recovers and run Sync now.
4. Never run a cloud profile on the server IP. If no managed proxy path is
   available, pause the profile and escalate.

## 7. Billing and plan questions

- The owner pays; members inherit the owner's plan and seat pool.
- Team-member pricing is unchanged during rollout. Do not promise free seats or
  a per-member price until product approves it.
- Cloud has no trial, including `intended_plan=cloud`.
- No customer-facing GB meter or overage charge exists. Usage is internal.

## 8. Escalation evidence to collect

- workspace/org id, member user id, profile id, proxy id (opaque)
- timestamp in UTC, action, and the exact customer-visible error
- relevant audit event names (`seat.assign`, `seat.remove`, `org.remove`,
  `proxy.provision`, `proxy.massive_*`)
- never include passwords, keys, cookies, tokens, or raw request bodies that may
  contain credentials.
