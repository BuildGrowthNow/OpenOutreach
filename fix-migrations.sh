#!/bin/bash
# Fix migration dependency issue by fake-applying emails.0001_initial
# since the table already exists in the database

echo "Checking if emails_mailbox table exists..."
if docker exec openoutreach-openoutreach-1 python manage.py dbshell <<< "SELECT name FROM sqlite_master WHERE type='table' AND name='emails_mailbox';" | grep -q emails_mailbox; then
    echo "Table exists. Fake-applying emails.0001_initial migration..."
    docker exec openoutreach-openoutreach-1 python manage.py migrate emails 0001_initial --fake
    echo "Done. Now running regular migrations..."
    docker exec openoutreach-openoutreach-1 python manage.py migrate
else
    echo "Table doesn't exist. Running migrations normally..."
    docker exec openoutreach-openoutreach-1 python manage.py migrate
fi
