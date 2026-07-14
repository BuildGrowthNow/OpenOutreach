# FastAPI + MongoDB Migration Plan

**Goal:** Migrate OpenOutreach from Django + SQLite to FastAPI + MongoDB Atlas — production-ready, nothing missed.

**Your Stack:** Python, FastAPI, Uvicorn, MongoDB Atlas, Next.js, Tailwind CSS

**Current State:**
- Partial MongoDB models created (pymongo-based) — ~30% of models ported
- Django ORM still used for most operations
- SQLite database in production
- Django REST Framework APIs (15+ view modules, 60+ endpoints)
- Supabase JWT authentication (primary) + SimpleJWT (secondary)
- Django Channels WebSocket (notifications + campaign status)
- SSE fallback endpoint for real-time
- Django Signals (3 receivers for side effects)
- Fernet encryption layer for LinkedIn cookies/credentials
- ML pipeline (scikit-learn model blobs stored in Campaign)
- Email channel (Mailbox pool with daily pacing)

**Timeline:** 6-9 weeks total (3 phases)

---

## Complete Model Inventory

Every Django model that must have a MongoDB equivalent:

| # | App | Model | Status | Notes |
|---|-----|-------|--------|-------|
| 1 | core | SiteConfig | ❌ Missing | Singleton, LLM keys, rate limits, active hours |
| 2 | core | CampaignTemplate | ❌ Missing | Predefined campaign settings |
| 3 | core | Campaign | ✅ Partial | Missing: model_blob (Binary), status field, users M2M |
| 4 | core | Task | ❌ Missing | Queue system with TaskQuerySet |
| 5 | crm | Lead | ✅ Partial | Check all fields ported |
| 6 | crm | Deal | ✅ Partial | Missing: mailbox, email_sent_at, connect_attempts, backoff |
| 7 | crm | TrackedLink | ❌ Missing | URL tracking with UTM params |
| 8 | crm | LinkClick | ❌ Missing | Individual click records |
| 9 | crm | LinkDealConversion | ❌ Missing | Link→Deal attribution |
| 10 | crm | Note | ❌ Missing | Deal notes |
| 11 | crm | LeadPersona | ❌ Missing | LLM-generated lead personas |
| 12 | crm | LinkedInCredentials | ✅ Partial | Encrypted fields |
| 13 | linkedin | LinkedInProfile | ✅ Partial | Missing: cookie_data_encrypted, rate limit fields |
| 14 | linkedin | SearchKeyword | ❌ Missing | Campaign search keywords |
| 15 | linkedin | ActionLog | ❌ Missing | Activity feed + error tracking |
| 16 | linkedin.state_machine | CampaignStateGraph | ❌ Missing | Campaign workflow definitions |
| 17 | linkedin.state_machine | StateNode | ❌ Missing | Graph nodes |
| 18 | linkedin.state_machine | StateTransition | ❌ Missing | Graph edges |
| 19 | linkedin.state_machine | CampaignState | ❌ Missing | Per-deal state tracking |
| 20 | linkedin.state_machine | CampaignExecutionLog | ❌ Missing | Step-by-step execution log |
| 21 | linkedin.health | CampaignHealthMetric | ❌ Missing | Hourly campaign metrics |
| 22 | linkedin.health | HealthAlert | ❌ Missing | Alert records |
| 23 | linkedin.health | RecoveryAction | ❌ Missing | Auto-remediation log |
| 24 | linkedin.rate_limits | SmartRateLimitContext | ❌ Missing | Per-profile rate state |
| 25 | linkedin.rate_limits | RateLimitWarning | ❌ Missing | Warning log |
| 26 | linkedin.ghost_mode | GhostCampaign | ❌ Missing | Ghost/simulation campaigns |
| 27 | linkedin.ghost_mode | GhostSimulationLog | ❌ Missing | Simulation results |
| 28 | linkedin.ghost_mode | GhostTestScenario | ❌ Missing | Reusable test scenarios |
| 29 | chat | ChatMessage | ❌ Missing | LinkedIn messages per deal |
| 30 | emails | Mailbox | ❌ Missing | SMTP inboxes with daily pacing |
| 31 | notifications | Notification | ❌ Missing | User notifications (7 types) |
| 32 | auth | User | ❌ Missing | Auth user (Django contrib.auth.User) |

---

## Complete API Endpoint Inventory

Every endpoint that must be ported to FastAPI:

### Auth (8 endpoints)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `auth/login/` | POST | JWT token obtain (currently SimpleJWT) |
| `auth/refresh/` | POST | Token refresh |
| `auth/verify/` | POST | Token verify |
| `auth/status/` | GET | Auth status check |
| `auth/logout/` | POST | Logout |
| `auth/password-reset/request/` | POST | Password reset email |
| `auth/password-reset/confirm/` | POST | Confirm reset |
| `auth/update-password/` | POST | Change password |

### Supabase Auth (3 endpoints)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `auth/link-supabase-user/` | POST | Link Supabase→Django user |
| `auth/supabase-user/<id>/` | GET | Get Supabase user info |
| `auth/verify-supabase-token/` | POST | Verify Supabase JWT |

### Campaigns (12 endpoints)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `campaigns/` | GET, POST | List/Create campaigns |
| `campaigns/<id>/` | GET, PATCH, DELETE | Campaign CRUD |
| `campaigns/<id>/leads/` | GET | Campaign leads with deal state |
| `campaigns/<id>/leads/upload/` | POST | CSV upload leads |
| `campaigns/<id>/messages/` | GET | Campaign conversation threads |
| `campaigns/<id>/analytics/` | GET | Campaign-specific analytics |
| `campaigns/<id>/state-machine/` | GET, PUT | State machine graph CRUD |
| `campaigns/<id>/state-machine/validate/` | POST | Validate graph |
| `campaigns/<id>/state-machine/simulate/` | POST | Simulate execution |
| `campaigns/<id>/activity/` | GET | Activity feed (ActionLog) |
| `campaigns/<id>/status/` | PATCH | Start/pause/complete |
| `campaigns/<id>/ghost-mode/simulations/` | GET | Ghost simulation list |
| `campaigns/<id>/ghost-mode/action/` | POST | Run ghost action |

### Campaign Templates (4 endpoints)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `campaign-templates/` | GET, POST | List/create templates |
| `campaign-templates/<id>/` | GET, PATCH, DELETE | Template CRUD |
| `campaign-templates/<id>/clone/` | POST | Clone template |
| `campaign-templates/<id>/create-campaign/` | POST | Create campaign from template |

### Leads (7 endpoints)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `leads/` | GET | List leads (filterable) |
| `leads/<id>/` | GET, PATCH | Lead detail/update |
| `leads/<id>/profile/` | GET | Full profile data |
| `leads/<id>/messages/` | GET | Lead message history |
| `leads/<id>/notes/` | GET, POST | Lead notes CRUD |
| `leads/<id>/add-to-campaign/` | POST | Add lead to campaign |
| `leads/<id>/campaigns/<cid>/state/` | GET, PATCH | Deal state management |

### Messages (2 endpoints)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `messages/` | GET | Global message list |
| `messages/<id>/` | GET | Message detail |

### Analytics (1 endpoint)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `analytics/overview/` | GET | Global analytics dashboard |

### Links/Tracking (3 endpoints)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `links/` | GET, POST | List/create tracked links |
| `links/<id>/` | GET, PATCH, DELETE | Link CRUD |
| `links/<id>/analytics/` | GET | Link click analytics |

### State Machine (2 endpoints)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `state-machine/simulate/` | POST | Global simulation |
| `state-machine/execute/` | POST | Execute state machine step |

### LinkedIn Credentials (7 endpoints)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `linkedin-credentials/` | GET, POST | List/create credentials |
| `linkedin-credentials/<id>/` | GET, PATCH, DELETE | Credential CRUD |
| `linkedin-credentials/<id>/verify/` | POST | Verify credentials work |
| `linkedin-credentials/<id>/confirm/` | POST | Confirm setup |
| `linkedin-credentials/<id>/rotate/` | POST | Rotate cookie/session |
| `linkedin-credentials/<id>/health/` | GET | Credential health check |
| `linkedin-credentials/<id>/logs/` | GET | Credential action logs |

### LinkedIn Profiles (3 endpoints)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `linkedin-profiles/` | GET, POST | List/create profiles |
| `linkedin-profiles/<id>/cookies/` | POST | Upload/verify cookies |
| `linkedin-profile-health/` | GET | Profile health status |

