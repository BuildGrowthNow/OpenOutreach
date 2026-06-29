import sqlite3
import os

# Path to the database file
DB_PATH = "/app/data/db.sqlite3"

def fix_database():
    print(f"Connecting to database: {DB_PATH}")
    
    # Check if database file exists
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database file not found at {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='auth_user'")
    auth_user_exists = cursor.fetchone()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='linkedin_linkedinprofile'")
    linkedin_profile_exists = cursor.fetchone()
    
    if not auth_user_exists:
        print("auth_user table does not exist - running migrations first may help")
    if not linkedin_profile_exists:
        print("linkedin_linkedinprofile table does not exist")
    
    if auth_user_exists and linkedin_profile_exists:
        # Get all users
        cursor.execute("SELECT id FROM auth_user")
        users = cursor.fetchall()
        user_ids = [u[0] for u in users]
        print(f"Users in database: {user_ids}")
        
        # Get all linkedin profiles
        cursor.execute("SELECT id, user_id FROM linkedin_linkedinprofile")
        profiles = cursor.fetchall()
        print(f"LinkedIn profiles: {profiles}")
        
        # Find orphaned profiles
        orphaned = [(id, user_id) for id, user_id in profiles if user_id not in user_ids]
        print(f"Orphaned profiles to delete: {orphaned}")
        
        if orphaned:
            for id, user_id in orphaned:
                cursor.execute("DELETE FROM linkedin_linkedinprofile WHERE id = ?", (id,))
            conn.commit()
            print(f"Deleted {len(orphaned)} orphaned profile(s)")
        else:
            print("No orphaned profiles found")
        
        # Verify
        cursor.execute("SELECT id, user_id FROM linkedin_linkedinprofile")
        remaining = cursor.fetchall()
        orphaned_after = [(id, user_id) for id, user_id in remaining if user_id not in user_ids]
        print(f"Remaining orphaned profiles: {len(orphaned_after)}")
    else:
        print("Cannot fix - required tables are missing")
    
    conn.close()
    print("\nFix complete!")

if __name__ == "__main__":
    fix_database()