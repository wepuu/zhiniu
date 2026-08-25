# Deployment

The current concrete target is the Phase 23 Hong Kong staging host. GitHub Actions builds immutable
API/Web images in GHCR; the VPS never builds application images. BT-managed Nginx terminates TLS and
proxies loopback-only Web/API ports. The Compose project contains PostgreSQL/pgvector, Redis, API,
Worker, Beat and Web; Caddy is no longer part of this topology.

Copy `.env.production.example` to `/etc/zhiniu/staging.env`, replace every placeholder, and validate
without starting services:

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

`check-beta-readiness` remains a diagnostic, not deployment authorization. Production deployment
must use a Phase 22 candidate and pass `closed_deployment`; invitation activation must later pass
`invite_activation`. Both deployment and release events re-evaluate live gates before they are
recorded. A passing container build or `/livez` response is not release approval. The Phase 23
staging deployment is explicitly not one of these production events.

See `docs/PHASE_22_PRODUCTION_RELEASE_GATE.md` for production gates and
`docs/PHASE_23_STAGING_DEPLOYMENT.md` for server and GitHub setup.