### LinkedIn Setup (3 endpoints)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `linkedin-setup/cookie-instructions/` | GET | Setup instructions |
| `linkedin-setup/guide/` | GET | Full setup guide |
| `linkedin-setup/status/` | GET | Setup completion status |

### Settings (3 endpoints)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `settings/` | GET, PATCH | SiteConfig CRUD |
| `settings/rate-limits/` | GET, PATCH | Rate limit config |
| `settings/daily-usage/` | GET | Daily action usage stats |

### Notifications (6 endpoints — currently in separate urls.py)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `notifications/` | GET | List notifications (filtered, paginated) |
| `notifications/` | POST | Mark all as read |
| `notifications/read-all/` | POST | Mark all as read (alternate) |
| `notifications/summary/` | GET | Unread count + last 10 |
| `notifications/<id>/` | GET, PATCH, DELETE | Single notification |
| `notifications/<id>/read/` | POST | Mark single as read |

### Real-Time (2 endpoints)
| Endpoint | Protocol | Description |
|----------|----------|-------------|
| `notifications/sse/` | SSE | Server-Sent Events stream |
| `ws/notifications/` | WebSocket | User notifications stream |
| `ws/campaigns/<id>/` | WebSocket | Campaign status stream |

### Health (1 endpoint)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `health/` | GET | System health check |

**Total: ~60 unique endpoints + 2 WebSocket routes + 1 SSE route**

---

## Phase 1: Complete MongoDB Data Layer (2-3 weeks)

### Status: ~30% Complete

You already have:
- ✅ `openoutreach/mongodb/connection.py` - MongoDB connection handler
- ✅ `openoutreach/mongodb/models.py` - Partial models (SupabaseUser, Lead, Campaign, Deal, Message, LinkedInProfile, etc.)
- ✅ `openoutreach/mongodb/migration.py` - Migration utilities
- ✅ `pymongo>=4.6.0` in requirements

### 1.1 Complete All MongoDB Models

**Action:** Add all missing models to `openoutreach/mongodb/models.py`

#### Task Model (Critical — daemon depends on this)

```python
class Task:
    """MongoDB Task model for queue management."""
    class TaskType:
        CONNECT = "connect"
        CHECK_PENDING = "check_pending"
        FOLLOW_UP = "follow_up"
        SEND_MANUAL_MESSAGE = "send_manual_message"
    
    class Status:
        PENDING = "pending"
        RUNNING = "running"
        COMPLETED = "completed"
        FAILED = "failed"
    
    def __init__(
        self,
        _id: Optional[str] = None,
        task_type: str = TaskType.CONNECT,
        status: str = Status.PENDING,
        scheduled_at: Optional[datetime] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        payload: Optional[Dict[str, Any]] = None,
        linkedin_profile_id: Optional[str] = None,
        error_message: Optional[str] = None,
        user_id: Optional[str] = None,
        created_at: Optional[datetime] = None,
    ):
        self._id = _id or str(uuid4())
        self.task_type = task_type
        self.status = status
        self.scheduled_at = scheduled_at or datetime.utcnow()
        self.started_at = started_at
        self.completed_at = completed_at
        self.payload = payload or {}
        self.linkedin_profile_id = linkedin_profile_id
        self.error_message = error_message
        self.user_id = user_id
        self.created_at = created_at or datetime.utcnow()

    # ... standard to_dict, from_dict, save, get, delete pattern
```

#### SiteConfig Model (Singleton per user)

```python
class SiteConfig:
    """MongoDB SiteConfig — per-user configuration (LLM, rate limits, active hours)."""
    
    class LLMProvider:
        OPENAI = "openai"
        ANTHROPIC = "anthropic"
        GOOGLE = "google"
        GROQ = "groq"
        MISTRAL = "mistral"
        COHERE = "cohere"
        OPENAI_COMPATIBLE = "openai_compatible"
    
    class AggressivenessPreset:
        VERY_SLOW = "very_slow"
        SLOW = "slow"
        AVERAGE = "average"
        AGGRESSIVE = "aggressive"
        VERY_AGGRESSIVE = "very_aggressive"
    
    def __init__(self, _id=None, user_id="", llm_provider="openai", llm_api_key="",
                 ai_model="", llm_api_base="", ai_writing_style="", ai_say_rules="",
                 ai_avoid_rules="", finder_api_key="", linkedin_username="",
                 linkedin_campaign="", enable_smart_rate_limiting=False,
                 aggressiveness_preset="average", daily_connection_limit=20,
                 daily_follow_up_limit=25, velocity=20, bettercontact_api_key="",
                 contacts_api_token="", contacts_api_url="",
                 enable_active_hours=True, active_start_hour=9, active_end_hour=19,
                 active_timezone="UTC", active_days="1,2,3,4,5", **kwargs):
        self._id = _id or str(uuid4())
        self.user_id = user_id
        # ... all fields
    
    @classmethod
    def load(cls, user_id: str) -> "SiteConfig":
        """Load or create config for a user."""
        collection = get_mongodb_collection("site_configs")
        data = collection.find_one({"user_id": user_id})
        if data:
            return cls.from_dict(data)
        config = cls(user_id=user_id)
        config.save()
        return config
```

#### Notification Model

```python
class Notification:
    """MongoDB Notification model — 7 notification types."""
    
    TYPE_CAMPAIGN_STARTED = "campaign_started"
    TYPE_CAMPAIGN_PAUSED = "campaign_paused"
    TYPE_CAMPAIGN_COMPLETED = "campaign_completed"
    TYPE_RATE_LIMIT_WARNING = "rate_limit_warning"
    TYPE_NEW_MESSAGE = "new_message"
    TYPE_CAMPAIGN_ERROR = "campaign_error"
    TYPE_SYSTEM_ANNOUNCEMENT = "system_announcement"
    
    def __init__(self, _id=None, recipient_id="", notification_type="",
                 title="", message="", campaign_id=None, deal_id=None,
                 is_read=False, read_at=None, data=None, created_at=None, **kwargs):
        self._id = _id or str(uuid4())
        self.recipient_id = recipient_id
        self.notification_type = notification_type
        self.title = title
        self.message = message
        self.campaign_id = campaign_id
        self.deal_id = deal_id
        self.is_read = is_read
        self.read_at = read_at
        self.data = data or {}
        self.created_at = created_at or datetime.utcnow()
    
    def mark_as_read(self):
        self.is_read = True
        self.read_at = datetime.utcnow()
        self.save()
    
    @classmethod
    def get_unread_count(cls, user_id: str) -> int:
        collection = get_mongodb_collection("notifications")
        return collection.count_documents({"recipient_id": user_id, "is_read": False})
```

#### ChatMessage Model

```python
class ChatMessage:
    """MongoDB ChatMessage — LinkedIn conversation messages."""
    
    def __init__(self, _id=None, deal_id="", content="", owner_id=None,
                 linkedin_urn="", is_outgoing=True, creation_date=None, **kwargs):
        self._id = _id or str(uuid4())
        self.deal_id = deal_id
        self.content = content
        self.owner_id = owner_id
        self.linkedin_urn = linkedin_urn
        self.is_outgoing = is_outgoing
        self.creation_date = creation_date or datetime.utcnow()
```

#### TrackedLink + LinkClick + LinkDealConversion

```python
class TrackedLink:
    """MongoDB TrackedLink — URL tracking with UTM parameters."""
    
    def __init__(self, _id=None, campaign_id=None, original_url="", short_code="",
                 is_active=True, utm_source="", utm_medium="", utm_campaign="",
                 utm_term="", utm_content="", total_clicks=0, unique_clicks=0,
                 created_at=None, last_clicked_at=None, user_id="", **kwargs):
        # ... all fields
        pass

class LinkClick:
    """Individual click record for analytics."""
    def __init__(self, _id=None, link_id="", ip_address=None, user_agent="",
                 referrer="", clicked_at=None, device_type="", country="", **kwargs):
        pass

class LinkDealConversion:
    """Link→Deal conversion attribution."""
    def __init__(self, _id=None, link_id="", click_id=None, deal_id="",
                 converted_at=None, **kwargs):
        pass
```

#### Note Model

```python
class Note:
    """MongoDB Note — notes on deals."""
    def __init__(self, _id=None, deal_id="", content="", created_by_id=None,
                 created_at=None, updated_at=None, **kwargs):
        pass
```

