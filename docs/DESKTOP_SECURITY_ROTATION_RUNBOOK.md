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

## Historical desktop log containing callback material

The desktop log is sensitive incident evidence. If an older build logged a
`lengrowth://` callback URL, treat the callback token as exposed. Do not paste
the log or token into chat, tickets, or shell output.

1. Obtain incident-commander and security approval before changing the log or
   revoking credentials.
2. Preserve the exact file and hash in the approved restricted evidence store:
   `C:\Users\<user>\AppData\Local\Lengrowth\daemon.log`.
3. Run the read-only aggregate audit, which never prints log contents:
   `python scripts/audit_desktop_log.py --path "C:\Users\<user>\AppData\Local\Lengrowth\daemon.log"`.
   A non-zero result means callback-token material was detected.
4. Revoke or rotate the affected session/credential in its authoritative
   provider or secret manager, then record only the credential type, scope,
   timestamp, and revocation result.
5. After retention approval, remove the local copy and verify the path is
   absent. Reinstall or start the current build, then confirm the new log
   contains no callback query strings using the same aggregate audit.

This procedure has external side effects only in steps 4 and 5 and requires
explicit approval immediately beforehand. The current source build redacts
callback query strings and raw exception values; this does not retroactively
sanitize historical logs.
