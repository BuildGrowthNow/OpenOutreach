# openoutreach/settings/development.py
"""
Development Django settings for OpenOutreach.
"""
from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-insecure-dev-key-change-in-production")

# Allow all hosts in development
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "*"]

# CORS - Allow all origins in development
CORS_ALLOW_ALL_ORIGINS = True

# Email backend for development (prints to console)
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# =============================================================================
# MongoDB Configuration (Development)
# =============================================================================
MONGODB_ENABLED = False

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
    }
}