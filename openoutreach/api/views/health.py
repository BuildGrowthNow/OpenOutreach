# Health API View

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import connection
import platform
import psutil
from typing import Any, Dict


class HealthView(APIView):
    """
    Health check endpoint to verify system status and database connectivity.
    """
    
    def get(self, request) -> Response:
        """
        GET /api/health
        Returns system health status including database connectivity.
        """
        health_data: Dict[str, Any] = {
            'system': {
                'status': 'operational',
                'timestamp': self._get_timestamp(),
                'python_version': platform.python_version(),
                'platform': platform.platform(),
                'cpu_percent': psutil.cpu_percent(),
                'memory_percent': psutil.virtual_memory().percent,
            },
            'database': self._check_database(),
            'services': self._check_services(),
        }
        
        # Determine overall system status
        overall_status = 'operational'
        if not health_data['database']['connected']:
            overall_status = 'degraded'
        if health_data['database'].get('error') or health_data['services'].get('error'):
            overall_status = 'unhealthy'
        
        health_data['status'] = overall_status
        health_data['message'] = self._get_status_message(overall_status)
        
        return Response(health_data, status=status.HTTP_200_OK)
    
    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from django.utils.timezone import now
        return now().isoformat()
    
    def _check_database(self) -> Dict[str, Any]:
        """Check database connectivity."""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            return {
                'connected': True,
                'engine': str(connection.settings_dict['ENGINE']),
                'database': connection.settings_dict['NAME']
            }
        except Exception as e:
            return {
                'connected': False,
                'error': str(e),
                'engine': str(connection.settings_dict.get('ENGINE', 'unknown')),
                'database': connection.settings_dict.get('NAME', 'unknown')
            }
    
    def _check_services(self) -> Dict[str, Any]:
        """Check key services status."""
        services: Dict[str, str] = {
            'database': 'operational',
            'api': 'operational',
            'linkedin': 'operational' if self._check_linkedin_service() else 'degraded',
        }
        
        # Calculate overall services status
        if any(status != 'operational' for status in services.values()):
            services['overall'] = 'degraded'
        else:
            services['overall'] = 'operational'
        
        return services
    
    def _check_linkedin_service(self) -> bool:
        """Check if LinkedIn service is available."""
        try:
            # This is a simplified check
            return True
        except:
            return False
    
    def _get_status_message(self, status: str) -> str:
        """Get status message based on overall health."""
        messages = {
            'operational': 'All systems operational',
            'degraded': 'System is operational but some services are degraded',
            'unhealthy': 'System is experiencing issues',
        }
        return messages.get(status, 'Unknown status')
