# Django Cleanup Status

**Date**: 2026-07-14  
**Status**: 🔄 In Progress (15% complete)

---

## ✅ Completed

### Requirements Files
- ✅ Removed Django REST Framework from `requirements/api.txt`
- ✅ Removed `pytest-django` from `requirements/local.txt`
- ✅ `requirements/fastapi.txt` is Django-free
- ✅ `requirements/base.txt` is Django-free

### MongoDB Connection
- ✅ Removed all Django imports from `openoutreach/mongodb/connection.py`
- ✅ Now uses `openoutreach.config.settings` (Pydantic) instead of Django settings
- ✅ Removed `django.conf.settings` dependency

### Browser Module
- ✅ Fixed `openoutreach/linkedin/browser/launch.py` 
  - Replaced `django.utils.timezone` with Python `datetime.timezone`
  - Updated credential verification to use MongoDB collections

### Core Infrastructure
- ✅ `openoutreach/daemon/main.py` - Pure Python, MongoDB-native (Django-free)
- ✅ `openoutreach/config.py` - Pydantic Settings (replaces Django settings)
- ✅ `openoutreach/cli.py` - Click CLI (replaces manage.py)

---

## 🔄 In Progress

### Task Handlers (Critical - Blocks Daemon)
The following files still import Django models and need MongoDB equivalents:

