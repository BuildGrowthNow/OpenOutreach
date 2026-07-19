# openoutreach/config.py
"""
Pydantic Settings Configuration for OpenOutreach.
Replaces Django settings with environment-based configuration.
"""
from pathlib import Path
from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """OpenOutreach application settings."""

    # =========================================================================
    # Core Application Settings
    # =========================================================================
    SECRET_KEY: str = "openoutreach-local-dev-key-change-in-production"
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
    # Supabase Authentication
    # =========================================================================
    SUPABASE_URL: Optional[str] = None
    SUPABASE_ANON_KEY: Optional[str] = None
    SUPABASE_SERVICE_KEY: Optional[str] = None

    # =========================================================================
    # JWT Configuration
    # =========================================================================
    JWT_SECRET_KEY: Optional[str] = None
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_LIFETIME_MINUTES: int = 60 * 24  # 24 hours
    JWT_REFRESH_TOKEN_LIFETIME_DAYS: int = 7

    # =========================================================================
    # API Server
    # =========================================================================
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8001
    API_WORKERS: int = 1
    API_RELOAD: bool = False

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
    # Finder API (BetterContact)
    # =========================================================================
    FINDER_API_KEY: Optional[str] = None

    # =========================================================================
    # Stripe Configuration
    # =========================================================================
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_PUBLISHABLE_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None

    # =========================================================================
    # Billing Configuration
    # =========================================================================
    TRIAL_DURATION_DAYS: int = 3
    LIFETIME_DEAL_ENABLED: bool = True
    LIFETIME_DEAL_ENDS_AT: Optional[str] = None

    # =========================================================================
    # Email Configuration
    # =========================================================================
    EMAIL_PROVIDER: str = "resend"  # "resend", "ses", or "smtp"
    RESEND_API_KEY: Optional[str] = None
    EMAIL_FROM_ADDRESS: str = "noreply@openoutreach.ai"
    EMAIL_FROM_NAME: str = "OpenOutreach"
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


# Global settings instance
settings = Settings()


# Ensure data directory exists
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.MEDIA_DIR.mkdir(parents=True, exist_ok=True)
