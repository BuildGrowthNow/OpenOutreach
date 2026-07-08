# openoutreach/core/rate_limit_presets.py
"""Aggressiveness presets for smart rate limiting."""

from __future__ import annotations

AGGRESSIVENESS_PRESETS = {
    "very_slow": {
        "velocity": 10,  # 10 actions/hour = 6 min spacing
        "detectability_multiplier": 0.3,  # very cautious
        "time_aware": True,
        "burst_mode": False,
        "description": "Maximum safety - best for new accounts or high-risk audiences",
        "spacing_desc": "~6 min between actions",
    },
    "slow": {
        "velocity": 15,
        "detectability_multiplier": 0.5,
        "time_aware": True,
        "burst_mode": False,
        "description": "Cautious pacing - good for established accounts",
        "spacing_desc": "~4 min between actions",
    },
    "average": {
        "velocity": 20,
        "detectability_multiplier": 0.7,
        "time_aware": True,
        "burst_mode": False,
        "description": "Balanced approach - recommended for most users",
        "spacing_desc": "~3 min between actions",
    },
    "aggressive": {
        "velocity": 40,
        "detectability_multiplier": 1.0,
        "time_aware": True,
        "burst_mode": True,  # cluster during business hours
        "description": "Fast pacing - for warm audiences and trusted accounts",
        "spacing_desc": "~1-2 min between actions",
    },
    "very_aggressive": {
        "velocity": 60,
        "detectability_multiplier": 1.2,
        "time_aware": True,
        "burst_mode": True,
        "description": "Maximum speed - highest detection risk, use with caution",
        "spacing_desc": "~30-60 sec between actions",
    },
}


def get_preset(preset_name: str) -> dict:
    """Get preset configuration by name, fallback to 'average' if not found."""
    return AGGRESSIVENESS_PRESETS.get(preset_name, AGGRESSIVENESS_PRESETS["average"])
