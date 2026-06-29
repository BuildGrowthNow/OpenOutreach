# Script to clean up migrations and reset database
import os
import shutil

# Base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Remove all migrations except the initial __init__.py
apps_to_cleanup = [
    'openoutreach/core/migrations',
    'openoutreach/linkedin/migrations',
    'openoutreach/api/migrations',
    'openoutreach/crm/migrations',
]

for app_dir in apps_to_cleanup:
    migrations_dir = os.path.join(BASE_DIR, app_dir)
    if os.path.exists(migrations_dir):
        # Keep only __init__.py
        for item in os.listdir(migrations_dir):
            item_path = os.path.join(migrations_dir, item)
            if item != '__init__.py' and os.path.isfile(item_path):
                os.remove(item_path)
        print(f"Cleaned: {app_dir}")

# Remove database
db_path = os.path.join(BASE_DIR, 'data', 'db.sqlite3')
if os.path.exists(db_path):
    os.remove(db_path)
    print(f"Removed: {db_path}")

print("Cleanup complete!")