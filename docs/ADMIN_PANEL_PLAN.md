# Admin Panel — Implementation Plan

Full-stack admin panel for OpenOutreach. Covers user management (view, edit, block, delete, impersonate,
extend trial, force-cancel), LinkedIn account inspection, execution mode visibility (desktop vs. cloud),
running task status, finance metrics, Stripe invoices, audit logs, and platform analytics.

---

## Architecture overview

```
Frontend (Next.js)              Backend (FastAPI)               MongoDB
──────────────────              ─────────────────               ───────
app/(admin)/                    /api/admin/*                    users
  layout.tsx  (guard)             ↑ all require is_admin        linkedin_profiles
  dashboard/                      Depends(get_admin_user)       campaigns
  users/                                                        tasks
    page.tsx   (list)           existing router                 action_logs
    [id]/                         admin.py                      admin_audit_logs
      page.tsx (detail)         new additions in               deals
  finance/                        admin.py (same file)
  audit/
  platform/
```

**Route group**: `(admin)` sits at the same nesting level as `(dashboard)` so it can share the root
providers (auth, billing status) without inheriting the dashboard sidebar. It gets its own layout with
an admin sidebar.

---

## Phase 1 — Backend foundations ✅

> Extend existing models, fix the auth/me gap, add login-IP capture, and flesh out the existing
> admin response schemas so Phase 2 and later phases have solid data contracts.

### 1.1 Extend `GET /api/auth/me` to expose `is_admin` and `admin_role` ✅

**File**: `openoutreach/api_v2/routers/auth.py`

Find the `/me` endpoint response and add `is_admin: bool` and `admin_role: Optional[str]` to it.

**File**: `openoutreach/api_v2/schemas/auth.py`

Add to `UserMeResponse` (or equivalent):
```python
is_admin: bool = False
admin_role: Optional[str] = None
```

**File**: `frontend/src/lib/authStoreV2.ts`

Extend the `User` interface:
```typescript
export interface User {
  id: string
  email: string
  full_name: string
  is_active: boolean
  created_at: string
  status: string
  admin_notes: string | null
  is_admin: boolean          // ADD
  admin_role: string | null  // ADD
}
```

Add a derived selector to the Zustand store:
```typescript
isAdmin: () => get().user?.is_admin === true,
```

### 1.2 Capture login IP on the `User` document ✅

**File**: `openoutreach/mongodb/models_user.py`

Add fields:
```python
last_login_ip: Optional[str] = None
signup_ip: Optional[str] = None
```

**File**: `openoutreach/api_v2/routers/auth.py`

In the login handler, after a successful authentication, extract the client IP from the request and
persist it:
```python
client_ip = (
    request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    or (request.client.host if request.client else None)
)
if client_ip:
    user.last_login_ip = client_ip
user.last_login = datetime.now(timezone.utc)
user.save()
```

Do the same for the signup handler — set `signup_ip`.

### 1.3 Extend `UserDetailResponse` in the admin router ✅

**File**: `openoutreach/api_v2/routers/admin.py`

Replace `UserDetailResponse` with:
```python
class UserDetailResponse(BaseModel):
    id: str
    email: str
    full_name: str
    created_at: str
    updated_at: str
    last_login: Optional[str]
    last_login_ip: Optional[str]      # new
    signup_ip: Optional[str]          # new
    status: str
    plan: str
    subscription_status: str
    billing_period: Optional[str]
    trial_ends_at: Optional[str]
    current_period_end: Optional[str]
    linkedin_account_limit: int
    campaign_limit: Optional[int]
    cloud_profiles: int
    is_admin: bool
    admin_role: Optional[str]
    admin_notes: Optional[str]        # new
    stripe_customer_id: Optional[str] # new (admin-only; never expose to regular users)
    stripe_subscription_id: Optional[str]  # new
    referral_code: Optional[str]      # new
    referrer_id: Optional[str]        # new
    referral_credits_earned: int      # new
    email_verified: bool              # new
    is_deleted: bool                  # new
    deleted_at: Optional[str]         # new
```

Update both `get_user_detail` and `update_user` to populate all new fields.

### 1.4 Extend `LinkedInProfileInfoResponse` in the admin router ✅

**File**: `openoutreach/api_v2/routers/admin.py`

Replace `LinkedInProfileInfoResponse` with:
```python
class LinkedInProfileInfoResponse(BaseModel):
    id: str
    username: Optional[str]
    display_name: Optional[str]
    is_active: bool
    created_at: str
    execution_mode: str               # "desktop" | "cloud"
    daemon_status: str                # "online" | "offline" | "unknown"
    daemon_last_seen: Optional[str]
    daemon_version: Optional[str]
    daemon_platform: Optional[str]    # "win32" | "darwin"
    daemon_browser: Optional[str]     # "chrome" | "edge"
    daemon_ip: Optional[str]          # IP of the desktop daemon process
    last_heartbeat: Optional[str]
    is_logged_in: bool
    requires_verification: bool
    verification_type: Optional[str]
    connect_daily_limit: int
    follow_up_daily_limit: int
    proxy_server: Optional[str]       # redacted for display — show host only, not credentials
```

### 1.5 Add `GET /api/admin/audit-logs` ✅

**File**: `openoutreach/api_v2/routers/admin.py`

