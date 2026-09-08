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
the sequence before saving edits. This protects in-progress deals until full
immutable per-lead sequence revisions are introduced.

Template and campaign link APIs are tenant-scoped. Links referenced by an
active sequence are deactivated rather than hard-deleted, preserving event
history. The tracking Worker rollout remains separate from API/web deployment.
