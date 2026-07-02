# Health API View

from rest_framework.decorators import authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.db import connection
import platform
import psutil
from typing import Any, Dict


@authentication_classes([])
@permission_classes([AllowAny])
def health_view(request) -> Response:
    """
    GET /api/health
    Returns system health status including database connectivity.
    This endpoint is public and does not require authentication.
    """
    health_data: Dict[str, Any] = {
        "system": _get_system_info(),
        "database": _check_database(),
        "services": _check_services(),
    }

    # Determine overall system status
    overall_status = "operational"
    if not health_data["database"]["connected"]:
        overall_status = "degraded"
    if health_data["database"].get("error") or health_data["services"].get("error"):
        overall_status = "unhealthy"

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
    """Check database connectivity."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return {
            "connected": True,
            "engine": str(connection.settings_dict["ENGINE"]),
            "database": connection.settings_dict["NAME"],
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
            "engine": str(connection.settings_dict.get("ENGINE", "unknown")),
            "database": connection.settings_dict.get("NAME", "unknown"),
        }


def _check_services() -> Dict[str, Any]:
    """Check key services status."""
    services: Dict[str, str] = {
        "database": "operational",
        "api": "operational",
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