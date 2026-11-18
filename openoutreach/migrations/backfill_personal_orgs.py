"""Backfill personal organizations and org ownership on existing records.

Additive and idempotent. Run the dry-run first:

    python -m openoutreach.migrations.backfill_personal_orgs
    python -m openoutreach.migrations.backfill_personal_orgs --apply

This migration never deletes data. It creates one personal organization per
user, links ``User.org_id``, creates the owner membership row, and backfills
``org_id`` / ``assigned_user_id`` on LinkedIn profiles and ``org_id`` on
campaigns.
"""
from __future__ import annotations

import argparse
import json
import logging

from openoutreach.mongodb.connection import initialize_mongodb_connection
from openoutreach.organizations.service import backfill_personal_orgs

logger = logging.getLogger(__name__)


def run(*, apply: bool = False) -> dict[str, int]:
    initialize_mongodb_connection()
    summary = backfill_personal_orgs(dry_run=not apply)
    logger.info(
        "personal_org_backfill_complete apply=%s summary=%s",
        apply,
        summary,
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
