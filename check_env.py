#!/usr/bin/env python
import os

print("=== Environment Variables Check ===")
print(f"MONGODB_ENABLED from os.environ: {os.environ.get('MONGODB_ENABLED', 'NOT SET')}")
print(f"MONGODB_ATLAS_URI from os.environ: {os.environ.get('MONGODB_ATLAS_URI', 'NOT SET')}")

# Test the actual import
from openoutreach.mongodb.settings import MONGODB_ENABLED, MONGODB_ATLAS_URI
print(f"\n=== From openoutreach.mongodb.settings ===")
print(f"MONGODB_ENABLED: {MONGODB_ENABLED}")
print(f"MONGODB_ATLAS_URI: {MONGODB_ATLAS_URI}")