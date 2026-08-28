You are the lead security architect, senior backend engineer, desktop platform engineer, and incident-remediation owner for this repository:

C:\Users\smikl\Desktop\Work\OpenOutreach

Your task is to implement the complete desktop bootstrap security migration described in:

C:\Users\smikl\Desktop\Work\OpenOutreach\docs\DESKTOP_BOOTSTRAP_SECURITY_MIGRATION_PLAN.md

This is an implementation task, not another planning exercise. Read the entire plan and the repository instructions before changing anything. Work through the migration sequentially until every safely implementable phase is complete, tested, and documented.

The current vulnerability is critical:

- A customer-controlled desktop daemon calls `GET /api/daemon/bootstrap`.
- The endpoint returns the global `SECRET_KEY`, shared `MONGODB_URI`, and database name.
- The desktop injects those values into its environment.
- It connects directly to the shared MongoDB database.
- It can use the global key for encryption/decryption and potentially HS256 JWT signing.
- The desktop executes LinkedIn, WhatsApp, and email handlers that directly read and write shared collections.
- `/api/daemon/config` also appears to disclose a backend LLM provider key.
- The desktop must be considered completely untrusted, including the binary, operating-system user, local files, process memory, browser profile, and network client.

The final architecture must ensure that a malicious tenant who fully controls their desktop process cannot:

- Obtain any global backend secret.
- Obtain any shared or server-only MongoDB credential.
- Connect directly to the shared database.
- Forge accepted JWTs.
- Use refresh, verification, or password-reset tokens as resource-access tokens.
- Enumerate or mutate another tenant’s data.
- Access another profile belonging to the same tenant unless that profile is explicitly bound to the device.
- Perform arbitrary state transitions by forging task results.
- Replay completed tasks or results to produce duplicate effects.
- Obtain LLM/provider keys, encryption keys, database credentials, administrative tokens, or equivalent replacement secrets.
- Restore the insecure behavior by running an old desktop client.

The desired end state is:

1. A fully API-based desktop daemon.
2. A dedicated daemon-gateway security boundary, initially allowed to live inside the existing FastAPI deployment.
3. Explicit device enrollment.
4. Short-lived daemon-only access credentials.
5. Device/profile/channel bindings and scopes.
6. Server-side tenant authorization on every operation.
7. Server-owned task leases, retries, reconciliation, and state transitions.
8. Local browser automation, with local-first LinkedIn and WhatsApp session storage.
9. No MongoDB driver or MongoDB-aware domain models in the distributed desktop artifact.
10. No server JWT, encryption, database, or provider secrets in desktop API responses, environment variables, files, logs, crash dumps, or binaries.
11. Permanent rejection of insecure desktop versions.
12. Coordinated rotation and revocation support for all previously exposed material.

Repository and execution rules
================================

Before modifying code:

1. Read these files completely:
   - `CLAUDE.md`
   - `ARCHITECTURE.md`
   - `docs/DESKTOP_BOOTSTRAP_SECURITY_MIGRATION_PLAN.md`
   - Any applicable `AGENTS.md` if one exists.
2. Run `git status --short`.
3. Treat all existing modified and untracked files as user-owned work.
4. Do not reset, discard, overwrite, clean, or broadly reformat unrelated changes.
5. Inspect current code before trusting line numbers in the plan, because the worktree may have changed.
6. Search before adding abstractions. Reuse or refactor existing utilities where appropriate.
7. Do not launch subagents; execute sequentially.
8. Do not deploy, rotate real production credentials, modify Atlas networking, notify customers, force production upgrades, or push externally unless the user explicitly authorizes those external actions.
9. You may and should implement the code, configuration hooks, migration commands, tests, dashboards-as-code, and runbooks required to perform those actions safely.
10. Do not merely rename or obfuscate exposed secrets.
11. Do not substitute a different global credential.
12. Do not introduce per-device MongoDB access to shared multi-tenant collections.
13. Do not trust a `user_id`, tenant ID, profile ID, task ID, campaign ID, deal ID, mailbox ID, or message ID supplied by the desktop as authorization.
14. IDs are locators only. Authorization must come from authenticated server-side context and database ownership predicates.
15. Unexpected failures should fail closed and follow repository error-handling rules.
16. Avoid compatibility shims that preserve the insecure path.
17. Use feature flags for staged behavior, but no flag may restore secret disclosure after the secure cutoff.
18. Update the existing migration-plan document with implementation checkboxes and evidence. Do not create a competing implementation-plan document.
19. Update `ARCHITECTURE.md` and `CLAUDE.md` when architecture or operational behavior changes.
20. Run focused tests continuously, followed by the repository’s complete required lint, type-check, and test commands before completion.
21. Do not stage or commit `build/`, `dist/`, `.next/`, `node_modules/`, `.wrangler/`, generated caches, credentials, databases, or release artifacts.

