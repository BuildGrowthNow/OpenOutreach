import sqlite3
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "openoutreach.settings")

import django
django.setup()

from django.db import connection

# Check migrations
cursor = connection.cursor()
cursor.execute("SELECT * FROM django_migrations WHERE app='auth'")
migrations = cursor.fetchall()
print('Auth migrations in django_migrations:')
for m in migrations:
    print(m)

# Check if auth_user table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='auth_user'")
result = cursor.fetchone()
print('auth_user table exists:', result is not None)

# List all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]
print('All tables:', tables)