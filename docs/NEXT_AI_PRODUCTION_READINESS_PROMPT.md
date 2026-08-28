# Prompt for the next AI agent

You are continuing the security migration in:

`C:\Users\smikl\Desktop\Work\OpenOutreach`

Your objective is to finish the migration and make the desktop and daemon system genuinely production-ready. Do not stop at documentation, feature flags, or passing mocks. Implement the missing functionality, test it, deploy only authorized changes, and report evidence.

## Read first

Read these files completely before changing anything:

- `docs/prompt-security.md`
- `docs/DESKTOP_BOOTSTRAP_SECURITY_MIGRATION_PLAN.md`
- `CLAUDE.md`
- `ARCHITECTURE.md`
- `docs/DESKTOP_SECURITY_ROTATION_RUNBOOK.md`

Preserve all existing user changes and dirty files. Never use `git reset --hard`, `git checkout --`, `git clean`, broad deletes, or destructive cleanup. Use `apply_patch` for edits. Never print, log, test, commit, or return secrets.

## Current verified state

- Production repository is on the security migration branch of `main`.
- `/api/daemon/bootstrap` permanently returns `410` and does not expose secrets.
- Legacy daemon routes require `X-Daemon-Version >= 2.0.0`.
- Human resource authentication rejects refresh tokens.
- Desktop startup no longer bootstraps secrets, injects server environment, or connects directly to MongoDB.
- PyInstaller excludes MongoDB and the legacy daemon boundary.
- Daemon v2 includes RS256 access tokens, device identity, enrollment codes, refresh rotation/reuse detection, revocation, proof-of-possession, timestamps, nonce replay protection, tenant context, ownership predicates, task leases, bounded events, encryption helpers, and redacted security audit persistence.
- Production has a dedicated daemon-v2 RSA keypair configured through base64 environment variables. Do not rotate existing JWT, MongoDB, provider, or encryption credentials unless explicitly required and separately authorized.
- Desktop version is `2.0.0`.
- Windows and macOS 2.0.0 artifacts are published. Stable URLs are:
  - `https://dl.lengrowth.com/Lengrowth-Windows-Setup.exe`
  - `https://dl.lengrowth.com/Lengrowth-macOS.dmg`
- Production smoke checks currently pass:
  - bootstrap `410`
  - v2 compatibility `200`
  - stable Windows/macOS download URLs `200`
- Focused security tests, broader API/desktop tests, Pyright, compileall, and diff checks have passed.

## Known incomplete work that must be finished

### 1. Complete the desktop browser execution adapter

`openoutreach/desktop/linkedin_browser_adapter.py` currently supports only a narrow subset:

- LinkedIn connect
- LinkedIn pending check
- LinkedIn manual send

Finish a robust adapter architecture for:

- LinkedIn connect, pending check, follow-up, manual send, and observations.
- WhatsApp session state, message send, sync, receipts, QR/reconnect handling, and bounded recovery.
- Email send/reply-scan operations using mailbox grants and receipts.

The adapters must:

- Use only local browser/provider execution code.
- Receive all task inputs from typed v2 API snapshots.
- Never import MongoDB models, server credentials, server settings, or backend repositories.
- Never receive or persist server-side passwords/cookies as desktop configuration.
- Use local OS-managed browser/session state and require human interaction for login/challenges.
- Return bounded, typed, sanitized receipts and observations.
- Handle provider challenge, logged-out, rate-limit, timeout, duplicate, and already-applied states explicitly.
- Never claim a task unless execution and receipt generation succeeded.

### 2. Replace lazy task slots with executable typed snapshots

Current scheduled tasks often contain only `campaign_id`, so a desktop adapter cannot safely execute them. Implement server-side task materialization or a typed claim-time resolver that supplies the minimum required fields:

- task type and channel
- target profile/contact identifier
- target URN/address where needed
- message content where needed
- campaign/action constraints needed for safety
- deterministic idempotency/effect key
- any required session/mailbox grant

Do not send credentials, cookies, arbitrary model documents, secrets, or unbounded campaign data. Ensure tenant, device, profile, channel, campaign, lease, and ownership checks happen server-side before materialization.