#### LeadPersona Model

```python
class LeadPersona:
    """MongoDB LeadPersona — LLM-generated persona for hyper-personalization."""
    def __init__(self, _id=None, lead_id="", campaign_id="", pain_points=None,
                 goals=None, messaging_preferences=None, buy_signals=None,
                 confidence_score=0.5, recommendations=None, generated_at=None,
                 last_updated=None, version=1, **kwargs):
        pass
```

#### CampaignTemplate Model

```python
class CampaignTemplate:
    """MongoDB CampaignTemplate — predefined campaign settings."""
    def __init__(self, _id=None, name="", description="", product_pitch="",
                 campaign_objective="", booking_link="", icp_titles=None,
                 follow_up_strategy="", ghost_mode_enabled=False, is_public=False,
                 created_by_id="", created_at=None, updated_at=None, **kwargs):
        pass
```

#### ActionLog Model

```python
class ActionLog:
    """MongoDB ActionLog — LinkedIn action tracking + activity feed."""
    class ActionType:
        CONNECT = "connect"
        CHECK_PENDING = "check_pending"
        FOLLOW_UP = "follow_up"
        SEND_MANUAL_MESSAGE = "send_manual_message"
        CAMPAIGN_PAUSED = "campaign_paused"
        CAMPAIGN_STARTED = "campaign_started"
        LEAD_DISCOVERED = "lead_discovered"
        LEAD_QUALIFIED = "lead_qualified"
        LEAD_DISQUALIFIED = "lead_disqualified"
    
    def __init__(self, _id=None, linkedin_profile_id=None, campaign_id="",
                 action_type="", created_at=None, details=None, status="",
                 error_message="", duration_ms=None, user_id="", **kwargs):
        pass
```

#### SearchKeyword Model

```python
class SearchKeyword:
    """MongoDB SearchKeyword — campaign search keywords."""
    def __init__(self, _id=None, campaign_id="", keyword="", used=False,
                 used_at=None, **kwargs):
        pass
```

#### State Machine Models

```python
class CampaignStateGraph:
    """Campaign workflow state machine definition."""
    def __init__(self, _id=None, campaign_id="", name="", description="",
                 is_active=True, graph_data=None, is_valid=False,
                 validation_errors=None, created_at=None, updated_at=None, **kwargs):
        pass

class StateNode:
    """Node in state machine graph."""
    TYPE_START = "start"
    TYPE_WAIT = "wait"
    TYPE_MESSAGE = "message"
    TYPE_GATE = "gate"
    TYPE_DECISION = "decision"
    TYPE_BRANCH = "branch"
    TYPE_WEBHOOK = "webhook"
    TYPE_END = "end"
    TYPE_LINK = "link"
    
    def __init__(self, _id=None, name="", node_type="", state_graph_id="",
                 config=None, x=0, y=0, is_active=True, description="",
                 created_at=None, updated_at=None, **kwargs):
        pass

class StateTransition:
    """Edge between state machine nodes."""
    def __init__(self, _id=None, source_node_id="", target_node_id="",
                 state_graph_id="", condition_type="always", condition_config=None,
                 label="", order=0, is_active=True, created_at=None, **kwargs):
        pass

class CampaignState:
    """Per-deal state machine execution tracker."""
    STATUS_ACTIVE = "active"
    STATUS_COMPLETED = "completed"
    STATUS_DROPPED = "dropped"
    STATUS_ERROR = "error"
    
    def __init__(self, _id=None, deal_id="", state_graph_id="",
                 current_node_id=None, previous_nodes=None, status="active",
                 error_message="", wait_until=None, wait_reason="",
                 metadata=None, started_at=None, completed_at=None, **kwargs):
        pass

class CampaignExecutionLog:
    """Step-by-step execution log for state machine."""
    def __init__(self, _id=None, state_machine_id="", node_id=None,
                 transition_id=None, action="", result=None, error="",
                 timestamp=None, **kwargs):
        pass
```

#### Health Models

```python
class CampaignHealthMetric:
    """Hourly campaign metrics snapshot."""
    def __init__(self, _id=None, campaign_id="", timestamp=None,
                 connections_sent=0, connections_accepted=0, connection_accept_rate=0.0,
                 messages_sent=0, messages_replied=0, response_rate=0.0,
                 errors_total=0, rate_limit_errors=0, auth_errors=0, network_errors=0,
                 deals_created=0, conversions=0, detectability_score=50,
                 created_at=None, **kwargs):
        pass

class HealthAlert:
    """Campaign health alert."""
    SEVERITY_LOW = "low"
    SEVERITY_MEDIUM = "medium"
    SEVERITY_HIGH = "high"
    SEVERITY_CRITICAL = "critical"
    
    def __init__(self, _id=None, campaign_id="", alert_type="", severity="medium",
                 message="", details=None, is_resolved=False, resolved_at=None,
                 resolution_notes="", auto_remediation_applied=False,
                 created_at=None, updated_at=None, **kwargs):
        pass

class RecoveryAction:
    """Auto-remediation action record."""
    def __init__(self, _id=None, campaign_id="", action_type="", before_state=None,
                 after_state=None, reason="", executed_at=None,
                 execution_result="", **kwargs):
        pass
```

#### Rate Limit Models

```python
class SmartRateLimitContext:
    """Per-profile contextual rate limiting state."""
    def __init__(self, _id=None, linkedin_profile_id="",
                 time_of_day_limit_multiplier=1.0, day_of_week_limit_multiplier=1.0,
                 detectability_score=50, last_detectability_update=None,
                 last_action_type="", last_action_at=None, consecutive_actions=0,
                 action_streak_reset_at=None, campaign_context=None,
                 created_at=None, updated_at=None, **kwargs):
        pass
    
    def get_effective_limit(self, action_type: str, campaign=None) -> int:
        """Calculate effective rate limit based on all context factors."""
        # Port logic from Django model
        pass
    
    def record_action(self, action_type: str):
        """Record action and update context (time multipliers, detectability)."""
        pass

class RateLimitWarning:
    """Rate limit violation warning log."""
    def __init__(self, _id=None, linkedin_profile_id="", action_type="",
                 limit_type="", limit_exceeded=0, actual_count=0,
                 warning_level="medium", at_time=None, resolved=False, **kwargs):
        pass
```

#### Ghost Mode Models

```python
class GhostCampaign:
    """Campaign in ghost/simulation mode."""
    class ModeType:
        SIMULATION = "simulation"
        VALIDATION = "validation"
        DRY_RUN = "dry_run"
    
    def __init__(self, _id=None, campaign_id="", name="", description="",
                 is_active=True, mode_type="simulation", test_seed_leads="",
                 test_keywords="", start_time=None, end_time=None,
                 leads_processed=0, connections_simulated=0, messages_simulated=0,
                 conversions_simulated=0, avg_rating=0.0, avg_score=0.0,
                 created_at=None, updated_at=None, **kwargs):
        pass

class GhostSimulationLog:
    """Individual ghost simulation run log."""
    def __init__(self, _id=None, ghost_campaign_id="", action_type="",
                 target_url="", target_name="", result_data=None, rating=None,
                 score=None, started_at=None, completed_at=None,
                 simulated_action=None, created_at=None, **kwargs):
        pass

class GhostTestScenario:
    """Reusable test scenarios for ghost mode."""
    def __init__(self, _id=None, name="", description="", test_cases=None,
                 is_public=False, created_by_id=None, runs_count=0,
                 avg_success_rate=0.0, created_at=None, updated_at=None, **kwargs):
        pass
```

#### Mailbox Model

```python
class Mailbox:
    """SMTP mailbox with daily send pacing."""
    def __init__(self, _id=None, host="smtp.gmail.com", port=587, username="",
                 password="", from_address="", daily_limit=50,
                 user_id="", **kwargs):
        pass
    
    def sent_today(self) -> int:
        """Count emails sent today by this mailbox."""
        collection = get_mongodb_collection("deals")
        midnight = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        return collection.count_documents({
            "mailbox_id": self._id,
            "email_sent_at": {"$gte": midnight}
        })
    
    def headroom_today(self) -> int:
        return max(0, self.daily_limit - self.sent_today())
```

### 1.2 Create Data Access Layer (DAL)

**Action:** Create `openoutreach/mongodb/dal.py`

