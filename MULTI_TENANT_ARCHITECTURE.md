# Multi-Tenant Architecture: Scaling from 1 to 100+ LinkedIn Accounts

## Overview

This document describes the migration from single-user architecture to multi-tenant SaaS, enabling multiple users to run independent campaigns with their own LinkedIn accounts.

**Scaling Path:**
- Phase 1: 1 user, 1 account (current state)
- Phase 2: 1 user, 3-5 accounts
- Phase 3: Multiple users, each with 1-N accounts
- Phase 4: 100+ users, horizontal scaling

---

## Current Architecture (Single-Tenant)

```
OpenOutreach Instance
├── One LinkedInProfile (implied owner)
├── One AccountSession
├── N Campaigns (all belong to same account)
└── Shared daemon (processes one account's tasks)
```

**Limitations:**
- No user authentication/authorization
- Cannot isolate data between users
- One browser session per instance
- Cannot scale beyond one LinkedIn account without conflicts

---

## Phase 1: Foundation - User Management & Data Isolation

### 1.1 Add User Model & Authentication

**Django User Model:**
```python
# Use Django's built-in User or create custom
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Future: plan_tier, usage_quota, etc.
```

**Add to all models:**
```python
# openoutreach/crm/models/lead.py
class LinkedInProfile(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='linkedin_profiles')
    # ... existing fields

# openoutreach/core/models/campaign.py
class Campaign(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    linkedin_profile = models.ForeignKey(LinkedInProfile, on_delete=models.CASCADE)
    # ... existing fields
    
    class Meta:
        # Ensure queries are always scoped
        indexes = [
            models.Index(fields=['user', 'created_at']),
        ]

# openoutreach/crm/models/lead.py
class Lead(models.Model):
    # Leads are global (same person can be targeted by multiple users)
    # But access is controlled through Deal
    pass

class Deal(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE)
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE)
    # Deal inherits user ownership through campaign
    
    @property
    def user(self):
        return self.campaign.user
```

**Migration Strategy:**
```bash
# Step 1: Add nullable user field to all models
python manage.py makemigrations

# Step 2: Create default user and assign existing data
python manage.py shell
>>> from django.contrib.auth import get_user_model
>>> User = get_user_model()
>>> default_user = User.objects.create_user('default@example.com', password='...')
>>> LinkedInProfile.objects.update(user=default_user)
>>> Campaign.objects.update(user=default_user)

# Step 3: Make user non-nullable
python manage.py makemigrations
```

### 1.2 API Authentication

**Add JWT or Session Auth:**
```python
# requirements/base.txt
djangorestframework-simplejwt

# openoutreach/settings.py
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# openoutreach/api/views/campaigns.py
class CampaignViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        # CRITICAL: Always scope to current user
        return Campaign.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
```

### 1.3 Frontend Authentication

**Add Login/Signup:**
```typescript
// frontend/src/app/(auth)/login/page.tsx
// frontend/src/app/(auth)/signup/page.tsx
// frontend/src/lib/auth.ts - token management

// All API calls include auth token:
fetch('/api/campaigns/', {
  headers: {
    'Authorization': `Bearer ${token}`
  }
})
```

**Account Switcher (for users with multiple LinkedIn profiles):**
```typescript
// frontend/src/components/account-switcher.tsx
// Shows dropdown of user's LinkedIn profiles
// Stores selected profile_id in context
// All API calls filtered by selected profile
```

---

## Phase 2: Multi-Account Support (Same User)

### 2.1 Browser Session Management

**Current:** One global `AccountSession` per daemon
**Target:** Multiple concurrent `AccountSession` objects

```python
# openoutreach/linkedin/browser/session.py
class AccountSessionManager:
    """Manages multiple concurrent browser sessions."""
    
    def __init__(self):
        self._sessions: Dict[int, AccountSession] = {}  # profile_id → session
        self._locks: Dict[int, asyncio.Lock] = {}
    
    async def get_session(self, profile_id: int) -> AccountSession:
        """Get or create session for a LinkedIn profile."""
        if profile_id not in self._sessions:
            profile = LinkedInProfile.objects.get(id=profile_id)
            self._sessions[profile_id] = await AccountSession.create(profile)
            self._locks[profile_id] = asyncio.Lock()
        return self._sessions[profile_id]
    
    async def close_session(self, profile_id: int):
        """Close and cleanup a session."""
        if profile_id in self._sessions:
            await self._sessions[profile_id].close()
            del self._sessions[profile_id]
            del self._locks[profile_id]

# Global manager
session_manager = AccountSessionManager()
```

