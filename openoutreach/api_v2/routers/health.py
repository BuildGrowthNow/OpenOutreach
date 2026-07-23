"""Health check endpoints"""
import sys
import platform
from datetime import datetime, timezone

import psutil
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """System health check"""
    from openoutreach.mongodb.connection import check_mongodb_connection

    mongodb_ok = check_mongodb_connection()
    db_service = "operational" if mongodb_ok else "degraded"
    overall = "operational" if mongodb_ok else "degraded"

    return {
        "status": overall,
        "message": "All systems operational" if mongodb_ok else "Database connectivity issue",
        "system": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "python_version": sys.version.split()[0],
            "platform": platform.system(),
            "cpu_percent": psutil.cpu_percent(interval=None),
            "memory_percent": psutil.virtual_memory().percent,
        },
        "database": {
            "connected": mongodb_ok,
            "engine": "MongoDB",
            "engine_type": "nosql",
        },
        "services": {
            "database": db_service,
            "api": "operational",
            "linkedin": "operational",
            "overall": overall,
        },
    }
