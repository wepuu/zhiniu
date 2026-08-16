# 找牛研究 / Zhaoniu

面向中国 A 股用户的证据驱动研究 SaaS。项目聚焦 Research / Data / Insight，不提供买入、卖出、目标价、上涨概率或个性化投资建议。

当前仓库已实现 **Phase 1 — Real A-Share Data Foundation**：AKShare 开发/评估
Provider、规范股票代码、PostgreSQL 未复权日 K、可查询同步运行、版本化行情 API、
OpenAPI TypeScript 类型和真实股票详情页。Watchlist、认证、AI 研究和支付仍未生产化。

## Repository map

```text
apps/
  web/                 Next.js desktop + mobile web
  api/                 FastAPI modular monolith boundary
  worker/              Celery worker foundation
packages/
  api-client/          OpenAPI-generated TypeScript types + lightweight fetch client
  market_data/         provider/normalizer boundary (reserved)
  fundamentals/        deterministic fundamentals (reserved)
  indicators/          deterministic indicators (reserved)
  research_engine/     structured research orchestration (reserved)
  change_engine/       material changes (reserved)
  event_engine/        normalized events (reserved)
  evidence_engine/     provenance and citations (reserved)
  llm/ news/ backtest/ future bounded packages
infrastructure/
  migrations/          Alembic migrations
  docker/              containerization notes
docs/                   architecture, data model, roadmap, reuse register
references/             isolated upstream source checkouts
```

## Prerequisites

- Node.js 22+ and pnpm 10+
- Python 3.12+ and uv
- Docker Desktop or Docker Engine with Compose (for PostgreSQL/Redis)

## First run

```text
pnpm install
uv sync --all-groups
docker compose up -d postgres redis
```

Copy `.env.example` to `.env` and replace local passwords/secrets. Never commit `.env`.

Run the apps in separate terminals:

```text
pnpm dev
uv run uvicorn zhaoniu_api.main:app --app-dir apps/api/src --reload
uv run celery -A zhaoniu_worker.celery_app:celery_app worker --workdir apps/worker/src --loglevel INFO
```

Apply migrations and sync the Phase 1 evaluation dataset:

```text
uv run alembic -c infrastructure/migrations/alembic.ini upgrade head
uv run python -m zhaoniu_api.cli sync-stock-master
uv run python -m zhaoniu_api.cli sync-daily-bars 600519 --start 2025-12-01
```

AKShare is not approved here for commercial display or redistribution. See
`docs/DATA_SOURCE_POLICY.md` before using the data outside development/evaluation.

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

Format code with `pnpm format` and `uv run ruff format .`. Regenerate the OpenAPI contract and
TypeScript types with:

```text
pnpm api:generate
```

## Versioned API

```text
GET  /api/v1/health
GET  /api/v1/stocks/search?q=茅台
GET  /api/v1/stocks/{symbol}
GET  /api/v1/stocks/{symbol}/daily-bars?limit=120&adjust=none
GET  /api/v1/watchlists
POST /api/v1/watchlists
POST /api/v1/watchlists/{id}/items
```

Watchlist endpoints currently use a fixed demo identity and an in-memory repository. This is an explicit seam, not production authentication or persistence.

Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/DATA_MODEL.md](docs/DATA_MODEL.md), and [AGENTS.md](AGENTS.md) before extending the system.
