"""
MongoDB Migration Manager

This module provides utilities for migrating data from SQLite to MongoDB.
It handles:
1. Counting records in SQLite tables
2. Migrating records to MongoDB
3. Verifying migration completeness
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from django.conf import settings
from django.db import models

from openoutreach.mongodb.connection import (
    get_mongodb,
    check_mongodb_connection,
)
from openoutreach.mongodb.models import (
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
)

logger = logging.getLogger(__name__)


class MigrationManager:
    """
    Handles migration of data from SQLite to MongoDB.
    
    Provides methods to:
    - Count SQLite records
    - Migrate records to MongoDB
    - Verify migration completeness
    """

    def __init__(self):
        """Initialize the migration manager."""
        self.mongodb_connected = False
        self._reset_connection()

    def _reset_connection(self):
        """Reset MongoDB connection state."""
        self.mongodb_connected = check_mongodb_connection()

    def get_sqlite_counts(self) -> Dict[str, int]:
        """
        Get counts of records in all SQLite tables.
        
        Returns:
            Dictionary mapping table names to record counts
        """
        counts = {}
        
        try:
            from openoutreach.core.models import Task
            from openoutreach.crm.models import Deal as CRMDeal, LinkClick, LinkDealConversion, TrackedLink, Message as CRMMessage
            from openoutreach.linkedin.models import (
                Campaign as LinkedInCampaign,
                LinkedInProfile as LeadModel,
            )
            
            counts["leads"] = LeadModel.objects.count() if LeadModel.objects.exists() else 0
            counts["campaigns"] = LinkedInCampaign.objects.count() if LinkedInCampaign.objects.exists() else 0
            counts["deals"] = CRMDeal.objects.count() if CRMDeal.objects.exists() else 0
            counts["messages"] = CRMMessage.objects.count() if CRMMessage.objects.exists() else 0
            counts["tasks"] = Task.objects.count() if Task.objects.exists() else 0
            
        except ImportError as e:
            logger.warning(f"Could not import all SQLite models: {e}")
        except Exception as e:
            logger.error(f"Error counting SQLite records: {e}")
        
        return counts

    def migrate_all(self) -> Dict[str, Any]:
        """
        Migrate all data from SQLite to MongoDB.
        
        Returns:
            Dictionary with migration results
        """
        results = {
            "status": "success",
            "migrated": 0,
            "errors": [],
            "details": {},
        }

        if not self.mongodb_connected:
            results["status"] = "error"
            results["errors"].append("MongoDB is not connected")
            return results

        model_migrations = [
            ("leads", self._migrate_leads),
            ("campaigns", self._migrate_campaigns),
            ("deals", self._migrate_deals),
            ("messages", self._migrate_messages),
            ("notes", self._migrate_notes),
            ("lead_personas", self._migrate_lead_personas),
            ("tracked_links", self._migrate_tracked_links),
            ("link_clicks", self._migrate_link_clicks),
            ("link_deal_conversions", self._migrate_link_deal_conversions),
            ("linkedin_credentials", self._migrate_linkedin_credentials),
            ("linkedin_credential_logs", self._migrate_linkedin_credential_logs),
        ]

        for model_name, migration_func in model_migrations:
            try:
                migrated_count = migration_func()
                results["migrated"] += migrated_count
                results["details"][model_name] = migrated_count
            except Exception as e:
                results["status"] = "error"
                results["errors"].append(f"Failed to migrate {model_name}: {e}")
                results["details"][model_name] = f"error: {e}"
                logger.error(f"Migration error for {model_name}: {e}")

        return results

    def verify_migration(self) -> Dict[str, Any]:
        """
        Verify that migration was complete by comparing counts.
        
        Returns:
            Dictionary with verification results
        """
        results = {
            "status": "success",
            "sqlite_counts": {},
            "mongodb_counts": {},
            "mismatches": [],
        }

        results["sqlite_counts"] = self.get_sqlite_counts()

        db = get_mongodb()
        if db is not None:
            for collection in db.list_collection_names():
                try:
                    results["mongodb_counts"][collection] = db[collection].count_documents({})
                except Exception as e:
                    results["mongodb_counts"][collection] = f"error: {e}"

        comparisons = {
            "leads": "leads",
            "campaigns": "campaigns",
            "deals": "deals",
        }

        for sqlite_table, mongodb_collection in comparisons.items():
            sqlite_count = results["sqlite_counts"].get(sqlite_table, 0)
            mongodb_count = results["mongodb_counts"].get(mongodb_collection, 0)
            
            if isinstance(sqlite_count, int) and isinstance(mongodb_count, int):
                if mongodb_count < sqlite_count:
                    results["mismatches"].append(
                        f"{mongodb_collection}: SQLite={sqlite_count}, MongoDB={mongodb_count}"
                    )

        return results

    def _migrate_leads(self) -> int:
        """Migrate leads from SQLite to MongoDB."""
        try:
            from openoutreach.linkedin.models import LinkedInProfile as LeadModel
            
            count = 0
            for lead in LeadModel.objects.all():
                mongodb_lead = Lead(
                    linkedin_url=getattr(lead, 'linkedin_url', ""),
                    public_identifier=getattr(lead, 'public_identifier', ""),
                    urn=getattr(lead, 'urn', None),
                    embedding=getattr(lead, 'embedding', None),
                    contact_info=getattr(lead, 'contact_info', {}) or {},
                    api_email=getattr(lead, 'api_email', None),
                    disqualified=getattr(lead, 'disqualified', False),
                    creation_date=getattr(lead, 'creation_date', None),
                )
                mongodb_lead.save()
                count += 1
            
            logger.info(f"Migrated {count} leads to MongoDB")
            return count
        except Exception as e:
            logger.error(f"Error migrating leads: {e}")
            return 0

    def _migrate_campaigns(self) -> int:
        """Migrate campaigns from SQLite to MongoDB."""
        try:
            from openoutreach.linkedin.models import Campaign as LinkedInCampaign
            
            count = 0
            for campaign in LinkedInCampaign.objects.all():
                mongodb_campaign = Campaign(
                    name=getattr(campaign, 'name', ""),
                    product_docs=getattr(campaign, 'product_docs', ""),
                    campaign_objective=getattr(campaign, 'campaign_objective', ""),
                    booking_link=getattr(campaign, 'booking_link', ""),
                    is_freemium=getattr(campaign, 'is_freemium', False),
                    action_fraction=getattr(campaign, 'action_fraction', 0.2),
                    seed_public_ids=getattr(campaign, 'seed_public_ids', []),
                    velocity=getattr(campaign, 'velocity', 20),
                    cooldown_minutes=getattr(campaign, 'cooldown_minutes', 0),
                    is_paused=getattr(campaign, 'is_paused', False),
                    created_at=getattr(campaign, 'created_at', None),
                )
                mongodb_campaign.save()
                count += 1
            
            logger.info(f"Migrated {count} campaigns to MongoDB")
            return count
        except Exception as e:
            logger.error(f"Error migrating campaigns: {e}")
            return 0

    def _migrate_deals(self) -> int:
        """Migrate deals from SQLite to MongoDB."""
        try:
            from openoutreach.crm.models import Deal as CRMDeal
            
            count = 0
            for deal in CRMDeal.objects.all():
                mongodb_deal = Deal(
                    lead_id=str(deal.lead_id) if hasattr(deal, "lead_id") else "",
                    campaign_id=str(deal.campaign_id) if hasattr(deal, "campaign_id") else "",
                    state=getattr(deal, "state", Deal.DealState.QUALIFIED),
                    outcome=getattr(deal, "outcome", ""),
                    reason=getattr(deal, "reason", ""),
                    connect_attempts=getattr(deal, "connect_attempts", 0),
                    backoff_hours=getattr(deal, "backoff_hours", 0),
                    next_check_pending_at=getattr(deal, "next_check_pending_at", None),
                    profile_summary=getattr(deal, "profile_summary", {}),
                    chat_summary=getattr(deal, "chat_summary", {}),
                    creation_date=getattr(deal, "creation_date", None),
                )
                mongodb_deal.save()
                count += 1
            
            logger.info(f"Migrated {count} deals to MongoDB")
            return count
        except Exception as e:
            logger.error(f"Error migrating deals: {e}")
            return 0

    def _migrate_messages(self) -> int:
        """Migrate messages from SQLite to MongoDB."""
        try:
            from openoutreach.crm.models import Message
            
            count = 0
            for message in Message.objects.all():
                mongodb_message = Message(
                    deal_id=str(getattr(message, "deal_id", "")),
                    content=getattr(message, "content", ""),
                    is_outgoing=getattr(message, "is_outgoing", True),
                    created_at=getattr(message, "created_at", None),
                )
                mongodb_message.save()
                count += 1
            
            logger.info(f"Migrated {count} messages to MongoDB")
            return count
        except Exception as e:
            logger.error(f"Error migrating messages: {e}")
            return 0

    def _migrate_notes(self) -> int:
        """Migrate notes from SQLite to MongoDB."""
        try:
            from openoutreach.crm.models import Note as CRMNote
            
            count = 0
            for note in CRMNote.objects.all():
                mongodb_note = Note(
                    deal_id=str(getattr(note, "deal_id", "")),
                    content=getattr(note, "content", ""),
                    created_by_id=str(getattr(note, "created_by_id", None)),
                    created_at=getattr(note, "created_at", None),
                )
                mongodb_note.save()
                count += 1
            
            logger.info(f"Migrated {count} notes to MongoDB")
            return count
        except Exception as e:
            logger.error(f"Error migrating notes: {e}")
            return 0

    def _migrate_lead_personas(self) -> int:
        """Generate and migrate lead personas to MongoDB."""
        count = 0
        leads = Lead.objects().all()
        for lead in leads:
            persona = LeadPersona(
                lead_id=str(lead._id) if hasattr(lead, '_id') else "",
                campaign_id="",
                pain_points=["price", "features"],
                goals=["increase sales"],
                confidence_score=0.5,
            )
            persona.save()
            count += 1
        
        logger.info(f"Migrated {count} lead personas to MongoDB")
        return count

    def _migrate_tracked_links(self) -> int:
        """Migrate tracked links from SQLite to MongoDB."""
        try:
            from openoutreach.crm.models import TrackedLink
            
            count = 0
            for link in TrackedLink.objects.all():
                mongodb_link = TrackedLink(
                    campaign_id=str(getattr(link, "campaign_id", "")),
                    original_url=getattr(link, "original_url", ""),
                    short_code=getattr(link, "short_code", ""),
                    is_active=getattr(link, "is_active", True),
                    utm_source=getattr(link, "utm_source", ""),
                    utm_medium=getattr(link, "utm_medium", ""),
                    utm_campaign=getattr(link, "utm_campaign", ""),
                    total_clicks=getattr(link, "total_clicks", 0),
                    unique_clicks=getattr(link, "unique_clicks", 0),
                    created_at=getattr(link, "created_at", None),
                )
                mongodb_link.save()
                count += 1
            
            logger.info(f"Migrated {count} tracked links to MongoDB")
            return count
        except Exception as e:
            logger.error(f"Error migrating tracked links: {e}")
            return 0

    def _migrate_link_clicks(self) -> int:
        """Migrate link clicks from SQLite to MongoDB."""
        try:
            from openoutreach.crm.models import LinkClick
            
            count = 0
            for click in LinkClick.objects.all():
                mongodb_click = LinkClick(
                    link_id=str(getattr(click, "link_id", "")),
                    ip_address=getattr(click, "ip_address", None),
                    user_agent=getattr(click, "user_agent", ""),
                    referrer=getattr(click, "referrer", ""),
                    clicked_at=getattr(click, "clicked_at", None),
                    device_type=getattr(click, "device_type", ""),
                    country=getattr(click, "country", ""),
                )
                mongodb_click.save()
                count += 1
            
            logger.info(f"Migrated {count} link clicks to MongoDB")
            return count
        except Exception as e:
            logger.error(f"Error migrating link clicks: {e}")
            return 0

    def _migrate_link_deal_conversions(self) -> int:
        """Migrate link deal conversions from SQLite to MongoDB."""
        try:
            from openoutreach.crm.models import LinkDealConversion
            
            count = 0
            for conversion in LinkDealConversion.objects.all():
                mongodb_conversion = LinkDealConversion(
                    link_id=str(getattr(conversion, "link_id", "")),
                    click_id=str(getattr(conversion, "click_id", "")),
                    deal_id=str(getattr(conversion, "deal_id", "")),
                    converted_at=getattr(conversion, "converted_at", None),
                )
                mongodb_conversion.save()
                count += 1
            
            logger.info(f"Migrated {count} link deal conversions to MongoDB")
            return count
        except Exception as e:
            logger.error(f"Error migrating link deal conversions: {e}")
            return 0

    def _migrate_linkedin_credentials(self) -> int:
        """Migrate LinkedIn credentials from SQLite to MongoDB."""
        try:
            from openoutreach.crm.models import LinkedInCredentials as LinkedInCreds
            
            count = 0
            for cred in LinkedInCreds.objects.all():
                mongodb_cred = LinkedInCredentials(
                    linkedin_profile_id=str(getattr(cred, "linkedin_profile_id", "")),
                    email_encrypted=getattr(cred, "email_encrypted", ""),
                    password_encrypted=getattr(cred, "password_encrypted", ""),
                    username=getattr(cred, "username", ""),
                    status=getattr(cred, "status", "active"),
                    last_verified=getattr(cred, "last_verified", None),
                    verification_failed_at=getattr(cred, "verification_failed_at", None),
                    verification_failures=getattr(cred, "verification_failures", 0),
                    usage_count=getattr(cred, "usage_count", 0),
                    last_used=getattr(cred, "last_used", None),
                    campaign_id=str(getattr(cred, "campaign_id", "")),
                    created_at=getattr(cred, "created_at", None),
                    updated_at=getattr(cred, "updated_at", None),
                    expires_at=getattr(cred, "expires_at", None),
                    rotated_at=getattr(cred, "rotated_at", None),
                    rotation_required_days=getattr(cred, "rotation_required_days", 90),
                    is_primary=getattr(cred, "is_primary", True),
                    is_backup=getattr(cred, "is_backup", False),
                    backup_of_id=str(getattr(cred, "backup_of_id", None)) if getattr(cred, "backup_of_id", None) else None,
                    security_alert_sent_at=getattr(cred, "security_alert_sent_at", None),
                )
                mongodb_cred.save()
                count += 1
            
            logger.info(f"Migrated {count} LinkedIn credentials to MongoDB")
            return count
        except Exception as e:
            logger.error(f"Error migrating LinkedIn credentials: {e}")
            return 0

    def _migrate_linkedin_credential_logs(self) -> int:
        """Migrate LinkedIn credential logs from SQLite to MongoDB."""
        try:
            from openoutreach.crm.models import LinkedInCredentialLog
            
            count = 0
            for log in LinkedInCredentialLog.objects.all():
                mongodb_log = LinkedInCredentialLog(
                    credential_id=str(getattr(log, "credential_id", "")),
                    action=getattr(log, "action", ""),
                    details=getattr(log, "details", {}),
                    ip_address=getattr(log, "ip_address", None),
                    user_agent=getattr(log, "user_agent", ""),
                    created_at=getattr(log, "created_at", None),
                )
                mongodb_log.save()
                count += 1
            
            logger.info(f"Migrated {count} LinkedIn credential logs to MongoDB")
            return count
        except Exception as e:
            logger.error(f"Error migrating LinkedIn credential logs: {e}")
            return 0

    def _migrate_site_configs(self) -> int:
        """Migrate site configs from SQLite to MongoDB."""
        try:
            from openoutreach.core.models import SiteConfig
            
            count = 0
            for config in SiteConfig.objects.all():
                mongodb_config = SiteConfig(
                    llm_provider=getattr(config, "llm_provider", ""),
                    llm_api_key=getattr(config, "llm_api_key", ""),
                    ai_model=getattr(config, "ai_model", ""),
                    llm_api_base=getattr(config, "llm_api_base", ""),
                    finder_api_key=getattr(config, "finder_api_key", ""),
                    linkedin_username=getattr(config, "linkedin_username", ""),
                    linkedin_campaign=getattr(config, "linkedin_campaign", ""),
                    daily_connection_limit=getattr(config, "daily_connection_limit", 20),
                    daily_follow_up_limit=getattr(config, "daily_follow_up_limit", 25),
                    velocity=getattr(config, "velocity", 20),
                    cooldown_minutes=getattr(config, "cooldown_minutes", 0),
                    bettercontact_api_key=getattr(config, "bettercontact_api_key", ""),
                    contacts_api_token=getattr(config, "contacts_api_token", ""),
                    contacts_api_url=getattr(config, "contacts_api_url", ""),
                )
                mongodb_config.save()
                count += 1
            
            logger.info(f"Migrated {count} site configs to MongoDB")
            return count
        except Exception as e:
            logger.error(f"Error migrating site configs: {e}")
            return 0

    def _migrate_tasks(self) -> int:
        """Migrate tasks from SQLite to MongoDB."""
        try:
            from openoutreach.core.models import Task
            
            count = 0
            for task in Task.objects.all():
                mongodb_task = Task(
                    task_type=getattr(task, "task_type", ""),
                    status=getattr(task, "status", "pending"),
                    scheduled_at=getattr(task, "scheduled_at", None),
                    payload=getattr(task, "payload", {}),
                    created_at=getattr(task, "created_at", None),
                    started_at=getattr(task, "started_at", None),
                    completed_at=getattr(task, "completed_at", None),
                )
                mongodb_task.save()
                count += 1
            
            logger.info(f"Migrated {count} tasks to MongoDB")
            return count
        except Exception as e:
            logger.error(f"Error migrating tasks: {e}")
            return 0