"""
WebSocket Router - Real-time notifications and campaign status
"""
import asyncio
import json
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
from typing import Dict, Set
import logging

from openoutreach.mongodb import models

logger = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    """
    Manages WebSocket connections for real-time updates.
    In-memory for single-process; use Redis pub/sub for multi-process deployments.
    """

    def __init__(self):
        # user_id -> set of WebSocket connections
        self.user_connections: Dict[str, Set[WebSocket]] = {}
        # campaign_id -> set of WebSocket connections
        self.campaign_connections: Dict[str, Set[WebSocket]] = {}

    async def connect_user(self, websocket: WebSocket, user_id: str):
        """Connect a user to their notification stream."""
        await websocket.accept()
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(websocket)
        logger.info(f"User {user_id} connected to notifications")

    async def connect_campaign(self, websocket: WebSocket, campaign_id: str):
        """Connect to a campaign status stream."""
        await websocket.accept()
        if campaign_id not in self.campaign_connections:
            self.campaign_connections[campaign_id] = set()
        self.campaign_connections[campaign_id].add(websocket)
        logger.info(f"Campaign {campaign_id} connection added")

    async def disconnect_user(self, websocket: WebSocket, user_id: str):
        """Disconnect user from notification stream."""
        self.user_connections.get(user_id, set()).discard(websocket)
        logger.info(f"User {user_id} disconnected from notifications")

    async def disconnect_campaign(self, websocket: WebSocket, campaign_id: str):
        """Disconnect from campaign status stream."""
        self.campaign_connections.get(campaign_id, set()).discard(websocket)
        logger.info(f"Campaign {campaign_id} connection removed")

    async def send_to_user(self, user_id: str, data: dict):
        """Send data to all connections for a user."""
        connections = self.user_connections.get(user_id, set())
        dead = set()
        for ws in connections:
            try:
                await ws.send_json(data)
            except Exception as e:
                logger.warning(f"Failed to send to user {user_id}: {e}")
                dead.add(ws)
        connections -= dead

    async def send_to_campaign(self, campaign_id: str, data: dict):
        """Send data to all connections for a campaign."""
        connections = self.campaign_connections.get(campaign_id, set())
        dead = set()
        for ws in connections:
            try:
                await ws.send_json(data)
            except Exception as e:
                logger.warning(f"Failed to send to campaign {campaign_id}: {e}")
                dead.add(ws)
        connections -= dead


# Global connection manager
manager = ConnectionManager()


@router.websocket("/ws/notifications/")
async def notification_websocket(websocket: WebSocket, token: str = Query(...)):
    """
    WebSocket endpoint for user notifications.
    Replaces Django NotificationConsumer.

    Connect: ws://host/ws/notifications/?token=<jwt>
    Receives: notification_message, notification_broadcast
    Sends: ping → pong, mark_read → ack
    """
    # Authenticate
    from openoutreach.api_v2.dependencies import get_current_user
    from fastapi.security import HTTPAuthorizationCredentials

    try:
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        user_id = await get_current_user(creds)
    except Exception as e:
        logger.warning(f"WebSocket auth failed: {e}")
        await websocket.close(code=4001)
        return

    await manager.connect_user(websocket, user_id)
    await websocket.send_json({"type": "connected", "user_id": user_id})

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            elif msg_type == "mark_read":
                notification_id = data.get("notification_id")
                if notification_id:
                    notif = models.Notification.get(notification_id)
                    if notif and notif.recipient_id == user_id:
                        notif.mark_as_read()
                        await websocket.send_json({
                            "type": "mark_read_ack",
                            "notification_id": notification_id
                        })
    except WebSocketDisconnect:
        await manager.disconnect_user(websocket, user_id)
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
        await manager.disconnect_user(websocket, user_id)


@router.websocket("/ws/campaigns/{campaign_id}/")
async def campaign_status_websocket(
    websocket: WebSocket,
    campaign_id: str,
    token: str = Query(...)
):
    """
    WebSocket endpoint for campaign status updates.
    Replaces Django CampaignStatusConsumer.

    Connect: ws://host/ws/campaigns/<id>/?token=<jwt>
    Receives: campaign_status_update, campaign_error
    """
    # Authenticate
    from openoutreach.api_v2.dependencies import get_current_user
    from fastapi.security import HTTPAuthorizationCredentials

    try:
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        user_id = await get_current_user(creds)
    except Exception as e:
        logger.warning(f"WebSocket auth failed: {e}")
        await websocket.close(code=4001)
        return

    # Verify user has access to this campaign
    campaign = models.Campaign.get(campaign_id)
    if not campaign or campaign.user_id != user_id:
        await websocket.close(code=4003)
        return

    await manager.connect_campaign(websocket, campaign_id)
    await websocket.send_json({"type": "connected", "campaign_id": campaign_id})

    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        await manager.disconnect_campaign(websocket, campaign_id)
    except Exception as e:
        logger.error(f"WebSocket error for campaign {campaign_id}: {e}")
        await manager.disconnect_campaign(websocket, campaign_id)


# === Emit helper functions (called from services/daemon) ===

async def emit_notification_to_user(user_id: str, notification_data: dict):
    """Send notification to user via WebSocket (replaces Django Channels emit)."""
    await manager.send_to_user(user_id, {
        "type": "notification_message",
        "data": {**notification_data, "timestamp": datetime.utcnow().isoformat()},
    })


async def emit_campaign_status_update(campaign_id: str, status: str, message: str = None):
    """Send campaign status update via WebSocket."""
    data = {
        "type": "campaign_status_update",
        "data": {
            "campaign_id": campaign_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
        }
    }
    if message:
        data["data"]["message"] = message
    await manager.send_to_campaign(campaign_id, data)


async def emit_campaign_error(campaign_id: str, error_message: str, deal_id: str = None):
    """Send campaign error via WebSocket."""
    data = {
        "type": "campaign_error",
        "data": {
            "campaign_id": campaign_id,
            "error_message": error_message,
            "timestamp": datetime.utcnow().isoformat(),
        }
    }
    if deal_id:
        data["data"]["deal_id"] = deal_id
    await manager.send_to_campaign(campaign_id, data)
