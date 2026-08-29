"""
FastAPI Application Entry Point
"""
import logging
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Lengrowth API",
    description="LinkedIn Automation Platform - FastAPI + MongoDB",
    version="2.1.2",
    docs_url="/docs",
    redoc_url="/redoc",
    # Preserve FastAPI's canonical trailing-slash redirects for human-facing
    # routes. Daemon proof-of-possession requests use their exact v2 path and
    # are never redirected by the desktop client.
    redirect_slashes=True,
)

# CORS configuration
_cors_origins = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
_allowed_origins = [o.strip() for o in _cors_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DaemonSecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if (request.url.path.startswith("/api/daemon/")
                and not request.url.path.startswith("/api/daemon/v2/")
                and request.url.path.rstrip("/") != "/api/daemon/bootstrap"):
            from openoutreach.api_v2.daemon_security import require_secure_daemon

            try:
                require_secure_daemon(request)
            except HTTPException as exc:
                if exc.status_code != 426:
                    raise
                return JSONResponse(
                    status_code=426,
                    content={"detail": "Desktop security update required"},
                    headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
                )
        response = await call_next(request)
        if request.url.path.startswith("/api/daemon/") or request.url.path == "/api/daemon":
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
        if request.url.path == "/api/auth/refresh/":
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
        return response


app.add_middleware(DaemonSecurityHeadersMiddleware)


@app.on_event("startup")
async def startup():
    """Initialize MongoDB connection and indexes on startup."""
    logger.info("🚀 Initializing FastAPI app...")

    from openoutreach.mongodb.connection import initialize_mongodb_connection
    from openoutreach.mongodb.indexes import ensure_all_indexes
    from openoutreach.billing.stripe_service import init_stripe
    from openoutreach.billing.config import load_from_env

    logger.info("📊 Connecting to MongoDB...")
    if not initialize_mongodb_connection():
        logger.error("❌ Failed to connect to MongoDB")
        raise RuntimeError("MongoDB connection failed")

    logger.info("🔍 Creating indexes...")
    ensure_all_indexes()

    logger.info("💳 Initializing Stripe...")
    init_stripe()
    load_from_env()

    # One-time migration: reset enable_active_hours to False for all site configs
    # that had it stored as True from the old incorrect default.
    try:
        from openoutreach.mongodb.connection import get_mongodb_collection
        site_configs = get_mongodb_collection("site_config")
        if site_configs is not None:
            result = site_configs.update_many(
                {"enable_active_hours": True},
                {"$set": {"enable_active_hours": False}},
            )
            if result.modified_count:
                logger.info("Migration: reset enable_active_hours=True → False for %d site config(s)", result.modified_count)
    except Exception as e:
        logger.warning("Migration enable_active_hours failed: %s", e)

    logger.info("✅ FastAPI app ready!")


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    logger.info("👋 Shutting down FastAPI app...")


# Include routers (will be added as we implement them)
from openoutreach.api_v2.routers import (
    health,
    auth,
    settings,
    campaigns,
    campaign_templates,
    leads,
    messages,
    analytics,
    links,
    state_machine,
    linkedin_credentials,
    linkedin_profiles,
    linkedin_setup,
    notifications,
    websocket,
    daemon,
    vnc,
    admin,
)
from openoutreach.api_v2.routers import daemon_v2

# Import rate limiting and campaign health routers
from openoutreach.api_v2.routers import rate_limits, campaign_health

# Import desktop daemon router
from openoutreach.api_v2.routers import desktop_daemon as desktop_daemon_router

# Email channel
from openoutreach.api_v2.routers import mailboxes as mailboxes_router
from openoutreach.api_v2.routers import email_tracking as email_tracking_router

# Health check (no auth required)
app.include_router(health.router, prefix="/api", tags=["health"])

# Auth endpoints (no auth required)
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])

# Settings
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(mailboxes_router.router, prefix="/api/mailboxes", tags=["email"])
app.include_router(email_tracking_router.router)

# LinkedIn setup
app.include_router(linkedin_credentials.router, prefix="/api/linkedin-credentials", tags=["linkedin"])
app.include_router(linkedin_profiles.router, prefix="/api/linkedin-profiles", tags=["linkedin"])
app.include_router(linkedin_setup.router, prefix="/api/linkedin-setup", tags=["linkedin"])

# Campaigns
app.include_router(campaigns.router, prefix="/api/campaigns", tags=["campaigns"])
app.include_router(campaign_templates.router, prefix="/api/campaign-templates", tags=["templates"])

# CRM
app.include_router(leads.router, prefix="/api/leads", tags=["leads"])
app.include_router(messages.router, prefix="/api/messages", tags=["messages"])

# Analytics
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])

# Phase 6 Secondary Surfaces (deferred features - hidden from launch)
# These routers are included but not exposed via frontend nav or public CTAs.
# Features exist in API but are unsupported post-launch: links, templates, ghost mode, email channel, state machine UI.
# Admin is API-only; no UI for launch phase. See PLATFORM_REMEDIATION_PLAN.md Phase 6 for full rationale.

# Link tracking (Phase 6: deferred; stub returns 501 if called)
app.include_router(links.router, prefix="/api/links", tags=["links"])

# State machine (Phase 6: gated behind NEXT_PUBLIC_ENABLE_STATE_MACHINE=false; daemon ignores state graphs)
app.include_router(state_machine.router, prefix="/api/state-machines", tags=["state-machine"])

# Rate limiting
app.include_router(rate_limits.router, prefix="/api", tags=["rate-limiting"])

# Campaign health monitoring
app.include_router(campaign_health.router, prefix="/api", tags=["campaign-health"])

# Notifications
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])

# Desktop daemon status and heartbeat
app.include_router(desktop_daemon_router.router)

# WebSocket routes
app.include_router(websocket.router, tags=["websocket"])

# Daemon communication
app.include_router(daemon.router, prefix="/api", tags=["daemon"])
app.include_router(daemon_v2.router, prefix="/api", tags=["daemon-v2"])

# VNC session management
app.include_router(vnc.router, prefix="/api", tags=["vnc"])

# Billing
from openoutreach.api_v2.routers.billing import router as billing_router
app.include_router(billing_router, tags=["billing"])

# Admin
app.include_router(admin.router, tags=["admin"])

# WhatsApp channel
from openoutreach.whatsapp.api.router import router as whatsapp_router
app.include_router(whatsapp_router, prefix="/api/whatsapp", tags=["whatsapp"])
