"""
MongoDB Connection Handler

This module provides a singleton MongoDB connection handler that manages
connections to both SQLite and MongoDB (dual-write mode).
"""

import logging
from typing import Optional, Any, Dict, Type, TypeVar
from django.conf import settings
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

# Import django.conf.settings at module level, not the values directly
# This ensures Django's settings (which are loaded last) take precedence
from django.conf import settings as django_settings

# Use helper functions to access settings dynamically at runtime
def _is_mongodb_enabled() -> bool:
    """Check if MongoDB is enabled by reading Django settings."""
    try:
        return django_settings.MONGODB_ENABLED
    except AttributeError:
        return False

def _get_mongodb_uri() -> Optional[str]:
    """Get MongoDB URI from Django settings."""
    try:
        from openoutreach.mongodb.settings import get_mongodb_uri as get_base_uri
        return get_base_uri() or getattr(django_settings, 'MONGODB_ATLAS_URI', None)
    except Exception:
        return None

def _get_mongodb_config() -> dict:
    """Get MongoDB config from Django settings."""
    try:
        from openoutreach.mongodb.settings import get_mongodb_config as get_base_config
        return get_base_config()
    except Exception:
        return {}

logger = logging.getLogger(__name__)

# Type variable for MongoDB models
T = TypeVar('T')


class MongoDBConnection:
    """
    Singleton MongoDB connection handler.
    
    Manages connections to MongoDB for dual-write operations while
    maintaining compatibility with existing SQLite database.
    """
    
    _instance: Optional['MongoDBConnection'] = None
    _client: Optional[MongoClient] = None
    _database: Optional[Database] = None
    _initialized: bool  # type: ignore[assignment]
    
    def __new__(cls) -> 'MongoDBConnection':
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False  # type: ignore[has-type]
        return cls._instance
    
    def __init__(self) -> None:
        """Initialize the MongoDB connection."""
        if self._initialized:
            return
        
        self._client = None
        self._database = None
        self._initialized = True  # type: ignore[has-type]
        
        if _is_mongodb_enabled():
            self.connect()
        else:
            logger.info("MongoDB is disabled. Using SQLite only.")
    
    def connect(self) -> bool:
        """
        Establish MongoDB connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        if self._client is not None:
            logger.debug("MongoDB connection already established")
            return True
        
        try:
            # Get connection URI
            uri = _get_mongodb_uri()
            
            if not uri:
                logger.warning("No MongoDB connection URI configured")
                return False
            
            # Create client with connection options
            # Use fallback defaults if settings don't exist
            self._client = MongoClient(
                uri,
                serverSelectionTimeoutMS=getattr(settings, 'MONGODB_SERVER_SELECTION_TIMEOUT', 30000),
                connectTimeoutMS=getattr(settings, 'MONGODB_CONNECT_TIMEOUT', 30000),
                socketTimeoutMS=getattr(settings, 'MONGODB_SOCKET_TIMEOUT', 10000)
            )
            
            # Verify connection
            self._client.admin.command('ping')
            
            # Get database
            db_name = getattr(settings, 'MONGODB_NAME', 'openoutreach')
            self._database = self._client[db_name]
            
            logger.info("MongoDB connection established successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            self._client = None
            self._database = None
            return False
    
    def disconnect(self) -> None:
        """Close the MongoDB connection."""
        if self._client is not None:
            self._client.close()
            self._client = None
            self._database = None
            logger.info("MongoDB connection closed")
    
    @property
    def client(self) -> Optional[MongoClient]:
        """Get the MongoDB client."""
        return self._client
    
    @property
    def database(self) -> Optional[Database]:
        """Get the MongoDB database."""
        return self._database
    
    def get_collection(self, collection_name: str) -> Optional[Collection]:
        """
        Get a MongoDB collection.
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            Collection object or None if not connected
        """
        if self._database is None:
            logger.warning(f"Attempted to get collection '{collection_name}' without active connection")
            return None
        
        try:
            return self._database[collection_name]
        except Exception as e:
            logger.error(f"Failed to get collection '{collection_name}': {e}")
            return None
    
    def collection_exists(self, collection_name: str) -> bool:
        """
        Check if a collection exists in MongoDB.
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            True if collection exists, False otherwise
        """
        if self._database is None:
            return False
        
        try:
            return collection_name in self._database.list_collection_names()
        except Exception as e:
            logger.error(f"Failed to check collection existence: {e}")
            return False
    
    def ensure_indexes(self, collection_name: str, indexes: list) -> None:
        """
        Ensure indexes exist on a collection.
        
        Args:
            collection_name: Name of the collection
            indexes: List of index specifications (tuples of (keys, options))
        """
        collection = self.get_collection(collection_name)
        if collection is None:
            return
        
        for key, options in indexes:
            index_name = options.get('name', '_'.join(key))
            try:
                collection.create_index(list(key.items()), name=index_name, **{k: v for k, v in options.items() if k != 'name'})
                logger.debug(f"Created index '{index_name}' on '{collection_name}'")
            except Exception as e:
                logger.error(f"Failed to create index '{index_name}': {e}")


# Global connection instance
mongodb_connection = MongoDBConnection()


def get_mongodb() -> Optional[Database]:
    """
    Get the MongoDB database connection.
    
    Returns:
        MongoDB Database object or None if not connected
    """
    return mongodb_connection.database


def get_mongodb_collection(collection_name: str) -> Optional[Collection]:
    """
    Get a MongoDB collection by name.
    
    Args:
        collection_name: Name of the collection
        
    Returns:
        Collection object or None if not connected
    """
    return mongodb_connection.get_collection(collection_name)


def check_mongodb_connection() -> bool:
    """
    Check if MongoDB connection is active.
    
    Returns:
        True if connected, False otherwise
    """
    return mongodb_connection.client is not None and mongodb_connection.database is not None


def reset_mongodb_connection() -> None:
    """Reset the MongoDB connection (for testing)."""
    mongodb_connection.disconnect()
    mongodb_connection._initialized = False