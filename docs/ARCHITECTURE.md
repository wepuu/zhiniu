# Zhaoniu Architecture

## System context

Zhaoniu is a browser-based, multi-user A-share research SaaS. The Phase 1 system remains a modular monolith: one Next.js web application, one FastAPI application, Celery workers, PostgreSQL/pgvector, and Redis. It optimizes for research, data, and traceable insight—not trading or investment advice.

```text
Desktop / Mobile browser
        | REST + later SSE
        v
Next.js web  --> FastAPI modular monolith --> PostgreSQL
                        |                       (canonical state)
                        +--> Redis <--> Celery workers
                        |
                        +--> provider adapters --> external data vendors
                        +--> LLM gateway --------> compatible model providers
```

## Frontend architecture

`apps/web` uses Next.js App Router, strict TypeScript, Tailwind CSS, Radix-compatible UI primitives, TanStack Query/Table, Zustand-ready local state, React Hook Form + Zod, ECharts and Lightweight Charts. The base shell has separately composed desktop navigation and mobile bottom navigation. Shared hooks, API models, formatters, chart primitives, and research cards will remain device-agnostic.

The visual system is a research instrument rather than an admin template: paper/mist surfaces, graphite text, restrained research blue, amber evidence rails, serif research headings, and monospaced data labels. Accessibility includes visible focus, touch-sized navigation, semantic landmarks, and reduced-motion handling.

## Backend architecture

`apps/api` separates routes, application services, ports, domain models, and infrastructure adapters.
Routes translate HTTP only. The market-data service coordinates the Provider → Normalizer →
Canonical Model → Quality Validator → Repository flow. SQLAlchemy repositories own stock, daily
bar, and sync-run persistence. AKShare's synchronous SDK is contained in a bounded thread adapter.

Authentication remains a deliberate seam returning a fixed demo identity. Persistent Watchlist and
production authentication are deferred to Phase 2. Authorization and entitlements remain separate
concerns.

## Data architecture

PostgreSQL is the system of record. Redis is for bounded caching, task coordination, rate limiting, and distributed locks—not durable business truth. pgvector is available for evidence retrieval when justified. Raw payloads, normalized clean data, derived metrics, research context, structured AI output, and evidence are separate layers and tables/modules.

## AI architecture

Business code targets `LLMGateway`, never a vendor SDK. Requests use named tasks and structured schemas. Each call can record task type, provider/model, token counts, latency, cost, and status. The LLM receives deterministic metrics and evidence; it summarizes and explains but never calculates metrics or chooses UI.

A shared research snapshot key is:

```text
symbol + data_version + research_template_version + model_version
```

That unique identity prevents thousands of users following one stock from triggering thousands of equivalent model calls. User-specific analysis is separate only when it actually includes private user data.

## Background jobs

Celery workers handle data sync, financial/news/event processing, research, reports, notifications, and future backtests. A production task must have a deterministic idempotency key, bounded retry policy, duplicate suppression, appropriate distributed lock, and queryable task status. An example is `analysis:600519:20260815:v1`.

## Shared data vs user data

Shared: stocks, market data, financials, metrics, industries, announcements, news, events, evidence, and public research snapshots.

User-owned: users, sessions, watchlists/items, alerts, preferences, AI chats, subscriptions, and usage. Every user-owned table and query carries `user_id`; even `watchlist_items` keeps it explicitly for isolation and future row-level security.

## Data provider pattern

```text
Tushare / AKShare / BaoStock adapter
              -> raw provider response
              -> provider-specific normalizer
              -> canonical domain model
              -> repository
```

Application services target the `MarketDataProvider` contract. Phase 1 registers only AKShare for
development/evaluation. The fallback contract is verified with fake providers; no real fallback is
claimed. Vendor models never leak into domain code.

## Research pipeline

```text
Raw data -> normalization -> clean data -> deterministic metrics
         -> change/event engines -> research context -> LLM gateway
         -> structured research -> evidence links -> research snapshot
```

## Module boundaries

- `market_data`: provider contracts/adapters, normalization, canonical quotes and bars.
- `fundamentals`: statements and deterministic fundamental metrics.
- `indicators`: deterministic technical/statistical calculations.
- `research_engine`: context assembly and structured snapshot orchestration.
- `change_engine`: version comparison and material-change detection.
- `event_engine`: event canonicalization and clustering.
- `evidence_engine`: source identity, citations, provenance, and retrieval.
- `llm`: provider-neutral gateway and usage records.
- `news`: news provider adapters and normalized articles.
- `backtest`: later isolated research simulation; absent from Phase 0 behavior.

Top-level `packages/*` currently reserve these boundaries. They should become installable packages only when they contain cohesive code; premature packaging would add build complexity without isolation.

## Future scaling strategy

Scale vertically and add worker queues first. Add read replicas, partition high-volume time series, cache hot canonical reads, and isolate workloads only after profiling. Kafka, ClickHouse, OpenSearch, Kubernetes, gRPC, vector databases beyond pgvector, and independent microservices require explicit scale evidence and an ADR.

## Third-party reuse strategy

Reference repositories live under `references/` and never join the product workspace. Prefer adapters around stable upstream surfaces, then extract small licensed algorithms with provenance when an adapter is impossible. Keep local patches minimal and retain tests against upstream behavior. See `OPEN_SOURCE_REUSE.md`.
