# Lengrowth Outreachs

> **Describe your product. Define your target market. The AI finds the leads for you.**

<div align="center">

[![GitHub stars](https://img.shields.io/github/stars/eracle/OpenOutreach.svg?style=flat-square&logo=github)](https://github.com/eracle/OpenOutreach/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/eracle/OpenOutreach.svg?style=flat-square&logo=github)](https://github.com/eracle/OpenOutreach/network/members)
[![License: GPLv3](https://img.shields.io/badge/License-GPLv3-blue.svg?style=flat-square)](https://www.gnu.org/licenses/gpl-3.0)
[![Open Issues](https://img.shields.io/github/issues/eracle/OpenOutreach.svg?style=flat-square&logo=github)](https://github.com/eracle/OpenOutreach/issues)

<br/>

# Demo:

<img src="docs/demo.gif" alt="Demo Animation" width="100%"/>

</div>

---

### 🚀 What is Lengrowth Outreach?

Lengrowth Outreach is a LinkedIn automation tool for B2B lead generation. Unlike other tools, **you don't need a list of profiles to contact** — you describe your product and your target market, and the system autonomously discovers, qualifies, and contacts the right people.

**How it works:**

1. **You provide** a product description and a campaign objective (e.g. "SaaS analytics platform" targeting "VP of Engineering at Series B startups")
2. **The AI generates** LinkedIn search queries to discover candidate profiles
3. **A Bayesian ML model** (Gaussian Process Regressor on profile embeddings) learns which profiles match your ideal customer — using an explore/exploit strategy to balance finding the best leads now vs. learning what makes a good lead
4. **An LLM classifies** each profile selected by the model; the GP learns from every decision to select better candidates over time
5. **Qualified leads** are automatically contacted, and an AI agent manages multi-turn follow-up conversations

The system gets smarter with every decision. It starts by exploring broadly, then progressively focuses on the highest-value profiles as it learns your ideal customer profile from its own classification history.

**Why choose Lengrowth Outreach?**

- 🧠 **Autonomous lead discovery** — No contact lists needed; AI finds your ideal customers
- 🛡️ **Undetectable** — Playwright + stealth plugins mimic real user behavior
- 💾 **Self-hosted + full data ownership** — Everything runs locally, browse your CRM in a web UI
- 🐳 **One-command setup** — Dockerized deployment, interactive onboarding
- ✨ **AI-powered messaging** — LLM-generated personalized outreach (bring your own model)

Perfect for founders, sales teams, and agencies who want powerful automation **without account bans or subscription lock-in**.

---

## 📋 What You Need

| # | What | Example |
|---|------|---------|
| 1 | **A LinkedIn account** | Your email + password |
| 2 | **An LLM API key** | OpenAI, Anthropic, or any OpenAI-compatible endpoint |
| 3 | **A product description + target market** | "We sell cloud cost optimization for DevOps teams at mid-market SaaS companies" |

That's it. No spreadsheets, no lead databases, no scraping setup.

---

## ⚡ Quick Start (Docker — Recommended)

Pre-built images are published to GitHub Container Registry on every push to `master`.

```bash
docker run --pull always -it -p 5900:5900 -p 6080:6080 -v ~/.Lengrowth Outreach/data:/app/data ghcr.io/eracle/Lengrowth Outreach:latest

# Open http://localhost:6080/vnc.html in your browser to watch the automation live
```

The interactive onboarding walks you through the three inputs above on first run. All data persists in `~/.Lengrowth Outreach/data` on your host across restarts.

Once the container is running, open **http://localhost:6080/vnc.html** in your browser to watch the browser live (noVNC). Alternatively, connect a native VNC client to `localhost:5900`.

For Docker Compose, build-from-source, and more options see the **[Docker Guide](./docs/docker.md)**.

---

## ⚙️ Local Installation (Development)

For contributors or if you prefer running directly on your machine.

### Prerequisites

- [Git](https://git-scm.com/)
- [Python](https://www.python.org/downloads/) (3.12+)

### 1. Clone & Set Up
```bash
git clone https://github.com/eracle/Lengrowth Outreach.git
cd Lengrowth Outreach

# Install deps, Playwright browsers, run migrations, and bootstrap CRM
make setup
```

### 2. Run the Daemon

```bash
make run
```
The interactive onboarding will prompt for LinkedIn credentials, LLM API key, and campaign details on first run. Fully resumable — stop/restart anytime without losing progress.

### 3. View Your Data (CRM Admin)

Lengrowth Outreach includes a full CRM web interface powered by DjangoCRM:
```bash
# Create an admin account (first time only)
python manage.py createsuperuser

# Start the web server
make admin
```
Then open:
- **Django Admin:** http://localhost:8000/admin/
- **Next.js Frontend:** http://localhost:3000 (new browser-based interface)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🧠 **Autonomous Lead Discovery** | No contact lists needed — LLM generates search queries from your product description and campaign objective. |
| 🎯 **Bayesian Active Learning** | Gaussian Process model on profile embeddings learns your ideal customer via explore/exploit, selecting the most informative candidates for LLM qualification. |
| 🤖 **Stealth Browser Automation** | Playwright + stealth plugins mimic real user behavior for undetectable interactions. |
| 🛡️ **Voyager API Scraping** | Uses LinkedIn's internal API for accurate, structured profile data (no fragile HTML parsing). |
| 🔄 **Stateful Pipeline** | Tracks profile states (`QUALIFIED` → `READY_TO_CONNECT` → `PENDING` → `CONNECTED` → `COMPLETED`) in a local DB — fully resumable. |
| ⏱️ **Smart Rate Limiting** | Configurable daily/weekly limits per action type, respects LinkedIn's own limits automatically with context-aware adjustments based on time of day, day of week, and LinkedIn detectability signals. |
| 💾 **Built-in CRM** | Full data ownership via DjangoCRM with Django Admin UI — browse Leads, Contacts, Companies, and Deals. |
| 🌐 **Next.js Frontend** | Modern web interface with real-time updates, intuitive navigation, and comprehensive campaign management dashboard. |
| 🎭 **Ghost Mode Campaign Testing** | Safe pre-launch testing mode where all processing logic runs without actually sending any messages or connection requests — perfect for validating campaign setup with zero risk. |
| ⚙️ **State Machine Workflow Editor** | Visual workflow builder for designing custom outreach sequences with drag-and-drop nodes, conditional branches, and multi-path follow-ups. |
| 🩺 **Campaign Health Monitor** | Continuous monitoring system that detects anomalies, auto-adjusts velocity, and implements self-healing recovery strategies to maintain optimal campaign performance. |
| 🔒 **Undetectable Automation** | Intelligent behavior patterns and rate limiting that adapts to LinkedIn's detection signals. |
| 📊 **Advanced Analytics** | Real-time analytics with connection success rates, response rates, conversion funnels, and performance recommendations. |
| 📑 **Agentic Follow-up** | AI agents manage multi-turn conversations with connected leads, reading history and making intelligent follow-up decisions. |
| 💼 **Generative Lead Persona** | Hyper-personalized LLM-generated personas with pain points, goals, messaging preferences, and buy signals for each lead. |
| 🌍 **Email Enrichment** | BetterContact integration with network data resilience — find work emails automatically and contribute to a shared hub. |
| 📧 **SMTP Mailboxes** | Multi-box email sending with daily pacing, warmup support, and automatic load balancing across mailboxes. |

---

## 🤖 Drive LinkedIn from Your Own LLM

Lengrowth Outreach's LinkedIn layer is also published as a standalone, Django-free package —
[**`linkedin-agent-cli`**](https://github.com/eracle/linkedin-cli) — so you can let *your own*
LLM agent drive LinkedIn directly, no Lengrowth Outreach install required. Every verb prints a human
summary or the full result dict with `--json`, and errors go to stderr with stable types — a
clean tool-use contract any agent (or any language) can call:

```bash
pip install linkedin-agent-cli
python -m playwright install chromium

linkedin-cli session open --session work   # launch + bind a browser (this process owns it)
linkedin-cli login   --session work         # authenticate in that session
linkedin-cli search "head of growth" --network first --json   # → handles your LLM can parse
linkedin-cli profile alice-smith --json                       # → full profile dict
linkedin-cli message alice-smith --session work --text "Hi Alice"
```

Point your agent at the `--json` output and the per-verb `--help`; see the
[`linkedin-cli` README](https://github.com/eracle/linkedin-cli#readme) for the full verb surface
and output contract.

---

## 📖 How the ML Pipeline Works

The daemon runs a continuous **task queue** backed by a persistent `Task` model. Three task types self-schedule follow-on work:

| Task Type | What it does |
|-----------|-------------|
| **Connect** | Ranks qualified profiles by GP model probability, sends connection requests (daily + weekly limits). Triggers qualification and search via composable generators when the pool is empty. |
| **Check Pending** | Checks if a pending request was accepted (exponential backoff per profile) |
| **Follow Up** | Runs an AI agent that manages multi-turn conversations with connected profiles |

**The qualification loop in detail:**

Profiles discovered during navigation are automatically scraped and embedded (384-dim FastEmbed vectors). The connect task's backfill chain decides which profile to evaluate next using a balance-driven strategy:

- **When negatives outnumber positives** → **exploit**: pick the profile with highest predicted qualification probability (seek likely positives to fill the pipeline)
- **Otherwise** → **explore**: pick the profile with highest BALD (Bayesian Active Learning by Disagreement) score (seek the most informative label to improve the model)

All qualification decisions go through the LLM. The GP model selects which candidate to evaluate next and gates promotion from QUALIFIED to READY_TO_CONNECT (confidence threshold). Every LLM decision feeds back into the model, making candidate selection progressively smarter.

**Cold start:** With fewer than 2 labelled profiles, the model can't fit — candidates are selected in order and qualified via LLM. As labels accumulate, the GP becomes better at selecting high-value candidates.

Configure rate limits and behavior via Django Admin (LinkedInProfile + Campaign models).

---

## 🌐 Next.js Frontend

Lengrowth Outreach features a modern, React-based frontend built with **Next.js 14+** (App Router) that provides:

- **Real-time dashboard** with system health and campaign statistics
- **Campaign management** with full CRUD operations
- **Lead tracking** with detailed analytics and message threads
- **State machine editor** for visual workflow building
- **Analytics dashboard** with conversion funnels and performance metrics
- **Settings panel** for rate limits, profile configuration, and API keys

### Key Components

| Component | Description |
|-----------|-------------|
| **Dashboard** | Real-time overview of system health, active campaigns, and recent activity |
| **Campaigns** | Create, edit, and manage campaigns with full analytics |
| **Leads** | Track and manage leads with message history and notes |
| **Analytics** | Visual performance metrics with actionable insights |
| **State Machine** | Visual workflow builder for custom outreach sequences |
| **Settings** | Configure rate limits, LinkedIn credentials, and API keys |

**Tech Stack:** Next.js 14+ (App Router), TypeScript, Tailwind CSS, shadcn/ui

---

## 🎭 Ghost Mode: Safe Campaign Testing

Ghost Mode is a "safe test" mode where:
- **No LinkedIn actions are performed** — No messages sent, no connections requested
- **Full simulation** — All processing logic runs, but stops at the last moment
- **Results tracked** — What would have happened is logged and analyzed
- **Cost-free** — No API costs, no rate limit impact, no LinkedIn exposure
- **Risk-free learning** — Test your setup with zero risk to your account

### Use Cases

- Campaign design validation before going live
- A/B testing of different message variants safely
- Lead qualification accuracy testing
- Pipeline flow verification without real-world consequences
- Training and demo scenarios for new team members

### Features

- Simulate search, qualify, connect, message, and follow-up actions
- Track detailed simulation logs with ratings and scores
- Export simulation results as CSV
- Share test scenarios with your team

---

## ⏱️ Smart Rate Limiting

Traditional rate limiting uses fixed values (e.g., 20 connections/day), which has significant flaws:

- **Over-limiting**: Quiet hours still count against daily quota
- **Under-limiting**: High-engagement periods use up quota too quickly
- **One-size-fits-all**: Doesn't account for individual lead quality
- **Detection-blind**: Doesn't adapt to LinkedIn's signals of automated behavior

Smart rate limiting solves this by dynamically adjusting limits based on:

| Context factor | Low Limit | Medium Limit | High Limit |
|----------------|-----------|--------------|------------|
| Time of day | 8-10pm = 10 | 9am-6pm = 25 | 6-8pm = 30 |
| Day of week | Weekend = 15 | Monday-Friday = 30 | Friday = 20 |
| Lead engagement | Cold lead = 5 | Hot lead = 50 | Verified warm = 100 |
| Campaign phase | Discovery = 15 | Follow-up = 35 | Nurturing = 25 |
| LinkedIn detectability | Normal = 30 | Suspicious = 15 | Warning = 5 |

**Benefits:** Reduce rate limit violations by 60-80% while maintaining or improving total daily outreach volume.

---

## ⚙️ State Machine Workflow Editor

Transform outreach from a linear pipeline into a flexible workflow system:

- **Visual editor**: Drag-and-drop interface for building outreach flows
- **Conditional branches**: Send different messages based on responses, timing, or lead characteristics
- **Loop protection**: Prevent infinite loops with automatic cycle detection
- **Execution simulation**: Test your workflow before launching
- **Runtime visualization**: Watch your campaign flow in real-time

### Node Types

| Node | Purpose |
|------|---------|
| **Start** | Entry point for the workflow |
| **Wait** | Pause for a specified time period |
| **Message** | Send an automated message |
| **Gate** | Qualification-based routing |
| **Decision** | Branch based on conditions |
| **Branch** | Multi-path routing |
| **Webhook** | External API integration |
| **End** | Workflow termination |

### Use Cases

- **Follow-up paths**: Different responses for response/no response
- **Timing-based routing**: Different messages after different waiting periods
- **qualification gates**: Route leads based on qualification score
- **Multi-channel flows**: Coordinate LinkedIn + email sequences

---

## 🩺 Campaign Health Monitor & Auto-Recovery

A self-healing system that detects rate limit warnings, monitors connection acceptance rates, auto-adjusts velocity, and implements recovery strategies.

### What It Monitors

1. **Key metrics** — Connection accept rates, response rates, error patterns
2. **Anomaly detection** — Identifies issues before they escalate
3. **Auto-adjustment** — Automatically adjusts campaign parameters
4. **Recovery strategies** — Implements fixes when issues arise

### Recovery Actions

| Action | Description |
|--------|-------------|
| Reduce Velocity | Lower outreach frequency automatically |
| Add Cooldown | Insert longer delays between actions |
| Switch Message | Try a different message variant |
| Pause Campaign | Stop outreach until conditions improve |
| Switch Account | Rotate to a backup LinkedIn account |

### Benefits

| Feature | Before | After |
|---------|--------|-------|
| Issue Detection | Manual (user checks logs) | Automatic (real-time monitoring) |
| Response Time | Hours/days | Seconds/minutes |
| Remediation | Manual intervention | Automatic (base level) |
| Downtime | Campaign stuck until user fixes | Self-healing |
| Insights | None | Comprehensive metrics |

**Result:** Reduce campaign failures by 70% and improve autonomy from "set-and-forget" to "self-maintaining."

---

## 📂 Project Structure

```
├── docs/
│   ├── architecture.md              # System architecture
│   ├── configuration.md             # Configuration reference
│   ├── docker.md                    # Docker setup guide
│   ├── templating.md                # Follow-up messaging guide
│   └── testing.md                   # Testing strategy
├── Lengrowth Outreach/                    # single source package; Django apps nested inside
│   ├── settings.py                  # Django/CRM settings (SQLite at data/db.sqlite3)
│   ├── core/                        # engine app: daemon, task queue + scheduler,
│   │                                #   Campaign/SiteConfig/Task, LLM factory, onboarding,
│   │                                #   follow-up agent, db helpers, management commands
│   ├── linkedin/                    # LinkedIn channel app: browser, discovery pipeline,
│   │                                #   ML qualifier, task handlers, channel models
│   ├── emails/                      # email channel app (Layer 1 of the email-first pivot)
│   ├── crm/                         # Lead + Deal models
│   └── chat/                        # ChatMessage model
├── frontend/                        # Next.js frontend
│   ├── src/
│   │   ├── app/                     # App Router pages and API routes
│   │   ├── components/              # Reusable UI components
│   │   └── lib/                     # API client and utilities
├── manage.py                         # Django management (no args defaults to rundaemon)
├── local.yml                        # Docker Compose
└── Makefile                         # Shortcuts (setup, run, admin, test)
```

---

## 📚 Documentation

- [Architecture](./docs/architecture.md)
- [Configuration](./docs/configuration.md)
- [Profile Lifecycle](./docs/profile_lifecycle.md)
- [Docker Installation](./docs/docker.md)
- [Follow-up Messaging](./docs/templating.md)
- [Template Variables](./docs/template-variables.md)
- [Testing](./docs/testing.md)
- [Frontend Documentation](./docs/FRONTEND_DOCUMENTATION.md)

### Feature-Specific Documentation

- [Ghost Mode Campaign Testing](./docs/01_ghost_mode_campaign_testing.md)
- [Smart Rate Limiting](./docs/07_SMART_RATE_LIMITING.md)
- [State Machine Editor](./docs/03_STATE_MACHINE_EDITOR.md)
- [Campaign Health Monitor](./docs/02_CAMPAIGN_HEALTH_MONITOR.md)

---


---


## 📜 Legal Notice

**Not affiliated with LinkedIn.**

By using this software you accept the [Legal Notice](LEGAL_NOTICE.md). It covers LinkedIn ToS risks, built-in self-promotional actions, automatic newsletter subscription for non-GDPR accounts, and liability disclaimers.

**Use at your own risk — no liability assumed.**

---