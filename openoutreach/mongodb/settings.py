"""
MongoDB Settings Configuration

This module provides MongoDB configuration options for the OpenOutreach system.
Supports both dual-write (SQLite + MongoDB) and MongoDB-only configurations.
"""

import os
import sys
from pathlib import Path
from typing import Optional

# Load .env file if available (for development)
try:
    from dotenv import load_dotenv
    # Get the root directory (parent of openoutreach)
    ROOT_DIR = Path(__file__).resolve().parent.parent.parent
    env_path = ROOT_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    # python-dotenv not installed, use system environment variables
    pass

# MongoDB Configuration
MONGODB_ENABLED = os.environ.get('MONGODB_ENABLED', 'false').lower() == 'true'

# MongoDB connection settings - use environment variables
MONGODB_NAME = os.environ.get('MONGODB_NAME', 'openoutreach')
MONGODB_HOST = os.environ.get('MONGODB_HOST', 'localhost')
MONGODB_PORT = int(os.environ.get('MONGODB_PORT', 27017))
MONGODB_USER = os.environ.get('MONGODB_USER', '')
MONGODB_PASSWORD = os.environ.get('MONGODB_PASSWORD', '')

# MongoDB Atlas URI format (if using Atlas)
# Format: mongodb+srv://username:password@cluster.mongodb.net/database
MONGODB_ATLAS_URI = os.environ.get('MONGODB_ATLAS_URI', '')

# MongoDB connection options
MONGODB_CONNECT_TIMEOUT = int(os.environ.get('MONGODB_CONNECT_TIMEOUT', 30000))
MONGODB_SERVER_SELECTION_TIMEOUT = int(os.environ.get('MONGODB_SERVER_SELECTION_TIMEOUT', 30000))
MONGODB_SOCKET_TIMEOUT = int(os.environ.get('MONGODB_SOCKET_TIMEOUT', 10000))

# Dual-write configuration (write to both SQLite and MongoDB)
DUAL_WRITE_ENABLED = os.environ.get('DUAL_WRITE_ENABLED', 'true').lower() == 'true'

# Migration mode (enable to run data migration)
MIGRATION_MODE = os.environ.get('MIGRATION_MODE', 'false').lower() == 'true'


def get_mongodb_uri() -> Optional[str]:
    """
    Get the MongoDB connection URI.
    
    Returns:
        MongoDB connection URI or None if not configured
    """
    if MONGODB_ATLAS_URI:
        return MONGODB_ATLAS_URI
    
    if MONGODB_USER and MONGODB_PASSWORD:
        return f"mongodb://{MONGODB_USER}:{MONGODB_PASSWORD}@{MONGODB_HOST}:{MONGODB_PORT}/{MONGODB_NAME}"
    
    if MONGODB_HOST and MONGODB_PORT:
        return f"mongodb://{MONGODB_HOST}:{MONGODB_PORT}/{MONGODB_NAME}"
    
    return None


def get_mongodb_config() -> dict[str, str | int]:
    """
    Get MongoDB connection configuration as a dictionary.
    
    Returns:
        Dictionary with MongoDB connection parameters
    """
    config: dict[str, str | int] = {
        'name': MONGODB_NAME,
    }
    
    uri = get_mongodb_uri()
    if uri:
        config['uri'] = uri
    else:
        config['host'] = MONGODB_HOST
        config['port'] = MONGODB_PORT
    
    if MONGODB_USER:
        config['username'] = MONGODB_USER
    
    if MONGODB_PASSWORD:
        config['password'] = MONGODB_PASSWORD
    
    return config
