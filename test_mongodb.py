#!/usr/bin/env python
import os
os.environ["DJANGO_SETTINGS_MODULE"] = "openoutreach.settings"
import django
django.setup()
from openoutreach.mongodb.connection import check_mongodb_connection, get_mongodb, mongodb_connection

print("=== MongoDB Connection Test ===")
print(f"Connection established: {check_mongodb_connection()}")
print(f"Client: {mongodb_connection.client}")
db = get_mongodb()
print(f"Database: {db}")
if db:
    print(f"Database name: {db.name}")
    collections = db.list_collection_names()
    print(f"Collections: {collections}")
    print(f"Collection count: {len(collections)}")
    
    # Test creating a sample collection
    test_col = db["test_collection"]
    result = test_col.insert_one({"test": "hello", "created_at": __import__('datetime').datetime.utcnow()})
    print(f"Test insert result: {result.inserted_id}")
    
    # Verify the document was inserted
    count = test_col.count_documents({})
    print(f"Test collection document count: {count}")
    
    # List all collections again
    collections = db.list_collection_names()
    print(f"Collections after test: {collections}")
else:
    print("Database is None - MongoDB not connected")