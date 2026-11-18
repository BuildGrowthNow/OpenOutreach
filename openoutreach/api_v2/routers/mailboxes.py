# openoutreach/api_v2/routers/mailboxes.py
"""Mailbox CRUD — add/test/list/delete SMTP sending inboxes."""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from openoutreach.api_v2.dependencies_v2 import get_current_user
from openoutreach.emails.models import Mailbox
from openoutreach.emails.smtp import verify_auth, verify_imap_auth
from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.mongodb.models_user import User
from openoutreach.organizations.access import (
    can_access_channel_doc,
    channel_access_query,
    resolve_org_context,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────


class MailboxCreate(BaseModel):
    host: str = "smtp.gmail.com"
    port: int = Field(default=587, ge=1, le=65535)
    username: str
    password: str
    from_address: str = ""
    from_name: str = ""
    daily_limit: int = Field(default=40, ge=1, le=2000)
    imap_host: str = ""
    imap_port: int = Field(default=993, ge=1, le=65535)
    imap_username: str = ""
    imap_password: str = ""


class MailboxUpdate(BaseModel):
    from_name: str | None = None
    daily_limit: int | None = Field(default=None, ge=1, le=2000)
    imap_host: str | None = None
    imap_port: int | None = Field(default=None, ge=1, le=65535)
    imap_username: str | None = None
    imap_password: str | None = None
    password: str | None = None


class MailboxTestRequest(BaseModel):
    host: str = "smtp.gmail.com"
    port: int = 587
    username: str
    password: str


class MailboxResponse(BaseModel):
    id: str
    host: str
    port: int
    username: str
    from_address: str
    from_name: str
    daily_limit: int
    headroom_today: int
    sent_today: int
    imap_host: str
    imap_port: int
    imap_username: str
    paused: bool
    org_id: str | None = None
    assigned_user_id: str | None = None
    seat_id: str | None = None
    managed: bool = False


class MailboxTestResponse(BaseModel):
    ok: bool
    message: str


def _to_response(box: Mailbox) -> MailboxResponse:
    return MailboxResponse(
        id=box._id,
        host=box.host,
        port=box.port,
        username=box.username,
        from_address=box.from_address,
        from_name=box.from_name,
        daily_limit=box.daily_limit,
        headroom_today=box.headroom_today(),
        sent_today=box.sent_today(),
        imap_host=box.imap_host,
        imap_port=box.imap_port,
        imap_username=box.imap_username,
        paused=box.paused,
        org_id=box.org_id,
        assigned_user_id=box.assigned_user_id,
        seat_id=box.seat_id,
        managed=box.managed,
    )


def _authorized_mailbox(mailbox_id: str, user_id: str) -> Mailbox:
    user = User.get(user_id)
    box = Mailbox.get(mailbox_id)
    if user is None or box is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found")
    if not can_access_channel_doc(user, box.to_dict()):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found")
    return box


# ── Endpoints ─────────────────────────────────────────────────────


@router.get("", response_model=List[MailboxResponse])
async def list_mailboxes(user_id: str = Depends(get_current_user)):
    user = User.get(user_id)
    collection = get_mongodb_collection("mailboxes")
    if user is None or collection is None:
        return []
    return [
        _to_response(Mailbox.from_dict(doc))
        for doc in collection.find(channel_access_query(user))
    ]


@router.post("/test", response_model=MailboxTestResponse)
async def test_mailbox(data: MailboxTestRequest, _: str = Depends(get_current_user)):
    ok, message = verify_auth(data.host, data.port, data.username, data.password)
    return MailboxTestResponse(ok=ok, message=message)


@router.post("", response_model=MailboxResponse, status_code=status.HTTP_201_CREATED)
async def create_mailbox(data: MailboxCreate, user_id: str = Depends(get_current_user)):
    ok, message = verify_auth(data.host, data.port, data.username, data.password)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    if data.imap_host:
        imap_ok, imap_message = verify_imap_auth(
            data.imap_host, data.imap_port, data.imap_username or data.username,
            data.imap_password or data.password,
        )
        if not imap_ok:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=imap_message)

    user = User.get(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    ctx = resolve_org_context(user)

    existing = Mailbox.find_by_username(data.username)
    if existing and (
        existing.org_id == ctx.org_id or existing.user_id == user_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Mailbox for {data.username} already exists",
        )

    from_address = data.from_address or data.username
    box = Mailbox(
        host=data.host,
        port=data.port,
        username=data.username,
        password=data.password,
        from_address=from_address,
        from_name=data.from_name,
        daily_limit=data.daily_limit,
        # The workspace owner is the accounting/data owner; the creator keeps
        # the assignment so members see only their own mailboxes.
        user_id=ctx.accounting_owner_id,
        org_id=ctx.org_id,
        assigned_user_id=user_id,
        imap_host=data.imap_host,
        imap_port=data.imap_port,
        imap_username=data.imap_username,
        imap_password=data.imap_password,
    )
    box.save()
    logger.info("mailboxes: created %s for user %s", from_address, user_id)
    return _to_response(box)


@router.patch("/{mailbox_id}", response_model=MailboxResponse)
async def update_mailbox(mailbox_id: str, data: MailboxUpdate, user_id: str = Depends(get_current_user)):
    box = _authorized_mailbox(mailbox_id, user_id)
    if data.from_name is not None:
        box.from_name = data.from_name
    if data.daily_limit is not None:
        box.daily_limit = data.daily_limit
    if data.imap_host is not None:
        box.imap_host = data.imap_host
    if data.imap_port is not None:
        box.imap_port = data.imap_port
    if data.imap_username is not None:
        box.imap_username = data.imap_username
    if data.imap_password is not None:
        box.imap_password = data.imap_password
    if data.password is not None:
        if data.password:
            ok, message = verify_auth(box.host, box.port, box.username, data.password)
            if not ok:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
        box.password = data.password
    if box.imap_host:
        imap_ok, imap_message = verify_imap_auth(
            box.imap_host, box.imap_port, box.imap_username or box.username,
            box.imap_password,
        )
        if not imap_ok:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=imap_message)
    box.save()
    logger.info("mailboxes: updated %s for user %s", box.from_address, user_id)
    return _to_response(box)


@router.patch("/{mailbox_id}/unpause", response_model=MailboxResponse)
async def unpause_mailbox(mailbox_id: str, user_id: str = Depends(get_current_user)):
    """Clear the paused flag set by auth-failure error handling."""
    box = _authorized_mailbox(mailbox_id, user_id)
    box.paused = False
    box.save()
    logger.info("mailboxes: unpaused %s for user %s", box.from_address, user_id)
    return _to_response(box)


@router.delete("/{mailbox_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mailbox(mailbox_id: str, user_id: str = Depends(get_current_user)):
    box = _authorized_mailbox(mailbox_id, user_id)
    Mailbox.delete(box._id)
    logger.info("mailboxes: deleted %s for user %s", mailbox_id, user_id)
    return None
