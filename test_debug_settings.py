#!/usr/bin/env python
import os
os.environ["DJANGO_SETTINGS_MODULE"] = "openoutreach.settings.development"
import django
django.setup()

from openoutreach.settings import MONGODB_ENABLED, DEBUG, MONGODB_ATLAS_URI, DUAL_WRITE_ENABLED
from openoutreach.mongodb.settings import MONGODB_ENABLED as MONGO_ENABLED, MONGODB_ATLAS_URI as MONGO_ATLAS_URI

print(f"MONGODB_ENABLED (from settings): {MONGODB_ENABLED}")
print(f"DEBUG: {DEBUG}")
print(f"MONGODB_ATLAS_URI (from settings): {MONGODB_ATLAS_URI[:30]}...<hidden>")
print(f"DUAL_WRITE_ENABLED: {DUAL_WRITE_ENABLED}")
print(f"MONGODB_ENABLED (from mongodb.settings): {MONGO_ENABLED}")
print(f"MONGODB_ATLAS_URI (from mongodb.settings): {MONGO_ATLAS_URI[:30]}...<hidden>")

# Test connection directly
from openoutreach.mongodb.connection import check_mongodb_connection
print(f"check_mongodb_connection(): {check_mongodb_connection()}")

# Get database
from openoutreach.mongodb.connection import get_mongodb
db = get_mongodb()
print(f"Database: {db}")

if db is not None:
    print(f"Collections: {db.list_collection_names()}")
else:
    print("DB is None - Connection failed")