"""Reconcile the unified cloud seat counter from real database rows.

Additive and idempotent. Dry-run by default:

    python -m openoutreach.migrations.reconcile_cloud_seats
    python -m openoutreach.migrations.reconcile_cloud_seats --apply

The migration never deletes or changes profile, proxy, or billing data. It
counts cloud LinkedIn (credentialed) and cloud WhatsApp browser accounts, pairs
a Cloud Duo WhatsApp number with its LinkedIn unit, and writes the counter for
each accounting owner.
"""
from __future__ import annotations

import argparse
import json
import logging

from openoutreach.billing.cloud_seats import reconcile_all_cloud_seat_usage
from openoutreach.mongodb.connection import initialize_mongodb_connection

logger = logging.getLogger(__name__)


def run(*, apply: bool = False) -> dict:
    initialize_mongodb_connection()
    summary = reconcile_all_cloud_seat_usage(dry_run=not apply)
    logger.info(
        "cloud_seat_reconciliation_complete apply=%s scopes=%s changed=%s",
        apply,
        summary.get("scopes"),
        summary.get("changed"),
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist changes. Without this flag the migration is a dry-run.",
    )
    args = parser.parse_args()
    summary = run(apply=args.apply)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
