# Architecture

## Security migration boundary

The desktop is an untrusted API client. `/api/daemon/bootstrap` is permanently
disabled (`410`), legacy daemon routes enforce the secure version floor, and
v2 routes use asymmetric daemon tokens bound to tenant, device, profile, and
channel scopes. Device private keys and rotating refresh credentials stay in
the desktop OS keychain; server-only signing, encryption, provider, and
MongoDB credentials are never returned to the desktop. Secure desktop task
execution uses typed v2 leases and event receipts; MongoDB/model imports are
excluded from the PyInstaller spec. See the migration plan for remaining
channel-adapter and production rollout gates.

Detailed module documentation for OpenOutreach. See `CLAUDE.md` for rules and quick reference.

## High-Level Overview

OpenOutreach automates LinkedIn outreach through a persistent task queue executed by one of two daemon modes:

1. **Desktop daemon** (default): runs `openoutreach/core/daemon_remote.py` on the user's own machine using their residential IP.
2. **Cloud daemon** (paid add-on): runs `openoutreach/core/daemon.py` server-side in Docker on EC2, using proxies.

The server-side daemon uses MongoDB. The legacy desktop daemon is cut off
from bootstrap, provider secrets, and MongoDB; it fails closed until the
API-only v2 gateway is deployed. Desktop requests are HTTPS-only and must use
server-owned task APIs.

```
┌────────────────────────────────────────┐
│              AWS EC2                    │
│  ┌─────────────┐  ┌─────────────┐      │
│  │  Next.js    │  │  FastAPI    │      │
│  │  Frontend   │  │  API v2     │      │
│  └─────────────┘  └──────┬──────┘      │
│                          │              │
│                    ┌─────┘              │
│                    ▼                    │
│              ┌──────────┐              │
│              │  MongoDB │              │
│              │  Atlas   │              │
│              └──────────┘              │
└───────────────────▲────────────────────┘
                    │ HTTPS
        ┌───────────┴──────────────┐
        │     User's Desktop App   │
        │  pystray + Playwright    │
        │  (residential IP)        │
        └──────────────────────────┘
```

## Project Layout

```

The daemon security boundary is implemented under `openoutreach/api_v2`: the
legacy bootstrap endpoint is disabled, v2 uses daemon-only RS256 credentials
and server-checked device bindings, and task leases are tenant/profile/channel
scoped. Desktop execution is fail-closed until all handlers use these APIs.
openoutreach/
├── api_v2/          # FastAPI routers, schemas, dependencies
├── billing/         # Stripe integration, plan enforcement, trial/expiry
├── core/            # Daemon, task queue, scheduler, LLM factory, follow-up agent, remote client
├── crm/             # Lead and Deal models (MongoDB)
├── chat/            # ChatMessage model (MongoDB)
├── linkedin/        # Browser, discovery pipeline, ML qualifier, task handlers
├── emails/          # Email enrichment (free waterfall finder)
├── desktop/         # System tray app, auto-updater, protocol handler, keychain auth
└── mongodb/         # Models base class, connection, DAL helpers

frontend/
├── src/app/         # Next.js App Router pages
├── src/components/  # UI components (shadcn/ui)
└── src/lib/         # API client, auth store, hooks

docs/                # Proxy guide, desktop app, billing, platform remediation
```

## Multi-Tenant Architecture (FastAPI + MongoDB)

Every MongoDB document carries a `user_id` field:
- `User` - base user account (Supabase SSO or email/password)
- `LinkedInProfile` - each user can have multiple; `linkedin_profile_id` scopes tasks and sessions
- `Campaign` - owned by user, executed by a specific profile, shareable with team members
- `Deal`, `Lead`, `Task`, `ActionLog`, `Notification`, etc. - all scoped to user

**Campaign team access**: `Campaign.user_id` (owner), `Campaign.linkedin_profile_id` (executor), `Campaign.team_member_ids` (additional users). `Campaign.has_access(user_id)` returns true for owner or team member.

**Per-profile rate limiting**: each `LinkedInProfile` has independent rate limits. `SmartRateLimitContext` tracks detectability score + multipliers per profile. `ActionLog` tracks actions per profile for daily counting.

### Multi-Tenant Security

Profile ownership check:
```python
collection.find_one({"_id": profile_id, "user_id": user_id})
```

