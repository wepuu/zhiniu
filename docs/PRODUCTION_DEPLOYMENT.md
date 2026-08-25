# Production deployment

Copy `.env.production.example` to a secret-managed environment file outside version control and
replace every placeholder. Validate without starting services:

```text
docker compose --env-file .env.production -f infrastructure/production/docker-compose.yml config
uv run python -m zhaoniu_api.cli check-beta-readiness
```

The production topology is Caddy -> Next.js/FastAPI, plus Celery, PostgreSQL and Redis. Alembic runs
as the one-shot `migrate` service before the API and worker. Only the proxy exposes host ports.
Configure TLS at the proxy and use an HTTPS `PUBLIC_BASE_URL`, secure cookies, explicit trusted
hosts and origins, strong domain-separated HMAC secrets, and external secret injection.

`check-beta-readiness` remains a diagnostic, not deployment authorization. Production deployment
must use a Phase 22 candidate and pass `closed_deployment`; invitation activation must later pass
`invite_activation`. Both deployment and release events re-evaluate live gates before they are
recorded. A passing container build or `/livez` response is not release approval. See
`docs/PHASE_22_PRODUCTION_RELEASE_GATE.md`.