```python
@router.get("/audit-logs", dependencies=[Depends(get_admin_user)])
async def list_audit_logs(
    admin_user_id: Optional[str] = Query(None),
    target_user_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    """Paginated admin audit log."""
    collection = get_mongodb_collection("admin_audit_logs")
    if collection is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    query: dict = {}
    if admin_user_id:
        query["admin_user_id"] = admin_user_id
    if target_user_id:
        query["target_user_id"] = target_user_id
    if action:
        query["action"] = action

    total = collection.count_documents(query)
    logs = list(collection.find(query).sort("created_at", -1).skip(skip).limit(limit))

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "logs": [
            {
                "id": str(log.get("_id")),
                "admin_user_id": log.get("admin_user_id"),
                "action": log.get("action"),
                "target_user_id": log.get("target_user_id"),
                "details": log.get("details", {}),
                "created_at": log.get("created_at", "").isoformat()
                    if hasattr(log.get("created_at", ""), "isoformat") else str(log.get("created_at", "")),
            }
            for log in logs
        ],
    }
```

### 1.6 Add `GET /api/admin/users/{user_id}/tasks` ✅

Returns the user's recent task rows (useful to see what is currently running / queued).

```python
@router.get("/users/{user_id}/tasks", dependencies=[Depends(get_admin_user)])
async def get_user_tasks(
    user_id: str,
    status: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    tasks_collection = get_mongodb_collection("tasks")
    if tasks_collection is None:
        return {"tasks": []}

    query: dict = {"user_id": user_id}
    if status:
        query["status"] = status

    tasks_data = list(
        tasks_collection.find(query).sort("scheduled_at", -1).limit(limit)
    )

    return {
        "tasks": [
            {
                "id": str(t.get("_id")),
                "task_type": t.get("task_type"),
                "status": t.get("status"),
                "scheduled_at": t.get("scheduled_at", "").isoformat()
                    if hasattr(t.get("scheduled_at", ""), "isoformat") else str(t.get("scheduled_at", "")),
                "started_at": t.get("started_at", "").isoformat()
                    if hasattr(t.get("started_at", ""), "isoformat") else None,
                "completed_at": t.get("completed_at", "").isoformat()
                    if hasattr(t.get("completed_at", ""), "isoformat") else None,
                "campaign_id": t.get("payload", {}).get("campaign_id"),
                "linkedin_profile_id": t.get("payload", {}).get("linkedin_profile_id")
                    or t.get("linkedin_profile_id"),
                "last_error": t.get("payload", {}).get("last_error"),
            }
            for t in tasks_data
        ]
    }
```

### 1.7 Add `GET /api/admin/users/{user_id}/action-logs` ✅

```python
@router.get("/users/{user_id}/action-logs", dependencies=[Depends(get_admin_user)])
async def get_user_action_logs(
    user_id: str,
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    collection = get_mongodb_collection("action_logs")
    if collection is None:
        return {"logs": []}

    logs = list(
        collection.find({"user_id": user_id}).sort("created_at", -1).limit(limit)
    )

    return {
        "logs": [
            {
                "id": str(log.get("_id")),
                "action_type": log.get("action_type"),
                "campaign_id": log.get("campaign_id"),
                "linkedin_profile_id": log.get("linkedin_profile_id"),
                "status": log.get("status"),
                "error_message": log.get("error_message"),
                "duration_ms": log.get("duration_ms"),
                "created_at": log.get("created_at", "").isoformat()
                    if hasattr(log.get("created_at", ""), "isoformat") else str(log.get("created_at", "")),
            }
            for log in logs
        ]
    }
```

### 1.8 Add `GET /api/admin/platform` ✅

Platform-level health metrics for the admin dashboard.

```python
@router.get("/platform", dependencies=[Depends(get_admin_user)])
async def get_platform_metrics() -> dict:
    """Platform-wide metrics: tasks, active daemons, connection rates."""
    tasks_col = get_mongodb_collection("tasks")
    profiles_col = get_mongodb_collection("linkedin_profiles")
    deals_col = get_mongodb_collection("deals")
    action_logs_col = get_mongodb_collection("action_logs")

    from datetime import datetime, timezone as tz, timedelta
    now = datetime.now(tz.utc)
    last_24h = now - timedelta(hours=24)

    running_tasks = tasks_col.count_documents({"status": "RUNNING"}) if tasks_col else 0
    pending_tasks = tasks_col.count_documents({"status": "PENDING"}) if tasks_col else 0
    failed_tasks_24h = tasks_col.count_documents({
        "status": "FAILED", "completed_at": {"$gte": last_24h}
    }) if tasks_col else 0
    completed_tasks_24h = tasks_col.count_documents({
        "status": "COMPLETED", "completed_at": {"$gte": last_24h}
    }) if tasks_col else 0

    # Daemons: online = last heartbeat within 5 minutes
    five_min_ago = now - timedelta(minutes=5)
    online_daemons = profiles_col.count_documents({
        "last_heartbeat": {"$gte": five_min_ago}
    }) if profiles_col else 0
    desktop_daemons = profiles_col.count_documents({
        "execution_mode": "desktop", "last_heartbeat": {"$gte": five_min_ago}
    }) if profiles_col else 0
    cloud_daemons = profiles_col.count_documents({
        "execution_mode": "cloud", "last_heartbeat": {"$gte": five_min_ago}
    }) if profiles_col else 0

    connects_24h = action_logs_col.count_documents({
        "action_type": "connect", "status": "completed", "created_at": {"$gte": last_24h}
    }) if action_logs_col else 0
    follow_ups_24h = action_logs_col.count_documents({
        "action_type": "follow_up", "status": "completed", "created_at": {"$gte": last_24h}
    }) if action_logs_col else 0

    return {
        "tasks": {
            "running": running_tasks,
            "pending": pending_tasks,
            "failed_24h": failed_tasks_24h,
            "completed_24h": completed_tasks_24h,
        },
        "daemons": {
            "online": online_daemons,
            "desktop": desktop_daemons,
            "cloud": cloud_daemons,
        },
        "activity_24h": {
            "connects": connects_24h,
            "follow_ups": follow_ups_24h,
        },
    }
```