Campaign access:
```python
# List: owner OR team member
{"$or": [{"user_id": user_id}, {"team_member_ids": user_id}]}

# Detail/mutate: access check
if not campaign.has_access(user_id):
    raise HTTPException(403, "Access denied")

# Delete: owner only
if user_id != campaign.user_id:
    raise HTTPException(403, "Only owner can delete")
```

## API (FastAPI v2)

Routers live in `openoutreach/api_v2/routers/`. All routes are registered in `api_v2/main.py`.

**Auth** (`/api/auth/`): register, login, logout, /me, refresh token, Supabase SSO callback.

**LinkedIn Profiles** (`/api/linkedin-profiles`): CRUD, cookies upload, health status.

**Campaigns** (`/api/campaigns`): CRUD with access control.

**Daemon** (`/api/daemon`): heartbeat, task claim/result, cookie sync, session state, config, credentials.

**Settings** (`/api/settings`): `SiteConfig` read/write (LLM, rate limits, active hours, guardrails).

**Billing** (`/api/billing`): Stripe portal, plan status, webhook handler.

**Admin** (`/api/admin`): user management, audit log, platform health - authenticated admin-only endpoints.

**Analytics** (`/api/analytics`): overview totals and per-campaign metrics with period filtering.

## Data Models

### MongoDB Models (openoutreach/mongodb/)

All models extend the base `MongoModel` class from `openoutreach/mongodb/models/base.py`. Document IDs are stored as `_id` (ObjectId) and serialized to strings.

**SiteConfig** (`core/models/site_config.py`) - singleton per user (`pk=user_id`). Fields: `llm_provider` (openai/anthropic/google/groq/mistral/cohere/openai_compatible), `llm_api_key`, `ai_model`, `llm_api_base`, `ai_writing_style`, `ai_say_rules`, `ai_avoid_rules` (follow-up guardrails), `enable_active_hours`, `active_start_hour`, `active_end_hour`, `active_timezone`, `active_days`, `enable_smart_rate_limiting`, `aggressiveness_preset`, `velocity`. Loaded via `SiteConfig.load(user_id=...)`.

**Campaign** (`core/models/campaign.py`) - `name`, `user_id`, `linkedin_profile_id`, `team_member_ids`, `product_pitch`, `campaign_objective`, `booking_link`, `icp_titles`, `follow_up_strategy`, `target_degrees` (default `[2, 3]`), `is_freemium`, `action_fraction`, `seed_public_ids`, `model_blob` (per-campaign GP model, joblib-compressed bytes), `is_paused`.

**LinkedInProfile** (`linkedin/models/profile.py`) - `user_id`, `linkedin_username`, `linkedin_password` (synced from credential), `cookie_data_encrypted`, `connect_daily_limit`, `follow_up_daily_limit`, `self_lead_id`, `execution_mode` (desktop/cloud), `last_heartbeat`, `daemon_status`.

**Lead** (`crm/models/lead.py`) - one per LinkedIn URL. `linkedin_url` (unique), `public_identifier`, `urn` (cached after first scrape), `embedding` (384-dim float32 bytes), `connection_degree` (1/2/3), `disqualified` (permanent exclusion), `contact_info` (nullable JSON - LinkedIn overlay), `api_email` (nullable - enrichment waterfall result), `cached_profile` (nullable JSON - Voyager-parsed profile), `user_id`.

**Deal** (`crm/models/deal.py`) - per campaign (FK to Campaign + FK to Lead). `state` (`DealState` - see funnel below), `outcome` (converted/not_interested/wrong_fit/no_budget/has_solution/bad_timing/unresponsive/unknown), `reason`, `connect_attempts`, `backoff_hours`, `next_check_pending_at`, `profile_summary` (JSON fact list), `chat_summary` (JSON fact list).

**Task** (`core/models/task.py`) - `task_type` (connect/check_pending/follow_up), `status` (pending/running/completed/failed), `scheduled_at`, `payload` (JSON `{"campaign_id": ...}`), `linkedin_profile_id`, `user_id`, `started_at`, `completed_at`.

**ChatMessage** (`chat/models/message.py`) - FK to Deal. `content`, `is_outgoing`, `owner`, `linkedin_urn` (Voyager entityUrn, dedup key per deal), `answer_to` (self FK), `topic` (self FK).

