#!/usr/bin/env python
import os
os.environ["DJANGO_SETTINGS_MODULE"] = "openoutreach.settings"
import django
django.setup()
from django.conf import settings

print("=== Django Settings Check ===")
print(f"MONGODB_ENABLED: {getattr(settings, 'MONGODB_ENABLED', 'NOT SET')}")
print(f"MONGODB_ATLAS_URI: {getattr(settings, 'MONGODB_ATLAS_URI', 'NOT SET')}")
print(f"MONGODB_NAME: {getattr(settings, 'MONGODB_NAME', 'NOT SET')}")

# Import MongoDB connection module
from openoutreach.mongodb.connection import check_mongodb_connection, get_mongodb, mongodb_connection
print("\n=== MongoDB Connection Status ===")
print(f"Connection established: {check_mongodb_connection()}")
print(f"Client: {mongodb_connection.client}")
print(f"Database: {mongodb_connection.database}")

# If not connected, check what's happening
if not check_mongodb_connection():
    print("\n=== Debugging ===")
    print("Checking settings module:")
    print(f"Settings file: {settings.DJANGO_SETTINGS_MODULE if hasattr(settings, 'DJANGO_SETTINGS_MODULE') else 'N/A'}")