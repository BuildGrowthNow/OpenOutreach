from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from openoutreach.api_v2.daemon_channel_contracts import LinkedInActionReceipt, WhatsAppSyncBatch


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
