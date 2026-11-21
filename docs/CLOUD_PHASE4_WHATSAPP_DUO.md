# Phase 4 — Cloud Duo Shared-IP WhatsApp

Status: implemented behind `WHATSAPP_CLOUD_PROXY_ENABLED=false`  
Date: 2026-11-21  
Scope owner: platform + product

This is the first Phase 4 slice. It adds a WhatsApp number to an existing
cloud LinkedIn seat as a **Cloud Duo shared-IP** channel. It does not change
prices, Stripe, or the cloud seat pool.

## 1. Product rule

A Cloud Duo seat is one client identity with:

- one cloud LinkedIn account,
- one WhatsApp number,
- one BYO email slot,
- one managed proxy identity.

The WhatsApp number shares the LinkedIn account's existing proxy and seat. It
does not create a second sub-account or consume a second seat. The proxy may
serve one LinkedIn account and one WhatsApp number only when they share the
same `identity_id`.

## 2. Gate

```text
WHATSAPP_CLOUD_PROXY_ENABLED=false
DAEMON_V2_WHATSAPP_ENABLED=false
```

Both are required. `WHATSAPP_CLOUD_PROXY_ENABLED` is the Phase 4 product gate;
`DAEMON_V2_WHATSAPP_ENABLED` is the existing server-WA runtime opt-in. When
either is false:

- the WhatsApp UI hides the Cloud Duo option,
- the API rejects cloud WhatsApp creation,
- the cloud daemon does not start any cloud WhatsApp session.

`CLOUD_SEATS_ENABLED` and `MANAGED_PROXIES_ENABLED` remain additional gates.

## 3. API

`POST /api/whatsapp/profiles` now accepts:

```json
{
  "display_name": "Acme WhatsApp",
  "execution_mode": "cloud",
  "duo_linkedin_profile_id": "<cloud LinkedIn profile id>"
}
```

Validation:

- the caller can access the LinkedIn profile (owner/admin or assigned member),
- the LinkedIn profile is cloud and belongs to the active workspace,
- it has a managed proxy that is still assigned to that exact profile,
- the proxy is not disabled, budget-disabled, retired, or in error,
- the proxy belongs to the same workspace and identity,
- no other cloud WhatsApp number already uses that proxy.

The response includes `executionMode`, `proxyMode`, `proxyId`, and the proxy
region. Credentials are never returned.

## 4. Launch and daemon

`openoutreach/whatsapp/browser/launch.py`:

- desktop profiles never receive a proxy,
- cloud profiles require a healthy managed proxy,
- the proxy is passed to Playwright's `browser.new_context(proxy=...)`,
- a missing/disabled proxy raises `WhatsAppCloudProxyError`; the browser is
  closed and the server IP is never used.

`openoutreach/core/daemon.py`:

- only selects `execution_mode="cloud"` WhatsApp profiles,
- requires `proxy_id`,
- skips the session unless the shared LinkedIn profile is active and still
  points at the same proxy,
- closes sessions for profiles that are no longer eligible.

## 5. Lifecycle

- Admin unassign/retire clears the WhatsApp proxy link and keeps the profile.
- Deleting the LinkedIn profile does not retire a proxy that is still shared
  with a cloud WhatsApp profile; the WhatsApp session stops because the shared
  LinkedIn profile is gone.
- Seat removal pauses the LinkedIn profile and disables the sub-account; the
  cloud daemon skips the WhatsApp session while the proxy is disabled.
- Re-adding the same LinkedIn seat re-enables the same sub-account and the
  WhatsApp session can resume.

## 6. Frontend

Settings → WhatsApp:

- Desktop (local IP, no proxy) remains the default.
- Cloud Duo appears only when the capability flag and a cloud seat are present.
- The user selects an existing cloud LinkedIn profile with a managed proxy.
- Cards show `Cloud Duo · Managed proxy · US` or `Desktop · Local IP · No proxy`.

## 6a. Email slot

Phase 4 keeps email **BYO**: the customer connects their own SMTP/IMAP mailbox
in Settings → Email. Email does not use a browser proxy and no managed mailbox
is provisioned. The existing mailbox model already carries `org_id`,
`assigned_user_id`, `seat_id`, and `managed=false`, so no schema change was
needed for the BYO slot.

## 7. Explicitly not in this slice

- WhatsApp-only cloud seats (no LinkedIn account).
- Separate-IP Cloud Duo (two proxies).
- Per-channel usage attribution on the shared proxy. The shared proxy keeps the
  LinkedIn sub-account label, so Reporting currently combines LinkedIn and
  WhatsApp traffic for that identity. This needs a channel-labelled session
  before customer usage reviews.
- Managed email provisioning. Email remains BYO SMTP/IMAP.
- Any price or Stripe change. Cloud Duo is $299/mo during rollout; separate IPs
  are a support configuration, not a price change.
- A second WhatsApp number per Duo seat.

## 8. Rollout

1. Deploy with `WHATSAPP_CLOUD_PROXY_ENABLED=false`.
2. Create one internal cloud LinkedIn profile with a managed proxy.
3. Enable the flag for an internal test.
4. Create a Cloud Duo WhatsApp number, scan the QR, confirm the session uses the
   shared proxy country and never the server IP.
5. Remove/re-add the LinkedIn seat and confirm the WhatsApp session pauses and
   resumes with the same proxy.
6. Keep the flag off for customers until that test passes.

## 9. Validation

```text
.venv\Scripts\python.exe -m pytest tests -q
# 603 passed, 56 skipped

.venv\Scripts\python.exe -m pytest tests/test_cloud_phase4.py -q
# 5 passed

ruff E9,F63,F7,F82; compileall; frontend eslint/tsc/build
# clean
```