How to execute the work
=======================

Implement the migration in small, reviewable vertical slices. Keep the system buildable after each slice. At the beginning of each phase:

- Reconfirm the relevant current code paths.
- Add or update checkboxes in the existing migration-plan document.
- State the precise security invariant being established.
- Add tests that fail before the implementation where practical.
- Implement the smallest complete secure boundary.
- Run focused tests.
- Record evidence and remaining gaps in the existing plan.

Do not declare a phase complete because scaffolding exists. Complete means its exit criteria and tests are satisfied.

If a later phase depends on external production authority, complete all local code, tests, migration tools, feature flags, and runbooks first. Clearly identify the exact remaining external action and why it requires authorization. Continue with other independent in-scope work rather than stopping unnecessarily.

Phase 0: immediate containment and security instrumentation
===========================================================

Implement code-side containment first.

Required work:

1. Stop secret disclosure.
   - Remove `SECRET_KEY`, `MONGODB_URI`, MongoDB database name when sensitive, LLM API keys, provider credentials, and any equivalent server-only values from every daemon response.
   - The existing `/api/daemon/bootstrap` must never return secrets in any environment.
   - Prefer returning `410 Gone` with a minimal version-independent error while telemetry is needed, then remove the route during legacy cleanup.
   - Do not include secret names, secret values, replacement credentials, infrastructure details, or remediation internals in the response.
   - Apply `Cache-Control: no-store` to daemon authentication, credential, session, and configuration responses.

2. Harden token-type enforcement.
   - `get_current_user` must accept access tokens only.
   - Refresh tokens must be accepted only by the refresh endpoint.
   - Email-verification and password-reset tokens must be purpose restricted.
   - Add explicit audience/purpose handling if the current token representation supports it.
   - Add negative tests proving refresh/reset/verification tokens cannot access ordinary APIs or daemon routes.

3. Remove provider-secret disclosure.
   - `/api/daemon/config` must expose typed behavior configuration only.
   - It must not return LLM API keys or any server credential.
   - Identify every provider secret currently injected into the desktop.
   - Move dependent LLM work toward server-side APIs in later phases.

4. Add minimum-secure-version controls.
   - Add a backend compatibility policy that can distinguish supported, deprecated, and insecure clients.
   - Insecure versions must receive a deterministic `426 Upgrade Required` or security-maintenance response.
   - They must not claim tasks or receive credentials/session material.
   - Do not rely only on user-agent strings; version must be part of authenticated device/client metadata once device enrollment exists.
   - Add feature flags with safe defaults:
     - bootstrap disabled by default;
     - minimum secure version;
     - task-claim kill switch;
     - per-channel kill switches;
     - v2 tenant/device allowlists.

5. Add security audit events.
   - Implement structured, append-only security events for:
     - bootstrap attempts;
     - insecure-version attempts;
     - token-type rejection;
     - device enrollment, refresh, reuse, revocation, and binding changes;
     - cross-tenant/profile authorization denials;
     - task lease conflicts and replay attempts;
     - forbidden configuration serialization.
   - Never log tokens, refresh credentials, authorization headers, enrollment codes, QR bytes, plaintext credentials, cookies, session state, provider keys, MongoDB URIs, or response bodies.
   - Include request/correlation ID, actor type, subject/device, server-derived tenant/profile when safe, outcome, source IP, version, and timestamp.

6. Add response-schema secret tests.
   - Recursively inspect daemon responses for forbidden key names and secret-like values.
   - Test authenticated, unauthenticated, old-client, current-client, human-token, daemon-token, and admin cases.
   - Ensure logs are redacted.