---

## Phase 2 — User management write endpoints ✅

> All mutating operations on users: soft-delete, trial extension, plan/billing override, force
> subscription cancel, impersonation token, email verification override, password reset.
> Every write goes through `AdminSecurityPolicy.log_admin_action`.

### 2.1 `DELETE /api/admin/users/{user_id}` — soft delete ✅

```python
@router.delete("/users/{user_id}", dependencies=[Depends(get_admin_user)])
async def delete_user(
    user_id: str,
    current_admin: str = Depends(get_admin_user),
) -> dict:
    """Soft-delete a user (sets is_deleted=True, schedules data wipe in 30 days)."""
    from openoutreach.billing.admin_security import AdminSecurityPolicy
    from datetime import datetime, timezone as tz, timedelta

    admin_user = User.get(current_admin)
    AdminSecurityPolicy.require_write_permission(admin_user)

    user = User.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_deleted:
        raise HTTPException(status_code=400, detail="User already deleted")

    now = datetime.now(tz.utc)
    user.is_deleted = True
    user.deleted_at = now
    user.deletion_scheduled_at = now + timedelta(days=30)
    user.status = "inactive"
    user.save()

    AdminSecurityPolicy.log_admin_action(
        current_admin, "delete_user", user_id,
        {"scheduled_wipe": user.deletion_scheduled_at.isoformat()}
    )
    return {"ok": True, "deletion_scheduled_at": user.deletion_scheduled_at.isoformat()}
```

### 2.2 `POST /api/admin/users/{user_id}/restore` — undo soft delete ✅

```python
@router.post("/users/{user_id}/restore", dependencies=[Depends(get_admin_user)])
async def restore_user(user_id: str, current_admin: str = Depends(get_admin_user)) -> dict:
    user = User.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_deleted = False
    user.deleted_at = None
    user.deletion_scheduled_at = None
    user.status = "active"
    user.save()
    AdminSecurityPolicy.log_admin_action(current_admin, "restore_user", user_id, {})
    return {"ok": True}
```

### 2.3 `POST /api/admin/users/{user_id}/extend-trial` ✅

```python
class ExtendTrialRequest(BaseModel):
    days: int  # positive integer

@router.post("/users/{user_id}/extend-trial", dependencies=[Depends(get_admin_user)])
async def extend_trial(
    user_id: str,
    body: ExtendTrialRequest,
    current_admin: str = Depends(get_admin_user),
) -> dict:
    from datetime import datetime, timezone as tz, timedelta

    if body.days <= 0 or body.days > 365:
        raise HTTPException(status_code=400, detail="days must be 1–365")

    user = User.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    base = user.trial_ends_at or datetime.now(tz.utc)
    user.trial_ends_at = base + timedelta(days=body.days)
    if user.subscription_status not in ("active",):
        user.subscription_status = "trialing"
    user.save()

    AdminSecurityPolicy.log_admin_action(
        current_admin, "extend_trial", user_id,
        {"days": body.days, "new_trial_ends_at": user.trial_ends_at.isoformat()}
    )
    return {"ok": True, "trial_ends_at": user.trial_ends_at.isoformat()}
```

### 2.4 `POST /api/admin/users/{user_id}/cancel-subscription` ✅

Cancels in Stripe (immediate) and updates local record.

```python
@router.post("/users/{user_id}/cancel-subscription", dependencies=[Depends(get_admin_user)])
async def force_cancel_subscription(
    user_id: str,
    current_admin: str = Depends(get_admin_user),
) -> dict:
    import stripe as _stripe

    user = User.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.stripe_subscription_id:
        raise HTTPException(status_code=400, detail="No active Stripe subscription")

    try:
        _stripe.Subscription.delete(user.stripe_subscription_id)
    except Exception as e:
        logger.error(f"Stripe cancel failed for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Stripe cancellation failed")

    user.subscription_status = "canceled"
    user.stripe_subscription_id = None
    user.save()

    AdminSecurityPolicy.log_admin_action(current_admin, "cancel_subscription", user_id, {})
    return {"ok": True}
```

### 2.5 `POST /api/admin/users/{user_id}/set-plan` ✅

Richer plan change that also sets `billing_period` and optionally overrides limits.

