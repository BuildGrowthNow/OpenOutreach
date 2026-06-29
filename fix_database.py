#!/usr/bin/env python
"""
Script to fix orphaned foreign key data directly in SQLite database.
This deletes LinkedIn profiles that have user_id references to non-existent users.
"""
import sqlite3

DB_PATH = '/app/data/db.sqlite3'

def fix_database():
    print(f"Opening database at {DB_PATH}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # First, let's see what users exist
    cursor.execute("SELECT id FROM auth_user")
    users = cursor.fetchall()
    user_ids = [u[0] for u in users]
    print(f"Users in database: {user_ids}")
    
    # Now check linkedin_linkedinprofile table for orphaned records
    cursor.execute("SELECT id, user_id FROM linkedin_linkedinprofile")
    profiles = cursor.fetchall()
    print(f"LinkedIn profiles: {profiles}")
    
    # Find orphaned profiles (profiles with user_id pointing to non-existent users)
    orphaned = [(id, user_id) for id, user_id in profiles if user_id not in user_ids]
    print(f"\nOrphaned profiles to delete: {orphaned}")
    
    if orphaned:
        # Delete orphaned profiles
        for id, user_id in orphaned:
            cursor.execute("DELETE FROM linkedin_linkedinprofile WHERE id = ?", (id,))
        conn.commit()
        print(f"\nDeleted {len(orphaned)} orphaned profile(s)")
    else:
        print("\nNo orphaned profiles found")
    
    # Verify after fix
    cursor.execute("SELECT id, user_id FROM linkedin_linkedinprofile")
    remaining_profiles = cursor.fetchall()
    
    orphaned_after = [(id, user_id) for id, user_id in remaining_profiles if user_id not in user_ids]
    print(f"\nRemaining orphaned profiles after fix: {len(orphaned_after)}")
    
    conn.close()
    print("\nFix complete!")

if __name__ == '__main__':
    fix_database()