from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class MongoDBConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "openoutreach.mongodb"

    def ready(self):
        """Initialize MongoDB connection and ensure indexes on startup."""
        try:
            from .connection import check_mongodb_connection, get_mongodb
            from .models import ensure_mongodb_indexes
            
            if check_mongodb_connection():
                db = get_mongodb()
                logger.info(f"MongoDB connected: {db.name if db else 'unknown'}")
                
                # Ensure indexes exist
                ensure_mongodb_indexes()
                
                logger.info("MongoDB initialization completed successfully")
            else:
                logger.info("MongoDB not enabled or not available")
        except Exception as e:
            logger.error(f"MongoDB initialization failed: {e}")
