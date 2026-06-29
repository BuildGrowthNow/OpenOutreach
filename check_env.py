import os
print("MONGODB_ENABLED:", os.environ.get('MONGODB_ENABLED'))
print("MONGODB_ATLAS_URI:", os.environ.get('MONGODB_ATLAS_URI')[:50] + '...' if os.environ.get('MONGODB_ATLAS_URI') else 'NOT SET')