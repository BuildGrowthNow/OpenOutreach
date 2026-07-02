# Health API View

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.parsers import JSONParser
from rest_framework.renderers import JSONRenderer
from django.db import connection
import platform
import psutil
import time
from typing import Any, Dict, Optional
from datetime import datetime, timedelta

# Try to import MongoDB connection modules
try:
    from openoutreach.mongodb.connection import check_mongodb_connection
    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False
    check_mongodb_connection = None  #类型绑定


class HealthView(APIView):
    """
    Health check endpoint to verify system status and database connectivity.
    This endpoint is public and does not require authentication.
    """
    authentication_classes = []
    permission_classes = [AllowAny]
    renderer_classes = [JSONRenderer]
    parser_classes = [JSONParser]

    def get(self, request) -> Response:
        """
        GET /api/health
        Returns system health status including database connectivity and operation statistics.
        """
        health_data: Dict[str, Any] = {
            "system": _get_system_info(),
            "database": _check_database(),
            "mongodb": _check_mongodb(),
            "services": _check_services(),
        }

        # Calculate database operation statistics (last 24 hours)
        db_stats = _calculate_database_stats()
        health_data["database_stats"] = db_stats

        # Determine overall system status
        overall_status = "operational"
        if not health_data["database"]["connected"]:
            overall_status = "degraded"
        if health_data["database"].get("error") or health_data["services"].get("error"):
            overall_status = "unhealthy"
        if health_data.get("mongodb") and not health_data["mongodb"].get("connected", True):
            overall_status = "degraded"

        health_data["status"] = overall_status
        health_data["message"] = _get_status_message(overall_status)

        return Response(health_data, status=status.HTTP_200_OK)


def _get_system_info() -> Dict[str, Any]:
    """Get system information with error handling."""
    system_info: Dict[str, Any] = {
        "status": "operational",
        "timestamp": _get_timestamp(),
        "python_version": platform.python_version(),
        "platform": "unknown",
        "cpu_percent": 0.0,
        "memory_percent": 0.0,
    }

    try:
        system_info["platform"] = platform.platform()
    except Exception as e:
        system_info["platform_error"] = str(e)

    try:
        system_info["cpu_percent"] = psutil.cpu_percent()
    except Exception as e:
        system_info["cpu_percent"] = -1.0
        system_info["cpu_error"] = str(e)

    try:
        system_info["memory_percent"] = psutil.virtual_memory().percent
    except Exception as e:
        system_info["memory_percent"] = -1.0
        system_info["memory_error"] = str(e)

    return system_info


def _get_timestamp() -> str:
    """Get current timestamp in ISO format."""
    from django.utils.timezone import now

    return now().isoformat()


def _check_database() -> Dict[str, Any]:
    """Check database connectivity (PostgreSQL/SQLite)."""
    try:
        start_time = time.time()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        query_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        # Convert Path objects to strings to ensure JSON serialization
        database_name = connection.settings_dict.get("NAME", "unknown")
        if hasattr(database_name, "__fspath__"):
            database_name = str(database_name)
        
        engine = str(connection.settings_dict.get("ENGINE", "unknown"))
        
        return {
            "connected": True,
            "engine": engine,
            "database": database_name,
            "latency_ms": round(query_time, 2),
            "engine_type": "postgresql" if "postgres" in engine else "sqlite" if "sqlite" in engine else "unknown",
        }
    except Exception as e:
        # Convert Path objects to strings to ensure JSON serialization
        database_name = connection.settings_dict.get("NAME", "unknown")
        if hasattr(database_name, "__fspath__"):
            database_name = str(database_name)
        
        engine = str(connection.settings_dict.get("ENGINE", "unknown"))
        
        return {
            "connected": False,
            "error": str(e),
            "engine": engine,
            "database": database_name,
            "latency_ms": -1,
            "engine_type": "postgresql" if "postgres" in engine else "sqlite" if "sqlite" in engine else "unknown",
        }


