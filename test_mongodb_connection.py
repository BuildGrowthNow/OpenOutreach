import os
import sys
import django
from datetime import datetime

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'openoutreach.settings')
django.setup()

from openoutreach.mongodb.connection import get_mongodb_client

def test_mongodb():
    """Test MongoDB connection and create a test document."""
    try:
        print("Testing MongoDB connection...")
        client = get_mongodb_client()
        print(f"Connected to MongoDB: {client.server_info()}")
        
        db = client['openoutreach']
        collection = db['test_collection']
        
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
        
        client.close()
        print("MongoDB connection test completed successfully!")
        return True
    except Exception as e:
        print(f"Error testing MongoDB: {e}")
        return False

if __name__ == '__main__':
    success = test_mongodb()
    sys.exit(0 if success else 1)