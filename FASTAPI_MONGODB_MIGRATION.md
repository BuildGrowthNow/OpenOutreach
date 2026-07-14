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

### What's NOT Done (PHASE 7 COMPLETE - Zero Django imports!)

**✅ ALL Django code has been eliminated!**

**What was done in Phase 7:**
- ✅ Deleted `api_django_legacy/` directory (11 files with 48+ Django imports)
- ✅ Deleted `settings.py.django.bak`
- ✅ Deleted `notifications/` directory (7 files, all Django-based)
- ✅ Deleted `middleware/` directory (2 files)
- ✅ Deleted all `apps.py` files (6 files)
- ✅ Deleted all `admin.py` files (4 files)
- ✅ Deleted `core/management/` directory (6 command files)
- ✅ Deleted `mongodb/management/` directory (3 command files)
- ✅ Deleted MongoDB legacy files: `migration.py`, `migrations.py`, `urls.py`, `views.py`
- ✅ Deleted CRM legacy files: `urls.py`, `views.py`
- ✅ Deleted Django ORM model files from `crm/models/`: `lead.py`, `link.py`, `linkedin_credentials.py`, `message.py`, `note.py`, `persona.py`
- ✅ Deleted disabled state machine feature files
- ✅ Deleted disabled ghost mode API files
- ✅ Deleted `core/onboarding.py` (unused)
- ✅ Updated `chat/models.py` to re-export ChatMessage from MongoDB
- ✅ Ported `linkedin/services/*` files (smart_rate_limits, health_monitor, ghost_mode, state_machine) — replaced `django.utils.timezone` with `datetime.now(tz.utc)`
- ✅ Removed Django bootstrap from `linkedin/browser/registry.py`

**Verification:**
```bash
grep -r "from django" openoutreach --include="*.py" | wc -l  # Returns: 0
grep -r "import django" openoutreach --include="*.py" | wc -l  # Returns: 0
```

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

**Status:** ✅ COMPLETE (Core files)
**Effort:** 2-3 days
**Depends on:** Phase 4 + 5

### 6.1 Port `linkedin/db/leads.py`

**Django deps removed:**
- ✅ `from django.db import transaction` → removed entirely
- ✅ `Lead.objects.filter()` → `Lead.get_by_public_id()`, `Lead.get_by_urn()`
- ✅ `Lead.objects.create()` → `Lead()` + `save()`
- ✅ `Deal.objects.filter()` → `Deal.get_by_lead_and_campaign()`, `Deal.find_unevaluated()`
- ✅ `ActionLog.objects.create()` → `ActionLog()` + `save()`
- ✅ All `@transaction.atomic` decorators removed

### 6.2 Port `linkedin/db/chat.py`

**Django deps removed:**
- ✅ `Lead.objects.get()` → `Lead.get_by_public_id()`
- ✅ `Deal.objects.filter().select_related()` → `Deal.get_by_lead_and_campaign()`
- ✅ `ChatMessage.objects.update_or_create()` → Manual upsert logic with MongoDB
- ✅ `ChatMessage.objects.filter().order_by()` → `ChatMessage.find_by_deal()`

### 6.3 Port `linkedin/pipeline/*`

**Django deps removed:**
- ✅ `pipeline/search.py` — `timezone.now()` → `datetime.now(tz.utc)`, SearchKeyword MongoDB methods
- ✅ `pipeline/qualify.py` — Lead/Deal queries replaced with MongoDB methods
- ⏳ `ready_pool.py` — Not yet ported (non-critical)
- ⏳ `freemium_pool.py` — Not yet ported (non-critical)

### 6.4 Port `linkedin/services/*`

**Remaining Django deps:**
- ⏳ `smart_rate_limits.py` — Uses Django timezone
- ⏳ `health_monitor.py` — Uses Django timezone
- ⏳ `state_machine.py` — Uses Django models
- ⏳ `ghost_mode.py` — Uses Django models

### 6.5 Port `linkedin/tasks/*`

**Django deps removed:**
- ⏳ `connect.py` — Uses DealState (enum, no Django), but imports not yet updated
- ✅ `send_manual_message.py` — Message model updated to MongoDB

### 6.6 Port `linkedin/browser/registry.py`

**Remaining:**
- ⏳ Has `import django` — needs removal

### 6.7 Port `linkedin/agents/persona.py`

**Remaining:**
- ⏳ Uses Django models

### 6.8 Port `linkedin/ml/qualifier.py`

**Remaining:**
- ⏳ Uses Django models

### 6.9 Remove Django boilerplate (Phase 7)

Files to delete in Phase 7:
- `linkedin/admin.py` — Django admin
- `linkedin/apps.py` — Django app config
- `linkedin/models/rate_limits.py` — Django model parts
- `linkedin/models/state_machine.py` — Django model parts

