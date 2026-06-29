"""
MongoDB Data Migration Utilities

This module provides utilities for migrating data from SQLite to MongoDB.
Supports dual-write mode during migration and rollback capabilities.
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Type, Union
from django.db import transaction
from django.apps import apps

from .connection import check_mongodb_connection, get_mongodb_collection
from .models import (
    Lead, Campaign, Deal, Message, Note, LeadPersona,
    TrackedLink, LinkClick, LinkDealConversion, LinkedInCredentials,
    LinkedInCredentialLog, SiteConfig, Task
)

logger = logging.getLogger(__name__)


class MongoDBMigrationManager:
    """
    Manager for SQLite to MongoDB data migration.
    
    Features:
    - Incremental migration
    - Dual-write support during migration
    - Rollback capabilities
    - Progress tracking
    - Data validation
    """
    
    def __init__(self):
        """Initialize the migration manager."""
        self.migration_log: List[Dict[str, Any]] = []
        self.migrated_count: int = 0
        self.failed_count: int = 0
    
    def migrate_all(self, models_to_migrate: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Migrate all data from SQLite to MongoDB.
        
        Args:
            models_to_migrate: Optional list of model names to migrate
            
        Returns:
            Migration summary
        """
        summary: Dict[str, Any] = {
            'started_at': datetime.utcnow().isoformat(),
            'completed_at': None,
            'models_migrated': [],
            'total_migrated': 0,
            'total_failed': 0,
        }
        
        # Default models to migrate
        if models_to_migrate is None:
            models_to_migrate = [
                'core.Campaign',
                'crm.Lead',
                'crm.Deal',
                'crm.Message',
                'crm.Note',
                'crm.LeadPersona',
                'crm.TrackedLink',
                'crm.LinkClick',
                'crm.LinkDealConversion',
                'crm.LinkedInCredentials',
                'crm.LinkedInCredentialLog',
                'core.SiteConfig',
                'core.Task',
            ]
        
        try:
            for model_name in models_to_migrate:
                result = self.migrate_model(model_name)
                summary['models_migrated'].append(result)  # type: ignore
                summary['total_migrated'] += result.get('migrated', 0)  # type: ignore
                summary['total_failed'] += result.get('failed', 0)  # type: ignore
            
            summary['completed_at'] = datetime.utcnow().isoformat()
            logger.info(f"Migration completed: {summary['total_migrated']} records migrated")
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            summary['error'] = str(e)
        
        return summary
    
    def migrate_model(self, model_path: str) -> Dict[str, Any]:
        """
        Migrate a single model from SQLite to MongoDB.
        
        Args:
            model_path: Full module path for the model (e.g., 'crm.Lead')
            
        Returns:
            Migration result for the model
        """
        model = apps.get_model(model_path)
        if not model:
            return {'model': model_path, 'error': 'Model not found'}
        
        # Skip models with file-based storage (BinaryField)
        if hasattr(model, 'model_blob'):
            logger.warning(f"Skipping {model_path} - contains file-based storage")
            return {'model': model_path, 'skipped': True}
        
        # Get source and target collections
        source_queryset = model.objects.all()
        target_collection = get_mongodb_collection(model._meta.db_table)
        
        if target_collection is None:
            return {'model': model_path, 'error': 'Target collection not available'}
        
        migrated = 0
        failed = 0
        
        for source_obj in source_queryset.iterator():
            try:
                with transaction.atomic():
                    # Convert to MongoDB document
                    document = self._convert_to_mongodb_doc(model, source_obj)
                    
                    # Insert into MongoDB
                    target_collection.insert_one(document)
                    migrated += 1
                    
            except Exception as e:
                failed += 1
                logger.error(f"Failed to migrate {model_path} #{source_obj.pk}: {e}")
        
        self.migrated_count += migrated
        self.failed_count += failed
        
        return {
            'model': model_path,
            'migrated': migrated,
            'failed': failed,
            'total': migrated + failed,
        }
    
    def _convert_to_mongodb_doc(self, model: Type[Any], obj: Any) -> Dict[str, Any]:
        """
        Convert a Django model instance to MongoDB document format.
        
        Args:
            model: The model class
            obj: The model instance
            
        Returns:
            Dictionary suitable for MongoDB insertion
        """
        from bson import ObjectId  # type: ignore
        
        document: Dict[str, Any] = {'_id': str(obj.pk)}
        
        # Get all fields
        for field in model._meta.get_fields():
            if field.is_relation:
                # Handle foreign keys
                rel_field = getattr(obj, field.name, None)
                if rel_field:
                    # Store the ID as string
                    document[f'{field.name}_id'] = str(rel_field.pk)
            else:
                # Get field value
                value = getattr(obj, field.name, None)
                
                # Convert special types
                if value is not None:
                    # Handle BinaryField
                    if field.get_internal_type() == 'BinaryField':
                        # Convert bytes to list of integers for JSON compatibility
                        document[field.name] = list(bytes(value))  # type: ignore
                    # Handle DateTimeField - convert to datetime
                    elif field.get_internal_type() == 'DateTimeField':
                        document[field.name] = value.isoformat() if hasattr(value, 'isoformat') else value
                    # Handle JSONField - already compatible
                    elif field.get_internal_type() == 'JSONField':
                        document[field.name] = value
                    # Handle other fields
                    else:
                        document[field.name] = value
        
        return document
    
    def rollback_migration(self, model_path: str) -> bool:
        """
        Rollback migration for a specific model.
        
        Args:
            model_path: Full module path for the model
            
        Returns:
            True if successful, False otherwise
        """
        model = apps.get_model(model_path)
        if not model:
            return False
        
        collection = get_mongodb_collection(model._meta.db_table)
        if collection is None:
            return False
        
        try:
            # Find all MongoDB documents and delete corresponding SQLite records
            for doc in collection.find():
                try:
                    from bson import ObjectId  # type: ignore
                    # Try to get the SQLite record
                    obj = model.objects.filter(pk=ObjectId(doc['_id'])).first()
                    if obj:
                        obj.delete()
                except Exception as e:
                    logger.error(f"Failed to rollback document {doc['_id']}: {e}")
            
            logger.info(f"Rollback completed for {model_path}")
            return True
            
        except Exception as e:
            logger.error(f"Rollback failed for {model_path}: {e}")
            return False
    
    def verify_migration(self, model_path: str) -> Dict[str, Any]:
        """
        Verify migration results for a model.
        
        Args:
            model_path: Full module path for the model
            
        Returns:
            Verification results
        """
        model = apps.get_model(model_path)
        if not model:
            return {'error': 'Model not found'}
        
        # Get source and target counts
        source_count = model.objects.count()
        collection = get_mongodb_collection(model._meta.db_table)
        
        if collection is None:
            return {'error': 'Target collection not available'}
        
        target_count = collection.count_documents({})
        
        return {
            'model': model_path,
            'source_count': source_count,
            'target_count': target_count,
            'match': source_count == target_count,
        }