7. Add an incident-response runbook and safe rotation tooling.
   - Do not execute real rotations without authorization.
   - Implement documented commands/checklists for:
     - JWT signing-key retirement;
     - MongoDB user rotation and existing-session termination;
     - provider-key rotation;
     - encryption-key migration;
     - forced session invalidation;
     - customer/profile/mailbox reauthentication.
   - Rotation tools must support dry-run, resumability, audit output, explicit target validation, and no secret output.

Phase 1: tenant isolation and authorization repositories
=======================================================

Make the backend safe before expanding daemon APIs.

Required work:

1. Introduce an authenticated context type containing:
   - actor type;
   - tenant/user ID;
   - human session or device ID;
   - authorized profile bindings;
   - scopes/channels;
   - token ID and version where applicable.

2. Introduce tenant-aware repositories/services.
   - Every repository method handling tenant data must require tenant context explicitly.
   - Never provide an optional empty tenant that produces a global query.
   - Queries and updates must include server-derived tenant ownership.
   - Updates should be atomic ownership predicates such as `{_id, user_id}`, not get-then-unscoped-update.
   - Not-owned and nonexistent resources should normally be indistinguishable.

3. Audit and remediate all daemon-reachable collections:
   - `tasks`
   - `campaigns`
   - `leads`
   - `deals`
   - `chat_messages`
   - `messages`
   - `action_logs`
   - `notifications`
   - `site_config`
   - `users`
   - `linkedin_profiles`
   - `linkedin_credentials`
   - `whatsapp_profiles`
   - `mailboxes`
   - `sequence_events`
   - `email_domain_patterns`
   - Any additional collection discovered in current reachable code.

4. Fix task claim and result authorization.
   - Claim predicates must include tenant, bound profile, channel, due status, subscription/account status, and version policy.
   - Result endpoints must never authorize based on an optional field inside task payload.
   - Task ownership must be top-level and immutable.
   - A task result must match the current authorized task state and actor.
   - Add concurrent-claim tests.

5. Backfill tenant ownership.
   - Build idempotent migrations for rows missing `user_id` or other ownership fields.
   - Resolve ownership through trustworthy relationships.
   - Quarantine ambiguous rows instead of exposing them globally.
   - Add dry-run, progress, restart, and reconciliation reporting.
   - Add compound indexes supporting tenant-scoped hot paths.
   - Review unique constraints so dedupe keys cannot collide across tenants.

6. Add a mandatory two-tenant negative matrix.
   - Tenant A credentials with tenant B IDs in paths, queries, bodies, nested payloads, batches, cursors, idempotency keys, and task results.
   - Same tenant but unbound profile.
   - Bound profile but wrong device or channel.
   - Missing tenant fields.
   - Forged ownership fields.
   - Ensure tenant B data is never returned, altered, logged, counted in analytics, or used to create notifications.

Phase 2: daemon device enrollment and scoped authentication
==========================================================

Replace use of human access/refresh tokens as daemon identity.

Implement:

1. Data models and indexes:
   - `daemon_devices`
   - `daemon_profile_bindings`
   - `daemon_refresh_families`
   - `daemon_enrollment_codes`
   - nonce/replay records or an appropriate short-lived cache
   - security events
   - TTL indexes for one-time codes and nonces.

2. Human-approved enrollment:
   - A recently authenticated human session creates a short-lived one-time enrollment code.
   - Bind it to tenant, selected profile IDs, channel scopes, requested device name, expiry, and creator.
   - Require step-up authentication for this action.
   - Codes are stored hashed and may be redeemed exactly once.
   - Enrollment cannot silently authorize all current or future profiles.

3. Desktop device key:
   - Generate an Ed25519 or P-256 key.
   - Prefer Windows CNG/DPAPI or macOS Keychain/Secure Enclave when available.
   - Provide a secure software-key fallback for supported systems.
   - Store key metadata, not private material, on the backend.
   - Be explicit in documentation that a customer-controlled host can still extract or use its own key.

4. Daemon credential lifecycle:
   - Server-signed, asymmetric access tokens.
   - Maximum five-minute access-token lifetime unless documented otherwise.
   - `aud=daemon-gateway`.
   - Claims include device, tenant, bound profiles, scopes, token ID, version, issued/expiry times.
   - Opaque or random rotating refresh credentials stored only as secure hashes server-side.
   - Rotate refresh credential on every successful use.
   - Implement family reuse detection and automatic family revocation.
   - Device revocation stops future refresh and invalidates active leases.
   - Sensitive operations must check current device/binding state in addition to token signature.