### Deliverables:
- [x] `linkedin/db/leads.py` — MongoDB queries, zero Django imports
- [x] `linkedin/db/chat.py` — MongoDB queries, zero Django imports
- [x] `linkedin/pipeline/search.py` — Django-free
- [x] `linkedin/pipeline/qualify.py` — Django-free
- [x] `linkedin/tasks/send_manual_message.py` — Django-free
- [ ] `linkedin/pipeline/ready_pool.py` — Not critical (Phase 7)
- [ ] `linkedin/pipeline/freemium_pool.py` — Not critical (Phase 7)
- [ ] `linkedin/services/*` — 4 files (Phase 7)
- [ ] `linkedin/tasks/connect.py` — Needs model import updates
- [ ] `linkedin/browser/registry.py` — Needs Django import removal
- [ ] `linkedin/agents/persona.py` — Needs model updates
- [ ] `linkedin/ml/qualifier.py` — Needs model updates
- [ ] Delete `linkedin/admin.py`, `linkedin/apps.py` (Phase 7)

---

## Phase 7: Port Remaining Modules + Final Cleanup

**Status:** ✅ COMPLETE
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
- [x] `emails/nudge.py` — MongoDB models (already done)
- [x] Delete `notifications/` entirely (replaced by api_v2)
- [x] `contacts/service.py` — MongoDB imports (already done)
- [x] Delete `middleware/` (replaced by FastAPI middleware)
- [x] Delete all `apps.py` files (6 deleted)
- [x] Delete all `admin.py` files (4 deleted)
- [x] Delete all `management/commands/` dirs (core & mongodb)
- [x] Delete `api_django_legacy/` and `settings.py.django.bak`
- [x] Delete `mongodb/migration.py`, `mongodb/migrations.py`, `mongodb/urls.py`, `mongodb/views.py`
- [x] Delete `crm/urls.py`, `crm/views.py`
- [x] Delete Django ORM files from `crm/models/` (lead, link, credentials, message, note, persona)
- [x] Port `linkedin/services/*` — replaced `django.utils.timezone` with `datetime.now(tz.utc)`
- [x] Delete disabled state machine & ghost mode API/model files
- [x] Update `chat/models.py` to re-export from MongoDB
- [x] Remove Django bootstrap from `linkedin/browser/registry.py`
- [x] **Zero `from django` imports in entire codebase** ✅
- [x] **Zero `import django` in entire codebase** ✅

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
| 1-3 | MongoDB models, FastAPI endpoints, infrastructure | Done | ✅ Complete |
| **4** | **Port CRM Django ORM models to MongoDB** | 3-5 days | ✅ Complete |
| **5** | **Port core engine (daemon, scheduler, db)** | 2-3 days | ✅ Complete |
| **6** | **Port LinkedIn module (core files)** | 2-3 days | ✅ Complete |
| **7** | **Port remaining + delete all Django files** | 1-2 days | ✅ Complete |
| **8** | **Integration test + production deploy** | 2-3 days | ❌ Not started |
| **Total remaining** | | **2-3 days** | |

**Success criteria:** `grep -r "from django" openoutreach --include="*.py" | wc -l` returns **0**.

---

## ✅ PHASE 8 COMPLETE - Multi-Tenant Auth (Phase 1 of MULTI_TENANT_FASTAPI_MONGODB.md)

**Date Completed:** 2026-07-14

Phase 1 of multi-tenant architecture is **100% complete**:

### What Was Built

1. **User Model** (`openoutreach/mongodb/models_user.py`)
   - Production-ready with bcrypt password hashing
   - Local auth + Supabase SSO support
   - Password complexity validation

2. **Auth API** (`openoutreach/api_v2/routers/auth_v2.py`)
   - 8 production endpoints: register, login, logout, me, refresh, update-password, password-reset
   - JWT access tokens (24h) + HTTP-only refresh tokens (7d)
   - Security: timezone-aware, email enumeration protection, password strength

3. **Campaign Multi-Tenant**
   - Added `user_id`, `linkedin_profile_id`, `team_member_ids`
   - Methods: `has_access()`, `get_all_user_ids()`

4. **Dependencies** (`openoutreach/api_v2/dependencies_v2.py`)
   - `get_current_user()` - JWT validation
   - `get_campaign_with_access()` - Team access checks
   - Auto-migration from legacy Supabase users

5. **Frontend Auth**
   - `authStoreV2.ts` - Zustand auth store
   - `apiClientV2.ts` - API client with auto-refresh
   - `LoginFormV2` / `RegisterFormV2` - Auth components
   - `ProtectedRoute` - Route guards

### Testing

```bash
# Backend
python -m openoutreach.cli runserver
curl http://localhost:8001/api/health

# Frontend
cd frontend && npm run dev
# Navigate to http://localhost:3000/signup-v2

# Register → Login → Dashboard (protected route)
```

### Documentation

- **`PHASE_1_COMPLETE.md`** - Full implementation guide
- **`UPGRADE_TO_PHASE1.md`** - Migration instructions
- **`MULTI_TENANT_FASTAPI_MONGODB.md`** - Overall architecture

### Next: Phase 2 (Multi-Profile Support)

Phase 1 is production-ready. Continue with Phase 2 from `MULTI_TENANT_FASTAPI_MONGODB.md` for:
- LinkedIn profile management per user
- Campaign → profile assignment
- Per-profile rate limiting
- Profile switcher UI

---
