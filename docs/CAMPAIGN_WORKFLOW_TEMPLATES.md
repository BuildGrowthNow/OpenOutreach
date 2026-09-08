# Campaign workflow templates

Campaign workflows are stored in `Campaign.sequence_steps` and
`Campaign.sequence_edges`, validated by `openoutreach/core/sequence_schema.py`,
and executed by `openoutreach/core/sequence_executor.py`.

Templates are reusable, versioned blueprints in the existing
`campaign_templates` collection. They contain logical link references such as
`{{link.demo}}`, never recipient-specific tracking URLs, credentials, sessions,
deals, leads, or historical analytics. Creating a campaign from a template
copies the graph and records an immutable `template_snapshot` plus the source
template ID/version.

New campaigns are drafts. The campaign Sequence tab must be reviewed before
activation. While a sequence is active, graph edits are rejected; deactivate
the sequence before saving edits. Each lead retains an immutable graph snapshot,
so reactivation safely resumes an in-progress lead on its original workflow.

Template and campaign link APIs are tenant-scoped. Links referenced by an
active sequence are deactivated rather than hard-deleted, preserving event
history. The tracking Worker rollout remains separate from API/web deployment.

## Daemon channel enablement

Task claiming is deliberately closed by default. A production operator must
explicitly configure `DAEMON_TASK_CLAIM_ENABLED=true` and enable each intended
channel with `DAEMON_V2_LINKEDIN_ENABLED`, `DAEMON_V2_WHATSAPP_ENABLED`, and
`DAEMON_V2_EMAIL_ENABLED`. The authenticated daemon compatibility endpoint
advertises only the channels currently enabled. Do not enable a channel merely
because a sequence can be edited for it: confirm its profile/mailbox, Worker,
and operational runbook first. These settings are deployment secrets/config and
are not changed by application releases.
