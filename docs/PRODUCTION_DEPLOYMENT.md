# Deployment

The current concrete target is the Phase 23 Hong Kong staging host. GitHub Actions builds immutable
API/Web images in GHCR; the VPS never builds application images. BT-managed Nginx terminates TLS and
proxies loopback-only Web/API ports. The Compose project contains PostgreSQL/pgvector, Redis, API,
Worker, Beat and Web; Caddy is no longer part of this topology.

Copy `.env.production.example` to `/etc/zhiniu/staging.env`, replace every placeholder, and validate
without starting services:

Keep `TRUSTED_HOSTS=app.zhiniu.cc,api` in that order. The deployment scripts use the first public
hostname for readiness probes, and the standalone Web container uses the internal `api` Compose
alias for `/gateway/api/` requests. Do not publish the `api` alias through DNS or a host port.

```text
PRODUCTION_ENV_FILE=/absolute/path/to/staging.env docker compose --env-file /absolute/path/to/staging.env -f infrastructure/production/docker-compose.yml config
```

After dependencies are running, execute readiness diagnostics inside the exact API image rather
than installing Python tooling on the host:

```text
docker compose --project-name zhaoniu-staging --env-file /etc/zhiniu/staging.env --env-file /opt/zhiniu/releases/current/release.env -f infrastructure/production/docker-compose.yml run --rm api python -m zhaoniu_api.cli check-beta-readiness
```

The deployment wrapper creates a verified off-host backup, pulls exact image digests, runs the
one-shot `migrate` service, updates long-running services, and only records success after API/Web
health checks. Image rollback never runs an Alembic downgrade, so schema changes must remain
compatible with the previous application version.

Phase 25D expects migration head `20260914_0030`. After calendar ingestion and a complete 24/48-hour
window, an elevated operations user may freeze the database-backed SLO and calendar result through
`POST /api/v1/admin/automation/observations`. The request must bind the exact release commit, API
and Web image digests and configuration fingerprint. This immutable application record supplements,
but does not replace, host-level OOM, restart, broker-depth, backup and restore evidence.

For Phase 25G, collect the complementary host record with the exact release-candidate configuration
fingerprint:

```text
sudo /usr/local/sbin/zhaoniu-phase25g-host-evidence \
  --configuration-fingerprint RELEASE_CONFIGURATION_SHA256
```

The collector is installed by `install-host-assets.sh` and refreshed after a healthy deployment.
It writes a new `0600` JSON file for every invocation and never reads or emits deployment secrets.
Archive the passing 24-hour and 48-hour host records next to the corresponding database observation
and release candidate. A failed record remains evidence and must not be edited into a pass.

The first release that introduces this collector may still be running the previous installed deploy
wrapper. After that release is healthy, install the collector once as root from the checked-out
repository; subsequent deployments refresh it automatically:

```text
install -m 0755 \
  /opt/zhiniu/repo/infrastructure/production/phase25g-host-evidence.py \
  /usr/local/sbin/zhaoniu-phase25g-host-evidence
```

`check-beta-readiness` remains a diagnostic, not deployment authorization. Production deployment
must use a Phase 22 candidate and pass `closed_deployment`; invitation activation must later pass
`invite_activation`. Both deployment and release events re-evaluate live gates before they are
recorded. A passing container build or `/livez` response is not release approval. The Phase 23
staging deployment is explicitly not one of these production events.

The automation switches have different meanings in these two phases. A closed deployment keeps
`AUTOMATION_HARD_DISABLED=true` while the application is observed. Before invite activation, the
operator must explicitly release that emergency stop and enable bounded user-triggered preparation
with `WATCHLIST_PREPARATION_ENABLED=true`; scheduled policies remain database-owned and must be
enabled separately. If either invite-phase switch is absent, the gate stays blocked and the API
returns a paused preparation state.

See `docs/PHASE_22_PRODUCTION_RELEASE_GATE.md` for production gates and
`docs/PHASE_23_STAGING_DEPLOYMENT.md` for server and GitHub setup.
