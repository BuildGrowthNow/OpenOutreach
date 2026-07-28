# linkedin_cli — Vendored Module Reference

> **Status**: Previously published as `linkedin-agent-cli` on PyPI (yanked). Now vendored at project root as `linkedin_cli/`. This is the authoritative copy — maintain it here.

---

## Overview

`linkedin_cli` is a framework-agnostic library of LinkedIn platform mechanics. It owns:
- Browser launch, auth, and session management (Playwright + stealth)
- The Voyager API client (profile scrape, degree check, contact info)
- All action verbs: connect, message, search, status, thread
- A verb CLI (`linkedin-cli`) using a bind+connect transport for headless operation

It owns **no database, no campaign/CRM logic, no scheduling**. OpenOutreach's `openoutreach/` package consumes it as a library and owns those layers.

---

## Module Layout

```
linkedin_cli/
├── __init__.py          — version string ("0.1.0")
├── cli.py               — CLI entry point + composition root (verb dispatch, output contract)
├── conf.py              — Browser timing/proxy constants (no CRM config)
├── enums.py             — ProfileState StrEnum
├── exceptions.py        — All custom exceptions
├── session.py           — LinkedInSession protocol + PlaywrightCliSession
├── page_state.py        — PageState enum, classify_page(), @transition decorator, PageFlow
├── auth.py              — authenticate() — declared @auth_flow transitions
├── launcher.py          — open_bound_session() — browser.bind() owner
├── url_utils.py         — url_to_public_id(), public_id_to_url()
│
├── api/
│   ├── client.py        — PlaywrightLinkedinAPI (Voyager GET/POST + retries)
│   ├── voyager.py       — Voyager JSON parsers, LinkedInProfile dataclass
│   ├── sdui.py          — parse_contact_info() — RSC/React flight parser
│   └── messaging/
│       ├── conversations.py  — fetch_conversations(), fetch_messages(), get_conversation()
│       ├── send.py           — send_message() via Voyager Messaging API
│       └── utils.py          — encode_urn(), check_response()
│
├── actions/
│   ├── connect.py       — send_connection_request()
│   ├── contact_info.py  — get_contact_info()
│   ├── conversations.py — get_conversation(), find_conversation_urn(), parse_messages()
│   ├── message.py       — send_raw_message() — UI first, API fallback
│   ├── profile.py       — scrape_profile()
│   ├── search.py        — search_people(), visit_profile()
│   └── status.py        — get_connection_status() — API first, UI fallback
│
├── browser/
│   ├── login.py         — launch_browser(), submit_login_form(), await_checkpoint_clear()
│   └── nav.py           — goto_page(), find_top_card(), human_type(), dump_page_html()
│
└── setup/
    └── self_profile.py  — discover_self_profile()
```

---

## Key Concepts

### Session Protocol

`LinkedInSession` is a `Protocol` (runtime-checkable). Any object with these attributes satisfies it:

| Attribute | Type | Description |
|---|---|---|
| `page` | `playwright.Page` | Active browser page |
| `context` | `playwright.BrowserContext` | Browser context (for cookies) |
| `self_profile` | `dict` | Logged-in member's profile |
| `ensure_browser()` | method | Re-connects to browser if needed |
| `wait()` | method | Human-paced delay between actions |
| `close()` | method | Closes the session |

`PlaywrightCliSession` implements the protocol via `chromium.connect(endpoint)` (connect to a bound browser). The daemon uses the library directly in-process via its own session class in `openoutreach/linkedin/browser/session.py`.

### Page State Machine

`page_state.py` is the core safety mechanism for auth navigation:

- `PageState` enum: `CHECKPOINT`, `LOGIN`, `AUTHWALL`, `FEED`, `PROFILE`, `MESSAGING`, `NOT_FOUND`, `UNKNOWN`
- `classify_page(page)` reads the URL **path only** (never query string or title) — deterministic and fast
- `@transition(when=..., then=...)` decorator: asserts page state before and after the decorated function. Raises `IllegalPageTransition` if the contract is violated.
- `PageFlow(goal, transitions)` + `PageFlow.run()`: generic observe→act loop, drives the page to a goal state in max 8 hops.

### Auth Flow

`auth.py:authenticate(session)` drives the browser to `PageState.FEED`:

