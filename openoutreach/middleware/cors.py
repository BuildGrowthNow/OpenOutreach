"""
Custom CORS middleware to ensure CORS headers are added to all responses,
including error responses (like 401, 403).
"""

from typing import Optional
from django.conf import settings
from django.http import HttpRequest, HttpResponse


class AddCorsHeadersToResponseMiddleware:
    """
    Middleware to add CORS headers to all responses, including error responses.
    
    This middleware ensures that CORS headers are added even when responses
    return error codes like 401, 403, etc., which is important for API
    calls from different origins.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.cors_allow_all_origins = getattr(settings, 'CORS_ALLOW_ALL_ORIGINS', True)
        
        # Get allowed origins from settings
        if self.cors_allow_all_origins:
            self.allowed_origins: Optional[list[str]] = None
        else:
            self.allowed_origins = getattr(settings, 'CORS_ALLOWED_ORIGINS', [])
        
        # Get other CORS settings
        self.cors_allow_credentials = getattr(settings, 'CORS_ALLOW_CREDENTIALS', False)
        self.cors_allowed_methods = getattr(settings, 'CORS_ALLOWED_METHODS', [
            'DELETE', 'GET', 'OPTIONS', 'PATCH', 'POST', 'PUT'
        ])
        self.cors_allowed_headers = getattr(settings, 'CORS_ALLOWED_HEADERS', [
            'accept', 'accept-encoding', 'authorization', 'content-type',
            'dnt', 'origin', 'user-agent', 'x-csrftoken', 'x-requested-with'
        ])
        self.cors_exposed_headers = getattr(settings, 'CORS_EXPOSED_HEADERS', [])
    
    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Handle preflight requests (OPTIONS)
        if request.method == 'OPTIONS':
            # Check if the request has Origin header
            origin = request.META.get('HTTP_ORIGIN', '')
            
            if origin:
                # Check if the origin is allowed
                origin_allowed = self._is_origin_allowed(origin)
                
                # Build response for preflight
                response = HttpResponse(status=200)
                response['Access-Control-Allow-Origin'] = origin if origin_allowed else ''
                response['Access-Control-Allow-Methods'] = ', '.join(self.cors_allowed_methods)
                response['Access-Control-Allow-Headers'] = ', '.join(self.cors_allowed_headers)
                if self.cors_allow_credentials:
                    response['Access-Control-Allow-Credentials'] = 'true'
                response['Access-Control-Max-Age'] = '86400'  # 24 hours
                
                return response
        
        # For actual requests, get the response first
        response = self.get_response(request)
        
        # Add CORS headers to all responses (including errors)
        self._add_cors_headers(request, response)
        
        return response
    
    def _is_origin_allowed(self, origin: str) -> bool:
        """Check if an origin is allowed based on settings."""
        if self.cors_allow_all_origins:
            return True
        
        if self.allowed_origins is None:
            return False
        
        return origin in self.allowed_origins
    
    def _add_cors_headers(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Add CORS headers to the response."""
        origin = request.META.get('HTTP_ORIGIN', '')
        
        if origin:
            # Check if the origin is allowed
            origin_allowed = self._is_origin_allowed(origin)
            
            if origin_allowed:
                response['Access-Control-Allow-Origin'] = origin
            else:
                response['Access-Control-Allow-Origin'] = ''
        
        if self.cors_allow_credentials:
            response['Access-Control-Allow-Credentials'] = 'true'
        
        # Always set Vary header if Access-Control-Allow-Origin is set
        if response.get('Access-Control-Allow-Origin'):
            response['Vary'] = 'Origin'
        
        # Add exposed headers if configured
        if self.cors_exposed_headers:
            response['Access-Control-Expose-Headers'] = ', '.join(self.cors_exposed_headers)
        
        # Add max age for preflight caching
        response['Access-Control-Max-Age'] = '86400'  # 24 hours
        
        return response