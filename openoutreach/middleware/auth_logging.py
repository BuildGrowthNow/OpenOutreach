"""Middleware to log Authorization header for incoming requests.

This is a temporary debugging middleware to help trace why requests
are getting 401 responses. It prints the `Authorization` header and
the request path to stdout so the Docker logs capture it.
"""
from typing import Callable

from django.http import HttpRequest, HttpResponse


class AuthHeaderLoggingMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        auth = request.META.get('HTTP_AUTHORIZATION')
        if auth:
            print(f"[AuthHeaderLogging] {request.method} {request.path} Authorization: {auth[:200]}")
        else:
            print(f"[AuthHeaderLogging] {request.method} {request.path} Authorization: (none)")
        return self.get_response(request)
