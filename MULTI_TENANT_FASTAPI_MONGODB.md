# Multi-Tenant & Multi-Session Architecture for FastAPI + MongoDB

**Context:** This plan assumes you've completed the FastAPI + MongoDB migration from `FASTAPI_MONGODB_MIGRATION.md`.

**Goal:** Enable multiple users, each with multiple LinkedIn profiles, running campaigns concurrently — with proper data isolation, team access, real-time notifications per-user, and per-profile rate limiting.

**Timeline:** 2-3 weeks (much simpler than Django version because MongoDB already has `user_id` fields)

---

## Current State (After FastAPI Migration)

✅ **Already Have:**
- MongoDB models with `user_id` fields
- Task model with `linkedin_profile_id` field
- FastAPI with JWT authentication (Supabase + local)
- Pydantic models for API schemas
- MongoDB connection to Atlas
- WebSocket + SSE for real-time notifications
- Notification model with `recipient_id`
- SmartRateLimitContext per LinkedInProfile
- Daemon with session pool

❌ **Still Missing:**
- User registration/login endpoints (local, non-Supabase)
- Proper team/org model (Campaign.users M2M equivalent)
- Multi-profile enforcement in all API endpoints
- Per-profile rate limit context creation on profile add
- Notification routing to multiple team members
- Frontend user/profile switcher UI
- Data isolation integration tests

---

## Architecture Overview

### Data Model (MongoDB)

```
User
  ├── email, hashed_password (local auth)
  ├── supabase_user_id (optional, for Supabase auth)
  ├── org_id (optional, for future team/org support)
  │
  ├── LinkedInProfile (1:N via user_id)
  │   ├── linkedin_username
  │   ├── cookie_data_encrypted (Fernet AES-256)
  │   ├── active: bool
  │   ├── connect_daily_limit, follow_up_daily_limit
  │   └── SmartRateLimitContext (1:1 via linkedin_profile_id)
  │       ├── detectability_score
  │       ├── time/day multipliers
  │       └── campaign_context: {}
  │
  ├── Campaign (1:N via user_id as owner)
  │   ├── user_id: str (owner)
  │   ├── linkedin_profile_id: str (executor)
  │   ├── team_member_ids: [str] (additional users with access)
  │   └── status: active|paused|draft
  │
  ├── SiteConfig (1:1 via user_id — per-user settings)
  │   ├── LLM provider + key
  │   ├── Rate limit settings
  │   └── Active hours config
  │
  └── Notification (N via recipient_id)
      ├── notification_type (7 types)
      ├── is_read, read_at
      └── campaign_id, deal_id (optional refs)

Task
  ├── user_id: str (owner)
  ├── linkedin_profile_id: str (executor)
  └── payload: {campaign_id, deal_id, ...}

Deal
  ├── user_id: str (owner)
  ├── campaign_id: str
  ├── lead_id: str
  └── mailbox_id: str (optional, for email channel)
```

**Key Insight:** MongoDB's `user_id` field in every document gives natural multi-tenancy — just filter by `user_id`!

---

## Phase 1: User Authentication & Model (Week 1)

### 1.1 User Model in MongoDB

**Action:** Add User model to `openoutreach/mongodb/models.py`

```python
class User:
    """MongoDB User model — supports both local auth and Supabase."""
    
    def __init__(
        self,
        _id: Optional[str] = None,
        email: str = "",
        hashed_password: str = "",
        full_name: str = "",
        is_active: bool = True,
        is_superuser: bool = False,
        supabase_user_id: Optional[str] = None,
        org_id: Optional[str] = None,  # Future: team/org support
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.email = email
        self.hashed_password = hashed_password
        self.full_name = full_name
        self.is_active = is_active
        self.is_superuser = is_superuser
        self.supabase_user_id = supabase_user_id
        self.org_id = org_id
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "_id": self._id,
            "email": self.email,
            "hashed_password": self.hashed_password,
            "full_name": self.full_name,
            "is_active": self.is_active,
            "is_superuser": self.is_superuser,
            "supabase_user_id": self.supabase_user_id,
            "org_id": self.org_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "User":
        return cls(
            _id=str(data.get("_id")),
            email=data.get("email", ""),
            hashed_password=data.get("hashed_password", ""),
            full_name=data.get("full_name", ""),
            is_active=data.get("is_active", True),
            is_superuser=data.get("is_superuser", False),
            supabase_user_id=data.get("supabase_user_id"),
            org_id=data.get("org_id"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )
    
    def save(self) -> str:
        collection = get_mongodb_collection("users")
        if not collection:
            raise RuntimeError("MongoDB collection 'users' not available")
        self.updated_at = datetime.utcnow()
        doc = self.to_dict()
        collection.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
        return self._id
    
    @classmethod
    def get_by_email(cls, email: str) -> Optional["User"]:
        collection = get_mongodb_collection("users")
        if not collection:
            return None
        data = collection.find_one({"email": email})
        return cls.from_dict(data) if data else None
    
    @classmethod
    def get(cls, user_id: str) -> Optional["User"]:
        collection = get_mongodb_collection("users")
        if not collection:
            return None
        data = collection.find_one({"_id": user_id})
        return cls.from_dict(data) if data else None
    
    @classmethod
    def get_by_supabase_id(cls, supabase_id: str) -> Optional["User"]:
        collection = get_mongodb_collection("users")
        if not collection:
            return None
        data = collection.find_one({"supabase_user_id": supabase_id})
        return cls.from_dict(data) if data else None
    
    def verify_password(self, password: str) -> bool:
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        return pwd_context.verify(password, self.hashed_password)
    
    @staticmethod
    def hash_password(password: str) -> str:
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        return pwd_context.hash(password)
```

