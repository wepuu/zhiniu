# 找牛研究 / Zhaoniu

面向中国 A 股用户的证据驱动研究 SaaS。产品聚焦 Research / Data / Insight，不提供买入、
卖出、目标价、上涨概率或个性化投资建议。

当前仓库已完成 Phase 4：在不可变研究快照之上增加结构化 AI 股票体检、多模型自动
fallback、稳定证据引用、不可变输出、调用审计和分别设计的桌面/移动 AI 研究体验。
AKShare 仍仅用于开发和技术评估；Watchlist、正式认证、AI 问股和支付尚未生产化。

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
docs/                   architecture, data model, metric/source decisions
references/             isolated, Git-ignored upstream source checkouts
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
```

AI 默认为关闭。启用前显式配置 `LLM_ENABLED=true`、有序 `LLM_MODEL_CHAIN` 和对应
Provider API Key；模型名没有非禁用默认值。密钥不得进入日志、数据库或版本控制。

AKShare is not approved here for commercial display or redistribution. Read
`docs/DATA_SOURCE_POLICY.md` and `docs/FINANCIAL_DATA_SOURCE_DECISION.md` before using the data
outside development/evaluation.

Web: `http://localhost:3000`  
API docs: `http://localhost:8000/docs`  
Health: `http://localhost:8000/api/v1/health`

## Quality commands

```text
pnpm lint
pnpm format:check
pnpm typecheck
pnpm test
pnpm build
pnpm api:check
uv run ruff check .
uv run mypy apps/api/src apps/worker/src
uv run pytest
docker compose config
```

Regenerate the OpenAPI contract and TypeScript types with `pnpm api:generate`.

## Versioned API

```text
GET /api/v1/health
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
```

Watchlist endpoints still use a fixed demo identity and in-memory repository. This is an explicit
seam, not production authentication or persistence.

Read [Architecture](docs/ARCHITECTURE.md), [Data model](docs/DATA_MODEL.md),
[Financial metrics](docs/FINANCIAL_METRICS.md), [Change rules](docs/CHANGE_RULES.md),
[Research snapshots](docs/RESEARCH_SNAPSHOT.md), [AI research](docs/AI_RESEARCH.md),
[LLM policy](docs/LLM_POLICY.md), and [Engineering rules](AGENTS.md) before extending the system.
