#!/usr/bin/env python
import os

print("=== Testing os.environ ===")
print(f"MONGODB_ATLAS_URI: {os.environ.get('MONGODB_ATLAS_URI', 'NOT SET')}")
print(f"MONGODB_ENABLED: {os.environ.get('MONGODB_ENABLED', 'NOT SET')}")

# Test the settings module
from openoutreach.mongodb.settings import MONGODB_ENABLED, MONGODB_ATLAS_URI, get_mongodb_uri
print(f"\n=== From settings module ===")
print(f"MONGODB_ENABLED: {MONGODB_ENABLED}")
print(f"MONGODB_ATLAS_URI: {MONGODB_ATLAS_URI}")
print(f"get_mongodb_uri(): {get_mongodb_uri()}")