# 找牛研究 / Zhaoniu

面向中国 A 股用户的证据驱动研究 SaaS。产品聚焦 Research / Data / Insight，不提供买入、
卖出、目标价、上涨概率或个性化投资建议。

当前仓库已经落地 Phase 0-21 的代码实现，包括受控 Beta、覆盖运营、运营控制台、单一
固定调度链路、公司研究时间线、受管 Provider 配置、DeepSeek 证据解读、两家公司
确定性对比、上线基线与 Provider/Beta 数据验收。Phase 19 内部工程基线已接受（邮件闭环
明确延期）；Phase 20 首次真实数据基线未通过。邀请 Beta 和生产发布仍受真实邮件交付、
获批数据源策略、Provider 数据完整性及其他发布门禁约束。

项目不包含支付、订单、公开价格或结算流程。AKShare 仍仅用于开发和技术评估；荐股、
自动化个人信息权利门户和未经审批的公开生产发布仍不在当前范围内。

## Repository map

```text
apps/
  web/                 Next.js desktop + mobile web
  api/                 FastAPI modular monolith boundary
  worker/              Celery background jobs
packages/
  api-client/          OpenAPI-generated TypeScript types + fetch client
  fundamentals/        future extracted deterministic package boundary
  market_data/         future extracted provider/normalizer boundary
  research_engine/     future structured research orchestration
infrastructure/
  migrations/          Alembic migrations
docs/                  architecture, data model, metric/source decisions
references/            isolated, Git-ignored upstream source checkouts
```

## Prerequisites

- Node.js 22+ and pnpm 11+
- Python 3.12+ and uv
- Docker Desktop or Docker Engine with Compose

## First run

```text
pnpm install
uv sync --all-groups
docker compose up -d postgres redis
uv run alembic -c infrastructure/migrations/alembic.ini upgrade head
```

Copy `.env.example` to `.env` and replace local passwords/secrets. Never commit `.env`.

Run the apps in separate terminals:

```text
pnpm dev
uv run uvicorn zhaoniu_api.main:app --app-dir apps/api/src --reload
uv run celery -A zhaoniu_worker.celery_app:celery_app worker --workdir apps/worker/src --loglevel INFO
```

## Development/evaluation data sync

```text
uv run python -m zhaoniu_api.cli sync-stock-master
uv run python -m zhaoniu_api.cli sync-daily-bars 600519 --start 2025-12-01
uv run python -m zhaoniu_api.cli sync-financial-statements 600519 --start-year 2019
uv run python -m zhaoniu_api.cli sync-valuations 600519 --start 2023-08-16
uv run python -m zhaoniu_api.cli compute-fundamentals 600519
uv run python -m zhaoniu_api.cli build-research-snapshot 600519
uv run python -m zhaoniu_api.cli generate-ai-stock-health 600519
uv run python -m zhaoniu_api.cli generate-ai-stock-health 600519 --retry-failed
uv run python -m zhaoniu_api.cli build-screening-snapshot
uv run python -m zhaoniu_api.cli validate-screen --query-file screen.json
uv run python -m zhaoniu_api.cli generate-registration-invites --count 10 --expires-in-days 7 --name internal-beta
uv run python -m zhaoniu_api.cli issue-access-code --user-email user@example.com --term month --expires-in-days 7
uv run python -m zhaoniu_api.cli inspect-user-access --user-email user@example.com
uv run python -m zhaoniu_api.cli check-beta-readiness
uv run python -m zhaoniu_api.cli build-beta-research-universe
uv run python -m zhaoniu_api.cli build-research-coverage-snapshot
uv run python -m zhaoniu_api.cli plan-coverage-backfill
uv run python -m zhaoniu_api.cli run-coverage-backfill RUN_ID
uv run python -m zhaoniu_api.cli generate-beta-learning-report --days 7
uv run python -m zhaoniu_api.cli beta-cohort-status
uv run python -m zhaoniu_api.cli invite-beta-gates
uv run python -m zhaoniu_api.cli production-release-status
uv run python scripts/postgres_ops.py backup --output .local/backups/zhaoniu.dump
uv run python scripts/postgres_ops.py verify --artifact .local/backups/zhaoniu.dump
```