**openoutreach/linkedin/tasks/**
- ⏳ `check_pending.py` - Uses `django.utils.timezone`, `openoutreach.crm.models.{Deal, DealState}`
- ⏳ `follow_up.py` - Uses `django.utils.timezone`, `openoutreach.crm.models.{Deal, Lead, DealState}`
- ⏳ `connect.py` - Uses `openoutreach.crm.models.{Deal, Lead, DealState}`
- ⏳ `send_manual_message.py` - Uses `openoutreach.crm.models.{Message, DealState}`

**Required Changes:**
```python
# Old (Django)
from django.utils import timezone
from openoutreach.crm.models import Deal, Lead, DealState

deal = Deal.objects.get(id=deal_id)
deal.state = DealState.CONNECTED
deal.save()

# New (MongoDB)
from datetime import datetime, timezone
from openoutreach.mongodb import models

deal = models.Deal.get(deal_id)
deal.state = models.Deal.State.CONNECTED
deal.save()
```

### Core Module (Django Models - Legacy)
These files contain Django ORM models that are deprecated but still referenced:

**openoutreach/core/**
- ⏳ `models.py` - Django models (SiteConfig, Campaign, CampaignTemplate, Task)
- ⏳ `signals.py` - Django signals (`cleanup_campaign_tasks`)
- ⏳ `apps.py` - Django AppConfig
- ⏳ `admin.py` - Django admin
- ⏳ `scheduler.py` - Uses Django models
- ⏳ `management/commands/` - Django management commands

### LinkedIn Module (Mixed - Some Django, Some Active)
**Django-only files (can be ignored):**
- `linkedin/models/` - All Django models (deprecated)
- `linkedin/admin.py` - Django admin (deprecated)
- `linkedin/apps.py` - Django AppConfig (deprecated)

**Active files that need fixing:**
- ⏳ `linkedin/services/smart_rate_limits.py` - Uses Django models
- ⏳ `linkedin/services/health_monitor.py` - Uses Django models
- ⏳ `linkedin/services/state_machine.py` - Uses Django models
- ⏳ `linkedin/services/ghost_mode.py` - Uses Django models
- ⏳ `linkedin/pipeline/search.py` - Uses Django models
- ⏳ `linkedin/db/leads.py` - Uses Django models
- ⏳ `linkedin/browser/registry.py` - May use Django models

### CRM Module (Django Models - Needs MongoDB Port)
**openoutreach/crm/**
- ⏳ `models/deal.py` - Django Deal model
- ⏳ `models/lead.py` - Django Lead model  
- ⏳ `models/linkedin_credentials.py` - Django LinkedInCredentials model
- ⏳ `models/link.py` - Django TrackedLink/LinkClick models
- ⏳ `models/message.py` - Django Message model
- ⏳ `models/note.py` - Django Note model
- ⏳ `models/persona.py` - Django LeadPersona model

---

## ❌ Blocked / Needs Decision

### Frontend API Integration
The frontend still points to port 8000 (Django). Need to:
- ⏳ Update frontend API base URL to port 8001
- ⏳ Test all frontend → FastAPI endpoints
- ⏳ Update authentication flow

### Server Deployment
- ⏳ Update Nginx configuration (use `update_nginx_ports.sh` script)
- ⏳ Test FastAPI server on production
- ⏳ Migrate production database to MongoDB

---

## 📊 Progress Metrics

| Category | Total Files | Cleaned | Remaining | % Complete |
|----------|-------------|---------|-----------|------------|
| Requirements | 4 | 4 | 0 | 100% |
| MongoDB Module | 6 | 2 | 4 | 33% |
| Core Module | 15 | 3 | 12 | 20% |
| LinkedIn Tasks | 4 | 0 | 4 | 0% |
| LinkedIn Services | 8 | 0 | 8 | 0% |
| CRM Models | 7 | 0 | 7 | 0% |
| **TOTAL** | **44** | **9** | **35** | **20%** |

---

## 🎯 Next Steps (Priority Order)

### 1. Task Handlers (CRITICAL - Blocks Daemon) ⭐⭐⭐
**Files:** `openoutreach/linkedin/tasks/*.py`  
**Reason:** Daemon cannot execute tasks without these fixes  
**Effort:** ~2-4 hours  
**Actions:**
- Replace `django.utils.timezone` → `datetime.timezone`
- Replace `openoutreach.crm.models.Deal` → `openoutreach.mongodb.models.Deal`
- Replace `openoutreach.crm.models.Lead` → `openoutreach.mongodb.models.Lead`
- Replace `DealState` enum from Django → MongoDB
- Test each handler individually

### 2. Core Scheduler (CRITICAL - Blocks Task Creation) ⭐⭐⭐
**File:** `openoutreach/core/scheduler.py`  
**Reason:** Creates tasks for the daemon  
**Effort:** ~2-3 hours  
**Actions:**
- Replace Django `Campaign`, `Task`, `Deal` models with MongoDB equivalents
- Update queries to use MongoDB query syntax
- Test task creation/reconciliation

### 3. MongoDB Models Completion (HIGH - Core Functionality) ⭐⭐
**Files:** `openoutreach/mongodb/models.py`, `openoutreach/mongodb/dal.py`  
**Reason:** Missing models referenced by task handlers  
**Effort:** ~4-6 hours  
**Actions:**
- Complete all 32 MongoDB models (currently ~50% done)
- Implement missing DAL methods
- Add proper indexes
- Write unit tests

### 4. LinkedIn Services (MEDIUM - Feature Completeness) ⭐
**Files:** `openoutreach/linkedin/services/*.py`  
**Reason:** Health monitoring, state machine, ghost mode  
**Effort:** ~3-4 hours  
**Actions:**
- Port to MongoDB models
- Test each service independently

### 5. Server Deployment (HIGH - Production) ⭐⭐
**Actions:**
- Run `update_nginx_ports.sh` on server
- Update systemd service to use FastAPI
- Test full stack end-to-end
- Migrate production data

---

## 🔍 How to Find Django Dependencies

```bash
# Find all Django imports (excluding legacy)
grep -r "from django" openoutreach --include="*.py" | \
  grep -v "api_django_legacy" | \
  grep -v ".pyc" | \
  wc -l
# Currently: 129 instances

# Find Django model imports
grep -r "from openoutreach.core.models\|from openoutreach.crm.models" \
  openoutreach --include="*.py" | \
  grep -v "api_django_legacy" | \
  wc -l

# Find files that need fixing
grep -r "from django" openoutreach --include="*.py" -l | \
  grep -v "api_django_legacy" | \
  sort | uniq
```

---

## 🚀 Testing Strategy

### Unit Tests
```bash
# Test MongoDB connection
pytest tests/test_mongodb_connection.py

# Test MongoDB models
pytest tests/test_mongodb_models.py

# Test task handlers (after porting)
pytest tests/linkedin/tasks/
```

### Integration Tests
```bash
# Test daemon startup
python -m openoutreach.cli rundaemon --test

# Test FastAPI server
python -m openoutreach.cli runserver
curl http://localhost:8001/api/health

# Test task execution
python -m openoutreach.cli test-task-handler connect
```

### Production Validation
```bash
# SSH into server
ssh -i ~/.ssh/lenquant.pem ubuntu@ec2-50-19-251-160.compute-1.amazonaws.com

# Check Nginx config
sudo nginx -t

# Update Nginx
./update_nginx_ports.sh

# Restart services
sudo systemctl restart openoutreach-api
sudo systemctl restart openoutreach-daemon

# Check logs
sudo journalctl -u openoutreach-api -f
sudo journalctl -u openoutreach-daemon -f
```

---

## ⚠️ Known Issues

### 1. MongoDB Models Incomplete
- Missing: `ChatMessage`, `Notification`, `TrackedLink`, `LinkClick`
- Impact: Task handlers will fail on certain operations
- Solution: Complete `openoutreach/mongodb/models.py`

### 2. Task Handlers Use Django Models
- Impact: Daemon will crash on task execution
- Solution: Port all 4 task handler files to MongoDB

### 3. Frontend API Port Mismatch
- Impact: Frontend cannot reach FastAPI backend
- Solution: Update `NEXT_PUBLIC_API_URL` to `http://localhost:8001/api`

### 4. No Production MongoDB Instance
- Impact: Server deployment will fail
- Solution: Set up MongoDB Atlas or local MongoDB on server

---

## 📞 Questions / Decisions Needed

1. **MongoDB Hosting:** MongoDB Atlas (cloud) or local MongoDB on EC2?
2. **Data Migration:** Migrate existing Django SQLite data to MongoDB?
3. **Rollback Plan:** Keep Django code in `api_django_legacy/` or delete?
4. **Frontend Update:** Update immediately or wait for backend completion?

---

**Last Updated**: 2026-07-14  
**Next Review**: After task handlers are ported  
**Owner**: Engineering Team
