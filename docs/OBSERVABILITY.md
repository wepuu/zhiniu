# Observability baseline

Every API response carries `X-Request-ID`. Request-completion logs are structured JSON with request
ID, method, route, status and duration; secrets, cookies, request bodies, activation codes and reset
tokens are excluded.

- `/livez`: process liveness only.
- `/readyz`: PostgreSQL connectivity, exact Alembic head and Redis health.
- `uv run python -m zhaoniu_api.cli beta-status`: active-user count and release blockers.
- Celery operations use `celery inspect ping` plus existing queryable job/run tables.

Alert on sustained readiness failures, migration mismatch, repeated authentication/email failures,
queue backlog and backup verification failures. Redis degradation must be visible even where a
read-only database-backed endpoint can continue serving.

On Phase 23 staging, public monitoring uses `/livez`; Nginx restricts `/readyz` to administrator
addresses. Also alert at 75% disk, sustained 85% CPU or memory, any OOM restart, failed systemd
backup, or a deployment health rollback. Docker JSON logs rotate at 10 MB with three files per
container. The immutable release record under `/opt/zhiniu/releases/current` identifies the exact
commit, API/Web digests and migration head.