### 2.2 Task Queue Partitioning

**Current:** Tasks pull from global queue
**Target:** Tasks partitioned by LinkedIn profile

```python
# openoutreach/core/models/task.py
class Task(models.Model):
    linkedin_profile = models.ForeignKey(LinkedInProfile, on_delete=models.CASCADE)
    # ... existing fields
    
    class Meta:
        indexes = [
            models.Index(fields=['linkedin_profile', 'status', 'scheduled_at']),
        ]

# Task handler signature changes:
def handle_connect(task, session, qualifiers):
    # session is now AccountSession for task.linkedin_profile
    deal = Deal.objects.get(id=task.payload['deal_id'])
    # Verify ownership
    assert deal.campaign.linkedin_profile_id == task.linkedin_profile_id
    # ... rest of handler
```

### 2.3 Daemon Refactor: Multi-Account Loop

**Current:** Single account task loop
**Target:** Concurrent task processing per account

```python
# openoutreach/core/daemon.py
class MultiAccountDaemon:
    def __init__(self):
        self.session_manager = AccountSessionManager()
        self.active_profiles = set()  # Currently processing profile IDs
    
    async def run(self):
        """Main daemon loop - process all active profiles."""
        while True:
            active_profiles = LinkedInProfile.objects.filter(
                is_active=True,
                user__is_active=True  # User not suspended
            )
            
            # Spawn concurrent workers per profile
            tasks = [
                self.process_profile_tasks(profile)
                for profile in active_profiles
            ]
            
            await asyncio.gather(*tasks, return_exceptions=True)
            await asyncio.sleep(10)  # Check for new profiles every 10s
    
    async def process_profile_tasks(self, profile: LinkedInProfile):
        """Process tasks for a single LinkedIn profile."""
        session = await self.session_manager.get_session(profile.id)
        
        # Pull tasks for this profile only
        tasks = Task.objects.filter(
            linkedin_profile=profile,
            status=TaskStatus.PENDING,
            scheduled_at__lte=now()
        ).order_by('scheduled_at')[:1]
        
        for task in tasks:
            await self.execute_task(task, session)
        
        # Reconcile if idle
        if not tasks.exists():
            await reconcile(session, profile)
```

### 2.4 Proxy Management (Residential Proxies)

**When to use proxies:**
- 1-2 accounts: No proxy (use local IP)
- 3-10 accounts: Datacenter proxies (cheap, ~$5/mo)
- 10+ accounts: Residential proxies (~$50-100/mo)

**Proxy per account:**
```python
# openoutreach/crm/models/linkedin_profile.py
class LinkedInProfile(models.Model):
    # ... existing fields
    proxy_url = models.CharField(max_length=500, blank=True)  # http://user:pass@proxy:port
    use_residential_proxy = models.BooleanField(default=False)

# openoutreach/linkedin/browser/launch.py
async def launch_browser(profile: LinkedInProfile) -> Browser:
    launch_options = {
        "headless": BROWSER_HEADLESS,
        "args": ["--disable-blink-features=AutomationControlled"],
    }
    
    if profile.proxy_url:
        launch_options["proxy"] = {
            "server": profile.proxy_url
        }
    
    browser = await playwright.chromium.launch(**launch_options)
    return browser
```

**Proxy Providers (Residential):**
- Bright Data: ~$12.75/GB
- Smartproxy: ~$8.5/GB  
- Oxylabs: ~$15/GB

**Cost estimate:** 100 accounts × $1-2/account/month = $100-200/month in proxy costs

---

## Phase 3: Horizontal Scaling (Multiple EC2 Instances)

### 3.1 Deployment Topology

**Single Instance (1-20 accounts):**
```
EC2 Instance
├── Postgres DB
├── Django API (gunicorn)
├── Next.js Frontend (pm2)
└── Daemon (multi-account loop)
```

**Multi-Instance (20-100+ accounts):**
```
AWS Architecture:
├── RDS Postgres (shared database)
├── EC2 Instance 1 (API + Frontend)
│   ├── Django API (gunicorn)
│   └── Next.js Frontend
├── EC2 Instance 2 (Daemon Worker 1)
│   └── Processes accounts 1-50
├── EC2 Instance 3 (Daemon Worker 2)
│   └── Processes accounts 51-100
└── Load Balancer (API/Frontend)
```

### 3.2 Distributed Task Processing

**Challenge:** Multiple daemon instances must not process same tasks

