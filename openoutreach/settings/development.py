# openoutreach/settings/development.py
"""
Development Django settings for OpenOutreach.
"""

from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY", "django-insecure-dev-key-change-in-production"
)

# Allow all hosts in development
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "*"]

# CORS - Allow all origins in development
CORS_ALLOW_ALL_ORIGINS = True

# Email backend for development (prints to console)
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# =============================================================================
# MongoDB Configuration (Development)
# =============================================================================
# Read MongoDB settings from environment variables for development
import os
from openoutreach.mongodb.settings import get_mongodb_uri, get_mongodb_config

# Read from environment variables (set in docker-compose.yml)
MONGODB_ENABLED = os.environ.get("MONGODB_ENABLED", "false").lower() == "true"
MONGODB_NAME = os.environ.get("MONGODB_NAME", "openoutreach")
MONGODB_HOST = os.environ.get("MONGODB_HOST", "localhost")
MONGODB_PORT = int(os.environ.get("MONGODB_PORT", "27017"))
MONGODB_USER = os.environ.get("MONGODB_USER")
MONGODB_PASSWORD = os.environ.get("MONGODB_PASSWORD")
MONGODB_ATLAS_URI = os.environ.get("MONGODB_ATLAS_URI", "")
DUAL_WRITE_ENABLED = os.environ.get("DUAL_WRITE_ENABLED", "false").lower() == "true"

# =============================================================================
# Logging (Development - verbose)
# =============================================================================
LOGGING["root"]["level"] = "DEBUG"  # type: ignore[call-arg]
LOGGING["loggers"]["openoutreach"]["level"] = "DEBUG"  # type: ignore[call-arg]
LOGGING["loggers"]["openoutreach.mongodb"]["level"] = "DEBUG"  # type: ignore[call-arg]

# =============================================================================
# Database (Development - SQLite)
# =============================================================================
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "data" / "db.sqlite3",
        "TEST": {
            "NAME": BASE_DIR / "data" / "test_db.sqlite3",
            "MIGRATE": True,
            "OPTIONS": {
                "timeout": 30,
            },
        },
    }
}
