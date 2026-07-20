# Production Readiness Checklist

## ✅ Completed Components

### Backend
- [x] LinkedInProfile model with execution_mode, last_heartbeat, daemon_status
- [x] Desktop daemon API endpoints (heartbeat, status)
- [x] Billing enforcement (trial users blocked from cloud)
- [x] Credential creation validation (execution_mode required)
- [x] Trial duration increased to 7 days
- [x] Campaign limits fixed (counts all campaigns)
- [x] Cloud execution removed from base plans
- [x] Migration script for existing profiles

### Frontend
- [x] ExecutionModeChoiceModal component
- [x] DesktopDownloadInstructions component
- [x] useDesktopDaemonStatus hook
- [x] ExecutionModeBadge component
- [x] LastSeenStatus component
- [x] Execution mode validation in credential creation

### Documentation
- [x] CLAUDE.md updated with execution mode architecture
- [x] Implementation guide created
- [x] Testing checklist created
- [x] Migration script documented

---

## 🔧 Integration Steps

### 1. Run Database Migration
```bash
# From project root
python -m openoutreach.migrations.add_execution_mode_to_profiles
```

**Expected output:**
```
Starting execution_mode migration...
Found X profiles to migrate
Migration complete: updated X profiles
✅ All profiles now have execution_mode field
```

### 2. Update LinkedIn Credentials UI

**File:** `frontend/src/components/settings/linkedin-connection-tab.tsx`

Add execution mode selection to the "Add LinkedIn Credentials" flow:

```typescript
import { ExecutionModeChoiceModal } from "./execution-mode-choice-modal";
import { DesktopDownloadInstructions } from "./desktop-download-instructions";

// Inside component:
const [showExecutionModeModal, setShowExecutionModeModal] = useState(false);
const [showDownloadInstructions, setShowDownloadInstructions] = useState(false);
const [showCredentialForm, setShowCredentialForm] = useState(false);

// Replace direct credential form opening:
const handleAddCredential = () => {
  setShowExecutionModeModal(true); // Show choice modal first
};

const handleSelectDesktop = () => {
  setShowExecutionModeModal(false);
  setShowDownloadInstructions(true); // Show download guide
};

const handleSelectCloud = () => {
  setShowExecutionModeModal(false);
  setShowCredentialForm(true); // Show credential form
};

// In render:
<ExecutionModeChoiceModal
  open={showExecutionModeModal}
  onClose={() => setShowExecutionModeModal(false)}
  onSelectDesktop={handleSelectDesktop}
  onSelectCloud={handleSelectCloud}
  canUseCloud={user.cloud_profiles > 0 || hasCloudFeature}
  isTrialing={user.subscription_status === "trialing"}
/>

<DesktopDownloadInstructions
  open={showDownloadInstructions}
  onClose={() => setShowDownloadInstructions(false)}
}
/>
```

### 3. Add Badges to Credential Cards

**File:** `frontend/src/components/settings/linkedin-credential-card.tsx`

Import and add badges:

```typescript
import { ExecutionModeBadge, LastSeenStatus } from "./execution-mode-badge";

// In the credential card header, after status badges:
<ExecutionModeBadge
  executionMode={credential.execution_mode || "desktop"}
  profileId={credential.linkedin_profile_id}
  showConnectionStatus={true}
/>

// In the metadata section:
<LastSeenStatus
  profileId={credential.linkedin_profile_id}
  executionMode={credential.execution_mode || "desktop"}
/>

// Add "Open Desktop App" button for offline desktop credentials:
{credential.execution_mode === "desktop" && !isConnected && (
  <Button
    variant="outline"
    size="sm"
    onClick={() => {
      // Platform-specific open command
      window.location.href = "openoutreach://open";
    }}
  >
    <Monitor className="mr-2 h-4 w-4" />
    Open Desktop App
  </Button>
)}
```

### 4. Update API Call for Credential Creation

