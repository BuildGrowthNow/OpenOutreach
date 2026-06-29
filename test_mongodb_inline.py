#!/usr/bin/env python
import os
os.environ["DJANGO_SETTINGS_MODULE"] = "openoutreach.settings"
import django
django.setup()

print("=== Testing MongoDB Connection ===")
from openoutreach.mongodb.connection import (
    get_mongodb,
    _is_mongodb_enabled,
    _get_mongodb_uri,
    mongodb_connection,
    initialize_mongodb_connection,
    check_mongodb_connection
)

print(f"MONGODB_ENABLED: {_is_mongodb_enabled()}")
print(f"MONGODB_URI: {_get_mongodb_uri()}")
print(f"MongoDB Connection object: {mongodb_connection}")
print(f"MongoDB Connection client: {mongodb_connection.client}")
print(f"MongoDB Connection database: {mongodb_connection.database}")

# Try to initialize
print("\n--- Initializing connection ---")
result = initialize_mongodb_connection()
print(f"initialize_mongodb_connection() returned: {result}")

# Check connection status
print(f"\nConnection status after init: {check_mongodb_connection()}")
print(f"Client: {mongodb_connection.client}")
print(f"Database: {mongodb_connection.database}")

# Try to get database
db = get_mongodb()
print(f"get_mongodb() returned: {db}")

if db is not None:
    print("Collections:", db.list_collection_names())
else:
    print("No database - connection failed")
