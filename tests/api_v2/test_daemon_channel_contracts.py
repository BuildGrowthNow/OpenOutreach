from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from openoutreach.api_v2.daemon_channel_contracts import (
    EmailTaskSnapshot, LinkedInActionReceipt, LinkedInTaskSnapshot,
    MailboxGrant, WhatsAppSyncBatch, WhatsAppTaskSnapshot,
)


def test_linkedin_receipt_is_strict_and_typed():
    receipt = LinkedInActionReceipt(
        action="connect", target_key="lead-1", effect_key="effect-1",
        outcome="already_applied", observed_at=datetime.now(timezone.utc),
    )
    assert receipt.outcome == "already_applied"
    with pytest.raises(ValidationError):
        LinkedInActionReceipt(
            action="connect", target_key="lead-1", effect_key="effect-1",
            outcome="unknown", observed_at=datetime.now(timezone.utc),
        )


def test_whatsapp_sync_is_bounded():
    with pytest.raises(ValidationError):
        WhatsAppSyncBatch(profile_id="p", messages=[{"id": "x"}] * 101)


def test_task_snapshots_reject_extra_fields_and_are_typed():
    snapshot = LinkedInTaskSnapshot(profile_id="p", target_public_identifier="person", effect_key="e")
    assert snapshot.target_public_identifier == "person"
    with pytest.raises(ValidationError):
        LinkedInTaskSnapshot(profile_id="p", target_public_identifier="person", effect_key="e", password="x")
    WhatsAppTaskSnapshot(profile_id="p", effect_key="e")
    EmailTaskSnapshot(profile_id="p", effect_key="e", mailbox_grant=MailboxGrant(
        task_id="t", mailbox_id="m", expires_at=datetime.now(timezone.utc) + timedelta(seconds=30), purpose="send"))
