# openoutreach/whatsapp/warmup.py
"""WhatsApp number warmup — computes effective daily send limit based on profile age.

New WA numbers that blast at full velocity on day 1 get banned. This module
enforces a ramp: day 1→20, day 7→60, day 30+→max_limit (configured ceiling).
Linear interpolation is used between breakpoints.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

# (age_days, limit) breakpoints — linear interpolation between them
_WARMUP_CURVE = [
    (0, 20),
    (7, 60),
    (30, 150),
]


def effective_wa_daily_limit(
    profile_created_at: Optional[datetime],
    max_limit: int,
) -> int:
    """Return the effective daily WA send limit for a profile at its current age.

    profile_created_at: UTC datetime of WhatsAppProfile.created_at.
    max_limit: the operator-configured ceiling (SiteConfig.wa_daily_limit).

    Returns min(warmup_value, max_limit) so the configured ceiling still caps
    the curve (useful for operators who want conservative ramp-up).
    If max_limit is 0 or negative, 20 is used as the floor.
    """
    if profile_created_at is None:
        return min(20, max(max_limit, 20))

    now = datetime.now(timezone.utc)
    if profile_created_at.tzinfo is None:
        profile_created_at = profile_created_at.replace(tzinfo=timezone.utc)

    age_days = (now - profile_created_at).days
    warmup_value = _interpolate_limit(age_days)

    # Honour the operator ceiling, but never go below 1
    effective_max = max(max_limit, 1)
    return min(warmup_value, effective_max)


def _interpolate_limit(age_days: int) -> int:
    """Linear interpolation across _WARMUP_CURVE breakpoints."""
    if age_days <= _WARMUP_CURVE[0][0]:
        return _WARMUP_CURVE[0][1]

    for i in range(1, len(_WARMUP_CURVE)):
        prev_age, prev_limit = _WARMUP_CURVE[i - 1]
        curr_age, curr_limit = _WARMUP_CURVE[i]
        if age_days <= curr_age:
            t = (age_days - prev_age) / (curr_age - prev_age)
            return int(prev_limit + t * (curr_limit - prev_limit))

    return _WARMUP_CURVE[-1][1]
