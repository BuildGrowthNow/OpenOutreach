# openoutreach/api_v2/routers/mailboxes.py
"""Mailbox CRUD — add/test/list/delete SMTP sending inboxes."""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from openoutreach.api_v2.dependencies_v2 import get_current_user
from openoutreach.emails.models import Mailbox
from openoutreach.emails.smtp import verify_auth

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────


class MailboxCreate(BaseModel):
    host: str = "smtp.gmail.com"
    port: int = 587
    username: str
    password: str
    from_address: str = ""
    from_name: str = ""
    daily_limit: int = 40
    imap_host: str = ""
    imap_port: int = 993


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
    paused: bool


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
        paused=box.paused,
    )


# ── Endpoints ─────────────────────────────────────────────────────


@router.get("", response_model=List[MailboxResponse])
async def list_mailboxes(user_id: str = Depends(get_current_user)):
    return [_to_response(b) for b in Mailbox.objects.all(user_id=user_id)]


@router.post("/test", response_model=MailboxTestResponse)
async def test_mailbox(data: MailboxTestRequest, _: str = Depends(get_current_user)):
    ok, message = verify_auth(data.host, data.port, data.username, data.password)
    return MailboxTestResponse(ok=ok, message=message)


@router.post("", response_model=MailboxResponse, status_code=status.HTTP_201_CREATED)
async def create_mailbox(data: MailboxCreate, user_id: str = Depends(get_current_user)):
    ok, message = verify_auth(data.host, data.port, data.username, data.password)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    from_address = data.from_address or data.username
    box = Mailbox(
        host=data.host,
        port=data.port,
        username=data.username,
        password=data.password,
        from_address=from_address,
        from_name=data.from_name,
        daily_limit=data.daily_limit,
        user_id=user_id,
        imap_host=data.imap_host,
        imap_port=data.imap_port,
    )
    box.save()
    logger.info("mailboxes: created %s for user %s", from_address, user_id)
    return _to_response(box)


@router.patch("/{mailbox_id}/unpause", response_model=MailboxResponse)
async def unpause_mailbox(mailbox_id: str, user_id: str = Depends(get_current_user)):
    """Clear the paused flag set by auth-failure error handling."""
    box = Mailbox.get(mailbox_id)
    if not box:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found")
    if box.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    box.paused = False
    box.save()
    logger.info("mailboxes: unpaused %s for user %s", box.from_address, user_id)
    return _to_response(box)


@router.delete("/{mailbox_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mailbox(mailbox_id: str, user_id: str = Depends(get_current_user)):
    box = Mailbox.get(mailbox_id)
    if not box:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found")
    if box.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    Mailbox.delete(mailbox_id)
    logger.info("mailboxes: deleted %s for user %s", mailbox_id, user_id)
    return None