```python
# openoutreach/mongodb/dal.py
"""
Data Access Layer for MongoDB.
Provides high-level CRUD, atomic operations, and query builders.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from pymongo import ASCENDING
from openoutreach.mongodb import models
from openoutreach.mongodb.connection import get_mongodb_collection

class TaskDAL:
    """Task queue operations (atomic claiming is critical)."""
    
    @staticmethod
    def create_task(task_type, linkedin_profile_id, payload, scheduled_at, user_id=None):
        task = models.Task(task_type=task_type, linkedin_profile_id=linkedin_profile_id,
                          payload=payload, scheduled_at=scheduled_at, user_id=user_id)
        task.save()
        return task
    
    @staticmethod
    def claim_next_task(linkedin_profile_id=None):
        """Atomic find-and-update to claim next pending task."""
        collection = get_mongodb_collection('tasks')
        if not collection:
            return None
        now = datetime.utcnow()
        query = {'status': 'pending', 'scheduled_at': {'$lte': now}}
        if linkedin_profile_id:
            query['linkedin_profile_id'] = linkedin_profile_id
        result = collection.find_one_and_update(
            query,
            {'$set': {'status': 'running', 'started_at': now}},
            sort=[('scheduled_at', ASCENDING)],
            return_document=True,
        )
        if result:
            return models.Task.from_dict(result)
        return None
    
    @staticmethod
    def mark_task_completed(task_id): ...
    @staticmethod
    def mark_task_failed(task_id, error_message): ...
    @staticmethod
    def get_pending_tasks_for_deal(deal_id, task_type): ...
    @staticmethod
    def get_pending_tasks_count(linkedin_profile_id=None): ...
    @staticmethod
    def cleanup_campaign_tasks(campaign_id):
        """Replace Django signal: delete tasks whose payload.campaign_id matches."""
        collection = get_mongodb_collection('tasks')
        collection.delete_many({"payload.campaign_id": campaign_id})

class CampaignDAL:
    @staticmethod
    def get_user_campaigns(user_id): ...
    @staticmethod
    def get_active_campaigns(user_id=None): ...
    @staticmethod
    def delete_campaign(campaign_id):
        """Delete campaign + cascade cleanup (replaces Django cascade + signal)."""
        # Delete tasks (replaces cleanup_campaign_tasks signal)
        TaskDAL.cleanup_campaign_tasks(campaign_id)
        # Delete deals
        get_mongodb_collection('deals').delete_many({"campaign_id": campaign_id})
        # Delete state graph + nodes + transitions
        graph = get_mongodb_collection('campaign_state_graphs').find_one({"campaign_id": campaign_id})
        if graph:
            get_mongodb_collection('state_nodes').delete_many({"state_graph_id": str(graph["_id"])})
            get_mongodb_collection('state_transitions').delete_many({"state_graph_id": str(graph["_id"])})
            get_mongodb_collection('campaign_state_graphs').delete_one({"_id": graph["_id"]})
        # Delete search keywords, action logs, health metrics, etc.
        get_mongodb_collection('search_keywords').delete_many({"campaign_id": campaign_id})
        get_mongodb_collection('action_logs').delete_many({"campaign_id": campaign_id})
        get_mongodb_collection('notifications').update_many(
            {"campaign_id": campaign_id}, {"$set": {"campaign_id": None}}
        )
        # Finally delete campaign
        get_mongodb_collection('campaigns').delete_one({"_id": campaign_id})

class DealDAL:
    @staticmethod
    def get_qualified_deals(campaign_id, limit=100): ...
    @staticmethod
    def get_deals_by_campaign(campaign_id): ...
    @staticmethod
    def set_deal_state(deal_id, new_state, reason=None): ...

class LeadDAL:
    @staticmethod
    def find_or_create_lead(linkedin_url, public_identifier, user_id): ...

class NotificationDAL:
    @staticmethod
    def create_notification(recipient_id, notification_type, title, message, **kwargs):
        """Create notification (replaces Django signal helper)."""
        notification = models.Notification(
            recipient_id=recipient_id,
            notification_type=notification_type,
            title=title,
            message=message,
            **kwargs
        )
        notification.save()
        return notification
    
    @staticmethod
    def get_unread(user_id, limit=50): ...
    @staticmethod
    def mark_all_read(user_id): ...

class ActionLogDAL:
    @staticmethod
    def create(linkedin_profile_id, campaign_id, action_type, details=None, user_id=None): ...
    @staticmethod
    def get_daily_count(linkedin_profile_id, action_type): ...

__all__ = ['TaskDAL', 'CampaignDAL', 'DealDAL', 'LeadDAL', 'NotificationDAL', 'ActionLogDAL']
```

### 1.3 Indexes for Performance

```python
# openoutreach/mongodb/indexes.py
def ensure_all_indexes():
    """Create all indexes needed for production performance."""
    from openoutreach.mongodb.connection import mongodb_connection
    
    # Users
    mongodb_connection.ensure_indexes('users', [
        ({'email': 1}, {'name': 'user_email_idx', 'unique': True}),
    ])
    
    # Tasks (critical for daemon)
    mongodb_connection.ensure_indexes('tasks', [
        ({'status': 1, 'scheduled_at': 1}, {'name': 'task_queue_idx'}),
        ({'linkedin_profile_id': 1, 'status': 1, 'scheduled_at': 1}, {'name': 'task_profile_queue_idx'}),
        ({'user_id': 1, 'status': 1}, {'name': 'task_user_status_idx'}),
        ({'payload.campaign_id': 1}, {'name': 'task_campaign_idx'}),
        ({'payload.deal_id': 1, 'task_type': 1, 'status': 1}, {'name': 'task_deal_type_idx'}),
    ])
    
    # Campaigns
    mongodb_connection.ensure_indexes('campaigns', [
        ({'user_id': 1}, {'name': 'campaign_user_idx'}),
        ({'linkedin_profile_id': 1}, {'name': 'campaign_profile_idx'}),
        ({'status': 1}, {'name': 'campaign_status_idx'}),
    ])
    
    # Deals
    mongodb_connection.ensure_indexes('deals', [
        ({'campaign_id': 1, 'state': 1}, {'name': 'deal_campaign_state_idx'}),
        ({'lead_id': 1}, {'name': 'deal_lead_idx'}),
        ({'user_id': 1}, {'name': 'deal_user_idx'}),
        ({'lead_id': 1, 'campaign_id': 1}, {'name': 'deal_lead_campaign_unique', 'unique': True}),
        ({'mailbox_id': 1, 'email_sent_at': 1}, {'name': 'deal_mailbox_sent_idx'}),
    ])
    
    # Leads
    mongodb_connection.ensure_indexes('leads', [
        ({'public_identifier': 1}, {'name': 'lead_public_id_idx', 'unique': True}),
        ({'linkedin_url': 1}, {'name': 'lead_url_idx'}),
        ({'user_id': 1}, {'name': 'lead_user_idx'}),
    ])
    
    # LinkedInProfiles
    mongodb_connection.ensure_indexes('linkedin_profiles', [
        ({'user_id': 1}, {'name': 'profile_user_idx'}),
        ({'linkedin_username': 1}, {'name': 'profile_username_idx'}),
    ])
    
    # ActionLogs
    mongodb_connection.ensure_indexes('action_logs', [
        ({'linkedin_profile_id': 1, 'action_type': 1, 'created_at': -1}, {'name': 'action_profile_type_time_idx'}),
        ({'campaign_id': 1, 'created_at': -1}, {'name': 'action_campaign_time_idx'}),
        ({'status': 1, 'created_at': -1}, {'name': 'action_status_time_idx'}),
    ])
    
    # ChatMessages
    mongodb_connection.ensure_indexes('chat_messages', [
        ({'deal_id': 1, 'creation_date': -1}, {'name': 'message_deal_time_idx'}),
        ({'deal_id': 1, 'linkedin_urn': 1}, {'name': 'message_deal_urn_unique', 'unique': True}),
    ])
    
    # Notifications
    mongodb_connection.ensure_indexes('notifications', [
        ({'recipient_id': 1, 'is_read': 1}, {'name': 'notification_recipient_read_idx'}),
        ({'created_at': -1}, {'name': 'notification_time_idx'}),
        ({'recipient_id': 1, 'created_at': -1}, {'name': 'notification_recipient_time_idx'}),
    ])
    
    # TrackedLinks
    mongodb_connection.ensure_indexes('tracked_links', [
        ({'short_code': 1}, {'name': 'link_shortcode_unique', 'unique': True}),
        ({'campaign_id': 1}, {'name': 'link_campaign_idx'}),
    ])
    
    # LinkClicks
    mongodb_connection.ensure_indexes('link_clicks', [
        ({'link_id': 1, 'clicked_at': -1}, {'name': 'click_link_time_idx'}),
    ])
    
    # SearchKeywords
    mongodb_connection.ensure_indexes('search_keywords', [
        ({'campaign_id': 1, 'keyword': 1}, {'name': 'keyword_campaign_unique', 'unique': True}),
        ({'campaign_id': 1, 'used': 1}, {'name': 'keyword_unused_idx'}),
    ])
    
    # State Machine
    mongodb_connection.ensure_indexes('campaign_state_graphs', [
        ({'campaign_id': 1}, {'name': 'graph_campaign_unique', 'unique': True}),
    ])
    mongodb_connection.ensure_indexes('state_nodes', [
        ({'state_graph_id': 1}, {'name': 'node_graph_idx'}),
    ])
    mongodb_connection.ensure_indexes('campaign_states', [
        ({'deal_id': 1, 'status': 1}, {'name': 'state_deal_status_idx'}),
        ({'state_graph_id': 1, 'status': 1}, {'name': 'state_graph_status_idx'}),
    ])
    
    # Health
    mongodb_connection.ensure_indexes('campaign_health_metrics', [
        ({'campaign_id': 1, 'timestamp': -1}, {'name': 'health_campaign_time_idx'}),
    ])
    mongodb_connection.ensure_indexes('health_alerts', [
        ({'campaign_id': 1, 'is_resolved': 1}, {'name': 'alert_campaign_resolved_idx'}),
    ])
    
    # Rate Limits
    mongodb_connection.ensure_indexes('smart_rate_limit_contexts', [
        ({'linkedin_profile_id': 1}, {'name': 'rate_limit_profile_unique', 'unique': True}),
    ])
    mongodb_connection.ensure_indexes('rate_limit_warnings', [
        ({'linkedin_profile_id': 1, 'at_time': -1}, {'name': 'warning_profile_time_idx'}),
    ])
    
    # Site Config
    mongodb_connection.ensure_indexes('site_configs', [
        ({'user_id': 1}, {'name': 'config_user_unique', 'unique': True}),
    ])
    
    # Lead Personas
    mongodb_connection.ensure_indexes('lead_personas', [
        ({'lead_id': 1, 'campaign_id': 1}, {'name': 'persona_lead_campaign_unique', 'unique': True}),
    ])
    
    # Notes
    mongodb_connection.ensure_indexes('notes', [
        ({'deal_id': 1, 'created_at': -1}, {'name': 'note_deal_time_idx'}),
    ])
```

