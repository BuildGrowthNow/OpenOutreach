# openoutreach/settings.py
"""
Django settings for OpenOutreach with REST API configuration.
"""
import os
import sys
import logging
from pathlib import Path
from datetime import timedelta
from typing import Optional

# Create logger
logger = logging.getLogger(__name__)

# =============================================================================
# Supabase Configuration (Required for authentication)
# =============================================================================
# Initialize Supabase configuration variables
SUPABASE_URL: Optional[str] = None
SUPABASE_ANON_KEY: Optional[str] = None
SUPABASE_SERVICE_KEY: Optional[str] = None

# Load from environment variables
try:
    from .env import SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY
except ImportError:
    # Fall back to os.environ for development
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

# Log Supabase configuration status
if SUPABASE_URL and SUPABASE_ANON_KEY:
    logger.info("Supabase configuration loaded successfully")
else:
    logger.warning(
        "Supabase not fully configured. Some authentication features may not work. "
        "Please set SUPABASE_URL, SUPABASE_ANON_KEY, and SUPABASE_SERVICE_KEY in environment."
    )

# Playwright's sync API runs inside an async event loop, which triggers
# Django's async-safety check. We only use the ORM synchronously, so this is safe.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

ROOT_DIR = Path(__file__).resolve().parent.parent

BASE_DIR = ROOT_DIR

SECRET_KEY = "openoutreach-local-dev-key-change-in-production"

DEBUG = True

ALLOWED_HOSTS = ["*"]

# Application definition
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
    "corsheaders.middleware.CorsMiddleware",  # Added for CORS support
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

DATABASES = {  # type: ignore[assignment]
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(ROOT_DIR / "data" / "db.sqlite3"),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SITE_ID = 1

STATIC_URL = "/static/"
STATIC_ROOT = ROOT_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = ROOT_DIR / "media"

LOGIN_URL = "/admin/login/"

DEFAULT_FROM_EMAIL = "noreply@localhost"
EMAIL_SUBJECT_PREFIX = "CRM: "

LANGUAGE_CODE = "en"
LANGUAGES = [("en", "English")]
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

TESTING = sys.argv[1:2] == ["test"]

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
        # Supabase JWT Authentication (for frontend)
        'openoutreach.api.authentication.supabase.SupabaseJWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/day',
    },
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'EXCEPTION_HANDLER': 'rest_framework.views.exception_handler',
}

# JWT Authentication Configuration
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': False,
    
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,
    'JWK_URL': None,
    'LEEWAY': 0,
    
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule',
    
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
    'TOKEN_USER_CLASS': 'rest_framework_simplejwt.models.TokenUser',
    
    'JTI_CLAIM': 'jti',
    
    'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp',
    'SLIDING_TOKEN_LIFETIME': timedelta(minutes=5),
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=1),
}

# CORS Configuration for frontend-backend communication
CORS_ALLOW_ALL_ORIGINS = True  # For development only
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",  # Next.js frontend
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
]
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# Environment-specific settings
if not DEBUG:
    CORS_ALLOW_ALL_ORIGINS = False
    SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', SECRET_KEY)
    
    # Add production CORS origins
    CORS_ALLOWED_ORIGINS.extend([
        "https://your-production-domain.com",
        # Add other production domains as needed
    ])

# ==================== MongoDB Configuration ====================
# MongoDB integration via Djongo connector
# Set MONGODB_ENABLED=true in environment to use MongoDB
# For MongoDB Atlas: set MONGODB_ATLAS_URI=mongodb+srv://user:pass@cluster.mongodb.net/dbname

# Type annotation for MongoDB_URI
MongoDB_URI: str | None = None

try:
    from openoutreach.mongodb.settings import (
        MONGODB_ENABLED,
        MONGODB_NAME,
        MONGODB_HOST,
        MONGODB_PORT,
        MONGODB_ATLAS_URI,
        DUAL_WRITE_ENABLED,
        get_mongodb_uri,
        get_mongodb_config
    )
    
    MONGODB_SERVER_SELECTION_TIMEOUT = 30000
    MONGODB_CONNECT_TIMEOUT = 30000
    MONGODB_SOCKET_TIMEOUT = 10000
    MONGODB_NAME = MONGODB_NAME
    
    # Configure MongoDB connection based on environment
    if MONGODB_ENABLED:
        MongoDB_URI = get_mongodb_uri() or MONGODB_ATLAS_URI
        logger.info("MongoDB integration enabled via Djongo")
    else:
        logger.info("MongoDB integration disabled, using SQLite")
        
except ImportError:
    MONGODB_ENABLED = False
    logger.info("MongoDB module not available, using SQLite only")

# =============================================================================
# Logging Configuration
# =============================================================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {name}:{module}:{lineno} - {message}',
            'style': '{',
        },
        'simple': {
            'format': '[{levelname}] {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': str(ROOT_DIR / 'data' / 'app.log'),
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'openoutreach': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'openoutreach.mongodb': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'django.db.backends': {
            'level': 'ERROR',
        },
    },
}

# MongoDB Database Configuration (when MONGODB_ENABLED=true)
# Uses Djongo connector to interface with MongoDB
if MONGODB_ENABLED:
    #type: ignore[typeddict-item]
    DATABASES = {  # type: ignore[assignment]
        'default': {
            'ENGINE': 'djongo',
            'NAME': MONGODB_NAME,
            'ENFORCE_SCHEMA': False,
            'LOGGING': {
                'level': 'DEBUG' if DEBUG else 'INFO',
                'log_queries': DEBUG,
            },
        }
    }