**ActionLog** (`linkedin/models/action_log.py`) - FK to LinkedInProfile + Campaign. `action_type` (connect/follow_up), `created_at`. Composite index on `(linkedin_profile_id, action_type, created_at)`.

### Deal State Funnel

`DealState` (in `crm/models/deal.py`):

```
DISCOVERED → QUALIFIED → READY_TO_CONNECT → PENDING → CONNECTED → COMPLETED / FAILED
                                                                         ↑
                                                                   NO_EMAIL (off-funnel)
```

- **DISCOVERED**: initial state for all newly added leads. Operators can manually promote to QUALIFIED.
- **QUALIFIED**: AI-approved. Enrichment (email finder) runs here.
- **NO_EMAIL**: enrichment ran but found no address - held out of the connect pool.
- **READY_TO_CONNECT**: GP confidence gate passed (`P(f>0.5) >= 0.9`).
- **PENDING**: connection request sent, waiting for acceptance.
- **CONNECTED**: accepted. Contact info captured (`Lead.capture_contact_info`).
- **COMPLETED**: follow-up conversation finished.
- **FAILED**: LLM rejection (`wrong_fit`) or task error - campaign-scoped, same lead can be FAILED in one campaign and QUALIFIED in another.

The funnel is OpenOutreach-owned. `linkedin_cli` only observes three states (QUALIFIED/PENDING/CONNECTED) from the LinkedIn UI and returns them as plain strings; task handlers lift them via `DealState(value)`.

## Entry Flow

`openoutreach/cli.py` - Click-based CLI. Key commands:
- `rundaemon` - starts the multi-profile cloud daemon (`core/daemon.py`): scans active `LinkedInProfile` records, manages one browser session per profile, claims tasks by `linkedin_profile_id`, round-robins across users. Profiles re-scanned every 5 min.
- `runserver` - starts FastAPI on port 8001.
- `desktop` - launches the system tray desktop app.
- `sync-stripe` - syncs billing plans to Stripe.

Docker `start` script handles Xvfb/VNC, starts Next.js, and the FastAPI server.

## Task Queue

`Task` is a persistent MongoDB collection. `Task.objects.claim_next(linkedin_profile_id=...)` atomically claims the next due task for a specific profile.

Task rows are **lazy**: `payload = {"campaign_id": <id>}` only. Handlers resolve the concrete target at execution time via an eligibility query.

Slot creation is centralized in `openoutreach/core/scheduler.py` - no other module inserts Task rows.

### Scheduler (core/scheduler.py)

Three per-type planners: `plan_connect_window`, `plan_follow_up_window`, `plan_check_pending_window`.

**Smart mode** (`SiteConfig.enable_smart_rate_limiting=True`): reads `aggressiveness_preset` (very_slow/slow/average/aggressive/very_aggressive) from `rate_limit_presets.py`, applies time-of-day weighting, adjusts for `SmartRateLimitContext.detectability_score`.

**Manual mode**: uses fixed `SiteConfig.velocity` (actions/hr). velocity ≥ 30 = burst mode (immediate, 5–10s gaps); < 30 = spread mode (Poisson across 24h).

Active-hours config read from `SiteConfig` DB fields (`enable_active_hours`, `active_start_hour`, `active_end_hour`, `active_timezone`, `active_days`).

`reconcile(session)` recovers stale RUNNING tasks and dispatches per-type planners. Daemon calls it on idle.

### Task Handlers (openoutreach/linkedin/tasks/)

Signature: `handle_*(task, session, qualifiers)`

**`handle_connect`** (`connect.py`): unified via `ConnectStrategy` dataclass. Regular: `find_candidate()` from `pools.py`; freemium: `find_freemium_candidate()`. Unreachable detection after `MAX_CONNECT_ATTEMPTS` (3).

**`handle_check_pending`** (`check_pending.py`): eligibility = oldest PENDING deal with `next_check_pending_at <= now`. On still-PENDING: doubles `backoff_hours`, re-stamps `next_check_pending_at`.

**`handle_follow_up`** (`follow_up.py`): eligibility = oldest CONNECTED deal with no recent outgoing message. Calls `run_follow_up_agent()` returning `FollowUpDecision` (send_message/mark_completed/wait), executed deterministically.

## Execution Modes

See `CLAUDE.md` "Execution Modes" section for the authoritative description and critical code constraints.

