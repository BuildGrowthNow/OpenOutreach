# openoutreach/linkedin/services/state_machine_stub.py
"""State Machine Engine stub - Feature is disabled.

The state machine feature is incomplete and disabled via the
NEXT_PUBLIC_ENABLE_STATE_MACHINE feature flag. This stub file
maintains the import structure for any legacy references.
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class StateMachineEngine:
    """Stub for state machine engine - feature is disabled."""

    def __init__(self, state_graph):
        self.state_graph = state_graph
        logger.warning(
            "State machine feature is disabled. StateMachineEngine is a stub."
        )

    def execute_step(self, state_machine, session=None) -> Tuple[bool, str]:
        """Stub method - state machine is disabled."""
        logger.warning("State machine execution attempted but feature is disabled")
        return False, "State machine feature is disabled"


# For backward compatibility
def get_engine(state_graph):
    """Get a state machine engine (stub)."""
    return StateMachineEngine(state_graph)