Make connect, follow-up, pending-check, WhatsApp, and email tasks executable through the v2 claim API. Preserve existing scheduling, rate limits, cooldowns, sequence rules, and campaign semantics without moving database access to the desktop.

### 3. Complete idempotency and reconciliation

Implement deterministic effect keys and safe duplicate reconciliation for every action. Verify behavior for:

- network loss after provider success
- retry after lease renewal
- duplicate completion
- expired lease
- device revocation during execution
- already-connected/already-sent/already-synced provider state
- provider receipt unavailable

The server must reconcile duplicate completion attempts without double-applying an action.

### 4. Finish tenant-scoped repositories and negative tests

Audit every daemon-reachable v2 endpoint and repository. Add two-tenant tests proving that tenant A cannot read, claim, renew, complete, fail, cancel, observe, sync, or mutate tenant B’s data. Include device/profile/channel mismatch tests and revoked-device tests.

### 5. Finish safe configuration retrieval

Expose only typed allowlisted operational fields needed by each adapter. Verify no credentials, cookies, raw encrypted values, MongoDB URI, provider secrets, or arbitrary settings can cross the API boundary. Add response-size and field allowlist tests.

### 6. Make migration wrappers production-operable

Complete resumable, checkpointed, dry-run-by-default wrappers for:

- tenant ownership backfill
- encryption migration
- index verification

Add explicit confirmation gates, bounded batches, retry behavior, progress counters, safe resume, and no secret/body logging. Do not execute destructive or irreversible migrations without inspecting the exact production scope and obtaining explicit confirmation.

### 7. Production readiness and supply-chain checks

Add or document:

- release artifact hashes and verification
- SBOM generation
- dependency/vulnerability scanning
- PyInstaller artifact inspection proving no forbidden imports or embedded secrets
- key/device revocation and re-enrollment runbook
- rollback procedure
- monitoring and alerting for auth failures, replay, lease failures, provider challenges, and duplicate effects
- migration acceptance tests
- desktop enrollment and first-run UX instructions

## Required validation

Run at minimum:

```powershell
pytest -q tests/api_v2/test_daemon_auth.py tests/api_v2/test_daemon_security.py tests/api_v2/test_envelope_crypto.py tests/desktop/test_secure_daemon_boundary.py tests/api_v2/test_phase5_desktop.py tests/desktop/test_updater.py
pytest -q tests/api_v2 --ignore=tests/api_v2/test_auth_phase1.py tests/desktop
pyright <all changed security and desktop modules>
py -m compileall -q openoutreach scripts desktop
git diff --check
```

Add real contract/integration tests for every newly implemented adapter and task type. Use deterministic fake provider/browser fixtures where external browser execution is unavailable, but do not treat mocks alone as proof of production readiness. If safe, perform a production smoke test using a disposable enrollment/device and a non-destructive test task.

## Deployment rules

- Do not rotate existing JWT, MongoDB, provider, or encryption credentials unless explicitly required.
- Do not modify Atlas networking.
- Do not expose any secret value in output.
- Deploy only after local tests and static checks pass.
- Verify the running production commit, container health, bootstrap `410`, compatibility response, legacy `426`, and both desktop download URLs.
- Do not enable task claiming globally until executable snapshots and every enabled channel have passed end-to-end validation.
- If a required production action cannot be safely performed from the repository, state the exact command/action the operator must perform and what evidence is needed afterward.

## Completion standard

Do not claim “production ready” merely because the service is healthy or artifacts build. Completion requires:

1. Every enabled task type has a real typed snapshot and real adapter.
2. The desktop can enroll, exchange/rotate/revoke credentials, open the local browser, execute supported actions, and submit receipts safely.
3. Duplicate/retry/replay/tenant-isolation tests pass.
4. No daemon-reachable path bypasses the v2 boundary or accesses MongoDB from the desktop.
5. Production flags match the actually validated capabilities.
6. Release artifacts are built and downloadable.
7. All remaining items are either completed or explicitly identified as operator-only actions with exact instructions.

At the end, inspect `git diff` and `git status`, report exact commits, tests, deployment runs, production smoke results, enabled flags, and any remaining operator action. Never hide a limitation to make the report appear complete.
