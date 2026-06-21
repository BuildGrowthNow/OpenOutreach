# openoutreach/settings/__init__.py
"""
Django settings package for OpenOutreach.
This package contains environment-specific settings files.

Usage:
    # For local development
    export DJANGO_SETTINGS_MODULE="openoutreach.settings.development"
    python manage.py runserver

    # For staging
    export DJANGO_SETTINGS_MODULE="openoutreach.settings.staging"
    python manage.py runserver

    # For production
    export DJANGO_SETTINGS_MODULE="openoutreach.settings.production"
    python manage.py runserver
"""
from .base import *
from .development import *

__all__ = [
    "BASE_DIR",
    "INSTALLED_APPS",
    "MIDDLEWARE",
    "DATABASES",
    "REST_FRAMEWORK",
    "SECRET_KEY",
    "DEBUG",
    "ALLOWED_HOSTS",
    "CORS_ALLOWED_ORIGINS",
    "LOGGING",
]