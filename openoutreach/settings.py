# openoutreach/settings.py
"""
Django settings for OpenOutreach with REST API configuration.
"""

import os
import sys
import logging
from pathlib import Path
from datetime import timedelta

# Initialize logging with an informational default to keep noisy third-party logs out of the console.
log_level_name = os.environ.get("OPENOUTREACH_LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_name, logging.INFO)
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
    force=True,
)

# Suppress verbose logging from all third-party libraries
# Set logging to WARNING or higher for noisy loggers
for noisy_logger in (
    "urllib3",
    "urllib3.connectionpool",
    "httpx",
    "pydantic_ai",
    "openai",
    "playwright",
    "httpcore",
    "fastembed",
    "huggingface_hub",
    "filelock",
    "asyncio",
    "requests",
    "pymongo",
    "pymongo.command",
    "pymongo.monitor",
    "pymongo.network",
    "pymongo.topology",
    "pymongo.server_selection",
    "pymongo.connection",
    "pymongo.client",
    "pymongo.uri_parser",
    "pymongo.events",
    "pymongo.operations",
    "pymongo.ismaster",
    "pymongo.hello",
    "pymongo.server",
    "pymongo.pool",
    "pymongo.restricted",
    "gridfs",
    "bson",
):
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)

# Explicitly set all MongoDB-related loggers to WARNING or higher to suppress DEBUG logs
logging.getLogger("openoutreach.mongodb").setLevel(logging.WARNING)

# For pymongo driver logs (server heartbeat, topology, etc.), set to CRITICAL to suppress
# Only ERROR and CRITICAL messages will be visible (index/collection creation errors)
logging.getLogger("pymongo-topology").setLevel(logging.CRITICAL)
logging.getLogger("pymongo-server-selection").setLevel(logging.CRITICAL)
logging.getLogger("pymongo-monitor").setLevel(logging.CRITICAL)
logging.getLogger("pymongo-network").setLevel(logging.CRITICAL)
logging.getLogger("pymongo.client").setLevel(logging.CRITICAL)
logging.getLogger("pymongo").setLevel(logging.WARNING)

# Clear existing handlers on MongoDB-related loggers to prevent duplicate logging
for logger_name in (
    "pymongo",
    "pymongo.command",
    "pymongo.monitor",
    "pymongo.network",
    "pymongo.topology",
    "pymongo.server_selection",
    "pymongo.connection",
    "pymongo.client",
    "pymongo.uri_parser",
    "pymongo.events",
    "pymongo.operations",
    "pymongo.ismaster",
    "pymongo.hello",
    "pymongo.server",
    "pymongo.pool",
    "pymongo.restricted",
    "pymongo-driver",
):
    try:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.ERROR)  # Only show actual errors
        # Remove any existing handlers
        logger.handlers = []
        logger.propagate = False
    except Exception:
        pass

# Use Django's default User model (from django.contrib.auth)
# No custom user model needed - using default auth.User
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
    from .env import SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY  # type: ignore[import]
except ImportError:
    # Fall back to os.environ for development
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

# Log Supabase configuration status
if SUPABASE_URL and SUPABASE_ANON_KEY:
    logger.info(f"Supabase configuration loaded successfully (URL: {SUPABASE_URL})")
    if SUPABASE_SERVICE_KEY:
        logger.info(f"Supabase SERVICE_KEY loaded (first 20 chars: {SUPABASE_SERVICE_KEY[:20]}...)")
    else:
        logger.warning("Supabase SERVICE_KEY NOT configured - JWT verification will fail")
else:
    logger.warning(
        "Supabase not fully configured. Some authentication features may not work. "
        "Please set SUPABASE_URL, SUPABASE_ANON_KEY, and SUPABASE_SERVICE_KEY in environment."
    )

# =============================================================================
# Django Core Configuration
# =============================================================================

# Local development default (used if not found in environment)
SECRET_KEY_DEV = "openoutreach-local-dev-key-change-in-production"