```
UNKNOWN      → navigate to feed URL
AUTHWALL     → navigate to login page
LOGIN        → submit credentials form
CHECKPOINT   → await human intervention (up to 30 min via noVNC)
FEED         → done
```

Raises `AuthenticationError` on `IllegalPageTransition`. The daemon must **not** call `authenticate()` again when it sees `CheckpointChallengeError` — re-auth hardens the block.

### Voyager API Client

`PlaywrightLinkedinAPI` runs all HTTP **inside the browser page** via `page.evaluate(fetch(...))`. This means:
- Requests carry real browser cookies, `x-li-track`, `sec-ch-*`, and `user-agent` headers automatically
- CSRF token is extracted from the `JSESSIONID` cookie
- No separate HTTP client needed

Three public methods, each with 3× exponential-backoff retry on `IOError`:

| Method | Endpoint | Returns |
|---|---|---|
| `get_profile(public_identifier)` | `FullProfileWithEntities-91` | `(dict, raw_data)` |
| `get_connection_degree(public_identifier)` | `TopCardSupplementary-120` | `int \| None` (1/2/3) |
| `get_contact_info(public_identifier)` | SDUI `ProfileContactDetailsOverlay` POST | `(dict, raw_text)` |

### Connection Status Detection

`get_connection_status()` uses two layers:

1. **API degree** (fast): `get_profile()` → `connection_degree` field. If 1 → `CONNECTED`. Done.
2. **UI fallback** (slower): navigate to profile page, inspect buttons:
   - Pending button visible → `PENDING`
   - Connect button visible → `QUALIFIED`
   - More → Connect menu → `QUALIFIED`
   - No indicators found → `QUALIFIED` (fallback, dumps page HTML when `DUMP_PAGES=True`)

### Send Connection Request

`send_connection_request()` assumes the profile page is already loaded. Two flows tried in order:

1. **Direct**: finds `[aria-label*="Invite"][aria-label*="to connect"]` in the top card → clicks it
2. **More menu**: opens `More` dropdown → clicks `Connect` option

After clicking, immediately clicks "Send now" / "Send without a note". Raises `ReachedConnectionLimit` if the weekly limit alert appears.

### Send Message

`send_raw_message()` uses two paths:

1. **UI first**: navigates to `/messaging/thread/new/?recipient=<encoded_urn>`, types and submits
2. **API fallback**: finds conversation URN via `find_conversation_urn()`, then calls `send_message()` (Voyager Messaging API)

### Search

`search_people(session, keywords, page, network)`:
- Navigates to `/search/results/people/?keywords=...`
- Extracts all `/in/` profile URLs from the page
- Returns `{query, page, network, profiles}` where `profiles` is a list of `{public_identifier, url}`

---

## Configuration (`conf.py`)

| Constant | Default | Description |
|---|---|---|
| `BROWSER_HEADLESS` | `False` | LinkedIn runs headed (Xvfb in Docker) |
| `BROWSER_SLOW_MO` | `200` | Playwright slow-mo ms (humanizes interactions) |
| `BROWSER_DEFAULT_TIMEOUT_MS` | `30_000` | Default action timeout |
| `BROWSER_LOGIN_TIMEOUT_MS` | `40_000` | Login form timeout |
| `BROWSER_NAV_TIMEOUT_MS` | `10_000` | Navigation timeout |
| `HUMAN_TYPE_MIN_DELAY_MS` | `50` | Per-key min delay for human_type() |
| `HUMAN_TYPE_MAX_DELAY_MS` | `200` | Per-key max delay for human_type() |
| `CHECKPOINT_RESOLVE_TIMEOUT_S` | `1800` | How long to wait for user to clear a checkpoint (30 min) |
| `DUMP_PAGES` | `False` | Save page HTML snapshots on selector failures |
| `BROWSER_PROXY_SERVER` | `None` | Optional HTTP/SOCKS5 proxy URL |
| `BROWSER_PROXY_USERNAME` | `None` | Proxy username |
| `BROWSER_PROXY_PASSWORD` | `None` | Proxy password |

---

## Exceptions

| Exception | When raised |
|---|---|
| `AuthenticationError` | 401 from API, or `IllegalPageTransition` during auth |
| `CheckpointChallengeError(url)` | LinkedIn flagged account with security checkpoint — carries URL, do NOT re-auth |
| `IllegalPageTransition` | `@transition` pre/post state violated |
| `ProfileInaccessibleError` | HTTP 403/404 on profile (private, deleted, restricted) |
| `ReachedConnectionLimit` | Weekly connection limit alert detected |
| `SkipProfile` | Profile must be skipped (e.g. error toast on connect) |
| `TerminalStateError` | Profile is already done or dead |

