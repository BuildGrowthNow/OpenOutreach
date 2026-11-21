"""Email BYO slot accounting (Phase 4).

Phase 4 email is bring-your-own SMTP/IMAP. One seat includes one email slot;
email never uses a browser proxy and no managed mailbox is provisioned.

The slot is counted per workspace. For the Cloud plan the seat pool is the
email pool (one slot per cloud seat). Desktop plans include one slot per
desktop seat, which is the larger of the plan's LinkedIn/WhatsApp account
allowances. Cloud seats are also included when an admin grants them.
"""
from __future__ import annotations

from typing import Any

from openoutreach.organizations.enforcement import EffectivePlan


def email_slot_limit(effective: EffectivePlan) -> int:
    """Return how many BYO mailboxes a workspace may have."""
    if effective.plan == "cloud":
        return max(0, int(effective.cloud_seat_limit or 0))
    return max(
        0,
        int(effective.linkedin_account_limit or 0),
        int(effective.whatsapp_account_limit or 0),
        int(effective.cloud_seat_limit or 0),
    )


def email_slot_usage(effective: EffectivePlan, used: int) -> dict[str, Any]:
    """Serialize slot usage for billing/onboarding surfaces."""
    limit = email_slot_limit(effective)
    used = max(0, int(used or 0))
    return {
        "used": used,
        "limit": limit,
        "remaining": max(0, limit - used),
        "at_limit": limit > 0 and used >= limit,
        "byo": True,
        "managed": False,
        "proxy": False,
    }


__all__ = ["email_slot_limit", "email_slot_usage"]
