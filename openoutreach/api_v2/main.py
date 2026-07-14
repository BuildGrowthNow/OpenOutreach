"""
FastAPI Application Entry Point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import logging

logger = logging.getLogger(__name__)

app = FastAPI(
    title="OpenOutreach API",
    description="LinkedIn Automation Platform - FastAPI + MongoDB",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        os.getenv("FRONTEND_URL", ""),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    """Initialize MongoDB connection and indexes on startup."""
    logger.info("🚀 Initializing FastAPI app...")

    from openoutreach.mongodb.connection import initialize_mongodb_connection
    from openoutreach.mongodb.indexes import ensure_all_indexes

    logger.info("📊 Connecting to MongoDB...")
    if not initialize_mongodb_connection():
        logger.error("❌ Failed to connect to MongoDB")
        raise RuntimeError("MongoDB connection failed")

    logger.info("🔍 Creating indexes...")
    ensure_all_indexes()

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
)

# Import new auth v2 router for multi-tenant
from openoutreach.api_v2.routers import auth_v2

# Health check (no auth required)
app.include_router(health.router, prefix="/api", tags=["health"])

# Auth endpoints (no auth required)
# Legacy auth (Supabase) - backwards compatibility
app.include_router(auth.router, prefix="/api/auth/legacy", tags=["auth-legacy"])

# New multi-tenant auth - production
app.include_router(auth_v2.router, prefix="/api/auth", tags=["auth"])

# Settings
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])

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

# Link tracking
app.include_router(links.router, prefix="/api/links", tags=["links"])

# State machine
app.include_router(state_machine.router, prefix="/api/state-machine", tags=["state-machine"])

# Notifications
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])

# WebSocket routes
app.include_router(websocket.router, tags=["websocket"])