5. Proof of possession:
   - Sign method, canonical path/query, body digest, timestamp, nonce, and access-token ID.
   - Enforce timestamp skew and one-time nonce use.
   - Prevent request replay across endpoints or bodies.
   - Add comprehensive canonicalization tests.

6. Strict token separation:
   - Daemon tokens cannot call human, billing, admin, or arbitrary CRUD APIs.
   - Human tokens cannot call v2 daemon execution routes.
   - Refresh credentials cannot authorize resources.
   - Profiles and channels are explicit scopes.

7. Desktop integration:
   - Separate human webview authentication from daemon device authentication.
   - Store daemon refresh material and device key in OS-protected storage.
   - Proactively refresh access tokens.
   - Handle revocation, keychain loss, profile unbinding, account switching, and re-enrollment.
   - Remove human refresh-token use from daemon requests after migration.

8. Frontend:
   - “Connect this desktop” flow.
   - Profile and channel selection.
   - Device list with name, platform, version, last seen, IP where appropriate, bindings, and status.
   - Revoke and re-enroll controls.
   - Security explanation and suspicious-device guidance.

Phase 3: daemon gateway and complete API contracts
=================================================

Create a dedicated v2 gateway boundary under `/api/daemon/v2`.

It may initially run inside the current FastAPI application, but it must have:

- Separate authentication dependency.
- Strict request/response schemas.
- Tenant-aware repositories.
- Purpose-built services.
- Versioned contracts.
- Request-size and batch limits.
- Per-device/profile/channel rate limits.
- Structured audit events.
- No generic model serialization.
- No general “get arbitrary object by ID” endpoints.
- No backend secrets.

Implement these contract groups:

1. Compatibility/configuration:
   - `GET /compatibility`
   - `GET /configuration`
   - ETag/conditional configuration fetch.
   - Typed active hours, rate limits, task capabilities, channel policy, retry hints, and minimum versions.
   - No provider keys or infrastructure configuration.

2. Task leases:
   - `POST /tasks/claim`
   - `POST /tasks/{id}/renew`
   - `POST /tasks/{id}/complete`
   - `POST /tasks/{id}/fail`
   - `POST /tasks/{id}/cancel-ack`
   - Atomic lease ownership and expiry.
   - Server-generated lease ID.
   - Attempt number, result schema version, idempotency key, record version.
   - Server-controlled retry, backoff, completion, and cancellation.
   - Clear `409 lease_conflict`, `410 lease_expired`, `422 invalid_transition`, and `429 rate_limited` behavior.

3. Self-contained execution snapshots:
   - Each claimed task contains only fields required for that action.
   - Do not let the daemon fetch arbitrary campaigns, deals, leads, users, messages, or mailboxes.
   - Derive tenant/profile/task ownership server-side.
   - Version task payloads with discriminated unions.
   - Avoid returning entire MongoDB documents.

4. LinkedIn contracts:
   - Profile-bound session state.
   - Login/challenge/verification reporting.
   - Optional one-use credential lease for web-managed credentials.
   - Cookie/storage-state handling according to local-first policy.
   - Connection/contact/message observations.
   - Action receipts for connect, pending check, follow-up, and manual send.
   - Rate-limit and platform-error reporting.
   - Duplicate-effect detection.
   - Server-side persistence, summaries, analytics, notifications, and state transitions.

5. WhatsApp contracts:
   - List only device-bound WhatsApp profiles.
   - QR publish, expire, clear, reset, and connected transition.
   - Health, disconnected, banned, reconnect-attempt reporting.
   - Message send receipts.
   - Bounded message sync batches with cursor and dedupe hashes.
   - Delivery-status monotonicity.
   - Optional session backup only if approved.
   - Server-owned task leases; remove direct WhatsApp task claims from MongoDB.

6. Email contracts:
   - Prefer backend-side SMTP/IMAP execution.
   - Move sending, mailbox selection, daily caps, reply scans, enrichment, and credential decryption server-side.
   - If local execution is still required, create a one-use, task-bound, mailbox-specific credential lease with:
     - maximum 60-second redemption window;
     - no caching;
     - one mailbox only;
     - one task only;
     - no mailbox enumeration;
     - audit;
     - explicit product/security approval.
   - Delivery, bounce, reply, unsubscribe, open/click, and mailbox-health results are typed commands.
   - Desktop may not read general mailbox rows.