### 1.4 Encryption Layer (Django-independent)

**Action:** Port `openoutreach/core/crypto.py` to not depend on Django settings:

```python
# openoutreach/crypto.py (NEW — no Django dependency)
"""
Fernet (AES-256) encryption utilities.
Uses COOKIE_ENCRYPTION_KEY or derives from SECRET_KEY env var.
"""
import base64
import hashlib
import os
from cryptography.fernet import Fernet

def get_fernet_key() -> bytes:
    """Get Fernet key from environment (no Django dependency)."""
    key = os.environ.get("COOKIE_ENCRYPTION_KEY")
    if key:
        return key.encode("utf-8") if isinstance(key, str) else key
    secret = os.environ.get("SECRET_KEY")
    if not secret:
        raise RuntimeError("No COOKIE_ENCRYPTION_KEY or SECRET_KEY in environment")
    h = hashlib.sha256()
    h.update(secret.encode("utf-8"))
    h.update(b"openoutreach-cookie-salt")
    return base64.urlsafe_b64encode(h.digest())

def encrypt_text(text: str) -> str:
    f = Fernet(get_fernet_key())
    token = f.encrypt(text.encode("utf-8"))
    return base64.urlsafe_b64encode(token).decode("utf-8")

def decrypt_text(encoded_token: str) -> str:
    f = Fernet(get_fernet_key())
    token = base64.urlsafe_b64decode(encoded_token.encode("utf-8"))
    return f.decrypt(token).decode("utf-8")
```

### 1.5 Dual-Write Mode & Data Migration

Same as before — enable dual-write from Django signals, run `migrate_mongodb` command, verify counts match.

### Deliverables for Phase 1:
- ✅ All 32 Django models have MongoDB equivalents
- ✅ Data Access Layer (DAL) with query builders + atomic operations
- ✅ Encryption layer ported (Django-independent)
- ✅ All indexes created (37 indexes across 18 collections)
- ✅ Dual-write enabled
- ✅ Data migrated + verified
- ✅ Test suite passing

---

## Phase 2: Migrate APIs to FastAPI (3-4 weeks)

### 2.1 FastAPI App Structure

```
openoutreach/
├── api_v2/                    # NEW: FastAPI app
│   ├── __init__.py
│   ├── main.py                # FastAPI entry point
│   ├── dependencies.py        # Auth + common deps
│   ├── middleware.py           # CORS, logging
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py            # Login/register/Supabase
│   │   ├── campaigns.py       # All campaign endpoints
│   │   ├── campaign_templates.py
│   │   ├── leads.py           # Lead management
│   │   ├── messages.py        # Chat messages
│   │   ├── analytics.py       # Analytics overview
│   │   ├── links.py           # Link tracking
│   │   ├── state_machine.py   # State machine CRUD + execution
│   │   ├── linkedin_credentials.py
│   │   ├── linkedin_profiles.py
│   │   ├── linkedin_setup.py
│   │   ├── notifications.py   # Notification REST + SSE
│   │   ├── settings.py        # SiteConfig
│   │   ├── health.py          # System health
│   │   └── websocket.py       # WebSocket endpoints
│   └── schemas/               # Pydantic models
│       ├── __init__.py
│       ├── auth.py
│       ├── campaign.py
│       ├── lead.py
│       ├── deal.py
│       ├── message.py
│       ├── notification.py
│       ├── link.py
│       ├── state_machine.py
│       ├── linkedin.py
│       └── settings.py
```

### 2.2 Auth Dependency (Supabase + Local JWT)

**Critical:** Your current auth is Supabase JWT first, with JWKS verification. The FastAPI dependency must replicate this.

```python
# openoutreach/api_v2/dependencies.py
"""
FastAPI Dependencies — Auth supports both Supabase JWT and local JWT.
"""
import os
import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError, jwk
from typing import Optional

from openoutreach.mongodb import models

security = HTTPBearer()

# Settings
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")

# JWKS cache
_jwks_cache = None

async def _fetch_supabase_jwks():
    """Fetch JWKS from Supabase for RS256/ES256 verification."""
    global _jwks_cache
    if _jwks_cache:
        return _jwks_cache
    
    urls_to_try = [
        f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json",
        f"{SUPABASE_URL}/.well-known/jwks.json",
    ]
    
    async with httpx.AsyncClient() as client:
        for url in urls_to_try:
            try:
                resp = await client.get(url, timeout=5.0)
                if resp.status_code == 200:
                    _jwks_cache = resp.json()
                    return _jwks_cache
            except Exception:
                continue
    return None

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """
    Extract and validate JWT token, return user_id.
    
    Supports:
    1. Supabase JWT (HS256 with service key, or RS256/ES256 with JWKS)
    2. Local JWT (HS256 with JWT_SECRET_KEY)
    
    On first Supabase login, creates/links user in MongoDB.
    """
    token = credentials.credentials
    
    try:
        # Decode header to determine algorithm
        unverified_header = jwt.get_unverified_header(token)
        algorithm = unverified_header.get("alg", "HS256")
        
        payload = None
        
        # Try Supabase HS256 (service key)
        if algorithm == "HS256" and SUPABASE_SERVICE_KEY:
            try:
                payload = jwt.decode(token, SUPABASE_SERVICE_KEY, algorithms=["HS256"],
                                    options={"verify_aud": False})
            except JWTError:
                pass
        
        # Try local JWT
        if payload is None and algorithm == "HS256" and JWT_SECRET_KEY:
            try:
                payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
            except JWTError:
                pass
        
        # Try Supabase RS256/ES256 with JWKS
        if payload is None and algorithm in ("RS256", "ES256"):
            jwks_data = await _fetch_supabase_jwks()
            if jwks_data:
                kid = unverified_header.get("kid")
                for key_data in jwks_data.get("keys", []):
                    if key_data.get("kid") == kid:
                        public_key = jwk.construct(key_data)
                        payload = jwt.decode(token, public_key, algorithms=[algorithm],
                                           options={"verify_aud": False})
                        break
        
        if payload is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Extract user info
        sub = payload.get("sub")  # Supabase user ID or local user ID
        email = payload.get("email", "")
        
        if not sub:
            raise HTTPException(status_code=401, detail="Token missing 'sub' claim")
        
        # Check if this is a Supabase token (has 'aud' or 'role' claims)
        if payload.get("aud") or payload.get("role"):
            # Supabase token — get or create local user
            user = models.User.get_by_supabase_id(sub)
            if not user:
                user = models.User(
                    email=email,
                    full_name=payload.get("user_metadata", {}).get("full_name", ""),
                    supabase_user_id=sub,
                    is_active=True,
                )
                user.save()
            return user._id
        else:
            # Local JWT — sub IS the user_id
            user = models.User.get(sub)
            if not user or not user.is_active:
                raise HTTPException(status_code=401, detail="User not found or inactive")
            return user._id
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")

async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
) -> Optional[str]:
    """Optional auth — returns None if no token."""
    if credentials is None:
        return None
    return await get_current_user(credentials)
```

