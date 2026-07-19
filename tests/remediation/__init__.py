"""
Remediation test suite for PLATFORM_REMEDIATION_PLAN.md

These are exit-criteria tests for each phase, confirming that critical user journeys
work end-to-end before moving to the next phase.

Phases:
- Phase 0: Baseline smoke tests (6 critical journeys)
- Phase 1: Auth unification tests (unit + integration)
- Phase 2: API contract alignment tests
- Phase 3+: Feature-specific tests

Run all: pytest tests/remediation/ -v
"""