7. Server-side domain operations:
   - Campaign reconciliation and task scheduling.
   - Sequence resolution and advancement.
   - Deal/lead/message/action-log/notification mutations.
   - LLM generation, qualification, summaries, and enrichment.
   - Analytics derivation.
   - State-machine validation.
   - Task retry and stale lease recovery.

8. Offline behavior:
   - No new action begins without an unexpired lease.
   - Permit finishing an already leased external action during a short outage.
   - Persist only a minimal encrypted outbox:
     - task ID;
     - lease ID;
     - idempotency key;
     - typed result/observation;
     - timestamps;
     - sanitized error evidence.
   - Do not cache broad tenant datasets or server credentials.
   - Server decides how to handle late results.

For external actions such as LinkedIn messages, WhatsApp messages, and email sends, design for this failure case:

1. External platform accepted the action.
2. Desktop lost network before reporting completion.
3. Lease expired and task was retried.

Use platform evidence, deterministic idempotency keys, conversation/message reconciliation, and pre-retry side-effect verification to avoid duplicates.

Phase 4: remove all desktop MongoDB dependencies
================================================

Refactor desktop execution so it uses only v2 DTOs and browser adapters.

Required changes:

1. Replace all desktop runtime uses of:
   - `Campaign.get`
   - `Lead.get`
   - `Deal.get/save`
   - `Task.objects`
   - `User.get`
   - `SiteConfig.load`
   - `WhatsAppProfile` MongoDB model persistence
   - `Mailbox` MongoDB model persistence
   - `ActionLog`, `Notification`, `ChatMessage`, and `Message` model access
   - `get_mongodb_collection`
   - encryption helpers that require backend keys
   - local qualifier/model-blob writes.

2. Separate browser mechanics from persistence.
   - Pure browser adapters accept a typed task DTO.
   - They return typed observations/results.
   - They cannot import MongoDB models.
   - Server services apply state transitions.

3. Local state:
   - Device key and rotating refresh credential.
   - Browser profile/session directories.
   - Configuration cache with no secrets.
   - Minimal encrypted outbox.
   - Capability/version metadata.
   - No server database data cache beyond active task snapshots.

4. Packaging:
   - Remove `pymongo` and `openoutreach.mongodb*` from desktop requirements and PyInstaller hidden imports.
   - Ensure transitive imports do not pull them back in.
   - Add a build-time architecture test that fails if forbidden modules are included.
   - Inspect the final binary/SBOM.

5. Network:
   - Add tests that run the complete desktop workflow with Atlas DNS/TCP blocked.
   - Capture outbound requests and verify only approved backend and automation-platform destinations occur.
   - No direct database traffic under any feature combination.

6. Preserve browser sessions across secure upgrades.
   - Migrate existing local LinkedIn browser profiles without forced re-login when safe.
   - Migrate WhatsApp local state where possible.
   - Never copy backend keys or MongoDB credentials into the new local store.
   - Test interrupted migrations and rollback to the immediately previous secure API-only build.

Phase 5: permanently delete bootstrap and enforce infrastructure boundary
=======================================================================

Once secure clients cover every task type:

1. Delete:
   - `/api/daemon/bootstrap`
   - `RemoteClient.bootstrap`
   - `_apply_server_env`
   - desktop MongoDB initialization
   - global desktop decryption-key injection
   - provider-secret injection
   - secret-bearing config fields
   - any fallback equivalent.

2. Enforce configuration allowlists.
   - Daemon response schemas must enumerate safe fields.
   - Unknown/internal settings cannot be automatically serialized.
   - Add recursive forbidden-field tests.

3. Add infrastructure controls and code/config support:
   - Atlas reachable only from backend workload identities/private networking.
   - Separate least-privilege database users per backend workload.
   - No database ingress from customer/public desktop networks.
   - Application name and workload identity in MongoDB connections for auditability.
   - Old database credentials rejected.
   - Implement manifests/runbooks but do not change production without approval.

4. Version enforcement:
   - Clients below the minimum secure version cannot enroll, refresh daemon credentials, claim tasks, download session/credential material, or execute automation.
   - Rollback artifacts must also be secure API-only builds.

