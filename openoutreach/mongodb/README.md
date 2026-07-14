# MongoDB Data Layer - Usage Guide

This package provides a complete MongoDB data layer for OpenOutreach, ready to replace Django ORM.

## Quick Start

### 1. Initialize Connection

```python
from openoutreach.mongodb.connection import initialize_mongodb_connection
from openoutreach.mongodb.indexes import ensure_all_indexes

# Initialize MongoDB (call once at startup)
initialize_mongodb_connection()

# Create all indexes
ensure_all_indexes()
```

### 2. Use Models Directly

```python
from openoutreach.mongodb.models import Lead, Campaign, Deal

# Create a lead
lead = Lead(
    linkedin_url="https://linkedin.com/in/johndoe",
    public_identifier="johndoe",
    user_id="user_123"
)
lead.save()

# Query a lead
lead = Lead.get(lead_id)
lead = Lead.find_by_public_identifier("johndoe")

# Update a lead
lead.api_email = "john@example.com"
lead.save()

# Delete a lead
Lead.delete(lead_id)
```

### 3. Use Data Access Layer (Recommended)

```python
from openoutreach.mongodb.dal import TaskDAL, CampaignDAL, LeadDAL

# Create a task
task = TaskDAL.create_task(
    task_type="connect",
    linkedin_profile_id="profile_123",
    payload={"campaign_id": "camp_456"},
    scheduled_at=datetime.utcnow()
)

# Daemon: atomically claim next task
task = TaskDAL.claim_next_task()
if task:
    try:
        # Process task...
        TaskDAL.mark_task_completed(task._id)
    except Exception as e:
        TaskDAL.mark_task_failed(task._id, str(e))

# Delete campaign with cascade
CampaignDAL.delete_campaign(campaign_id)

# Find or create lead
lead, created = LeadDAL.find_or_create_lead(
    linkedin_url="https://linkedin.com/in/jane",
    public_identifier="jane",
    user_id="user_123"
)
```

### 4. Encryption

```python
from openoutreach.mongodb.crypto import encrypt_text, decrypt_text, EncryptedField

# Manual encryption
encrypted = encrypt_text("my_password")
decrypted = decrypt_text(encrypted)

# Auto-encrypting model field
class MyModel:
    password = EncryptedField()
    
    def __init__(self, password=""):
        self._password = None
        self.password = password  # Auto-encrypts

model = MyModel(password="secret")
print(model.password)  # Auto-decrypts on read
```

## Architecture

```
openoutreach/mongodb/
├── connection.py       # MongoDB connection management
├── models.py           # Core models (Lead, Campaign, Deal, Task, etc.)
├── models_extended.py  # Extended models (ChatMessage, Notification, etc.)
├── dal.py              # Data Access Layer (recommended interface)
├── indexes.py          # Index definitions (37 indexes)
├── crypto.py           # Encryption utilities
└── README.md           # This file
```

## Models Available

### Core Models (models.py)
- `SupabaseUser` - Supabase user mapping
- `Lead` - LinkedIn leads
- `Campaign` - Marketing campaigns
- `Deal` - Lead-Campaign relationships
- `Task` - Task queue
- `SiteConfig` - Global configuration
- `LinkedInCredentials` - Encrypted LinkedIn credentials
- `LinkedInCredentialLog` - Credential audit log
- `UserProfile` - Extended user profiles
- `Message` - Generic messages
- `Note` - Deal notes
- `LeadPersona` - LLM-generated personas
- `TrackedLink` - URL tracking
- `LinkClick` - Click records
- `LinkDealConversion` - Conversion attribution

### Extended Models (models_extended.py)
- `ChatMessage` - LinkedIn conversation messages
- `ActionLog` - Activity feed + error tracking
- `Notification` - User notifications
- `SearchKeyword` - Campaign search keywords
- `Mailbox` - SMTP mailboxes
- `CampaignTemplate` - Campaign templates

## DAL Methods

### TaskDAL
- `create_task()` - Create task
- `claim_next_task()` - **Atomic** claim (critical for daemon)
- `mark_task_completed()` - Complete task
- `mark_task_failed()` - Fail task
- `get_pending_tasks_count()` - Count pending
- `cleanup_campaign_tasks()` - Cascade delete
- `recover_stale_tasks()` - Recover hung tasks

### CampaignDAL
- `get_user_campaigns()` - List campaigns
- `get_active_campaigns()` - Filter active
- `delete_campaign()` - **Cascade delete** (safe)

### DealDAL
- `get_qualified_deals()` - Query by state
- `get_deals_by_campaign()` - List all
- `set_deal_state()` - Update state
- `get_deals_by_state()` - Filter

### LeadDAL
- `find_or_create_lead()` - Upsert
- `get_leads_by_user()` - List

### NotificationDAL
- `create_notification()` - Create
- `get_unread()` - Query unread
- `mark_all_read()` - Bulk update

### ActionLogDAL
- `create()` - Log action
- `get_daily_count()` - Rate limiting
- `get_campaign_activity()` - Activity feed

## Environment Variables

