#!/usr/bin/env python
import os
os.environ["DJANGO_SETTINGS_MODULE"] = "openoutreach.settings"
import django
django.setup()

print("=== Environment Variables Check ===")
print(f"MONGODB_ENABLED from os.environ: {os.environ.get('MONGODB_ENABLED', 'NOT SET')}")
print(f"MONGODB_ATLAS_URI from os.environ: {os.environ.get('MONGODB_ATLAS_URI', 'NOT SET')}")

# Test the actual import (after Django setup)
from openoutreach.mongodb.connection import check_mongodb_connection
print(f"\n=== MongoDB Connection Status ===")
print(f"Connection established: {check_mongodb_connection()}")