Phase 6: key rotation, token invalidation, and data re-encryption
===============================================================

Implement all required code and migration tooling.

1. JWT:
   - Move from shared HS256 fallback to asymmetric signing with key IDs.
   - Separate access, daemon, refresh/session, password-reset, and email-verification purposes.
   - Add short-lived access tokens.
   - Add server-side refresh sessions/families and revocation.
   - Add user session version/global incident cutoff.
   - Test rejection of every old key/token type.

2. MongoDB:
   - Prepare safe user/credential rotation procedure.
   - Terminate old sessions.
   - Verify old credentials cannot connect.
   - Audit source IPs and collection access.
   - Do not execute production rotation without authorization.

3. Provider keys:
   - Inventory every key that the desktop could receive.
   - Add rotation and usage-review runbooks.
   - Ensure new keys are server-only.
   - Add cost/anomaly alerts.

4. Encryption:
   - Introduce envelope-encryption records with version, key ID, algorithm, nonce, ciphertext, and context binding.
   - Use a server-only KMS/HSM KEK and per-record or per-profile/tenant DEKs as approved.
   - Implement dual-read/new-write migration:
     - read old ciphertext using sealed old key server-side;
     - always write new format;
     - batch re-encrypt existing data;
     - dry-run and counts;
     - resumable checkpoints;
     - backups;
     - sampled decrypt verification;
     - quarantine failures;
     - old-key-use telemetry;
     - final old-key disable.
   - Cover:
     - LinkedIn credentials;
     - LinkedIn cookies/storage state;
     - WhatsApp session state;
     - SMTP credentials;
     - IMAP credentials;
     - proxy credentials;
     - any other encrypted fields found during audit.

5. Be explicit that re-encryption does not undo prior plaintext exposure.
   - Add credential-remediation state and UI support.
   - Support LinkedIn reauthentication/session invalidation.
   - Support WhatsApp relink.
   - Support SMTP/IMAP app-password replacement.
   - Do not silently claim old credentials are safe.

Phase 7: cleanup and production verification
============================================

1. Remove all v1 daemon routes, clients, schemas, feature flags, model adapters, and migration shims after the secure soak period.
2. Delete obsolete desktop token/profile cache fields when rollback support no longer needs them.
3. Finalize:
   - v2 API lifecycle/version policy;
   - SLOs and error budgets;
   - rate limits;
   - audit retention;
   - privacy/data minimization;
   - abuse controls;
   - on-call runbooks;
   - disaster recovery;
   - secure rollback.
4. Update all architecture and operator documentation.
5. Ensure no release or rollback artifact contains the insecure path.

Mandatory test strategy
=======================

Implement and run:

1. Unit tests:
   - tenant repository predicates;
   - authorization policy;
   - token purpose/audience;
   - device scopes/bindings;
   - proof-of-possession canonicalization;
   - nonce replay;
   - refresh rotation/reuse;
   - task transition reducers;
   - lease state;
   - idempotency;
   - encryption key ring/migration.

2. API integration tests:
   - enrollment;
   - device token exchange;
   - revoke;
   - profile binding;
   - configuration;
   - claim/renew/complete/fail/cancel;
   - channel observations;
   - QR/session state;
   - email receipts;
   - version blocking.

3. Multi-tenant negative tests:
   - Tenant A attempts every operation on tenant B identifiers.
   - Nested and batch payload attacks.
   - Same tenant, unbound profile.
   - Wrong channel/device/lease.
   - Forged tenant/user/profile fields.
   - Confirm zero cross-tenant data exposure or mutation.

4. Token tests:
   - old exposed key rejected;
   - human token rejected by daemon v2;
   - daemon token rejected by human/admin APIs;
   - refresh/reset/verification token rejected by resources;
   - revoked device;
   - expired token;
   - wrong audience;
   - wrong scope;
   - refresh reuse;
   - signing-key rotation.

5. Desktop tests:
   - fresh enrollment;
   - restart;
   - proactive refresh;
   - account/profile switch;
   - keychain loss;
   - device revoke;
   - offline outbox;
   - lease expiration;
   - crash before/after external effect;
   - local session migration;
   - minimum-version enforcement.

6. Upgrade and rollback:
   - last insecure version to first secure version;
   - failed/interrupted update;
   - signed asset and digest validation;
   - downgrade refusal below secure floor;
   - rollback only to a secure API-only artifact.

