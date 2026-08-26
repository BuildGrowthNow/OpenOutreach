# OpenOutreach

> **Describe your product. Define your target market. The AI finds the leads for you.**

<div align="center">

[![License: GPLv3](https://img.shields.io/badge/License-GPLv3-blue.svg?style=flat-square)](https://www.gnu.org/licenses/gpl-3.0)

</div>

---

## What is OpenOutreach?

OpenOutreach is a self-hosted LinkedIn automation platform for B2B lead generation. You don't need a contact list - describe your product and target market and the system autonomously discovers, qualifies, and contacts the right people on LinkedIn.

**How it works:**

1. You provide a product description and campaign objective (e.g. "SaaS analytics platform targeting VP of Engineering at Series B startups")
2. The AI generates LinkedIn search queries to discover candidate profiles
3. A Bayesian ML model (Gaussian Process Regressor on profile embeddings) learns your ideal customer profile via an explore/exploit strategy
4. An LLM qualifies each candidate; the GP learns from every decision to select better leads over time
5. Qualified leads are automatically contacted and an AI agent manages multi-turn follow-up conversations

---

## What You Need

| # | What | Example |
|---|------|---------|
| 1 | A LinkedIn account | Your email + password |
| 2 | An LLM API key | OpenAI, Anthropic, Google, Groq, Mistral, Cohere, or any OpenAI-compatible endpoint |
| 3 | A product description + target market | "We sell cloud cost optimization for DevOps teams at mid-market SaaS companies" |

---

## Quick Start (Docker)

```bash
git clone https://github.com/Lengrowth/outbound.git
cd outbound

cp .env.example .env
# Edit .env with your MongoDB URI, JWT secret, LLM API key, and Stripe keys

docker compose up --build

# Frontend:   http://localhost:3000
# API:        http://localhost:8001
# API Docs:   http://localhost:8001/docs
# noVNC:      http://localhost:6080  (if ENABLE_VNC=true)
```

## Local Development

```bash
make setup   # install deps, Playwright browsers, bootstrap MongoDB
make api     # FastAPI server at localhost:8001
make run     # daemon

cd frontend && npm install && npm run dev   # Next.js at localhost:3000
```

---

## Desktop App

OpenOutreach ships a native desktop daemon for **macOS and Windows** (v1.5.8). Instead of running the browser automation on a cloud server (which requires expensive mobile proxies), the desktop daemon runs Playwright on your own machine using your residential IP - the same IP LinkedIn already knows.

**Why this matters:** LinkedIn blocks cloud provider IP ranges (AWS, GCP, Azure). Running on your own machine with your own IP eliminates proxy costs ($25–75/profile/month) and reduces detection risk.

### Desktop Features

- **System tray app** - start/stop the daemon from the menu bar with real-time status
- **Secure credential storage** - credentials stored in your OS keychain (macOS Keychain / Windows Credential Manager)
- **Auto-updates** - checks GitHub releases every 6 hours and notifies you of new versions
- **One-click login** - opens the web app in your browser and captures the JWT token via the `openoutreach://` protocol handler
- **Automatic browser detection** - finds your installed Chrome, Edge, or Safari automatically
- **Full feature parity** - same task execution, active hours, rate limits, and campaign support as the cloud daemon

### Download

Download the latest release from [GitHub Releases](https://github.com/Lengrowth/outbound/releases):

| Platform | Format |
|----------|--------|
| macOS | `.dmg` |
| Windows | NSIS installer (`.exe`) or standalone `.exe` or `.msix` |

---

## Features

| Feature | Description |
|---------|-------------|
| **Autonomous lead discovery** | LLM generates LinkedIn search queries from your product description - no contact lists needed |
| **Bayesian active learning** | Gaussian Process model on 384-dim profile embeddings learns your ICP via explore/exploit; cold-starts with pure LLM qualification |
| **AI follow-up agent** | Manages multi-turn conversations using profile summaries, chat history, and your messaging guardrails |
| **Stealth browser automation** | Playwright + stealth plugins mimic real user behavior; bandwidth optimization blocks third-party assets (60–70% bandwidth reduction) |
| **Voyager API scraping** | LinkedIn's internal API for accurate structured profile data |
| **Smart rate limiting** | Time-of-day weighting, aggressiveness presets (very slow → very aggressive), and detectability-score adjustments |
| **Active hours** | Per-user timezone, start/end hours, and active-days config so the daemon only runs when it looks natural |
| **Email enrichment** | Free 6-layer waterfall (domain → website scrape → WHOIS/RDAP → pattern generation → SMTP probe → web search) - automatically finds work emails for qualified leads |
| **Deal summaries** | mem0-style incremental JSON fact lists per lead - profile summary + chat summary consumed by the follow-up agent |
| **Multi-tenant** | Multiple users, multiple LinkedIn profiles, per-user settings, full data isolation |
| **VNC browser viewer** | Live noVNC iframe in Settings so you can solve LinkedIn CAPTCHAs or security checks from the web UI |
| **Analytics** | Live connection rates, response rates, conversion funnels - no hard-coded placeholders |
| **Billing & subscriptions** | Stripe integration with plan enforcement on every mutating endpoint and both daemons |

---

## Pricing

| Plan | Monthly | Annual | LinkedIn Accounts | Campaigns |
|------|---------|--------|-------------------|-----------|
| Starter | $19/mo | $192/yr | 1 | 3 |
| Pro | $49/mo | $492/yr | 1 | Unlimited |
| Business | $99/mo | $996/yr | 3 | Unlimited |
| Agency | $249/mo | $2,496/yr | 10 | Unlimited |

3-day free trial (full Pro access, credit card required). Lifetime deal available at launch ($149 one-time, Pro-equivalent).

Cloud execution add-on: +$299/profile/month (server-side browser via proxy, for users who prefer not to run the desktop app). Trial users cannot use cloud execution - desktop app required during trial.

---

## ML Pipeline

The daemon runs a persistent task queue with three self-scheduling task types:

| Task | What it does |
|------|-------------|
| `connect` | Ranks qualified leads by GP probability, sends connection requests within daily/weekly limits; triggers qualification and discovery when the pool is low |
| `check_pending` | Checks if a pending connection request was accepted (exponential backoff) |
| `follow_up` | Runs the AI follow-up agent against connected leads using profile + chat summaries |

**Qualification loop:**
- Profile embeddings (384-dim FastEmbed) are computed on discovery and cached
- When negatives outnumber positives → **exploit**: pick highest predicted qualification probability
- Otherwise → **explore**: pick highest BALD score (most informative label for model improvement)
- Every LLM classification feeds back into the GP; cold start (<2 labels) uses LLM-only ordering

**Lead/Deal separation:** `Lead` = discovered person (permanent record). `Deal` = that lead's relationship to a specific campaign (tracks funnel state: DISCOVERED → QUALIFIED → READY_TO_CONNECT → PENDING → CONNECTED → COMPLETED/FAILED).

---

## Stack

- **Backend**: FastAPI + MongoDB (zero Django), JWT auth, multi-tenant
- **Frontend**: Next.js 14+ (App Router), TypeScript, Tailwind CSS, shadcn/ui
- **Daemon**: Playwright + stealth, LinkedIn Voyager API, per-profile browser sessions
- **Desktop**: pystray, keyring, PyInstaller - distributed via GitHub Releases
- **ML**: sklearn GPR, FastEmbed (384-dim), BALD active learning
- **Billing**: Stripe (subscriptions, webhooks, customer portal)
- **Infra**: Docker on AWS EC2, MongoDB Atlas

---

## Architecture

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

The cloud daemon (EC2) and desktop daemon (user's machine) both pull tasks from the same queue and report results back to the same API - same code path, different execution environment.

---

## Project Structure

```
openoutreach/
├── api_v2/          # FastAPI routers, schemas, dependencies
├── billing/         # Stripe integration, plan enforcement, trial/expiry
├── core/            # Daemon, task queue, scheduler, LLM factory, follow-up agent
├── crm/             # Lead and Deal models
├── chat/            # ChatMessage model
├── linkedin/        # Browser, discovery pipeline, ML qualifier, task handlers
├── emails/          # Email enrichment (free waterfall finder)
├── desktop/         # System tray app, auto-updater, protocol handler, keychain auth
└── mongodb/         # Models, connection, DAL

frontend/
├── src/app/         # Next.js App Router pages
├── src/components/  # UI components (shadcn/ui)
└── src/lib/         # API client, auth store, hooks

docs/                # Architecture, proxy guide, desktop app, billing, etc.
```

---

## Configuration

All settings are editable from the Settings page in the web UI or via FastAPI endpoints. Key settings:

| Setting | Where |
|---------|-------|
| LLM provider + API key + model | Settings → LLM / AI Settings |
| LinkedIn credentials | Settings → LinkedIn Connection |
| Rate limits + active hours | Settings → Rate Limits |
| Follow-up writing style, say/avoid rules | Settings → Profile |
| Stripe keys, email finder key | `.env` |

Environment variables: `MONGODB_URI`, `MONGODB_NAME`, `JWT_SECRET_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`.

---

## linkedin-agent-cli

The LinkedIn automation layer lives in `linkedin_cli/` (vendored at the project root). It was previously published as `linkedin-agent-cli` on PyPI but is now yanked and maintained in-repo. You can drive LinkedIn from your own code by importing it directly or via the installed `linkedin-cli` console command:

```bash
# After `make setup`, the CLI is on your PATH:
linkedin-cli session open --session work
linkedin-cli login --session work
linkedin-cli search "head of growth" --network first --json
linkedin-cli profile alice-smith --json
linkedin-cli message alice-smith --session work --text "Hi Alice"
linkedin-cli thread alice-smith --session work
```

The library uses a bind+connect transport: a session owner `browser.bind()`s the browser, clients `chromium.connect()`. Each verb returns a result dict - brief human summary by default, full dict with `--json`.

---

## Commands

```bash
# Docker
make build / make up / make stop / make logs

# Local dev
make setup    # install deps + browsers + bootstrap MongoDB
make run      # daemon
make api      # FastAPI at localhost:8001

# Testing
make test
pytest tests/api/test_voyager.py
pytest -k test_name

# Desktop build
python desktop/build.py

# Billing
openoutreach sync-stripe   # sync plans to Stripe
```

---

## Documentation

- [Architecture](./ARCHITECTURE.md)
- [Configuration](./docs/configuration.md)
- [Docker setup](./docs/docker.md)
- [Proxy guide](./docs/PROXY_GUIDE.md)
- [Desktop app](./docs/DESKTOP_APP.md)
- [Billing implementation](./docs/BILLING_IMPLEMENTATION.md)
- [Follow-up agent](./docs/follow_up_agent.md)
- [Profile lifecycle](./docs/profile_lifecycle.md)
- [Testing](./TESTING_GUIDE.md)

---

## Legal Notice

**Not affiliated with LinkedIn.**

Use of this software may violate LinkedIn's Terms of Service. By using it you accept full responsibility for your account's compliance. See [LEGAL_NOTICE.md](LEGAL_NOTICE.md) for full terms.

**Use at your own risk - no liability assumed.**
