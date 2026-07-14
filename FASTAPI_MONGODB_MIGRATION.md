# FastAPI + MongoDB Migration

**Goal:** Fully eliminate Django — zero `from django` imports, zero Django dependencies. Everything runs on FastAPI + MongoDB.

**Stack:** Python, FastAPI, Uvicorn, MongoDB Atlas, Next.js, Tailwind CSS

---

## Real Current State (2026-07-14)

### What's Done
- MongoDB connection layer (`openoutreach/mongodb/connection.py`)
- MongoDB models file (`openoutreach/mongodb/models.py`) — ~50% of models ported
- Data Access Layer (`openoutreach/mongodb/dal.py`)
- Indexes (`openoutreach/mongodb/indexes.py`)
- Crypto layer (`openoutreach/mongodb/crypto.py`) — Django-independent
- FastAPI app structure (`openoutreach/api_v2/`) — 15 routers, 60+ endpoints
- Pydantic schemas (`openoutreach/api_v2/schemas/`)
- Config (`openoutreach/config.py`) — Pydantic Settings
- CLI (`openoutreach/cli.py`) — Click-based
- New daemon skeleton (`openoutreach/daemon/main.py`)
- Some models already MongoDB-native: `LinkedInProfile`, `SearchKeyword`, `ActionLog`, `Deal` (enum only), `Campaign`, `Task`, `SiteConfig`, `GhostCampaign`, `GhostSimulationLog`, `GhostTestScenario`, `CampaignHealthMetric`, `HealthAlert`, `RecoveryAction`, `Mailbox`
- Django migration dirs deleted, `manage.py` deleted, `urls.py`/`wsgi.py`/`routing.py` deleted
- Requirements cleaned of Django packages

### What's NOT Done (108 Django imports across 56 files)

**Critical active code still on Django:**