- **Desktop**: `core/daemon_remote.py` on user's machine; bootstrapped via `GET /api/daemon/config` which returns MongoDB URI + server env. `RemoteDaemon._apply_server_env()` injects into `os.environ` before any DB code runs.
- **Cloud**: `core/daemon.py` in Docker on EC2; full `.env` file, no bootstrap needed.
- Both share MongoDB Atlas, task handlers, `SiteConfig`, and `authenticate()` from `linkedin_cli`.

## Key Modules

Paths relative to `openoutreach/`.

### Core

- **`core/daemon.py`** - Cloud daemon worker loop. Active-hours guard, `_build_qualifiers()`, freemium support.
- **`core/daemon_remote.py`** - Desktop daemon. Connects to backend API, executes tasks locally, sends heartbeats.
- **`core/remote_client.py`** - Async HTTP client for desktop daemon ↔ backend communication (task claim/result, cookie sync, config fetch).
- **`core/browser_detect.py`** - Detects Chrome/Edge/Safari on Windows/macOS for the desktop daemon.
- **`core/scheduler.py`** - Single owner of Task row creation. See Task Queue section above.
- **`core/llm.py`** - `get_llm_model()` factory + `run_agent_sync(coro)` sync boundary. Never use `Agent.run_sync` - it poisons subsequent sync Playwright calls.
- **`core/conf.py`** - `CAMPAIGN_CONFIG` (timing/ML defaults), planner caps, scheduler constants.
- **`core/onboarding.py`** - Interactive setup wizard.
- **`core/agents/follow_up.py`** - Follow-up agent. Single LLM call with structured output (`FollowUpDecision`). Injects `profile_summary + chat_summary + last 6 messages` plus `SiteConfig` guardrails.
- **`core/db/deals.py`** - Deal/state ops, `set_profile_state()` (fires `_capture_contact_info()` on CONNECTED), `increment_connect_attempts()`.
- **`core/db/summaries.py`** - mem0-style LLM boundary. `materialize_profile_summary_if_missing(deal, session)` fires on first follow-up; `update_chat_summary(deal, new_messages, *, seller_name)` folds new messages via `reconcile_facts`. Filters outgoing messages - `chat_summary` stores facts about the lead only. `seller_name_from(session)` is the single derivation point (first_name from `session.self_profile`).
- **`core/crypto.py`** - Cookie encryption/decryption (requires `SECRET_KEY` - bootstrapped by desktop daemon before use).

### LinkedIn Channel

- **`linkedin/browser/session.py`** - `AccountSession`: central session object. `campaigns` cached_property (list). `self_profile` cached_property (Voyager scrape on first access). `ensure_browser()`, `reauthenticate()`.
- **`linkedin/browser/launch.py`** - `start_browser_session()` + `_save_cookies()`: launch/persistence orchestration. `_save_cookies()` called after every successful task completion.
- **`linkedin/browser/registry.py`** - `get_or_create_session()`, `get_first_active_profile()`.
- **`linkedin/tasks/`** - Task handlers (see Task Handlers section).
- **`linkedin/pipeline/qualify.py`** - `run_qualification()`, `fetch_qualification_candidates()`.
- **`linkedin/pipeline/search.py`** - `run_search()`, keyword management.
- **`linkedin/pipeline/search_keywords.py`** - `generate_search_keywords()` via LLM.
- **`linkedin/pipeline/ready_pool.py`** - GP confidence gate, `promote_to_ready()`.
- **`linkedin/pipeline/pools.py`** - Composable generators: `search_source` → `qualify_source` → `ready_source`.
- **`linkedin/pipeline/freemium_pool.py`** - Seed priority + undiscovered pool, ranked by qualifier.
- **`linkedin/ml/qualifier.py`** - `BayesianQualifier` (GPR + BALD), `KitQualifier` (freemium pre-trained model).
- **`linkedin/ml/embeddings.py`** - FastEmbed utilities (`embed_text`, `embed_texts`). Default model: BAAI/bge-small-en-v1.5 (384 dim).
- **`linkedin/db/leads.py`** - Lead CRUD, `create_enriched_lead()`, `disqualify_lead()`, `register_self_lead()`.
- **`linkedin/db/chat.py`** - `sync_conversation()`, folds new messages into `Deal.chat_summary`.
- **`linkedin/diagnostics.py`** - `failure_diagnostics()` context manager, saves page HTML/screenshot/traceback.

### Desktop App