**File:** Wherever credentials are created (e.g., `lib/api/dashboard.ts`)

Add execution_mode to the request:

```typescript
export async function createLinkedInCredentials(data: {
  email: string;
  password: string;
  execution_mode: "desktop" | "cloud"; // NEW
  // ... other fields
}) {
  const response = await fetch("/api/linkedin-credentials/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json();
    // Handle upgrade_required error
    if (error.detail?.upgrade_required) {
      throw new UpgradeRequiredError(error.detail.error);
    }
    throw new Error(error.detail || "Failed to create credential");
  }

  return response.json();
}
```

---

## 🧪 Testing Checklist

### Backend API Tests

**Desktop Daemon Heartbeat:**
```bash
curl -X POST http://localhost:8001/api/desktop-daemon/heartbeat \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "profile_id": "PROFILE_ID",
    "daemon_version": "1.0.0",
    "platform": "Windows",
    "browser": "Chrome"
  }'

# Expected: {"status": "ok", "next_heartbeat_seconds": 60}
```

**Daemon Status:**
```bash
curl http://localhost:8001/api/desktop-daemon/status \
  -H "Authorization: Bearer YOUR_TOKEN"

# Expected: {"profiles": [...]}
```

**Credential Creation with Desktop Mode:**
```bash
curl -X POST http://localhost:8001/api/linkedin-credentials/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "password",
    "execution_mode": "desktop"
  }'

# Expected: 201 Created with credential object
```

**Credential Creation with Cloud Mode (Trial User):**
```bash
curl -X POST http://localhost:8001/api/linkedin-credentials/ \
  -H "Authorization: Bearer TRIAL_USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "password",
    "execution_mode": "cloud"
  }'

# Expected: 403 Forbidden
# {"detail": {"error": "Cloud execution is not available during trial...", "upgrade_required": true, "recommended_action": "use_desktop"}}
```

### Frontend UI Tests

**Test 1: Execution Mode Choice Modal**
- [ ] Modal opens when clicking "Add LinkedIn Credentials"
- [ ] Desktop option is always available
- [ ] Cloud option shows "Upgrade Required" badge for trial users
- [ ] Trial users see amber alert explaining cloud limitation
- [ ] "Continue" button is disabled when cloud is selected but not available
- [ ] "Upgrade to Cloud Add-on" button appears for users without addon

**Test 2: Desktop Download Instructions**
- [ ] Opens when desktop option is selected
- [ ] Detects platform correctly (Windows/macOS)
- [ ] Download button links to correct GitHub release
- [ ] Shows 4-step installation guide
- [ ] "View all releases" link works
- [ ] Can close and return to credential list

**Test 3: Credential Badges**
- [ ] Desktop credentials show blue "Desktop" badge
- [ ] Cloud credentials show green "Cloud" badge
- [ ] Desktop credentials show connection status (Active/Offline/Pending)
- [ ] Active desktop credentials show green pulse dot
- [ ] Offline desktop credentials show gray dot
- [ ] Last seen time updates correctly

**Test 4: Desktop Daemon Status**
- [ ] useDesktopDaemonStatus hook polls every 30s
- [ ] Connection status updates in real-time
- [ ] Offline status appears after 2min without heartbeat
- [ ] "Open Desktop App" button appears for offline credentials

**Test 5: Cloud Execution Validation**
- [ ] Trial users cannot select cloud execution
- [ ] Users without addon see upgrade prompt
- [ ] Users with addon can create cloud credentials
- [ ] Error messages are clear and actionable

---

## 📊 Monitoring & Metrics

### Key Metrics to Track

1. **Execution Mode Adoption:**
   - % of credentials using desktop vs cloud
   - Cloud addon conversion rate from trial to paid

2. **Desktop Daemon Health:**
   - Average heartbeat interval
   - % of desktop credentials with active connection
   - Disconnection frequency and duration

