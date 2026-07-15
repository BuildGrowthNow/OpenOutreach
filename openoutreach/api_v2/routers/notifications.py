"""
Notification endpoints - REST + SSE
Replaces Django notification views with FastAPI implementation.
"""
import json
import asyncio
import logging
from datetime import datetime
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from openoutreach.api_v2.dependencies import get_current_user
from openoutreach.api_v2.schemas.notification import (
    NotificationResponse,
    NotificationListResponse,
    NotificationSummaryResponse,
    NotificationUpdate,
    MarkAllReadResponse,
)
from openoutreach.mongodb.models_extended import Notification
from openoutreach.mongodb.dal import NotificationDAL
from openoutreach.mongodb.connection import get_mongodb_collection

logger = logging.getLogger(__name__)
router = APIRouter()


def _notification_to_response(notification: Notification) -> NotificationResponse:
    """Convert Notification model to response schema."""
    return NotificationResponse(
        _id=notification._id,
        recipient_id=notification.recipient_id,
        notification_type=notification.notification_type,
        title=notification.title,
        message=notification.message,
        campaign_id=notification.campaign_id,
        deal_id=notification.deal_id,
        is_read=notification.is_read,
        read_at=notification.read_at,
        data=notification.data,
        created_at=notification.created_at,
    )


@router.get("/", response_model=NotificationListResponse)
async def list_notifications(
    user_id: str = Depends(get_current_user),
    skip: int = Query(0, ge=0, description="Number of notifications to skip"),
    limit: int = Query(50, ge=1, le=100, description="Number of notifications to return"),
    is_read: Optional[bool] = Query(None, description="Filter by read status"),
    notification_type: Optional[str] = Query(None, description="Filter by type"),
):
    """
    List notifications for the current user with pagination and filtering.

    - **skip**: Number of notifications to skip (pagination)
    - **limit**: Maximum number of notifications to return (max 100)
    - **is_read**: Filter by read status (optional)
    - **notification_type**: Filter by notification type (optional)
    """
    collection = get_mongodb_collection("notifications")
    if collection is None:
        raise HTTPException(status_code=503, detail="Database not available")

    # Build query
    query: Dict[str, Any] = {"recipient_id": user_id}
    if is_read is not None:
        query["is_read"] = is_read
    if notification_type:
        query["notification_type"] = notification_type

    try:
        # Get total count
        total = collection.count_documents(query)

        # Get unread count
        unread_count = collection.count_documents({
            "recipient_id": user_id,
            "is_read": False
        })

        # Get paginated notifications
        cursor = collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
        notifications = []
        for data in cursor:
            notif = Notification.from_dict(data)
            notifications.append(_notification_to_response(notif))

        return NotificationListResponse(
            notifications=notifications,
            total=total,
            unread_count=unread_count,
        )
    except Exception as e:
        logger.error(f"Failed to list notifications: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve notifications")


@router.get("/summary", response_model=NotificationSummaryResponse)
async def get_notification_summary(
    user_id: str = Depends(get_current_user),
):
    """
    Get notification summary: unread count + last 10 notifications.
    Useful for notification bell/badge UI elements.
    """
    collection = get_mongodb_collection("notifications")
    if collection is None:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        # Get unread count
        unread_count = Notification.get_unread_count(user_id)

        # Get last 10 notifications
        cursor = collection.find({"recipient_id": user_id}).sort("created_at", -1).limit(10)
        recent_notifications = []
        for data in cursor:
            notif = Notification.from_dict(data)
            recent_notifications.append(_notification_to_response(notif))

        return NotificationSummaryResponse(
            unread_count=unread_count,
            recent_notifications=recent_notifications,
        )
    except Exception as e:
        logger.error(f"Failed to get notification summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve summary")


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(
    notification_id: str,
    user_id: str = Depends(get_current_user),
):
    """
    Get a single notification by ID.
    Returns 404 if notification doesn't exist or user doesn't own it.
    """
    notification = Notification.get(notification_id)

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    # Verify ownership
    if notification.recipient_id != user_id:
        raise HTTPException(status_code=404, detail="Notification not found")

    return _notification_to_response(notification)