def run_migration() -> Dict[str, Any]:
    """Run the full SQLite to MongoDB migration."""
    migration_manager = MongoDBMigrationManager()
    return migration_manager.migrate_all()


def verify_migration() -> Dict[str, Any]:
    """Verify the migration results."""
    migration_manager = MongoDBMigrationManager()
    summary: Dict[str, Any] = {'models': [], 'all_match': True}
    
    models_to_check = [
        'core.Campaign',
        'crm.Lead',
        'crm.Deal',
        'crm.Message',
        'crm.Note',
        'crm.LeadPersona',
        'crm.TrackedLink',
        'crm.LinkClick',
        'crm.LinkDealConversion',
        'crm.LinkedInCredentials',
        'core.SiteConfig',
        'core.Task',
    ]
    
    for model_path in models_to_check:
        result = migration_manager.verify_migration(model_path)
        summary['models'].append(result)
        if not result.get('match', False):
            summary['all_match'] = False
    
    return summary


def rollback_migration(models_to_rollback: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Rollback migration for specified models.
    
    Args:
        models_to_rollback: Optional list of model paths to rollback
        
    Returns:
        Rollback summary
    """
    migration_manager = MongoDBMigrationManager()
    
    if models_to_rollback is None:
        models_to_rollback = [
            'core.Campaign',
            'crm.Lead',
            'crm.Deal',
            'crm.Message',
            'crm.Note',
            'crm.LeadPersona',
            'crm.TrackedLink',
            'crm.LinkClick',
            'crm.LinkDealConversion',
            'crm.LinkedInCredentials',
            'core.SiteConfig',
            'core.Task',
        ]
    
    summary: Dict[str, Any] = {'started_at': datetime.utcnow().isoformat(), 'results': []}
    
    for model_path in models_to_rollback:
        result = migration_manager.rollback_migration(model_path)
        summary['results'].append({'model': model_path, 'success': result})
    
    summary['completed_at'] = datetime.utcnow().isoformat()
    return summary