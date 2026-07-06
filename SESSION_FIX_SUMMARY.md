# LinkedIn Session Cookie Fix - Implementation Summary

## Problem
LinkedIn session cookies (`li_at`) were expiring every ~30 minutes, causing 401 errors and forcing full re-authentication (email/password login) which often triggered LinkedIn's security challenges.

## Root Cause
Cookies were only saved on initial login, never refreshed. Each time the session died, the daemon would:
1. Clear saved cookies
2. Perform a fresh email/password login
3. Often hit LinkedIn security challenges/CAPTCHAs
4. Exit the daemon for manual intervention

## Solution Implemented

### 1. Proactive Cookie Refresh
**Files Modified:**
- `openoutreach/core/daemon.py` (lines 454-462)
- `openoutreach/linkedin/browser/launch.py` (lines 65-75)

**What Changed:**
- After every successful task completion, the daemon now calls `_save_cookies(session)` to persist the current Playwright storage state (including the `li_at` auth cookie) back to the DB
- This keeps the session "warm" by continuously refreshing the stored cookie data with the active browser session's state
- Reduces the frequency of 401 errors and full re-authentications

**How It Works:**
```python
# After task completion in daemon.py
try:
    from openoutreach.linkedin.browser.launch import _save_cookies
    _save_cookies(session)
    logger.debug("Refreshed session cookies after task completion")
except Exception as e:
    logger.debug("Failed to refresh cookies: %s", e)
```

### 2. noVNC Web Viewer in Frontend
**Files Created:**
- `frontend/src/components/settings/vnc-viewer.tsx`

**Files Modified:**
- `frontend/src/components/settings/linkedin-connection-tab.tsx`

**What Changed:**
- Added a new `VncViewer` component that embeds noVNC as an iframe in the Settings page
- When clicked, opens a live browser session viewer at `http://<your-domain>:6080`
- Operators can now solve LinkedIn CAPTCHAs, security verifications, and challenges directly from the platform
- No need for external VNC clients, SSH tunnels, or copying VNC URLs

**Features:**
- Expandable/collapsible viewer (full-screen mode)
- Auto-connect to noVNC with scale-to-window
- Error handling and status messages
- Positioned in the LinkedIn Connection tab for easy access

### 3. Documentation Updates
**Files Modified:**
- `CLAUDE.md`
- `ARCHITECTURE.md`

**What Changed:**
- Documented the proactive cookie refresh behavior
- Documented the noVNC web viewer component and its purpose
- Updated Docker/VNC port documentation

## Testing Checklist

Before deploying to production:

1. **Cookie Refresh Test:**
   - [ ] Start the daemon
   - [ ] Let it execute at least 5-10 tasks successfully
   - [ ] Check Django Admin → LinkedIn Profiles → verify `cookie_data_encrypted` field is being updated
   - [ ] Monitor logs for "Refreshed session cookies after task completion" debug messages
   - [ ] Verify no 401 errors for at least 1-2 hours of operation

2. **VNC Viewer Test:**
   - [ ] Ensure `ENABLE_VNC=true` in docker-compose.yml
   - [ ] Navigate to Settings → LinkedIn Connection tab
   - [ ] Click "Open Browser Viewer"
   - [ ] Verify noVNC iframe loads and shows the live browser session
   - [ ] Test expand/collapse functionality
   - [ ] Verify you can interact with the browser (click, type, scroll)

3. **Challenge Handling Test:**
   - [ ] Force a LinkedIn challenge (change location, clear cookies, etc.)
   - [ ] Open the VNC viewer from Settings
   - [ ] Solve the CAPTCHA/challenge manually in the viewer
   - [ ] Verify the daemon resumes normal operation after challenge is cleared

## Deployment Notes

### Environment Variables
No new environment variables required. Existing `ENABLE_VNC=true` in docker-compose.yml enables the VNC/noVNC stack.

### Port Exposure
Ensure ports are exposed in docker-compose.yml:
```yaml
ports:
  - "6080:6080"  # noVNC web viewer
  - "5900:5900"  # VNC (optional, for external clients)
```

### Firewall/Security
If running on EC2/cloud:
- Port 6080 should be accessible from your IP (for the VNC web viewer)
- Consider restricting access via security groups/firewall rules
- noVNC runs without password by default (controlled via `-nopw` flag in start script)

## Expected Behavior After Fix

1. **Session Duration:** Sessions should stay alive for several hours (LinkedIn's default cookie expiry) instead of dying every 30 minutes
2. **Re-authentication Frequency:** Full email/password logins should be rare (only after genuine session expiry or 401 from LinkedIn's side)
3. **Challenge Handling:** When challenges appear, operators can solve them via the web viewer without SSH/VNC client
4. **Log Noise:** Fewer "Session expired" and "Re-authenticating" warnings in logs

## Rollback Plan

If issues arise:
1. Remove the cookie refresh code from `daemon.py` (lines 461-467)
2. Remove the VNC viewer from the LinkedIn Connection tab
3. Restart the daemon
4. Fall back to manual cookie copying via Cookie Editor (previous workflow)

## Future Improvements

Consider these enhancements:
1. Add a "Challenge Detected" notification in the frontend when the daemon hits a checkpoint
2. Implement automatic retry with exponential backoff for 401 errors
3. Add session health monitoring (cookie expiry warnings before they die)
4. Implement multiple LinkedIn account support with session pooling
