# Desktop Bootstrap Security Migration Plan

Status: implementation in progress; production rollout remains approval-gated
Audit snapshot: 2026-08-28, including uncommitted working-tree changes present at review time
Owners: Security, Backend/Platform, Desktop, Automation/Channels, SRE

## Executive decision

Treat the current desktop bootstrap design as a critical secret disclosure, not as a theoretical weakness. An authenticated customer desktop can retrieve the shared MongoDB connection string and the application's global `SECRET_KEY`; that key is the fallback for both JWT signing and credential/session encryption. A customer-controlled process can therefore bypass application authorization, enumerate or modify other tenants' database records, decrypt credential material it can read, and forge user JWTs when `JWT_SECRET_KEY` is not independently configured.

The recommended target is a fully API-based desktop daemon behind a dedicated daemon gateway boundary. The desktop receives only short-lived, profile-scoped daemon access tokens. It never receives a database credential, JWT signing key, encryption key, provider API key, or a ciphertext that requires a global backend key to decrypt. Browser automation remains local; all durable shared state is read or mutated through tenant-enforcing backend commands and queries.

This is a forced security migration. Compatibility may be preserved at the API-contract level for supported upgraded clients, but the legacy secret-returning bootstrap cannot remain available as a compatibility mechanism.

## 1. Evidence, facts, and assumptions

### 1.1 Labels

- **Confirmed** means directly established by the reviewed repository at the cited line.
- **Inferred** means the conclusion follows from confirmed code but production configuration or deployment evidence is not in this repository.
- **Assumption to validate** means implementation planning needs a product or operational answer that the repository cannot supply.

### 1.2 Confirmed critical path