3. **User Experience:**
   - Time from account creation to first credential
   - Cloud upgrade funnel: modal view → upgrade click → conversion
   - Desktop download funnel: modal → download → credential creation

### Database Queries

**Count credentials by execution mode:**
```javascript
db.linkedin_profiles.aggregate([
  { $group: { _id: "$execution_mode", count: { $sum: 1 } } }
])
```

**Find disconnected desktop daemons:**
```javascript
db.linkedin_profiles.find({
  execution_mode: "desktop",
  last_heartbeat: { $lt: new Date(Date.now() - 2 * 60 * 1000) }
})
```

**Trial users with cloud execution attempts:**
```javascript
// Check audit logs for 403 errors on credential creation
db.linkedin_credential_logs.find({
  action: "create_failed",
  details: { error: /trial/ }
})
```

---

## 🚀 Deployment Steps

1. **Backend Deploy:**
   ```bash
   git push origin worktree-billing-model-fix
   # Wait for GitHub Actions to build and deploy (~4 min)
   ```

2. **Run Migration:**
   ```bash
   ssh -i ~/.ssh/lenquant.pem ubuntu@ec2-50-19-251-160.compute-1.amazonaws.com
   cd /app
   python -m openoutreach.migrations.add_execution_mode_to_profiles
   ```

3. **Frontend Deploy:**
   ```bash
   # Frontend is bundled with backend, deploys automatically
   ```

4. **Verify Deployment:**
   ```bash
   curl https://api.openoutreach.ai/api/desktop-daemon/status \
     -H "Authorization: Bearer YOUR_TOKEN"
   ```

5. **Monitor Logs:**
   ```bash
   docker compose -f docker-compose.v2.yml logs -f
   ```

---

## 🐛 Troubleshooting

### Issue: Desktop daemon not connecting
**Symptoms:** Credentials stuck in "Pending" status
**Check:**
- Desktop app is running and signed in
- Heartbeat endpoint is reachable
- Network/firewall not blocking requests
- User has valid auth token

**Fix:**
```bash
# Check heartbeat logs
grep "desktop-daemon/heartbeat" /var/log/app.log

# Verify profile exists
mongo --eval 'db.linkedin_profiles.find({_id: "PROFILE_ID"})'
```

### Issue: Trial user seeing cloud option
**Symptoms:** Cloud execution not locked for trial users
**Check:**
- Frontend correctly reads subscription_status
- canUseCloud prop correctly evaluates isTrialing
- API returns 403 on cloud credential creation

**Fix:**
```typescript
// Verify in ExecutionModeChoiceModal props:
isTrialing={user.subscription_status === "trialing"}
canUseCloud={user.cloud_profiles > 0 && !isTrialing}
```

### Issue: Migration failed
**Symptoms:** Profiles missing execution_mode after migration
**Check:**
```python
# Re-run migration with verbose logging
import logging
logging.basicConfig(level=logging.DEBUG)
from openoutreach.migrations.add_execution_mode_to_profiles import migrate_execution_mode
migrate_execution_mode()
```

---

## ✅ Sign-off Criteria

Before marking as production-ready:

- [ ] All backend tests pass (pytest)
- [ ] All frontend components render without errors
- [ ] Migration runs successfully on staging
- [ ] Trial users cannot create cloud credentials
- [ ] Desktop daemon heartbeat works end-to-end
- [ ] Badges display correctly for both execution modes
- [ ] Download instructions show correct platform
- [ ] Error messages are user-friendly
- [ ] Documentation is complete and accurate
- [ ] Monitoring is in place
- [ ] Team has reviewed and approved

---

## 📞 Support

**For implementation questions:**
- Slack: #engineering
- Email: dev@openoutreach.ai

**For bug reports:**
- GitHub Issues: https://github.com/BuildGrowthNow/OpenOutreach/issues

**For production incidents:**
- PagerDuty: OpenOutreach On-Call
- Escalation: CTO
