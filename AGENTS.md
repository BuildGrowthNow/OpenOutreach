# Agent operations

## Production access

- Production runs in Scalingo project `outreach` (region `osc-fr1`). Use the authenticated Scalingo CLI; never commit or print environment values.
- Apps: `outreach-web` (Next.js) and `outreach-api` (FastAPI plus the single `daemon` process).
- The server daemon is cloud-only: it selects profiles with `execution_mode="cloud"`; desktop-enrolled profiles stay owned by the desktop daemon.
- Public URLs: `https://outreach.lengrowth.com`, `https://outreach-api.lengrowth.com`, and the existing tracking Worker `https://track.lengrowth.com`.
- MongoDB Atlas remains the production database. Do not create a staging database or change the tracking Worker during routine deployments.
- Cloudflare DNS routes the two `outreach` hostnames to their Scalingo custom domains and keeps `track.lengrowth.com` on the existing Worker.
- The former AWS EC2 host is stopped during the observation period; do not terminate it or release its Elastic IP until the migration runbook gates and explicit approval are complete.

## Deployment

- Production deploys are performed from the protected production workflow or the authenticated Scalingo CLI.
- Keep `outreach-api` at exactly one `daemon` container unless the migration runbook explicitly authorizes a change; browser-session ownership must not be duplicated.
- Validate `/api/health` and the web root after deployments. Never expose secrets in logs, evidence, or documentation.