**Indexes:**
```python
mongodb_connection.ensure_indexes('users', [
    ({'email': 1}, {'name': 'user_email_idx', 'unique': True}),
    ({'supabase_user_id': 1}, {'name': 'user_supabase_idx', 'sparse': True}),
    ({'org_id': 1}, {'name': 'user_org_idx', 'sparse': True}),
])
```

### 1.2 Campaign Team Access (Replaces Django M2M)

The Django `Campaign.users` M2M allowed multiple users to access one campaign. In MongoDB, we implement this with a `team_member_ids` array:

```python
class Campaign:
    def __init__(
        self,
        # ... existing fields ...
        user_id: str = "",               # Campaign owner
        linkedin_profile_id: Optional[str] = None,  # Which profile executes
        team_member_ids: Optional[List[str]] = None,  # Additional users with access
    ):
        self.user_id = user_id
        self.linkedin_profile_id = linkedin_profile_id
        self.team_member_ids = team_member_ids or []
    
    def has_access(self, user_id: str) -> bool:
        """Check if a user has access (owner OR team member)."""
        return user_id == self.user_id or user_id in self.team_member_ids
    
    def get_all_user_ids(self) -> List[str]:
        """Get all users with access (owner + team members)."""
        return [self.user_id] + self.team_member_ids
```

**Authorization helper:**

```python
# openoutreach/api_v2/dependencies.py

async def get_campaign_with_access(
    campaign_id: str,
    user_id: str = Depends(get_current_user),
) -> models.Campaign:
    """Verify user has access to campaign (owner OR team member)."""
    campaign = models.Campaign.get(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if not campaign.has_access(user_id):
        raise HTTPException(status_code=403, detail="Access denied")
    return campaign
```

### 1.3 Auth Endpoints (FastAPI)

```python
# openoutreach/api_v2/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from jose import jwt

from openoutreach.mongodb import models
from openoutreach.settings import settings

router = APIRouter()

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int = 604800  # 7 days

class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    is_active: bool
    created_at: datetime

@router.post("/register", response_model=UserResponse, status_code=201)
async def register_user(user_data: UserRegister):
    """Register a new user. Public endpoint."""
    existing = models.User.get_by_email(user_data.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user = models.User(
        email=user_data.email,
        hashed_password=models.User.hash_password(user_data.password),
        full_name=user_data.full_name,
    )
    user.save()
    
    # Create default SiteConfig for user
    models.SiteConfig(user_id=user._id).save()
    
    return UserResponse(id=user._id, email=user.email, full_name=user.full_name,
                       is_active=user.is_active, created_at=user.created_at)

@router.post("/login", response_model=Token)
async def login(credentials: UserLogin):
    """Login and get JWT token. Public endpoint."""
    user = models.User.get_by_email(credentials.email)
    if not user or not user.verify_password(credentials.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")
    
    # Create access token
    expires = timedelta(days=7)
    payload = {
        "sub": user._id,
        "email": user.email,
        "exp": datetime.utcnow() + expires,
    }
    access_token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    
    return Token(access_token=access_token, expires_in=int(expires.total_seconds()))

@router.get("/me", response_model=UserResponse)
async def get_me(user_id: str = Depends(get_current_user)):
    """Get current user info. Authenticated."""
    user = models.User.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(id=user._id, email=user.email, full_name=user.full_name,
                       is_active=user.is_active, created_at=user.created_at)

@router.post("/refresh", response_model=Token)
async def refresh_token(user_id: str = Depends(get_current_user)):
    """Refresh JWT token. Authenticated."""
    user = models.User.get(user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    expires = timedelta(days=7)
    payload = {"sub": user._id, "email": user.email, "exp": datetime.utcnow() + expires}
    access_token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return Token(access_token=access_token, expires_in=int(expires.total_seconds()))
```

### 1.4 Frontend Auth Integration

```typescript
// frontend/src/lib/auth.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface AuthState {
  token: string | null;
  user: { id: string; email: string; full_name: string } | null;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName: string) => Promise<void>;
  logout: () => void;
  getHeaders: () => Record<string, string>;
}

export const useAuth = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      
      login: async (email, password) => {
        const res = await fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password }),
        });
        if (!res.ok) throw new Error('Login failed');
        const { access_token } = await res.json();
        set({ token: access_token });
        
        // Fetch user info
        const userRes = await fetch('/api/auth/me', {
          headers: { 'Authorization': `Bearer ${access_token}` },
        });
        if (userRes.ok) {
          set({ user: await userRes.json() });
        }
      },
      
      register: async (email, password, fullName) => {
        const res = await fetch('/api/auth/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password, full_name: fullName }),
        });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Registration failed');
        }
        // Auto-login after registration
        await get().login(email, password);
      },
      
      logout: () => {
        set({ token: null, user: null });
        window.location.href = '/login';
      },
      
      getHeaders: () => {
        const token = get().token;
        return token ? { 'Authorization': `Bearer ${token}` } : {};
      },
    }),
    { name: 'auth-storage' }
  )
);
```

```typescript
// frontend/src/app/(auth)/login/page.tsx
'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    try {
      await login(email, password);
      router.push('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Invalid credentials');
    }
  };
  
  return (
    <div className="flex min-h-screen items-center justify-center">
      <form onSubmit={handleSubmit} className="w-full max-w-md space-y-4 p-8">
        <h1 className="text-2xl font-bold">Login to OpenOutreach</h1>
        {error && <div className="bg-red-100 text-red-700 p-3 rounded">{error}</div>}
        <input type="email" placeholder="Email" value={email}
               onChange={(e) => setEmail(e.target.value)}
               className="w-full px-4 py-2 border rounded" required />
        <input type="password" placeholder="Password" value={password}
               onChange={(e) => setPassword(e.target.value)}
               className="w-full px-4 py-2 border rounded" required />
        <button type="submit" className="w-full bg-blue-600 text-white py-2 rounded hover:bg-blue-700">
          Login
        </button>
        <p className="text-center text-sm">
          Don't have an account? <a href="/register" className="text-blue-600">Register</a>
        </p>
      </form>
    </div>
  );
}
```

