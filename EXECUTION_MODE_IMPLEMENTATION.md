# Execution Mode Selection - Implementation Status

## ✅ Backend Complete

### 1. LinkedInProfile Model Updates
- ✅ Added `execution_mode` field (desktop/cloud)
- ✅ Added `last_heartbeat` timestamp for desktop daemon tracking
- ✅ Added `daemon_status` field (connected/disconnected/unknown)

### 2. Desktop Daemon API Endpoints
- ✅ POST `/api/desktop-daemon/heartbeat` - Desktop app reports status every 60s
- ✅ GET `/api/desktop-daemon/status` - Frontend polls connection status

### 3. Billing Enforcement
- ✅ Trial users blocked from cloud execution
- ✅ Cloud execution requires `cloud_addon` plan or explicit feature

---

## 🚧 Frontend TODO

### 1. Create Execution Mode Choice Modal
**File:** `frontend/src/components/settings/execution-mode-choice-modal.tsx`

```tsx
interface ExecutionModeChoiceModalProps {
  open: boolean;
  onClose: () => void;
  onSelectDesktop: () => void;
  onSelectCloud: () => void;
}

// Show two options:
// - Desktop App (Recommended) ✨
//   • Free - no additional cost
//   • Uses your residential IP
//   • Runs on your computer
//   [Download Desktop App →]
//
// - Cloud Execution
//   • $39/month per LinkedIn account
//   • Runs 24/7 on our servers
//   [Upgrade to Cloud Add-on →]  🔒

// Lock cloud option if:
// - User is in trial (subscription_status === "trialing")
// - User doesn't have cloud_addon and no cloud_profiles > 0
```

### 2. Update LinkedIn Connection Tab
**File:** `frontend/src/components/settings/linkedin-connection-tab.tsx`

**Changes:**
- "Add LinkedIn Credentials" button → opens `ExecutionModeChoiceModal` first
- If Desktop selected → show download instructions + link
- If Cloud selected → show existing credential creation form

### 3. Add Execution Mode Badges to Credentials List
**File:** `frontend/src/components/settings/linkedin-credential-card.tsx`

**Add badges:**
- 🖥️ Desktop (blue) or ☁️ Cloud (green)
- ● Active (green pulse) / ○ Offline (gray) for desktop
- Show `last_heartbeat` time for desktop credentials
- Add "Open Desktop App" button for offline desktop credentials

### 4. Create Desktop Daemon Status Hook
**File:** `frontend/src/lib/hooks/use-desktop-daemon-status.ts`

```typescript
export function useDesktopDaemonStatus() {
  // Poll /api/desktop-daemon/status every 30s
  // Return: { profiles: ProfileStatus[] }
  
  // ProfileStatus:
  // - id, email, execution_mode
  // - is_connected: boolean
  // - last_seen: string | null
  // - daemon_status: "connected" | "disconnected" | "never_connected"
}
```

### 5. Update Credential Creation API Call
**File:** Wherever credentials are created (API call)

**Add field to request:**
```typescript
{
  email: string;
  password: string;
  execution_mode: "desktop" | "cloud"; // NEW
}
```

### 6. Update Billing Status Types
**File:** `frontend/src/types/billing.ts` (or wherever billing types live)

**Add to user billing status:**
```typescript
{
  cloud_profiles: number;  // Number of cloud execution seats
  subscription_status: string; // "trialing", "active", etc.
}
```

---

## 🖥️ Desktop App TODO

### 1. Update Desktop App Login Flow
**File:** `openoutreach/desktop/app.py`

**After successful LinkedIn login:**
1. Call POST `/api/linkedin-credentials` with:
   ```json
   {
     "email": "user@company.com",
     "password": "encrypted_password",
     "execution_mode": "desktop"
   }
   ```
2. Start heartbeat loop:
   ```python
   async def heartbeat_loop(profile_id):
       while True:
           await asyncio.sleep(60)
           await post_heartbeat(profile_id)
   ```

### 2. Implement Heartbeat
**File:** `openoutreach/desktop/daemon.py`

```python
async def post_heartbeat(profile_id: str):
    """Send heartbeat to server every 60s"""
    response = await api_client.post(
        "/api/desktop-daemon/heartbeat",
        json={
            "profile_id": profile_id,
            "daemon_version": __version__,
            "platform": platform.system(),
            "browser": "Chrome",  # or detected browser
        }
    )
    return response.json()
```

---

## 📋 Testing Checklist

### Backend
- [x] LinkedInProfile saves/loads execution_mode correctly
- [x] Desktop heartbeat endpoint accepts and stores data
- [x] Status endpoint returns correct connection state
- [x] Trial users get 403 when trying cloud execution
- [x] Paid users without addon get upgrade error

### Frontend
- [ ] Execution mode choice modal shows correct options
- [ ] Trial users see only desktop option (cloud locked)
- [ ] Paid users see both options
- [ ] Desktop flow shows download instructions
- [ ] Cloud flow shows credential form
- [ ] Credentials list shows correct badges
- [ ] Desktop credentials show connection status
- [ ] Offline credentials show "Open Desktop App" button
- [ ] Status updates every 30s via polling

### Desktop App
- [ ] Desktop app creates credential with execution_mode="desktop"
- [ ] Heartbeat posts every 60s
- [ ] Connection status updates on web
- [ ] Offline status shows after 2min without heartbeat

---

## 🎨 UI Mockups

### Execution Mode Choice Modal
```
┌─────────────────────────────────────────┐
│  How do you want to run automation?     │
├─────────────────────────────────────────┤
│                                          │
│  ○ Desktop App (Recommended) ✨          │
│    • Free - no additional cost          │
│    • Uses your residential IP           │
│    • Runs on your computer              │
│    [Download Desktop App →]             │
│                                          │
│  ○ Cloud Execution                       │
│    • $39/month per LinkedIn account     │
│    • Runs 24/7 on our servers          │
│    [Upgrade to Cloud Add-on →]  🔒      │
│                                          │
└─────────────────────────────────────────┘
```

### Credentials List with Badges
```
LinkedIn Credentials
┌────────────────────────────────────────────────┐
│ john.doe@company.com                           │
│ ● Active  🖥️ Desktop  ✓ Connected             │
│ Last active: 2 minutes ago                     │
└────────────────────────────────────────────────┘

┌────────────────────────────────────────────────┐
│ jane.smith@company.com                         │
│ ● Active  ☁️ Cloud  ✓ Running                 │
│ Last active: Just now                          │
└────────────────────────────────────────────────┘

┌────────────────────────────────────────────────┐
│ old.account@company.com                        │
│ ○ Offline  🖥️ Desktop  ⚠️ Disconnected        │
│ Last seen: 3 hours ago                         │
│ [Open Desktop App →]                           │
└────────────────────────────────────────────────┘
```

---

## 📝 Notes

- **Desktop is the default** for all base plans (starter/pro/business/agency/lifetime)
- **Cloud execution** is a paid add-on only ($39/month per seat via `cloud_addon`)
- **Trial users** cannot use cloud execution (must use desktop app)
- **Migration**: Existing credentials default to `execution_mode="desktop"` (can be updated to "cloud" if needed)
- **Heartbeat timeout**: 2 minutes without heartbeat = disconnected
- **Polling interval**: Frontend polls status every 30s
