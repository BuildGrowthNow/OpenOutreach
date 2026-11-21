# Support Runbook — Team Workspaces and Managed Proxies

Status: Phase 4 operations reference
Audience: support, platform on-call  
Related: `docs/CLOUD_TEAM_PROXY_ROLLOUT_PLAN.md`,
`docs/CLOUD_TEAM_PROXY_IMPLEMENTATION_SPEC.md`,
`docs/CLOUD_PHASE3A_ORGS_TEAMS.md`,
`docs/CLOUD_PHASE4_WHATSAPP_DUO.md`

Never ask a customer for proxy passwords, `MASSIVE_*` keys, cookies, or
tokens. Never paste them into a ticket, chat, log, or audit note.

## 1. "A member cannot see a LinkedIn or WhatsApp account"

1. Confirm the member accepted the invite and is in the workspace:
   Admin → Organizations → select the workspace → Members.
2. Confirm the profile is cloud or desktop and is assigned to that member:
   - Cloud LinkedIn or WhatsApp: Settings → Team → Cloud seats, or Admin →
     Organizations → Proxies.
   - Desktop: the member must enroll the assigned desktop profile on their device.
3. Confirm the profile belongs to the same `org_id`. A profile created in the
   member's personal workspace is not visible in the shared workspace until it
   is moved by an owner/admin.
4. A Cloud Duo WhatsApp number follows the LinkedIn seat assignment for the same
   identity. If the member has the LinkedIn seat, the Duo number should be
   visible; if not, assign the LinkedIn seat first.
5. If the member was removed and re-added, reassign the profile. Removal pauses
   the profile and clears `assigned_user_id`; it does not delete the proxy.
6. If `TEAM_WORKSPACES_ENABLED=false`, team surfaces are intentionally hidden and
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
2. Settings → Team shows `used / limit` unified cloud seats and a breakdown of
   LinkedIn, Duo, and WhatsApp-only units. Paused and active credentialed
   accounts both consume a seat.
3. One cloud seat is one browser account: LinkedIn **or** WhatsApp, plus one
   email slot and one proxy identity. A Cloud Duo uses one seat for one
   LinkedIn + one WhatsApp of the same identity.
4. Resolve by:
   - buying another cloud seat (owner only),
   - unassigning/removing a seat (owner/admin; pauses the channel and keeps its
     proxy), or
   - deleting the profile (owner/admin; retires the proxy and releases the seat).
5. Do not delete a profile merely to free a seat if the customer wants to keep
   the identity. Unassign first.
6. Deleting only a Cloud Duo WhatsApp number does not release the seat while the
   LinkedIn account remains. Deleting the LinkedIn profile while the WhatsApp
   number remains also keeps the seat (the number becomes a WhatsApp-only unit).
7. Admin seat overrides are audited and do not change Stripe. Use only with an
   approved support reason. If a workspace is over its pool, Admin → Proxies →
   Massive shows a seat-over-limit alert.

## 4. "Proxy is unhealthy / country mismatch"

1. Admin → Proxies → Health: filter failures or country mismatch. Use the
   channel filter to isolate LinkedIn, WhatsApp, or Duo.
2. Test the proxy. A `407` means bad credentials; rotate or replace it.
3. A `521`/timeout usually means the region is too narrow. Switch to
   country-level targeting.
4. Admin → Proxies → Massive: check `limit_reached`, `proxy_access`, and the
   last sync. Pool Stats warns below 1,000 nodes; use country-level targeting.
5. Never move a used proxy to a different LinkedIn account or WhatsApp number.
   Retire it on profile deletion.
6. A WhatsApp proxy that is disabled or in error pauses the WhatsApp session and
   raises `whatsapp_proxy_unavailable`. The server IP is never used.

## 5. "Massive sub-account is disabled"

- `disabled`: seat cancellation/unassignment. Reassign the same profile to a
  seat to re-enable it. Do not create a new sub-account for the same identity.
- `budget_disabled`: internal monthly hard threshold. Review usage in Admin →
  Proxies → Usage. It re-enables automatically next month when under the soft
  threshold, or an admin can enable it after review.
- `retired`: profile deleted. Never reuse.
- `error`: check `last_error` and the admin alerts. Fix credentials/region and
  retry; rotate only when the provider password is the problem.
