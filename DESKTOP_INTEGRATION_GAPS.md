# Desktop App Integration - Missing Pieces

## ✅ Fixed
- Desktop config now points to correct API: `https://linkedin-api.lengrowth.com`
- Login button opens correct platform: `https://linkedin.lengrowth.com`
- Dashboard button opens correct platform

## 🔴 Critical - Missing Frontend Support

### 1. Desktop Login Flow Not Implemented

**Current Flow (doesn't exist)**:
```
Desktop app → Opens browser to https://linkedin.lengrowth.com/login?desktop=true
User logs in → ???
Should redirect to → lengrowth://auth?token=xxx&profile_id=yyy
Desktop app catches URL → Stores credentials → Starts daemon
```

**Problem**: Frontend login page doesn't handle `?desktop=true` parameter.

**What needs to be added to `frontend/src/app/(auth)/login/page.tsx`**:

```tsx
useEffect(() => {
  const isDesktop = searchParams.get("desktop") === "true"
  const callback = searchParams.get("callback") || "lengrowth://auth"
  
  if (isDesktop && isAuthenticated && session) {
    // Get user's LinkedIn profile ID
    const getProfileAndRedirect = async () => {
      try {
        const response = await fetch('/api/linkedin/profiles', {
          headers: { Authorization: `Bearer ${session.access_token}` }
        })
        const profiles = await response.json()
        
        if (profiles.length > 0) {
          const profileId = profiles[0].id
          // Redirect back to desktop app with credentials
          window.location.href = `${callback}?token=${session.access_token}&profile_id=${profileId}`
        }
      } catch (err) {
        console.error('Failed to get profile:', err)
      }
    }
    
    getProfileAndRedirect()
  }
}, [isAuthenticated, session, searchParams])
```

### 2. Backend API Endpoint Missing

**Desktop app expects**: `GET /api/linkedin/profiles`

**Needs to return**:
```json
[
  {
    "id": "profile_uuid",
    "linkedin_username": "user@example.com",
    ...
  }
]
```

**Check if this endpoint exists**:
```bash
grep -r "linkedin/profiles" openoutreach/api_v2/routers/
```

If not, needs to be added to `openoutreach/api_v2/routers/linkedin.py`:

```python
@router.get("/profiles")
async def get_user_profiles(user_id: str = Depends(get_current_user)):
    """Get all LinkedIn profiles for the current user."""
    profiles = LinkedInProfile.objects.filter(user_id=user_id)
    return [
        {
            "id": str(profile._id),
            "linkedin_username": profile.linkedin_username,
            "display_name": profile.display_name or profile.linkedin_username,
        }
        for profile in profiles
    ]
```

### 3. Multi-Profile Selection

**Current**: Desktop app only handles ONE profile.

**If user has multiple LinkedIn accounts**:
- Frontend needs to show profile picker before redirecting
- Desktop app needs to accept `profile_id` in callback
- OR: Desktop app needs multi-profile support (like cloud daemon)

**Current desktop app code**:
```python
# openoutreach/desktop/auth.py
def login(self, token: str, profile_id: str):
    keyring.set_password(SERVICE_NAME, "token", token)
    keyring.set_password(SERVICE_NAME, "profile_id", profile_id)  # Only one
```

**Problem**: If user has 3 LinkedIn accounts, desktop app can only run 1 at a time.

---

## 🟡 Medium Priority

### 4. Test the Full Flow

Once frontend is updated, test:

1. **Install desktop app** (from built .exe/.dmg)
2. **Click "Login to Lengrowth"** in system tray
3. **Browser opens** → https://linkedin.lengrowth.com/login?desktop=true&callback=lengrowth://auth
4. **User logs in** with email/password
5. **Frontend gets LinkedIn profile ID** from backend
6. **Frontend redirects** to `lengrowth://auth?token=xxx&profile_id=yyy`
7. **Desktop app catches callback** (already implemented in `protocol_handler.py`)
8. **Desktop app stores credentials** in system keychain (already implemented)
9. **Desktop app starts daemon** (already implemented)
10. **Daemon claims tasks from backend** and executes using local IP ✅

### 5. Error Handling

What if:
- User has no LinkedIn profile configured? → Frontend should redirect to settings
- User cancels login? → Desktop app shows "Login required" state
- Token expires? → Desktop app needs refresh token flow

---

## 🟢 Nice to Have

### 6. Desktop Indicator in Web UI

Show in web dashboard which profiles are running on desktop vs cloud:

```tsx
// In Settings → LinkedIn Connection
{profile.daemon_last_seen && (
  <Badge variant={profile.daemon_platform === "win32" ? "desktop" : "cloud"}>
    {profile.daemon_platform === "darwin" ? "macOS" :
     profile.daemon_platform === "win32" ? "Windows" : "Cloud"}
  </Badge>
)}
```

Backend already tracks:
- `daemon_last_seen`
- `daemon_version`
- `daemon_platform` ("darwin" | "win32")
- `daemon_browser` ("chrome" | "edge" | "safari")

Just needs frontend display.

---

## Summary

**To make desktop app work, you need to**:

1. ✅ Fix API URL in config (DONE)
2. ❌ Add desktop login handling to frontend (`login/page.tsx`)
3. ❌ Add/verify LinkedIn profiles API endpoint exists
4. ❌ Handle multi-profile scenario
5. ⏳ Test end-to-end flow

**Estimated work**: 1-2 hours for frontend changes + backend endpoint verification.

**After that**: Desktop app should work! 🎉
