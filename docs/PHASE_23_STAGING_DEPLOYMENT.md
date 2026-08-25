# Phase 23 — Hong Kong staging deployment

## Status and boundary

Phase 23 prepares an automatically updated staging environment at `https://app.zhiniu.cc`. It uses
production security settings but is not a Phase 22 production release. Staging accounts and data are
disposable. A later production launch must use new `zhaoniu-production` volumes and a new Phase 22
candidate; do not promote staging accounts into production.

The application remains a modular monolith. Only the deployment boundary changes: GitHub-hosted
runners build and scan immutable images, GHCR stores them, and the VPS pulls exact digests. BT Nginx
owns public HTTP/TLS. PostgreSQL, Redis and the application processes remain in Compose.

## One-time GitHub configuration

1. Protect `main`: require pull requests and the `frontend`, `backend`, and `api-contract` checks from
   the **Continuous integration** workflow. Disable force pushes and branch deletion.
2. Create the `staging` GitHub Environment. It does not require manual approval, because this host is
   pre-production.
3. Grant Actions read/write package permission. GHCR packages remain private unless deliberately
   changed later.
4. Keep repository variable `STAGING_DEPLOY_ENABLED` absent or `false` until DNS, Nginx, VPS secrets,
   GHCR login and backup destination are ready. Set it to `true` only for the first controlled deploy.
5. Add environment secrets:
   - `STAGING_HOST`
   - `STAGING_SSH_PORT`
   - `STAGING_SSH_USER` (`zhaoniu-deploy`)
   - `STAGING_SSH_KEY`
   - `STAGING_KNOWN_HOSTS` captured out-of-band with the VPS host fingerprint verified
6. Add a separate read-only repository Deploy Key for root's repository checkout on the VPS. The
   workflow SSH key and the repository Deploy Key must not be the same key.

A PR runs all engineering gates. A successful `main` workflow triggers image build, registry push,
Trivy scanning, CycloneDX SBOM export, and a serialized SSH deployment. A failed CI or scan never
contacts the VPS. A successful deployment triggers independent 1440×900 and 390×844 Chromium flows
against the public HTTPS origin; real email-link consumption remains a controlled manual run because
tokens must not be passed through workflow inputs or logs.

## One-time VPS preparation

Use Ubuntu 24.04 x86_64 with at least 2 vCPU, 6 GB RAM and 60 GB disk. Install Docker Engine and the
Compose plugin from Docker's official repository. In BT install only Nginx; do not install MySQL,
PHP or a second certificate manager.

Put the read-only repository Deploy Key in root's SSH configuration, clone the root-owned repository,
then create the separate workflow login through the installer:

```text
sudo install -d -o root -g root /opt/zhiniu
sudo git clone git@github.com:wepuu/zhiniu.git /opt/zhiniu/repo
sudo bash /opt/zhiniu/repo/infrastructure/production/install-host-assets.sh
```

Install the GitHub workflow public key in `/home/zhaoniu-deploy/.ssh/authorized_keys`. Add the
account's GHCR `read:packages` token to root's Docker credential store using `docker login ghcr.io
--password-stdin`; the workflow account cannot write the root-owned checkout and can only call the
validated deployment entry through its allow-listed sudo rule.
Restrict SSH and the BT panel to administrator IPs where operationally possible.

Copy `.env.production.example` to `/etc/zhiniu/staging.env`, replace every placeholder, and keep mode
`0600`. Generate all HMAC values independently. Generate the provider key ring with the existing
CLI; never copy the local development `.env`.

Create `/etc/zhiniu/backup.env` from `infrastructure/production/backup.env.example`. The age private
identity stays root-readable on the VPS and in offline recovery custody. `BACKUP_REMOTE` points to a
dedicated SSH account and `/srv/backups/zhiniu` on another server. That server owns the 14-daily and
8-weekly retention policy. Pin its host key in `BACKUP_KNOWN_HOSTS` and use a dedicated key named by
`BACKUP_SSH_KEY`; the backup command refuses interactive or unverified SSH.

Install `infrastructure/production/nginx-app.zhiniu.cc.conf` through BT after replacing
`REPLACE_WITH_ADMIN_IP`. Let BT issue and renew the certificate. Do not install standalone Certbot.
Validate with `nginx -t` before reload. Only ports 22, 80, 443 and the restricted BT port are public;
3000 and 8000 bind to loopback, while PostgreSQL and Redis have no host ports.

## First deployment and bootstrap

Before merging the first deployment PR, verify DNS, HTTPS, root GHCR login, the environment files,
the off-host backup SSH destination, and at least 15 GB free under `/var/lib/docker`.

The first successful main workflow creates the empty database, runs Alembic to `20260826_0027`, and
starts the six long-running services. No pre-deployment backup is required when no PostgreSQL
container exists. Every later deployment requires an encrypted, verified, successfully transferred
backup before migration.

Bootstrap the first operator without direct database writes:

1. Put the real Resend bootstrap credential in the root-only environment file, publish the required
   `zhiniu.cc` SPF/DKIM/DMARC records, and configure the webhook as
   `https://app.zhiniu.cc/api/v1/webhooks/resend`.
2. Temporarily set `REGISTRATION_MODE=invite_only`, recreate API/Worker, and generate exactly one
   registration invitation through the CLI.
3. Register, receive the real verification email, verify the account, then grant that email the
   `security_admin` role with `grant-operator`.
4. Use the operations console to import, diagnose and publish Resend into the encrypted managed
   Provider vault. Remove Resend secrets from the environment file and recreate API/Worker.
5. Restore `REGISTRATION_MODE=closed` and confirm the public registration path remains blocked.

Start from a clean stock database and run Provider acceptance for `600519`, `300750`, `300376`, and
`000001`. Hong Kong egress failures remain visible blockers; do not add a personal proxy as a
production dependency. Automation, AI explanation and natural-language screening stay disabled.

## Operations and rollback

`zhaoniu-deploy` validates a 40-character commit and exact repository digests, obtains an exclusive
lock, checks disk/memory, backs up the current database, pulls images, migrates once, updates the
services, and waits up to two minutes for API/Web health. Failure restores the previous images but
never downgrades the database. Therefore every migration merged to `main` must remain compatible
with the prior application release.

After the first deployment and backup test:

```text
sudo systemctl enable --now zhaoniu-backup.timer
sudo systemctl list-timers zhaoniu-backup.timer
sudo /usr/local/sbin/zhaoniu-backup --remote-required
sudo /usr/local/sbin/zhaoniu-restore-drill /var/backups/zhiniu/ARTIFACT.dump.age zhaoniu_restore_phase23
```

The timer runs daily at 18:00 UTC (02:00 Asia/Shanghai). Keep three local days; the remote receiver
keeps 14 daily and 8 weekly generations. Run an isolated restore drill monthly and before any
production candidate.

BT or another external monitor should check public `/livez`; administrators check `/readyz`. Alert
at 75% disk, sustained 85% memory/CPU, readiness failures, OOM, Celery backlog, or backup failure.
Keep the staging `X-Robots-Tag` and one-day HSTS until the environment is replaced by an approved
production release.