7. LinkedIn:
   - existing local cookies/profile;
   - login credential lease if retained;
   - checkpoint/CAPTCHA;
   - connect;
   - pending check;
   - follow-up;
   - manual message;
   - contact capture;
   - message synchronization;
   - duplicate-effect prevention;
   - rate limits.

8. WhatsApp:
   - new profile;
   - QR generation/publish/expiry/reset;
   - scan and local state persistence;
   - restart;
   - send;
   - follow-up;
   - sync and delivery statuses;
   - health;
   - reconnect cap;
   - disconnect;
   - ban;
   - relink;
   - multiple profiles;
   - tenant isolation.

9. Email:
   - SMTP TLS/auth/send;
   - server-side mailbox selection;
   - daily cap;
   - bounce;
   - IMAP reply;
   - open/click/unsubscribe effects;
   - app-password failure;
   - credential lease only if approved;
   - tenant isolation.

10. Reliability/load:
    - concurrent task claims;
    - lease renewal/revoke races;
    - result replay;
    - deployment during tasks;
    - device sleep/wake;
    - clock skew;
    - Atlas/backend interruption;
    - projected 10x device load;
    - long soak through token rotations.

11. Security tests:
    - No MongoDB connection from desktop.
    - No MongoDB driver in desktop artifact.
    - No `SECRET_KEY`, `MONGODB_URI`, LLM key, JWT signing key, encryption key, or equivalent in responses, environment, logs, files, crash dumps, network traces, or binaries.
    - Modified desktop cannot access another tenant or unbound profile.
    - Modified desktop cannot forge an accepted JWT.
    - Modified desktop cannot arbitrarily complete another task.
    - Modified desktop cannot replay completed work.
    - Fuzz path/query/body/batch/cursor/idempotency input.
    - Test NoSQL injection, SSRF, oversized/compressed input, and rate-limit bypass.
    - Run or prepare for an external penetration test.

Definition of done
==================

Do not report completion until all of the following are true, or clearly identified as requiring external authorization:

- The secret-bearing bootstrap path is impossible to use.
- The LLM/provider key is not returned to desktop.
- Refresh/reset/verification tokens cannot authorize resources.
- A complete daemon-only device authentication system exists.
- Device/profile/channel scopes are enforced.
- Every desktop operation is available through typed v2 APIs.
- LinkedIn, WhatsApp, and email workflows no longer directly access MongoDB.
- Scheduling, reconciliation, LLM, enrichment, state transitions, analytics, logs, and notifications are server-owned.
- The desktop artifact contains no MongoDB driver or server-secret mechanism.
- Atlas can be blocked from desktops without breaking supported workflows.
- Old insecure versions are denied.
- Rotation, token invalidation, encryption migration, and reauth tooling exist and are tested.
- Multi-tenant isolation tests prove tenant A cannot access or alter tenant B.
- Upgrade, rollback, offline, restart, and duplicate-effect scenarios pass.
- Documentation and the existing migration plan reflect actual implementation status.
- Focused tests, full tests, lint, and type checking pass.
- No unrelated user work was overwritten.
- Remaining external production actions are listed precisely with commands/runbooks, risks, required approver, and verification procedure.

Final handoff format
====================

At the end, provide:

1. Security outcome achieved.
2. Completed phases and checkboxes.
3. Files and major components changed.
4. API contracts introduced or removed.
5. Database migrations and their status.
6. Desktop packaging/dependency changes.
7. Authentication, rotation, and revocation behavior.
8. Test commands run and exact results.
9. Evidence that desktop cannot receive secrets or access MongoDB.
10. Evidence from multi-tenant negative tests.
11. Performance/reliability results.
12. Any remaining risks.
13. Exact external actions awaiting authorization, especially:
    - production bootstrap cutoff;
    - JWT signing-key retirement;
    - MongoDB credential/network rotation;
    - provider-key rotation;
    - encryption migration activation;
    - forced desktop upgrade;
    - customer notification or credential resets.
14. Secure rollback procedure.
15. Links to the updated migration plan, architecture documentation, and key implementation files.

Do not respond with another high-level plan. Begin by reading the repository instructions, inspecting the dirty worktree, validating the current vulnerability paths, and then implement Phase 0 safely.