---

## Phase 2: Multi-Profile Support (Week 2)

### 2.1 LinkedInProfile → User Relationship

**Already done!** Your MongoDB `LinkedInProfile` model already has `user_id` field.

**What needs enforcement:**

```python
# openoutreach/api_v2/routers/linkedin_profiles.py
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from openoutreach.mongodb import models
from openoutreach.api_v2.dependencies import get_current_user
from openoutreach.crypto import encrypt_text

router = APIRouter()

class LinkedInProfileCreate(BaseModel):
    linkedin_username: str
    linkedin_password: str  # Will be encrypted before storage

class LinkedInProfileResponse(BaseModel):
    id: str
    linkedin_username: str
    active: bool
    connect_daily_limit: int
    follow_up_daily_limit: int
    has_cookies: bool
    created_at: Optional[datetime] = None

@router.get("/", response_model=List[LinkedInProfileResponse])
async def list_profiles(user_id: str = Depends(get_current_user)):
    """List user's LinkedIn profiles. Returns only user's own profiles."""
    collection = get_mongodb_collection("linkedin_profiles")
    profiles = list(collection.find({"user_id": user_id}))
    return [
        LinkedInProfileResponse(
            id=str(p["_id"]),
            linkedin_username=p.get("linkedin_username", ""),
            active=p.get("active", True),
            connect_daily_limit=p.get("connect_daily_limit", 20),
            follow_up_daily_limit=p.get("follow_up_daily_limit", 25),
            has_cookies=bool(p.get("cookie_data_encrypted")),
            created_at=p.get("created_at"),
        )
        for p in profiles
    ]

@router.post("/", response_model=LinkedInProfileResponse, status_code=201)
async def create_profile(
    data: LinkedInProfileCreate,
    user_id: str = Depends(get_current_user),
):
    """Add a new LinkedIn profile for the current user."""
    # Check duplicate
    collection = get_mongodb_collection("linkedin_profiles")
    existing = collection.find_one({"user_id": user_id, "linkedin_username": data.linkedin_username})
    if existing:
        raise HTTPException(status_code=400, detail="Profile already exists")
    
    profile = models.LinkedInProfile(
        user_id=user_id,
        linkedin_username=data.linkedin_username,
        linkedin_password=encrypt_text(data.linkedin_password),
        active=True,
    )
    profile.save()
    
    # Create SmartRateLimitContext for this profile
    rate_ctx = models.SmartRateLimitContext(linkedin_profile_id=profile._id)
    rate_ctx.save()
    
    return LinkedInProfileResponse(
        id=profile._id,
        linkedin_username=profile.linkedin_username,
        active=profile.active,
        connect_daily_limit=profile.connect_daily_limit,
        follow_up_daily_limit=profile.follow_up_daily_limit,
        has_cookies=False,
    )

@router.post("/{profile_id}/cookies/")
async def upload_cookies(
    profile_id: str,
    cookies: dict,  # JSON body with cookie data
    user_id: str = Depends(get_current_user),
):
    """Upload/update cookies for a LinkedIn profile."""
    profile = models.LinkedInProfile.get(profile_id)
    if not profile or profile.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Encrypt and store cookies
    import json
    profile.cookie_data_encrypted = encrypt_text(json.dumps(cookies))
    profile.save()
    
    return {"status": "ok", "message": "Cookies updated"}

@router.delete("/{profile_id}", status_code=204)
async def delete_profile(profile_id: str, user_id: str = Depends(get_current_user)):
    """Delete a LinkedIn profile (owner only)."""
    profile = models.LinkedInProfile.get(profile_id)
    if not profile or profile.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Check if any active campaigns use this profile
    active_campaigns = get_mongodb_collection("campaigns").count_documents({
        "linkedin_profile_id": profile_id,
        "status": {"$ne": "draft"},
    })
    if active_campaigns > 0:
        raise HTTPException(status_code=400, detail="Cannot delete profile with active campaigns")
    
    # Delete rate limit context
    get_mongodb_collection("smart_rate_limit_contexts").delete_one({"linkedin_profile_id": profile_id})
    # Delete profile
    get_mongodb_collection("linkedin_profiles").delete_one({"_id": profile_id})
    return None
```

### 2.2 Campaign → LinkedInProfile Assignment

**Update Campaign creation to require profile selection:**

```python
# openoutreach/api_v2/routers/campaigns.py
class CampaignCreate(BaseModel):
    name: str
    product_pitch: str
    campaign_objective: str
    linkedin_profile_id: str  # Required: which profile executes
    booking_link: Optional[str] = None
    velocity: int = 20
    team_member_ids: Optional[List[str]] = None  # Optional: share with team

@router.post("/", response_model=CampaignResponse, status_code=201)
async def create_campaign(
    data: CampaignCreate,
    user_id: str = Depends(get_current_user),
):
    """Create a new campaign. User must own the specified LinkedIn profile."""
    # Verify user owns the LinkedIn profile
    profile = models.LinkedInProfile.get(data.linkedin_profile_id)
    if not profile or profile.user_id != user_id:
        raise HTTPException(status_code=403, detail="LinkedIn profile not found or access denied")
    
    # Verify team members exist (if provided)
    team_ids = data.team_member_ids or []
    for tid in team_ids:
        if not models.User.get(tid):
            raise HTTPException(status_code=400, detail=f"Team member {tid} not found")
    
    campaign = models.Campaign(
        name=data.name,
        product_pitch=data.product_pitch,
        campaign_objective=data.campaign_objective,
        linkedin_profile_id=data.linkedin_profile_id,
        booking_link=data.booking_link or "",
        velocity=data.velocity,
        user_id=user_id,
        team_member_ids=team_ids,
    )
    campaign.save()
    
    return CampaignResponse(...)
```