### 2.3 Real-Time: WebSocket + SSE Replacements

**Action:** Replace Django Channels with native FastAPI WebSocket + SSE

```python
# openoutreach/api_v2/routers/websocket.py
"""
WebSocket endpoints — replaces Django Channels consumers.
Uses Redis pub/sub for multi-process message delivery.
"""
import asyncio
import json
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Dict, Set
import redis.asyncio as aioredis

router = APIRouter()

# Connection manager (in-memory for single-process; use Redis pub/sub for multi-process)
class ConnectionManager:
    def __init__(self):
        # user_id -> set of WebSocket connections
        self.user_connections: Dict[str, Set[WebSocket]] = {}
        # campaign_id -> set of WebSocket connections
        self.campaign_connections: Dict[str, Set[WebSocket]] = {}
    
    async def connect_user(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(websocket)
    
    async def connect_campaign(self, websocket: WebSocket, campaign_id: str):
        await websocket.accept()
        if campaign_id not in self.campaign_connections:
            self.campaign_connections[campaign_id] = set()
        self.campaign_connections[campaign_id].add(websocket)
    
    async def disconnect_user(self, websocket: WebSocket, user_id: str):
        self.user_connections.get(user_id, set()).discard(websocket)
    
    async def disconnect_campaign(self, websocket: WebSocket, campaign_id: str):
        self.campaign_connections.get(campaign_id, set()).discard(websocket)
    
    async def send_to_user(self, user_id: str, data: dict):
        connections = self.user_connections.get(user_id, set())
        dead = set()
        for ws in connections:
            try:
                await ws.send_json(data)
            except Exception:
                dead.add(ws)
        connections -= dead
    
    async def send_to_campaign(self, campaign_id: str, data: dict):
        connections = self.campaign_connections.get(campaign_id, set())
        dead = set()
        for ws in connections:
            try:
                await ws.send_json(data)
            except Exception:
                dead.add(ws)
        connections -= dead

manager = ConnectionManager()

@router.websocket("/ws/notifications/")
async def notification_websocket(websocket: WebSocket, token: str = Query(...)):
    """
    WebSocket endpoint for user notifications.
    Replaces Django NotificationConsumer.
    
    Connect: ws://host/ws/notifications/?token=<jwt>
    Receives: notification_message, notification_broadcast
    Sends: ping → pong, mark_read → ack
    """
    # Authenticate
    from openoutreach.api_v2.dependencies import get_current_user
    from fastapi.security import HTTPAuthorizationCredentials
    
    try:
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        user_id = await get_current_user(creds)
    except Exception:
        await websocket.close(code=4001)
        return
    
    await manager.connect_user(websocket, user_id)
    await websocket.send_json({"type": "connected", "user_id": user_id})
    
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            elif msg_type == "mark_read":
                notification_id = data.get("notification_id")
                if notification_id:
                    from openoutreach.mongodb import models
                    notif = models.Notification.get(notification_id)
                    if notif and notif.recipient_id == user_id:
                        notif.mark_as_read()
                        await websocket.send_json({"type": "mark_read_ack", "notification_id": notification_id})
    except WebSocketDisconnect:
        await manager.disconnect_user(websocket, user_id)

@router.websocket("/ws/campaigns/{campaign_id}/")
async def campaign_status_websocket(websocket: WebSocket, campaign_id: str, token: str = Query(...)):
    """
    WebSocket endpoint for campaign status updates.
    Replaces Django CampaignStatusConsumer.
    
    Connect: ws://host/ws/campaigns/<id>/?token=<jwt>
    Receives: campaign_status_update, campaign_error
    """
    from openoutreach.api_v2.dependencies import get_current_user
    from fastapi.security import HTTPAuthorizationCredentials
    from openoutreach.mongodb import models
    
    try:
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        user_id = await get_current_user(creds)
    except Exception:
        await websocket.close(code=4001)
        return
    
    # Verify user has access to this campaign
    campaign = models.Campaign.get(campaign_id)
    if not campaign or campaign.user_id != user_id:
        await websocket.close(code=4003)
        return
    
    await manager.connect_campaign(websocket, campaign_id)
    await websocket.send_json({"type": "connected", "campaign_id": campaign_id})
    
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        await manager.disconnect_campaign(websocket, campaign_id)


# === Emit helpers (called from services/daemon) ===

async def emit_notification_to_user(user_id: str, notification_data: dict):
    """Send notification to user via WebSocket (replaces Django Channels emit)."""
    await manager.send_to_user(user_id, {
        "type": "notification_message",
        "data": {**notification_data, "timestamp": datetime.utcnow().isoformat()},
    })

async def emit_campaign_status_update(campaign_id: str, status: str, message: str = None):
    """Send campaign status update via WebSocket."""
    data = {"type": "campaign_status_update", "data": {
        "campaign_id": campaign_id, "status": status,
        "timestamp": datetime.utcnow().isoformat(),
    }}
    if message:
        data["data"]["message"] = message
    await manager.send_to_campaign(campaign_id, data)

async def emit_campaign_error(campaign_id: str, error_message: str, deal_id: str = None):
    """Send campaign error via WebSocket."""
    data = {"type": "campaign_error", "data": {
        "campaign_id": campaign_id, "error_message": error_message,
        "timestamp": datetime.utcnow().isoformat(),
    }}
    if deal_id:
        data["data"]["deal_id"] = deal_id
    await manager.send_to_campaign(campaign_id, data)
```

**SSE Endpoint (fallback):**

```python
# openoutreach/api_v2/routers/notifications.py (SSE section)
from fastapi import Request
from fastapi.responses import StreamingResponse

@router.get("/sse/")
async def sse_notification_stream(request: Request, user_id: str = Depends(get_current_user)):
    """
    Server-Sent Events endpoint for notifications (browser fallback).
    Replaces Django StreamingHttpResponse SSE.
    """
    async def event_generator():
        yield f"data: {json.dumps({'type': 'connected', 'user_id': user_id})}\n\n"
        
        # Poll for new notifications every 5 seconds
        last_check = datetime.utcnow()
        while True:
            await asyncio.sleep(5)
            
            # Check for new notifications since last check
            collection = get_mongodb_collection("notifications")
            new_notifs = list(collection.find({
                "recipient_id": user_id,
                "created_at": {"$gt": last_check},
            }).sort("created_at", -1).limit(10))
            
            for notif in new_notifs:
                yield f"data: {json.dumps({'type': 'notification', 'data': notif})}\n\n"
            
            last_check = datetime.utcnow()
            
            # Keepalive
            yield ": keepalive\n\n"
            
            # Check if client disconnected
            if await request.is_disconnected():
                break
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

### 2.4 Django Signal Replacements

The 3 Django signals become explicit service-layer calls:

| Django Signal | Trigger | FastAPI Replacement |
|---------------|---------|---------------------|
| `cleanup_campaign_tasks` (pre_delete Campaign) | Campaign deletion | `CampaignDAL.delete_campaign()` cascade logic |
| `create_new_message_notification` (post_save ChatMessage) | New inbound message | Call `NotificationService.on_new_message()` after message creation |
| `create_action_error_notification` (post_save ActionLog) | ActionLog with error | Call `NotificationService.on_action_error()` after action log creation |

```python
# openoutreach/api_v2/services/notifications.py
"""
Notification Service — replaces Django signals for notification creation.
Called explicitly from endpoints/daemon after relevant events.
"""
from openoutreach.mongodb.dal import NotificationDAL
from openoutreach.mongodb import models

