"""Health check endpoints"""
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Response

router = APIRouter()


@router.get("/health")
async def health_check(response: Response):
    """System health check"""
    response.headers["Cache-Control"] = "no-store"
    from openoutreach.api_v2.build_info import APP_VERSION, BUILD_COMMIT
    from openoutreach.mongodb.connection import check_mongodb_connection

    started_at = time.perf_counter()
    database_started_at = started_at
    # Health probes must not tie up an async worker for the full application
    # connection timeout when the database is unavailable.
    mongodb_ok = check_mongodb_connection(timeout_ms=5000)
    database_latency_ms = round((time.perf_counter() - database_started_at) * 1000, 2)
    db_service = "operational" if mongodb_ok else "degraded"
    overall = "operational" if mongodb_ok else "degraded"
    api_latency_ms = round((time.perf_counter() - started_at) * 1000, 2)

    return {
        "status": overall,
        "message": "All systems operational" if mongodb_ok else "Database connectivity issue",
        "build": {"version": APP_VERSION, "commit": BUILD_COMMIT},
        "system": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "database": {
            "connected": mongodb_ok,
            "engine": "MongoDB",
            "engine_type": "nosql",
            "latency_ms": database_latency_ms,
        },
        "api": {
            "latency_ms": api_latency_ms,
        },
        "services": {
            "database": db_service,
            "api": "operational",
            # This endpoint does not contact the provider. Do not report
            # provider health as operational without a real provider probe.
            "linkedin": "unknown",
            "overall": overall,
        },
    }
