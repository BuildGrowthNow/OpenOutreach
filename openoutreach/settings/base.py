# openoutreach/settings/base.py
"""
Base Django settings for OpenOutreach.
This is the foundation configuration used by all environments.
"""
import os
from pathlib import Path
from datetime import timedelta
from typing import Optional, Any

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# =============================================================================
# Supabase Configuration (Required for authentication)
# =============================================================================
SUPABASE_URL: Optional[str] = os.environ.get("SUPABASE_URL")
SUPABASE_ANON_KEY: Optional[str] = os.environ.get("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_KEY: Optional[str] = os.environ.get("SUPABASE_SERVICE_KEY")

# =============================================================================
# Security Settings - Base Configuration
# =============================================================================
SECRET_KEY: str = os.environ.get("DJANGO_SECRET_KEY", "change-me-in-production")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG: bool = False

ALLOWED_HOSTS: list[str] = ["localhost", "127.0.0.1"]

# =============================================================================
# Application definition
# =============================================================================
INSTALLED_APPS = [
    "django.contrib.sites",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party apps
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    # Local apps
    "openoutreach.api.apps.ApiConfig",
    "openoutreach.crm.apps.CrmConfig",
    "openoutreach.chat.apps.ChatConfig",
    "openoutreach.core.apps.CoreConfig",
    "openoutreach.linkedin.apps.LinkedInConfig",
    "openoutreach.emails.apps.EmailsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "openoutreach.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "openoutreach.wsgi.application"

# =============================================================================
# Database Configuration
# =============================================================================
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "data" / "db.sqlite3",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# =============================================================================
# Internationalization
# =============================================================================
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# =============================================================================
# Static Files (CSS, JavaScript, Images)
# =============================================================================
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# =============================================================================
# Default Primary Key Field Type
# =============================================================================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# =============================================================================
# Authentication
# =============================================================================
LOGIN_URL = "/admin/login/"
DEFAULT_FROM_EMAIL = "noreply@localhost"
EMAIL_SUBJECT_PREFIX = "CRM: "

# =============================================================================
# REST Framework Configuration
# =============================================================================
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
        "openoutreach.api.authentication.supabase.SupabaseJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/day",
        "user": "1000/day",
    },
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "EXCEPTION_HANDLER": "rest_framework.views.exception_handler",
}

# =============================================================================
# JWT Authentication Configuration
# =============================================================================
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "VERIFYING_KEY": None,
    "AUDIENCE": None,
    "ISSUER": None,
    "JWK_URL": None,
    "LEEWAY": 0,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "USER_AUTHENTICATION_RULE": "rest_framework_simplejwt.authentication.default_user_authentication_rule",
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "TOKEN_USER_CLASS": "rest_framework_simplejwt.models.TokenUser",
    "JTI_CLAIM": "jti",
    "SLIDING_TOKEN_REFRESH_EXP_CLAIM": "refresh_exp",
    "SLIDING_TOKEN_LIFETIME": timedelta(minutes=5),
    "SLIDING_TOKEN_REFRESH_LIFETIME": timedelta(days=1),
}

# =============================================================================
# CORS Configuration - Base (overridden in production/staging)
# =============================================================================
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = True  # Overridden in production
CORS_ALLOWED_ORIGINS: list[str] = []

CORS_ALLOWED_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]

CORS_ALLOWED_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]

# =============================================================================
# Logging Configuration - Base
# =============================================================================
LOGGING: dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{levelname}] {asctime} {name}:{module}:{lineno} - {message}",
            "style": "{",
        },
        "simple": {
            "format": "[{levelname}] {message}",
            "style": "{",
        },
        "structured": {
            "format": '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
                      '"logger": "%(name)s", "module": "%(module)s", '
                      '"lineno": %(lineno)d, "message": "%(message)s"}',
            "style": "%",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "file": {
            "class": "logging.FileHandler",
            "filename": str(BASE_DIR / "data" / "app.log"),
            "formatter": "verbose",
        },
        # Production logging handlers (enable in production.py)
        "error_file": {
            "class": "logging.FileHandler",
            "filename": str(BASE_DIR / "data" / "error.log"),
            "formatter": "verbose",
            "level": "ERROR",
        },
        "warning_file": {
            "class": "logging.FileHandler",
            "filename": str(BASE_DIR / "data" / "warning.log"),
            "formatter": "verbose",
            "level": "WARNING",
        },
        # Sentry handler (optional - requires sentry-sdk)
        # Sentry handler (optional - enabled in production.py via sentry-sdk)
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "openoutreach": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": True,
        },
        "openoutreach.mongodb": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": True,
        },
        "openoutreach.error": {
            "handlers": ["console", "error_file"],
            "level": "ERROR",
            "propagate": False,
        },
        "openoutreach.warning": {
            "handlers": ["console", "warning_file"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.db.backends": {
            "level": "ERROR",
        },
        "django.request": {
            "handlers": ["error_file"],
            "level": "ERROR",
            "propagate": False,
        },
        # Sentry logger (optional - enabled in production.py via sentry-sdk)
    },
}

# =============================================================================
# Sentry Configuration (Optional - Production)
# =============================================================================
# Enable Sentry for error tracking in production
# Set SENTRY_DSN in environment to enable
# SENTRY_DSN = os.environ.get("SENTRY_DSN")
# SENTRY_TRACES_SAMPLE_RATE = 0.1
# SENTRY_PROFILES_SAMPLE_RATE = 0.1

# =============================================================================
# Production Environment Detection
# =============================================================================
# Detect if we're running in production for conditional logging configuration
IS_PRODUCTION = os.environ.get("DJANGO_ENV", "development").lower() == "production"

# =============================================================================
# MongoDB Configuration (Optional)
# =============================================================================
MONGODB_ENABLED: bool = False
MONGODB_NAME: str = "openoutreach"
MONGODB_HOST: str = "localhost"
MONGODB_PORT: int = 27017
MONGODB_USER: str | None = None
MONGODB_PASSWORD: str | None = None

# =============================================================================
# Site ID for Django sites framework
# =============================================================================
SITE_ID = 1