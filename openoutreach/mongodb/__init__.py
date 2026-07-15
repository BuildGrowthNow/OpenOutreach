"""
MongoDB Integration Module for OpenOutreach

This module provides MongoDB integration for FastAPI, with native MongoDB
models and queries.

Features:
- Native MongoDB models and queries
- Data aggregation pipelines
- Performance indexing
- Backup strategies
"""

from .settings import *

# Import only connection-related items that don't redefine T from utils
from .connection import (
    MongoDBConnection,
    mongodb_connection,
    get_mongodb,
    get_mongodb_collection,
    check_mongodb_connection,
    reset_mongodb_connection,
)

# Import utils without T (already imported from connection)
from .utils import (
    AggregationPipelines,
    BackupManager,
    CleanupManager,
    create_indexes,
    get_index_stats,
    validate_document,
)

# Import models
from .models import (
    Lead,
    Campaign,
    Deal,
    Message,
    Note,
    LeadPersona,
    TrackedLink,
    LinkClick,
    LinkDealConversion,
    LinkedInCredentials,
    LinkedInCredentialLog,
    SiteConfig,
    Task,
    SupabaseUser,
    ensure_mongodb_indexes,
)

# Import T from utils, but we don't define it here to avoid redefinition error
# T = TypeVar('T')  # Already defined in utils.py
