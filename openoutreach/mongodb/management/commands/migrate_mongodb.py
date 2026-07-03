# type: ignore
"""
Management command to migrate data from SQLite to MongoDB.

Usage:
    python manage.py migrate_mongodb
    python manage.py migrate_mongodb --models core.Campaign crm.Lead
    python manage.py migrate_mongodb --verify
    python manage.py migrate_mongodb --rollback
"""

from django.core.management.base import BaseCommand
from openoutreach.mongodb.migrations import (
    run_migration,
    verify_migration,
    rollback_migration,
)
import json


class Command(BaseCommand):
    """Migrate data from SQLite to MongoDB."""

    help = "Migrate data from SQLite to MongoDB"

    def add_arguments(self, parser):
        parser.add_argument(
            "--models",
            nargs="+",
            help="Specific models to migrate (e.g., core.Campaign crm.Lead)",
        )
        parser.add_argument(
            "--verify",
            action="store_true",
            help="Verify migration results instead of running migration",
        )
        parser.add_argument(
            "--rollback",
            action="store_true",
            help="Rollback migration for specified models",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Show detailed output",
        )

    def handle(self, *args, **options):
        """Execute the command."""
        models = options.get("models")
        verify = options.get("verify", False)
        rollback = options.get("rollback", False)
        verbose = options.get("verbose", False)

        self.stdout.write("=" * 60)
        self.stdout.write("SQLite to MongoDB Migration")
        self.stdout.write("=" * 60)

        if verify:
            self.stdout.write("\nVerifying migration results...")
            result = verify_migration()
            self._print_verification_results(result, verbose)
        elif rollback:
            self.stdout.write("\nRolling back migration...")
            result = rollback_migration(models_to_rollback=models)
            self._print_rollback_results(result, verbose)
        else:
            self.stdout.write("\nStarting migration...")
            result = run_migration() if not models else run_migration(models_to_migrate=models)
            self._print_migration_results(result, verbose)

    def _print_migration_results(self, result, verbose=False):
        """Print migration results."""
        self.stdout.write(f"\nStarted: {result.get('started_at', 'N/A')}")
        self.stdout.write(f"Completed: {result.get('completed_at', 'N/A')}")
        
        if 'error' in result:
            self.stdout.write(self.style.ERROR(f"Migration failed: {result['error']}"))
            return

        models_migrated = result.get('models_migrated', [])
        total_migrated = result.get('total_migrated', 0)
        total_failed = result.get('total_failed', 0)

        self.stdout.write(f"\nTotal Records Migrated: {total_migrated}")
        self.stdout.write(f"Total Records Failed: {total_failed}")

        if verbose and models_migrated:
            self.stdout.write("\nModel Details:")
            for model_result in models_migrated:
                model_name = model_result.get('model', 'Unknown')
                migrated = model_result.get('migrated', 0)
                failed = model_result.get('failed', 0)
                total = model_result.get('total', 0)
                
                status = "SUCCESS" if failed == 0 else "PARTIAL" if migrated > 0 else "FAILED"
                status_style = self.style.SUCCESS if failed == 0 else self.style.WARNING if migrated > 0 else self.style.ERROR
                
                self.stdout.write(f"  {model_name}:")
                self.stdout.write(f"    Status: {status_style(status)}")
                self.stdout.write(f"    Migrated: {migrated}")
                self.stdout.write(f"    Failed: {failed}")
                self.stdout.write(f"    Total: {total}")

        if total_failed == 0:
            self.stdout.write(self.style.SUCCESS("\nMigration completed successfully!"))
        else:
            self.stdout.write(self.style.WARNING(f"\nMigration completed with {total_failed} failures."))

    def _print_verification_results(self, result, verbose=False):
        """Print verification results."""
        models = result.get('models', [])
        all_match = result.get('all_match', False)

        if verbose and models:
            self.stdout.write("\nVerification Results:")
            for model_result in models:
                model_name = model_result.get('model', 'Unknown')
                source_count = model_result.get('source_count', 0)
                target_count = model_result.get('target_count', 0)
                match = model_result.get('match', False)
                
                status = "MATCH" if match else "MISMATCH"
                status_style = self.style.SUCCESS if match else self.style.ERROR
                
                self.stdout.write(f"  {model_name}:")
                self.stdout.write(f"    Status: {status_style(status)}")
                self.stdout.write(f"    Source (SQLite): {source_count}")
                self.stdout.write(f"    Target (MongoDB): {target_count}")

        if all_match:
            self.stdout.write(self.style.SUCCESS("\nAll verifications passed! Data is consistent."))
        else:
            self.stdout.write(self.style.ERROR("\nVerification failed! Data inconsistency detected."))

    def _print_rollback_results(self, result, verbose=False):
        """Print rollback results."""
        started_at = result.get('started_at', 'N/A')
        completed_at = result.get('completed_at', 'N/A')
        results = result.get('results', [])

        self.stdout.write(f"\nStarted: {started_at}")
        self.stdout.write(f"Completed: {completed_at}")

        if verbose and results:
            self.stdout.write("\nRollback Results:")
            for rollback_result in results:
                model_name = rollback_result.get('model', 'Unknown')
                success = rollback_result.get('success', False)
                
                status = "SUCCESS" if success else "FAILED"
                status_style = self.style.SUCCESS if success else self.style.ERROR
                
                self.stdout.write(f"  {model_name}: {status_style(status)}")

        success_count = sum(1 for r in results if r.get('success', False))
        total_count = len(results)

        if success_count == total_count:
            self.stdout.write(self.style.SUCCESS(f"\nRollback completed successfully for all {total_count} models!"))
        else:
            self.stdout.write(self.style.WARNING(f"\nRollback completed for {success_count}/{total_count} models."))