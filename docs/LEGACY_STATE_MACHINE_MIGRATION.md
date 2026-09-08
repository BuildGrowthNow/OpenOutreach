# Retired state-machine migration

The legacy state-machine API, models, and execution service have been removed.
Campaign sequences are the only supported workflow runtime. These scripts are
retained solely to audit and explicitly migrate existing legacy MongoDB data;
they do not expose or reactivate the retired feature.

`scripts/audit_legacy_state_machine.py` is read-only and reports collection
counts without documents. `scripts/migrate_legacy_state_machine.py` is also
read-only by default. Review and archive its JSON report before running with
`--apply`.

The apply mode is idempotent: it only writes campaigns with an empty canonical
sequence, validates the translated graph first, keeps campaigns inactive, and
never drops or alters legacy collections. Rollback is to restore the affected
campaign documents from the pre-migration backup, or unset the canonical
sequence fields after operator review; do not delete the legacy collections
until migration verification and an explicit approval are complete.
