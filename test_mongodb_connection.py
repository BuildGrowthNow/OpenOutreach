import os
os.environ["DJANGO_SETTINGS_MODULE"] = "openoutreach.settings"
import django
django.setup()
from openoutreach.mongodb.connection import check_mongodb_connection, get_mongodb
print(f"Connection: {check_mongodb_connection()}")
db = get_mongodb()
print(f"DB: {db}")
if db is not None:
    print(f"Collections: {db.list_collection_names()}")
else:
    print("DB is None")
