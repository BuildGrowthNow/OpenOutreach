# openoutreach/config.py
"""
Pydantic Settings Configuration for OpenOutreach.
Replaces Django settings with environment-based configuration.
"""
from pathlib import Path
import base64
from typing import Optional, List
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """OpenOutreach application settings."""

    # =========================================================================
    # Core Application Settings
    # =========================================================================
    SECRET_KEY: str
    DEBUG: bool = False
    ALLOWED_HOSTS: str = "localhost,127.0.0.1"
    LOG_LEVEL: str = "INFO"

    # =========================================================================
    # Database - MongoDB (Primary)
    # =========================================================================
    MONGODB_URI: str = ""
    MONGODB_NAME: str = "openoutreach"
    MONGODB_ENABLED: bool = True

    # =========================================================================
    # JWT Configuration
    # =========================================================================
    JWT_SECRET_KEY: Optional[str] = None
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_LIFETIME_MINUTES: int = 60 * 24  # 24 hours
    JWT_REFRESH_TOKEN_LIFETIME_DAYS: int = 30

    # Daemon v2 signing keys are backend-only PEM values supplied by the
    # deployment secret manager. There is intentionally no desktop fallback.
    DAEMON_JWT_PRIVATE_KEY: Optional[str] = None
    DAEMON_JWT_PUBLIC_KEY: Optional[str] = None
    # Single-line deployment-secret variants avoid multiline dotenv parsing
    # ambiguity. They are decoded only in memory and never logged or returned.
    DAEMON_JWT_PRIVATE_KEY_B64: Optional[str] = None
    DAEMON_JWT_PUBLIC_KEY_B64: Optional[str] = None
    DAEMON_JWT_KEY_ID: Optional[str] = None
    # Security controls default closed for legacy/bootstrap behavior and
    # require an explicit deployment decision for task execution.
    DAEMON_BOOTSTRAP_ENABLED: bool = False
    DAEMON_MIN_SECURE_VERSION: str = "2.1.0"
    DAEMON_TASK_CLAIM_ENABLED: bool = False
    DAEMON_V2_LINKEDIN_ENABLED: bool = True
    DAEMON_V2_WHATSAPP_ENABLED: bool = False
    DAEMON_V2_EMAIL_ENABLED: bool = False

    @model_validator(mode="after")
    def load_daemon_key_variants(self):
        for plain_name, encoded_name in (
            ("DAEMON_JWT_PRIVATE_KEY", "DAEMON_JWT_PRIVATE_KEY_B64"),
            ("DAEMON_JWT_PUBLIC_KEY", "DAEMON_JWT_PUBLIC_KEY_B64"),
        ):
            if not getattr(self, plain_name) and getattr(self, encoded_name):
                try:
                    value = base64.b64decode(getattr(self, encoded_name), validate=True)
                    setattr(self, plain_name, value.decode("ascii"))
                except (ValueError, UnicodeDecodeError):
                    raise ValueError(f"Invalid {encoded_name}")
        return self

    # =========================================================================
    # API Server
    # =========================================================================
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8001
    API_WORKERS: int = 1
    API_RELOAD: bool = False
    APP_URL: str = "http://localhost:3000"

    # =========================================================================
    # CORS Configuration
    # =========================================================================
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # =========================================================================
    # Encryption
    # =========================================================================
    COOKIE_ENCRYPTION_KEY: Optional[str] = None

    # =========================================================================
    # LLM Configuration
    # =========================================================================
    LLM_PROVIDER: str = "openai"
    LLM_API_KEY: str = ""
    LLM_API_BASE: Optional[str] = None
    AI_MODEL: str = "gpt-4o-mini"
    AI_MODEL_FALLBACKS: str = ""
    CLOUDFLARE_ACCOUNT_ID: str = ""
    CLOUDFLARE_API_TOKEN: str = ""

    # =========================================================================
    # LinkedIn Configuration
    # =========================================================================
    LINKEDIN_USERNAME: Optional[str] = None
    LINKEDIN_PASSWORD: Optional[str] = None

    # =========================================================================
    # Browser/Playwright Configuration
    # =========================================================================
    BROWSER_HEADLESS: bool = True
    ENABLE_VNC: bool = False

    # =========================================================================
    # Campaign Configuration
    # =========================================================================
    CAMPAIGN_NAME: str = "LinkedIn Outreach"

    # =========================================================================
    # Redis (Optional - for WebSocket scaling)
    # =========================================================================
    REDIS_URL: Optional[str] = None


    # =========================================================================
    # Stripe Configuration
    # =========================================================================
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_PUBLISHABLE_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None

    # =========================================================================
    # Billing Configuration
    # =========================================================================
    TRIAL_DURATION_DAYS: int = 7
    LIFETIME_DEAL_ENABLED: bool = True
    LIFETIME_DEAL_ENDS_AT: Optional[str] = None

    # =========================================================================
    # Email Configuration
    # =========================================================================
    EMAIL_PROVIDER: str = "resend"  # "resend", "ses", or "smtp"
    RESEND_API_KEY: Optional[str] = None
    EMAIL_FROM_ADDRESS: str = "noreply@lengrowth.com"
    EMAIL_FROM_NAME: str = "Lengrowth Outreach"
    SUPPORT_EMAIL: str = "support@lengrowth.com"  # Support email for user-facing messages
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None

    # =========================================================================
    # Environment Detection
    # =========================================================================
    DOCKER_ENV: bool = False

    # =========================================================================
    # Paths
    # =========================================================================
    @property
    def ROOT_DIR(self) -> Path:
        """Project root directory."""
        return Path(__file__).resolve().parent.parent

    @property
    def DATA_DIR(self) -> Path:
        """Data directory for persistent storage."""
        return self.ROOT_DIR / "data"

    @property
    def MEDIA_DIR(self) -> Path:
        """Media directory for uploaded files."""
        return self.ROOT_DIR / "openoutreach" / "media"

    @property
    def STATIC_DIR(self) -> Path:
        """Static files directory."""
        return self.ROOT_DIR / "staticfiles"

    @property
    def FASTEMBED_CACHE_DIR(self) -> Path:
        """FastEmbed model cache directory."""
        cache_dir = self.ROOT_DIR / ".cache" / "fastembed"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    # =========================================================================
    # Computed Properties
    # =========================================================================
    @property
    def allowed_hosts_list(self) -> List[str]:
        """Parse ALLOWED_HOSTS into a list."""
        hosts = []
        for host in self.ALLOWED_HOSTS.split(","):
            host = host.strip()
            # Remove protocol prefix if present
            if host.startswith("https://"):
                host = host[8:]
            elif host.startswith("http://"):
                host = host[7:]
            if host:
                hosts.append(host)
        return hosts or ["localhost", "127.0.0.1"]

    @property
    def cors_allowed_origins_list(self) -> List[str]:
        """Parse CORS_ALLOWED_ORIGINS into a list."""
        origins = []
        for origin in self.CORS_ALLOWED_ORIGINS.split(","):
            origin = origin.strip()
            if origin:
                origins.append(origin)
        return origins or ["http://localhost:3000", "http://127.0.0.1:3000"]

    @property
    def jwt_secret(self) -> str:
        """Get JWT secret key (fallback to SECRET_KEY)."""
        return self.JWT_SECRET_KEY or self.SECRET_KEY

    @property
    def encryption_key(self) -> str:
        """Get encryption key (fallback to SECRET_KEY)."""
        return self.COOKIE_ENCRYPTION_KEY or self.SECRET_KEY

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# Global settings instance - SECRET_KEY loaded from env/.env at runtime
settings = Settings()  # type: ignore[call-arg]


# Ensure data directory exists
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.MEDIA_DIR.mkdir(parents=True, exist_ok=True)