class NotificationService:
    @staticmethod
    async def on_new_message(chat_message: models.ChatMessage, campaign: models.Campaign):
        """Called after new inbound ChatMessage is created. Replaces post_save signal."""
        if chat_message.is_outgoing:
            return  # Only notify on inbound
        
        # Notify campaign owner (in multi-tenant, user_id)
        deal = models.Deal.get(chat_message.deal_id)
        if not deal or not campaign:
            return
        
        notification = NotificationDAL.create_notification(
            recipient_id=campaign.user_id,
            notification_type=models.Notification.TYPE_NEW_MESSAGE,
            title=f"New message in '{campaign.name}'",
            message=chat_message.content[:100],
            campaign_id=campaign._id,
            deal_id=deal._id,
            data={"message_id": chat_message._id},
        )
        
        # Real-time delivery
        from openoutreach.api_v2.routers.websocket import emit_notification_to_user
        await emit_notification_to_user(campaign.user_id, {
            "notification_id": notification._id,
            "notification_type": models.Notification.TYPE_NEW_MESSAGE,
            "title": notification.title,
            "message": notification.message,
        })
    
    @staticmethod
    async def on_action_error(action_log: models.ActionLog):
        """Called after ActionLog with error is created. Replaces post_save signal."""
        if not action_log.error_message:
            return
        
        campaign = models.Campaign.get(action_log.campaign_id)
        if not campaign:
            return
        
        NotificationDAL.create_notification(
            recipient_id=campaign.user_id,
            notification_type=models.Notification.TYPE_CAMPAIGN_ERROR,
            title=f"Error in '{campaign.name}'",
            message=action_log.error_message[:200],
            campaign_id=campaign._id,
        )
        
        from openoutreach.api_v2.routers.websocket import emit_campaign_error
        await emit_campaign_error(campaign._id, action_log.error_message)
    
    @staticmethod
    async def on_campaign_status_change(campaign: models.Campaign, status_change: str):
        """Called from campaign status endpoint. Replaces manual signal call."""
        type_map = {
            "started": models.Notification.TYPE_CAMPAIGN_STARTED,
            "paused": models.Notification.TYPE_CAMPAIGN_PAUSED,
            "completed": models.Notification.TYPE_CAMPAIGN_COMPLETED,
        }
        notification_type = type_map.get(status_change)
        if not notification_type:
            return
        
        NotificationDAL.create_notification(
            recipient_id=campaign.user_id,
            notification_type=notification_type,
            title=f"Campaign '{campaign.name}' {status_change}",
            message=f"Campaign '{campaign.name}' has been {status_change}.",
            campaign_id=campaign._id,
        )
        
        from openoutreach.api_v2.routers.websocket import emit_campaign_status_update
        await emit_campaign_status_update(campaign._id, status_change)
```

### 2.5 File Upload (CSV Leads)

```python
# openoutreach/api_v2/routers/campaigns.py (upload section)
from fastapi import UploadFile, File
import csv
import io

@router.post("/{campaign_id}/leads/upload/")
async def upload_campaign_leads(
    campaign_id: str,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
):
    """
    Upload CSV file with leads to add to campaign.
    Replaces Django CampaignLeadsUploadView.
    """
    campaign = models.Campaign.get(campaign_id)
    if not campaign or campaign.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    content = await file.read()
    text = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    
    added = 0
    for row in reader:
        linkedin_url = row.get("linkedin_url", "").strip()
        public_identifier = row.get("public_identifier", "").strip()
        if not linkedin_url and not public_identifier:
            continue
        
        lead, created = LeadDAL.find_or_create_lead(
            linkedin_url=linkedin_url,
            public_identifier=public_identifier,
            user_id=user_id,
        )
        # Create deal linking lead to campaign
        DealDAL.find_or_create_deal(lead._id, campaign_id, user_id)
        added += 1
    
    return {"added": added, "campaign_id": campaign_id}
```

### 2.6 ML Model Blob Storage

```python
# Campaign model update — store model_blob as Binary in MongoDB
import bson

class Campaign:
    def __init__(self, ..., model_blob: Optional[bytes] = None, ...):
        self.model_blob = model_blob  # scikit-learn model bytes
    
    def to_dict(self):
        doc = {... all fields ...}
        if self.model_blob:
            doc["model_blob"] = bson.Binary(self.model_blob)
        return doc
    
    @classmethod
    def from_dict(cls, data):
        model_blob = data.get("model_blob")
        if isinstance(model_blob, bson.Binary):
            model_blob = bytes(model_blob)
        return cls(..., model_blob=model_blob, ...)
```

### 2.7 All Routers Implementation Order

Port in this order (dependencies flow downward):

1. **`health.py`** — Simple, no dependencies
2. **`auth.py`** — Register, login, Supabase verify, /me
3. **`settings.py`** — SiteConfig CRUD, rate limits, daily usage
4. **`linkedin_profiles.py`** — Profile list, cookie upload
5. **`linkedin_credentials.py`** — Credential CRUD, verify, rotate, health
6. **`linkedin_setup.py`** — Setup guide, status
7. **`campaigns.py`** — Full CRUD + leads + upload + messages + analytics + activity + status
8. **`campaign_templates.py`** — Template CRUD, clone, create-from-template
9. **`leads.py`** — List, detail, profile, messages, notes, add-to-campaign, deal-state
10. **`messages.py`** — Global message list/detail
11. **`analytics.py`** — Overview dashboard
12. **`links.py`** — TrackedLink CRUD + click analytics
13. **`state_machine.py`** — Graph CRUD, validate, simulate, execute
14. **`notifications.py`** — REST endpoints + SSE
15. **`websocket.py`** — WS notification + campaign status

### 2.8 FastAPI Main App

```python
# openoutreach/api_v2/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from openoutreach.api_v2.routers import (
    auth, campaigns, campaign_templates, leads, messages,
    analytics, links, state_machine, linkedin_credentials,
    linkedin_profiles, linkedin_setup, notifications,
    settings, health, websocket,
)

