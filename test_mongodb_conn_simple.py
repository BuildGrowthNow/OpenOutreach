import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'openoutreach.settings.development')

import django
django.setup()

from openoutreach.mongodb.connection import reset_mongodb_connection, initialize_mongodb_connection, get_mongodb

# Reset connection
reset_mongodb_connection()
print("After reset - database:", get_mongodb())

# Initialize connection
result = initialize_mongodb_connection()
print("Initialize result:", result)
print("After init - database:", get_mongodb())