### 2.3 Per-Profile Rate Limiting

The `SmartRateLimitContext` is created per-profile and used by the daemon to enforce limits:

```python
# openoutreach/daemon/rate_limiter.py
"""Rate limiter — checks SmartRateLimitContext before executing tasks."""

from openoutreach.mongodb import models
from openoutreach.mongodb.connection import get_mongodb_collection
from datetime import datetime

class ProfileRateLimiter:
    """Checks if a profile can execute an action based on rate limits."""
    
    @staticmethod
    def can_execute(linkedin_profile_id: str, action_type: str, campaign=None) -> bool:
        """Check if the profile is allowed to execute this action."""
        # Get SmartRateLimitContext
        ctx = models.SmartRateLimitContext.get_by_profile(linkedin_profile_id)
        if not ctx:
            return True  # No context = no limits
        
        # Get effective limit
        effective_limit = ctx.get_effective_limit(action_type, campaign)
        
        # Count actions today
        from openoutreach.mongodb.dal import ActionLogDAL
        daily_count = ActionLogDAL.get_daily_count(linkedin_profile_id, action_type)
        
        return daily_count < effective_limit
    
    @staticmethod
    def record_action(linkedin_profile_id: str, action_type: str):
        """Record action and update rate limit context."""
        ctx = models.SmartRateLimitContext.get_by_profile(linkedin_profile_id)
        if ctx:
            ctx.record_action(action_type)
    
    @staticmethod
    def check_and_warn(linkedin_profile_id: str, action_type: str) -> bool:
        """Check limits and create warning if approaching threshold."""
        ctx = models.SmartRateLimitContext.get_by_profile(linkedin_profile_id)
        if not ctx:
            return False
        
        from openoutreach.mongodb.dal import ActionLogDAL
        daily_count = ActionLogDAL.get_daily_count(linkedin_profile_id, action_type)
        effective_limit = ctx.get_effective_limit(action_type)
        
        # Warn at 80% of limit
        if daily_count >= effective_limit * 0.8:
            warning = models.RateLimitWarning(
                linkedin_profile_id=linkedin_profile_id,
                action_type=action_type,
                limit_type="daily",
                limit_exceeded=effective_limit,
                actual_count=daily_count,
                warning_level="medium" if daily_count < effective_limit else "high",
            )
            warning.save()
            return True
        return False
```

### 2.4 Notification Routing to Team Members

When a campaign event occurs, notifications must go to the owner AND all team members:

```python
# openoutreach/api_v2/services/notifications.py (updated)
class NotificationService:
    @staticmethod
    async def notify_campaign_users(campaign: models.Campaign, notification_type: str,
                                     title: str, message: str, **kwargs):
        """
        Send notification to ALL users with campaign access (owner + team).
        Replaces Django's campaign.users.all() pattern.
        """
        from openoutreach.api_v2.routers.websocket import emit_notification_to_user
        
        recipient_ids = campaign.get_all_user_ids()
        
        for recipient_id in recipient_ids:
            notification = models.Notification(
                recipient_id=recipient_id,
                notification_type=notification_type,
                title=title,
                message=message,
                campaign_id=campaign._id,
                **kwargs,
            )
            notification.save()
            
            # Real-time delivery via WebSocket
            await emit_notification_to_user(recipient_id, {
                "notification_id": notification._id,
                "notification_type": notification_type,
                "title": title,
                "message": message,
            })
    
    @staticmethod
    async def on_campaign_status_change(campaign: models.Campaign, status_change: str):
        """Notify all campaign users of status change."""
        type_map = {
            "started": models.Notification.TYPE_CAMPAIGN_STARTED,
            "paused": models.Notification.TYPE_CAMPAIGN_PAUSED,
            "completed": models.Notification.TYPE_CAMPAIGN_COMPLETED,
        }
        notification_type = type_map.get(status_change)
        if not notification_type:
            return
        
        await NotificationService.notify_campaign_users(
            campaign=campaign,
            notification_type=notification_type,
            title=f"Campaign '{campaign.name}' {status_change}",
            message=f"Campaign '{campaign.name}' has been {status_change}.",
        )
        
        from openoutreach.api_v2.routers.websocket import emit_campaign_status_update
        await emit_campaign_status_update(campaign._id, status_change)
    
    @staticmethod
    async def on_new_message(chat_message: models.ChatMessage, campaign: models.Campaign):
        """Notify all campaign users of new inbound message."""
        if chat_message.is_outgoing:
            return
        
        await NotificationService.notify_campaign_users(
            campaign=campaign,
            notification_type=models.Notification.TYPE_NEW_MESSAGE,
            title=f"New message in '{campaign.name}'",
            message=chat_message.content[:100],
            deal_id=chat_message.deal_id,
            data={"message_id": chat_message._id},
        )
    
    @staticmethod
    async def on_rate_limit_warning(campaign: models.Campaign, profile_username: str,
                                     warning_message: str):
        """Notify campaign users of rate limit warning."""
        await NotificationService.notify_campaign_users(
            campaign=campaign,
            notification_type=models.Notification.TYPE_RATE_LIMIT_WARNING,
            title=f"Rate limit warning for {profile_username}",
            message=f"Rate limit in '{campaign.name}': {warning_message}",
        )
    
    @staticmethod
    async def on_action_error(action_log: models.ActionLog):
        """Notify campaign users of action error."""
        if not action_log.error_message:
            return
        campaign = models.Campaign.get(action_log.campaign_id)
        if not campaign:
            return
        
        await NotificationService.notify_campaign_users(
            campaign=campaign,
            notification_type=models.Notification.TYPE_CAMPAIGN_ERROR,
            title=f"Error in '{campaign.name}'",
            message=action_log.error_message[:200],
        )
        
        from openoutreach.api_v2.routers.websocket import emit_campaign_error
        await emit_campaign_error(campaign._id, action_log.error_message)
```