@router.patch("/{notification_id}", response_model=NotificationResponse)
async def update_notification(
    notification_id: str,
    update_data: NotificationUpdate,
    user_id: str = Depends(get_current_user),
):
    """
    Update a notification (typically to mark as read).
    Returns 404 if notification doesn't exist or user doesn't own it.
    """
    notification = Notification.get(notification_id)

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    # Verify ownership
    if notification.recipient_id != user_id:
        raise HTTPException(status_code=404, detail="Notification not found")

    # Update fields
    if update_data.is_read is not None:
        if update_data.is_read:
            notification.mark_as_read()
        else:
            notification.is_read = False
            notification.read_at = None
            notification.save()

    return _notification_to_response(notification)


@router.post("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: str,
    user_id: str = Depends(get_current_user),
):
    """
    Mark a single notification as read.
    Convenience endpoint that's equivalent to PATCH with is_read=true.
    """
    notification = Notification.get(notification_id)

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    # Verify ownership
    if notification.recipient_id != user_id:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.mark_as_read()

    return _notification_to_response(notification)


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    user_id: str = Depends(get_current_user),
):
    """
    Delete a notification.
    Returns 404 if notification doesn't exist or user doesn't own it.
    """
    notification = Notification.get(notification_id)

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    # Verify ownership
    if notification.recipient_id != user_id:
        raise HTTPException(status_code=404, detail="Notification not found")

    success = Notification.delete(notification_id)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete notification")

    return {"message": "Notification deleted successfully"}


@router.post("/read-all", response_model=MarkAllReadResponse)
async def mark_all_notifications_read(
    user_id: str = Depends(get_current_user),
):
    """
    Mark all notifications as read for the current user.
    Returns the count of notifications marked as read.
    """
    marked_count = NotificationDAL.mark_all_read(user_id)

    return MarkAllReadResponse(
        marked_count=marked_count,
        message=f"Marked {marked_count} notification(s) as read",
    )


@router.get("/sse/")
async def sse_notification_stream(
    request: Request,
    user_id: str = Depends(get_current_user),
):
    """
    Server-Sent Events endpoint for notifications (browser fallback).
    Replaces Django StreamingHttpResponse SSE fallback.

    The client can connect to this endpoint to receive notifications
    in real-time without WebSocket support. This is a fallback for
    environments where WebSocket connections are not available.

    Usage:
        const eventSource = new EventSource('/api/notifications/sse/');
        eventSource.onmessage = (event) => {
            const notification = JSON.parse(event.data);
            console.log('New notification:', notification);
        };
    """
    async def event_generator() -> AsyncIterator[str]:
        """Generate SSE events for new notifications."""
        # Send initial connection confirmation
        yield f"data: {json.dumps({'type': 'connected', 'user_id': user_id, 'timestamp': datetime.utcnow().isoformat()})}\n\n"

        collection = get_mongodb_collection("notifications")
        if collection is None:
            logger.error("Database not available for SSE stream")
            return

        # Track last check time
        last_check = datetime.utcnow()

        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info(f"SSE client disconnected for user {user_id}")
                    break

                # Poll for new notifications every 5 seconds
                await asyncio.sleep(5)

                # Find new notifications since last check
                try:
                    new_notifs = list(collection.find({
                        "recipient_id": user_id,
                        "created_at": {"$gt": last_check},
                    }).sort("created_at", -1).limit(10))

                    # Send each new notification as an event
                    for notif_data in new_notifs:
                        notif = Notification.from_dict(notif_data)
                        notification_dict = _notification_to_response(notif).model_dump(mode='json')
                        yield f"data: {json.dumps({'type': 'notification', 'notification': notification_dict, 'timestamp': datetime.utcnow().isoformat()})}\n\n"

                    last_check = datetime.utcnow()

                    # Send keepalive comment
                    yield ": keepalive\n\n"

                except Exception as e:
                    logger.error(f"Error polling notifications for user {user_id}: {e}")
                    # Continue polling despite errors

        except asyncio.CancelledError:
            logger.info(f"SSE stream cancelled for user {user_id}")
        except Exception as e:
            logger.error(f"SSE stream error for user {user_id}: {e}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )
