# AWS EC2 to Scalingo + Cloudflare Migration Plan

Status: Phase 0 evidence captured; backup/restore requirement explicitly waived by the user; proceeding with production-only Scalingo migration, 2026-09-01  
Scalingo destination project: `outreach` (new; existing `lengrowth` project is out of scope)  
Confirmed AWS source: `Linkedin-auth`, instance `i-027c586e0728aaded`, `t3.large`, `us-east-1b`, Elastic IP `50.19.251.160`  
Confirmed root volume: `vol-0d7f16cbe367284fd`, 35 GiB gp3, unencrypted, `DeleteOnTermination=true`  
Cloudflare zone hostnames: `outreach.lengrowth.com`, `outreach-api.lengrowth.com`, `track.lengrowth.com`

Execution evidence: local, timestamped, Git-ignored records are under
`.migration-evidence/20260901-201741/`. No production infrastructure or DNS
state has been changed. Phase 2 provisioning is intentionally paused until a
recent Atlas backup and successful non-production restore are evidenced.

## Executive decision

Use Scalingo for application compute and Cloudflare for authoritative DNS, reverse proxy, TLS edge, WAF/rate limiting, static caching, and the existing email-tracking Worker.

Create two production apps in the new Scalingo project `outreach`:

| App | Scalingo processes | Public hostname | Initial scale |
|---|---|---|---|
| `outreach-web` | `web`: Next.js, bound to `0.0.0.0:$PORT` | `outreach.lengrowth.com` | `web:1:L` |
| `outreach-api` | `web`: FastAPI; `daemon`: Playwright/Xvfb automation; `postdeploy`: MongoDB indexes | `outreach-api.lengrowth.com` | `web:1:L`, `daemon:1:2XL` |

This migration uses production Scalingo apps only: `outreach-web` and `outreach-api`. The Atlas restore test remains the non-production validation boundary; no Scalingo staging apps are required.

Do not horizontally scale `daemon` until profile/session ownership has been tested across multiple containers. The MongoDB task claim is atomic, but duplicate browser sessions for the same LinkedIn profile are a separate risk. The API and frontend can scale horizontally once their statelessness tests pass.

Keep MongoDB Atlas as the system of record during this migration. This avoids a database cutover and makes application rollback safe. Measure Paris-to-Atlas latency before production; if Atlas is restricted by source IP, allow the current `osc-fr1` egress addresses resolved from `egress.osc-fr1.scalingo.com`. Do not use `0.0.0.0/0` as the permanent Atlas access rule.

The current `track.lengrowth.com` Worker stays in place. Its `BACKEND_URL` remains the canonical API hostname, so it should not need a production secret change when DNS moves the API hostname to Scalingo.

## Facts established during discovery

- Both `outreach.lengrowth.com` and `outreach-api.lengrowth.com` currently resolve directly to `50.19.251.160`, confirming `Linkedin-auth` as the origin.
- The frontend and API currently return `Server: nginx/1.28.3 (Ubuntu)` and are not Cloudflare-proxied. `track.lengrowth.com` is already Cloudflare-proxied.
- The live API health endpoint is operational, reports MongoDB connected, and reports build `2.1.4` at commit `110dbdef289ad9e28a6f35315ac7b589a51a5783` at discovery time.
- The current Docker startup combines Next.js, FastAPI, Xvfb, and the automation daemon. Scalingo exposes only the `web` process on `$PORT`, so this must be separated into process types/apps.
- MongoDB is external. Browser storage state/cookies are persisted in MongoDB. Runtime diagnostics are written to `/tmp`, so they are intentionally ephemeral.
- Scalingo filesystems are ephemeral. Before cutover, the EC2 audit must prove that `/app/data` and `/app/openoutreach/media` contain no required production state. Any required objects must move to R2 or another external object store first.
- Billing jobs currently use GitHub Actions to SSH into EC2. They must be moved before the instance is terminated.
- Installed CLIs at discovery: AWS CLI `2.36.15`, Wrangler `4.118.0`, Scalingo CLI `1.47.0`. Scalingo CLI must be upgraded to `1.48.0`. Wrangler authentication is currently invalid/insufficient and must be renewed.
- EC2 termination protection is disabled. The root EBS volume will be deleted automatically with the instance. This is useful only after all gates pass; it makes an accidental early termination unrecoverable.

## Safety model for an AI-executed migration

Every phase ends with a machine-verifiable gate. The AI must stop on a failed gate and may not compensate by skipping checks. Production DNS mutation, disabling the old daemon/schedulers, EC2 stop, EC2 termination, and Elastic IP release are separate checkpoints.

The termination command must never be embedded in the ordinary deploy workflow. It belongs in a dedicated decommission script that:

1. validates the exact instance ID and `Name=Linkedin-auth` tag;
2. validates the expected Elastic IP and root volume;
3. requires a fresh health/acceptance evidence file;
4. requires an explicit `--confirm-instance-id i-027c586e0728aaded` argument;
5. terminates only that exact instance; and
6. waits for the `terminated` state before optionally releasing the exact Elastic IP allocation.

Never print `.env`, secret values, MongoDB URIs, signing keys, Stripe secrets, LinkedIn credentials, or Cloudflare tokens to logs. Preserve the current encryption/signing material for the initial move; rotation is a later coordinated migration because existing encrypted cookies and tokens depend on it.

## Phase 0 — Freeze the baseline and restore tool access

AI actions:

1. Record the Git SHA, working-tree status, live health response, DNS answers, Cloudflare configuration export, Scalingo app/project inventory, and AWS instance/volume/EIP metadata in a timestamped evidence directory excluded from Git.
2. Upgrade Scalingo CLI to `1.48.0` and verify `scalingo whoami`.
3. Renew Wrangler authentication or install a least-privilege API token, then verify `npx wrangler whoami`. Add `account_id` to the Worker configuration only if the repository's configuration convention requires it.
4. Resolve the new project/app names for global availability. The intended project is exactly `outreach`; intended apps are `outreach-web` and `outreach-api` only.
5. Audit the EC2 host read-only over its verified SSH host key:
   - running containers/processes and deployed Git SHA;
   - `.env` variable names only, never values;
   - sizes/checksums/file lists for mounted `/app/data` and `/app/openoutreach/media`;
   - active crons/systemd timers;
   - nginx virtual hosts;
   - Docker volumes;
   - recent daemon task activity and any running task leases.
6. Confirm a recent MongoDB Atlas backup and test that the migration operator can restore it into a non-production database.
7. Resolve and record Scalingo `osc-fr1` egress addresses from DNS immediately before modifying the Atlas allowlist.

Gate 0:

- CLI authentication succeeds for AWS, Scalingo, and Cloudflare.
- `Linkedin-auth` metadata still matches the identifiers at the top of this document.
- The local-state audit classifies every file as disposable, source-controlled, secret/config, or migrated to external storage.
- A MongoDB restore test succeeds.

Rollback: no production state has changed.

## Phase 1 — Make the repository Scalingo-native

Implement on a migration branch and keep the AWS deployment functional during this phase.

### Backend slug (`outreach-api`)

1. Add a root `requirements.txt` that includes `requirements/production.txt`, and pin the supported Python 3.12 line using the current Scalingo Python mechanism.
2. Add `.buildpacks` with the Scalingo APT buildpack followed by the Python buildpack. The root `package.json` exists only for Wrangler and must not cause Node to be selected for the backend.
3. Add an `Aptfile` for the selected Scalingo stack with Chromium/Playwright/X11 dependencies, including Xvfb. Use the package names for that exact stack.
4. Add a build hook that installs the Playwright Chromium binary into the slug and fails deployment if the browser cannot launch.
5. Add a `Procfile` with separate commands:
   - `web`: run FastAPI on `0.0.0.0:$PORT`;
   - `daemon`: run Xvfb and `python -m openoutreach.cli rundaemon`;
   - `postdeploy`: run `python -m openoutreach.cli ensure-indexes`.
6. Update Playwright launch arguments for Scalingo only if required. Scalingo's browser guidance requires `--no-sandbox`; scope that flag to the trusted application browser and test it explicitly rather than enabling it globally.
7. Ensure SIGTERM reaches FastAPI, the daemon, and Chromium, with a clean shutdown inside Scalingo's 30-second replacement window.
8. Add `cron.json` for the three current billing jobs (`expire-trials`, `cleanup-deleted-accounts`, `send-trial-warnings`). Keep the existing schedules, make each command idempotent, and add a distributed lock because Scalingo notes that scheduled runs can overlap and are not guaranteed to be exact.
9. Add a `.slugignore` so desktop build artifacts, tests, local caches, `.env`, data, and unrelated release assets do not enter the production slug.

### Frontend slug (`outreach-web`)

1. Deploy with `PROJECT_DIR=frontend` or an equivalent monorepo layout.
2. Bind Next.js to `0.0.0.0:$PORT` and use standalone output to reduce slug size.
3. Set `NEXT_PUBLIC_API_URL=https://outreach-api.lengrowth.com` and `NEXT_PUBLIC_APP_URL=https://outreach.lengrowth.com` at build time.
4. Ensure authenticated/dynamic pages retain `private`/`no-store` behavior.

### CI/CD

1. Add a Scalingo deployment workflow that deploys the same tested commit to production only, behind a protected production environment approval.
2. Replace EC2 SSH deployment and billing workflows. Do not delete the old workflows yet; disable their schedules only at the production cutover gate.
3. Add rollback jobs that select the previous Scalingo deployment. Database changes must remain backward-compatible through the observation window.

Gate 1:

- Local/unit/integration tests pass.
- Backend slug builds successfully in CI before any production deploy.
- `web` binds to `$PORT`; Chromium launches under Xvfb; SIGTERM exits cleanly.
- `daemon` is defined but still scaled to zero in production until database/task ownership is verified.
- No secret scanner findings and no required writes to the local filesystem.

Rollback: revert the migration branch; AWS remains the production deployment.

## Phase 2 — Create the isolated Scalingo project and production apps

Use region `osc-fr1` unless a documented business/compliance decision selects the restricted SecNumCloud region.

Illustrative CLI sequence (resolve the returned project ID rather than guessing it):

```text
scalingo projects-add --region osc-fr1 outreach
scalingo create --region osc-fr1 --project-id <OUTREACH_PROJECT_ID> outreach-web
scalingo create --region osc-fr1 --project-id <OUTREACH_PROJECT_ID> outreach-api
```

AI actions:

1. Verify both apps show project `outreach`; abort if any app lands in `lengrowth`.
2. Link the repository/branch or configure archive deploys. Keep production auto-deploy disabled until cutover.
3. Configure production from the authoritative secret source. Do not scrape values into a committed file. Preserve production `SECRET_KEY`, cookie encryption key, daemon signing keys, and Stripe webhook secret initially.
5. Add the current `osc-fr1` egress IPs to MongoDB Atlas, deploy, test connectivity, then narrow/remove obsolete allowlist entries only after EC2 termination.
6. Start with `outreach-api` `web:1:L`, `daemon:0`; `outreach-web` `web:1:L`. Increase sizes based on measured memory/CPU, not EC2 vCPU equivalence.
7. Configure log retention/drain, exception alerts, container restart alerts, latency alerts, and MongoDB connectivity alerts.

Gate 2:

- Both production apps deploy from the intended commit while DNS remains unchanged.
- Production API health is green and reports the intended build SHA.
- Production frontend is configured to use only the production API.
- Production apps are reachable on their `*.osc-fr1.scalingo.io` domains but have no production DNS traffic.
- Production daemon remains at zero.

Rollback: scale/delete only the new apps; AWS is untouched.

## Phase 3 — Full pre-cutover acceptance

Run automated and operator acceptance against the production apps on their native `*.scalingo.io` domains before DNS cutover:

1. API health, build identity, CORS, auth/login/logout/refresh, account export, admin authorization, and rate-limit behavior.
2. Create/read/update flows for campaigns, leads, deals, settings, and billing test mode.
3. Desktop daemon v2 enrollment, compatibility, task lease, receipt, replay rejection, version gate, and redaction tests.
4. Stripe test webhook signature and idempotency tests.
5. Email sending plus the existing Worker path for open, click, unsubscribe, suppression, and webhook delivery. Run `wrangler deploy --dry-run`; do not replace the existing Worker.
6. Run each billing scheduled command manually as a Scalingo one-off, then verify scheduler discovery from `cron.json`.
7. With an explicit cutover checkpoint, scale the production daemon to exactly one container and use a dedicated non-production profile/account for verification. Verify Xvfb, Chromium, proxy support, cookie save/reload from MongoDB, graceful restart, and task recovery.
8. Restart/redeploy each production app to prove nothing required is stored on its filesystem.
9. Load test API and frontend at expected peak plus headroom; record p50/p95/p99 latency, memory, CPU, restart count, and MongoDB latency.

Gate 3:

- All acceptance tests pass twice, including once after a full restart.
- No duplicate daemon claims or scheduled jobs.
- Scalingo-to-Atlas latency is acceptable for the product or a separate Atlas-region plan has been approved.
- A Scalingo rollback to the prior production deployment succeeds before DNS cutover.

Rollback: production apps remain on the prior deployment; AWS remains available until observation gates pass.

## Phase 4 — Prepare Cloudflare and deploy production dark

1. Deploy the accepted SHA to both production Scalingo apps.
2. Keep the production daemon at zero and scheduled jobs disabled until the ownership handoff.
3. Add `outreach.lengrowth.com` to `outreach-web` and `outreach-api.lengrowth.com` to `outreach-api` as custom domains.
4. Verify Scalingo certificates are issued. Use Scalingo Force HTTPS. For the Scalingo/Cloudflare combination, use Cloudflare SSL/TLS mode `Full (strict)` and follow Scalingo's current guidance not to enable Cloudflare “Always Use HTTPS,” because `/.well-known/` must remain reachable for Scalingo's Let's Encrypt renewal.
5. Prepare proxied Cloudflare CNAME records:
   - `outreach` -> `outreach-web.osc-fr1.scalingo.io`;
   - `outreach-api` -> `outreach-api.osc-fr1.scalingo.io`.
6. Keep `track.lengrowth.com` on the email-tracking Worker custom domain.
7. Initial cache policy:
   - bypass cache for all API, auth, webhook, SSE, and daemon paths;
   - bypass personalized frontend HTML;
   - cache only versioned immutable assets such as `/_next/static/*`;
   - honor the application's `private`/`no-store` headers.
8. Enable an appropriate Cloudflare managed WAF baseline and narrowly rate-limit login/enrollment/high-risk mutation routes. Do not place interactive challenges on Stripe webhooks, Worker webhooks, health checks, or desktop daemon APIs. Test every exclusion.
9. Configure health monitoring for `/api/health` and external synthetic checks for the frontend. Capture the baseline Cloudflare and Scalingo metrics.

Gate 4:

- The production Scalingo default domains and custom-host-header probes pass.
- TLS is valid end-to-end.
- Cloudflare configuration is exported and rollback DNS records are prepared.
- The AWS origin remains healthy and unchanged.

Rollback: remove/unproxy prepared records or domains; no traffic has moved yet.

## Phase 5 — Controlled production cutover

Schedule a low-traffic window and announce a short automation maintenance period.

### 5A. Establish single ownership of background work

