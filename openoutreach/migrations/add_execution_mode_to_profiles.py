"""
Migration: Add execution_mode field to existing LinkedInProfile documents

This migration adds the execution_mode, last_heartbeat, and daemon_status fields
to all existing LinkedInProfile documents in MongoDB. Existing profiles default
to 'desktop' mode.

Run with: python -m openoutreach.migrations.add_execution_mode_to_profiles
"""
import logging

from openoutreach.mongodb.connection import initialize_mongodb_connection, get_mongodb_collection

logger = logging.getLogger(__name__)


def migrate_execution_mode():
    """Add execution_mode fields to existing LinkedInProfile documents."""

    logger.info("Starting execution_mode migration...")

    # Initialize MongoDB connection
    if not initialize_mongodb_connection():
        logger.error("Failed to connect to MongoDB")
        return False

    collection = get_mongodb_collection("linkedin_profiles")
    if collection is None:
        logger.error("Could not access linkedin_profiles collection")
        return False

    # Find all profiles without execution_mode
    profiles_to_update = collection.count_documents({
        "execution_mode": {"$exists": False}
    })

    if profiles_to_update == 0:
        logger.info("No profiles need migration. All profiles already have execution_mode.")
        return True

    logger.info(f"Found {profiles_to_update} profiles to migrate")

    # Update all profiles without execution_mode
    result = collection.update_many(
        {"execution_mode": {"$exists": False}},
        {
            "$set": {
                "execution_mode": "desktop",  # Default to desktop for existing profiles
                "last_heartbeat": None,
                "daemon_status": "unknown",
            }
        }
    )

    logger.info(f"Migration complete: updated {result.modified_count} profiles")

    # Verify migration
    remaining = collection.count_documents({
        "execution_mode": {"$exists": False}
    })

    if remaining > 0:
        logger.warning(f"Migration incomplete: {remaining} profiles still missing execution_mode")
        return False

    logger.info("✅ All profiles now have execution_mode field")
    return True


if __name__ == "__main__":
    from openoutreach.core.logging import RedactingFormatter

    handler = logging.StreamHandler()
    handler.setFormatter(RedactingFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])

    success = migrate_execution_mode()
    exit(0 if success else 1)
