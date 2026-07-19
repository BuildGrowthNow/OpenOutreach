# Remote Daemon Critical Bug Fixes

## Summary
Fixed two critical bugs that prevented the remote daemon (desktop app) from claiming and executing tasks.

## Bug 1: Task Claim Query Uses Wrong Field Path

**File**: `openoutreach/api_v2/routers/daemon.py:123`

**Issue**: The MongoDB query was looking for `"payload.linkedin_profile_id"` but the Task model stores `linkedin_profile_id` as a top-level field, not nested inside payload.

**Impact**: The daemon would NEVER find tasks to claim — every poll would return empty, making the desktop app completely non-functional.

**Fix**: Changed the query filter from:
```python
"payload.linkedin_profile_id": linkedin_profile_id
```
to:
```python
"linkedin_profile_id": linkedin_profile_id
```

## Bug 2: Task Handlers Crash — session.campaign is None

**File**: `openoutreach/core/daemon_remote.py:340`

**Issue**: `RemoteSession.campaign` was initialized to `None` and never set before calling task handlers. All handlers (handle_connect, handle_check_pending, handle_follow_up) immediately access `session.campaign` (e.g., connect.py:74).

**Impact**: Every task execution would crash with `AttributeError: 'NoneType' object has no attribute ...` immediately upon handler invocation.

**Fix**: Added campaign resolution and validation before handler execution (matching the local daemon pattern):
```python
# Validate campaign (same as local daemon does)
campaign_id = task.get("payload", {}).get("campaign_id")
if not campaign_id:
    raise ValueError("Task missing campaign_id in payload")

campaign = Campaign.get(campaign_id)
if not campaign or campaign.status != Campaign.Status.ACTIVE:
    raise ValueError(f"Campaign {campaign_id} not found or inactive")

# Verify session is initialized
if not self.session:
    raise RuntimeError("Session not initialized")

# Set campaign on session (required by all handlers)
self.session.campaign = campaign
```

## Additional Improvements

### Deprecated datetime.utcnow() Fixes
Updated all `datetime.utcnow()` calls in `daemon.py` to use timezone-aware `datetime.now(timezone.utc)` to eliminate deprecation warnings and ensure consistent timezone handling.

### Type Safety
- Added proper type hints for `RemoteSession.campaign` as `Optional[Any]`
- Added runtime session validation before task execution
- All changes pass pyright type checking with 0 errors

## Testing
- ✅ Syntax validation: All files compile successfully
- ✅ Linting: `ruff check` passes with no new errors
- ✅ Type checking: `pyright` passes with 0 errors, 0 warnings

## Deployment Considerations

### Web App (AWS)
The web app uses the cloud daemon which:
- Runs on AWS EC2 using the server's IP address
- Uses the existing local daemon code path (`openoutreach/core/daemon.py`)
- Is NOT affected by these bugs (local daemon was already working correctly)
- No changes needed for web deployment

### Desktop App (Local)
The desktop app uses the remote daemon which:
- Runs on the user's desktop machine using their residential IP
- Uses the fixed remote daemon code path (`openoutreach/core/daemon_remote.py`)
- Communicates with the backend via the fixed API endpoints (`openoutreach/api_v2/routers/daemon.py`)
- Now properly claims tasks and executes them with the campaign context set

## Next Steps
1. Deploy these fixes to production
2. Test the desktop app with a real LinkedIn profile to verify:
   - Tasks are claimed successfully
   - Handlers execute without crashing
   - Cookies are synced after successful execution
3. Monitor logs for any remaining issues