# Load SECRET_KEY from environment variables
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY", os.environ.get("SECRET_KEY", SECRET_KEY_DEV)
)

# Load DEBUG from environment (default to False in production)
DEBUG = os.environ.get("DEBUG", "False").lower() in ("true", "1", "t")

# Load ALLOWED_HOSTS from environment - comma-separated list
# Strip protocol (http/https) from hostnames if present
ALLOWED_HOSTS_STR = os.environ.get("ALLOWED_HOSTS", "")
if ALLOWED_HOSTS_STR:
    ALLOWED_HOSTS = []
    for host in ALLOWED_HOSTS_STR.split(","):
        host = host.strip()
        # Remove protocol prefix if present
        if host.startswith("https://"):
            host = host[8:]
        elif host.startswith("http://"):
            host = host[7:]
        if host:
            ALLOWED_HOSTS.append(host)
else:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

# Playwright's sync API runs inside an async event loop, which triggers
# Django's async-safety check. We only use the ORM synchronously, so this is safe.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

ROOT_DIR = Path(__file__).resolve().parent.parent

BASE_DIR = ROOT_DIR

# Disable Django's automatic trailing slash addition
# APPEND_SLASH = False prevents 301 redirects when frontend calls
# endpoints without trailing slashes (which would lose authentication headers)
APPEND_SLASH = False

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
    "openoutreach.linkedin.apps.LinkedInConfig",
    "openoutreach.emails.apps.EmailsConfig",
    "openoutreach.mongodb.apps.MongoDBConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "openoutreach.middleware.auth_logging.AuthHeaderLoggingMiddleware",
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

# =============================================================================
# REST Framework Configuration - Supabase JWT must be FIRST
# =============================================================================
# The SupabaseJWTAuthentication must be the FIRST authentication class
# because the frontend sends Supabase JWT tokens (signed with Supabase's service key)
# not Django SimpleJWT tokens (signed with SECRET_KEY)
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        # Supabase JWT Authentication (for frontend) - MUST BE FIRST
        # This authenticates users using Supabase JWT tokens
        "openoutreach.api.authentication.supabase.SupabaseJWTAuthentication",
        # Django SimpleJWT (for admin/internal use)
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        # Session and Basic authentication for fallback
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
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
# JWT Authentication Configuration (for Django SimpleJWT)
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
# CORS Configuration for frontend-backend communication
# =============================================================================
CORS_ALLOW_ALL_ORIGINS = DEBUG  # Allow all origins in development
CORS_ALLOW_CREDENTIALS = True

# Load CORS allowed origins from environment
CORS_ALLOWED_ORIGINS_STR = os.environ.get("CORS_ALLOWED_ORIGINS", "")
if CORS_ALLOWED_ORIGINS_STR:
    CORS_ALLOWED_ORIGINS = []
    for origin in CORS_ALLOWED_ORIGINS_STR.split(","):
        origin = origin.strip()
        # Skip localhost entries in production (they don't work with HTTPS cross-origin)
        if origin in ("localhost", "127.0.0.1") and not DEBUG:
            continue
        if origin:
            CORS_ALLOWED_ORIGINS.append(origin)
else:
    CORS_ALLOWED_ORIGINS = [
        "http://localhost:3000",  # Next.js frontend (development)
        "http://127.0.0.1:3000",
    ]

# In production, add the production domain
if not DEBUG:
    # Only add if not already present from CORS_ALLOWED_ORIGINS
    for origin in ["https://linkedin.lengrowth.com", "https://linkedin-api.lengrowth.com"]:
        if origin not in CORS_ALLOWED_ORIGINS:
            CORS_ALLOWED_ORIGINS.append(origin)

CSRF_TRUSTED_ORIGINS = []
if not DEBUG:
    CSRF_TRUSTED_ORIGINS = [
        "https://linkedin.lengrowth.com",
        "https://linkedin-api.lengrowth.com",
    ]
