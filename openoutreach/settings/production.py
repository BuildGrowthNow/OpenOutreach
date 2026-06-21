# openoutreach/settings/production.py
"""
Production Django settings for OpenOutreach.
This configuration is used for the production environment.
"""
import os
from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")

# Production environment hosts - MUST be set
ALLOWED_HOSTS = os.environ.get(
    "DJANGO_ALLOWED_HOSTS",
    "",
).split(",")

# Validate that ALLOWED_HOSTS is set in production
if not ALLOWED_HOSTS or ALLOWED_HOSTS == [""]:
    raise ValueError(
        "DJANGO_ALLOWED_HOSTS must be set in production environment. "
        "Example: DJANGO_ALLOWED_HOSTS=api.openoutreach.com,www.openoutreach.com"
    )

# Validate SECRET_KEY is set in production
if not SECRET_KEY or SECRET_KEY == "":
    raise ValueError(
        "DJANGO_SECRET_KEY must be set in production environment. "
        "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(50))'"
    )

# CORS - Only allow specific production domains
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "DJANGO_CORS_ALLOWED_ORIGINS",
        "https://openoutreach.com,https://www.openoutreach.com",
    ).split(",")
]

# Email backend for production (always use SMTP)
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("DJANGO_EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("DJANGO_EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.environ.get("DJANGO_EMAIL_USE_TLS", "true").lower() == "true"
EMAIL_HOST_USER = os.environ.get("DJANGO_EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("DJANGO_EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get("DJANGO_DEFAULT_FROM_EMAIL", "noreply@openoutreach.com")

# =============================================================================
# MongoDB Configuration (Production)
# =============================================================================
MONGODB_ENABLED = os.environ.get("MONGODB_ENABLED", "false").lower() == "true"
MONGODB_NAME = os.environ.get("MONGODB_NAME", "openoutreach")
MONGODB_HOST = os.environ.get("MONGODB_HOST", "localhost")
MONGODB_PORT = int(os.environ.get("MONGODB_PORT", "27017"))
MONGODB_USER = os.environ.get("MONGODB_USER")
MONGODB_PASSWORD = os.environ.get("MONGODB_PASSWORD")

# =============================================================================
# Logging (Production)
# =============================================================================
LOGGING["root"]["level"] = "WARNING"  # type: ignore[call-arg]  # Reduce noise in production
LOGGING["loggers"]["openoutreach"]["level"] = "INFO"  # type: ignore[call-arg]  # Keep at INFO for visibility
LOGGING["loggers"]["openoutreach.mongodb"]["level"] = "WARNING"  # type: ignore[call-arg]  # Reduce MongoDB noise

# =============================================================================
# Database (Production - must use PostgreSQL)
# =============================================================================
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DATABASE_NAME", "openoutreach"),
        "USER": os.environ.get("DATABASE_USER", "openoutreach"),
        "PASSWORD": os.environ.get("DATABASE_PASSWORD", ""),
        "HOST": os.environ.get("DATABASE_HOST", "localhost"),
        "PORT": os.environ.get("DATABASE_PORT", "5432"),
        "OPTIONS": {
            "sslmode": os.environ.get("DATABASE_SSLMODE", "require"),
        },
    }
}

# =============================================================================
# Sentry Configuration (Optional)
# =============================================================================
# Enable Sentry for error tracking if sentry-sdk is installed and DSN is set
# To use Sentry, install: pip install sentry-sdk
SENTRY_DSN = os.environ.get("SENTRY_DSN")
if SENTRY_DSN:
    try:
        import sentry_sdk  # type: ignore[import-not-found]
        from sentry_sdk.integrations.django import DjangoIntegration  # type: ignore[import-not-found]

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[DjangoIntegration()],
            traces_sample_rate=0.1,
            profiles_sample_rate=0.1,
            environment="production",
        )
        # Update logging to include Sentry handler
        LOGGING["handlers"]["sentry"] = {  # type: ignore[call-arg]
            "class": "sentry_sdk.integrations.logging.SentryHandler",
            "level": "ERROR",
            "formatter": "verbose",
        }
        LOGGING["loggers"]["openoutreach"]["handlers"].append("sentry")  # type: ignore[call-arg]
        LOGGING["loggers"]["django.request"]["handlers"].append("sentry")  # type: ignore[call-arg]
    except ImportError:
        pass  # Sentry not installed, skip Sentry configuration

# =============================================================================
# Security middleware settings (Production only)
# =============================================================================
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True