1. `GET /api/daemon/bootstrap` uses the normal bearer-token dependency, verifies that the requested LinkedIn profile belongs to the authenticated user, and returns `SECRET_KEY`, `MONGODB_URI`, and `MONGODB_NAME` ([daemon.py](../openoutreach/api_v2/routers/daemon.py#L335), lines 335-359).
2. `RemoteClient.bootstrap()` calls that endpoint once during startup ([remote_client.py](../openoutreach/core/remote_client.py#L153), lines 153-164). Repository search found no other caller.
3. `RemoteDaemon.start()` fetches bootstrap, injects its values into the process, and initializes a `MongoClient` against the returned database ([daemon_remote.py](../openoutreach/core/daemon_remote.py#L287), lines 287-315; [daemon_remote.py](../openoutreach/core/daemon_remote.py#L358), lines 358-396).
4. The shared Mongo client accepts the URI without a tenant-enforcing wrapper and exposes arbitrary named collections ([connection.py](../openoutreach/mongodb/connection.py#L92), lines 92-105; [connection.py](../openoutreach/mongodb/connection.py#L134), lines 134-152; [connection.py](../openoutreach/mongodb/connection.py#L222), lines 222-232).
5. JWT validation uses HS256 and `settings.jwt_secret` ([dependencies_v2.py](../openoutreach/api_v2/dependencies_v2.py#L20), lines 20-49). `jwt_secret` falls back to global `SECRET_KEY` when `JWT_SECRET_KEY` is unset ([config.py](../openoutreach/config.py#L177), lines 177-185). Access and refresh tokens are signed with that value ([auth.py](../openoutreach/api_v2/routers/auth.py#L74), lines 74-102).
6. Credential encryption similarly falls back to `SECRET_KEY` ([mongodb/crypto.py](../openoutreach/mongodb/crypto.py#L19), lines 19-63). LinkedIn cookies, WhatsApp storage state, LinkedIn passwords, and SMTP/IMAP passwords are decrypted in desktop-reachable paths ([linkedin/models/__init__.py](../openoutreach/linkedin/models/__init__.py#L145), lines 145-200; [whatsapp/models/profile.py](../openoutreach/whatsapp/models/profile.py#L61), lines 61-83; [emails/models.py](../openoutreach/emails/models.py#L146), lines 146-176).
7. `/api/daemon/config` also returns the backend LLM provider key and related server configuration to the desktop ([daemon.py](../openoutreach/api_v2/routers/daemon.py#L287), lines 287-332), and the desktop injects them into its environment ([daemon_remote.py](../openoutreach/core/daemon_remote.py#L371), lines 371-396). This is an additional provider-secret exposure and is in scope.
8. The locally generated `daemon_id` is a UUID stored in a plaintext file; the server does not register it, bind it to a profile, or use it in an authorization predicate ([daemon_remote.py](../openoutreach/core/daemon_remote.py#L113), lines 113-122; [daemon.py](../openoutreach/api_v2/routers/daemon.py#L111), lines 111-158).
9. The desktop stores the human access token, refresh token, and cached profile ID in the OS keychain ([desktop/auth.py](../openoutreach/desktop/auth.py#L21), lines 21-67). Access tokens last 24 hours and refresh tokens 30 days by default ([config.py](../openoutreach/config.py#L30), lines 30-35). Refresh tokens are stateless signed JWTs and are not rotated in the refresh response ([auth.py](../openoutreach/api_v2/routers/auth.py#L293), lines 293-382). Logout only clears client cookies; it does not revoke tokens server-side ([auth.py](../openoutreach/api_v2/routers/auth.py#L425), lines 425-438).
10. Startup resolves the first current LinkedIn profile using the human token, falls back to the cached profile ID when the API is unreachable, and then starts the daemon ([desktop/app.py](../openoutreach/desktop/app.py#L628), lines 628-685). The daemon itself cannot operate offline at startup because subscription, config, bootstrap, and database connection are required ([daemon_remote.py](../openoutreach/core/daemon_remote.py#L237), lines 237-326).

### 1.3 Confirmed authorization gaps relevant to migration

- Task claim verifies profile ownership but the atomic task predicate omits `user_id`; its safety depends on globally correct profile IDs and task rows ([daemon.py](../openoutreach/api_v2/routers/daemon.py#L128), lines 128-158).
- Task result loads by task ID alone. It verifies ownership only if `linkedin_profile_id` happens to be inside `task.payload`, even though the Task model has top-level `user_id` and `linkedin_profile_id` fields ([daemon.py](../openoutreach/api_v2/routers/daemon.py#L173), lines 173-201; [mongodb/models.py](../openoutreach/mongodb/models.py#L4590), lines 4590-4600).
- Generic model helpers frequently read or update by `_id` without `user_id`, for example Lead ([mongodb/models.py](../openoutreach/mongodb/models.py#L160), lines 160-199), Deal ([mongodb/models.py](../openoutreach/mongodb/models.py#L1289), lines 1289-1333), Task ([mongodb/models.py](../openoutreach/mongodb/models.py#L4602), lines 4602-4626), and ChatMessage ([mongodb/models_extended.py](../openoutreach/mongodb/models_extended.py#L104), lines 104-139). These are unsafe primitives for an untrusted desktop and fragile inside APIs unless ownership is established before every call.
- The normal auth dependency accepts both access and refresh token types on protected endpoints ([dependencies_v2.py](../openoutreach/api_v2/dependencies_v2.py#L26), lines 26-49). A refresh token should never authorize resource endpoints.

### 1.4 Assumptions to validate before Phase 0 exit

- Whether the reviewed bootstrap endpoint and the same credentials are currently deployed in production.
- Whether `JWT_SECRET_KEY` and `COOKIE_ENCRYPTION_KEY` are independently configured in production; absent proof, assume both fall back to `SECRET_KEY`.
- Whether the MongoDB URI is a cluster-wide administrative/read-write credential or a narrower application credential; absent proof, assume it reaches every application collection.
- Whether MongoDB Atlas audit logging, reverse-proxy access logging, and immutable application logs were enabled for the full exposure window.
- Number and minimum version of installed desktop clients. Repository documentation says there are no external users, but production/customer status must be confirmed by Product and Support.
- Whether customers expect cross-device recovery of LinkedIn/WhatsApp browser sessions. The target defaults to local-only sessions with an optional server-encrypted recovery feature.

## 2. Current architecture audit

### 2.1 Bootstrap and startup sequence

```text
Human login -> access + refresh JWT -> desktop OS keychain
     |
     v
resolve first LinkedIn profile -> subscription -> config (+ LLM key)
     |
     v
/daemon/bootstrap -> global SECRET_KEY + shared MongoDB URI/name
     |
     v
inject environment -> connect directly to Atlas -> load/decrypt shared records
     |
     +-> API claim/result/heartbeat for LinkedIn tasks
     +-> direct MongoDB claim/result/state for WhatsApp tasks
     +-> direct MongoDB domain writes from LinkedIn/WhatsApp/email handlers
```

The API already mediates subscription checks, LinkedIn task claim/result, cookies, session state, config, credentials, profile details, campaign summary, and scheduling/reconciliation ([remote_client.py](../openoutreach/core/remote_client.py#L104), lines 104-355). However, most handler inputs and all domain side effects are still loaded/saved through shared MongoDB models.

### 2.2 Desktop dependency inventory

| Dependency | Confirmed desktop use | Security consequence | Migration disposition |
|---|---|---|---|
| `SECRET_KEY` | Injected at startup; used through fallback encryption and potentially JWT signing | Global signing/decryption capability on customer host | Never return; separate JWT and encryption key rings server-side |
| `MONGODB_URI` / name | Initializes direct Atlas client | Bypasses all API authorization and tenant filters | Remove MongoDB package from desktop artifact and deny database network access |
| LLM provider key | Returned by `/config` and injected | Provider account theft/cost abuse | Perform LLM generation server-side through gateway APIs |
| LinkedIn encrypted password | `/daemon/credentials` returns ciphertext; desktop decrypts with global key ([daemon.py](../openoutreach/api_v2/routers/daemon.py#L499), lines 499-541; [daemon_remote.py](../openoutreach/core/daemon_remote.py#L603), lines 603-610) | Global key is required locally | Return a one-use plaintext credential lease over TLS, or store credential locally; never return ciphertext/key pair |
| LinkedIn cookies | API currently returns decrypted cookie JSON; desktop uploads plaintext over TLS for server encryption ([daemon.py](../openoutreach/api_v2/routers/daemon.py#L206), lines 206-248; [daemon.py](../openoutreach/api_v2/routers/daemon.py#L533), lines 533-540) | Session is necessarily visible to the executing desktop | Make local browser profile primary; optional profile-scoped backup through session API |
| Proxy credentials | Server encrypts them and desktop decrypts them with global key ([daemon.py](../openoutreach/api_v2/routers/daemon.py#L601), lines 601-616; [daemon_remote.py](../openoutreach/core/daemon_remote.py#L564), lines 564-569) | Same global-key dependency | One-use plaintext lease or local secret; omit unless profile is configured for proxy |
| WhatsApp storage state | Desktop reads/writes encrypted state directly in `whatsapp_profiles` | Session theft across tenants if DB/key exposed | Keep local primary; API upload/download only for optional recovery |
| SMTP/IMAP password | Desktop loads mailbox row and decrypts password for send/reply scan | All tenant mail credentials exposed by shared DB/key | Prefer server-side email execution; if local egress is required, issue one-use mailbox credential lease scoped to task/mailbox |

### 2.3 MongoDB collections and desktop operations

This inventory is for code reachable from `RemoteDaemon` task/session paths, not every server collection in the repository. `read` includes `find`, `get`, `count`, or model hydration; `write` includes insert/upsert/update/delete/state transition.

| Collection | Desktop operation(s) and call paths | Target owner |
|---|---|---|
| `tasks` | Direct WhatsApp claim, running/completed/failed transitions, and stale recovery ([daemon_remote.py](../openoutreach/core/daemon_remote.py#L734), lines 734-824); task lookup is also reachable from follow-up agent | Daemon gateway: atomic claim/lease/complete/fail/renew |
| `campaigns` | Read full campaigns for LinkedIn, WhatsApp, email execution; qualifier may write `model_blob` ([daemon_remote.py](../openoutreach/core/daemon_remote.py#L1032), lines 1032-1165; [linkedin/ml/qualifier.py](../openoutreach/linkedin/ml/qualifier.py#L350)) | Gateway returns immutable execution snapshot; training/model write is backend job |
| `leads` | Read target/contact/profile; update degree, cached profile, email resolution, WhatsApp registration/bounce/unsubscribe fields. Generic helpers are not tenant scoped ([mongodb/models.py](../openoutreach/mongodb/models.py#L160), lines 160-283) | Gateway task input plus typed observation/result commands |
| `deals` | Candidate queries, idempotency checks, funnel/channel/sequence state, summaries, timestamps, retry metadata; direct writes occur across every channel ([linkedin/tasks/follow_up.py](../openoutreach/linkedin/tasks/follow_up.py#L254), lines 254-336; [whatsapp/tasks/send_message.py](../openoutreach/whatsapp/tasks/send_message.py#L63), lines 63-210; [emails/tasks/handle_email_follow_up.py](../openoutreach/emails/tasks/handle_email_follow_up.py#L59), lines 59-276) | Server-side command handler with state-machine and expected-version checks |
| `chat_messages` | Read conversation context; upsert LinkedIn/WhatsApp/email inbound/outbound messages and delivery status ([mongodb/models_extended.py](../openoutreach/mongodb/models_extended.py#L104), lines 104-178; [whatsapp/tasks/sync.py](../openoutreach/whatsapp/tasks/sync.py#L193), lines 193-343) | Batch message-observation API with dedupe/idempotency keys |
| `messages` | Read queued manual message by ID; deal timestamp write after send ([linkedin/tasks/send_manual_message.py](../openoutreach/linkedin/tasks/send_manual_message.py#L7), lines 7-71) | Gateway embeds message content in leased task and accepts send receipt |
| `action_logs` | Insert success/failure/action records and count for idempotency/rate limits ([daemon_remote.py](../openoutreach/core/daemon_remote.py#L1002), lines 1002-1017; [whatsapp/tasks/send_message.py](../openoutreach/whatsapp/tasks/send_message.py#L103), lines 103-210) | Append-only server API; server derives tenant/profile/task from token/lease |
| `notifications` | Count dedupe keys and create warnings for follow-up/WhatsApp conditions ([whatsapp/tasks/follow_up.py](../openoutreach/whatsapp/tasks/follow_up.py#L147), lines 147-181) | Backend domain service, not desktop-authored arbitrary records |
| `site_config` | Read per-user pacing, active hours, AI rules/provider settings through model calls | Existing `/daemon/config`, stripped of provider secrets and expanded as typed config |
| `users` | Read user record for LLM/task context ([daemon_remote.py](../openoutreach/core/daemon_remote.py#L1143), lines 1143-1148) | Never return a general user row; gateway returns minimal seller identity/settings |
| `linkedin_profiles` | Direct action logging/session-linked model behavior; cookie and status persistence also have existing APIs | Existing hardened profile/session APIs |
| `linkedin_credentials` | Backend endpoint reads credential, but desktop receives encrypted password and decrypts it | Server-only vault/credential lease endpoint |
| `whatsapp_profiles` | List profiles, read/decrypt/write session state, QR, status, phone/name, health, reconnect, ban ([whatsapp/models/profile.py](../openoutreach/whatsapp/models/profile.py#L61), lines 61-158; [whatsapp/browser/launch.py](../openoutreach/whatsapp/browser/launch.py#L24), lines 24-138) | WhatsApp daemon APIs; local browser state primary |
| `mailboxes` | Select least-loaded mailbox, decrypt SMTP/IMAP secrets, increment/health/pause state ([emails/models.py](../openoutreach/emails/models.py#L20), lines 20-107; [emails/models.py](../openoutreach/emails/models.py#L220), lines 220-315) | Prefer backend email worker; otherwise task-bound credential lease and receipt API |
| `sequence_events` | Insert sequence audit events and resolve transitions when sequence code is run ([sequence_executor.py](../openoutreach/core/sequence_executor.py#L25), lines 25-43) | Server-side sequence service only |
| `email_domain_patterns` | Cache enrichment patterns in email enrichment path | Backend enrichment service; daemon receives resolved recipient only |

Collections used by user-facing APIs but not confirmed as desktop-daemon task-path operations (for example `campaign_templates`, `tracked_links`, `link_clicks`, `admin_audit_logs`) must remain server-only and should be included in database-credential blast-radius review, not added to daemon APIs.

### 2.4 Existing APIs that can be retained and hardened

- Heartbeat, subscription, config, profile resolution, LinkedIn task claim/result, reconcile, cookies/session status, credential fetch, and campaign summary already exist under `/api/daemon/*` ([daemon.py](../openoutreach/api_v2/routers/daemon.py#L75), lines 75-359 and 362-643).
- User-facing tenant-scoped APIs already cover campaign CRUD, leads/messages, settings, mailboxes, analytics, notifications, LinkedIn profiles/credentials, and WhatsApp profile/QR management. Router registration is centralized in [main.py](../openoutreach/api_v2/main.py#L113), lines 113-180.
- WhatsApp profile and QR endpoints perform explicit ownership checks ([whatsapp/api/router.py](../openoutreach/whatsapp/api/router.py#L49), lines 49-170). They can remain frontend APIs, while daemon-only state changes move to separate contracts.
- Existing user-facing APIs are not automatically safe for daemon use: their scopes are human-user-wide, payloads are UI-oriented, and they do not implement task leases, idempotency, or restricted mutation sets.

### 2.5 Missing daemon APIs

1. Device enrollment, approval, key registration, token exchange/rotation, device list/revoke, and minimum-version policy.
2. Atomic task leases for all channels, including WhatsApp; lease renewal; idempotent completion/failure; server-side stale lease recovery.
3. Self-contained execution snapshots for task/campaign/lead/deal/message/config data, with field minimization and no arbitrary record lookup.
4. Typed observations/commands for LinkedIn connection state, contact capture, inbound/outbound messages, delivery receipts, limits, summaries, and action logs.
5. WhatsApp profile assignment, QR publish/clear, session status/health/ban/reconnect reporting, message sync, and optional encrypted session backup.
6. Email send work, mailbox lease or server-side send, IMAP sync results, bounce/reply/delivery reports, and credential-health reporting.
7. Server-side LLM generation and qualification endpoints so no provider key or model blob is required on desktop.
8. Version/capability negotiation, kill switch, retry hints, cursor/checkpoint APIs, and bounded offline result queue semantics.

## 3. Threat model and security invariants

### 3.1 Adversaries

- A legitimate tenant who fully controls and instruments their desktop daemon.
- Malware or another local user with access to the desktop process, files, keychain session, or browser profile.
- A stolen desktop refresh token or enrolled device private key.
- A replaying client, modified old client, or client that sends forged task results.
- An attacker who previously obtained the global bootstrap response and may retain database dumps, JWTs, ciphertext, or plaintext credentials indefinitely.

### 3.2 Required invariants

- A desktop authorized for tenant A cannot read, infer existence of, or mutate tenant B data, even with arbitrary requests and a modified binary.
- No desktop response or artifact contains backend signing keys, encryption KEKs/DEKs, database credentials, provider secrets, or administrative tokens.
- Every daemon operation is authorized from server-derived `(tenant_id, device_id, profile_id, task_id, lease_id, scopes)`, never trusted request fields alone.
- IDs are treated as locators, not authorization. Every database query includes server-derived tenant ownership or traverses a previously authorized aggregate.
- Every mutating request is idempotent and replay bounded. Task state transitions are server-enforced.
- A revoked device loses access within the access-token lifetime and cannot refresh.
- A compromised desktop can misuse only the profiles and task capabilities currently delegated to that device. It cannot be made safe from abuse of its own authorized LinkedIn/WhatsApp session; that is a product/abuse-control problem, not tenant isolation.
- Browser/session data exposed to the executing desktop is minimized and never enables another tenant or backend compromise.

## 4. Target architecture options

| Option | Isolation and forgery properties | Advantages | Material drawbacks | Decision |
|---|---|---|---|---|
| Fully API-based daemon | Strongest: database and signing/encryption keys remain server-side; all operations tenant checked | Auditable, revocable, supports schema evolution and rate limiting | Largest refactor; more API traffic; offline execution must be bounded | **Recommended foundation** |
| Per-device/per-tenant MongoDB credentials | Database roles can constrain databases/collections | Faster bridge for simple schemas | MongoDB permissions do not reliably express row-level `user_id` isolation in shared collections; client can bypass business invariants, scrape all tenant data, or corrupt state; rotation and schema changes remain hard | Reject as target; use only if every tenant has a physically separate database and risk is accepted |
| Dedicated daemon gateway/service | Same isolation as API approach when it alone reaches DB; clear trust boundary and scaling policy | Purpose-built contracts, audit, rate limits, versioning; can later deploy separately | New service boundary/operations overhead | **Recommended boundary**, initially a modular FastAPI router/service to reduce deployment risk |
| Hybrid compatibility | New gateway plus temporarily supported upgraded contract versions | Enables staged rollout and shadow validation | Any legacy path that returns shared secrets preserves the critical vulnerability | Use only for API contract coexistence; no secret-returning compatibility after containment |

### 4.1 Recommended design

Create a `daemon_gateway` application boundary in the existing backend first, with its own authentication dependency, schemas, services, repositories, audit log, rate limits, and feature flags. It may share the FastAPI deployment initially, but desktop routes must not call generic unscoped model helpers. Once load and ownership are understood it can be extracted into a separately deployed service without changing client contracts.

The desktop contains only browser automation adapters, a small encrypted local state store, an API client, an offline outbox, and device identity. Campaign reconciliation, scheduling, LLM calls, enrichment, state machines, tenant data joins, analytics, notifications, credential encryption, and database access run server-side.

### 4.2 Identity and credentials

- Enrollment begins from a recently authenticated human session with step-up confirmation. Backend creates a one-time, 10-minute enrollment code bound to user, selected profiles, requested device name, and allowed channels.
- Desktop generates a non-exportability-preferred Ed25519/P-256 key in Windows CNG/DPAPI or macOS Keychain/Secure Enclave when available. Hardware binding improves theft resistance but is not a trust guarantee on a customer-controlled host.
- Desktop redeems the code with its public key, installation ID, app version, platform, and capabilities. Backend creates `daemon_devices` and `daemon_profile_bindings` records and returns a one-time rotating device refresh credential. Store only its Argon2id/SHA-256-peppered hash server-side.
- Access tokens are server-signed asymmetrically, five minutes maximum, with `iss`, `aud=daemon-gateway`, `sub=device_id`, `tenant_id`, `profile_ids`, `scopes`, `jti`, `iat`, `nbf`, `exp`, and `client_version`. Resource APIs reject human and refresh tokens. Requests include a proof-of-possession signature over method, path, body digest, timestamp, nonce, and access-token `jti`.
- Refresh credentials rotate on every use with reuse detection and a bounded device session family. Revocation disables the family and bindings immediately. Access-token revocation is enforced through a short TTL plus a cached device status/version check for sensitive operations.
- Device bindings are explicit per LinkedIn/WhatsApp profile and channel. A token for one profile cannot enumerate or act on another profile in the same tenant unless separately bound.

This prevents JWT forgery because no symmetric JWT signing material reaches the desktop. Device proof does not make a fully compromised host trustworthy; it makes credentials scoped, attributable, rotatable, and useless for other tenants.

### 4.3 Browser and credential security

- LinkedIn and WhatsApp persistent browser state lives locally in an OS-user-protected directory. Do not upload it by default.
- If recovery/sync is a product requirement, upload through a profile-scoped session endpoint. Backend encrypts under an envelope-encrypted per-profile DEK with KMS/HSM KEK and stores `key_id`, algorithm, nonce, ciphertext, and version. The desktop receives only the session plaintext for its own bound profile over TLS.
- Prefer entering LinkedIn credentials locally and retaining them only in the OS credential vault. If web-managed credentials must remain, issue a single-use credential lease only when a bound profile needs interactive login. Lease response contains the minimum plaintext credential, is `Cache-Control: no-store`, expires in at most 60 seconds, is never logged, and cannot be replayed.
- QR images are short-lived enrollment artifacts. Desktop publishes a QR with expiration; frontend reads it through the existing tenant API; backend clears it on scan/timeout. Session storage never travels with the QR.
- Prefer moving SMTP/IMAP execution to backend workers. If local mail egress is a hard requirement, use a task-bound, one-use mailbox credential lease. Never return all tenant mailboxes or encrypted secrets.

### 4.4 Offline and upgrade behavior

- No new task may start without an unexpired task lease. The desktop may finish a currently leased browser action during a brief outage and enqueue a signed result locally.
- Offline outbox contains only task ID, lease ID, idempotency key, result/observation, timestamps, and minimal error evidence; it must not cache broad campaign/lead datasets or server credentials.
- Lease duration is action-specific (for example 5 minutes for sends, longer with heartbeat renewals for interactive login). The server decides whether a late result is accepted, reconciled as duplicate, or rejected.
- Version negotiation occurs during token exchange and heartbeat. Server publishes `minimum_supported`, `minimum_secure`, capabilities, deprecation deadline, and `force_update`. Versions below `minimum_secure` cannot enroll, refresh, bootstrap, or claim work.
- Updater assets remain digest verified ([desktop/updater.py](../openoutreach/desktop/updater.py#L114), lines 114-165; [desktop/updater.py](../openoutreach/desktop/updater.py#L174), lines 174-225). Production release signing and an authenticated update manifest are required before forced rollout.

## 5. Proposed daemon API contracts

All routes use `/api/daemon/v2`, daemon-only authentication, `Cache-Control: no-store`, structured audit events, strict Pydantic schemas with unknown fields rejected, request size limits, and consistent error bodies. IDs in request bodies are checked against token bindings and lease state.

### 5.1 Enrollment and token lifecycle

| Method/path | Request | Response / rules |
|---|---|---|
| `POST /enrollment-codes` (human auth) | `profile_ids`, `channels`, `device_name` | One-time code, expiry, approved scopes; step-up and CSRF required |
| `POST /devices/enroll` | code, public key, version, platform, capabilities | `device_id`, rotating refresh credential, bindings; one redemption only |
| `POST /tokens/exchange` | device refresh credential + proof | 5-minute daemon access token + rotated refresh credential; reuse revokes family |
| `GET /devices` / `DELETE /devices/{id}` (human auth) | none / reason | List last seen, IP, profiles, version; revoke device and active leases |
| `GET /compatibility` | version/capabilities | minimum versions, flags, server capabilities, upgrade URL |

### 5.2 Work and configuration

| Method/path | Request | Response / rules |
|---|---|---|
| `GET /configuration` | bound `profile_id`, ETag | Typed active hours/rate limits/channel settings; no provider keys |
| `POST /tasks/claim` | profile, supported task types, capacity | Atomic lease plus self-contained execution snapshot; query includes tenant/profile/channel/status/due time |
| `POST /tasks/{id}/renew` | lease ID, progress | New lease expiry if device/profile still authorized |
| `POST /tasks/{id}/complete` | lease ID, idempotency key, typed result/observations | Server transaction/conditional updates; duplicate returns original outcome |
| `POST /tasks/{id}/fail` | lease ID, category, retryability, sanitized error | Server owns retry/backoff/final state; no arbitrary status field |
| `POST /tasks/{id}/cancel-ack` | lease ID | Desktop stops/cleans local work after server cancellation |

The claim snapshot contains only fields needed by that handler: task type/version, campaign execution policy, target public profile/contact, generated message or generation inputs, rate-limit budget, and allowed result schema. It never permits `GET /campaign/{arbitrary_id}` or `GET /lead/{arbitrary_id}` under daemon auth.

### 5.3 Channel observations

| Method/path | Purpose and authorization |
|---|---|
| `POST /linkedin/sessions/{profile}/state` | Login/challenge/username/health for bound profile |
| `POST /linkedin/sessions/{profile}/backup` | Optional storage-state upload; size/version bounded, backend encrypted |
| `POST /linkedin/observations` | Batch connection/contact/message observations tied to active task lease |
| `POST /linkedin/actions/{task}/receipt` | Sent/connected/pending result with platform idempotency evidence |
| `GET /whatsapp/profiles` | Only profiles bound to device, minimal session metadata |
| `POST /whatsapp/profiles/{id}/qr` / `DELETE .../qr` | Publish/clear expiring QR for bound disconnected profile |
| `POST /whatsapp/profiles/{id}/state` | Connected/disconnected/banned/health/reconnect result; allowed transition matrix |
| `POST /whatsapp/profiles/{id}/session-backup` | Optional versioned backup, never general profile update |
| `POST /whatsapp/messages/sync` | Bounded batch, cursor, hashes, direction/delivery status; server maps to authorized deals |
| `POST /email/actions/{task}/receipt` | Delivery/message ID/bounce/reply observation for leased task |
| `POST /email/mailboxes/{id}/health` | Restricted health transition; requires task-bound mailbox grant |
| `POST /events/batch` | Append-only structured daemon diagnostics; server supplies tenant/device identity |

LLM message generation, qualification, summaries, email enrichment, campaign reconciliation, sequence advancement, analytics, and notification creation remain internal backend operations and are not general daemon APIs.

## 6. Phased implementation roadmap

### Phase 0 — Incident containment, threat model, telemetry, and safeguards

**Goal.** Stop further global-secret disclosure, preserve evidence, determine exposure, and establish a safe emergency operating posture before refactoring.

**Files/modules likely to change.** `openoutreach/api_v2/routers/daemon.py`, `openoutreach/api_v2/dependencies_v2.py`, `openoutreach/config.py`, `openoutreach/api_v2/main.py`, logging middleware/new security audit module, reverse-proxy/WAF configuration, deployment secrets, `openoutreach/desktop/__version__.py`, `openoutreach/desktop/updater.py`, release workflow, incident runbook.

**Backend changes.** Immediately gate `/daemon/bootstrap` with a server kill switch defaulting off; remove LLM key from `/daemon/config`; reject refresh tokens at resource dependencies; add a minimum-secure-version check and rate limits; log bootstrap attempts without logging query tokens or response bodies. If production exposure is confirmed, disable bootstrap and direct Mongo access even if automation pauses.

**Desktop changes.** Publish an emergency build that does not log secrets, clearly reports “secure upgrade required,” and can be force-updated. Do not create a replacement secret-bearing endpoint.

**Frontend changes.** Device/security banner, automation-paused status, and customer reauthentication instructions. Admin view for affected versions and last-seen devices.

**Database/schema.** Add append-only `security_audit_events` and optionally `desktop_installations`/version inventory. Do not store raw access/refresh tokens, enrollment codes, secrets, QR bytes, credential plaintext, or request bodies.

**API contracts.** Temporary `GET /api/daemon/compatibility` and deterministic `426 upgrade_required`/`503 security_maintenance` errors. Bootstrap returns no secret and is `410 Gone` once the emergency cutoff is active.

**Authentication/authorization.** Only access tokens authorize resource endpoints. Add explicit account/profile ownership and current account status checks to every retained daemon route. Rate-limit by user, IP, profile, and token `jti` where available.

**Rollout/flags.** `DAEMON_BOOTSTRAP_ENABLED=false`, `DAEMON_MIN_SECURE_VERSION`, `DAEMON_TASK_CLAIM_ENABLED`, and tenant allowlist for controlled testing. Turn on audit-only alerts before cutoff, then cutoff globally.

**Backward compatibility.** Security cutoff overrides legacy compatibility. Old clients receive upgrade/maintenance response and cannot retrieve secrets or claim new tasks.

**Rollback.** Roll back UI or telemetry separately, but never re-enable global-secret responses. Operational rollback is pause automation or enable only the v2 allowlist.

**Tests/security tests.** Assert bootstrap never serializes secret/URI/LLM key; refresh token cannot call resource routes; response/log redaction; rate-limit tests; old version gets 426; WAF/proxy log validation.

**Metrics/logs/alerts.** Bootstrap requests by user/profile/IP/version/status; distinct source IPs; Mongo connections by credential/IP/app name; JWT auth failures and impossible user/IP changes; forced-upgrade success; paused automation count. Page Security on any post-cutoff secret response or old database credential use.

**Exit criteria.** Global secret disclosure stopped; evidence snapshot preserved; incident commander assigned; production key topology documented; emergency release available; impacted user/device/version inventory established.

**Complexity.** Medium, operationally high risk.

#### Implementation evidence (2026-08-28)

- [x] `/api/daemon/bootstrap` is permanently disabled with `410 Gone` and
  `Cache-Control: no-store`; it never reads or serializes server settings.
- [x] `/api/daemon/config` is an allowlisted behavior response with no
  `server_env`, provider key, database, or encryption field.
- [x] Resource authentication rejects every JWT whose `type` is not `access`.
- [x] Legacy daemon routes fail closed with `426` unless `X-Daemon-Version`
  meets the secure floor (`2.0.0`); the client reports its version.
- [x] Desktop startup no longer calls bootstrap, injects server environment,
  or initializes MongoDB from server-provided material.
- [x] Recursive forbidden-field/secret-like response checks and focused
  regression tests were added.
- [ ] Device enrollment, asymmetric daemon credentials, tenant repositories,
  typed v2 task leases, and API-only channel execution remain required work.

#### Phase 2/3 implementation evidence (2026-08-28)

- [x] Added backend-only RS256 daemon access-token issuance/validation with
  audience, purpose, device, tenant, profile, scope, key ID, and five-minute
  lifetime claims.
- [x] Added hashed one-time enrollment-code and rotating-refresh primitives,
  plus canonical request proof signing and replay timestamp checks.
- [x] Added persistent device enrollment/revocation, nonce storage, refresh-
  family rotation/reuse detection, and device/profile/channel binding checks.
- [x] Added daemon-only v2 compatibility/configuration, typed task lease
  routes, bounded idempotent observations, and atomic tenant/device/profile/
  channel predicates.
- [ ] Desktop key generation/integration and production enrollment UI remain.

- [x] Added versioned AES-GCM envelope records with tenant/profile context
  binding, dual-read/new-write support, and resumable dry-run migration helper.
- [x] Added daemon nonce TTL indexes and server-side device/refresh/enrollment
  indexes.
- [ ] Production KMS integration, migration execution, key retirement, and
  credential/session reauthentication remain approval-gated operations.

- [x] v2 requests now re-check current device revocation/version and intersect
  token claims with current profile/channel bindings on every request.
- [x] Added the incident rotation runbook covering JWT, MongoDB, provider,
  encryption, session invalidation, verification, and secure rollback.
- [x] Removed MongoDB/server-model hidden imports and broad package data from
  the PyInstaller desktop spec; the desktop entry point is now an API-only
  fail-closed secure daemon shell.
- [ ] Browser adapters, local session persistence, and all LinkedIn/WhatsApp/
  email execution workflows still need migration onto v2 contracts.
- [x] Added dry-run-by-default tenant ownership backfill tooling with trusted
  profile/campaign resolution, idempotent predicates, checkpoints, and
  quarantine for ambiguous records.
- [x] Added append-only redacted security-event persistence and indexes.
- [x] Token exchange now requires a device-key proof, fresh timestamp, and
  one-time nonce; completion/failure payloads and event batches are bounded.
- [ ] Backfill execution, reconciliation review, and production index rollout
  remain approval-gated.

### Phase 1 — Authorization and tenant-isolation hardening

**Goal.** Make the backend safe as the sole data boundary before increasing daemon API coverage.

**Files/modules likely to change.** `openoutreach/api_v2/dependencies_v2.py`, `routers/daemon.py`, `routers/campaigns.py`, `routers/leads.py`, `routers/messages.py`, `routers/mailboxes.py`, `whatsapp/api/router.py`, `mongodb/models*.py`, `mongodb/dal.py`, `mongodb/indexes.py`, new `api_v2/repositories/*` and authorization policy module.

**Backend changes.** Introduce typed tenant context; repository methods require `tenant_id`; replace get-by-ID-then-check patterns with atomic `{_id, user_id}` queries; make not-owned indistinguishable from missing; validate cross-aggregate ownership; fix task claim/result predicates; centralize state transitions and idempotency.

**Desktop changes.** None beyond handling normalized 403/404/409/426 responses.

**Frontend changes.** Only error handling if status semantics change; no broader data access.

**Database/schema.** Backfill missing `user_id` on tasks, deals, leads, messages, logs, notifications, mailboxes, profiles, and sequence events; quarantine ambiguous rows; add compound tenant indexes and unique constraints such as `(user_id, _id)`, `(user_id, linkedin_profile_id, status, scheduled_at)`, and tenant-scoped dedupe keys.

**API contracts.** Current endpoints remain, but ownership is mandatory. Task result requires top-level task ownership and valid current lease/status; arbitrary `status` strings are rejected.

**Authentication/authorization.** Human access tokens only on human APIs; daemon v1 temporarily uses access token but is profile constrained. Refresh/email/reset tokens are rejected by `get_current_user`. Never accept `user_id` from a resource request as authority.

**Rollout/flags.** Shadow-query legacy and tenant-scoped results, compare counts, then enable per route. Add `STRICT_TENANT_REPOSITORIES` with fail-closed behavior.

**Backward compatibility.** Preserve response shapes where safe. Rows lacking tenant ownership are unavailable until backfilled; do not fall back to global lookup.

**Rollback.** Disable strict route flag only after confirming old query still has an independent ownership check. Never roll back the token-type restriction or expose quarantined rows.

**Tests/security tests.** Parameterized two-tenant matrix for every CRUD/daemon endpoint; swapped IDs; missing `user_id`; payload/profile mismatch; mass assignment; object enumeration; concurrency on claims/results; property tests for repository predicates.

**Metrics/logs/alerts.** Cross-tenant denial counts without leaking target IDs, shadow-query mismatches, quarantined rows, duplicate keys, task transition conflicts, repository calls missing context (fatal in production).

**Exit criteria.** All daemon-reachable data access uses tenant repositories; zero unexplained shadow mismatches; multi-tenant negative suite passes; data backfill reconciled and signed off.

**Complexity.** Large.

#### Implementation evidence (2026-08-28)

- [x] Added a non-empty `TenantContext` and fail-closed ownership-predicate
  builder; client-supplied ownership fields are rejected.
- [x] Daemon task claims now require immutable top-level `user_id` plus profile,
  due, and pending predicates; unbackfilled tasks are unavailable.
- [x] Task results now validate the status union and atomically require the
  server-derived tenant and `RUNNING` state; payload ownership is ignored.
- [x] Profile cookie/session metadata updates include tenant ownership in the
  write predicate.
- [ ] Complete repository migration, ownership backfill/quarantine, device and
  channel binding, and the full two-tenant endpoint matrix remain required.

### Phase 2 — Scoped daemon authentication and device enrollment

**Goal.** Replace human bearer credentials as daemon identity with revocable device/profile/channel credentials.

**Files/modules likely to change.** New `api_v2/routers/daemon_devices.py`, `api_v2/security/daemon_auth.py`, schemas, models/indexes; `core/remote_client.py`, `core/daemon_remote.py`, `desktop/auth.py`, `desktop/app.py`, protocol/login frontend, Settings security/device UI.

**Backend changes.** Implement enrollment, public-key binding, daemon audience tokens, rotating refresh families/reuse detection, device/profile bindings, scope checks, revocation, nonce/replay cache, last-seen/version/capability records, and audit events.

**Desktop changes.** Generate/store device key; redeem one-time code; store device refresh credential separately from human web session; sign requests; refresh proactively; erase old human daemon token use after enrollment; support revoke/re-enroll.

**Frontend changes.** “Connect this desktop” flow with profile/channel selection and step-up; device list, last seen, version, profile bindings, revoke action, and suspicious-device guidance.

**Database/schema.** `daemon_devices`, `daemon_profile_bindings`, `daemon_refresh_families`, `daemon_enrollment_codes`, `daemon_nonces`, `daemon_security_events`; TTL indexes for codes/nonces and indexes by tenant/device/status.

**API contracts.** Enrollment/token/device contracts in section 5.1. Tokens are audience restricted and contain no general user API scope.

**Authentication/authorization.** Human step-up creates enrollment code; daemon proof redeems/exchanges. Profile scope intersection occurs on every operation. Local key protection is defense in depth, not a reason to trust the host.

**Rollout/flags.** Enroll internal devices first, then pilot tenants. `DAEMON_AUTH_V2_REQUIRED` by tenant/version; issue both old human session and new daemon credential during pilot, but v2 routes accept only daemon tokens.

**Backward compatibility.** Existing web login continues. Supported transitional clients can enroll after human login; old clients cannot use v2. Do not let v2 device tokens call human APIs.

**Rollback.** Revoke pilot device credentials and pause v2 work; fall back only to the contained API-based pilot path, never bootstrap secrets.

**Tests/security tests.** Enrollment code replay, device-key mismatch, stolen refresh reuse, nonce replay, wrong audience/scope/profile/tenant, revoked device, version floor, clock skew, keychain loss, re-enrollment, concurrent refresh rotation.

**Metrics/logs/alerts.** Enrollment/revocation/exchange rates, refresh reuse, invalid proofs, device IP/geo changes, obsolete versions, token issue latency, per-device denials.

**Exit criteria.** Pilot devices operate with daemon-only credentials; revocation meets five-minute maximum; no daemon v2 request relies on a human token; threat-model review complete.

**Complexity.** Large.

### Phase 3 — Daemon gateway APIs and server-side domain operations

**Goal.** Provide every operation needed to execute automation without direct database or global/provider secrets.

**Files/modules likely to change.** New `api_v2/routers/daemon_v2.py`, `api_v2/services/daemon_gateway/*`, repositories and schemas; refactor `core/scheduler.py`, `core/sequence_executor.py`, `linkedin/tasks/*`, `whatsapp/tasks/*`, `emails/tasks/*`, `core/agents/*`, `core/db/*`, `core/llm.py`; extend `remote_client.py`.

**Backend changes.** Implement atomic task leasing for all channels; execution snapshots; typed completion/observation commands; server-owned scheduling/reconciliation, LLM/enrichment, deal/sequence transitions, analytics/log/notification writes; WhatsApp state and message sync; server-side email execution or tightly scoped credential leases.

**Desktop changes.** Add v2 client methods and DTOs; separate pure browser adapters from persistence-aware handlers; produce observations/receipts instead of model saves; bounded encrypted offline outbox; lease renew/cancel handling.

**Frontend changes.** Device task diagnostics, pending QR/status, mailbox execution-location disclosure, and actionable reauth states. Existing business views continue consuming server data.

**Database/schema.** Add task `lease_id`, `leased_by_device_id`, `lease_expires_at`, `attempt`, `result_version`, `idempotency_key`, `record_version`; observation dedupe hashes/cursors; channel health events; optional per-profile encrypted session backup metadata.

**API contracts.** Section 5.2 and 5.3. Define versioned discriminated unions per task/result type; strict maximum batch/page sizes; `ETag` for config; `409 lease_conflict`, `410 lease_expired`, `422 invalid_transition`, `429 rate_limited` with `retry_after`.

**Authentication/authorization.** Every claim is filtered by token tenant, bound profile, channel scopes, subscription, version, and capacity. Every result must match current device/task/lease and permitted transition. Server derives all ownership fields.

**Rollout/flags.** Per task type and tenant: shadow snapshot generation, dual-read comparison, then v2 execution. Start heartbeat/config, then task lease/result, LinkedIn, WhatsApp, email. `DAEMON_V2_TASK_TYPES` and per-channel kill switches.

**Backward compatibility.** V1 and v2 task contracts may coexist for upgraded API-only clients. Do not dual-write from desktop and backend simultaneously; choose one authoritative writer per task type/tenant.

**Rollback.** Stop issuing affected v2 task type, expire/requeue leases server-side, restore previous API-only writer if available. Do not restore direct DB.

**Tests/security tests.** Contract tests, lease concurrency/expiry, idempotent replay, malformed/oversized batches, forged result fields, state-machine invariants, duplicate platform effects, server LLM/enrichment behavior, chaos tests for result lost after external send.

**Metrics/logs/alerts.** Claim latency/empty rate, lease expiry/renewal/conflict, task success and duplicate suppression by type/version, API payload/latency/error, observation lag, channel health, LLM cost, email/WA/LinkedIn platform errors.

**Exit criteria.** Gateway contract covers every operation in section 2.3; channel regression suites pass; one pilot tenant runs each channel with database access disabled on desktop.

**Complexity.** Extra large; critical path.

### Phase 4 — Migrate desktop execution away from MongoDB

**Goal.** Remove all runtime imports and behavior that let the desktop read or write shared MongoDB.

**Files/modules likely to change.** `core/daemon_remote.py`, `core/remote_client.py`, desktop spec/requirements, `linkedin/tasks/*`, `whatsapp/browser/*`, `whatsapp/tasks/*`, `emails/*`, new desktop browser adapters/local store/outbox; tests and build workflow.

**Backend changes.** Enable v2 contracts by task type, compare outcomes to legacy baselines, and run scheduler/reconciliation exclusively server-side.

**Desktop changes.** Replace `Campaign.get`, `Lead.get`, `Deal.save`, `Task.objects`, `WhatsAppProfile` DB models, mailbox models, ActionLog/Notification/ChatMessage writes, and qualifier training with API DTOs. Store only local browser profiles, device credentials, config cache, and outbox. Remove `openoutreach.mongodb*` and `pymongo` from PyInstaller hidden imports/dependencies (currently explicitly bundled in [desktop/openoutreach.spec](../desktop/openoutreach.spec#L92), lines 92-95).

**Frontend changes.** Display offline/outbox/lease status and clear remediation messages; no data-path change.

**Database/schema.** No desktop-visible schema. Complete server backfills and record-version support; retain legacy fields during observation window.

**API contracts.** Desktop uses v2 only. Add capability negotiation so server never sends unsupported task shape.

**Authentication/authorization.** Device token only; browser adapters receive a task-scoped DTO and cannot make general data queries.

**Rollout/flags.** Canary signed desktop builds; disable database egress locally/in test harness; enable one task type at a time. Shadow compare state/result timelines without duplicating external actions.

**Backward compatibility.** Auto-upgrade supported clients before switching their tenant. Old insecure versions remain blocked. Preserve local session directories across upgrade; include schema migration and downgrade compatibility for local outbox only.

**Rollback.** Roll back to the immediately previous API-only signed client and pause incompatible tasks. Server expires/requeues leases. Never roll back to a MongoDB-capable build.

**Tests/security tests.** Static import/package scan for `pymongo`, `mongodb_uri`, `SECRET_KEY`; network test proving no Atlas DNS/TCP; end-to-end all task types; local profile migration; crash/restart/outbox; update/downgrade; offline lease expiration; corrupted local store.

**Metrics/logs/alerts.** Client capability adoption, task parity, outbox size/age, restart recovery, update failure, unexpected network destinations, old client attempts, session reauth rate.

**Exit criteria.** Production candidate artifact contains no Mongo driver/server secret handling; all supported workflows pass with Atlas blocked; pilot parity accepted for at least one full scheduling window.

**Complexity.** Extra large.

### Phase 5 — Remove bootstrap secrets and enforce the trust boundary

**Goal.** Make it technically impossible for any desktop version to retrieve backend secrets or connect to the shared database.

**Files/modules likely to change.** Delete bootstrap code in `routers/daemon.py`, `remote_client.py`, `daemon_remote.py`; remove env injection; config schema; desktop spec/requirements; deployment/WAF/Atlas network policy; secret scanning policy.

**Backend changes.** Delete `/api/daemon/bootstrap`; remove LLM key from daemon config; add response-schema denylist defense for secret-like fields; separate server JWT/encryption/provider/database settings from any daemon serializer.

**Desktop changes.** Delete `bootstrap()` and `_apply_server_env()`; no settings singleton patching; no Mongo initialization; no global decrypt helpers; use local vault and gateway.

**Frontend changes.** Force-update countdown and final unsupported-client messaging.

**Database/schema.** No schema requirement. Change Atlas firewall/private networking so customer networks cannot reach the cluster; use distinct least-privilege credentials per backend workload.

**API contracts.** `/api/daemon/bootstrap` is permanently `410` without body details, then removed after telemetry window. `/configuration` contains an explicit allowlisted schema.

**Authentication/authorization.** Only backend workload identities can reach MongoDB. Daemon credentials cannot be exchanged for human or infrastructure credentials.

**Rollout/flags.** Preflight telemetry shows zero supported clients calling bootstrap; enforce version floor; disable route; rotate network/DB credentials; remove code next release.

**Backward compatibility.** None for insecure clients. Contract compatibility applies only to secure v2 minor versions.

**Rollback.** Roll back application code only if it still contains no secret response. If outage occurs, pause claims or roll back to prior API-only client/gateway version.

**Tests/security tests.** Source/binary string scan; endpoint tests for all auth states; schema fuzzing; egress-denied end-to-end; attempt arbitrary Mongo URI injection; verify no secret in logs/crash dumps/environment.

**Metrics/logs/alerts.** Bootstrap 410 hits, unsupported versions, Atlas rejected connections, secret scanner findings, configuration response schema violations.

**Exit criteria.** Endpoint and code removed; Atlas unreachable from customer networks; zero server secrets/provider keys in desktop binary, process environment, API traffic, or logs.

**Complexity.** Medium after Phases 3-4.

### Phase 6 — Revoke/rotate exposed material and deprecate legacy clients

**Goal.** Invalidate all material that could have been obtained before cutoff and complete credential/session remediation.

**Files/modules likely to change.** Deployment secret management, auth key ring, encryption service/migration command, User/token schema, credential/session models, incident tooling, frontend reauth flows, support runbooks.

**Backend changes.** Rotate Mongo credentials and network policy; switch JWT signing to asymmetric keys with `kid`; invalidate all old access/refresh tokens using signing-key retirement plus token/session version; rotate provider keys exposed through `/config`; move encryption to envelope key ring and re-encrypt all stored secrets server-side.

**Desktop changes.** Re-enroll device, discard human daemon tokens, clear obsolete environment/local caches, prompt only for profiles/mailboxes whose sessions or credentials must be re-established.

**Frontend changes.** Global session sign-out notice; device re-enrollment; LinkedIn/WhatsApp/mailbox credential health and guided reauth; incident communications link.

**Database/schema.** `auth_session_version`/refresh-session records; ciphertext envelope fields (`key_id`, `version`, `nonce`, `ciphertext`); migration checkpoints and irrecoverable-record quarantine; credential compromise/remediation status.

**API contracts.** Token responses include `kid`-signed access tokens and opaque rotating refresh credential; session/credential endpoints report `reauth_required` without secret detail.

**Authentication/authorization.** Retire old symmetric verification key after a tightly bounded overlap used only for web session migration; never accept tokens signed by exposed key on daemon/admin routes. Revoked devices and refresh families fail closed.

**Rollout/flags.** Dual-read/single-write encryption: backend can decrypt old key in memory and always writes new envelope; batch re-encrypt; verify counts; disable old-key decrypt. Coordinate global JWT sign-out and provider rotations. Rotation order is detailed in section 7.

**Backward compatibility.** Users reauthenticate. Old desktop versions and old refresh tokens are permanently invalid. Data ciphertext remains readable during controlled server-only key migration.

**Rollback.** Keep old encryption key sealed and server-only until migration verification/backups pass; it may be temporarily enabled for decrypt-only recovery by break-glass approval. Do not restore old JWT, Mongo, or provider credentials.

**Tests/security tests.** Old/new ciphertext fixtures, interrupted/resumed migration, wrong `kid`, old JWT rejection, refresh-family revocation, provider-key failure handling, reauth workflow, backup restore, sampled full decrypt verification.

**Metrics/logs/alerts.** Rows migrated/failed by secret type, old-key decrypt attempts, old JWT/refresh use, old Mongo credential attempts, provider key errors, reauth completion, support volume.

**Exit criteria.** Old JWT/Mongo/provider credentials rejected; all decryptable rows migrated and old encryption key disabled; affected user sessions/devices remediated; incident closure criteria met.

**Complexity.** Large and operationally sensitive.

### Phase 7 — Legacy removal and production-readiness verification

**Goal.** Remove transitional code/fields, prove the security properties, and transfer the system to steady-state operations.

**Files/modules likely to change.** Delete v1 daemon router/client paths and Mongo-aware remote handlers; simplify models; update `ARCHITECTURE.md`, `CLAUDE.md`, desktop docs, runbooks, threat model, CI security checks, dashboards/alerts.

**Backend changes.** Remove v1 flags/routes/serializers; enforce repository lint/architecture tests; finalize gateway SLOs, quotas, abuse controls, retention, and privacy controls.

**Desktop changes.** Remove migration shims, old token/profile cache fields, old session backup format, and unused dependencies. Keep secure local migration only as long as supported rollback needs it.

**Frontend changes.** Remove upgrade banners after unsupported-client traffic reaches agreed threshold; retain device management and security history.

**Database/schema.** Archive/drop obsolete bootstrap/device-v1 fields only after backup and retention approval; finalize indexes and TTL policies; verify tenant backfill constraints.

**API contracts.** Publish v2 lifecycle/versioning policy, error catalog, and compatibility window. Add contract snapshots to CI.

**Authentication/authorization.** Independent penetration test validates tenant, device, profile, scope, lease, replay, and revocation boundaries.

**Rollout/flags.** Delete flags only after sustained 100% secure-client traffic and rollback window. Progressive removal in staging, canary, then production.

**Backward compatibility.** Only documented secure v2 versions. Unsupported clients get 426 and cannot perform automation.

**Rollback.** Restore last secure v2 build/schema-compatible release; no legacy secrets/direct database path exists in rollback artifacts.

**Tests/security tests.** Full section 8 suite, external pen test, disaster recovery, capacity/load/soak, binary analysis, SBOM/signature verification, incident game day.

**Metrics/logs/alerts.** Gateway SLO/error budget, authorization denials, revocation latency, lease health, channel success/regression, secret scan, database network sources, supported-version distribution.

**Exit criteria.** Production checklist signed; no v1 traffic/code/credentials; pen-test critical/high findings closed; runbooks/game day complete; SLO observed through agreed soak period.

**Complexity.** Medium.

## 7. Secret-compromise response and rotation order

### 7.1 Must keys be rotated immediately?

**Yes.** Any legitimate desktop that completed bootstrap obtained the values. Under the required untrusted-desktop model, confidentiality is already lost even if logs show no malicious use.

Use this order, under an incident commander:

1. Preserve reverse-proxy/WAF/app/Atlas/auth/deployment logs and current configuration; restrict access to evidence.
2. Disable bootstrap and LLM-key return; block new task claims from insecure versions. If necessary, accept a temporary automation outage.
3. Separate `JWT_SECRET_KEY` from `SECRET_KEY`, deploy a new server-only signing key, and reject tokens signed with the exposed key. Force web and desktop re-login. The current stateless refresh design means retiring the signing key is the only reliable global invalidation; adding server-side session versions comes next.
4. Restrict Atlas network paths to backend workloads and rotate the exposed MongoDB user/password. Terminate existing sessions. Verify old credential attempts fail.
5. Rotate every provider secret returned via config, especially the LLM API key, and review provider usage/billing.
6. Deploy encryption key-ring dual-read/new-write support. Keep the old encryption key server-only for migration, set a new `COOKIE_ENCRYPTION_KEY`, and re-encrypt LinkedIn credentials/cookies, WhatsApp sessions, SMTP/IMAP passwords, proxy passwords, and any other ciphertext with record type/tenant/profile binding as authenticated associated data.
7. After complete verified migration and backup, disable old-key decryption. Destroy it according to incident/legal retention approval.

Rotating encryption at rest does not undo plaintext exposure if an attacker already copied the database and global key. Based on evidence and risk tolerance, revoke/reissue mailbox app passwords, invalidate LinkedIn sessions/change passwords, and require WhatsApp relink. At minimum, mark all as potentially compromised and provide one-click guided remediation.

### 7.2 Token invalidation design

- Immediate: retire exposed symmetric JWT key and force all sessions to authenticate again.
- Target: asymmetric access-token key ring with short TTL and `kid`; opaque, hashed, rotating refresh sessions with family reuse detection; per-user `auth_session_version`; per-device revocation and profile-binding versions.
- Password reset, email verification, web access, web refresh, and daemon access must use different audiences/keys or purpose-bound verification policies. The current dependency accepting refresh tokens on resource endpoints must be removed.

### 7.3 Evidence needed to assess abuse

- CDN/WAF/load-balancer/nginx access records for `/api/daemon/bootstrap` and `/api/daemon/config`: timestamp, source IP/ASN/country, authenticated subject if separately logged, profile ID, user agent, version, request ID, response status/bytes. Never reconstruct/log response bodies.
- Application auth logs: token subject, `jti` if present, login/refresh history, account changes, admin impersonation, password reset, and anomalous IP/device patterns.
- Atlas audit/database access logs: authentication/user, source IP, connection `appName`, collections/actions, bulk reads, aggregation/export behavior, index/admin operations, user/role changes, and continued use after cutoff.
- Domain audit: unusual cross-tenant record reads/writes where available, task claims/results, campaign/deal/message/action-log mutations, credential/session reads, mass deletes, and notification changes.
- Provider logs: LLM usage/key identity/cost/source IP; email provider logins/sends; GitHub release/update integrity; cloud/KMS/secret-manager access.
- Endpoint deployment history and desktop release/version adoption to establish the exposure window.

### 7.4 Incident and customer notification

1. Classify severity, retain counsel/privacy lead, open immutable timeline, assign evidence and remediation owners.
2. Establish facts and jurisdictions; determine whether credential/session/customer personal data access is reasonably likely.
3. Notify affected customers within contractual/legal deadlines with dates, exposed data categories, actions taken, required reauth/credential rotation, monitoring advice, and a support channel. Do not claim “no abuse” when logs are absent; say what could and could not be determined.
4. Provide targeted notifications when evidence identifies particular tenant data access or provider credential use; coordinate LinkedIn/WhatsApp/email resets.
5. Publish a post-incident review with root cause, blast radius, detection gaps, remediation owners/dates, and verification evidence.

## 8. Test strategy

### 8.1 Unit and static tests

- Tenant repository requires nonempty tenant context; generated Mongo predicates always contain server-derived tenant/profile constraints.
- Authorization policy matrix for device status, binding, scope, subscription, task/lease state, and version.
- JWT audience/type/key ID/expiry/skew; refresh rotation/reuse; proof signature and nonce replay.
- Task transition and idempotency reducers; observation validation/dedupe; encryption envelope/key rotation.
- Static forbidden-import scan for desktop (`pymongo`, `openoutreach.mongodb`, server settings/crypto); binary string and dependency scan for `MONGODB_URI`, secret values, provider keys.

### 8.2 API integration and multi-tenant isolation

Create tenants A and B, multiple profiles/devices per tenant, and execute every endpoint with:

- A token + B object ID in path, query, body, nested payload, batch, cursor, task result, and idempotency key.
- Correct tenant + unbound profile/wrong channel/wrong device/wrong lease.
- Human token on daemon API, daemon token on human/admin API, refresh/reset/verification token on resource API.
- Guessed/nonexistent IDs; ensure identical 404 behavior and no timing/material data oracle.
- Concurrency: two devices claim same task, renew vs revoke, complete after lease expiry, duplicate result after network loss.

Assertions include zero B records returned or changed, zero cross-tenant logs/notifications/analytics effects, and an authorization audit event without sensitive target disclosure.

### 8.3 Desktop and upgrade tests

- Fresh enroll, restart, token refresh, keychain loss, device revoke, account/profile switch, re-enroll, minimum-version block.
- Online/offline startup, network interruption before/during/after external action, outbox replay, lease expiry, duplicate effect reconciliation.
- Upgrade from last insecure version to first secure version while preserving local LinkedIn/WhatsApp browser profiles; forced update; failed update rollback; downgrade refusal below minimum secure version.
- Inspect process environment, files, logs, crash dumps, IPC, and network capture: no backend/global/provider secret or Mongo endpoint.

### 8.4 Channel regressions

- LinkedIn: existing cookies, password login, checkpoint/CAPTCHA headed relaunch, username discovery, connect, check pending, follow-up, manual message, cookie/local profile persistence, rate limits, idempotency.
- WhatsApp: new profile detection, QR publish/expire/reset/scan, local session restore, send, follow-up, inbound sync/dedupe/delivery status, health, reconnect cap, disconnected, banned, relink, multiple profiles.
- Email: SMTP TLS/auth/send, app-password failure, mailbox daily cap, bounce policy, IMAP reply scan, message IDs, unsubscribe/open/click effects, backend-worker and any approved local-lease mode.
- Campaign/sequence: reconcile, active hours/time zones, stale leases, channel routing, sequence step effects, duplicate prevention, deals/leads/messages/action logs/analytics/notifications consistency.

### 8.5 Load, reliability, and security validation

- Load task claim/renew/result and message sync at projected 10x device count; measure hot indexes and pool saturation.
- Soak through token rotations, backend deployments, Atlas failover, queue delays, device sleep/wake, and clock skew.
- Fuzz schemas, batch sizes, compressed payloads, errors, and identifiers; SSRF/path/NoSQL injection; rate-limit bypass.
- External penetration test with a modified desktop and full local control. Required proof: it cannot connect to MongoDB, obtain any global key/URI/provider secret, mint accepted JWTs, access another tenant/profile, mutate arbitrary state, or replay a completed task.
- Explicit endpoint tests assert `/api/daemon/bootstrap` returns no `secret_key`, `mongodb_uri`, `mongodb_name`, LLM key, or replacement-equivalent credential for unauthenticated, human-authenticated, daemon-authenticated, admin, old, and current clients.

## 9. Risks, tradeoffs, and mitigations

| Risk/tradeoff | Impact | Mitigation |
|---|---|---|
| Handler refactor is the largest effort | LinkedIn/WA/email code mixes browser actions with persistence | Introduce pure browser adapters and typed observations incrementally; one authoritative writer per task type |
| External action succeeds but result is lost | Duplicate connect/message/email | Leases + idempotency + channel-specific effect verification + reconciliation before retry |
| Forced cutoff breaks automation | Immediate customer-visible outage | Emergency signed release, clear UI/status, support playbook; security cutoff takes priority |
| Local-only session storage reduces cross-device recovery | More QR/login challenges after device loss | Product-approved optional server backup with per-profile envelope encryption |
| API traffic/latency grows | Slower actions and backend load | Self-contained snapshots, bounded batches, ETags, async observation ingestion, capacity tests |
| Device proof can be extracted on a compromised host | Attacker can act as that device temporarily | Narrow profile/scopes, short tokens, rotation/revocation, behavior/rate controls; do not overstate hardware identity |
| Encryption rotation can make credentials unreadable | Automation outage/data loss | Backup, dual-read/new-write, resumable migration, sampled decrypt verification, sealed old key |
| Email execution location | Backend IP/reputation or local secret exposure | Prefer provider OAuth/server worker; if local required, task-bound single mailbox lease |
| Missing audit history | Cannot prove non-abuse | Honest uncertainty in notices; add immutable logs now; use Atlas/provider corroboration |
| Old client population unknown | Cutover planning uncertainty | Version telemetry and minimum-version policy in Phase 0; Product decision on deadline |

Temporary mitigations before full migration:

- Disable bootstrap and LLM secret return; block insecure versions; pause automation if required.
- Set independent `JWT_SECRET_KEY` and `COOKIE_ENCRYPTION_KEY`; rotate JWT/Mongo/provider credentials as incident actions.
- Atlas private networking/IP allowlist to backend only; distinct workload users; audit logging and anomaly alerts.
- Shorten access-token lifetime; reject refresh tokens on resource APIs; rate-limit daemon endpoints.
- Fix task result/claim ownership and all high-risk get/update-by-ID paths.
- Disable channels/task types whose secure API path is not ready instead of retaining direct DB.

## 10. Critical path, staffing, and sequencing

Priority order:

1. Phase 0 containment and incident response — **Medium**.
2. Phase 1 tenant boundary — **Large**.
3. Phase 2 device identity — **Large**; can overlap late Phase 1 only after policy primitives stabilize.
4. Phase 3 gateway/domain APIs — **Extra large**, primary critical path.
5. Phase 4 desktop decoupling — **Extra large**, proceeds task type by task type alongside Phase 3.
6. Phase 5 secret/bootstrap/database removal — **Medium**, gated by secure client coverage.
7. Phase 6 permanent rotation/remediation — **Large**; emergency rotations begin in Phase 0, data re-encryption completes here.
8. Phase 7 cleanup/verification — **Medium**.

Required roles/skills:

- Security architect/incident commander; application security and penetration testing.
- Senior FastAPI/backend engineers experienced in authorization, MongoDB concurrency/indexing, idempotent distributed workflows, and cryptography integration.
- Desktop engineers for Windows/macOS key stores, code signing, secure update, Playwright lifecycle, offline storage, and migrations.
- LinkedIn, WhatsApp Web, email/SMTP/IMAP domain engineers for side-effect reconciliation and regression testing.
- SRE/platform engineer for Atlas/IAM/private networking, KMS/secret rotation, observability, WAF/rate limits, CI/CD, capacity, and disaster recovery.
- Frontend/product designer and Support/Customer Success for enrollment, forced-upgrade, reauth, and incident messaging.
- Privacy/legal/compliance for notification and evidence retention decisions.

## 11. Production release checklist

- [ ] Threat model and data-flow diagrams approved; assets, trust boundaries, abuse cases, and residual same-tenant risk documented.
- [ ] Bootstrap and config responses contain no backend/global/provider secrets; automated denylist and schema tests pass.
- [ ] Desktop artifact has no Mongo driver, URI, server crypto/signing code, or forbidden secret strings; SBOM reviewed.
- [ ] Atlas reachable only from approved backend workloads; old credential rejected and existing sessions terminated.
- [ ] JWT access/refresh/daemon purposes separated; old signing key rejected; device revoke/refresh-reuse tests pass.
- [ ] All gateway repository queries use server-derived tenant/profile scope; full two-tenant negative matrix passes.
- [ ] Task leases, idempotency, duplicate-effect reconciliation, cancellation, retry, and stale recovery pass per task type.
- [ ] LinkedIn, WhatsApp, email, campaign, deal/lead/message/log/analytics/notification regressions pass.
- [ ] Local browser sessions survive secure upgrade; reauth/relink flows tested; no plaintext secrets in logs/crash dumps/outbox.
- [ ] Signed updater and minimum-secure-version enforcement tested on Windows/macOS, including failed update and safe rollback.
- [ ] Load/soak/chaos targets and gateway SLOs met; dashboards, alerts, runbooks, on-call ownership active.
- [ ] Encryption migration backed up, resumable, verified, and old-key shutdown rehearsed.
- [ ] Incident evidence preserved; customer/legal notification decision recorded; provider and customer remediation tracked.
- [ ] External penetration test has no open critical/high issues and explicitly proves cross-tenant/global-secret properties.
- [ ] Rollback artifact is itself API-only and cannot restore bootstrap/direct DB access.
- [ ] Architecture and operator documentation updated; legacy code/flags removal date assigned.

## 12. Decisions requiring Product/Security approval

1. Whether to pause all desktop automation immediately while secure APIs are built; Security recommendation: yes if the endpoint/credentials have been deployed.
2. Forced-upgrade deadline and minimum secure desktop version; no exception may restore shared secrets.
3. Whether LinkedIn and WhatsApp session state is local-only or supports optional encrypted cross-device backup.
4. Whether LinkedIn credentials are entered/stored locally or remain web-managed through one-use leases.
5. Whether email execution moves server-side (recommended) or uses local task-bound credential leases.
6. Scope of customer credential/session resets: LinkedIn password/session, WhatsApp relink, SMTP/IMAP app-password rotation.
7. Incident classification, evidence-retention period, regulators/jurisdictions, and customer notification content/timing.
8. Device binding strength and platform support expectations (software keychain vs hardware-backed key when available).
9. Offline policy: maximum lease duration, which actions may finish offline, outbox retention, and late-result behavior.
10. Supported rollback/compatibility window and when insecure clients are permanently denied.
11. Whether the daemon gateway remains a module in the current FastAPI service or becomes a separately deployed service after stabilization.
12. SLOs, rate limits, data retention/privacy limits, abuse controls, and support staffing for device management.

## Final recommendation

Adopt the fully API-based daemon with a dedicated daemon gateway boundary, asymmetric server signing, rotating profile-scoped device credentials, server-enforced task leases and state transitions, local-first browser sessions, and server-only database/encryption/provider keys. Begin incident containment and key rotation immediately; do not wait for the full migration to stop returning secrets. The critical engineering path is tenant-safe repositories -> device identity -> complete gateway contracts -> desktop persistence decoupling -> irreversible bootstrap/database cutoff. No design that leaves a shared database credential or global decrypt/signing capability on a customer desktop satisfies the stated security objective.

## Repository implementation update (2026-08-28)

- [x] Desktop Ed25519 identity generation and OS-keychain persistence are
  implemented in `openoutreach/desktop/device_identity.py`; the backend stores
  only the public key and device metadata.
- [x] Desktop enrollment, proof-bound token exchange, rotating v2 refresh
  credentials, automatic re-exchange on expiry, typed lease calls, and bounded
  event ingestion are implemented in `secure_daemon.py` and `remote_client.py`.
- [x] All authenticated v2 resource calls require a fresh proof-of-possession
  signature and one-time nonce; typed LinkedIn, WhatsApp, email, and session
  observation/receipt routes enforce device/profile/channel scope.
- [x] v2 configuration reads only an allowlisted projection of per-tenant
  rate/active-hours fields and supports ETag/304 responses with `no-store`.
- [x] Backfill and encryption migration wrappers execute only when explicitly
  configured deployment variables exist; default remains dry-run/no-op and
  output contains counts/checkpoints only.
- [x] Focused security, desktop boundary, updater, and crypto tests pass;
  Ed25519 signing/keychain tests cover local identity behavior.
- [ ] Full LinkedIn/WhatsApp/email browser adapters and server-owned channel
  observation/action contracts remain incomplete.
- [ ] Production key retirement, Atlas credential/network changes, customer
  reauthentication, forced upgrade, index rollout, and external artifact/SBOM
  verification require authorized deployment access and approval.
