"""
Migration script for Phase 10: Grandfather existing users into Pro plan.

For users created before billing launch:
- Set subscription_status = "active"
- Set plan = "pro"
- Set billing_period = "annual"
- Set current_period_end = 90 days from now (grace period)
- Send welcome email

This allows existing users to use the platform without immediate payment,
while giving them 90 days to accept the new billing terms or choose a plan.
"""

import logging
from datetime import datetime, timedelta, timezone as tz

from openoutreach.mongodb.models_user import User
from openoutreach.mongodb.connection import get_mongodb_collection

logger = logging.getLogger(__name__)


def migrate_existing_users_to_billing(
    dry_run: bool = True,
    grandfathered_plan: str = "pro",
    grace_period_days: int = 90,
) -> dict:
    """
    Migrate existing users to Pro plan with 90-day grace period.

    Args:
        dry_run: If True, only count users and print summary (don't commit)
        grandfathered_plan: Plan to assign to existing users (default: "pro")
        grace_period_days: Days before enforcement kicks in (default: 90)

    Returns:
        dict with migration stats
    """
    users_collection = get_mongodb_collection("users")
    if users_collection is None:
        raise RuntimeError("Users collection not available")

    # Find users with no subscription (subscription_status = "none" or missing)
    # These are pre-billing users
    query = {
        "$or": [
            {"subscription_status": "none"},
            {"subscription_status": {"$exists": False}},
            {"plan": {"$exists": False}},
        ]
    }

    count = 0
    updated_count = 0
    errors = []

    try:
        users = list(users_collection.find(query))
        count = len(users)
        logger.info(f"Found {count} users eligible for migration")

        if dry_run:
            logger.info(f"[DRY RUN] Would migrate {count} users to {grandfathered_plan} plan")
            for user_doc in users[:5]:  # Show first 5
                logger.info(f"  - {user_doc.get('email')}")
            if count > 5:
                logger.info(f"  ... and {count - 5} more")
            return {
                "status": "dry_run",
                "users_found": count,
                "users_updated": 0,
                "errors": errors,
            }

        # Perform migration
        grace_period_end = datetime.now(tz.utc) + timedelta(days=grace_period_days)

        for user_doc in users:
            try:
                user = User.from_dict(user_doc)

                # Skip if already has active subscription
                if user.subscription_status in ("active", "trialing", "past_due"):
                    logger.info(f"Skipping {user.email}: already has subscription")
                    continue

                # Set plan fields
                user.plan = grandfathered_plan
                user.subscription_status = "active"
                user.billing_period = "annual"
                user.current_period_end = grace_period_end

                # Set account limits based on plan
                if grandfathered_plan == "pro":
                    user.linkedin_account_limit = 1
                    user.campaign_limit = None  # Unlimited
                elif grandfathered_plan == "business":
                    user.linkedin_account_limit = 3
                    user.campaign_limit = None
                elif grandfathered_plan == "agency":
                    user.linkedin_account_limit = 10
                    user.campaign_limit = None

                user.save()
                updated_count += 1
                logger.info(f"Migrated {user.email} to {grandfathered_plan}")

            except Exception as e:
                error_msg = f"Failed to migrate {user_doc.get('email')}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

        logger.info(
            f"Migration complete: {updated_count} users updated, "
            f"{len(errors)} errors"
        )

        return {
            "status": "completed",
            "users_found": count,
            "users_updated": updated_count,
            "errors": errors,
        }

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise


def mark_migration_complete():
    """
    Mark that billing migration has been run.

    Stores a flag in site_config so admins know the migration was executed.
    """
    try:
        site_config_coll = get_mongodb_collection("site_config")
        if site_config_coll is not None:
            site_config_coll.update_one(
                {},
                {
                    "$set": {
                        "billing_migration_completed": True,
                        "billing_migration_completed_at": datetime.now(tz.utc),
                    }
                },
                upsert=True,
            )
            logger.info("Migration marked as complete in SiteConfig")
    except Exception as e:
        logger.error(f"Failed to mark migration complete: {e}")


if __name__ == "__main__":
    import sys

    dry_run = "--dry-run" in sys.argv or "--dry_run" in sys.argv
    result = migrate_existing_users_to_billing(dry_run=dry_run)

    print("\n=== Migration Result ===")
    print(f"Status: {result['status']}")
    print(f"Users found: {result['users_found']}")
    print(f"Users updated: {result['users_updated']}")
    if result["errors"]:
        print(f"Errors ({len(result['errors'])}):")
        for err in result["errors"]:
            print(f"  - {err}")

    if not dry_run and result["users_updated"] > 0:
        mark_migration_complete()