---

## OpenOutreach Import Map

| OpenOutreach file | What it imports |
|---|---|
| `linkedin/browser/launch.py` | `auth.authenticate`, `browser.login.*`, `browser.nav.goto_page` |
| `linkedin/browser/session.py` | `setup.self_profile.discover_self_profile` |
| `linkedin/db/leads.py` | `url_utils.*`, `api.client.PlaywrightLinkedinAPI` |
| `linkedin/db/chat.py` | `actions.conversations.*`, `api.client.*`, `api.messaging.*` |
| `linkedin/tasks/connect.py` | `exceptions.*`, `actions.connect.*`, `actions.status.*` |
| `linkedin/tasks/check_pending.py` | `exceptions.SkipProfile`, `actions.status.*` |
| `linkedin/tasks/follow_up.py` | `actions.message.send_raw_message` |
| `linkedin/tasks/send_manual_message.py` | `actions.message.send_raw_message` |
| `linkedin/pipeline/search.py` | `actions.search.search_people` |
| `linkedin/setup/seeds.py` | `url_utils.*` |
| `mongodb/models.py` | `api.client.*`, `exceptions.*`, `browser.login.*`, `page_state.*` |
| `core/daemon.py` | `exceptions.AuthenticationError`, `exceptions.CheckpointChallengeError` |
| `core/daemon_remote.py` | `auth.authenticate`, `setup.self_profile.*`, `exceptions.*`, `conf.*` |
| `core/db/deals.py` | `exceptions.ProfileInaccessibleError` |
| `api_v2/routers/linkedin_credentials.py` | `auth.authenticate`, `browser.login.*`, `page_state.IllegalPageTransition` |

**Not imported**: `linkedin_cli.enums.ProfileState` — OpenOutreach uses its own `DealState` and lifts values via `DealState(value)` at the task-handler boundary.

---

## Known Fragility Areas

These are the places most likely to break when LinkedIn changes their UI or API:

1. **CSS selectors in `actions/connect.py` and `actions/status.py`** — The `aria-label`, `role`, and text-based selectors for Connect/Pending/More buttons. LinkedIn's frontend changes regularly. When these break, the daemon silently falls back to `QUALIFIED` and dumps HTML (if `DUMP_PAGES=True`).

2. **Voyager API decoration IDs** — `FullProfileWithEntities-91` and `TopCardSupplementary-120` in `api/client.py`. The numeric suffix changes on LinkedIn backend updates. Symptom: `get_profile()` returns `(None, None)` or raises `IOError`.

3. **SDUI contact info RSC parsing** (`api/sdui.py`) — The RSC stream format (`mailto:` / `tel:` regex extraction) is fragile. LinkedIn could change this with any frontend deploy.

4. **Messaging API** (`api/messaging/`) — Uses `messengerConversations` / `messengerMessages` GraphQL query IDs that are hard-coded. LinkedIn occasionally rotates these.

5. **Login form selectors** (`browser/login.py`) — The email/password/submit locator chains use fallback strategies, but new LinkedIn security flows (slider CAPTCHA, email OTP, etc.) are not handled.

6. **Connection degree from FullProfileWithEntities** — `connection_degree` sometimes comes back `None` from the full profile decoration. The `TopCardSupplementary` fallback catches most cases, but degree may still be `None` for very new connections or restricted accounts.

---

## CLI Usage (for dev/debugging)

```bash
# Start a bound browser session (blocks until killed)
linkedin-cli session open --session myaccount

# In another terminal:
linkedin-cli login --session myaccount
linkedin-cli whoami --session myaccount
linkedin-cli profile alice-smith --session myaccount --json
linkedin-cli status alice-smith --session myaccount
linkedin-cli connect alice-smith --session myaccount
linkedin-cli message alice-smith --text "Hi Alice" --session myaccount
linkedin-cli thread alice-smith --session myaccount
linkedin-cli search "VP Engineering San Francisco" --network second --session myaccount

# Close session
linkedin-cli session close --session myaccount
```

All output: result to stdout, logs/errors to stderr. `--json` for full dict.