```python
class SetPlanRequest(BaseModel):
    plan: str
    billing_period: Optional[str] = None   # "monthly" | "annual" | "lifetime"
    linkedin_account_limit: Optional[int] = None  # override, None = use plan default
    campaign_limit: Optional[int] = None
    cloud_profiles: Optional[int] = None

@router.post("/users/{user_id}/set-plan", dependencies=[Depends(get_admin_user)])
async def set_user_plan(
    user_id: str,
    body: SetPlanRequest,
    current_admin: str = Depends(get_admin_user),
) -> UserDetailResponse:
    from openoutreach.billing.api_security import BillingAPISecurity

    if not BillingAPISecurity.validate_plan_name(body.plan):
        raise HTTPException(status_code=400, detail="Invalid plan name")
    if body.billing_period and not BillingAPISecurity.validate_billing_period(body.billing_period):
        raise HTTPException(status_code=400, detail="Invalid billing period")

    user = User.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    plan = _get_plan_limits(body.plan)
    user.plan = body.plan
    if body.billing_period:
        user.billing_period = body.billing_period
    user.linkedin_account_limit = body.linkedin_account_limit or plan["max_linkedin_accounts"]
    user.campaign_limit = body.campaign_limit or plan["max_campaigns"]
    if body.cloud_profiles is not None:
        user.cloud_profiles = body.cloud_profiles
    user.save()

    AdminSecurityPolicy.log_admin_action(
        current_admin, "set_plan", user_id,
        {"plan": body.plan, "billing_period": body.billing_period}
    )
    return _build_user_detail_response(user)   # helper that builds UserDetailResponse from a User obj
```

Create `_build_user_detail_response(user: User) -> UserDetailResponse` as a module-level helper to
avoid duplicating the mapping code across endpoints.

### 2.6 `POST /api/admin/users/{user_id}/verify-email` ✅

Force-mark an email as verified (e.g., for support cases).

```python
@router.post("/users/{user_id}/verify-email", dependencies=[Depends(get_admin_user)])
async def force_verify_email(user_id: str, current_admin: str = Depends(get_admin_user)) -> dict:
    user = User.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.email_verified = True
    user.email_verification_token = None
    user.email_verification_expires = None
    user.save()
    AdminSecurityPolicy.log_admin_action(current_admin, "force_verify_email", user_id, {})
    return {"ok": True}
```

### 2.7 `POST /api/admin/users/{user_id}/send-password-reset` ✅

Triggers the existing password-reset email flow on behalf of the user.

```python
@router.post("/users/{user_id}/send-password-reset", dependencies=[Depends(get_admin_user)])
async def send_password_reset(user_id: str, current_admin: str = Depends(get_admin_user)) -> dict:
    """Trigger a password-reset email for the user."""
    user = User.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Reuse the existing password-reset token generation + email send
    from openoutreach.api_v2.routers.auth import _send_password_reset_email  # or equivalent
    await _send_password_reset_email(user)

    AdminSecurityPolicy.log_admin_action(current_admin, "send_password_reset", user_id, {})
    return {"ok": True}
```

If `_send_password_reset_email` is inlined in the auth router rather than extracted, extract it to a
shared helper first.

### 2.8 `POST /api/admin/users/{user_id}/impersonate` ✅

Returns a short-lived JWT for the target user so the admin can log in as them in a new tab.

```python
class ImpersonateResponse(BaseModel):
    access_token: str
    expires_in: int   # seconds

@router.post("/users/{user_id}/impersonate", dependencies=[Depends(get_admin_user)])
async def impersonate_user(
    user_id: str,
    current_admin: str = Depends(get_admin_user),
) -> ImpersonateResponse:
    """Issue a short-lived (15 min) JWT for the target user."""
    from openoutreach.api_v2.routers.auth import create_access_token  # or equivalent
    from datetime import timedelta

    target_user = User.get(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    if target_user.status == "blocked":
        raise HTTPException(status_code=400, detail="Cannot impersonate a blocked user")

    token = create_access_token(
        data={"sub": user_id, "impersonated_by": current_admin},
        expires_delta=timedelta(minutes=15),
    )

    AdminSecurityPolicy.log_admin_action(
        current_admin, "impersonate_user", user_id, {"expires_in": 900}
    )
    return ImpersonateResponse(access_token=token, expires_in=900)
```

The frontend opens the returned token in a new tab via the `lengrowth://` protocol or by setting it
directly in local storage. Show a visible "Impersonation active" banner in the UI (read
`impersonated_by` claim from the JWT).

### 2.9 Register all new endpoints in the API router ✅

**File**: `openoutreach/api_v2/main.py`

Verify that `admin.router` is already included. If not:
```python
from openoutreach.api_v2.routers import admin
app.include_router(admin.router)
```

---

## Phase 3 — Frontend: guard, layout, and dashboard page

### 3.1 Admin route guard

**New file**: `frontend/src/app/(admin)/layout.tsx`

```tsx
"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { useAuthStore } from "@/lib/authStoreV2"
import AdminSidebar from "@/components/admin/admin-sidebar"

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const { user, isInitialized } = useAuthStore()

  useEffect(() => {
    if (!isInitialized) return
    if (!user || !user.is_admin) {
      router.replace("/dashboard")
    }
  }, [user, isInitialized, router])

  if (!isInitialized || !user?.is_admin) return null

  return (
    <div className="flex h-screen bg-background">
      <AdminSidebar />
      <main className="flex-1 overflow-y-auto p-6">{children}</main>
    </div>
  )
}
```

### 3.2 Admin sidebar

**New file**: `frontend/src/components/admin/admin-sidebar.tsx`

Navigation items:
- Dashboard (`/admin`)
- Users (`/admin/users`)
- Finance (`/admin/finance`)
- Audit Log (`/admin/audit`)
- Platform (`/admin/platform`)