**Solution 1: Database-Level Locking**
```python
# Use SELECT FOR UPDATE to claim tasks
with transaction.atomic():
    task = Task.objects.select_for_update(skip_locked=True).filter(
        status=TaskStatus.PENDING,
        linkedin_profile_id=profile_id,
        scheduled_at__lte=now()
    ).first()
    
    if task:
        task.status = TaskStatus.RUNNING
        task.started_at = now()
        task.save()
```

**Solution 2: Partition by Profile**
```python
# Env var on each daemon instance
ASSIGNED_PROFILE_IDS = "1,2,3,10,15"  # Comma-separated profile IDs

# Daemon only processes assigned profiles
active_profiles = LinkedInProfile.objects.filter(
    id__in=ASSIGNED_PROFILE_IDS.split(','),
    is_active=True
)
```

**Solution 3: Redis-Based Distributed Lock**
```python
import redis
from redis.lock import Lock

redis_client = redis.Redis(host='localhost', port=6379)

async def process_profile_tasks(self, profile: LinkedInProfile):
    lock_key = f"profile_lock:{profile.id}"
    lock = Lock(redis_client, lock_key, timeout=300)
    
    if lock.acquire(blocking=False):
        try:
            # Process tasks
            await self._process_tasks(profile)
        finally:
            lock.release()
    else:
        # Another daemon is processing this profile
        return
```

### 3.3 Infrastructure as Code (Terraform)

```hcl
# terraform/main.tf
resource "aws_db_instance" "postgres" {
  identifier        = "openoutreach-db"
  engine            = "postgres"
  instance_class    = "db.t3.medium"
  allocated_storage = 100
}

resource "aws_instance" "daemon_worker" {
  count         = 3  # Scale to N workers
  ami           = "ami-xxxxxxxxx"
  instance_type = "t3.large"
  
  user_data = <<-EOF
    #!/bin/bash
    docker run -d \
      -e DATABASE_URL=${aws_db_instance.postgres.endpoint} \
      -e ASSIGNED_PROFILE_IDS="..." \
      ghcr.io/openoutreach:latest \
      python manage.py rundaemon
  EOF
}

resource "aws_lb" "api" {
  name               = "openoutreach-api-lb"
  load_balancer_type = "application"
  subnets            = [aws_subnet.public.*.id]
}
```

### 3.4 Auto-Scaling Strategy

**Metrics to monitor:**
- Active LinkedIn profiles / daemon instances
- Task queue depth per profile
- CPU/memory per instance

**Scaling rules:**
- 1 daemon instance per 20-30 accounts (conservative)
- 1 API instance per 100-200 concurrent users
- Postgres RDS: scale vertically as needed (db.t3.medium → db.t3.large)

---

## Phase 4: Multi-Tenant SaaS Features

### 4.1 User Signup & Onboarding Flow

```
User Journey:
1. Sign up (email + password)
2. Email verification
3. Add LinkedIn credentials
4. Create first campaign
5. Daemon picks up and starts processing
```

**Self-Service Onboarding:**
```python
# Remove interactive wizard for new users
# Auto-provision defaults:
- SiteConfig per user (or inherit from global defaults)
- First LinkedInProfile created on credential add
- Default campaign template available
```

### 4.2 Billing & Usage Limits

**Quotas per plan tier:**
```python
class PlanTier(models.TextChoices):
    FREE = 'free'      # 1 LinkedIn account, 50 connections/mo
    PRO = 'pro'        # 3 accounts, 500 connections/mo
    BUSINESS = 'biz'   # 10 accounts, 2000 connections/mo
    ENTERPRISE = 'ent' # Unlimited

class User(AbstractUser):
    plan_tier = models.CharField(choices=PlanTier.choices, default=PlanTier.FREE)
    linkedin_account_limit = models.IntegerField(default=1)
    monthly_connection_limit = models.IntegerField(default=50)
    connections_sent_this_month = models.IntegerField(default=0)
```

**Enforce limits in daemon:**
```python
# Before creating connect task
if user.connections_sent_this_month >= user.monthly_connection_limit:
    logger.warning(f"User {user.id} hit monthly limit")
    return  # Skip task creation
```

**Stripe Integration:**
```python
# requirements/base.txt
stripe

# Webhook handler for subscription events
@api_view(['POST'])
def stripe_webhook(request):
    event = stripe.Webhook.construct_event(...)
    
    if event.type == 'customer.subscription.updated':
        # Update user plan_tier
        user.plan_tier = map_stripe_plan_to_tier(event.data)
        user.save()
```