app = FastAPI(
    title="OpenOutreach API",
    description="LinkedIn Automation Platform",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST routers
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(campaigns.router, prefix="/api/campaigns", tags=["campaigns"])
app.include_router(campaign_templates.router, prefix="/api/campaign-templates", tags=["templates"])
app.include_router(leads.router, prefix="/api/leads", tags=["leads"])
app.include_router(messages.router, prefix="/api/messages", tags=["messages"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(links.router, prefix="/api/links", tags=["links"])
app.include_router(state_machine.router, prefix="/api/state-machine", tags=["state-machine"])
app.include_router(linkedin_credentials.router, prefix="/api/linkedin-credentials", tags=["linkedin"])
app.include_router(linkedin_profiles.router, prefix="/api/linkedin-profiles", tags=["linkedin"])
app.include_router(linkedin_setup.router, prefix="/api/linkedin-setup", tags=["linkedin"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])

# WebSocket routers
app.include_router(websocket.router, tags=["websocket"])

@app.on_event("startup")
async def startup():
    from openoutreach.mongodb.connection import initialize_mongodb_connection
    from openoutreach.mongodb.indexes import ensure_all_indexes
    initialize_mongodb_connection()
    ensure_all_indexes()
```

### 2.9 Frontend Migration

**Key principle:** Keep the same `/api/` prefix so frontend changes are minimal.

```typescript
// frontend/src/lib/api-client.ts
// Only change: point BASE_URL at FastAPI (same path structure)
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api';

// All existing fetch calls keep working because endpoints match!
// e.g. /api/campaigns/, /api/leads/, etc.
```

**Frontend Auth update:**

```typescript
// frontend/src/lib/auth.ts
// Works with both Supabase and local JWT
export function getAuthHeaders(): Record<string, string> {
    // Try Supabase session first
    const supabaseToken = getSupabaseAccessToken();
    if (supabaseToken) {
        return { 'Authorization': `Bearer ${supabaseToken}` };
    }
    // Fall back to local JWT
    const localToken = localStorage.getItem('auth_token');
    if (localToken) {
        return { 'Authorization': `Bearer ${localToken}` };
    }
    return {};
}
```

### Deliverables for Phase 2:
- ✅ All 60+ endpoints ported to FastAPI
- ✅ WebSocket (2 routes) + SSE endpoint working
- ✅ Supabase + local JWT auth
- ✅ File upload (CSV leads)
- ✅ Django signal logic moved to service layer
- ✅ Frontend pointing at FastAPI
- ✅ Integration tests passing

---

## Phase 3: Remove Django & Port Daemon (1-2 weeks)

### 3.1 Port Daemon to Pure Python

```python
# openoutreach/daemon/main.py
"""OpenOutreach Daemon — pure Python, no Django."""
import asyncio
import logging
from openoutreach.settings import settings
from openoutreach.mongodb.dal import TaskDAL, CampaignDAL
from openoutreach.mongodb import models
from openoutreach.daemon.handlers import TASK_HANDLERS
from openoutreach.daemon.scheduler import reconcile
from openoutreach.api_v2.services.notifications import NotificationService

class Daemon:
    def __init__(self):
        self.session_pool: dict[str, "AccountSession"] = {}
        self.running = False
    
    async def run(self):
        self.running = True
        while self.running:
            task = TaskDAL.claim_next_task()
            if task is None:
                await reconcile()
                await asyncio.sleep(60)
                continue
            
            try:
                await self.execute_task(task)
                TaskDAL.mark_task_completed(task._id)
            except Exception as e:
                TaskDAL.mark_task_failed(task._id, str(e))
                # Trigger error notification (replaces Django signal)
                action_log = models.ActionLog(
                    linkedin_profile_id=task.linkedin_profile_id,
                    campaign_id=task.payload.get("campaign_id", ""),
                    action_type=task.task_type,
                    error_message=str(e),
                    user_id=task.user_id,
                )
                action_log.save()
                await NotificationService.on_action_error(action_log)
            
            await asyncio.sleep(2)
```

### 3.2 Pydantic Settings (replaces Django settings)

```python
# openoutreach/settings.py
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # MongoDB
    MONGODB_URI: str = ""
    MONGODB_NAME: str = "openoutreach"
    
    # Auth
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    
    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    
    # Encryption
    SECRET_KEY: str = ""
    COOKIE_ENCRYPTION_KEY: Optional[str] = None
    
    # Browser
    BROWSER_HEADLESS: bool = True
    
    # Server
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8001
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    # Redis (optional — for multi-process WebSocket pub/sub)
    REDIS_URL: Optional[str] = None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
```

### 3.3 Click CLI (replaces manage.py)

```python
# openoutreach/cli.py
import click
import asyncio

@click.group()
def cli():
    """OpenOutreach CLI"""
    pass

@cli.command()
def rundaemon():
    """Run the task daemon."""
    from openoutreach.daemon.main import main
    asyncio.run(main())

@cli.command()
@click.option('--host', default='0.0.0.0')
@click.option('--port', default=8001)
def runserver(host, port):
    """Run the FastAPI server."""
    import uvicorn
    uvicorn.run("openoutreach.api_v2.main:app", host=host, port=port, reload=True)

@cli.command()
def migrate():
    """Migrate data from SQLite to MongoDB."""
    from openoutreach.mongodb.migration import MigrationManager
    manager = MigrationManager()
    results = manager.migrate_all()
    click.echo(f"Migrated {results['migrated']} records")

@cli.command()
def ensure_indexes():
    """Create all MongoDB indexes."""
    from openoutreach.mongodb.indexes import ensure_all_indexes
    ensure_all_indexes()
    click.echo("All indexes created")

@cli.command()
def shell():
    """Interactive shell."""
    import code
    from openoutreach.mongodb import models
    code.interact(local={'models': models})

if __name__ == '__main__':
    cli()
```

### 3.4 Remove Django

```bash
# Delete Django-specific files
rm manage.py
rm -rf openoutreach/core/migrations/
rm -rf openoutreach/crm/migrations/
rm -rf openoutreach/linkedin/migrations/
rm -rf openoutreach/chat/migrations/
rm -rf openoutreach/emails/migrations/
rm -rf openoutreach/notifications/migrations/
rm -rf openoutreach/api/  # Old DRF views
rm -rf openoutreach/settings/  # Old Django settings dir
rm openoutreach/wsgi.py
rm openoutreach/urls.py
rm openoutreach/routing.py  # Old Django Channels routing
```

### 3.5 Final requirements.txt

```txt
# Core
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
pydantic>=2.10.0
pydantic-settings>=2.7.0
python-multipart>=0.0.20

# MongoDB
pymongo>=4.6.0
motor>=3.6.0

# Auth
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
httpx>=0.27.0

# Encryption
cryptography>=39.0.0

# CLI
click>=8.1.0

# Browser automation
playwright>=1.59
playwright-stealth

# LLM
pydantic-ai-slim[openai,anthropic,google,groq,mistral,cohere,bedrock]

# ML
scikit-learn>=1.3.0
pandas

# Templates
jinja2

# Utilities
pytz
psutil
termcolor

# Redis (optional, for multi-process WebSocket)
redis>=5.0.0

# NO DJANGO DEPENDENCIES
```

### 3.6 Docker (simplified)

```dockerfile
FROM mcr.microsoft.com/playwright/python:v1.59.0-focal
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY openoutreach/ openoutreach/
RUN pip install -e .
```

```yaml
# docker-compose.yml
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
```

### Deliverables for Phase 3:
- ✅ Daemon runs without Django
- ✅ Click CLI replaces manage.py
- ✅ Pydantic Settings replaces Django settings
- ✅ All Django code removed
- ✅ Docker simplified
- ✅ Requirements cleaned (no Django)
- ✅ Production deployment working

---

## Migration Checklist

### Phase 1: MongoDB Data Layer (2-3 weeks)
- [ ] Complete all 32 MongoDB models
- [ ] Create Data Access Layer (dal.py)
- [ ] Port encryption layer (no Django dependency)
- [ ] Create all indexes (37 indexes, 18 collections)
- [ ] Enable dual-write
- [ ] Migrate existing data
- [ ] Verify migration (count match)
- [ ] Test suite for MongoDB models

### Phase 2: FastAPI APIs (3-4 weeks)
- [ ] FastAPI app structure + main.py
- [ ] Auth dependency (Supabase + local JWT)
- [ ] Port auth endpoints (8)
- [ ] Port settings endpoints (3)
- [ ] Port campaign endpoints (12)
- [ ] Port campaign template endpoints (4)
- [ ] Port lead endpoints (7)
- [ ] Port message endpoints (2)
- [ ] Port analytics endpoints (1)
- [ ] Port link/tracking endpoints (3)
- [ ] Port state machine endpoints (2 + campaign sub-routes)
- [ ] Port LinkedIn credential endpoints (7)
- [ ] Port LinkedIn profile endpoints (3)
- [ ] Port LinkedIn setup endpoints (3)
- [ ] Port notification endpoints (6)
- [ ] Implement WebSocket endpoints (2 routes)
- [ ] Implement SSE endpoint
- [ ] Implement signal replacement service layer
- [ ] File upload (CSV leads)
- [ ] ML model blob handling
- [ ] Frontend API client updated
- [ ] Integration tests passing

### Phase 3: Remove Django (1-2 weeks)
- [ ] Daemon pure Python
- [ ] Click CLI
- [ ] Pydantic Settings
- [ ] Django code deleted
- [ ] Docker simplified
- [ ] Documentation updated
- [ ] Production deployment

---

## Rollback Plan

| Phase | Rollback Strategy |
|-------|-------------------|
| Phase 1 | Disable MongoDB connection; Django still primary |
| Phase 2 | Revert frontend to Django API (feature flags) |
| Phase 3 | ⚠️ No easy rollback — must be confident before proceeding |

---

## Timeline Summary

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| Phase 1 | 2-3 weeks | All MongoDB models + dual-write + migrated data |
| Phase 2 | 3-4 weeks | All 60+ FastAPI endpoints + WebSocket + SSE + frontend |
| Phase 3 | 1-2 weeks | Pure Python daemon + Django removed |
| **Total** | **6-9 weeks** | **Full FastAPI + MongoDB + Next.js stack** |
