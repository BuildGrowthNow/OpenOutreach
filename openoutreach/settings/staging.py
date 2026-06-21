# openoutreach/settings/staging.py
"""
Staging Django settings for OpenOutreach.
This configuration is used for the staging environment.
"""
import os
from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")

# Staging environment hosts
ALLOWED_HOSTS = os.environ.get(
    "DJANGO_ALLOWED_HOSTS",
    "staging.openoutreach.com,staging-api.openoutreach.com",
).split(",")

# CORS - Only allow specific staging domains
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "DJANGO_CORS_ALLOWED_ORIGINS",
        "https://staging.openoutreach.com,https://staging-api.openoutreach.com",
    ).split(",")
]

# Email backend for staging
EMAIL_BACKEND = os.environ.get("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.environ.get("DJANGO_EMAIL_HOST", "smtp.staging-domain.com")
EMAIL_PORT = int(os.environ.get("DJANGO_EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.environ.get("DJANGO_EMAIL_USE_TLS", "true").lower() == "true"
EMAIL_HOST_USER = os.environ.get("DJANGO_EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("DJANGO_EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get("DJANGO_DEFAULT_FROM_EMAIL", "staging@openoutreach.com")

# =============================================================================
# MongoDB Configuration (Staging)
# =============================================================================
MONGODB_ENABLED = os.environ.get("MONGODB_ENABLED", "false").lower() == "true"
MONGODB_NAME = os.environ.get("MONGODB_NAME", "openoutreach_staging")
MONGODB_HOST = os.environ.get("MONGODB_HOST", "localhost")
MONGODB_PORT = int(os.environ.get("MONGODB_PORT", "27017"))
MONGODB_USER = os.environ.get("MONGODB_USER")
MONGODB_PASSWORD = os.environ.get("MONGODB_PASSWORD")

# =============================================================================
# Logging (Staging - production-like but with debug enabled for openoutreach)
# =============================================================================
LOGGING["root"]["level"] = "INFO"  # type: ignore[call-arg]
LOGGING["loggers"]["openoutreach"]["level"] = "DEBUG"  # type: ignore[call-arg]  # Keep openoutreach logs at DEBUG for staging
LOGGING["loggers"]["openoutreach.mongodb"]["level"] = "INFO"  # type: ignore[call-arg]

# =============================================================================
# Database (Staging - can use PostgreSQL)
# =============================================================================
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DATABASE_NAME", "openoutreach_staging"),
        "USER": os.environ.get("DATABASE_USER", "openoutreach"),
        "PASSWORD": os.environ.get("DATABASE_PASSWORD", ""),
        "HOST": os.environ.get("DATABASE_HOST", "localhost"),
        "PORT": os.environ.get("DATABASE_PORT", "5432"),
        "OPTIONS": {
            "sslmode": os.environ.get("DATABASE_SSLMODE", "require"),
        },
    }
}