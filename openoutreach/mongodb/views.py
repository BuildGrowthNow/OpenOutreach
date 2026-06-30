from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.http import require_GET
import logging
from .connection import check_mongodb_connection, get_mongodb, mongodb_connection

logger = logging.getLogger(__name__)


@require_GET
def health_check(request):
    """Health check endpoint for MongoDB connection."""
    result = {
        "mongodb": {
            "enabled": False,
            "connected": False,
            "database": None,
            "collection_count": 0,
            "uptime_ms": 0,
        },
        "status": "error",
        "message": "MongoDB not enabled",
    }

    try:
        from django.conf import settings

        result["mongodb"]["enabled"] = getattr(settings, "MONGODB_ENABLED", False)

        if not check_mongodb_connection():
            if result["mongodb"]["enabled"]:
                result["message"] = "MongoDB is enabled but not connected"
                result["status"] = "warning"
            else:
                result["status"] = "ok"
                result["message"] = "MongoDB integration disabled"
            return JsonResponse(result, status=200 if result["status"] == "ok" else 200)

        # MongoDB is connected
        db = get_mongodb()
        result["mongodb"]["connected"] = True
        if db is not None:
            result["mongodb"]["database"] = db.name

        # Get collection count
        if db is not None:
            try:
                result["mongodb"]["collection_count"] = len(db.list_collection_names())
            except Exception as e:
                logger.warning(f"Could not get collection count: {e}")

        # Calculate uptime
        if mongodb_connection._client is not None:
            try:
                server_info = mongodb_connection._client.server_info()
                local_time = server_info.get("localTime", datetime.utcnow())
                result["mongodb"]["uptime_ms"] = (
                    datetime.utcnow() - local_time
                ).total_seconds() * 1000
            except Exception as e:
                logger.warning(f"Could not get server info: {e}")

        result["status"] = "ok"
        result["message"] = "MongoDB is connected and healthy"

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        result["message"] = str(e)
        result["status"] = "error"

    status_code = 200 if result["status"] == "ok" else 503
    return JsonResponse(result, status=status_code)