Use shadcn `Button` with `variant="ghost"` for nav items. Highlight the active route with
`usePathname()`.

```tsx
import Link from "next/link"
import { usePathname } from "next/navigation"
import { Users, BarChart2, DollarSign, FileText, Server, ShieldCheck } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

const NAV = [
  { href: "/admin", label: "Dashboard", icon: BarChart2 },
  { href: "/admin/users", label: "Users", icon: Users },
  { href: "/admin/finance", label: "Finance", icon: DollarSign },
  { href: "/admin/audit", label: "Audit Log", icon: FileText },
  { href: "/admin/platform", label: "Platform", icon: Server },
]

export default function AdminSidebar() {
  const pathname = usePathname()
  return (
    <aside className="w-56 border-r flex flex-col py-6 gap-1 shrink-0">
      <div className="px-4 mb-4 flex items-center gap-2 text-sm font-semibold text-muted-foreground uppercase tracking-wide">
        <ShieldCheck className="h-4 w-4" />
        Admin
      </div>
      {NAV.map(({ href, label, icon: Icon }) => (
        <Button
          key={href}
          asChild
          variant="ghost"
          className={cn(
            "justify-start gap-2 mx-2",
            (href === "/admin" ? pathname === href : pathname.startsWith(href)) &&
              "bg-accent text-accent-foreground"
          )}
        >
          <Link href={href}>
            <Icon className="h-4 w-4" />
            {label}
          </Link>
        </Button>
      ))}
    </aside>
  )
}
```

### 3.3 Admin API client

**New file**: `frontend/src/lib/api/admin.ts`

Centralizes all admin fetch calls. Uses the same `apiClient` (or `fetchWithAuth`) already used by
the rest of the frontend.

```typescript
import { apiClient } from "@/lib/api/client"  // or whatever the shared fetcher is

export const adminApi = {
  getDashboard: () =>
    apiClient.get<AdminDashboardResponse>("/api/admin/dashboard"),

  getUsers: (params: UsersQueryParams) =>
    apiClient.get<UsersListResponse>("/api/admin/users", { params }),

  getUser: (userId: string) =>
    apiClient.get<UserDetailResponse>(`/api/admin/users/${userId}`),

  updateUser: (userId: string, body: UserUpdateRequest) =>
    apiClient.patch<UserDetailResponse>(`/api/admin/users/${userId}`, body),

  setPlan: (userId: string, body: SetPlanRequest) =>
    apiClient.post(`/api/admin/users/${userId}/set-plan`, body),

  extendTrial: (userId: string, days: number) =>
    apiClient.post(`/api/admin/users/${userId}/extend-trial`, { days }),

  cancelSubscription: (userId: string) =>
    apiClient.post(`/api/admin/users/${userId}/cancel-subscription`),

  deleteUser: (userId: string) =>
    apiClient.delete(`/api/admin/users/${userId}`),

  restoreUser: (userId: string) =>
    apiClient.post(`/api/admin/users/${userId}/restore`),

  verifyEmail: (userId: string) =>
    apiClient.post(`/api/admin/users/${userId}/verify-email`),

  sendPasswordReset: (userId: string) =>
    apiClient.post(`/api/admin/users/${userId}/send-password-reset`),

  impersonate: (userId: string) =>
    apiClient.post<ImpersonateResponse>(`/api/admin/users/${userId}/impersonate`),

  getUserLinkedInProfiles: (userId: string) =>
    apiClient.get(`/api/admin/users/${userId}/linkedin-profiles`),

  getUserCampaigns: (userId: string) =>
    apiClient.get(`/api/admin/users/${userId}/campaigns`),

  getUserTasks: (userId: string, status?: string) =>
    apiClient.get(`/api/admin/users/${userId}/tasks`, { params: { status } }),

  getUserActionLogs: (userId: string) =>
    apiClient.get(`/api/admin/users/${userId}/action-logs`),

  getUserNotes: (userId: string) =>
    apiClient.get<{ notes: string | null }>(`/api/admin/users/${userId}/notes`),

  updateUserNotes: (userId: string, notes: string | null) =>
    apiClient.post(`/api/admin/users/${userId}/notes`, { notes }),

  getFinanceMetrics: () =>
    apiClient.get<FinanceMetricsResponse>("/api/admin/finance"),

  getInvoices: (skip = 0, limit = 50) =>
    apiClient.get("/api/admin/finance/invoices", { params: { skip, limit } }),

  getAuditLogs: (params: AuditLogsParams) =>
    apiClient.get("/api/admin/audit-logs", { params }),

  getPlatformMetrics: () =>
    apiClient.get<PlatformMetricsResponse>("/api/admin/platform"),
}
```

Also define corresponding TypeScript interfaces mirroring the Pydantic response models above.

### 3.4 Admin dashboard page

**New file**: `frontend/src/app/(admin)/admin/page.tsx`

Layout: two rows of stat cards (use shadcn `Card`) followed by a quick-view table of recent users.

**Stat cards — row 1** (user metrics):
- Total users
- Active users
- Blocked users
- New signups today
- Active subscriptions
- Expired trials

**Stat cards — row 2** (finance KPIs, from `/api/admin/finance`):
- MRR
- ARR
- Trial conversion rate
- Churn rate

**Stat cards — row 3** (platform metrics, from `/api/admin/platform`):
- Online daemons (desktop + cloud badge)
- Running tasks
- Pending tasks
- Connects (24h)
- Follow-ups (24h)