```bash
# Required
MONGODB_URI=mongodb://localhost:27017/
MONGODB_NAME=openoutreach

# Encryption (choose one)
COOKIE_ENCRYPTION_KEY=<base64-encoded-32-byte-key>
# OR derive from:
SECRET_KEY=<django-secret-key>

# Optional
MONGODB_SERVER_SELECTION_TIMEOUT=30000
MONGODB_CONNECT_TIMEOUT=30000
MONGODB_SOCKET_TIMEOUT=10000
```

## Best Practices

### 1. Use DAL Over Direct Models
```python
# Good - uses DAL
from openoutreach.mongodb.dal import TaskDAL
task = TaskDAL.claim_next_task()

# Avoid - direct model usage (bypasses business logic)
from openoutreach.mongodb.models import Task
task = Task.objects().filter(status="pending").first()
```

### 2. Always Use Atomic Operations for Daemon
```python
# Correct - atomic claim prevents race conditions
task = TaskDAL.claim_next_task()

# Wrong - non-atomic (race condition!)
tasks = Task.objects().filter(status="pending")
if tasks:
    task = tasks[0]
    task.status = "running"
    task.save()
```

### 3. Use Cascade Delete for Campaigns
```python
# Correct - cascade deletes everything
CampaignDAL.delete_campaign(campaign_id)

# Wrong - orphans related data
Campaign.delete(campaign_id)
```

### 4. Safe Encryption
```python
from openoutreach.mongodb.crypto import safe_encrypt, safe_decrypt

# Safe - won't double-encrypt
encrypted = safe_encrypt(password)
encrypted = safe_encrypt(encrypted)  # No-op

# Safe - won't crash on non-encrypted
decrypted = safe_decrypt(plain_text)  # Returns plain_text
```

## Migration from Django ORM

### Before (Django)
```python
from openoutreach.core.models import Campaign, Task

# Query
campaigns = Campaign.objects.filter(user_id=user_id, is_paused=False)

# Create
task = Task.objects.create(
    task_type="connect",
    status="pending",
    payload={"campaign_id": campaign_id}
)

# Update
task.status = "completed"
task.save()

# Delete with cascade (via signal)
campaign.delete()
```

### After (MongoDB)
```python
from openoutreach.mongodb.models import Campaign
from openoutreach.mongodb.dal import TaskDAL, CampaignDAL

# Query
campaigns = Campaign.objects().filter(user_id=user_id, is_paused=False)

# Create (use DAL)
task = TaskDAL.create_task(
    task_type="connect",
    payload={"campaign_id": campaign_id},
    scheduled_at=datetime.utcnow()
)

# Update
task.status = "completed"
task.save()

# Delete with cascade (use DAL)
CampaignDAL.delete_campaign(campaign_id)
```

## Performance Tips

### 1. Indexes Are Created Automatically
```python
# Run once at startup - creates all 37 indexes
ensure_all_indexes()
```

### 2. Use Compound Index Queries
```python
# Good - uses task_queue_idx
tasks = collection.find({
    "status": "pending",
    "scheduled_at": {"$lte": datetime.utcnow()}
}).sort("scheduled_at", 1)

# Bad - doesn't use index
tasks = collection.find({"status": "pending"}).sort("created_at", 1)
```

### 3. Pagination
```python
# Good - uses limit/skip
leads = LeadDAL.get_leads_by_user(user_id, limit=100)

# Bad - loads everything
leads = Lead.objects().filter(user_id=user_id)
```

## Troubleshooting

### Connection Fails
```python
# Check MongoDB is running
from openoutreach.mongodb.connection import check_mongodb_connection

if not check_mongodb_connection():
    print("MongoDB not connected!")
```

### Encryption Fails
```python
# Generate a new key
from openoutreach.mongodb.crypto import generate_key

key = generate_key()
print(f"COOKIE_ENCRYPTION_KEY={key}")
# Add to .env
```

### Indexes Not Created
```python
# Force index creation
from openoutreach.mongodb.indexes import ensure_all_indexes

result = ensure_all_indexes()
print(f"Created {result['created']} indexes")
```

### Stale Tasks
```python
# Recover hung tasks (run periodically)
from openoutreach.mongodb.dal import TaskDAL

recovered = TaskDAL.recover_stale_tasks(timeout_minutes=30)
print(f"Recovered {recovered} stale tasks")
```

## Testing

```python
import pytest
from openoutreach.mongodb.connection import initialize_mongodb_connection, reset_mongodb_connection

@pytest.fixture(autouse=True)
def mongodb_connection():
    initialize_mongodb_connection()
    yield
    reset_mongodb_connection()

def test_task_claiming():
    from openoutreach.mongodb.dal import TaskDAL
    from datetime import datetime
    
    # Create task
    task = TaskDAL.create_task(
        task_type="connect",
        linkedin_profile_id="test",
        payload={},
        scheduled_at=datetime.utcnow()
    )
    
    # Claim it
    claimed = TaskDAL.claim_next_task()
    assert claimed._id == task._id
    assert claimed.status == "running"
```

## Next Steps

1. Enable dual-write (Django + MongoDB)
2. Migrate data from SQLite to MongoDB
3. Port API endpoints to use DAL
4. Remove Django dependencies
5. Switch to FastAPI

See `/FASTAPI_MONGODB_MIGRATION.md` for full migration plan.
