# State Machine Editor - Feature Status

**STATUS:** Hidden from production users (incomplete)

## Overview

Visual workflow builder for campaign automation. Currently accessible only via feature flag `NEXT_PUBLIC_ENABLE_STATE_MACHINE=true`.

## What Works

- ✅ Backend Django models (`CampaignStateGraph`, `StateNode`, `StateTransition`, `CampaignState`)
- ✅ Visual canvas with drag-and-drop nodes
- ✅ Node types: start, end, wait, message, gate, decision, branch
- ✅ Node creation/deletion
- ✅ Edge/transition creation/deletion
- ✅ Node repositioning
- ✅ Save/load from API
- ✅ Basic validation endpoint
- ✅ Simulation endpoint (dry-run execution)
- ✅ Node editing modal (name, type, description)

## Missing Features (Production Blockers)

### 1. Edge Editing UI (4-6 hours)
**Current:** Can create/delete edges, but cannot edit labels or conditions  
**Needed:**
- Edge edit modal triggered by clicking edge label or context menu
- Fields: label (string), condition_type (dropdown: always/response/time_based/custom)
- Save changes via API

### 2. Node Configuration Panels (8-10 hours)
**Current:** Nodes store `config` JSON but UI doesn't edit it  
**Needed:** Type-specific configuration forms:

- **Message node:** Template editor (message content, variables like `{lead_name}`)
- **Wait node:** Duration picker (hours/days), optional condition
- **Gate node:** Qualification rules (e.g., profile field checks, enrichment requirements)
- **Decision node:** Branch conditions (if/else rules)
- **Webhook node:** URL, method, headers, payload template

### 3. Connection Drawing Tool (2-3 hours)
**Current:** Auto-creates edges from start node, or adds via Add Edge button  
**Needed:**
- Click source node → enters "connecting mode" → click target node → creates edge
- Visual feedback (arrow cursor, temp line preview)
- Cancel on ESC or click canvas

### 4. Validation Improvements (2 hours)
**Current:** Backend checks for start node existence  
**Needed:**
- Enforce single start node (prevent multiple)
- Require at least one end node
- Check for unreachable nodes (no incoming transitions except start)
- Check for infinite loops (no path to end)

### 5. Daemon Integration (1-2 days)
**Current:** State machine exists in DB but daemon doesn't execute it  
**Needed:**
- Wire `StateMachineEngine` into task queue
- Replace/augment Task handlers to check for active state machine
- State machine executes instead of default follow-up logic
- Migration strategy for existing campaigns

### 6. Activation Toggle (1 hour)
**Current:** `is_active` field exists but no UI toggle  
**Needed:**
- Toggle switch in header "Activate Workflow"
- Warning modal: "This will replace default campaign behavior"
- API endpoint to toggle `CampaignStateGraph.is_active`

## Files to Modify

### Frontend
- `frontend/src/app/(dashboard)/state-machine/page.tsx` - Main editor
- `frontend/src/components/state-machine/canvas.tsx` - Canvas component
- `frontend/src/components/state-machine/edge.tsx` - Edge rendering (add edit handler)
- `frontend/src/lib/api/dashboard.ts` - Add edge update endpoint

### Backend
- `openoutreach/api/views/state_machine.py` - Add edge PATCH endpoint
- `openoutreach/linkedin/services/state_machine.py` - StateMachineEngine
- `openoutreach/core/daemon.py` - Integrate state machine execution
- `openoutreach/linkedin/tasks/` - Check for state machine before default handlers

## How to Enable for Development

```bash
# In frontend/.env.local
NEXT_PUBLIC_ENABLE_STATE_MACHINE=true
```

Restart Next.js dev server. State Machine will appear in sidebar.

## Testing Strategy

1. **Unit tests:** Node/edge CRUD operations
2. **Integration tests:** Full workflow simulation
3. **E2E tests:** Canvas interactions, save/load cycle
4. **Manual QA:** Build complex workflow with 10+ nodes, execute on test campaign

## Recommended Implementation Order

1. Edge editing modal (unblocks visual workflow building)
2. Node configuration panels (unblocks functional workflows)
3. Connection drawing tool (improves UX)
4. Validation improvements (prevents broken workflows)
5. Activation toggle + daemon integration (enables production use)

## Decision: Why Hidden?

- Current Task-based system works reliably
- Missing features would frustrate users
- Daemon integration not done = workflows don't actually run
- Better to hide than ship incomplete feature

## Re-enabling Checklist

Before unhiding in production:

- [ ] All production blockers above implemented
- [ ] State machine execution tested on real campaign
- [ ] Migration path for existing campaigns documented
- [ ] User documentation written
- [ ] Support team trained on new feature
- [ ] Feature flag removed from code