### 2.5 Daemon Multi-Profile Support

**Already implemented by design!** The daemon design from Phase 3 of the migration doc supports multiple profiles:

```python
# openoutreach/daemon/main.py
class Daemon:
    def __init__(self):
        self.session_pool: dict[str, AccountSession] = {}  # profile_id -> session
    
    async def run(self):
        while self.running:
            # Claim next task for ANY profile (round-robin across all users' profiles)
            task = TaskDAL.claim_next_task()
            
            if task:
                profile_id = task.linkedin_profile_id
                
                # Check rate limits BEFORE execution
                if not ProfileRateLimiter.can_execute(profile_id, task.task_type):
                    # Reschedule task for later
                    TaskDAL.reschedule_task(task._id, minutes=30)
                    continue
                
                # Get or create session for this profile
                session = await self.get_session(profile_id)
                
                # Execute task
                await self.execute_task(task, session)
                
                # Record action for rate limiting
                ProfileRateLimiter.record_action(profile_id, task.task_type)
                
                # Check if approaching limits (emit warning)
                if ProfileRateLimiter.check_and_warn(profile_id, task.task_type):
                    campaign = models.Campaign.get(task.payload.get("campaign_id"))
                    if campaign:
                        profile = models.LinkedInProfile.get(profile_id)
                        await NotificationService.on_rate_limit_warning(
                            campaign, profile.linkedin_username,
                            f"Approaching daily {task.task_type} limit"
                        )
    
    async def get_session(self, profile_id: str) -> AccountSession:
        """Get or create browser session for profile."""
        if profile_id not in self.session_pool:
            profile = models.LinkedInProfile.get(profile_id)
            if not profile:
                raise ValueError(f"Profile {profile_id} not found")
            session = AccountSession(profile)
            await session.authenticate()
            self.session_pool[profile_id] = session
        return self.session_pool[profile_id]
```

### 2.6 Task Creation with Profile Assignment

```python
# openoutreach/daemon/scheduler.py
async def reconcile_campaign(campaign: models.Campaign):
    """Reconcile tasks for one campaign — tasks use campaign's linkedin_profile_id."""
    if not campaign.linkedin_profile_id:
        return  # No profile assigned, skip
    
    qualified_deals = DealDAL.get_qualified_deals(campaign._id, limit=100)
    
    for deal in qualified_deals:
        existing_tasks = TaskDAL.get_pending_tasks_for_deal(deal._id, 'connect')
        if not existing_tasks:
            TaskDAL.create_task(
                task_type='connect',
                linkedin_profile_id=campaign.linkedin_profile_id,  # ← From campaign
                payload={'deal_id': deal._id, 'campaign_id': campaign._id},
                scheduled_at=datetime.utcnow() + timedelta(minutes=5),
                user_id=campaign.user_id,
            )
```

---

## Phase 3: Data Isolation & Security (Week 3)

### 3.1 Enforce User Ownership in All APIs

**Every endpoint must filter by user_id or check access:**

```python
# Pattern for list endpoints:
@router.get("/")
async def list_resource(user_id: str = Depends(get_current_user)):
    collection = get_mongodb_collection("resource")
    # ALWAYS filter by user_id
    items = list(collection.find({"user_id": user_id}))
    return items

# Pattern for detail endpoints:
@router.get("/{resource_id}")
async def get_resource(resource_id: str, user_id: str = Depends(get_current_user)):
    item = collection.find_one({"_id": resource_id})
    if not item:
        raise HTTPException(status_code=404)
    # ALWAYS check ownership
    if item.get("user_id") != user_id:
        raise HTTPException(status_code=403)
    return item

# Pattern for campaign-scoped resources (deals, leads, messages):
@router.get("/campaigns/{campaign_id}/leads")
async def list_campaign_leads(
    campaign_id: str,
    user_id: str = Depends(get_current_user),
):
    # Verify campaign access (owner OR team member)
    campaign = models.Campaign.get(campaign_id)
    if not campaign or not campaign.has_access(user_id):
        raise HTTPException(status_code=403)
    
    # Then query scoped to campaign
    deals = list(get_mongodb_collection("deals").find({"campaign_id": campaign_id}))
    return deals
```

**Complete endpoint access control checklist:**

| Resource | List Filter | Detail Check |
|----------|------------|--------------|
| Campaigns | `user_id == current OR current in team_member_ids` | `campaign.has_access(user_id)` |
| Leads | Via user's campaigns' deals | Via campaign access |
| Deals | `user_id == current` | `deal.user_id == current` |
| Tasks | `user_id == current` | `task.user_id == current` |
| LinkedIn Profiles | `user_id == current` | `profile.user_id == current` |
| LinkedIn Credentials | `user_id == current` | `cred.user_id == current` |
| Notifications | `recipient_id == current` | `notification.recipient_id == current` |
| SiteConfig | `user_id == current` | Singleton per user |
| Messages | Via user's campaigns' deals | Via campaign access |
| TrackedLinks | Via user's campaigns | `link.campaign.has_access()` |
| Notes | Via deal → campaign access | Via campaign access |
| Templates | `created_by_id == current OR is_public` | Owner or public |

### 3.2 MongoDB Indexes for Multi-Tenant Queries