Below the cards, a compact table of the 10 most recent users (sorted by `created_at` desc) with
columns: Email, Plan, Status, Signed up, Last login. Each row links to `/admin/users/{id}`.

Use `useEffect` + `useState` for data fetching, or wrap in a `useSWR` hook if already used in the
project. Show shadcn `Skeleton` components while loading.

---

## Phase 4 — Frontend: users list and user detail

### 4.1 Users list page

**New file**: `frontend/src/app/(admin)/admin/users/page.tsx`

#### Filters bar (top of page)
- Text search input (debounced 300 ms) — searches email and full_name
- Plan select: All / Starter / Pro / Business / Agency / Cloud / Lifetime
- Status select: All / Active / Blocked / Inactive
- Subscription status select: All / Active / Trialing / Canceled / None

#### Table columns
| Column | Notes |
|---|---|
| Email + name | Clicking navigates to `/admin/users/{id}` |
| Plan | Badge (color-coded by plan tier) |
| Status | Badge: green=active, red=blocked, gray=inactive |
| Sub. status | trialing, active, canceled, none |
| LinkedIn profiles | count |
| Campaigns | count |
| Signed up | relative date (`2 days ago`) + tooltip with absolute |
| Last login | same |
| Actions | Kebab menu: View, Block/Unblock, Delete |

#### Inline actions (kebab menu)
- **View** → navigate to detail page
- **Block** (if active) / **Unblock** (if blocked) → PATCH `status`; logs via `AdminSecurityPolicy`
- **Delete** → confirmation dialog (shadcn `AlertDialog`) → DELETE endpoint

#### Pagination
Show `skip`/`limit` controls. Page size selector: 20 / 50 / 100.

#### Implementation notes
- Debounce the search input with a `useCallback` + `setTimeout` (or use the pattern already in the
  campaigns page).
- Keep all filter state in `useSearchParams` so URLs are bookmarkable.
- Use shadcn `Table`, `Badge`, `Button`, `Select`, `Input`, `AlertDialog`, `DropdownMenu`.

### 4.2 User detail page

**New file**: `frontend/src/app/(admin)/admin/users/[id]/page.tsx`

Page layout: header row (email, plan badge, status badge, action buttons) followed by shadcn `Tabs`.

#### Header action buttons
- **Block / Unblock** toggle
- **Impersonate** (opens a dialog confirming the action, then opens a new tab)
- **Delete** (AlertDialog)
- **More** dropdown: Restore, Send Password Reset, Force Verify Email

#### Tabs

**Tab 1 — Profile**

Two-column layout: left column = read/edit fields; right column = admin notes.

Editable fields (inline edit on click or via a modal):
- Full name
- Email (display only — email changes require re-verification; note this in the UI)
- Status: active / blocked / inactive (Select)
- Admin role: none / support / finance / superadmin (Select, optional)
- `is_admin` toggle (shadcn `Switch`)
- `email_verified` toggle with "Force verify" button

Read-only fields:
- User ID (copy button)
- Signed up (`created_at`)
- Signup IP
- Last login
- Last login IP
- Referral code
- Referred by (link to referrer user detail page if `referrer_id` set)
- Referral credits earned

Admin notes textarea (auto-saves on blur via POST `/api/admin/users/{id}/notes`).

**Tab 2 — Billing**

Left column — current billing state:
- Plan (Select — all plan names), Billing period (Select — monthly/annual/lifetime)
- Subscription status (badge)
- Trial ends at (datetime display + **Extend Trial** button → dialog to enter days)
- Current period end
- LinkedIn account limit (editable input)
- Campaign limit (editable input)
- Cloud profiles (editable input)
- Stripe customer ID (masked: `cus_****xyz`, copy button)
- Stripe subscription ID (masked)

Actions:
- **Save plan changes** — calls POST `/api/admin/users/{id}/set-plan`
- **Cancel subscription** — AlertDialog → POST `/api/admin/users/{id}/cancel-subscription`
- **Extend trial** → inline dialog: number input (days) → POST `/api/admin/users/{id}/extend-trial`

Right column — Invoice list (from `/api/admin/finance/invoices` filtered by the user's
`stripe_customer_id`). Since the current `/api/admin/finance/invoices` endpoint lists all invoices
(not filtered by user), add a `user_id` query parameter in Phase 2 (the endpoint filters by
matching `customer_email_map`).

Each invoice row: date, amount, status, PDF link.

**Tab 3 — LinkedIn & Execution**

For each `LinkedInProfile` returned by `/api/admin/users/{id}/linkedin-profiles`:

Card per profile showing:
- Username / display name
- Execution mode badge: **Desktop** (blue) / **Cloud** (purple)
- Daemon status badge: **Online** (green, if `last_heartbeat` within 5 min) / **Offline** (gray)
- Daemon IP
- Platform (win32 / darwin) + browser (chrome / edge)
- Daemon version
- Daemon last seen (relative time)
- Login status: **Logged in** (green) / **Logged out** (gray) / **Needs verification** (yellow,
  shows `verification_type`)
- Connect daily limit / Follow-up daily limit
- Proxy server (host only, no credentials)
- Session updated at / Cookies updated at

Active tasks for this profile: fetch from `/api/admin/users/{id}/tasks` and filter by
`linkedin_profile_id`. Show a compact list: task type, status badge, scheduled at, last error.

