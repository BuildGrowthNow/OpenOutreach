"""
Configuration loading and management for billing.
"""
import logging
import time
from datetime import datetime, timezone as tz

from openoutreach.billing.models import SiteConfig
from openoutreach.config import settings

logger = logging.getLogger(__name__)

_site_config_cache: SiteConfig | None = None
_site_config_cache_time: float = 0.0
_CACHE_TTL_SECONDS = 30


def get_site_config() -> SiteConfig:
    """Get global site configuration, cached with 30s TTL."""
    global _site_config_cache, _site_config_cache_time

    now = time.monotonic()
    if _site_config_cache is not None and (now - _site_config_cache_time) < _CACHE_TTL_SECONDS:
        return _site_config_cache

    config = SiteConfig.load()
    _site_config_cache = config
    _site_config_cache_time = now
    return config


def invalidate_config_cache() -> None:
    """Invalidate the cached config."""
    global _site_config_cache, _site_config_cache_time
    _site_config_cache = None
    _site_config_cache_time = 0.0


def get_trial_duration_days() -> int:
    """Get trial duration in days."""
    config = get_site_config()
    return config.trial_duration_days


def is_lifetime_deal_active() -> bool:
    """Check if lifetime deal is still active (enabled, within window, and under buyer cap)."""
    config = get_site_config()

    if not config.lifetime_deal_enabled:
        return False

    if config.lifetime_deal_buyer_count >= config.lifetime_deal_max_buyers:
        return False

    if config.lifetime_deal_ends_at is None:
        return True

    if isinstance(config.lifetime_deal_ends_at, str):
        ends_at = datetime.fromisoformat(config.lifetime_deal_ends_at)
    else:
        ends_at = config.lifetime_deal_ends_at

    if ends_at.tzinfo is None:
        ends_at = ends_at.replace(tzinfo=tz.utc)
    return datetime.now(tz.utc) < ends_at


def increment_lifetime_buyer_count() -> int:
    """Atomically increment lifetime deal buyer count. Returns new count."""
    collection_name = "site_config"
    from openoutreach.mongodb.connection import get_mongodb_collection
    collection = get_mongodb_collection(collection_name)
    if collection is None:
        logger.error("MongoDB collection 'site_config' not available for buyer count increment")
        return 0

    result = collection.find_one_and_update(
        {"_id": "site_config"},
        {"$inc": {"lifetime_deal_buyer_count": 1}},
        return_document=True,
        upsert=False,
    )
    invalidate_config_cache()
    count = result.get("lifetime_deal_buyer_count", 0) if result else 0
    logger.info(f"Lifetime deal buyer count incremented to {count}")
    return count


def load_from_env() -> None:
    """Load billing config from environment variables."""
    if settings.TRIAL_DURATION_DAYS is not None:
        config = get_site_config()
        config.trial_duration_days = settings.TRIAL_DURATION_DAYS
        config.save()
        invalidate_config_cache()
        logger.info(f"Updated trial duration: {settings.TRIAL_DURATION_DAYS} days")

    if settings.LIFETIME_DEAL_ENABLED is not None:
        config = get_site_config()
        config.lifetime_deal_enabled = settings.LIFETIME_DEAL_ENABLED
        config.save()
        invalidate_config_cache()
        logger.info(f"Updated lifetime deal enabled: {settings.LIFETIME_DEAL_ENABLED}")

    if settings.LIFETIME_DEAL_ENDS_AT:
        config = get_site_config()
        config.lifetime_deal_ends_at = datetime.fromisoformat(settings.LIFETIME_DEAL_ENDS_AT)
        config.save()
        invalidate_config_cache()
        logger.info(f"Updated lifetime deal end date: {settings.LIFETIME_DEAL_ENDS_AT}")
