import os
import sys
import django
from datetime import datetime

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'openoutreach.settings')
django.setup()

from openoutreach.mongodb.connection import (
    MongoDBConnection,
    get_mongodb,
    get_mongodb_collection
)

def test_mongodb():
    """Test MongoDB connection and create a test document."""
    try:
        print("Testing MongoDB connection...")
        
        # Get MongoDB connection instance
        conn = MongoDBConnection()
        
        # Check if MongoDB is enabled
        if not conn.client:
            print("MongoDB is not enabled. Check MONGODB_ENABLED in settings.")
            # Still test that we can connect to the configured MongoDB server
            from openoutreach.mongodb.settings import MONGODB_ENABLED, MONGODB_ATLAS_URI
            print(f"MONGODB_ENABLED: {MONGODB_ENABLED}")
            print(f"MONGODB_ATLAS_URI: {'***' + MONGODB_ATLAS_URI[-10:] if MONGODB_ATLAS_URI else 'Not set'}")
            return False
        
        # Test connection with ping
        conn.client.admin.command('ping')
        print("MongoDB connection successful!")
        
        db = get_mongodb()
        if not db:
            print("Failed to get MongoDB database")
            return False
        
        collection = get_mongodb_collection('test_collection')
        if not collection:
            print("Failed to get test_collection")
            return False
        
        # Insert a test document
        test_data = {
            'test': 'test_data',
            'created': datetime.utcnow(),
            'status': 'success'
        }
        result = collection.insert_one(test_data)
        print(f"Test record created with ID: {result.inserted_id}")
        
        # Verify the document was inserted
        doc = collection.find_one({'_id': result.inserted_id})
        print(f"Retrieved document: {doc}")
        
        conn.disconnect()
        print("MongoDB connection test completed successfully!")
        return True
    except Exception as e:
        print(f"Error testing MongoDB: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_mongodb()
    sys.exit(0 if success else 1)