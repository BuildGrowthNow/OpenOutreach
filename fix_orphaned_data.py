#!/usr/bin/env python
"""
Script to fix orphaned foreign key data in the database.
This deletes LinkedIn profiles that have user_id references to non-existent users.
"""
import os
import sys
import django

# Add the app directory to Python path
sys.path.insert(0, '/app')

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'openoutreach.settings')
django.setup()

from django.contrib.auth.models import User
from openoutreach.linkedin.models import LinkedInProfile
from django.db import transaction

def fix_orphaned_data():
    print("Starting data fix...")
    
    # Show current state
    all_users = list(User.objects.values_list('id', flat=True))
    all_profiles = list(LinkedInProfile.objects.values_list('id', 'user_id'))
    
    print(f"Users in database: {all_users}")
    print(f"LinkedIn profiles: {all_profiles}")
    
    # Find orphaned profiles (profiles with user_id pointing to non-existent users)
    orphaned_profiles = LinkedInProfile.objects.filter(user_id__isnull=False).exclude(user_id__in=User.objects.values_list('id', flat=True))
    
    print(f"\nOrphaned profiles to delete: {list(orphaned_profiles.values_list('id', 'user_id'))}")
    
    if orphaned_profiles.exists():
        with transaction.atomic():
            deleted_count, _ = orphaned_profiles.delete()
            print(f"\nDeleted {deleted_count} orphaned profile(s)")
    else:
        print("\nNo orphaned profiles found")
    
    # Verify after fix
    remaining_orphaned = LinkedInProfile.objects.filter(user_id__isnull=False).exclude(user_id__in=User.objects.values_list('id', flat=True))
    print(f"\nRemaining orphaned profiles after fix: {remaining_orphaned.count()}")
    
    print("\nFix complete!")

if __name__ == '__main__':
    fix_orphaned_data()