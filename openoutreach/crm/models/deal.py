from __future__ import annotations

# Deal enums for CRM

from enum import Enum


class DealState(str, Enum):
    """OpenOutreach-owned funnel state for a Deal.

    OpenOutreach owns these values, not linkedin_cli. The library's connect/status
    verbs only *observe* three of them off the LinkedIn UI — QUALIFIED, PENDING,
    CONNECTED — and hand them back as plain strings over the CLI boundary; every
    other state is written only here: DISCOVERED (initial state for all new leads),
    READY_TO_CONNECT (passed the GP threshold), COMPLETED/FAILED (outcome), and
    NO_EMAIL (enrichment found no address — the deal is held out of the connect pool
    without advancing the LinkedIn state machine). String values match the library's
    UI states so lifting a returned string into this enum is a plain ``DealState(value)``
    lookup at the boundary.

    ALL leads start in DISCOVERED state. AI qualification moves them to QUALIFIED,
    but operators can manually qualify any DISCOVERED lead via UI actions.
    """

    DISCOVERED = "Discovered"
    QUALIFIED = "Qualified"
    READY_TO_CONNECT = "Ready to Connect"
    PENDING = "Pending"
    CONNECTED = "Connected"
    COMPLETED = "Completed"
    FAILED = "Failed"
    NO_EMAIL = "No Email"


class Outcome(str, Enum):
    CONVERTED = "converted"
    NOT_INTERESTED = "not_interested"
    WRONG_FIT = "wrong_fit"
    NO_BUDGET = "no_budget"
    HAS_SOLUTION = "has_solution"
    BAD_TIMING = "bad_timing"
    UNRESPONSIVE = "unresponsive"
    UNKNOWN = "unknown"


# The actual Deal model implementation is in openoutreach.mongodb.models
# Import it from there when needed:
# from openoutreach.mongodb.models import Deal
