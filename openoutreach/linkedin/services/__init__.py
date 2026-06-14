# openoutreach/linkedin/services/__init__.py
"""LinkedIn services for various campaign automations."""

from __future__ import annotations

# Import service modules
from . import ghost_mode
from . import health_monitor
from . import state_machine

# Export classes/functions that may be used elsewhere
from .ghost_mode import GhostModeInterceptor
from .health_monitor import CampaignHealthMonitor, run_health_check_for_campaign, create_hourly_health_metric
from .state_machine import (
    StateMachineEngine,
    validate_state_graph,
    simulate_state_machine,
)

__all__ = [
    # Ghost mode
    'GhostModeInterceptor',
    # Health monitor
    'CampaignHealthMonitor',
    'run_health_check_for_campaign',
    'create_hourly_health_metric',
    # State machine
    'StateMachineEngine',
    'validate_state_graph',
    'simulate_state_machine',
]