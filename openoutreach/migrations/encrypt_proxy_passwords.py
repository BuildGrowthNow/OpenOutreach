"""
Migration: Encrypt plaintext proxy passwords on LinkedInProfile documents.

Existing profiles store ``proxy_password`` as plaintext. This migration moves
each value into ``proxy_password_encrypted`` and removes the plaintext field.
It is idempotent and never logs credential values.

Dry run (default):
    python -m openoutreach.migrations.encrypt_proxy_passwords

Apply:
    python -m openoutreach.migrations.encrypt_proxy_passwords --apply
"""
import argparse
import logging

from openoutreach.mongodb.connection import (
    get_mongodb_collection,
    initialize_mongodb_connection,
)
from openoutreach.mongodb.crypto import decrypt_text, encrypt_text, is_encrypted

logger = logging.getLogger(__name__)


def migrate_proxy_passwords(dry_run: bool = True) -> bool:
    """Encrypt plaintext proxy passwords and remove the plaintext column."""
    logger.info("Starting proxy password encryption migration (dry_run=%s)...", dry_run)

    if not initialize_mongodb_connection():
        logger.error("Failed to connect to MongoDB")
        return False

    collection = get_mongodb_collection("linkedin_profiles")
    if collection is None:
        logger.error("Could not access linkedin_profiles collection")
        return False

    query = {"proxy_password": {"$exists": True, "$nin": [None, ""]}}
    total = collection.count_documents(query)
    if total == 0:
        logger.info("No plaintext proxy passwords to migrate.")
        return True

    logger.info("Found %s profiles with plaintext proxy passwords", total)

    migrated = 0
    failed = 0
    for doc in collection.find(
        query,
        {"_id": 1, "proxy_password": 1, "proxy_password_encrypted": 1},
    ):
        plaintext = doc.get("proxy_password")
        if not plaintext:
            continue

        try:
            existing_encrypted = doc.get("proxy_password_encrypted")
            if existing_encrypted and is_encrypted(existing_encrypted):
                # A valid encrypted value is authoritative; the plaintext field
                # is the legacy duplicate this migration is removing.
                encrypted = existing_encrypted
                try:
                    decrypt_text(encrypted)
                except Exception:
                    logger.warning(
                        "Encrypted proxy password could not be decrypted for profile %s; "
                        "re-encrypting the plaintext value",
                        doc["_id"],
                    )
                    encrypted = encrypt_text(plaintext)
            else:
                if existing_encrypted:
                    logger.warning(
                        "proxy_password_encrypted was not encrypted for profile %s; "
                        "replacing it with an encrypted value",
                        doc["_id"],
                    )
                encrypted = plaintext if is_encrypted(plaintext) else encrypt_text(plaintext)

            if not dry_run:
                collection.update_one(
                    {"_id": doc["_id"]},
                    {
                        "$set": {"proxy_password_encrypted": encrypted},
                        "$unset": {"proxy_password": ""},
                    },
                )
            migrated += 1
        except Exception as e:
            failed += 1
            logger.error(
                "Failed to encrypt proxy password for profile %s: %s",
                doc["_id"],
                type(e).__name__,
            )

    logger.info("Migration complete: %s migrated, %s failed", migrated, failed)

    if not dry_run:
        remaining = collection.count_documents(query)
        if remaining > 0:
            logger.warning(
                "Migration incomplete: %s profiles still have plaintext proxy passwords",
                remaining,
            )
            return False
        logger.info("All proxy passwords are encrypted at rest.")

    return failed == 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Encrypt plaintext LinkedIn proxy passwords"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the migration; without this flag it only reports what would change",
    )
    args = parser.parse_args()

    from openoutreach.core.logging import RedactingFormatter

    handler = logging.StreamHandler()
    handler.setFormatter(
        RedactingFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    logging.basicConfig(level=logging.INFO, handlers=[handler])

    return 0 if migrate_proxy_passwords(dry_run=not args.apply) else 1


if __name__ == "__main__":
    raise SystemExit(main())
