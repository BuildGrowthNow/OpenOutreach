"""
Data Access Layer for MongoDB.

Provides high-level CRUD, atomic operations, and query builders.
Replaces Django ORM queries and signals with explicit service-layer calls.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pymongo import ASCENDING, DESCENDING

from .connection import get_mongodb_collection

logger = logging.getLogger(__name__)


class TaskDAL:
    """Task queue operations (atomic claiming is critical for daemon)."""

    @staticmethod
    def create_task(
        task_type: str,
        linkedin_profile_id: Optional[str],
        payload: Dict[str, Any],
        scheduled_at: datetime,
        user_id: Optional[str] = None
    ):
        """Create a new task."""
        from .models import Task

        if linkedin_profile_id:
            payload = {**payload, "linkedin_profile_id": linkedin_profile_id}
        task = Task(
            task_type=task_type,
            payload=payload,
            scheduled_at=scheduled_at,
            user_id=user_id,
            status=Task.STATUS_PENDING,
        )
        task.save()
        return task

    @staticmethod
    def claim_next_task(linkedin_profile_id: Optional[str] = None):
        """
        Atomic find-and-update to claim next pending task.
        This is critical for daemon concurrency - prevents race conditions.
        """
        from .models import Task

        collection = get_mongodb_collection('tasks')
        if collection is None:
            return None

        now = datetime.now(timezone.utc)
        query = {'status': Task.STATUS_PENDING, 'scheduled_at': {'$lte': now}}

        if linkedin_profile_id:
            query['linkedin_profile_id'] = linkedin_profile_id

        try:
            # Atomic find-and-modify operation
            result = collection.find_one_and_update(
                query,
                {'$set': {'status': Task.STATUS_RUNNING, 'started_at': now}},
                sort=[('scheduled_at', ASCENDING)],
                return_document=True,
            )

            if result:
                return Task.from_dict(result)
            return None
        except Exception as e:
            logger.error(f"Failed to claim next task: {e}")
            return None

    @staticmethod
    def mark_task_completed(task_id: str):
        """Mark a task as completed."""
        from .models import Task

        collection = get_mongodb_collection('tasks')
        if collection is None:
            return False

        try:
            result = collection.update_one(
                {"_id": task_id},
                {"$set": {
                    "status": Task.STATUS_COMPLETED,
                    "completed_at": datetime.now(timezone.utc)
                }}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to mark task completed '{task_id}': {e}")
            return False

    @staticmethod
    def mark_task_failed(task_id: str, error_message: str):
        """Mark a task as failed with error message."""
        from .models import Task

        collection = get_mongodb_collection('tasks')
        if collection is None:
            return False

        try:
            result = collection.update_one(
                {"_id": task_id},
                {"$set": {
                    "status": Task.STATUS_FAILED,
                    "error_message": error_message,
                    "completed_at": datetime.now(timezone.utc)
                }}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to mark task failed '{task_id}': {e}")
            return False

    @staticmethod
    def get_pending_tasks_for_deal(deal_id: str, task_type: Optional[str] = None):
        """Get pending tasks for a specific deal."""
        from .models import Task

        collection = get_mongodb_collection('tasks')
        if collection is None:
            return []

        query = {
            "payload.deal_id": deal_id,
            "status": Task.STATUS_PENDING
        }

        if task_type:
            query["task_type"] = task_type

        try:
            tasks = []
            for data in collection.find(query):
                tasks.append(Task.from_dict(data))
            return tasks
        except Exception as e:
            logger.error(f"Failed to get pending tasks for deal '{deal_id}': {e}")
            return []

    @staticmethod
    def get_pending_tasks_count(linkedin_profile_id: Optional[str] = None) -> int:
        """Count pending tasks, optionally filtered by profile."""
        from .models import Task

        collection = get_mongodb_collection('tasks')
        if collection is None:
            return 0

        query = {"status": Task.STATUS_PENDING}
        if linkedin_profile_id:
            query["linkedin_profile_id"] = linkedin_profile_id

        try:
            return collection.count_documents(query)
        except Exception as e:
            logger.error(f"Failed to count pending tasks: {e}")
            return 0

    @staticmethod
    def cleanup_campaign_tasks(campaign_id: str):
        """
        Delete tasks whose payload.campaign_id matches.
        Replaces Django pre_delete signal on Campaign.
        """
        collection = get_mongodb_collection('tasks')
        if collection is None:
            return 0

        try:
            result = collection.delete_many({"payload.campaign_id": campaign_id})
            deleted_count = result.deleted_count
            logger.info(f"Deleted {deleted_count} tasks for campaign '{campaign_id}'")
            return deleted_count
        except Exception as e:
            logger.error(f"Failed to cleanup tasks for campaign '{campaign_id}': {e}")
            return 0

    @staticmethod
    def recover_stale_tasks(timeout_minutes: int = 30):
        """
        Recover tasks that have been running for too long (stale).
        Resets them to PENDING so they can be retried.
        """
        from .models import Task

        collection = get_mongodb_collection('tasks')
        if collection is None:
            return 0

        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)

        try:
            result = collection.update_many(
                {
                    "status": Task.STATUS_RUNNING,
                    "started_at": {"$lt": cutoff}
                },
                {"$set": {"status": Task.STATUS_PENDING, "started_at": None}}
            )
            recovered_count = result.modified_count
            if recovered_count > 0:
                logger.warning(f"Recovered {recovered_count} stale tasks")
            return recovered_count
        except Exception as e:
            logger.error(f"Failed to recover stale tasks: {e}")
            return 0


class CampaignDAL:
    """Campaign operations including cascade delete."""

    @staticmethod
    def get_user_campaigns(user_id: str):
        """Get all campaigns for a user."""
        from .models import Campaign

        collection = get_mongodb_collection('campaigns')
        if collection is None:
            return []

        try:
            campaigns = []
            for data in collection.find({"user_id": user_id}):
                campaigns.append(Campaign.from_dict(data))
            return campaigns
        except Exception as e:
            logger.error(f"Failed to get campaigns for user '{user_id}': {e}")
            return []

    @staticmethod
    def get_active_campaigns(user_id: Optional[str] = None):
        """Get active (not paused) campaigns."""
        from .models import Campaign

        collection = get_mongodb_collection('campaigns')
        if collection is None:
            return []

        query: Dict[str, Any] = {"is_paused": False}
        if user_id:
            query["user_id"] = user_id

        try:
            campaigns = []
            for data in collection.find(query):
                campaigns.append(Campaign.from_dict(data))
            return campaigns
        except Exception as e:
            logger.error(f"Failed to get active campaigns: {e}")
            return []

    @staticmethod
    def delete_campaign(campaign_id: str):
        """
        Delete campaign + cascade cleanup (replaces Django cascade + signal).
        This is the single entry point for campaign deletion.
        """
        # Delete tasks (replaces cleanup_campaign_tasks signal)
        TaskDAL.cleanup_campaign_tasks(campaign_id)

        # Delete deals
        deals_collection = get_mongodb_collection('deals')
        if deals_collection is not None:
            try:
                result = deals_collection.delete_many({"campaign_id": campaign_id})
                logger.info(f"Deleted {result.deleted_count} deals for campaign '{campaign_id}'")
            except Exception as e:
                logger.error(f"Failed to delete deals for campaign '{campaign_id}': {e}")

        # Delete state graph + nodes + transitions
        graph_collection = get_mongodb_collection('campaign_state_graphs')
        if graph_collection is not None:
            try:
                graph = graph_collection.find_one({"campaign_id": campaign_id})
                if graph:
                    graph_id = str(graph["_id"])

                    # Delete nodes
                    nodes_collection = get_mongodb_collection('state_nodes')
                    if nodes_collection is not None:
                        nodes_collection.delete_many({"state_graph_id": graph_id})

                    # Delete transitions
                    transitions_collection = get_mongodb_collection('state_transitions')
                    if transitions_collection is not None:
                        transitions_collection.delete_many({"state_graph_id": graph_id})

                    # Delete graph
                    graph_collection.delete_one({"_id": graph["_id"]})
            except Exception as e:
                logger.error(f"Failed to delete state graph for campaign '{campaign_id}': {e}")

        # Delete search keywords
        keywords_collection = get_mongodb_collection('search_keywords')
        if keywords_collection is not None:
            try:
                keywords_collection.delete_many({"campaign_id": campaign_id})
            except Exception as e:
                logger.error(f"Failed to delete keywords for campaign '{campaign_id}': {e}")

        # Delete action logs
        logs_collection = get_mongodb_collection('action_logs')
        if logs_collection is not None:
            try:
                logs_collection.delete_many({"campaign_id": campaign_id})
            except Exception as e:
                logger.error(f"Failed to delete action logs for campaign '{campaign_id}': {e}")

        # Nullify campaign_id in notifications (don't delete notifications)
        notifications_collection = get_mongodb_collection('notifications')
        if notifications_collection is not None:
            try:
                notifications_collection.update_many(
                    {"campaign_id": campaign_id},
                    {"$set": {"campaign_id": None}}
                )
            except Exception as e:
                logger.error(f"Failed to nullify notifications for campaign '{campaign_id}': {e}")

        # Finally delete the campaign itself
        campaigns_collection = get_mongodb_collection('campaigns')
        if campaigns_collection is not None:
            try:
                result = campaigns_collection.delete_one({"_id": campaign_id})
                if result.deleted_count > 0:
                    logger.info(f"Successfully deleted campaign '{campaign_id}'")
                    return True
                else:
                    logger.warning(f"Campaign '{campaign_id}' not found")
                    return False
            except Exception as e:
                logger.error(f"Failed to delete campaign '{campaign_id}': {e}")
                return False

        return False


class DealDAL:
    """Deal operations."""

    @staticmethod
    def get_qualified_deals(campaign_id: str, limit: int = 100):
        """Get qualified deals for a campaign (ready to connect)."""
        from .models import Deal

        collection = get_mongodb_collection('deals')
        if collection is None:
            return []

        try:
            deals = []
            query = {
                "campaign_id": campaign_id,
                "state": Deal.DealState.QUALIFIED
            }
            for data in collection.find(query).limit(limit):
                deals.append(Deal.from_dict(data))
            return deals
        except Exception as e:
            logger.error(f"Failed to get qualified deals for campaign '{campaign_id}': {e}")
            return []

    @staticmethod
    def get_deals_by_campaign(campaign_id: str):
        """Get all deals for a campaign."""
        from .models import Deal

        collection = get_mongodb_collection('deals')
        if collection is None:
            return []

        try:
            deals = []
            for data in collection.find({"campaign_id": campaign_id}):
                deals.append(Deal.from_dict(data))
            return deals
        except Exception as e:
            logger.error(f"Failed to get deals for campaign '{campaign_id}': {e}")
            return []

    @staticmethod
    def set_deal_state(deal_id: str, new_state: str, reason: Optional[str] = None):
        """Update deal state with optional reason."""
        collection = get_mongodb_collection('deals')
        if collection is None:
            return False

        update = {"state": new_state}
        if reason:
            update["reason"] = reason

        try:
            result = collection.update_one(
                {"_id": deal_id},
                {"$set": update}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to set deal state '{deal_id}': {e}")
            return False

    @staticmethod
    def get_deals_by_state(campaign_id: str, state: str):
        """Get deals in a specific state for a campaign."""
        from .models import Deal

        collection = get_mongodb_collection('deals')
        if collection is None:
            return []

        try:
            deals = []
            query = {
                "campaign_id": campaign_id,
                "state": state
            }
            for data in collection.find(query):
                deals.append(Deal.from_dict(data))
            return deals
        except Exception as e:
            logger.error(f"Failed to get deals by state for campaign '{campaign_id}': {e}")
            return []


class LeadDAL:
    """Lead operations."""

    @staticmethod
    def find_or_create_lead(
        linkedin_url: str,
        public_identifier: str,
        user_id: str
    ):
        """
        Find existing lead or create new one.
        Returns (lead, created) tuple.
        """
        from .models import Lead

        # Try to find by public_identifier first
        if public_identifier:
            lead = Lead.find_by_public_identifier(public_identifier)
            if lead:
                return lead, False

        # Try to find by linkedin_url
        if linkedin_url:
            lead = Lead.find_by_linkedin_url(linkedin_url)
            if lead:
                return lead, False

        # Create new lead
        lead = Lead(
            linkedin_url=linkedin_url,
            public_identifier=public_identifier,
            user_id=user_id
        )
        lead.save()
        return lead, True

    @staticmethod
    def get_leads_by_user(user_id: str, limit: Optional[int] = None):
        """Get leads for a user."""
        from .models import Lead

        collection = get_mongodb_collection('leads')
        if collection is None:
            return []

        try:
            query = {"user_id": user_id}
            cursor = collection.find(query).sort("creation_date", DESCENDING)

            if limit:
                cursor = cursor.limit(limit)

            leads = []
            for data in cursor:
                leads.append(Lead.from_dict(data))
            return leads
        except Exception as e:
            logger.error(f"Failed to get leads for user '{user_id}': {e}")
            return []


class NotificationDAL:
    """Notification operations."""

    @staticmethod
    def create_notification(
        recipient_id: str,
        notification_type: str,
        title: str,
        message: str,
        **kwargs
    ):
        """
        Create notification (replaces Django signal helper).
        """
        from .models_extended import Notification

        notification = Notification(
            recipient_id=recipient_id,
            notification_type=notification_type,
            title=title,
            message=message,
            **kwargs
        )
        notification.save()
        return notification

    @staticmethod
    def get_unread(user_id: str, limit: int = 50):
        """Get unread notifications for a user."""
        from .models_extended import Notification

        collection = get_mongodb_collection('notifications')
        if collection is None:
            return []

        try:
            notifications = []
            query = {
                "recipient_id": user_id,
                "is_read": False
            }
            cursor = collection.find(query).sort("created_at", DESCENDING).limit(limit)

            for data in cursor:
                notifications.append(Notification.from_dict(data))
            return notifications
        except Exception as e:
            logger.error(f"Failed to get unread notifications for user '{user_id}': {e}")
            return []

    @staticmethod
    def mark_all_read(user_id: str):
        """Mark all notifications as read for a user."""
        collection = get_mongodb_collection('notifications')
        if collection is None:
            return 0

        try:
            result = collection.update_many(
                {
                    "recipient_id": user_id,
                    "is_read": False
                },
                {"$set": {
                    "is_read": True,
                    "read_at": datetime.now(timezone.utc)
                }}
            )
            return result.modified_count
        except Exception as e:
            logger.error(f"Failed to mark all notifications read for user '{user_id}': {e}")
            return 0


class ActionLogDAL:
    """Action log operations."""

    @staticmethod
    def create(
        linkedin_profile_id: Optional[str],
        campaign_id: str,
        action_type: str,
        details: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        status: str = "",
        error_message: str = "",
        duration_ms: Optional[int] = None
    ):
        """Create an action log entry."""
        from .models_extended import ActionLog

        log = ActionLog(
            linkedin_profile_id=linkedin_profile_id,
            campaign_id=campaign_id,
            action_type=action_type,
            details=details or {},
            user_id=user_id,
            status=status,
            error_message=error_message,
            duration_ms=duration_ms
        )
        log.save()
        return log

    @staticmethod
    def get_daily_count(linkedin_profile_id: str, action_type: str) -> int:
        """Count actions of a specific type today for a profile."""
        collection = get_mongodb_collection('action_logs')
        if collection is None:
            return 0

        midnight = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        try:
            return collection.count_documents({
                "linkedin_profile_id": linkedin_profile_id,
                "action_type": action_type,
                "created_at": {"$gte": midnight}
            })
        except Exception as e:
            logger.error(f"Failed to count daily actions: {e}")
            return 0

    @staticmethod
    def get_campaign_activity(campaign_id: str, limit: int = 100):
        """Get recent activity for a campaign."""
        from .models_extended import ActionLog

        collection = get_mongodb_collection('action_logs')
        if collection is None:
            return []

        try:
            logs = []
            cursor = collection.find(
                {"campaign_id": campaign_id}
            ).sort("created_at", DESCENDING).limit(limit)

            for data in cursor:
                logs.append(ActionLog.from_dict(data))
            return logs
        except Exception as e:
            logger.error(f"Failed to get campaign activity '{campaign_id}': {e}")
            return []


__all__ = [
    'TaskDAL',
    'CampaignDAL',
    'DealDAL',
    'LeadDAL',
    'NotificationDAL',
    'ActionLogDAL',
]