```python
def ensure_multi_tenant_indexes():
    """Indexes optimized for user-scoped queries."""
    
    # Campaigns (team access queries)
    mongodb_connection.ensure_indexes('campaigns', [
        ({'user_id': 1, 'status': 1}, {'name': 'campaign_user_status_idx'}),
        ({'team_member_ids': 1}, {'name': 'campaign_team_idx'}),
        ({'linkedin_profile_id': 1, 'status': 1}, {'name': 'campaign_profile_status_idx'}),
    ])
    
    # Tasks (daemon queries per-profile)
    mongodb_connection.ensure_indexes('tasks', [
        ({'linkedin_profile_id': 1, 'status': 1, 'scheduled_at': 1}, {'name': 'task_profile_queue_idx'}),
        ({'user_id': 1, 'status': 1}, {'name': 'task_user_status_idx'}),
    ])
    
    # Notifications (per-user unread queries)
    mongodb_connection.ensure_indexes('notifications', [
        ({'recipient_id': 1, 'is_read': 1, 'created_at': -1}, {'name': 'notif_user_unread_time_idx'}),
    ])
    
    # Deals (per-user)
    mongodb_connection.ensure_indexes('deals', [
        ({'user_id': 1, 'state': 1}, {'name': 'deal_user_state_idx'}),
    ])
    
    # Action logs (per-profile daily count for rate limiting)
    mongodb_connection.ensure_indexes('action_logs', [
        ({'linkedin_profile_id': 1, 'action_type': 1, 'created_at': -1}, {'name': 'action_profile_type_time_idx'}),
    ])
```

### 3.3 Integration Tests for Data Isolation

```python
# tests/integration/test_multi_tenant.py
import pytest
from fastapi.testclient import TestClient
from openoutreach.api_v2.main import app

client = TestClient(app)

@pytest.fixture
def user1_token():
    """Register and login user1."""
    client.post("/api/auth/register", json={
        "email": "user1@test.com", "password": "pass123", "full_name": "User One"
    })
    res = client.post("/api/auth/login", json={"email": "user1@test.com", "password": "pass123"})
    return res.json()["access_token"]

@pytest.fixture
def user2_token():
    """Register and login user2."""
    client.post("/api/auth/register", json={
        "email": "user2@test.com", "password": "pass123", "full_name": "User Two"
    })
    res = client.post("/api/auth/login", json={"email": "user2@test.com", "password": "pass123"})
    return res.json()["access_token"]

def test_user_cannot_see_other_user_campaigns(user1_token, user2_token):
    """Test campaign isolation between users."""
    # User1 creates a campaign
    res = client.post("/api/campaigns/", json={
        "name": "User1 Campaign", "product_pitch": "test",
        "campaign_objective": "test", "linkedin_profile_id": "profile1"
    }, headers={"Authorization": f"Bearer {user1_token}"})
    assert res.status_code == 201
    
    # User2 should NOT see it
    res = client.get("/api/campaigns/", headers={"Authorization": f"Bearer {user2_token}"})
    assert res.status_code == 200
    campaigns = res.json()["campaigns"]
    assert all(c["name"] != "User1 Campaign" for c in campaigns)

def test_user_cannot_access_other_user_campaign_detail(user1_token, user2_token):
    """Test campaign detail access control."""
    # User1 creates campaign
    res = client.post("/api/campaigns/", json={...},
                     headers={"Authorization": f"Bearer {user1_token}"})
    campaign_id = res.json()["id"]
    
    # User2 cannot access it
    res = client.get(f"/api/campaigns/{campaign_id}",
                    headers={"Authorization": f"Bearer {user2_token}"})
    assert res.status_code == 403

def test_team_member_can_access_shared_campaign(user1_token, user2_token):
    """Test team member access to shared campaign."""
    # Get user2's ID
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {user2_token}"})
    user2_id = res.json()["id"]
    
    # User1 creates campaign with user2 as team member
    res = client.post("/api/campaigns/", json={
        "name": "Shared Campaign", "product_pitch": "test",
        "campaign_objective": "test", "linkedin_profile_id": "profile1",
        "team_member_ids": [user2_id]
    }, headers={"Authorization": f"Bearer {user1_token}"})
    campaign_id = res.json()["id"]
    
    # User2 CAN access it
    res = client.get(f"/api/campaigns/{campaign_id}",
                    headers={"Authorization": f"Bearer {user2_token}"})
    assert res.status_code == 200

def test_notifications_are_isolated(user1_token, user2_token):
    """Test notification isolation."""
    # User1's notifications
    res = client.get("/api/notifications/", headers={"Authorization": f"Bearer {user1_token}"})
    user1_notifs = res.json()
    
    # User2's notifications
    res = client.get("/api/notifications/", headers={"Authorization": f"Bearer {user2_token}"})
    user2_notifs = res.json()
    
    # No overlap in notification IDs
    user1_ids = {n["id"] for n in user1_notifs.get("results", [])}
    user2_ids = {n["id"] for n in user2_notifs.get("results", [])}
    assert user1_ids.isdisjoint(user2_ids)

def test_task_isolation_per_profile():
    """Test that daemon claims tasks per-profile correctly."""
    from openoutreach.mongodb.dal import TaskDAL
    from openoutreach.mongodb import models
    
    # Create tasks for different profiles
    TaskDAL.create_task("connect", "profile_A", {"campaign_id": "c1"},
                       datetime.utcnow(), "user1")
    TaskDAL.create_task("connect", "profile_B", {"campaign_id": "c2"},
                       datetime.utcnow(), "user2")
    
    # Claim for profile_A only gets profile_A tasks
    task = TaskDAL.claim_next_task("profile_A")
    assert task.linkedin_profile_id == "profile_A"
    
    # Claim for profile_B only gets profile_B tasks
    task = TaskDAL.claim_next_task("profile_B")
    assert task.linkedin_profile_id == "profile_B"
```