**Tab 4 — Campaigns**

Table from `/api/admin/users/{id}/campaigns`:
- Name
- Status (active/paused)
- Leads count
- Created at

Each row links to the campaign detail page at `/campaigns/{id}` (the existing user-facing page —
admins can navigate there directly).

**Tab 5 — Activity**

Two sub-sections:

*Recent action logs* (from `/api/admin/users/{id}/action-logs`):
- Table: action type, campaign ID, LinkedIn profile ID, status, duration ms, created at

*Recent tasks* (from `/api/admin/users/{id}/tasks`):
- Table: task type, status, scheduled at, started at, completed at, campaign ID, last error

**Tab 6 — Audit trail**

Audit log entries where `target_user_id = {id}` (from `/api/admin/audit-logs?target_user_id={id}`):
- admin_user_id, action, details (expandable JSON), created at

---

## Phase 5 — Finance, audit log, and platform pages

### 5.1 Finance page

**New file**: `frontend/src/app/(admin)/admin/finance/page.tsx`

**Section 1 — KPI cards**
- MRR (formatted as currency)
- ARR
- Active subscriptions
- Trialing users
- Trial conversion rate (%)
- Churn rate (%)

**Section 2 — Revenue by plan**

A bar chart (use existing Recharts, following the dark-theme fixes in the project). X-axis: plan
names. Y-axis: contribution to MRR. Backend: extend `GET /api/admin/finance` to return a
`revenue_by_plan` array:
```python
revenue_by_plan = []
for plan_name, plan_data in PLANS.items():
    count = users_collection.count_documents({
        "subscription_status": "active", "plan": plan_name
    })
    monthly_revenue = 0.0
    for user_doc in users_collection.find({"subscription_status": "active", "plan": plan_name}):
        user = User.from_dict(user_doc)
        if user.billing_period == "monthly":
            monthly_revenue += plan_data["monthly_price"] / 100.0
        elif user.billing_period == "annual":
            monthly_revenue += (plan_data["annual_price"] / 12) / 100.0
    revenue_by_plan.append({"plan": plan_name, "count": count, "mrr": monthly_revenue})
```

**Section 3 — User funnel**

Horizontal funnel (or stacked bar) showing counts at each stage:
- Total signups
- Email verified
- Trial started (subscription_status = "trialing")
- Converted (subscription_status = "active")
- Churned (subscription_status = "canceled")

Backend: add to `GET /api/admin/finance`:
```python
funnel = {
    "total_signups": users_collection.count_documents({}),
    "email_verified": users_collection.count_documents({"email_verified": True}),
    "trial_started": users_collection.count_documents({"subscription_status": {"$in": ["trialing", "active", "canceled"]}}),
    "converted": users_collection.count_documents({"subscription_status": "active"}),
    "churned": users_collection.count_documents({"subscription_status": "canceled"}),
}
```

**Section 4 — Invoices table**

Full-page data table from `/api/admin/finance/invoices`:
- Invoice ID
- User email (link to user detail)
- Amount (formatted)
- Status badge (paid/open/void/draft)
- Period
- PDF link

Pagination controls (skip/limit). Add a `user_id` filter query param to the backend endpoint (map
`user_id` → `stripe_customer_id` via the `customer_email_map` already built in that endpoint):
```python
if user_id_filter:
    user_doc = users_collection.find_one({"_id": user_id_filter})
    if user_doc and user_doc.get("stripe_customer_id"):
        params["customer"] = user_doc["stripe_customer_id"]
```

### 5.2 Audit log page

**New file**: `frontend/src/app/(admin)/admin/audit/page.tsx`

Filter bar:
- Admin user ID (text input)
- Target user ID (text input)
- Action (Select: all or specific actions like `delete_user`, `set_plan`, `impersonate_user`, etc.)

Table:
| Column | Notes |
|---|---|
| Time | relative + absolute tooltip |
| Admin | admin_user_id (link to user detail) |
| Action | badge |
| Target | target_user_id (link to user detail) |
| Details | expandable: click to show JSON in a `<pre>` block |

Pagination: skip/limit. Sort: newest first.

### 5.3 Platform health page

**New file**: `frontend/src/app/(admin)/admin/platform/page.tsx`

**Section 1 — Live status cards** (from `/api/admin/platform`, auto-refresh every 30 seconds)
- Online daemons: N total (desktop: X, cloud: Y)
- Running tasks
- Pending tasks
- Failed tasks (24h)
- Completed tasks (24h)
- Connects (24h)
- Follow-ups (24h)

**Section 2 — Daemon map**

Table of all `LinkedInProfile` records with their daemon status. Fetched via a new endpoint:

