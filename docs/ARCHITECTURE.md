# Zhaoniu Architecture

Zhaoniu is a browser-based, multi-user A-share research SaaS. Phase 3 remains a modular monolith:
one Next.js web app, one FastAPI app, Celery workers, PostgreSQL/pgvector, and Redis. It optimizes
for traceable research, not trading or investment advice.

```text
Desktop / Mobile browser
        | versioned REST
        v
Next.js web -> FastAPI modular monolith -> PostgreSQL
                    |                       canonical truth
                    +-> Redis <-> Celery workers
                    +-> provider adapters -> external vendors
                    +-> future LLM gateway -> model providers
```

## Frontend

`apps/web` uses Next.js App Router, strict TypeScript, Tailwind, TanStack Query, ECharts and
Lightweight Charts. Desktop and mobile stock research pages are separately composed while sharing
API types, formatters, chart adapters and business components.

The visual system behaves like a research instrument: paper/mist surfaces, graphite text,
restrained research blue, serif headings, monospaced data labels, visible focus, touch-sized
navigation, and reduced-motion support. Every financial state distinguishes missing input,
insufficient history, not applicable, invalid input, and operational failure.

## Backend boundaries

Routes translate HTTP. Application services coordinate. Domain modules own formulas and period
rules. Repositories own persistence. Vendor SDK calls stay inside provider adapters.

```text
Provider DTO -> provider normalizer -> canonical model -> quality validator -> repository
```

The financial adapter wraps AKShare's synchronous SDK in bounded worker threads. Financial facts
are immutable versions. Deterministic metrics reference input report IDs and a formula version.
The LLM boundary is not involved in any financial calculation.

## Data layers

- Raw/provider DTOs exist only at the edge.
- Clean stock, bar, statement and valuation facts are typed and use Decimal.
- Derived metrics use version-controlled Python formulas.
- Fundamental metric points make historical formula outputs addressable and evidence-linkable.
- Research snapshots freeze a data version, metric version, rule-set version and structured result.
- Future AI research receives metrics and evidence; Markdown is presentation, not the contract.

PostgreSQL is the system of record. Redis is limited to task coordination, bounded caching, rate
limiting and locks; it is not durable business truth.

## Point-in-time semantics

Report period and publication availability are separate. A report revision stores provider,
payload checksum, normalizer version, publication precision, `known_at`, and first observation.
Date-only disclosures use a conservative next-China-day boundary. This prevents obvious future
leakage but is not represented as intraday/backtest-grade point-in-time data.

## Background jobs

Celery entry points call the same application services as CLI commands. Statement and valuation
syncs use deterministic idempotency keys, bounded retries, queryable sync runs and batched
PostgreSQL Upserts. Research snapshot jobs deduplicate by symbol, data version, metric version,
rule-set version and template version; stale build leases may be reclaimed after 30 minutes.
Celery Beat is intentionally deferred.

## Shared versus user data

Shared: stocks, bars, financial reports, valuation observations, deterministic metrics, events,
evidence and public research snapshots.

User-owned: users, sessions, watchlists/items, alerts, preferences, chats, subscriptions and usage.
Every user-owned record and query carries `user_id`. Watchlist persistence and real authentication
remain the next product phase.

## Module boundaries

- `market_data`: symbols, stock master, bars and market provider adapters.
- `fundamentals`: financial providers, versions, typed statements, formulas and research service.
- `indicators`: future technical/statistical calculations.
- `research`: historical metric series, deterministic change rules, evidence and snapshot service.
- `research_engine`: future expansion boundary for richer structured orchestration.
- `change_engine`: implemented inside `research` until an extracted package is justified.
- `event_engine`: future announcement/news canonicalization.
- `evidence_engine`: current typed evidence references; future disclosure-document retrieval.
- `llm`: provider-neutral structured generation and usage audit.

Reference repositories remain isolated under `references/` and never enter product packages. See
`OPEN_SOURCE_REUSE.md` for source, commit, license and reuse decisions.