1. Pause production campaign/task execution through the supported application control.
2. Wait until no production tasks are `running` and all leases have expired or completed.
3. Disable the old GitHub billing schedules.
4. Disable the EC2 daemon without taking down the EC2 API/frontend. Prefer a controlled deployment/restart with `SKIP_DAEMON=true`; verify from logs and MongoDB that it no longer claims work.
5. Enable Scalingo scheduled tasks and run one controlled job.
6. Scale `outreach-api` daemon to exactly one container and verify it starts without claiming work while campaigns remain paused.

Gate 5A: exactly one daemon is alive, only on Scalingo; exactly one scheduler owns each billing job; zero duplicate task claims.

### 5B. Move API, then frontend

1. Change the Cloudflare `outreach-api` record from the EC2 A record to the proxied CNAME for `outreach-api.osc-fr1.scalingo.io`.
2. Run health/build checks, desktop compatibility checks, auth, a harmless read, a controlled write, Stripe/Worker webhook tests, and log/error checks.
3. Change the Cloudflare `outreach` record from the EC2 A record to the proxied CNAME for `outreach-web.osc-fr1.scalingo.io`.
4. Run browser acceptance and confirm that frontend API calls reach the Scalingo API.
5. Resume campaigns gradually: one internal/test profile, then a small cohort, then all profiles. Watch daemon task claims and provider checkpoints at each step.

Gate 5B (minimum 60 minutes stable before ending the cutover window):

- Public hostnames resolve through Cloudflare and return the accepted Scalingo build SHA.
- Error rate, p95 latency, MongoDB latency, auth success, task throughput, webhook success, scheduled jobs, and email tracking remain within agreed thresholds.
- No request is reaching the EC2 nginx access log except deliberate rollback probes.

Immediate rollback:

1. Pause campaigns.
2. Scale the Scalingo daemon to zero and disable Scalingo scheduled ownership.
3. Re-enable the EC2 daemon and old scheduled owner.
4. Restore Cloudflare DNS targets to `50.19.251.160` for API first, then frontend.
5. Verify the EC2 health/build and resume campaigns.

Because MongoDB remains shared and schema changes are backward-compatible, no data restore should be needed for this rollback.

## Phase 6 — Observation and EC2 stop

Observe the Scalingo production deployment for at least 72 hours, including one complete daily billing cycle and normal daemon workloads.

During observation:

- keep the EC2 deployment intact but with daemon and schedulers disabled;
- compare application, Cloudflare, Worker, MongoDB, Stripe, and daemon metrics daily;
- confirm there are no required files accumulating on Scalingo's ephemeral disk;
- verify the email Worker webhook reaches Scalingo reliably;
- test a Scalingo app rollback without changing DNS;
- update runbooks and operational links from AWS/SSH to Scalingo.

After 72 hours of clean evidence:

1. Stop only `i-027c586e0728aaded`.
2. Wait for `instance-stopped` and rerun all production acceptance tests for at least 24 additional hours.
3. Confirm no monitoring, GitHub workflow, DNS record, SSH job, webhook, documentation, or operator procedure still references `50.19.251.160` or `Linkedin-auth` as an active service.

Gate 6: the service passes for 24 hours with EC2 stopped. Rollback remains possible by starting the same instance and restoring the two DNS targets.

## Phase 7 — Permanent EC2 decommission

Preconditions, all mandatory:

- Gate 6 evidence is complete and timestamped.
- MongoDB backup is current and restorable.
- EC2 local-state audit is empty of required data.
- Source and deployment SHA are preserved in Git/GitHub.
- All production secrets exist in the new authoritative store.
- AWS deployment and EC2 SSH billing workflows are disabled/replaced.
- Public DNS has no EC2 origin references.
- The exact instance still has `Name=Linkedin-auth`, instance ID `i-027c586e0728aaded`, EIP `50.19.251.160`, and root volume `vol-0d7f16cbe367284fd`.
- A human has approved permanent deletion after reviewing the evidence. This is a deletion approval, not merely a deploy approval.

Decommission sequence:

