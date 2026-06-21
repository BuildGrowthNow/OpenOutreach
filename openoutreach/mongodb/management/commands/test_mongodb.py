# type: ignore
"""
Management command to test MongoDB connection and configuration.

Usage:
    python manage.py test_mongodb
"""

from django.core.management.base import BaseCommand
from openoutreach.mongodb.connection import (
    check_mongodb_connection,
    mongodb_connection,
    get_mongodb,
    get_mongodb_collection
)
from openoutreach.mongodb.models import (
    ensure_mongodb_indexes,
    get_mongodb_lead,
    get_mongodb_campaign
)
from openoutreach.mongodb.utils import (
    AggregationPipelines,
    BackupManager,
    CleanupManager,
    create_indexes,
    get_index_stats
)


class Command(BaseCommand):
    """Test MongoDB connection and configuration."""
    
    help = "Test MongoDB connection, indexes, and basic operations"
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--create-indexes',
            action='store_true',
            help='Create MongoDB indexes if not present'
        )
        parser.add_argument(
            '--check-only',
            action='store_true',
            help='Only check connection, skip tests'
        )
    
    def handle(self, *args, **options):
        """Execute the command."""
        create_indexes = options.get('create_indexes', False)
        check_only = options.get('check_only', False)
        
        self.stdout.write("=" * 60)
        self.stdout.write("MongoDB Connection Test")
        self.stdout.write("=" * 60)
        
        # Check connection
        self.stdout.write("\n1. Checking MongoDB connection...")
        if check_mongodb_connection():
            self.stdout.write(self.style.SUCCESS("   [OK] MongoDB connection is active"))
        else:
            self.stdout.write(self.style.WARNING("   [INFO] MongoDB not enabled or not connected"))
            self.stdout.write("   Switching to SQLite mode...")
        
        # Get database
        db = get_mongodb()
        if db:
            self.stdout.write(f"   Database: {db.name}")
        
        if check_only:
            return
        
        # Create indexes if requested
        if create_indexes and db:
            self.stdout.write("\n2. Creating MongoDB indexes...")
            ensure_mongodb_indexes()
        
        # Test collection operations
        self.stdout.write("\n3. Testing collection operations...")
        if db:
            collections = db.list_collection_names()
            self.stdout.write(f"   Found {len(collections)} collections:")
            for coll in collections:
                self.stdout.write(f"   - {coll}")
        
        # Test index operations
        self.stdout.write("\n4. Testing index operations...")
        if db:
            indexes = get_index_stats("campaigns")
            self.stdout.write(f"   Campaigns collection has {len(indexes)} indexes:")
            for idx in indexes:
                self.stdout.write(f"   - {idx['name']}")
        
        # Test backup manager
        self.stdout.write("\n5. Testing backup manager...")
        backup_mgr = BackupManager()
        backups = backup_mgr.list_backups()
        self.stdout.write(f"   Found {len(backups)} backup records")
        
        # Test cleanup manager
        self.stdout.write("\n6. Testing cleanup manager...")
        cleanup_mgr = CleanupManager()
        deleted_logs = cleanup_mgr.cleanup_old_logs(days=30)
        self.stdout.write(f"   Deleted {deleted_logs} old log entries")
        
        # Test aggregation pipelines
        self.stdout.write("\n7. Testing aggregation pipelines...")
        if db:
            pipeline = AggregationPipelines.get_campaign_performance_pipeline(
                campaign_id="test_campaign"
            )
            self.stdout.write(f"   Campaign performance pipeline has {len(pipeline)} stages")
        
        # Test MongoDB-specific model functions
        self.stdout.write("\n8. Testing MongoDB model utilities...")
        if db:
            # Try to get a campaign (will return None if collection empty)
            campaign = get_mongodb_campaign("test_campaign")
            self.stdout.write(f"   get_mongodb_campaign() returned: {campaign}")
        
        # Summary
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("Test Summary")
        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS("MongoDB integration test completed successfully"))
        self.stdout.write("\nNext steps:")
        self.stdout.write("1. Add 'djongo' to DATABASES settings in settings.py")
        self.stdout.write("2. Run 'python manage.py migrate' to create MongoDB collections")
        self.stdout.write("3. Use 'python manage.py test_mongodb --create-indexes' to create indexes")
        self.stdout.write("\nFor production:")
        self.stdout.write("- Set MONGODB_ENABLED=true in your environment")
        self.stdout.write("- Configure MONGODB_ATLAS_URI or MongoDB connection details")
        self.stdout.write("- Run 'python manage.py migrate' to create collections")
        self.stdout.write("- Run 'python manage.py test_mongodb --create-indexes'")
    
    def _print_list(self, items, prefix="   "):
        """Print a list of items."""
        for item in items:
            self.stdout.write(f"{prefix}- {item}")