"""
WebSocket Router - Real-time notifications and campaign status
"""
from datetime import datetime, timezone as _tz
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Optional, Set
import logging

from openoutreach.mongodb import models
from openoutreach.mongodb.models_extended import Notification

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


async def _ws_authenticate(websocket: WebSocket) -> Optional[str]:
    """Accept the connection, wait for first auth message, return user_id or None.

    Client must send {"type": "auth", "token": "<jwt>"} as the first message.
    Closes with code 4001 on failure and returns None.
    """
    from openoutreach.api_v2.dependencies_v2 import get_current_user
    from fastapi.security import HTTPAuthorizationCredentials

    await websocket.accept()
    try:
        first = await websocket.receive_json()
    except Exception:
        await websocket.close(code=4001)
        return None

    if first.get("type") != "auth" or not first.get("token"):
        await websocket.close(code=4001)
        return None

    try:
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=first["token"])
        return await get_current_user(creds)
    except Exception as e:
        logger.warning(f"WebSocket auth failed: {e}")
        await websocket.close(code=4001)
        return None


@router.websocket("/ws/notifications/")
async def notification_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for user notifications.

    Connect: ws://host/ws/notifications/
    First message must be: {"type": "auth", "token": "<jwt>"}
    Then: ping → pong, mark_read → mark_read_ack
    """
    user_id = await _ws_authenticate(websocket)
    if user_id is None:
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
                    notif = Notification.get(notification_id)
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
async def campaign_status_websocket(websocket: WebSocket, campaign_id: str):
    """
    WebSocket endpoint for campaign status updates.

    Connect: ws://host/ws/campaigns/<id>/
    First message must be: {"type": "auth", "token": "<jwt>"}
    """
    user_id = await _ws_authenticate(websocket)
    if user_id is None:
        return

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
        "data": {**notification_data, "timestamp": datetime.now(_tz.utc).isoformat()},
    })


async def emit_campaign_status_update(campaign_id: str, status: str, message: Optional[str] = None):
    """Send campaign status update via WebSocket."""
    data = {
        "type": "campaign_status_update",
        "data": {
            "campaign_id": campaign_id,
            "status": status,
            "timestamp": datetime.now(_tz.utc).isoformat(),
        }
    }
    if message:
        data["data"]["message"] = message
    await manager.send_to_campaign(campaign_id, data)


async def emit_campaign_error(campaign_id: str, error_message: str, deal_id: Optional[str] = None):
    """Send campaign error via WebSocket."""
    data = {
        "type": "campaign_error",
        "data": {
            "campaign_id": campaign_id,
            "error_message": error_message,
            "timestamp": datetime.now(_tz.utc).isoformat(),
        }
    }
    if deal_id:
        data["data"]["deal_id"] = deal_id
    await manager.send_to_campaign(campaign_id, data)
