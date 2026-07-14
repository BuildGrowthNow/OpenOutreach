"""Health check endpoints"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """System health check"""
    from openoutreach.mongodb.connection import check_mongodb_connection

    mongodb_ok = check_mongodb_connection()

    return {
        "status": "ok" if mongodb_ok else "degraded",
        "mongodb": "connected" if mongodb_ok else "disconnected",
        "version": "2.0.0",
    }
