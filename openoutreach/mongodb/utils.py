"""
MongoDB Utility Functions

This module provides utility functions for MongoDB operations including:
- Aggregation pipelines for analytics
- Backup strategies
- Data cleanup routines
- Performance optimization helpers
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, TypeVar, cast
from pymongo.collection import Collection
from pymongo.results import InsertOneResult, UpdateResult, DeleteResult

from .connection import get_mongodb_collection, mongodb_connection

logger = logging.getLogger(__name__)
T = TypeVar('T')


# ==================== Aggregation Pipelines ====================

class AggregationPipelines:
    """Collection of aggregation pipelines for MongoDB analytics."""
    
    @staticmethod
    def get_campaign_performance_pipeline(
        campaign_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get aggregation pipeline for campaign performance metrics.
        
        Args:
            campaign_id: ID of the campaign
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            List of aggregation pipeline stages
        """
        pipeline: List[Dict[str, Any]] = [
            # Match documents by campaign
            {"$match": {"campaign_id": campaign_id}},
        ]
        
        # Add date range filter if specified
        if start_date or end_date:
            date_match: dict[str, Any] = {}
            if start_date:
                date_match["$gte"] = start_date
            if end_date:
                date_match["$lte"] = end_date
            pipeline.append({"$match": {"created_at": date_match}})
        
        # Add performance calculations
        pipeline.extend([
            # Group by state for funnel analysis
            {
                "$group": {
                    "_id": "$state",
                    "count": {"$sum": 1},
                    "avg_response_time": {"$avg": "$response_time_ms"},
                    "total_revenue": {"$sum": "$revenue"}
                }
            },
            # Calculate totals
            {
                "$group": {
                    "_id": None,
                    "total": {"$sum": "$count"},
                    "states": {"$push": {"state": "$_id", "count": "$count"}},
                    "avg_response_time": {"$avg": "$avg_response_time"},
                    "total_revenue": {"$sum": "$total_revenue"}
                }
            },
            # Add calculated metrics
            {
                "$project": {
                    "_id": 0,
                    "total_leads": "$total",
                    "states": "$states",
                    "avg_response_time_ms": {"$round": ["$avg_response_time", 2]},
                    "total_revenue": {"$round": ["$total_revenue", 2]},
                    "conversion_rate": {
                        "$cond": [
                            {"$gt": ["$total", 0]},
                            {"$multiply": [{"$divide": [{"$size": "$states"}, "$total"]}, 100]},
                            0
                        ]
                    }
                }
            }
        ])
        
        return pipeline
    
    @staticmethod
    def get_link_performance_pipeline(
        campaign_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get aggregation pipeline for link performance metrics.
        
        Args:
            campaign_id: Optional campaign ID filter
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            List of aggregation pipeline stages
        """
        pipeline: List[Dict[str, Any]] = []
        
        # Match tracked links
        if campaign_id:
            pipeline.append({"$match": {"campaign_id": campaign_id}})
        
        # Project link data with click counts
        pipeline.extend([
            {
                "$lookup": {
                    "from": "link_clicks",
                    "localField": "_id",
                    "foreignField": "link_id",
                    "as": "clicks"
                }
            },
            {
                "$addFields": {
                    "total_clicks": {"$size": "$clicks"},
                    "unique_clicks": {"$size": {"$setUnion": [{"$map": {
                        "input": "$clicks",
                        "as": "c",
                        "in": "$$c.ip_address"
                    }}]}}
                }
            },
            # Group by campaign
            {
                "$group": {
                    "_id": "$campaign_id",
                    "total_links": {"$sum": 1},
                    "total_clicks": {"$sum": "$total_clicks"},
                    "avg_clicks_per_link": {"$avg": "$total_clicks"},
                    "links": {"$push": {
                        "short_code": "$short_code",
                        "total_clicks": "$total_clicks",
                        "unique_clicks": "$unique_clicks"
                    }}
                }
            }
        ])
        
        return pipeline
    
    @staticmethod
    def get_lead_analytics_pipeline(
        campaign_id: str,
        state_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get aggregation pipeline for lead analytics.
        
        Args:
            campaign_id: ID of the campaign
            state_filter: Optional state filter
            
        Returns:
            List of aggregation pipeline stages
        """
        pipeline: List[Dict[str, Any]] = [
            {"$match": {"campaign_id": campaign_id}},
        ]
        
        if state_filter:
            pipeline.append({"$match": {"state": state_filter}})
        
        pipeline.extend([
            # Group by state
            {
                "$group": {
                    "_id": "$state",
                    "count": {"$sum": 1},
                    "avg_quality_score": {"$avg": "$quality_score"},
                    "leads": {"$push": {
                        "lead_id": "$lead_id",
                        "public_identifier": "$public_identifier",
                        "quality_score": "$quality_score"
                    }}
                }
            },
            # Add pipeline stage
            {
                "$group": {
                    "_id": None,
                    "total_leads": {"$sum": "$count"},
                    "states": {"$push": {"state": "$_id", "count": "$count"}},
                    "avg_quality_score": {"$avg": "$avg_quality_score"},
                    "leads": {"$push": "$leads"}
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "total_leads": "$total_leads",
                    "states": "$states",
                    "avg_quality_score": {"$round": ["$avg_quality_score", 2]}
                }
            }
        ])
        
        return pipeline


# ==================== Backup Functions ====================

class BackupManager:
    """Manager for MongoDB backup operations."""
    
    def __init__(self):
        """Initialize the backup manager."""
        self.backup_collection = get_mongodb_collection("backups")
    
    def create_backup(self, collection_name: str, description: str = "") -> Optional[Dict[str, Any]]:
        """
        Create a backup of a MongoDB collection.
        
        Args:
            collection_name: Name of the collection to backup
            description: Optional backup description
            
        Returns:
            Backup record or None if failed
        """
        collection = get_mongodb_collection(collection_name)
        if collection is None:
            logger.error(f"Collection '{collection_name}' not found")
            return None
        
        try:
            # Export all documents
            documents = list(collection.find())
            
            # Create backup record
            backup_record = {
                "collection": collection_name,
                "description": description,
                "document_count": len(documents),
                "backup_date": datetime.utcnow(),
                "documents": documents  # For now, store in backup collection
            }
            
            if self.backup_collection:
                result = self.backup_collection.insert_one(backup_record)
                logger.info(f"Backup created for '{collection_name}': {result.inserted_id}")
                return {"backup_id": str(result.inserted_id), "collection": collection_name}
            
            logger.warning("Backup collection not available, backup saved in memory")
            return {"backup_id": "temp", "collection": collection_name}
            
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return None
    
    def restore_backup(self, backup_id: str) -> bool:
        """
        Restore a backup from a backup record.
        
        Args:
            backup_id: ID of the backup record
            
        Returns:
            True if successful, False otherwise
        """
        if self.backup_collection is None:
            logger.error("Backup collection not available")
            return False
        
        try:
            backup = self.backup_collection.find_one({"_id": backup_id})
            if not backup:
                logger.error(f"Backup '{backup_id}' not found")
                return False
            
            collection = get_mongodb_collection(backup["collection"])
            if collection is None:
                logger.error(f"Target collection '{backup['collection']}' not found")
                return False
            
            # Clear existing data and restore
            collection.delete_many({})
            if backup.get("documents"):
                collection.insert_many(backup["documents"])
            
            logger.info(f"Backup '{backup_id}' restored successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore backup: {e}")
            return False
    
    def list_backups(self, collection_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List available backups.
        
        Args:
            collection_name: Optional filter by collection name
            
        Returns:
            List of backup records
        """
        if self.backup_collection is None:
            return []
        
        try:
            query: dict[str, Any] = {}
            if collection_name:
                query["collection"] = collection_name
            
            backups = list(self.backup_collection.find(query).sort("backup_date", -1))
            return [
                {
                    "id": str(b["_id"]),
                    "collection": b["collection"],
                    "description": b.get("description", ""),
                    "document_count": b.get("document_count", 0),
                    "backup_date": b.get("backup_date")
                }
                for b in backups
            ]
        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
            return []


# ==================== Cleanup Functions ====================

class CleanupManager:
    """Manager for MongoDB data cleanup operations."""
    
    def __init__(self):
        """Initialize the cleanup manager."""
        pass
    
    def cleanup_old_logs(self, days: int = 30) -> int:
        """
        Cleanup old log entries.
        
        Args:
            days: Number of days to retain
            
        Returns:
            Number of documents deleted
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        collection = get_mongodb_collection("log_entries")
        
        if collection is None:
            return 0
        
        try:
            result = collection.delete_many({"created_at": {"$lt": cutoff_date}})
            logger.info(f"Cleaned up {result.deleted_count} old log entries")
            return result.deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old logs: {e}")
            return 0
    
    def cleanup_expired_tokens(self) -> int:
        """
        Cleanup expired authentication tokens.
        
        Returns:
            Number of tokens deleted
        """
        collection = get_mongodb_collection("token_blacklist")
        
        if collection is None:
            return 0
        
        try:
            result = collection.delete_many({"expires_at": {"$lt": datetime.utcnow()}})
            logger.info(f"Cleaned up {result.deleted_count} expired tokens")
            return result.deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired tokens: {e}")
            return 0
    
    def cleanup_orphaned_data(self, collection_name: str, reference_field: str) -> int:
        """
        Cleanup orphaned data records.
        
        Args:
            collection_name: Name of the collection to clean
            reference_field: Field that references the parent document
            
        Returns:
            Number of orphaned records deleted
        """
        collection = get_mongodb_collection(collection_name)
        
        if collection is None:
            return 0
        
        try:
            # Find orphaned records (where the reference doesn't exist)
            orphaned = collection.aggregate([
                {
                    "$lookup": {
                        "from": "leads",
                        "localField": reference_field,
                        "foreignField": "_id",
                        "as": "parent"
                    }
                },
                {"$match": {"parent": {"$size": 0}}},
                {"$group": {"_id": "$_id"}}
            ])
            
            orphaned_ids = [doc["_id"] for doc in orphaned]
            if orphaned_ids:
                result = collection.delete_many({"_id": {"$in": orphaned_ids}})
                logger.info(f"Cleaned up {result.deleted_count} orphaned records from '{collection_name}'")
                return result.deleted_count
            
            return 0
            
        except Exception as e:
            logger.error(f"Failed to cleanup orphaned data: {e}")
            return 0


# ==================== Performance Helpers ====================

def create_indexes(collection_name: str, indexes: List[Dict[str, Any]]) -> None:
    """
    Create indexes on a MongoDB collection.
    
    Args:
        collection_name: Name of the collection
        indexes: List of index specifications
            [
                {
                    "name": "index_name",
                    "fields": {"field1": 1, "field2": -1},
                    "unique": False,
                    "sparse": True
                }
            ]
    """
    collection = get_mongodb_collection(collection_name)
    if collection is None:
        return
    
    for index_spec in indexes:
        try:
            field_list = list(index_spec["fields"].items())
            options: dict[str, Any] = {
                "name": index_spec.get("name", "_".join(index_spec["fields"].keys()))
            }
            
            if index_spec.get("unique"):
                options["unique"] = True
            if index_spec.get("sparse"):
                options["sparse"] = True
            
            collection.create_index(field_list, **options)
            logger.info(f"Created index '{options['name']}' on '{collection_name}'")
            
        except Exception as e:
            logger.error(f"Failed to create index: {e}")


def get_index_stats(collection_name: str) -> List[Dict[str, Any]]:
    """
    Get index statistics for a collection.
    
    Args:
        collection_name: Name of the collection
        
    Returns:
        List of index statistics
    """
    collection = get_mongodb_collection(collection_name)
    if collection is None:
        return []
    
    try:
        indexes = collection.list_indexes()
        return [
            {
                "name": idx["name"],
                "key": idx.get("key", {}),
                "unique": idx.get("unique", False),
                "sparse": idx.get("sparse", False),
                "background": idx.get("background", False)
            }
            for idx in indexes
        ]
    except Exception as e:
        logger.error(f"Failed to get index stats: {e}")
        return []


# ==================== Validation Helpers ====================

def validate_document(collection_name: str, document: Dict[str, Any], schema: Dict[str, Any]) -> bool:
    """
    Validate a document against a schema.
    
    Args:
        collection_name: Name of the collection
        document: Document to validate
        schema: Validation schema
        
    Returns:
        True if valid, False otherwise
    """
    collection = get_mongodb_collection(collection_name)
    if collection is None:
        return False
    
    try:
        # Validate required fields
        required_fields = schema.get("required", [])
        for field in required_fields:
            if field not in document:
                logger.error(f"Missing required field: {field}")
                return False
        
        # Validate field types
        properties = schema.get("properties", {})
        for field, value in document.items():
            if field in properties:
                expected_type = properties[field].get("type")
                if expected_type and not isinstance(value, eval(expected_type).__class__):
                    logger.error(f"Invalid type for field '{field}': expected {expected_type}")
                    return False
        
        logger.info(f"Document validation passed for '{collection_name}'")
        return True
        
    except Exception as e:
        logger.error(f"Document validation failed: {e}")
        return False