### 4.3 Admin Dashboard (Super User)

**Multi-tenant admin needs:**
- View all users and their usage
- Suspend/activate users
- View system-wide metrics
- Manually adjust quotas

```python
# openoutreach/admin.py
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['email', 'plan_tier', 'linkedin_profiles_count', 'is_active']
    actions = ['suspend_users', 'reset_monthly_limits']
    
    def linkedin_profiles_count(self, obj):
        return obj.linkedin_profiles.count()
```

---

## Security & Isolation Checklist

### Data Isolation
- [ ] All querysets filtered by `request.user`
- [ ] User cannot access another user's campaigns/leads/deals
- [ ] API tests validate cross-user access is blocked
- [ ] Django Admin respects user ownership

### Browser Isolation
- [ ] Each LinkedIn profile has dedicated browser context
- [ ] Cookies stored per profile (encrypted)
- [ ] Proxy assigned per profile (if used)
- [ ] Browser crashes don't affect other accounts

### Task Queue Isolation
- [ ] Tasks cannot be claimed by wrong profile
- [ ] Distributed locks prevent double-processing
- [ ] Failed tasks don't block other accounts

### Rate Limiting Isolation
- [ ] LinkedIn rate limits tracked per profile (not global)
- [ ] One account's ban doesn't affect others
- [ ] Active hours configured per profile or inherited from user

---

## Migration Checklist: Single → Multi-Tenant

### Phase 1: Foundation
- [ ] Add User model and authentication
- [ ] Migrate existing data to default user
- [ ] Add `user` foreign key to all models
- [ ] Update all API views to filter by user
- [ ] Add frontend login/signup
- [ ] Test: Create second user, verify data isolation

### Phase 2: Multi-Account
- [ ] Refactor daemon to support multiple sessions
- [ ] Add `linkedin_profile` to Task model
- [ ] Implement `AccountSessionManager`
- [ ] Add proxy support to browser launch
- [ ] Test: Run 3 accounts concurrently on same instance

### Phase 3: Scaling
- [ ] Migrate to RDS Postgres (if using SQLite)
- [ ] Implement distributed task locking (Redis or DB-level)
- [ ] Deploy multiple daemon workers
- [ ] Set up load balancer for API
- [ ] Test: 20+ accounts across 2 instances

### Phase 4: SaaS
- [ ] Add plan tiers and usage limits
- [ ] Implement Stripe billing
- [ ] Add usage tracking and enforcement
- [ ] Build admin dashboard
- [ ] Test: User hits limit, upgrade flow

---

## Cost Estimation (100 Users)

**AWS Infrastructure:**
- RDS Postgres (db.t3.large): ~$150/mo
- 3x EC2 daemon workers (t3.large): ~$225/mo
- 1x EC2 API/frontend (t3.medium): ~$60/mo
- Load balancer: ~$25/mo
- **Total infrastructure: ~$460/mo**

**Proxies (if 50% of users use 3+ accounts):**
- 50 users × 3 accounts × $1.50/account = ~$225/mo

**LLM Costs (with research workflows):**
- 100 users × 50 connections/mo × 100k tokens = 500M tokens/mo
- Claude Sonnet: 500M × $3/1M = ~$1,500/mo
- (Cost scales with usage - can optimize with cheaper models for some tasks)

**Total monthly cost for 100 active users: ~$2,200/mo**
**Revenue target (pro rata): $50/user/mo = $5,000/mo → 56% margin**

---

## Next Steps

1. **Immediate (Phase 1):**
   - Add User model and authentication
   - Scope all API views to current user
   - Test with 2-3 users manually

2. **Short-term (Phase 2):**
   - Refactor daemon for multi-account
   - Add proxy support
   - Deploy and test with 5-10 accounts

3. **Medium-term (Phase 3):**
   - Migrate to RDS
   - Deploy multiple workers
   - Set up monitoring and auto-scaling

4. **Long-term (Phase 4):**
   - Add billing and plan tiers
   - Build marketing site
   - Launch beta program

---

## Questions & Decisions Needed

1. **Billing model:** Flat monthly fee vs usage-based (per connection)?
2. **Self-serve vs approval:** Can anyone sign up or require manual approval?
3. **Proxy strategy:** Include in pricing or let users BYO proxy?
4. **Data retention:** How long to keep leads/messages after user churns?
5. **LinkedIn account policy:** Allow users to share accounts (team mode) or strictly 1:1?

---

This is the blueprint. Let me know which phase you want to start implementing first!
