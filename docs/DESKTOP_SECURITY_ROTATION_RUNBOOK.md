# Desktop security incident and rotation runbook

This runbook is intentionally operational. It does not contain credentials and
must be executed by the incident commander with the security/platform approver.

## Immediate containment

1. Preserve WAF, API, authentication, Atlas, provider, deployment, and release
   logs. Do not collect response bodies, tokens, cookies, QR data, or plaintext
   credentials.
2. Confirm `/api/daemon/bootstrap` returns `410` and legacy daemon routes return
   `426` without a secure version header.
3. Pause legacy automation and record the cutoff timestamp.
4. Inventory versions, device IDs, profiles, source IPs, and provider usage from
   metadata only.

## Rotation order

1. Generate and deploy a new asymmetric JWT signing key with a new `kid`; reject
   the exposed HS256 key and force human sessions to reauthenticate.
2. Rotate MongoDB users, terminate existing sessions, restrict Atlas ingress to
   backend workloads, and verify the old credential fails from an approved test
   network. Never place the replacement credential in desktop configuration.
3. Rotate every provider key that was returned to a desktop and review usage,
   cost, source IP, and anomaly alerts.
4. Enable envelope-encryption dual-read/new-write with a new KMS key ID; run the
   migration command in dry-run mode, review counts, back up, then apply in
   resumable batches with checkpoint and quarantine reporting.
5. Invalidate affected LinkedIn sessions, WhatsApp links, and SMTP/IMAP app
   passwords. Mark remediation state as potentially compromised until customer
   reauthentication completes.

## Verification and rollback

- Verify old JWT, MongoDB, provider, and encryption keys are rejected before
  disabling the old key ring.
- Verify daemon token exchange fails for revoked devices and refresh reuse
  revokes the complete family.
- Roll back only to the last API-only secure desktop/backend artifact. Never
  restore bootstrap, direct MongoDB access, or secret injection.

## Commands

Use `python scripts/migrate_encryption.py --collection <name> --field <field>
--checkpoint-file <path>` for a dry run. Add `--apply` only after approval and
backup verification. Key loading, production database selection, and provider
rotation are deployment-specific and must come from the secret manager.