| Category | Files | Django Usage |
|----------|-------|-------------|
| **CRM Lead model** | `crm/models/lead.py` | Full Django ORM `models.Model` |
| **CRM Message model** | `crm/models/message.py` | Full Django ORM |
| **CRM Note model** | `crm/models/note.py` | Full Django ORM |
| **CRM LeadPersona** | `crm/models/persona.py` | Full Django ORM |
| **CRM TrackedLink/LinkClick** | `crm/models/link.py` | Full Django ORM |
| **CRM LinkedInCredentials** | `crm/models/linkedin_credentials.py` | Full Django ORM |
| **Core daemon** | `core/daemon.py` | `django.utils.timezone`, `django.contrib.auth.models.User` |
| **Core scheduler** | `core/scheduler.py` | `django.utils.timezone` |
| **Core deals DB** | `core/db/deals.py` | `django.db.transaction`, Django ORM queries |
| **Core follow-up agent** | `core/agents/follow_up.py` | `django.utils.timezone`, Django models |
| **Core crypto** | `core/crypto.py` | `django.conf.settings` |
| **Core signals** | `core/signals.py` | `django.db.models.signals` |
| **LinkedIn db/leads** | `linkedin/db/leads.py` | `django.db.transaction`, Django ORM queries |
| **LinkedIn db/chat** | `linkedin/db/chat.py` | Django ORM queries |
| **LinkedIn pipeline/*** | `search.py`, `qualify.py`, `ready_pool.py`, `freemium_pool.py` | `django.utils.timezone`, Django ORM |
| **LinkedIn services/*** | `smart_rate_limits.py`, `health_monitor.py`, `state_machine.py`, `ghost_mode.py` | `django.utils.timezone`, Django models |
| **LinkedIn browser/registry** | `browser/registry.py` | `import django` |
| **LinkedIn tasks/connect** | `tasks/connect.py` | Django CRM model imports |
| **LinkedIn tasks/send_manual_message** | `tasks/send_manual_message.py` | Django CRM model imports |
| **Emails nudge** | `emails/nudge.py` | Django CRM models |
| **Contacts service** | `contacts/service.py` | `core.models.SiteConfig` |
| **Notifications** | `consumers.py`, `models.py`, `signals.py`, `views.py` | Full Django (ORM, signals, views) |
| **Middleware** | `middleware/auth_logging.py`, `middleware/cors.py` | `django.conf.settings` |
| **All apps.py files** | 7 files | `django.apps.AppConfig` |
| **All admin.py files** | 4 files | `django.contrib.admin` |
| **Management commands** | 6 files | `django.core.management.base.BaseCommand` |
| **MongoDB legacy utils** | `mongodb/migration.py`, `mongodb/migrations.py`, `mongodb/urls.py`, `mongodb/views.py` | Django ORM for migration source |

**Backup files still present:**
- `openoutreach/api_django_legacy/` (11 files)
- `openoutreach/settings.py.django.bak`

---

## Phase 4: Port CRM Models to MongoDB (CRITICAL)

**Status:** COMPLETE
**Effort:** 3-5 days
**Blocks:** Everything else — these models are imported everywhere

The `crm/models/` directory still contains full Django ORM models that are actively used by the daemon, scheduler, pipeline, and task handlers.

### 4.1 Port `Lead` model to MongoDB

**File:** `openoutreach/crm/models/lead.py` (Django `models.Model`)
**Used by:** 30+ files across the entire codebase

The Lead model is the most referenced Django model. It uses:
- `models.URLField`, `models.CharField`, `models.TextField`, `models.BinaryField`
- `models.BooleanField`, `models.JSONField`, `models.DateTimeField`
- `Lead.objects.filter(...)`, `Lead.objects.get(...)`, `Lead.objects.create(...)`
- `lead.save()`, `lead.deals.filter(...)` (reverse FK)
- Methods: `get_profile()`, `get_urn()`, `get_embedding()`, `capture_contact_info()`, `resolve_api_email()`, `embed_from_profile()`, `to_profile_dict()`

**Action:**
1. Create MongoDB `Lead` class in `openoutreach/mongodb/models.py` (or extend existing)
2. Must support: `objects.filter()`, `objects.get()`, `objects.create()`, `.save()`, `.exists()`
3. Port all custom methods
4. Keep `Lead.deals` as a query helper (find deals by lead_id)

### 4.2 Port `Message` model (ChatMessage)

**File:** `openoutreach/crm/models/message.py`
**Used by:** `linkedin/db/chat.py`, task handlers

### 4.3 Port `Note` model

**File:** `openoutreach/crm/models/note.py`
**Used by:** API endpoints

### 4.4 Port `LeadPersona` model

**File:** `openoutreach/crm/models/persona.py`
**Used by:** `linkedin/agents/persona.py`

### 4.5 Port `TrackedLink`, `LinkClick`, `LinkDealConversion`

**File:** `openoutreach/crm/models/link.py`
**Used by:** `core/models.py`, `linkedin/services/state_machine.py`

### 4.6 Port `LinkedInCredentials` / `LinkedInCredentialLog`

**File:** `openoutreach/crm/models/linkedin_credentials.py`
**Used by:** `core/daemon.py`, `core/management/commands/rundaemon.py`

### 4.7 Update `crm/models/__init__.py`

Once all models are ported, this file should export from MongoDB models only. Currently it imports `DealState`/`Outcome` (already plain enums) and `Deal` from MongoDB, but re-exports Django models for `Lead`, `Message`, `Note`, etc.

### Deliverables:
- [x] `Lead` MongoDB model with full method parity
- [x] `Message` MongoDB model
- [x] `Note` MongoDB model
- [x] `LeadPersona` MongoDB model
- [x] `TrackedLink` / `LinkClick` / `LinkDealConversion` MongoDB models
- [x] `LinkedInCredentials` / `LinkedInCredentialLog` MongoDB models
- [x] `crm/models/__init__.py` exports only MongoDB models
- [ ] Delete Django ORM files from `crm/models/` (Phase 7 cleanup)

---

## Phase 5: Port Core Engine (daemon, scheduler, db layer)

**Status:** ✅ COMPLETE
**Effort:** 2-3 days
**Depends on:** Phase 4 (CRM models must be ported first)

### 5.1 Port `core/daemon.py`

**Django deps removed:**
- ✅ `from django.utils import timezone` → replaced with `datetime.now(timezone.utc)`
- ✅ `from django.contrib.auth.models import User` → removed notification code, uses MongoDB models
- ✅ `from openoutreach.core.models import Task` → `from openoutreach.mongodb.models import Task`
- ✅ `from openoutreach.core.models import Campaign` → `from openoutreach.mongodb.models import Campaign`
- ✅ `from openoutreach.core.models import SiteConfig` → `from openoutreach.mongodb.models import SiteConfig`

### 5.2 Port `core/scheduler.py`

**Django deps removed:**
- ✅ `from django.utils import timezone` → replaced with `datetime.now(timezone.utc)`
- ✅ `from openoutreach.core.models import Task` → `from openoutreach.mongodb.models import Task`
- ✅ `from openoutreach.core.models import SiteConfig` → `from openoutreach.mongodb.models import SiteConfig`
- ✅ `from openoutreach.crm.models import Deal` → `from openoutreach.mongodb.models import Deal`

### 5.3 Port `core/db/deals.py`

**Django deps removed:**
- ✅ `from django.db import transaction` → removed (MongoDB doesn't need this for single-doc ops)
- ✅ `Deal.objects.filter(...)` → MongoDB query methods (`get_by_lead_and_campaign`, `find_by_state_and_campaign`)
- ✅ `Lead.objects.filter(...)` → MongoDB query methods (`get_by_public_id`)
- ✅ All querysets replaced with MongoDB model methods

### 5.4 Port `core/crypto.py`

**Django deps removed:**
- ✅ `from django.conf import settings` → `from openoutreach.config import settings`
- ✅ Updated to use `settings.cookie_encryption_key` and `settings.secret_key`

### 5.5 Port `core/agents/follow_up.py`

**Django deps removed:**
- ✅ `from django.utils import timezone` → replaced with `datetime.now(timezone.utc)`
- ✅ `from openoutreach.chat.models import ChatMessage` → `from openoutreach.mongodb.models import ChatMessage`
- ✅ `from openoutreach.core.models import SiteConfig` → `from openoutreach.mongodb.models import SiteConfig`
- ✅ `from openoutreach.core.models import Task, Campaign` → `from openoutreach.mongodb.models import Task, Campaign`
- ✅ `from openoutreach.crm.models import Deal` → `from openoutreach.mongodb.models import Deal`

### 5.6 Remaining files (to be handled in Phase 7)

Files still containing Django imports but not critical for daemon operation:
- `core/signals.py` — Django signals, will be deleted
- `core/apps.py` — Django app config, will be deleted
- `core/admin.py` — Django admin, will be deleted
- `core/management/commands/*.py` — Django management commands, will be deleted

### Deliverables:
- [x] `core/daemon.py` — zero Django imports
- [x] `core/scheduler.py` — zero Django imports
- [x] `core/db/deals.py` — MongoDB queries, no `django.db.transaction`
- [x] `core/crypto.py` — uses `openoutreach.config.settings`
- [x] `core/agents/follow_up.py` — zero Django imports
- [ ] Delete `core/signals.py` (Phase 7)
- [ ] Delete `core/apps.py` (Phase 7)
- [ ] Delete `core/admin.py` (Phase 7)

---

## Phase 6: Port LinkedIn Module

**Status:** Not started
**Effort:** 2-3 days
**Depends on:** Phase 4 + 5

### 6.1 Port `linkedin/db/leads.py`

**Current Django deps:**
- `from django.db import transaction`
- Django ORM: `Lead.objects.filter()`, `Lead.objects.create()`, `Deal.objects.filter()`

### 6.2 Port `linkedin/db/chat.py`

Django ORM queries for messages/deals.

### 6.3 Port `linkedin/pipeline/*`

4 files using `django.utils.timezone` and Django ORM:
- `search.py` — `timezone.now()`, Lead/Deal queries
- `qualify.py` — Lead queries, DealState transitions
- `ready_pool.py` — Deal queries
- `freemium_pool.py` — Deal/Lead queries

### 6.4 Port `linkedin/services/*`

4 files using `django.utils.timezone` and Django model imports:
- `smart_rate_limits.py`
- `health_monitor.py`
- `state_machine.py`
- `ghost_mode.py`

### 6.5 Port `linkedin/tasks/connect.py` and `send_manual_message.py`

Import `DealState` (already an enum) and Django CRM models.

### 6.6 Port `linkedin/browser/registry.py`

Has `import django` — likely for Django setup. Remove.

### 6.7 Port `linkedin/agents/persona.py`

Uses `Deal`, `Lead`, `LeadPersona` from CRM Django models.

### 6.8 Port `linkedin/ml/qualifier.py`

Uses `Lead` from CRM Django models.

### 6.9 Remove Django boilerplate

- Delete `linkedin/admin.py`
- Delete `linkedin/apps.py`
- Delete `linkedin/models/rate_limits.py` Django parts (if any remain)
- Delete `linkedin/models/state_machine.py` Django parts (if any remain)

### Deliverables:
- [ ] `linkedin/db/leads.py` — MongoDB queries
- [ ] `linkedin/db/chat.py` — MongoDB queries
- [ ] `linkedin/pipeline/*` — all 4 files Django-free
- [ ] `linkedin/services/*` — all 4 files Django-free
- [ ] `linkedin/tasks/connect.py` — Django-free
- [ ] `linkedin/tasks/send_manual_message.py` — Django-free
- [ ] `linkedin/browser/registry.py` — no Django setup
- [ ] `linkedin/agents/persona.py` — MongoDB models
- [ ] `linkedin/ml/qualifier.py` — MongoDB models
- [ ] Delete `linkedin/admin.py`, `linkedin/apps.py`

---

## Phase 7: Port Remaining Modules + Final Cleanup

**Status:** Not started
**Effort:** 1-2 days
**Depends on:** Phase 6

### 7.1 Port `emails/` module

- `emails/nudge.py` — uses `Deal`, `DealState`, `Lead`, `SiteConfig`
- Delete `emails/admin.py`, `emails/apps.py`

### 7.2 Port `notifications/` module

- `notifications/models.py` — full Django ORM
- `notifications/consumers.py` — Django auth, Campaign model
- `notifications/signals.py` — Django signals
- `notifications/views.py` — Django views
- `notifications/sse.py` — may have Django deps
- Delete `notifications/apps.py`, `notifications/urls.py`

These are fully replaced by `api_v2/routers/notifications.py` and `api_v2/routers/websocket.py`. The entire `notifications/` directory can likely be deleted.

### 7.3 Port `contacts/service.py`

Uses `SiteConfig` from `core.models` — should just update the import path.

### 7.4 Port `middleware/`

- `middleware/auth_logging.py` — `django.conf.settings`
- `middleware/cors.py` — `django.conf.settings`

These are Django middleware — replaced by FastAPI middleware in `api_v2/`. Delete both.

### 7.5 Delete all `apps.py` files

7 files across `chat/`, `core/`, `crm/`, `emails/`, `linkedin/`, `mongodb/`, `notifications/`.

### 7.6 Delete all `admin.py` files

4 files: `chat/`, `core/`, `emails/`, `linkedin/`.

### 7.7 Delete all management commands

6 files in `core/management/commands/` and `mongodb/management/commands/`. Functionality moves to `cli.py`.

### 7.8 Delete Django legacy/backup files

- `openoutreach/api_django_legacy/` (entire directory)
- `openoutreach/settings.py.django.bak`
- `openoutreach/mongodb/migration.py` (Django-to-MongoDB migrator, no longer needed)
- `openoutreach/mongodb/migrations.py` (Django transaction-based)
- `openoutreach/mongodb/urls.py` (Django URL conf)
- `openoutreach/mongodb/views.py` (Django views)
- `openoutreach/crm/urls.py` (Django URL conf)
- `openoutreach/crm/views.py` (Django views)

### 7.9 Final verification

```bash
# Must return 0 lines:
grep -r "from django" openoutreach --include="*.py" | grep -v "__pycache__" | wc -l

# Must return 0 lines:
grep -r "import django" openoutreach --include="*.py" | grep -v "__pycache__" | wc -l
```

### Deliverables:
- [ ] `emails/nudge.py` — MongoDB models
- [ ] Delete `notifications/` entirely (replaced by api_v2)
- [ ] `contacts/service.py` — updated import
- [ ] Delete `middleware/` (replaced by FastAPI middleware)
- [ ] Delete all `apps.py` files (7)
- [ ] Delete all `admin.py` files (4)
- [ ] Delete all `management/commands/` dirs
- [ ] Delete `api_django_legacy/` and `settings.py.django.bak`
- [ ] Delete `mongodb/migration.py`, `mongodb/migrations.py`, `mongodb/urls.py`, `mongodb/views.py`
- [ ] Delete `crm/urls.py`, `crm/views.py`
- [ ] **Zero `from django` imports in entire codebase**

---

## Phase 8: Integration Testing + Production Deploy

**Status:** Not started
**Effort:** 2-3 days
**Depends on:** Phase 7

### 8.1 Verify daemon runs end-to-end

```bash
python -m openoutreach.cli rundaemon
```

- Task claiming works
- All 4 handlers execute (connect, check_pending, follow_up, send_manual_message)
- Scheduler creates tasks correctly
- Active hours respected

### 8.2 Verify FastAPI serves all endpoints

```bash
python -m openoutreach.cli runserver
curl http://localhost:8001/api/health
```

- Auth flow (Supabase + local JWT)
- Campaign CRUD
- Lead management
- WebSocket connections
- SSE streaming

### 8.3 Frontend integration

- Update `NEXT_PUBLIC_API_URL` to port 8001
- Test all pages work
- Test real-time (WebSocket/SSE)

### 8.4 Docker

```bash
docker compose up --build
```

- All services start
- No Django-related errors in logs
- Health check passes

### 8.5 Remove Django from Python environment

Ensure `django` is not installed in the venv. If any import fails, that file was missed.

```bash
pip uninstall django djangorestframework django-cors-headers channels daphne -y
python -c "import openoutreach"  # Must not fail
```

### Deliverables:
- [ ] Daemon runs without Django installed
- [ ] All FastAPI endpoints respond correctly
- [ ] Frontend connects to FastAPI
- [ ] Docker compose works
- [ ] `pip uninstall django` doesn't break anything
- [ ] Production deployment tested

---

## Migration Pattern Reference

### Replacing `django.utils.timezone`

```python
# Old
from django.utils import timezone
now = timezone.now()

# New
from datetime import datetime, timezone
now = datetime.now(timezone.utc)
```

### Replacing Django ORM queries

```python
# Old
from openoutreach.crm.models import Lead
lead = Lead.objects.filter(public_identifier=pid).first()
leads = Lead.objects.filter(campaign_id=cid, state="Qualified")
lead.save()

# New
from openoutreach.mongodb.connection import get_mongodb_collection
collection = get_mongodb_collection("leads")
lead_doc = collection.find_one({"public_identifier": pid})
lead = Lead.from_dict(lead_doc) if lead_doc else None
leads = [Lead.from_dict(d) for d in collection.find({"campaign_id": cid, "state": "Qualified"})]
lead.save()  # upsert to MongoDB
```

### Replacing `django.db.transaction`

MongoDB single-document operations are atomic by default. For multi-document ops, use MongoDB transactions only when truly needed:

```python
# Old
from django.db import transaction
with transaction.atomic():
    deal.state = new_state
    deal.save()
    log.save()

# New — single-doc ops are already atomic
deal.state = new_state
deal.save()
log.save()
```

### Replacing `django.contrib.auth.models.User`

```python
# Old
from django.contrib.auth.models import User
user = User.objects.get(id=user_id)

# New
from openoutreach.mongodb.models import SupabaseUser
user = SupabaseUser.get(user_id)
```

### Replacing `django.conf.settings`

```python
# Old
from django.conf import settings
key = settings.SECRET_KEY

# New
from openoutreach.config import settings
key = settings.SECRET_KEY
```

---

## Summary

| Phase | What | Effort | Status |
|-------|------|--------|--------|
| 1-3 | MongoDB models, FastAPI endpoints, infrastructure | Done | ✅ Partial |
| **4** | **Port CRM Django ORM models to MongoDB** | 3-5 days | ✅ Complete |
| **5** | **Port core engine (daemon, scheduler, db)** | 2-3 days | ✅ Complete |
| **6** | **Port LinkedIn module** | 2-3 days | ❌ Not started |
| **7** | **Port remaining + delete all Django files** | 1-2 days | ❌ Not started |
| **8** | **Integration test + production deploy** | 2-3 days | ❌ Not started |
| **Total remaining** | | **6-10 days** | |

**Success criteria:** `grep -r "from django" openoutreach --include="*.py" | wc -l` returns **0**.