---

## Phase 4: Frontend Multi-User UI (Week 3)

### 4.1 Profile Switcher Component

```typescript
// frontend/src/components/ProfileSwitcher.tsx
'use client';
import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth';

interface LinkedInProfile {
  id: string;
  linkedin_username: string;
  active: boolean;
  has_cookies: boolean;
}

export function ProfileSwitcher() {
  const { getHeaders } = useAuth();
  const [profiles, setProfiles] = useState<LinkedInProfile[]>([]);
  const [selectedId, setSelectedId] = useState<string>('');
  
  useEffect(() => {
    fetch('/api/linkedin-profiles/', { headers: getHeaders() })
      .then(r => r.json())
      .then(data => {
        setProfiles(data);
        const saved = localStorage.getItem('selected_profile_id');
        if (saved && data.find((p: any) => p.id === saved)) {
          setSelectedId(saved);
        } else if (data.length > 0) {
          setSelectedId(data[0].id);
          localStorage.setItem('selected_profile_id', data[0].id);
        }
      });
  }, []);
  
  if (profiles.length === 0) {
    return (
      <a href="/settings" className="text-yellow-600 text-sm">
        ⚠️ No LinkedIn profiles — Add one in Settings
      </a>
    );
  }
  
  if (profiles.length === 1) {
    return (
      <span className="text-sm text-gray-600">
        Profile: <strong>{profiles[0].linkedin_username}</strong>
        {!profiles[0].has_cookies && <span className="text-yellow-600 ml-1">⚠️ No cookies</span>}
      </span>
    );
  }
  
  return (
    <select
      value={selectedId}
      onChange={(e) => {
        setSelectedId(e.target.value);
        localStorage.setItem('selected_profile_id', e.target.value);
        window.location.reload();
      }}
      className="px-3 py-1 border rounded text-sm"
    >
      {profiles.map(p => (
        <option key={p.id} value={p.id}>
          {p.linkedin_username} {!p.has_cookies ? '⚠️' : ''}
        </option>
      ))}
    </select>
  );
}
```

### 4.2 Campaign Creation with Profile Selection

```typescript
// frontend/src/components/campaigns/CreateCampaignForm.tsx (updated)
'use client';
import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth';

export function CreateCampaignForm() {
  const { getHeaders } = useAuth();
  const [profiles, setProfiles] = useState([]);
  const [selectedProfileId, setSelectedProfileId] = useState('');
  const [name, setName] = useState('');
  const [pitch, setPitch] = useState('');
  const [objective, setObjective] = useState('');
  
  useEffect(() => {
    fetch('/api/linkedin-profiles/', { headers: getHeaders() })
      .then(r => r.json())
      .then(setProfiles);
  }, []);
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const res = await fetch('/api/campaigns/', {
      method: 'POST',
      headers: { ...getHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name,
        product_pitch: pitch,
        campaign_objective: objective,
        linkedin_profile_id: selectedProfileId,
      }),
    });
    if (res.ok) {
      window.location.href = '/campaigns';
    }
  };
  
  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium">LinkedIn Profile *</label>
        <select value={selectedProfileId} onChange={e => setSelectedProfileId(e.target.value)}
                className="w-full border rounded px-3 py-2" required>
          <option value="">Select profile...</option>
          {profiles.map((p: any) => (
            <option key={p.id} value={p.id}>{p.linkedin_username}</option>
          ))}
        </select>
      </div>
      <div>
        <label className="block text-sm font-medium">Campaign Name *</label>
        <input value={name} onChange={e => setName(e.target.value)}
               className="w-full border rounded px-3 py-2" required />
      </div>
      <div>
        <label className="block text-sm font-medium">Product Pitch *</label>
        <textarea value={pitch} onChange={e => setPitch(e.target.value)}
                  className="w-full border rounded px-3 py-2" rows={3} required />
      </div>
      <div>
        <label className="block text-sm font-medium">Campaign Objective *</label>
        <textarea value={objective} onChange={e => setObjective(e.target.value)}
                  className="w-full border rounded px-3 py-2" rows={3} required />
      </div>
      <button type="submit" className="bg-blue-600 text-white px-4 py-2 rounded">
        Create Campaign
      </button>
    </form>
  );
}
```

### 4.3 Protected Routes (Middleware)

```typescript
// frontend/src/middleware.ts
import { NextRequest, NextResponse } from 'next/server';

const PUBLIC_PATHS = ['/login', '/register', '/', '/pricing'];

export function middleware(request: NextRequest) {
  const token = request.cookies.get('auth_token')?.value;
  const { pathname } = request.nextUrl;
  
  // Allow public paths
  if (PUBLIC_PATHS.some(p => pathname === p || pathname.startsWith('/api'))) {
    return NextResponse.next();
  }
  
  // Redirect to login if no token
  if (!token && pathname.startsWith('/dashboard') || pathname.startsWith('/campaigns') ||
      pathname.startsWith('/leads') || pathname.startsWith('/settings')) {
    return NextResponse.redirect(new URL('/login', request.url));
  }
  
  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};
```

### 4.4 User Menu

```typescript
// frontend/src/components/layout/UserMenu.tsx
'use client';
import { useAuth } from '@/lib/auth';

export function UserMenu() {
  const { user, logout } = useAuth();
  
  if (!user) return null;
  
  return (
    <div className="flex items-center gap-3">
      <div className="text-sm">
        <span className="font-medium">{user.full_name}</span>
        <span className="text-gray-500 ml-1">({user.email})</span>
      </div>
      <button onClick={logout} className="text-sm text-red-600 hover:text-red-800">
        Logout
      </button>
    </div>
  );
}
```

