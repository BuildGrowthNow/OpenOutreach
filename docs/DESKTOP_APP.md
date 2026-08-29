# OpenOutreach Desktop Application

Production-ready desktop app for Mac and Windows. Runs the LinkedIn browser daemon locally using the user's residential IP and existing browser, while connecting to the centralized AWS backend.

## Table of Contents

1. [Architecture Overview](#phase-1-architecture-overview)
2. [Backend API Changes](#phase-2-backend-api-changes)
3. [Daemon Remote Mode](#phase-3-daemon-remote-mode)
4. [System Tray App](#phase-4-system-tray-app)
5. [Python Packaging](#phase-5-python-packaging)
6. [macOS Distribution](#phase-6-macos-distribution)
7. [Windows Distribution](#phase-7-windows-distribution)
8. [Auto-Updates](#phase-8-auto-updates)
9. [Testing & QA](#phase-9-testing--qa)
10. [Production Checklist](#production-checklist)

---

## Phase 1: Architecture Overview

### Current Architecture (Cloud-Only)

```
┌─────────────────────────────────────────────────────────────┐
│                        AWS EC2                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  Next.js    │  │  FastAPI    │  │  Daemon + Playwright │  │
│  │  Frontend   │  │  Backend    │  │  (Cloud IP = Bad)    │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│                          │                    │              │
│                    ┌─────┴────────────────────┘              │
│                    ▼                                         │
│              ┌──────────┐                                    │
│              │ MongoDB  │                                    │
│              │  Atlas   │                                    │
│              └──────────┘                                    │
└─────────────────────────────────────────────────────────────┘
                           │
                    Proxy Required
                    ($25-75/profile/mo)
                           │
                           ▼
                    ┌──────────────┐
                    │   LinkedIn   │
                    └──────────────┘
```

### Target Architecture (Hybrid Desktop)

```
┌────────────────────────────────────────┐
│              AWS EC2                    │
│  ┌─────────────┐  ┌─────────────┐      │
│  │  Next.js    │  │  FastAPI    │      │
│  │  Frontend   │  │  Backend    │      │
│  │  (Web UI)   │  │  (API)      │      │
│  └─────────────┘  └─────────────┘      │
│                          │              │
│                    ┌─────┘              │
│                    ▼                    │
│              ┌──────────┐              │
│              │ MongoDB  │              │
│              │  Atlas   │              │
│              └──────────┘              │
└────────────────────────────────────────┘
         ▲              
         │   HTTPS      
         │              
┌────────┴───────────────────────┐
│      User's Desktop App         │
│  ┌───────────────────────────┐ │
│  │  Python Daemon (~20MB)    │ │
│  │  + System Tray Icon       │ │
│  │  + pystray                │ │
│  └─────────────┬─────────────┘ │
│                │               │
│                ▼               │
│  ┌───────────────────────────┐ │
│  │  User's Existing Browser  │ │
│  │  (Chrome/Edge/Safari)     │ │
│  └───────────────────────────┘ │
│         Residential IP          │
└─────────────────────────────────┘
                │
         No Proxy Needed!
                │
                ▼
         ┌──────────────┐
         │   LinkedIn   │
         └──────────────┘
```

### Benefits

| Aspect | Cloud-Only | Desktop App |
|--------|------------|-------------|
| LinkedIn IP | Datacenter (blocked) or proxy ($$$) | User's residential IP (free) |
| Proxy cost | $25-75/profile/month | $0 |
| Detection risk | High | Low |
| Browser | Bundled Chromium | User's real browser (more natural) |
| App size | N/A | ~20-30MB |
| Distribution cost | N/A | $0 |

### Component Responsibilities

| Component | Location | Responsibility |
|-----------|----------|----------------|
| FastAPI Backend | AWS | Auth, campaigns, leads, deals, analytics, task scheduling |
| MongoDB | Atlas | All persistent data |
| Next.js Frontend | AWS | Web UI (users access via browser) |
| Python Daemon | User's machine | Browser automation, task execution, tray icon |
| User's Browser | User's machine | Actual LinkedIn sessions (Chrome/Edge/Safari) |

### Both Options Coexist

The cloud version continues to work. Users choose:
- **Cloud**: Works 24/7, requires proxy ($25-75/mo)
- **Desktop**: Free, uses their IP, runs only when computer is on

---

## Phase 2: Backend API Changes

- [x] Phase 2 complete - daemon communication endpoints implemented

### 2.1 New Daemon Communication Endpoints

Create `openoutreach/api_v2/routers/daemon.py`:

```python
"""
Remote daemon communication endpoints.

Desktop app daemons use these to:
1. Claim and execute tasks
2. Report task results
3. Sync cookies/session state
4. Report health/status
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from openoutreach.api_v2.dependencies_v2 import get_current_user
from openoutreach.mongodb.models import Task, LinkedInProfile, SiteConfig
from openoutreach.core.enums import TaskStatus

router = APIRouter(prefix="/daemon", tags=["daemon"])


class DaemonHeartbeat(BaseModel):
    daemon_id: str
    linkedin_profile_id: str
    version: str
    platform: str  # "darwin" | "win32"
    uptime_seconds: int
    browser: str  # "chrome" | "edge" | "safari"


class TaskClaimResponse(BaseModel):
    task_id: Optional[str] = None
    task_type: Optional[str] = None
    payload: Optional[dict] = None
    campaign_id: Optional[str] = None


class TaskResultRequest(BaseModel):
    task_id: str
    status: str  # "completed" | "failed"
    result: Optional[dict] = None
    error: Optional[str] = None
    duration_ms: int


class CookieSyncRequest(BaseModel):
    linkedin_profile_id: str
    cookie_data: str  # encrypted


class SessionStateRequest(BaseModel):
    linkedin_profile_id: str
    is_logged_in: bool
    requires_verification: bool = False
    verification_type: Optional[str] = None


@router.post("/heartbeat")
async def daemon_heartbeat(
    heartbeat: DaemonHeartbeat,
    user=Depends(get_current_user),
):
    """Receive daemon health heartbeat. Called every 30s."""
    profile = await LinkedInProfile.find_one(
        LinkedInProfile.id == heartbeat.linkedin_profile_id,
        LinkedInProfile.user_id == user.id,
    )
    if not profile:
        raise HTTPException(404, "LinkedIn profile not found")
    
    profile.daemon_last_seen = datetime.utcnow()
    profile.daemon_version = heartbeat.version
    profile.daemon_platform = heartbeat.platform
    profile.daemon_browser = heartbeat.browser
    await profile.save()
    
    return {"status": "ok", "server_time": datetime.utcnow().isoformat()}


@router.post("/tasks/claim", response_model=TaskClaimResponse)
async def claim_task(
    linkedin_profile_id: str,
    daemon_id: str,
    user=Depends(get_current_user),
):
    """Atomically claim the next available task for this profile."""
    profile = await LinkedInProfile.find_one(
        LinkedInProfile.id == linkedin_profile_id,
        LinkedInProfile.user_id == user.id,
    )
    if not profile:
        raise HTTPException(404, "LinkedIn profile not found")
    
    task = await Task.objects.claim_next(linkedin_profile_id=linkedin_profile_id)
    
    if not task:
        return TaskClaimResponse()
    
    return TaskClaimResponse(
        task_id=str(task.id),
        task_type=task.task_type,
        payload=task.payload,
        campaign_id=str(task.campaign_id) if task.campaign_id else None,
    )


@router.post("/tasks/result")
async def report_task_result(
    request: TaskResultRequest,
    user=Depends(get_current_user),
):
    """Report task completion or failure."""
    task = await Task.get(request.task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    
    # Verify ownership
    profile = await LinkedInProfile.find_one(
        LinkedInProfile.id == task.linkedin_profile_id,
        LinkedInProfile.user_id == user.id,
    )
    if not profile:
        raise HTTPException(403, "Not authorized")
    
    task.status = TaskStatus.COMPLETED if request.status == "completed" else TaskStatus.FAILED
    task.result = request.result
    task.error = request.error
    task.completed_at = datetime.utcnow()
    task.duration_ms = request.duration_ms
    await task.save()
    
    return {"status": "ok"}


@router.post("/cookies/sync")
async def sync_cookies(
    request: CookieSyncRequest,
    user=Depends(get_current_user),
):
    """Sync browser cookies from desktop daemon to backend."""
    profile = await LinkedInProfile.find_one(
        LinkedInProfile.id == request.linkedin_profile_id,
        LinkedInProfile.user_id == user.id,
    )
    if not profile:
        raise HTTPException(404, "LinkedIn profile not found")
    
    profile.cookie_data_encrypted = request.cookie_data
    profile.cookies_updated_at = datetime.utcnow()
    await profile.save()
    
    return {"status": "ok"}


@router.post("/session/state")
async def report_session_state(
    request: SessionStateRequest,
    user=Depends(get_current_user),
):
    """Report session state (login status, verification needed)."""
    profile = await LinkedInProfile.find_one(
        LinkedInProfile.id == request.linkedin_profile_id,
        LinkedInProfile.user_id == user.id,
    )
    if not profile:
        raise HTTPException(404, "LinkedIn profile not found")
    
    profile.is_logged_in = request.is_logged_in
    profile.requires_verification = request.requires_verification
    profile.verification_type = request.verification_type
    profile.session_updated_at = datetime.utcnow()
    await profile.save()
    
    return {"status": "ok"}


@router.get("/config")
async def get_daemon_config(
    linkedin_profile_id: str,
    user=Depends(get_current_user),
):
    """Get daemon configuration (rate limits, active hours, etc)."""
    profile = await LinkedInProfile.find_one(
        LinkedInProfile.id == linkedin_profile_id,
        LinkedInProfile.user_id == user.id,
    )
    if not profile:
        raise HTTPException(404, "LinkedIn profile not found")
    
    config = await SiteConfig.load(user_id=user.id)
    
    return {
        "rate_limits": {
            "velocity": config.velocity,
            "daily_connect_limit": config.daily_connect_limit,
            "daily_message_limit": config.daily_message_limit,
            "cooldown_minutes": config.cooldown_minutes,
        },
        "active_hours": {
            "enabled": config.enable_active_hours,
            "start_hour": config.active_start_hour,
            "end_hour": config.active_end_hour,
            "timezone": config.active_timezone,
            "days": config.active_days,
        },
        "poll_interval_seconds": 30,
        "heartbeat_interval_seconds": 30,
    }


@router.get("/credentials")
async def get_credentials(
    linkedin_profile_id: str,
    user=Depends(get_current_user),
):
    """Get LinkedIn credentials for daemon login."""
    profile = await LinkedInProfile.find_one(
        LinkedInProfile.id == linkedin_profile_id,
        LinkedInProfile.user_id == user.id,
    )
    if not profile:
        raise HTTPException(404, "LinkedIn profile not found")
    
    # Decrypt and return credentials
    return {
        "email": profile.get_decrypted_email(),
        "password": profile.get_decrypted_password(),
        "cookie_data": profile.cookie_data_encrypted,
    }
```

### 2.2 Register Router

Add to `openoutreach/api_v2/main.py`:

```python
from openoutreach.api_v2.routers import daemon

app.include_router(daemon.router, prefix="/api")
```

### 2.3 Model Updates

- [x] LinkedInProfile model updated with daemon tracking fields

Add daemon tracking fields to `LinkedInProfile`:

```python
# In openoutreach/mongodb/models/linkedin_profile.py

class LinkedInProfile(Document):
    # ... existing fields ...
    
    # Daemon tracking
    daemon_last_seen: Optional[datetime] = None
    daemon_version: Optional[str] = None
    daemon_platform: Optional[str] = None  # "darwin" | "win32"
    daemon_browser: Optional[str] = None   # "chrome" | "edge" | "safari"
    
    # Session state (reported by daemon)
    is_logged_in: bool = False
    requires_verification: bool = False
    verification_type: Optional[str] = None
    session_updated_at: Optional[datetime] = None
```

---

## Phase 3: Daemon Remote Mode

- [x] Phase 3 complete - remote daemon, client, and browser detection implemented

### 3.1 Remote Client

Create `openoutreach/core/remote_client.py`:

```python
"""
HTTP client for daemon-to-backend communication.
"""

import httpx
from typing import Optional
from datetime import datetime
from dataclasses import dataclass
import platform

@dataclass
class DaemonConfig:
    velocity: int
    daily_connect_limit: int
    daily_message_limit: int
    cooldown_minutes: int
    enable_active_hours: bool
    active_start_hour: int
    active_end_hour: int
    active_timezone: str
    active_days: list[int]
    poll_interval_seconds: int
    heartbeat_interval_seconds: int


class RemoteClient:
    """HTTP client for desktop daemon."""
    
    def __init__(self, api_url: str, token: str, daemon_id: str):
        self.api_url = api_url.rstrip("/")
        self.daemon_id = daemon_id
        self._client = httpx.AsyncClient(
            base_url=self.api_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )
    
    async def close(self):
        await self._client.aclose()
    
    async def heartbeat(
        self,
        linkedin_profile_id: str,
        version: str,
        uptime_seconds: int,
        browser: str,
    ) -> dict:
        response = await self._client.post(
            "/api/daemon/heartbeat",
            json={
                "daemon_id": self.daemon_id,
                "linkedin_profile_id": linkedin_profile_id,
                "version": version,
                "platform": platform.system().lower().replace("windows", "win32"),
                "uptime_seconds": uptime_seconds,
                "browser": browser,
            },
        )
        response.raise_for_status()
        return response.json()
    
    async def get_config(self, linkedin_profile_id: str) -> DaemonConfig:
        response = await self._client.get(
            "/api/daemon/config",
            params={"linkedin_profile_id": linkedin_profile_id},
        )
        response.raise_for_status()
        data = response.json()
        
        return DaemonConfig(
            velocity=data["rate_limits"]["velocity"],
            daily_connect_limit=data["rate_limits"]["daily_connect_limit"],
            daily_message_limit=data["rate_limits"]["daily_message_limit"],
            cooldown_minutes=data["rate_limits"]["cooldown_minutes"],
            enable_active_hours=data["active_hours"]["enabled"],
            active_start_hour=data["active_hours"]["start_hour"],
            active_end_hour=data["active_hours"]["end_hour"],
            active_timezone=data["active_hours"]["timezone"],
            active_days=data["active_hours"]["days"],
            poll_interval_seconds=data["poll_interval_seconds"],
            heartbeat_interval_seconds=data["heartbeat_interval_seconds"],
        )
    
    async def claim_task(self, linkedin_profile_id: str) -> Optional[dict]:
        response = await self._client.post(
            "/api/daemon/tasks/claim",
            params={
                "linkedin_profile_id": linkedin_profile_id,
                "daemon_id": self.daemon_id,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data if data.get("task_id") else None
    
    async def report_result(
        self,
        task_id: str,
        status: str,
        result: Optional[dict] = None,
        error: Optional[str] = None,
        duration_ms: int = 0,
    ) -> dict:
        response = await self._client.post(
            "/api/daemon/tasks/result",
            json={
                "task_id": task_id,
                "status": status,
                "result": result,
                "error": error,
                "duration_ms": duration_ms,
            },
        )
        response.raise_for_status()
        return response.json()
    
    async def sync_cookies(self, linkedin_profile_id: str, cookie_data: str) -> dict:
        response = await self._client.post(
            "/api/daemon/cookies/sync",
            json={
                "linkedin_profile_id": linkedin_profile_id,
                "cookie_data": cookie_data,
            },
        )
        response.raise_for_status()
        return response.json()
    
    async def report_session_state(
        self,
        linkedin_profile_id: str,
        is_logged_in: bool,
        requires_verification: bool = False,
        verification_type: Optional[str] = None,
    ) -> dict:
        response = await self._client.post(
            "/api/daemon/session/state",
            json={
                "linkedin_profile_id": linkedin_profile_id,
                "is_logged_in": is_logged_in,
                "requires_verification": requires_verification,
                "verification_type": verification_type,
            },
        )
        response.raise_for_status()
        return response.json()
    
    async def get_credentials(self, linkedin_profile_id: str) -> dict:
        response = await self._client.get(
            "/api/daemon/credentials",
            params={"linkedin_profile_id": linkedin_profile_id},
        )
        response.raise_for_status()
        return response.json()
```

### 3.2 Browser Detection

Create `openoutreach/core/browser_detect.py`:

```python
"""
Detect user's installed browsers.
"""

import platform
import subprocess
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class BrowserInfo:
    name: str           # "chrome" | "edge" | "safari"
    channel: str        # Playwright channel name
    path: Optional[str] # Executable path
    version: Optional[str]


def detect_browsers() -> list[BrowserInfo]:
    """Detect installed browsers on the system."""
    browsers = []
    system = platform.system()
    
    if system == "Darwin":  # macOS
        # Chrome
        chrome_path = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        if chrome_path.exists():
            browsers.append(BrowserInfo(
                name="chrome",
                channel="chrome",
                path=str(chrome_path),
                version=_get_mac_app_version("/Applications/Google Chrome.app"),
            ))
        
        # Edge
        edge_path = Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge")
        if edge_path.exists():
            browsers.append(BrowserInfo(
                name="edge",
                channel="msedge",
                path=str(edge_path),
                version=_get_mac_app_version("/Applications/Microsoft Edge.app"),
            ))
        
        # Safari (always present on macOS)
        browsers.append(BrowserInfo(
            name="safari",
            channel="webkit",  # Playwright uses webkit for Safari
            path="/Applications/Safari.app",
            version=None,
        ))
    
    elif system == "Windows":
        # Chrome
        chrome_paths = [
            Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe",
            Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
            Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
        ]
        for path in chrome_paths:
            if path.exists():
                browsers.append(BrowserInfo(
                    name="chrome",
                    channel="chrome",
                    path=str(path),
                    version=None,
                ))
                break
        
        # Edge (usually pre-installed on Windows 10/11)
        edge_paths = [
            Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
            Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
        ]
        for path in edge_paths:
            if path.exists():
                browsers.append(BrowserInfo(
                    name="edge",
                    channel="msedge",
                    path=str(path),
                    version=None,
                ))
                break
    
    return browsers


def get_preferred_browser() -> Optional[BrowserInfo]:
    """Get the best available browser for automation."""
    browsers = detect_browsers()
    
    # Preference: Chrome > Edge > Safari
    for name in ["chrome", "edge", "safari"]:
        for browser in browsers:
            if browser.name == name:
                return browser
    
    return browsers[0] if browsers else None


def _get_mac_app_version(app_path: str) -> Optional[str]:
    """Get version from macOS app bundle."""
    try:
        result = subprocess.run(
            ["defaults", "read", f"{app_path}/Contents/Info", "CFBundleShortVersionString"],
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None
```

### 3.3 Remote Daemon

> Historical reference only. The legacy implementation shown below is
> retired and is not distributed. Current desktop execution uses
> `openoutreach/desktop/secure_daemon.py` with the v2-only client in
> `openoutreach/desktop/remote_client.py`; it never receives credentials,
> cookies, server settings, or database access.

Create `openoutreach/core/daemon_remote.py`:

```python
"""
Remote daemon - runs on user's desktop, connects to AWS backend.
"""

import asyncio
import logging
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from openoutreach.core.remote_client import RemoteClient, DaemonConfig
from openoutreach.core.browser_detect import get_preferred_browser, BrowserInfo
from openoutreach.linkedin.browser.launch import create_browser_session
from openoutreach.linkedin.tasks import get_task_handler

logger = logging.getLogger(__name__)

# Version - update on releases
__version__ = "1.0.0"


class RemoteDaemon:
    """Desktop daemon that executes LinkedIn automation locally."""
    
    def __init__(
        self,
        api_url: str,
        token: str,
        linkedin_profile_id: str,
        data_dir: Optional[Path] = None,
    ):
        self.api_url = api_url
        self.token = token
        self.linkedin_profile_id = linkedin_profile_id
        self.data_dir = data_dir or self._default_data_dir()
        self.daemon_id = self._get_or_create_daemon_id()
        
        self.client = RemoteClient(api_url, token, self.daemon_id)
        self.config: Optional[DaemonConfig] = None
        self.session = None
        self.browser: Optional[BrowserInfo] = None
        self.running = False
        self.start_time: Optional[datetime] = None
        self.last_task_at: Optional[datetime] = None
        
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def _default_data_dir(self) -> Path:
        if sys.platform == "darwin":
            return Path.home() / "Library/Application Support/OpenOutreach"
        elif sys.platform == "win32":
            return Path.home() / "AppData/Local/OpenOutreach"
        return Path.home() / ".openoutreach"
    
    def _get_or_create_daemon_id(self) -> str:
        id_file = self.data_dir / "daemon_id"
        if id_file.exists():
            return id_file.read_text().strip()
        
        daemon_id = str(uuid.uuid4())
        id_file.parent.mkdir(parents=True, exist_ok=True)
        id_file.write_text(daemon_id)
        return daemon_id
    
    async def start(self):
        """Start the daemon."""
        logger.info("Starting remote daemon...")
        self.running = True
        self.start_time = datetime.utcnow()
        
        # Detect browser
        self.browser = get_preferred_browser()
        if not self.browser:
            raise RuntimeError("No supported browser found. Please install Chrome or Edge.")
        logger.info(f"Using browser: {self.browser.name}")
        
        # Fetch config
        self.config = await self.client.get_config(self.linkedin_profile_id)
        logger.info(f"Config loaded: velocity={self.config.velocity}/hr")
        
        # Start browser session
        await self._start_session()
        
        # Run loops
        await asyncio.gather(
            self._heartbeat_loop(),
            self._task_loop(),
            self._config_refresh_loop(),
        )
    
    async def stop(self):
        """Stop the daemon gracefully."""
        logger.info("Stopping daemon...")
        self.running = False
        
        if self.session:
            await self._sync_cookies()
            await self.session.close()
        
        await self.client.close()
    
    async def _start_session(self):
        """Initialize browser session using user's browser."""
        logger.info("Starting browser session...")
        
        creds = await self.client.get_credentials(self.linkedin_profile_id)
        
        # Create session using user's browser
        self.session = await create_browser_session(
            channel=self.browser.channel,  # "chrome", "msedge", or "webkit"
            headless=False,
            user_data_dir=self.data_dir / "browser_data",
        )
        
        try:
            await self.session.login(
                email=creds["email"],
                password=creds["password"],
                cookie_data=creds.get("cookie_data"),
            )
            
            await self.client.report_session_state(
                linkedin_profile_id=self.linkedin_profile_id,
                is_logged_in=True,
            )
            logger.info("Logged in to LinkedIn")
            
        except Exception as e:
            logger.error(f"Login failed: {e}")
            if "verification" in str(e).lower():
                await self.client.report_session_state(
                    linkedin_profile_id=self.linkedin_profile_id,
                    is_logged_in=False,
                    requires_verification=True,
                )
            raise
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeats."""
        while self.running:
            try:
                uptime = int((datetime.utcnow() - self.start_time).total_seconds())
                await self.client.heartbeat(
                    linkedin_profile_id=self.linkedin_profile_id,
                    version=__version__,
                    uptime_seconds=uptime,
                    browser=self.browser.name,
                )
            except Exception as e:
                logger.warning(f"Heartbeat failed: {e}")
            
            await asyncio.sleep(self.config.heartbeat_interval_seconds)
    
    async def _task_loop(self):
        """Main task execution loop."""
        while self.running:
            try:
                if not self._is_active_time():
                    await asyncio.sleep(60)
                    continue
                
                task = await self.client.claim_task(self.linkedin_profile_id)
                
                if not task:
                    await asyncio.sleep(self.config.poll_interval_seconds)
                    continue
                
                logger.info(f"Executing: {task['task_type']} ({task['task_id']})")
                start = datetime.utcnow()
                
                try:
                    handler = get_task_handler(task["task_type"])
                    result = await handler(task=task, session=self.session, qualifiers=None)
                    
                    duration_ms = int((datetime.utcnow() - start).total_seconds() * 1000)
                    await self.client.report_result(
                        task_id=task["task_id"],
                        status="completed",
                        result=result,
                        duration_ms=duration_ms,
                    )
                    
                    self.last_task_at = datetime.utcnow()
                    await self._sync_cookies()
                    
                except Exception as e:
                    duration_ms = int((datetime.utcnow() - start).total_seconds() * 1000)
                    await self.client.report_result(
                        task_id=task["task_id"],
                        status="failed",
                        error=str(e),
                        duration_ms=duration_ms,
                    )
                    logger.error(f"Task failed: {e}")
                    
                    if "authentication" in str(e).lower() or "401" in str(e):
                        await self.client.report_session_state(
                            linkedin_profile_id=self.linkedin_profile_id,
                            is_logged_in=False,
                        )
                
            except Exception as e:
                logger.error(f"Task loop error: {e}")
                await asyncio.sleep(30)
    
    async def _config_refresh_loop(self):
        """Periodically refresh config."""
        while self.running:
            await asyncio.sleep(300)
            try:
                self.config = await self.client.get_config(self.linkedin_profile_id)
            except Exception as e:
                logger.warning(f"Config refresh failed: {e}")
    
    async def _sync_cookies(self):
        """Sync cookies to backend."""
        if not self.session:
            return
        try:
            cookie_data = await self.session.get_cookie_data()
            await self.client.sync_cookies(self.linkedin_profile_id, cookie_data)
        except Exception as e:
            logger.warning(f"Cookie sync failed: {e}")
    
    def _is_active_time(self) -> bool:
        """Check if within active hours."""
        if not self.config.enable_active_hours:
            return True
        
        from datetime import datetime
        import pytz
        
        tz = pytz.timezone(self.config.active_timezone)
        now = datetime.now(tz)
        
        if now.weekday() not in self.config.active_days:
            return False
        
        return self.config.active_start_hour <= now.hour < self.config.active_end_hour


async def run_daemon(api_url: str, token: str, linkedin_profile_id: str):
    """Entry point for the daemon."""
    daemon = RemoteDaemon(api_url, token, linkedin_profile_id)
    
    try:
        await daemon.start()
    except KeyboardInterrupt:
        await daemon.stop()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--profile-id", required=True)
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_daemon(args.api_url, args.token, args.profile_id))
```

---

## Phase 4: System Tray App

- [x] Phase 4 complete - system tray app with auth, daemon control, and protocol handler

### 4.1 Tray Application

Create `openoutreach/desktop/app.py`:

```python
"""
Desktop tray application.

Provides:
- System tray icon with status
- Start/Stop daemon control
- Open web dashboard
- Login flow
"""

import asyncio
import threading
import webbrowser
from pathlib import Path
from typing import Optional
import logging

import pystray
from PIL import Image
from pystray import MenuItem as Item

from openoutreach.core.daemon_remote import RemoteDaemon, __version__
from openoutreach.desktop.auth import AuthManager
from openoutreach.desktop.config import AppConfig

logger = logging.getLogger(__name__)


class TrayApp:
    """System tray application."""
    
    def __init__(self):
        self.config = AppConfig.load()
        self.auth = AuthManager(self.config)
        self.daemon: Optional[RemoteDaemon] = None
        self.daemon_thread: Optional[threading.Thread] = None
        self.icon: Optional[pystray.Icon] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
    
    def run(self):
        """Run the tray application."""
        self.icon = pystray.Icon(
            "OpenOutreach",
            self._create_icon(),
            "OpenOutreach",
            menu=self._create_menu(),
        )
        self.icon.run(setup=self._on_setup)
    
    def _create_icon(self) -> Image.Image:
        """Create tray icon."""
        icon_path = Path(__file__).parent / "assets" / "icon.png"
        if icon_path.exists():
            return Image.open(icon_path)
        
        # Fallback: create simple colored circle
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        # Draw circle
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        color = (34, 197, 94) if self._is_running() else (156, 163, 175)
        draw.ellipse([8, 8, 56, 56], fill=color)
        return img
    
    def _create_menu(self) -> pystray.Menu:
        """Create tray menu."""
        if not self.auth.is_logged_in():
            return pystray.Menu(
                Item("Login to OpenOutreach", self._on_login),
                Item("Quit", self._on_quit),
            )
        
        return pystray.Menu(
            Item(
                f"Status: {'Running' if self._is_running() else 'Stopped'}",
                None,
                enabled=False,
            ),
            pystray.Menu.SEPARATOR,
            Item(
                "Stop Automation" if self._is_running() else "Start Automation",
                self._on_toggle_daemon,
            ),
            Item("Open Dashboard", self._on_open_dashboard),
            pystray.Menu.SEPARATOR,
            Item("Logout", self._on_logout),
            Item("Quit", self._on_quit),
        )
    
    def _update_menu(self):
        """Update the tray menu."""
        if self.icon:
            self.icon.menu = self._create_menu()
            self.icon.icon = self._create_icon()
    
    def _is_running(self) -> bool:
        """Check if daemon is running."""
        return self.daemon is not None and self.daemon.running
    
    def _on_setup(self, icon):
        """Called when tray icon is ready."""
        icon.visible = True
        
        # Auto-start daemon if logged in
        if self.auth.is_logged_in():
            self._start_daemon()
    
    def _on_login(self):
        """Open login page in browser."""
        login_url = f"{self.config.api_url}/login?desktop=true&callback=openoutreach://auth"
        webbrowser.open(login_url)
    
    def _on_logout(self):
        """Log out and stop daemon."""
        self._stop_daemon()
        self.auth.logout()
        self._update_menu()
    
    def _on_toggle_daemon(self):
        """Toggle daemon on/off."""
        if self._is_running():
            self._stop_daemon()
        else:
            self._start_daemon()
        self._update_menu()
    
    def _on_open_dashboard(self):
        """Open web dashboard."""
        webbrowser.open(self.config.api_url)
    
    def _on_quit(self):
        """Quit the application."""
        self._stop_daemon()
        if self.icon:
            self.icon.stop()
    
    def _start_daemon(self):
        """Start the daemon in a background thread."""
        if self._is_running():
            return
        
        if not self.auth.is_logged_in():
            logger.error("Not logged in")
            return
        
        def run_daemon():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            
            self.daemon = RemoteDaemon(
                api_url=self.config.api_url,
                token=self.auth.get_token(),
                linkedin_profile_id=self.auth.get_profile_id(),
            )
            
            try:
                self._loop.run_until_complete(self.daemon.start())
            except Exception as e:
                logger.error(f"Daemon error: {e}")
            finally:
                self._loop.close()
        
        self.daemon_thread = threading.Thread(target=run_daemon, daemon=True)
        self.daemon_thread.start()
        
        logger.info("Daemon started")
        self._update_menu()
    
    def _stop_daemon(self):
        """Stop the daemon."""
        if not self._is_running():
            return
        
        if self._loop and self.daemon:
            future = asyncio.run_coroutine_threadsafe(
                self.daemon.stop(),
                self._loop,
            )
            future.result(timeout=10)
        
        self.daemon = None
        self.daemon_thread = None
        
        logger.info("Daemon stopped")
        self._update_menu()


def main():
    """Entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    app = TrayApp()
    app.run()


if __name__ == "__main__":
    main()
```

### 4.2 Configuration

Create `openoutreach/desktop/config.py`:

```python
"""
Desktop app configuration.
"""

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional
import sys


@dataclass
class AppConfig:
    api_url: str = "https://app.openoutreach.io"
    
    @classmethod
    def _config_path(cls) -> Path:
        if sys.platform == "darwin":
            base = Path.home() / "Library/Application Support/OpenOutreach"
        elif sys.platform == "win32":
            base = Path.home() / "AppData/Local/OpenOutreach"
        else:
            base = Path.home() / ".openoutreach"
        
        base.mkdir(parents=True, exist_ok=True)
        return base / "config.json"
    
    @classmethod
    def load(cls) -> "AppConfig":
        path = cls._config_path()
        if path.exists():
            data = json.loads(path.read_text())
            return cls(**data)
        return cls()
    
    def save(self):
        path = self._config_path()
        path.write_text(json.dumps(asdict(self)))
```

### 4.3 Auth Manager

Create `openoutreach/desktop/auth.py`:

```python
"""
Desktop app authentication.
"""

import json
from pathlib import Path
from typing import Optional
import sys

import keyring


SERVICE_NAME = "OpenOutreach"


class AuthManager:
    """Manages authentication state using system keychain."""
    
    def __init__(self, config):
        self.config = config
    
    def is_logged_in(self) -> bool:
        return self.get_token() is not None
    
    def get_token(self) -> Optional[str]:
        return keyring.get_password(SERVICE_NAME, "token")
    
    def get_profile_id(self) -> Optional[str]:
        return keyring.get_password(SERVICE_NAME, "profile_id")
    
    def login(self, token: str, profile_id: str):
        keyring.set_password(SERVICE_NAME, "token", token)
        keyring.set_password(SERVICE_NAME, "profile_id", profile_id)
    
    def logout(self):
        try:
            keyring.delete_password(SERVICE_NAME, "token")
            keyring.delete_password(SERVICE_NAME, "profile_id")
        except keyring.errors.PasswordDeleteError:
            pass
```

### 4.4 URL Protocol Handler

The custom protocol is retained for launching an installed client, but current
login tokens are transferred only through the in-process desktop bridge. Never
put access or refresh tokens in a custom-protocol URL, browser history, or
process arguments.

**macOS** - Add to Info.plist:
```xml
<key>CFBundleURLTypes</key>
<array>
    <dict>
        <key>CFBundleURLSchemes</key>
        <array>
            <string>lengrowth</string>
        </array>
        <key>CFBundleURLName</key>
        <string>Lengrowth Auth</string>
    </dict>
</array>
```

**Windows** - Registry entries (added by installer):
```reg
[HKEY_CLASSES_ROOT\lengrowth]
@="URL:Lengrowth Protocol"
"URL Protocol"=""

[HKEY_CLASSES_ROOT\lengrowth\shell\open\command]
@="\"C:\\Program Files\\Lengrowth\\Lengrowth.exe\" \"%1\""
```

---

## Phase 5: Python Packaging

- [x] Phase 5 complete - PyInstaller spec, build script, and requirements implemented

### 5.1 PyInstaller Spec

Create `desktop/openoutreach.spec`:

```python
# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for OpenOutreach desktop app.

Output: ~20-30MB executable (no bundled browser)
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(SPECPATH).parent

# Collect data files
datas = [
    # Tray icon
    (str(PROJECT_ROOT / "openoutreach/desktop/assets"), "openoutreach/desktop/assets"),
]

# Hidden imports
hiddenimports = [
    "pystray._darwin" if sys.platform == "darwin" else "pystray._win32",
    "PIL._tkinter_finder",
    "keyring.backends.macOS" if sys.platform == "darwin" else "keyring.backends.Windows",
]

a = Analysis(
    [str(PROJECT_ROOT / "openoutreach/desktop/app.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=[
        # No bundled browser needed
        "playwright",
        # Exclude heavy unused packages
        "matplotlib",
        "numpy",
        "pandas",
        "scipy",
        "sklearn",
        "tensorflow",
        "torch",
        "tkinter",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="OpenOutreach",
    debug=False,
    strip=False,
    upx=True,
    console=False,
    icon="desktop/assets/icon.ico" if sys.platform == "win32" else None,
)

# macOS app bundle
if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="OpenOutreach.app",
        icon="desktop/assets/icon.icns",
        bundle_identifier="io.openoutreach.desktop",
        info_plist={
            "CFBundleShortVersionString": "1.0.0",
            "CFBundleVersion": "1.0.0",
            "NSHighResolutionCapable": True,
            "LSUIElement": False,
            "CFBundleURLTypes": [
                {
                    "CFBundleURLSchemes": ["openoutreach"],
                    "CFBundleURLName": "OpenOutreach Auth",
                }
            ],
        },
    )
```

### 5.2 Build Script

Create `desktop/build.py`:

```python
#!/usr/bin/env python3
"""
Build script for OpenOutreach desktop app.

Usage:
    python desktop/build.py          # Build for current platform
    python desktop/build.py --dmg    # Build .dmg for macOS
"""

import subprocess
import sys
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
BUILD_DIR = PROJECT_ROOT / "desktop/build"
DIST_DIR = PROJECT_ROOT / "desktop/dist"


def build():
    """Run PyInstaller build."""
    print("Building OpenOutreach desktop app...")
    
    shutil.rmtree(BUILD_DIR, ignore_errors=True)
    shutil.rmtree(DIST_DIR, ignore_errors=True)
    
    subprocess.run([
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "--noconfirm",
        "--workpath", str(BUILD_DIR),
        "--distpath", str(DIST_DIR),
        str(PROJECT_ROOT / "desktop/openoutreach.spec"),
    ], check=True)
    
    print(f"Build complete: {DIST_DIR}")


def create_dmg():
    """Create macOS .dmg installer."""
    if sys.platform != "darwin":
        print("DMG creation only supported on macOS")
        return
    
    print("Creating DMG...")
    
    dmg_path = DIST_DIR / "OpenOutreach.dmg"
    app_path = DIST_DIR / "OpenOutreach.app"
    
    # Use create-dmg if available, otherwise hdiutil
    try:
        subprocess.run([
            "create-dmg",
            "--volname", "OpenOutreach",
            "--window-size", "600", "400",
            "--icon-size", "100",
            "--icon", "OpenOutreach.app", "150", "200",
            "--app-drop-link", "450", "200",
            str(dmg_path),
            str(app_path),
        ], check=True)
    except FileNotFoundError:
        # Fallback to hdiutil
        subprocess.run([
            "hdiutil", "create",
            "-volname", "OpenOutreach",
            "-srcfolder", str(app_path),
            "-ov",
            "-format", "UDZO",
            str(dmg_path),
        ], check=True)
    
    print(f"DMG created: {dmg_path}")


if __name__ == "__main__":
    build()
    
    if "--dmg" in sys.argv and sys.platform == "darwin":
        create_dmg()
```

### 5.3 Requirements

Create `desktop/requirements.txt`:

```
# Desktop app dependencies
pyinstaller>=6.0
pystray>=0.19
Pillow>=10.0
keyring>=24.0

# Runtime (subset of main requirements)
httpx>=0.25
pydantic>=2.0
pytz
```

---

## Phase 6: macOS Distribution

- [x] Phase 6 complete - build process, signing, notarization, and CI/CD implemented

### 6.1 Build Process

```bash
# On macOS machine
cd /path/to/openoutreach
pip install -r desktop/requirements.txt
python desktop/build.py --dmg
```

Output: `desktop/dist/Lengrowth-{version}.dmg`

### 6.2 CI/CD Build

GitHub Actions workflow at `.github/workflows/desktop-build.yml` builds on qualifying pushes to `main` or by manual dispatch:

- **Trigger**: qualifying push to `main` or manual workflow dispatch
- **Artifacts**: macOS DMG, Windows executable, MSIX, and NSIS installer uploaded as workflow artifacts
- **macOS**: Builds on `macos-latest`, generates proper `.icns` icons

Manual build trigger:
```bash
git tag desktop-v1.0.0
git push origin desktop-v1.0.0
```

The publish job is intentionally manual. Set `publish` to `true` to publish an interim unsigned release, or set both `publish` and `sign` to `true` only after release approval and signing/notarization secrets are configured. Unsigned releases are for controlled testing and require the first-launch trust bypass described below.

### 6.3 First Launch Instructions

Unsigned local and interim published builds may require the right-click → Open flow on macOS and a SmartScreen override on Windows. Signed published builds use the manual release job with `sign: true`.

**Add this to the download page and in-app:**

```
## macOS Installation

1. Download `Lengrowth-{version}.dmg`
2. Open the DMG and drag Lengrowth to Applications
3. **Important - First launch only:**
   - Right-click (or Control-click) on Lengrowth in Applications
   - Click "Open" from the menu
   - Click "Open" again in the dialog
4. Log in with your Lengrowth account

After the first launch, you can open normally.
```

### 6.4 Code Signing (Optional)

Sign the app to enable Gatekeeper approval without right-click:

```bash
# Set environment variables
export APPLE_DEVELOPER_ID="Developer ID Application: Your Name (TEAMID)"
python desktop/build.py --sign --dmg
```

Entitlements file: `desktop/macos/entitlements.plist`

### 6.5 Notarization (Optional)

Remove the right-click requirement entirely with Apple notarization:

1. Get Apple Developer account ($99/yr)
2. Create an app-specific password at appleid.apple.com
3. Build and notarize:

```bash
export APPLE_DEVELOPER_ID="Developer ID Application: Your Name (TEAMID)"
export APPLE_TEAM_ID="YOURTEAMID"
export APPLE_ID="your@email.com"
export APPLE_APP_PASSWORD="xxxx-xxxx-xxxx-xxxx"

python desktop/build.py --sign --dmg --notarize
```

The notarization process:
1. Signs the app with hardened runtime
2. Creates DMG
3. Submits to Apple for notarization (takes 5-15 minutes)
4. Staples the notarization ticket to the DMG

---

## Phase 7: Windows Distribution

- [x] Phase 7 complete - MSIX, NSIS installer, protocol handler, CI/CD, and installation docs

### 7.1 Microsoft Store Submission

**Cost: Free**

Steps:
1. Create Microsoft Partner Center account (free)
2. Create app submission
3. Package as MSIX
4. Submit for review

### 7.2 MSIX Packaging

**Implementation:** MSIX creation is handled by `desktop/build.py --msix`, which:
- Generates AppxManifest.xml dynamically
- Creates required asset images from icon.png
- Packages with Windows SDK makeappx.exe
- Output: `desktop/dist/Lengrowth-{version}.msix`

The manifest template:

```xml
<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
         xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"
         xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities">
  
  <Identity Name="Lengrowth"
            Publisher="CN=YourPublisher"
            Version="1.0.0.0"
            ProcessorArchitecture="x64" />
  
  <Properties>
    <DisplayName>Lengrowth</DisplayName>
    <PublisherDisplayName>Lengrowth</PublisherDisplayName>
    <Description>LinkedIn automation with your local IP</Description>
    <Logo>assets\icon-150.png</Logo>
  </Properties>
  
  <Resources>
    <Resource Language="en-us" />
  </Resources>
  
  <Dependencies>
    <TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.17763.0" MaxVersionTested="10.0.22000.0" />
  </Dependencies>
  
  <Capabilities>
    <Capability Name="internetClient" />
    <rescap:Capability Name="runFullTrust" />
  </Capabilities>
  
  <Applications>
    <Application Id="Lengrowth"
                 Executable="Lengrowth.exe"
                 EntryPoint="Windows.FullTrustApplication">
      <uap:VisualElements DisplayName="Lengrowth"
                          Description="LinkedIn automation"
                          BackgroundColor="#22c55e"
                          Square150x150Logo="assets\icon-150.png"
                          Square44x44Logo="assets\icon-44.png">
      </uap:VisualElements>
      <Extensions>
        <uap:Extension Category="windows.protocol">
          <uap:Protocol Name="lengrowth">
            <uap:DisplayName>Lengrowth Auth</uap:DisplayName>
          </uap:Protocol>
        </uap:Extension>
      </Extensions>
    </Application>
  </Applications>
</Package>
```

### 7.3 Build MSIX

**Automated via build script:**
```bash
python desktop/build.py --msix
```

**Manual process (if needed):**
```powershell
# Build exe first
python desktop/build.py

# Create MSIX
& "C:\Program Files (x86)\Windows Kits\10\bin\10.0.22000.0\x64\makeappx.exe" pack /d desktop\dist /p desktop\dist\Lengrowth-{version}.msix
```

### 7.4 NSIS Installer (Recommended Distribution Method)

**Created via:**
```bash
python desktop/build.py --installer
```

**Features:**
- Traditional Windows installer experience
- Start Menu and Desktop shortcuts
- Protocol handler auto-registration
- Add/Remove Programs integration
- Uninstaller included

**Output:** `desktop/dist/Lengrowth-{version}-Setup.exe`

### 7.5 Code Signing (Required for Signed Publish)

Sign with a code signing certificate to remove SmartScreen warnings:

**Local PowerShell helper:**
```powershell
.\desktop\windows\sign.ps1 -FilePath "desktop\dist\Lengrowth.exe"
```

**Environment variables:**
- Local signing uses `SIGN_CERT_PATH` and `SIGN_CERT_PASS`.
- Approved CI publishing uses the ephemeral certificate workflow in `desktop/windows/sign_release.ps1` with repository secrets; do not paste certificate material into chat or commit it.

**Manual signing:**
```powershell
signtool sign /f cert.pfx /p password /tr https://timestamp.digicert.com /td SHA256 /fd SHA256 desktop\dist\Lengrowth.exe
```

### 7.6 Distribution Options

Three distribution methods supported:

1. **NSIS Installer (Recommended for most users)**
   - Download: `Lengrowth-{version}-Setup.exe`
   - Pros: Familiar installer UX, protocol handler auto-registered, uninstaller
   - Best for: Direct download from website

2. **Standalone Executable**
    - Download: `Lengrowth.exe`
   - Pros: Portable, no installation needed
   - Best for: Users who prefer portable apps

3. **MSIX Package**
    - Download: `Lengrowth-{version}.msix`
   - Pros: Microsoft Store compatible, sandboxed
   - Best for: Enterprise deployment or Store submission

### 7.7 Installation Instructions

Full user documentation in `desktop/windows/INSTALLATION.md`:
- Download options explained
- SmartScreen bypass steps
- Manual protocol registration
- Auto-start configuration
- Troubleshooting guide

**SmartScreen Note:**
All unsigned builds show SmartScreen warning on first run:
1. Click "More info"
2. Click "Run anyway"

Warning disappears after app gains reputation (~10-20 downloads).

### 7.8 CI/CD Integration

GitHub Actions workflow (`.github/workflows/desktop-build.yml`) automatically:
- Builds Windows exe
- Creates MSIX package (if SDK available)
- Creates NSIS installer (via Chocolatey NSIS install)
- Uploads all artifacts to release
- Triggers on `desktop-v*` tags

**Trigger a build:**
```bash
git tag desktop-v1.0.0
git push origin desktop-v1.0.0
```

### 7.9 Protocol Handler Registration

**Auto-registered by NSIS installer**

Registry entries:
```
HKEY_CLASSES_ROOT\lengrowth
  (Default) = "URL:Lengrowth Protocol"
  URL Protocol = ""

HKEY_CLASSES_ROOT\lengrowth\shell\open\command
  (Default) = "C:\Program Files\Lengrowth\Lengrowth.exe" "%1"
```

**Manual registration:** Use `desktop/windows/register_protocol.reg` (edit paths first)

**Testing:**
```
lengrowth://auth?probe=1
```

---

## Phase 8: Auto-Updates

- [x] Phase 8 complete - auto-update checker with GitHub releases integration

### 8.1 Update Checker Implementation

**Implementation:** `openoutreach/desktop/updater.py` provides:
- Periodic check against GitHub releases API (every 6 hours)
- Platform-specific asset detection (DMG for macOS, Setup.exe for Windows)
- Version comparison using semantic versioning
- Automatic fallback to release page if specific asset not found
- Graceful error handling with no user interruption

**Features:**
- Checks `https://api.github.com/repos/BuildGrowthNow/OpenOutreach/releases/latest`
- Parses `desktop-v*` tags (strips prefix automatically)
- Finds platform-appropriate download URLs from release assets
- Returns structured update info: `{version, download_url, release_page, notes, tag_name}`

### 8.2 Tray App Integration

**Implementation:** Integrated in `openoutreach/desktop/app.py`:
- Background thread runs update checker on 6-hour interval
- First check delayed by 10 seconds after app startup
- Updates detected → tray menu gains "Update Available: vX.X.X" item
- System notification shown on first detection
- Clicking menu item opens platform-specific download URL in browser
- Update state persists across daemon restarts within same session
- Update checker gracefully stops on app quit

**User Flow:**
1. App checks for updates in background (no blocking)
2. If newer version found → notification appears
3. Tray menu shows "Update Available: vX.X.X"
4. User clicks → browser opens to download page
5. User downloads and installs manually (no forced updates)

**Notes:**
- Non-intrusive: never interrupts running automation
- Works whether logged in or not
- Survives network failures gracefully
- No auto-download or auto-install (user stays in control)

---

## Phase 9: Testing & QA

### 9.1 Test Matrix

| Test | macOS Intel | macOS ARM | Windows x64 |
|------|-------------|-----------|-------------|
| Install from DMG/.exe | ☐ | ☐ | ☐ |
| First launch (right-click/SmartScreen) | ☐ | ☐ | ☐ |
| Login flow | ☐ | ☐ | ☐ |
| Browser detection (Chrome) | ☐ | ☐ | ☐ |
| Browser detection (Edge) | ☐ | ☐ | ☐ |
| Browser detection (Safari) | ☐ | N/A | N/A |
| Daemon starts | ☐ | ☐ | ☐ |
| Tray icon shows | ☐ | ☐ | ☐ |
| Tray menu works | ☐ | ☐ | ☐ |
| Task execution | ☐ | ☐ | ☐ |
| Cookie sync | ☐ | ☐ | ☐ |
| Logout | ☐ | ☐ | ☐ |
| Quit | ☐ | ☐ | ☐ |
| Auto-start on login | ☐ | ☐ | ☐ |

### 9.2 Performance Targets

| Metric | Target |
|--------|--------|
| App size | < 30MB |
| Memory (idle) | < 50MB |
| Memory (running) | < 150MB |
| CPU (idle) | < 1% |
| Startup time | < 2s |

---

## Production Checklist

### Backend
- [x] Daemon API endpoints implemented
- [x] Rate limiting on daemon endpoints (inherited from FastAPI)
- [x] Logging for daemon connections

### Desktop App
- [x] Browser detection works (Chrome, Edge, Safari)
- [x] System tray with menu
- [x] Login via web callback
- [x] Daemon start/stop
- [x] Cookie persistence
- [x] Update checker (6-hour interval, platform-specific downloads, non-intrusive)

### macOS
- [x] .dmg builds correctly (via `python desktop/build.py --dmg` on macOS)
- [x] Right-click → Open documented (Phase 6.3)
- [x] URL protocol handler works (Info.plist in PyInstaller spec)
- [x] Code signing support (`--sign` flag)
- [x] Notarization support (`--notarize` flag)
- [x] GitHub Actions CI/CD (`.github/workflows/desktop-build.yml`)

### Windows
- [x] .exe builds correctly (PyInstaller spec with Windows version info)
- [x] MSIX package creation automated (build.py --msix)
- [x] NSIS installer creation automated (build.py --installer)
- [x] SmartScreen instructions documented (INSTALLATION.md)
- [x] URL protocol handler implemented (auto-registered by installer)
- [x] Code signing script provided (sign.ps1)
- [x] GitHub Actions CI/CD (NSIS + MSIX builds)
- [x] Three distribution methods (installer, standalone, MSIX)

### Distribution
- [ ] Download page live
- [ ] Installation instructions clear
- [ ] First-launch instructions prominent

---

## Cost Summary

| Item | Cost |
|------|------|
| Apple Developer (optional for interim unsigned releases) | $0 for testing; $99/yr for Developer ID signing and notarization |
| Windows public trust | $0 for self-signed testing; paid certificate/service or Store enrollment for public distribution |
| **Interim unsigned total** | **$0** |

---

## Timeline

| Phase | Duration | Status |
|-------|----------|--------|
| 1. Architecture | Done | ✅ Done |
| 2. Backend API | 2-3 days | ✅ Done |
| 3. Daemon Remote Mode | 2-3 days | ✅ Done |
| 4. System Tray App | 2-3 days | ✅ Done |
| 5. Python Packaging | 1-2 days | ✅ Done |
| 6. macOS Distribution | 1 day | ✅ Done |
| 7. Windows Distribution | 1-2 days | ✅ Done |
| 8. Auto-Updates | 1 day | ✅ Done |
| 9. Testing | 2-3 days | ⏳ Pending |

**Total: ~2-3 weeks**
