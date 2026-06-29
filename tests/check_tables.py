#!/usr/bin/env python
"""Check what tables exist in the database after migration."""

import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DJANGO_SETTINGS_MODULE"] = "openoutreach.settings.development"
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

import django
django.setup()

from django.core.management import call_command
from django.db import connection

# Run migrations
call_command("migrate", "--run-syncdb", verbosity=0)

# Check what tables exist
with connection.cursor() as cursor:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print("Tables:", [t[0] for t in tables])

# Check if auth_user exists
with connection.cursor() as cursor:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='auth_user'")
    tables = cursor.fetchall()
    print("auth_user table exists:", len(tables) > 0)

# Check if core_user exists
with connection.cursor() as cursor:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='core_user'")
    tables = cursor.fetchall()
    print("core_user table exists:", len(tables) > 0)