- For WhatsApp, the sub-account is the `.wa.` channel. Disabling the LinkedIn
  `.li.` sub-account of a shared-IP Duo disables the shared proxy and pauses both
  channels; separate-IP Duo channels are independent.

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

## 8a. "WhatsApp cloud will not create / QR does not appear"

| Symptom | Check | Action |
|---|---|---|
| Cloud option hidden | `WHATSAPP_CLOUD_PROXY_ENABLED` and `DAEMON_V2_WHATSAPP_ENABLED` | Enable both; reload Settings → WhatsApp |
| `Cloud WhatsApp requires a Cloud seat` | `cloud_seat_limit` / unified seat usage | Buy a seat, remove a profile, or use Desktop |
| `Select the cloud LinkedIn profile` | Duo variants need an existing cloud LinkedIn account | Create/assign the LinkedIn cloud profile first |
| `one WhatsApp per Duo seat` | The LinkedIn identity already has a cloud WhatsApp number | Use the existing number or choose WhatsApp-only with a new seat |
| `Could not provision a managed proxy` | Admin → Proxies → Massive, Pool Stats | Check provider access/region; retry or add inventory |
| QR stays pending | Cloud daemon WA session | Confirm `DAEMON_V2_WHATSAPP_ENABLED=true`, exactly one daemon, and the proxy is active |
| `WhatsApp cloud proxy is not active` | Admin → Proxies → Health/Massive | Test/rotate/enable the proxy; never fall back to the server IP |
| `proxy identity does not match` | Proxy `identity_id` vs profile `identity_id` | Do not move a used proxy; assign the correct proxy or recreate the seat |

Cloud WhatsApp never uses the server IP. A missing or disabled proxy is a hard
stop, not a warning.

## 8b. Email BYO slot

- Phase 4 email is BYO SMTP/IMAP. There is no managed mailbox, domain purchase,
  warmup, or deliverability service.
- Each seat includes one email slot. Settings → Email shows `used of limit`.
- Email never uses a proxy. Do not add proxy fields to a mailbox.
- `Email slot limit reached` means the workspace has used every slot: remove a
  mailbox or add a seat.
- SMTP auth is checked on create; optional IMAP auth is checked when IMAP host
  is supplied. A failure is returned to the customer; the mailbox row is not
  created.
- Org visibility: owners/admins see all workspace mailboxes; members see the
  ones assigned to them. Do not ask for the customer's mailbox password.

## 8c. Shared vs separate usage

- **Shared-IP Duo**: one sub-account and one proxy for the LinkedIn + WhatsApp
  identity. Reporting shows combined Duo usage. Do not promise a per-channel
  split; the provider cannot supply one.
- **Separate-IP Duo**: two sub-accounts (`.li.` and `.wa.`) and two proxies. One
  seat, but Reporting `group_by=subaccount` and Admin → Proxies → Usage show each
  channel separately.
- **WhatsApp-only cloud**: one `.wa.` sub-account and one proxy.
- **LinkedIn Solo**: one `.li.` sub-account and one proxy.
- Usage is internal only. Never quote a GB allowance, meter, or overage charge
  to a customer. Pricing is flat per seat under fair use.

## 8d. `MASSIVE_RESELLER_ENABLED` behavior

- `true`: new profiles can create Reseller sub-accounts; admin
  disable/enable/rotate and Reseller usage sync are available.
- `false`: new profiles use the Phase 1 parent `-subaccount-li/wa` fallback.
  Existing Reseller sub-accounts stay assigned and disabled as needed, but admin
  disable/enable/rotate and Reseller usage sync are unavailable until the flag
  is re-enabled. Do not delete sub-accounts or proxies.
- The first owner live test keeps the flag false; enable it only after that
  profile passes provisioning, assignment, egress, disable/enable, password
  rotation, and launch.

## 9. Escalation evidence to collect

- workspace/org id, member user id, profile id, WhatsApp profile id, proxy id
  (opaque)
- channel (`linkedin`, `whatsapp`, `duo`) and cloud mode (`duo_shared`,
  `duo_separate`, `whatsapp_only`)
- timestamp in UTC, action, and the exact customer-visible error
- relevant audit event names (`seat.assign`, `seat.remove`, `org.remove`,
  `proxy.provision`, `proxy.massive_*`)
- never include passwords, keys, cookies, tokens, or raw request bodies that may
  contain credentials.
