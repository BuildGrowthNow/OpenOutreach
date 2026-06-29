"""Debug test to check what tables exist in the test database."""

import pytest


@pytest.mark.django_db
class TestDebugDB:
    def test_check_tables(self):
        from django.db import connection
        
        # Check what tables exist
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            print("Tables:", [t[0] for t in tables])
        
        # Check if auth_user exists
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='auth_user'")
            tables = cursor.fetchall()
            print("auth_user table exists:", len(tables) > 0)
            if tables:
                print("auth_user table found!")
            else:
                print("ERROR: auth_user table NOT found!")
        
        # Check if core_user exists
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='core_user'")
            tables = cursor.fetchall()
            print("core_user table exists:", len(tables) > 0)