1. Capture final metadata and billing tags. Do not create a long-lived machine image unless an explicit retention requirement exists: the image would preserve production secrets from the unencrypted root volume.
2. Terminate only `i-027c586e0728aaded` and wait for the terminal state.
3. Verify root volume `vol-0d7f16cbe367284fd` was deleted by `DeleteOnTermination`.
4. Release only Elastic IP allocation `eipalloc-02e6bfaa77ead1673` after confirming it is no longer associated and no DNS record references it.
5. Do not delete the default security group or shared VPC. Review them separately for other instances.
6. Remove obsolete EC2 SSH keys, GitHub secrets (`EC2_HOST`, `EC2_USER`, `EC2_SSH_KEY`, `EC2_KNOWN_HOSTS`), host-key records, and EC2-specific monitoring.
7. Remove the EC2 address from the MongoDB Atlas allowlist. Retain only current required sources, including current Scalingo egress addresses.
8. Record AWS resource deletion results and close the migration.

Representative guarded AWS operations (the decommission script must perform the identity checks before these):

```text
aws ec2 terminate-instances --instance-ids i-027c586e0728aaded
aws ec2 wait instance-terminated --instance-ids i-027c586e0728aaded
aws ec2 describe-volumes --volume-ids vol-0d7f16cbe367284fd
aws ec2 release-address --allocation-id eipalloc-02e6bfaa77ead1673
```

Expected `describe-volumes` result after termination is `InvalidVolume.NotFound`. Treat any other result as a cleanup exception to investigate, not permission to delete a different volume.

## Acceptance checklist

- [ ] Scalingo project is exactly `outreach`; existing `lengrowth` project unchanged.
- [ ] Production frontend and API deploy from the same accepted Git SHA.
- [ ] API and frontend each bind to their own Scalingo `$PORT`.
- [ ] MongoDB backup/restore and connectivity validated.
- [ ] Local persistent-state audit completed; required objects externalized.
- [ ] Daemon runs as exactly one production process and survives restart.
- [ ] No simultaneous AWS and Scalingo daemon ownership.
- [ ] Billing schedules have exactly one owner and distributed locking.
- [ ] Desktop daemon v2, Stripe, email tracking, unsubscribe, and auth flows pass.
- [ ] Cloudflare is proxied, Full (strict), with safe cache and WAF exclusions.
- [ ] Wrangler authentication repaired and Worker rollback tested.
- [ ] 72-hour live observation plus 24-hour EC2-stopped observation pass.
- [ ] Human reviews the final evidence and approves exact-instance termination.
- [ ] `Linkedin-auth` terminated; root EBS volume deleted; EIP released.
- [ ] EC2-specific secrets, workflows, allowlists, monitoring, and docs removed.

## Current reference documentation

- Scalingo Procfile/process types: https://doc.scalingo.com/platform/app/procfile
- Scalingo deployment lifecycle: https://doc.scalingo.com/platform/deployment/deployment-process
- Scalingo multi-buildpack: https://doc.scalingo.com/platform/deployment/buildpacks/multi
- Scalingo APT buildpack: https://doc.scalingo.com/platform/deployment/buildpacks/apt
- Scalingo browser/Xvfb guidance: https://doc.scalingo.com/languages/nodejs/puppeteer
- Scalingo scheduler: https://doc.scalingo.com/platform/app/task-scheduling/scalingo-scheduler
- Scalingo ephemeral filesystem: https://doc.scalingo.com/platform/app/filesystem
- Scalingo/Cloudflare integration: https://doc.scalingo.com/platform/app/cloudflare-scalingo-app
- Scalingo egress addresses: https://doc.scalingo.com/platform/networking/public/egress
- Cloudflare proxied DNS: https://developers.cloudflare.com/dns/proxy-status/
- Cloudflare Wrangler configuration: https://developers.cloudflare.com/workers/wrangler/configuration/
- Cloudflare Worker rollback: https://developers.cloudflare.com/workers/wrangler/commands/workers/
