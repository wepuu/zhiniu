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

Deployment is permitted only when `check-beta-readiness` returns `ready`. A passing container build
or `/livez` response is not release approval. Legal review, financial-data usage approval and email
delivery are independent blocking gates.