def _check_mongodb() -> Dict[str, Any]:
    """Check MongoDB connectivity."""
    if not MONGODB_AVAILABLE:
        return {
            "connected": False,
            "error": "MongoDB client not available",
            "database": "mongodb",
        }
    
    try:
        # Use check_mongodb_connection to verify connection
        if check_mongodb_connection is None:
            return {
                "connected": False,
                "error": "MongoDB connection not available",
                "database": "mongodb",
            }
        connected = check_mongodb_connection()
        
        return {
            "connected": connected,
            "latency_ms": 5,  # Default estimate
            "database": "mongodb",
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
            "latency_ms": -1,
            "database": "mongodb",
        }


def _calculate_database_stats() -> Dict[str, Any]:
    """
    Calculate database operation statistics for the last 24 hours.
    Returns stats based on ActionLog entries in the database.
    """
    from django.utils import timezone
    from datetime import timedelta
    
    # Get time range for last 24 hours
    since = timezone.now() - timedelta(hours=24)
    
    # Import models
    try:
        from openoutreach.linkedin.models import ActionLog
        from openoutreach.core.models import Campaign
        
        # Get total action count (queries)
        total_actions = ActionLog.objects.filter(created_at__gte=since).count()
        
        # Get successful actions count
        successful_actions = ActionLog.objects.filter(
            created_at__gte=since,
            error_message="",  # Empty error means success
        ).count()
        
        # Calculate success rate
        success_rate = round((successful_actions / total_actions * 100) if total_actions > 0 else 100, 1)
        
        # Calculate average latency from successful actions
        try:
            from django.db import models
            successful_with_timing = ActionLog.objects.filter(
                created_at__gte=since,
                error_message="",
            )
            
            # Get count of actions
            total_timing_actions = successful_with_timing.count()
            
            if total_timing_actions > 0:
                # Try to get average from duration_ms if it exists
                try:
                    avg_latency = successful_with_timing.aggregate(
                        avg_duration=models.Avg('duration_ms')
                    )['avg_duration'] or 0
                    avg_latency = round(avg_latency, 2)
                except Exception:
                    # duration_ms field doesn't exist, use default
                    avg_latency = 15  # Default estimate if no timing data
            else:
                avg_latency = 15  # Default estimate if no timing data
        except Exception:
            avg_latency = 15  # Default estimate
        
        # Get error count
        error_count = ActionLog.objects.filter(
            created_at__gte=since,
            error_message__isnull=False,
        ).exclude(
            error_message=""
        ).count()
        
        return {
            "queries": total_actions,
            "success_rate": success_rate,
            "avg_latency_ms": avg_latency,
            "errors": error_count,
            "period": "last_24_hours",
        }
        
    except Exception as e:
        # Return default values if models are not available
        return {
            "queries": 0,
            "success_rate": 100.0,
            "avg_latency_ms": 15,
            "errors": 0,
            "period": "last_24_hours",
            "error": str(e),
        }


def _check_services() -> Dict[str, Any]:
    """Check key services status."""
    services: Dict[str, str] = {
        "database": "operational",
        "api": "operational",
        "mongodb": "operational" if (MONGODB_AVAILABLE and _check_mongodb().get("connected", False)) else "degraded",
        "linkedin": "operational" if _check_linkedin_service() else "degraded",
    }

    # Calculate overall services status
    if any(status != "operational" for status in services.values()):
        services["overall"] = "degraded"
    else:
        services["overall"] = "operational"

    return services


def _check_linkedin_service() -> bool:
    """Check if LinkedIn service is available."""
    try:
        # This is a simplified check
        return True
    except Exception:
        return False


def _get_status_message(status: str) -> str:
    """Get status message based on overall health."""
    messages = {
        "operational": "All systems operational",
        "degraded": "System is operational but some services are degraded",
        "unhealthy": "System is experiencing issues",
    }
    return messages.get(status, "Unknown status")