```python
@router.get("/platform/daemons", dependencies=[Depends(get_admin_user)])
async def list_all_daemons(
    status: Optional[str] = Query(None),  # "online" | "offline"
    execution_mode: Optional[str] = Query(None),
) -> dict:
    from datetime import datetime, timezone as tz, timedelta
    profiles_col = get_mongodb_collection("linkedin_profiles")
    users_col = get_mongodb_collection("users")
    if profiles_col is None:
        return {"daemons": []}

    five_min_ago = datetime.now(tz.utc) - timedelta(minutes=5)
    query: dict = {}
    if execution_mode:
        query["execution_mode"] = execution_mode

    profiles = list(profiles_col.find(query))
    result = []
    for p in profiles:
        is_online = (
            p.get("last_heartbeat") is not None
            and p["last_heartbeat"] >= five_min_ago
        )
        if status == "online" and not is_online:
            continue
        if status == "offline" and is_online:
            continue

        user_doc = users_col.find_one({"_id": p.get("user_id")}, {"email": 1, "full_name": 1})
        result.append({
            "profile_id": str(p.get("_id")),
            "username": p.get("username") or p.get("linkedin_username"),
            "execution_mode": p.get("execution_mode", "desktop"),
            "daemon_status": "online" if is_online else "offline",
            "daemon_ip": p.get("daemon_ip"),
            "daemon_platform": p.get("daemon_platform"),
            "daemon_browser": p.get("daemon_browser"),
            "daemon_version": p.get("daemon_version"),
            "last_heartbeat": p.get("last_heartbeat", "").isoformat()
                if hasattr(p.get("last_heartbeat", ""), "isoformat") else None,
            "user_id": p.get("user_id"),
            "user_email": user_doc.get("email") if user_doc else None,
        })

    return {"daemons": result, "total": len(result)}
```

Table columns: User email (link to user detail), LinkedIn username, Mode (Desktop/Cloud), Status
(Online/Offline), IP, Platform, Browser, Version, Last heartbeat.

---

## Navigation integration

**File**: `frontend/src/components/navigation/nav-items.tsx` (or wherever the main nav is defined)

Add an "Admin" item that only renders when `user.is_admin === true`:

```tsx
{user?.is_admin && (
  <Link href="/admin">
    <Button variant="ghost" className="gap-2">
      <ShieldCheck className="h-4 w-4" />
      Admin
    </Button>
  </Link>
)}
```

---

## Security checklist

Every item in this list must be true before shipping Phase 5.

- [ ] All `/api/admin/*` routes have `dependencies=[Depends(get_admin_user)]`.
- [ ] `get_admin_user` re-checks the User doc from MongoDB on every request (it already does via
      `User.get(user_id)`) — no stale JWT claims bypass the check.
- [ ] `UserDetailResponse` never returns `hashed_password`. Stripe IDs are returned only on the
      admin detail endpoint (never on public `/api/auth/me`).
- [ ] Impersonation tokens carry `impersonated_by` claim; the main app banner reads this claim to
      display a visible warning. Impersonation tokens must be short-lived (15 min max).
- [ ] Every write action calls `AdminSecurityPolicy.log_admin_action` before returning.
- [ ] Soft delete does not immediately purge data — sets `is_deleted=True` and schedules wipe.
- [ ] The frontend admin layout redirects non-admin users to `/dashboard` before rendering any
      admin content (server-side protection via the backend is the real gate; frontend redirect is
      UX-only).
- [ ] Admin navigation item hidden for non-admin users in the frontend.
- [ ] `admin_notes`, `stripe_customer_id`, `stripe_subscription_id` are not included in any
      non-admin API response.

---

## Dependency and file inventory

### Backend — files to create or modify

| File | Change |
|---|---|
| `openoutreach/mongodb/models_user.py` | Add `last_login_ip`, `signup_ip` fields |
| `openoutreach/api_v2/schemas/auth.py` | Add `is_admin`, `admin_role` to me-response schema |
| `openoutreach/api_v2/routers/auth.py` | Populate `last_login_ip`, `signup_ip` on login/signup; include new fields in `/me` response; extract `_send_password_reset_email` helper |
| `openoutreach/api_v2/routers/admin.py` | Extend response models; add all new endpoints; add `_build_user_detail_response` helper |
| `openoutreach/api_v2/main.py` | Verify `admin.router` is included |

### Frontend — files to create

| File | Purpose |
|---|---|
| `frontend/src/lib/authStoreV2.ts` | Extend `User` interface + `isAdmin` selector |
| `frontend/src/lib/api/admin.ts` | Admin API client + TypeScript interfaces |
| `frontend/src/app/(admin)/layout.tsx` | Admin route guard + layout |
| `frontend/src/components/admin/admin-sidebar.tsx` | Admin nav sidebar |
| `frontend/src/app/(admin)/admin/page.tsx` | Dashboard page |
| `frontend/src/app/(admin)/admin/users/page.tsx` | Users list |
| `frontend/src/app/(admin)/admin/users/[id]/page.tsx` | User detail (tabbed) |
| `frontend/src/app/(admin)/admin/finance/page.tsx` | Finance + funnel |
| `frontend/src/app/(admin)/admin/audit/page.tsx` | Audit log |
| `frontend/src/app/(admin)/admin/platform/page.tsx` | Platform health |

### Frontend — files to modify

| File | Change |
|---|---|
| `frontend/src/lib/authStoreV2.ts` | Add `is_admin`, `admin_role` to `User` interface |
| Main nav component | Conditional "Admin" link for `is_admin` users |

---

## Implementation order

```
Phase 1  →  Phase 2  →  Phase 3  →  Phase 4  →  Phase 5
Backend      Backend      Frontend     Frontend     Frontend
foundations  write ops    layout +     users        finance +
                          dashboard    list + detail audit + platform
```

Phases 1 and 2 can be committed and deployed without any visible frontend change — the new endpoints
are inert until Phase 3 ships the UI. This allows backend work to land on `main` continuously while
frontend work lands in a feature branch (or in the same branch in weekly slices).