---

## Migration Checklist

### Week 1: User Authentication
- [ ] User model in MongoDB (with supabase_user_id support)
- [ ] Auth endpoints (register, login, /me, refresh)
- [ ] JWT token generation/validation
- [ ] Frontend login/register pages (Zustand auth store)
- [ ] Protected routes middleware
- [ ] SiteConfig auto-creation on user register

### Week 2: Multi-Profile + Rate Limiting
- [ ] LinkedInProfile → User relationship enforced in APIs
- [ ] Campaign → LinkedInProfile assignment required
- [ ] Campaign team_member_ids array (replaces Django M2M)
- [ ] SmartRateLimitContext created per-profile
- [ ] Per-profile rate limit checking in daemon
- [ ] Rate limit warning notifications
- [ ] Task creation uses campaign's profile
- [ ] ProfileRateLimiter class

### Week 3: Data Isolation + Frontend
- [ ] All API endpoints filter by user_id
- [ ] Campaign access checks (owner OR team member)
- [ ] Notification routing to team members
- [ ] MongoDB indexes for multi-tenant queries
- [ ] Integration tests for isolation
- [ ] Profile switcher component
- [ ] Campaign creation with profile selection
- [ ] User menu with logout
- [ ] Protected routes

---

## Key Differences from Django Version

### ✅ Much Simpler:
- **No migrations** — MongoDB is schema-less, just add fields
- **No Django ORM refactoring** — Already using MongoDB models
- **No Django signals** — Explicit service-layer calls
- **No RDS/PostgreSQL** — Using MongoDB Atlas
- **No Django Admin** — FastAPI + Next.js UI only
- **M2M → Array field** — `team_member_ids: [str]` instead of join table

### ✅ Better Performance:
- **Indexes on `user_id`** — Fast user-scoped queries
- **Atomic task claiming** — `findOneAndUpdate` prevents race conditions
- **No N+1 queries** — MongoDB flexible queries
- **Connection pooling** — MongoDB driver handles it

### ✅ Proper Rate Limiting:
- **Per-profile SmartRateLimitContext** — Not global
- **Daemon checks before execution** — Not after
- **Warning notifications** — At 80% threshold
- **Automatic backoff** — Reschedule tasks when at limit

---

## Security Considerations

### ✅ Data Isolation
- Every MongoDB document has `user_id`
- All queries filter by `user_id` or check `campaign.has_access()`
- Team access is explicit (array of user IDs)
- No way to access another user's data via API

### ✅ Authentication
- JWT tokens with 7-day expiration
- Bcrypt password hashing (cost factor 12)
- Supabase JWT supported (JWKS verification)
- Token validation on every request

### ✅ Authorization
- Endpoint-level ownership checks
- Campaign team access model
- LinkedIn profile ownership verified before use
- Profile deletion blocked if active campaigns exist

### ✅ Browser Isolation
- Each LinkedIn profile = separate browser session
- Cookies stored encrypted (Fernet AES-256)
- One profile's failure doesn't affect others
- Session pool in daemon (no cross-contamination)

### ✅ Rate Limit Safety
- Per-profile daily limits (not global)
- Smart context-aware multipliers (time, detectability)
- Automatic pause at threshold
- Warning notifications to user

---

## Production Deployment

### Environment Variables

```bash
# .env
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/openoutreach
MONGODB_NAME=openoutreach

JWT_SECRET_KEY=your-256-bit-secret
JWT_ALGORITHM=HS256

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-key

SECRET_KEY=your-django-compatible-secret-for-fernet
COOKIE_ENCRYPTION_KEY=your-base64-fernet-key

REDIS_URL=redis://localhost:6379  # Optional, for multi-process WS

LOG_LEVEL=INFO
BROWSER_HEADLESS=true
```

### Docker Compose

```yaml
version: '3.8'
services:
  api:
    build: .
    command: openoutreach runserver --host 0.0.0.0 --port 8001
    ports: ["8001:8001"]
    env_file: .env
    
  daemon:
    build: .
    command: openoutreach rundaemon
    env_file: .env
    
  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    environment:
      NEXT_PUBLIC_API_URL: http://api:8001/api
  
  redis:  # Optional: for WebSocket pub/sub across processes
    image: redis:7-alpine
    ports: ["6379:6379"]
```

### Cost Estimates

**For 100 users (each with 1-2 LinkedIn profiles):**

| Component | Cost/Month |
|-----------|-----------|
| MongoDB Atlas M10 | $57 |
| EC2 t3.medium (API + Daemon) | $30 |
| Redis (ElastiCache t3.micro) | $15 |
| **Total** | **~$102/month** |

**vs Django + PostgreSQL multi-tenant:** ~$460/month (**78% cheaper**)

---

## Testing Strategy

```bash
# Unit tests — models and DAL
pytest tests/mongodb/ -v

# API tests — all endpoints with auth
pytest tests/api_v2/ -v

# Integration tests — multi-tenant isolation
pytest tests/integration/test_multi_tenant.py -v

# Load test — concurrent users
k6 run tests/load/multi_user.js
```

---

## Summary

**Multi-tenancy with FastAPI + MongoDB is ~80% done after the migration!**

Your MongoDB models already have:
- ✅ `user_id` fields on all documents
- ✅ `linkedin_profile_id` in tasks and campaigns
- ✅ Notification model with `recipient_id`
- ✅ SmartRateLimitContext per profile

You just need to:
1. **Week 1:** Add User auth model + registration/login endpoints + frontend auth
2. **Week 2:** Enforce profile ownership + add team access + wire rate limiting in daemon
3. **Week 3:** Add authorization checks to all endpoints + frontend UI + tests

**Total: 2-3 weeks** vs **6-9 weeks** for Django PostgreSQL approach.