- **`desktop/app.py`** - System tray (pystray): start/stop daemon, status, open dashboard, login/logout, auto-start.
- **`desktop/auth.py`** - OS keychain integration via `keyring` (macOS Keychain / Windows Credential Manager).
- **`desktop/config.py`** - Persistent config (`~/Library/Application Support/OpenOutreach/` on macOS, `%LOCALAPPDATA%\OpenOutreach\` on Windows).
- **`desktop/protocol_handler.py`** - `lengrowth://auth?token=...` URL callback handler for web login flow.
- **`desktop/updater.py`** - Checks `https://api.github.com/repos/Lengrowth/outbound/releases/latest` every 6 hours.

### API v2

- **`api_v2/main.py`** - FastAPI app, router registration, CORS, middleware.
- **`api_v2/routers/`** - One file per domain: `auth.py`, `campaigns.py`, `linkedin_profiles.py`, `linkedin_credentials.py`, `settings.py`, `billing.py`, `analytics.py`, `admin.py`, `daemon.py`, etc.
- **`api_v2/schemas/`** - Pydantic request/response models.
- **`api_v2/dependencies.py`** - `get_current_user()`, plan enforcement, admin check.

### Billing

- **`billing/plans.py`** - Plan definitions (starter/pro/business/agency/lifetime + cloud_addon). Desktop execution included in all base plans; cloud execution requires `cloud_addon` only.
- **`billing/enforcement.py`** - `PlanEnforcer`: checks campaign limits, cloud access, trial restrictions. Called on every mutating endpoint.
- **`billing/stripe_client.py`** - Stripe API wrapper (subscriptions, customer portal, webhook verification).

## ML Qualification Pipeline

GPR (`sklearn.gaussian_process.GaussianProcessRegressor`, `ConstantKernel * RBF`) inside `Pipeline(StandardScaler, GPR)` with BALD active learning.

1. **Balance-driven selection**: negatives > positives → exploit (highest P); otherwise → explore (highest BALD).
2. **LLM decision**: all qualification decisions via LLM (`qualify_lead.j2`). GP only for candidate ranking and confidence gate.
3. **READY_TO_CONNECT gate**: `P(f > 0.5) >= min_ready_to_connect_prob` (0.9) promotes QUALIFIED → READY_TO_CONNECT.

384-dim FastEmbed embeddings stored on Lead model. Per-campaign GP models in `Campaign.model_blob` (joblib-compressed bytes). Cold start (< 2 labels of both classes) returns `None` - pure LLM ordering until both classes are present.

## Deal Summaries (mem0-style)

`Deal.profile_summary` and `Deal.chat_summary` are lazy JSON fact lists. Single boundary in `core/db/summaries.py`:

- `materialize_profile_summary_if_missing(deal, session)` - fires on first follow-up; one Voyager re-scrape per (lead, campaign) lifetime.
- `update_chat_summary(deal, new_messages, *, seller_name)` - folds newly-synced ChatMessages via `reconcile_facts`, which routes facts through mem0's UPDATE prompt (ADD/UPDATE/DELETE/NONE events). Outgoing messages filtered - only lead messages contribute to `chat_summary`.
- Identity binding: `seller_name` injected into extraction and reconcile prompts to prevent seller-name greetings from being misattributed to the lead.
- mem0's `DEFAULT_UPDATE_MEMORY_PROMPT` vendored at `core/vendor/mem0/configs/prompts.py`. No `mem0ai` runtime dependency.

## `linkedin_cli` - Vendored LinkedIn Library

Vendored at project root as `linkedin_cli/` - previously published as `linkedin-agent-cli` on PyPI (now yanked), maintained in-repo. Django-free. Holds LinkedIn *platform mechanics*: browser nav/login, Voyager API, profile/conversation scrape, connect/message/status/thread verbs. Full reference in `docs/LINKEDIN_CLI.md`.

- **`session.py`** - `LinkedInSession` protocol. `PlaywrightCliSession` connects to a bound browser.
- **`page_state.py`** - Page-state machine. `classify_page(page)` judges by URL path only. `@transition(when=,then=)` enforces pre/post state contracts raising `IllegalPageTransition`. `PageFlow` is the generic observe→act engine.
- **`auth.py`** - Login flow as `@auth_flow.transition` actions. `authenticate(session, *, username, password)` drives the flow to feed. Shared by CLI verb and daemon - no duplicated login path.
- **`api/client.py`** - `PlaywrightLinkedinAPI`: in-page `fetch()` for authentic Voyager headers. `VOYAGER_REQUEST_TIMEOUT_MS` is the constructor default.
- **`api/voyager.py`** - `parse_linkedin_voyager_response()`, `parse_connection_degree()`.
- **`api/messaging/`** - `send.py` (`send_message`), `conversations.py` (`fetch_conversations`/`fetch_messages`), `utils.py`.
- **`actions/`** - `connect.py`, `status.py`, `message.py`, `profile.py`, `search.py`, `conversations.py`.
- **`conf.py`** - `BROWSER_*`, `HUMAN_TYPE_*`, `BROWSER_HEADLESS`, `DUMP_PAGES` (save HTML snapshots for fixture collection), `BROWSER_PROXY_SERVER/USERNAME/PASSWORD` (optional proxy config).
- **`exceptions.py`** - `AuthenticationError`, `SkipProfile`, `ProfileInaccessibleError`, `ReachedConnectionLimit`, `CheckpointChallengeError`.

## Configuration

All settings editable from Settings page in the web UI or via FastAPI endpoints:

| Setting | Location |
|---------|----------|
| LLM provider, API key, model | Settings → LLM / AI Settings → `SiteConfig` |
| LinkedIn credentials | Settings → LinkedIn Connection → `LinkedInCredential` model |
| Rate limits + active hours | Settings → Rate Limits → `SiteConfig` |
| Follow-up writing style/say/avoid rules | Settings → Profile → `SiteConfig` |
| Stripe keys, email finder key, JWT secret | `.env` / `openoutreach/config.py` |
| MongoDB URI + name | `.env` or `/api/daemon/config` response (desktop) |

Environment variables (`openoutreach/config.py`, pydantic `Settings`): `MONGODB_URI`, `MONGODB_NAME`, `JWT_SECRET_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`.

`conf.py:CAMPAIGN_CONFIG` - `min_ready_to_connect_prob` (0.9), `min_positive_pool_prob` (0.20), `check_pending_recheck_after_hours` (24), `embedding_model` ("BAAI/bge-small-en-v1.5"), timing/burst constants.

## Docker

Base image: `mcr.microsoft.com/playwright/python:v1.55.0-noble`. Dockerfile at `compose/linkedin/Dockerfile`. `BUILD_ENV` arg selects requirements file.

When `ENABLE_VNC=true`: x11vnc on port 5900, noVNC websockify on port 6080. Frontend embeds a live noVNC iframe (`frontend/src/components/settings/vnc-viewer.tsx`) in Settings → LinkedIn Connection so operators can handle LinkedIn challenges from the UI without an external VNC client.

## CI/CD

- `tests.yml` - pytest in Docker on push to `main` and PRs.
- `deploy.yml` - Tests → build + push to `ghcr.io`. Tags: `latest`, `sha-<commit>`.
- `desktop-build.yml` - triggered on `desktop-v*` tags; builds Lengrowth.exe via PyInstaller, creates GitHub Release on `Lengrowth/outbound` repo.

## Analytics Contract

`api_v2/routers/analytics.py`:
- `AnalyticsOverviewView` - live overview totals + per-campaign metrics for selected `campaign_id` + `period` window.
- `CampaignAnalyticsView` - per-campaign page: live `connectionsSent`, `connectionsAccepted`, `messagesSent`, `messagesReplied`; zero-safe rates; real 7/30-day aggregates; reply timestamps from `ChatMessage.creation_date`.

## Visual Campaign Sequences

Campaigns may store a visual directed graph in `sequence_steps` and `sequence_edges`. The API validates node types, channel compatibility, roots, reachability, cycles, branch labels, wait durations, and runtime prerequisites before activation. The reconciler advances each deal with a short lease and creates deterministic, deal-targeted tasks; inbound replies, missing prerequisites, exhausted retries, and end nodes are recorded as terminal sequence outcomes. Sequence-owned work is idempotent and suppresses legacy planner tasks. The same execution contract is enforced by the local desktop daemon and the remote/cloud daemon, including side-effect verification for email, LinkedIn, and WhatsApp tasks. Sequence metrics and a dry-run preview are available from the campaign API for operational checks before launch.

No hard-coded placeholder percentages anywhere.
