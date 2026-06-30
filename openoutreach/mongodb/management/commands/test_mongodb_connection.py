"""
Management command to test MongoDB connection and configuration.

Usage:
    python manage.py test_mongodb_connection
"""

import sys
from django.core.management.base import BaseCommand
from django.conf import settings
from openoutreach.mongodb.connection import (
    check_mongodb_connection,
    mongodb_connection,
    get_mongodb,
    get_mongodb_collection,
)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pymongo.database import Database
from openoutreach.mongodb.models import (
    Lead,
    Campaign,
    Deal,
    ensure_mongodb_indexes,
)


class Command(BaseCommand):
    """Test MongoDB connection and configuration."""

    help = "Test MongoDB connection, create collections, and verify data operations"

    def add_arguments(self, parser):
        parser.add_argument(
            "--create-indexes",
            action="store_true",
            help="Create MongoDB indexes if not present",
        )
        parser.add_argument(
            "--create-test-data",
            action="store_true",
            help="Create test records in MongoDB",
        )
        parser.add_argument(
            "--verify-data",
            action="store_true",
            help="Verify test data exists in MongoDB",
        )
        parser.add_argument(
            "--drop-test-data",
            action="store_true",
            help="Drop test collections (for cleanup)",
        )

    def handle(self, *args, **options):
        """Execute the command."""
        create_indexes = options.get("create_indexes", False)
        create_test_data = options.get("create_test_data", False)
        verify_data = options.get("verify_data", False)
        drop_test_data = options.get("drop_test_data", False)

        self.stdout.write("=" * 60)
        self.stdout.write("MongoDB Connection Test")
        self.stdout.write("=" * 60)

        # Check if MongoDB is enabled
        if not settings.MONGODB_ENABLED:
            self.stdout.write(
                self.style.WARNING(
                    "\n[INFO] MongoDB is not enabled (MONGODB_ENABLED=false)"
                )
            )
            self.stdout.write(
                "Set MONGODB_ENABLED=true in your environment to use MongoDB."
            )
            return

        # Check connection
        self.stdout.write("\n1. Checking MongoDB connection...")
        if check_mongodb_connection():
            self.stdout.write(
                self.style.SUCCESS("   [OK] MongoDB connection is active")
            )
        else:
            self.stdout.write(self.style.WARNING("   [FAIL] MongoDB not connected"))
            return

        # Get database info
        db = get_mongodb()
        if db is not None:
            self.stdout.write(f"   Database: {db.name}")
            self.stdout.write(f"   Host: {settings.MONGODB_HOST}")

        # Create indexes if requested
        if create_indexes:
            self.stdout.write("\n2. Creating MongoDB indexes...")
            ensure_mongodb_indexes()

        # Drop test data if requested
        if drop_test_data:
            self.stdout.write("\n2. Dropping test collections...")
            self._drop_test_collections()

        # Create test data if requested
        if create_test_data:
            self.stdout.write("\n2. Creating test data...")
            self._create_test_data()

        # Verify data if requested
        if verify_data:
            self.stdout.write("\n3. Verifying data in MongoDB...")
            self._verify_data()

        # Show collections
        self.stdout.write("\n4. MongoDB Collections:")
        if db is not None:
            collections = db.list_collection_names()
            if collections:
                for coll in collections:
                    # Get document count
                    try:
                        count = db[coll].count_documents({})
                        self.stdout.write(f"   - {coll}: {count} documents")
                    except Exception as e:
                        self.stdout.write(f"   - {coll}: (error counting: {e})")
            else:
                self.stdout.write("   (No collections found)")

        # Show model counts using pymongo
        self.stdout.write("\n5. Model counts (via PyMongo):")
        try:
            self.stdout.write(f"   Leads: {Lead.objects.count()}")  # type: ignore[union-attr]
            self.stdout.write(f"   Campaigns: {Campaign.objects.count()}")  # type: ignore[union-attr]
            self.stdout.write(f"   Deals: {Deal.objects.count()}")  # type: ignore[union-attr]
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"   Error counting models: {e}"))

        # Summary
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("MongoDB connection test completed!"))
        self.stdout.write("\nNext steps:")
        self.stdout.write("1. Run 'python manage.py migrate' to create collections")
        self.stdout.write(
            "2. Use 'python manage.py test_mongodb_connection --create-test-data'"
        )
        self.stdout.write("3. Check MongoDB Compass to verify data")
        self.stdout.write("\nTo enable MongoDB in production:")
        self.stdout.write("- Set MONGODB_ENABLED=true in your .env file")
        self.stdout.write(
            "- Set MONGODB_ATLAS_URI=mongodb+srv://user:pass@cluster.mongodb.net/dbname"
        )

    def _create_test_data(self):
        """Create test records in MongoDB."""
        try:
            # Create a test lead
            lead, created = Lead.objects.get_or_create(  # type: ignore[union-attr]
                linkedin_url="https://linkedin.com/in/testuser",
                defaults={
                    "public_identifier": "testuser",
                    "contact_info": {"email": "test@example.com"},
                },
            )
            self.stdout.write(
                f"   Lead: {'Created' if created else 'Already exists'} (ID: {lead.pk})"
            )

            # Create a test campaign
            campaign, created = Campaign.objects.get_or_create(  # type: ignore[union-attr]
                name="Test Campaign",
                defaults={
                    "description": "Test campaign for MongoDB verification",
                    "velocity": 10,
                },
            )
            self.stdout.write(
                f"   Campaign: {'Created' if created else 'Already exists'} (ID: {campaign.pk})"
            )

            # Create a test deal
            deal, created = Deal.objects.get_or_create(  # type: ignore[union-attr]
                lead_id=str(lead.pk),
                campaign_id=str(campaign.pk),
                defaults={
                    "state": Deal.DealState.QUALIFIED,
                    "connect_attempts": 0,
                },
            )
            self.stdout.write(
                f"   Deal: {'Created' if created else 'Already exists'} (ID: {deal.pk}, State: {deal.state})"
            )

            self.stdout.write(self.style.SUCCESS("   Test data created successfully!"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   Error creating test data: {e}"))
            import traceback

            traceback.print_exc()

    def _verify_data(self):
        """Verify test data exists in MongoDB."""
        try:
            # Check if test records exist
            test_lead = Lead.objects.filter(public_identifier="testuser").first()  # type: ignore[union-attr]
            if test_lead:
                self.stdout.write(
                    self.style.SUCCESS(f"   Found test lead: {test_lead}")
                )
            else:
                self.stdout.write(self.style.WARNING("   Test lead not found"))

            test_campaign = Campaign.objects.filter(name="Test Campaign").first()  # type: ignore[union-attr]
            if test_campaign:
                self.stdout.write(
                    self.style.SUCCESS(f"   Found test campaign: {test_campaign}")
                )
            else:
                self.stdout.write(self.style.WARNING("   Test campaign not found"))

            test_deal = Deal.objects.filter(  # type: ignore[union-attr]
                lead_id__contains="testuser"
            ).first()
            if test_deal:
                self.stdout.write(
                    self.style.SUCCESS(f"   Found test deal: {test_deal}")
                )
            else:
                self.stdout.write(self.style.WARNING("   Test deal not found"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   Error verifying data: {e}"))

    def _drop_test_collections(self):
        """Drop test collections from MongoDB."""
        try:
            # Get database
            db = get_mongodb()
            if db is None:
                self.stdout.write(self.style.WARNING("   No database connection"))
                return

            # List collections to drop
            collections_to_drop = [
                "leads",
                "campaigns",
                "deals",
                "messages",
                "notes",
                "lead_personas",
            ]

            for coll_name in collections_to_drop:
                try:
                    if coll_name in db.list_collection_names():
                        db[coll_name].drop()
                        self.stdout.write(f"   Dropped collection: {coll_name}")
                    else:
                        self.stdout.write(f"   Collection not found: {coll_name}")
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f"   Error dropping '{coll_name}': {e}")
                    )

            self.stdout.write(self.style.SUCCESS("   Test collections dropped!"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   Error dropping collections: {e}"))