AI is disabled by default. Before enabling it, explicitly configure `LLM_ENABLED=true`,
`LLM_MODEL_CHAIN` and provider credentials. Model names have no non-disabled defaults. Plaintext
secrets must not enter logs, ordinary domain tables or version control; managed provider
credentials may only enter the encrypted credential vault.

AKShare is not approved here for commercial display or redistribution. Read
`docs/DATA_SOURCE_POLICY.md` and `docs/FINANCIAL_DATA_SOURCE_DECISION.md` before using the data
outside development/evaluation.

Web: `http://localhost:3000`  
API docs: `http://localhost:8000/docs`  
Liveness: `http://localhost:8000/livez`
Readiness: `http://localhost:8000/readyz`

## Quality commands

```text
pnpm lint
pnpm format:check
pnpm typecheck
pnpm test
pnpm e2e
pnpm build
pnpm api:check
uv run ruff check .
uv run mypy apps/api/src apps/worker/src
uv run pytest
docker compose config
```

Regenerate the OpenAPI contract and TypeScript types with `pnpm api:generate`.

## Versioned API

以下为代表性路由；完整、可执行的当前合同以
`packages/api-client/openapi.json` 和生成的 TypeScript 类型为准。

```text
GET /api/v1/health
POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/auth/logout
POST /api/v1/auth/email-verification/verify
POST /api/v1/auth/email-verification/resend
POST /api/v1/auth/password-reset/request
POST /api/v1/auth/password-reset/confirm
GET /api/v1/legal/current
GET /api/v1/me
POST /api/v1/me/legal-acceptances
GET /api/v1/me/access
POST /api/v1/me/access/activate
GET /api/v1/me/sessions
DELETE /api/v1/me/sessions/{session_id}
GET /api/v1/stocks/search?q=茅台
GET /api/v1/stocks/{symbol}
GET /api/v1/stocks/{symbol}/daily-bars
GET /api/v1/stocks/{symbol}/research/fundamentals
GET /api/v1/stocks/{symbol}/financials/periods
GET /api/v1/stocks/{symbol}/valuations
GET /api/v1/stocks/{symbol}/research/snapshot
GET /api/v1/stocks/{symbol}/research/observations
GET /api/v1/stocks/{symbol}/research/observations/{observation_id}
GET /api/v1/stocks/{symbol}/ai-research
GET /api/v1/stocks/{symbol}/coverage
GET /api/v1/stocks/{symbol}/timeline
GET /api/v1/stocks/{symbol}/events/{event_id}/thread
GET /api/v1/stocks/{symbol}/ai/questions
POST /api/v1/stocks/{symbol}/ai/explanation-requests
POST /api/v1/me/beta-feedback
GET /api/v1/watchlists
POST /api/v1/watchlists
POST /api/v1/watchlists/{watchlist_id}/items
DELETE /api/v1/watchlists/{watchlist_id}/items/{symbol}
GET /api/v1/watchlists/membership/{symbol}
GET /api/v1/screens/catalog
GET /api/v1/screens/coverage
POST /api/v1/screens/validate
POST /api/v1/screens/executions
GET /api/v1/screens/executions/{execution_id}
GET /api/v1/screens/executions/{execution_id}/results
GET /api/v1/comparisons/catalog
POST /api/v1/comparisons
GET /api/v1/comparisons/{request_id}
GET /api/v1/admin/context
GET /api/v1/admin/providers/configurations
GET /api/v1/admin/releases
```

Watchlist endpoints require a valid HttpOnly session cookie and persist user-owned records in
PostgreSQL. Shared stocks, bars, financial facts, research snapshots and AI outputs remain global
shared data.

Read [Architecture](docs/ARCHITECTURE.md), [Data model](docs/DATA_MODEL.md),
[Financial metrics](docs/FINANCIAL_METRICS.md), [Change rules](docs/CHANGE_RULES.md),
[Research snapshots](docs/RESEARCH_SNAPSHOT.md), [AI research](docs/AI_RESEARCH.md),
[LLM policy](docs/LLM_POLICY.md), [screening engine](docs/SCREENING_ENGINE.md),
[company research timeline](docs/COMPANY_RESEARCH_TIMELINE.md),
[event engine V2](docs/EVENT_ENGINE_V2.md),
[production release gate](docs/PHASE_22_PRODUCTION_RELEASE_GATE.md),
[screen query DSL](docs/SCREEN_QUERY_DSL.md), and [Engineering rules](AGENTS.md) before extending
the system.
