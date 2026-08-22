# Zhaoniu Architecture

Zhaoniu is a browser-based, multi-user A-share research SaaS. Phase 16 remains a modular monolith:
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
                    +-> LiteLLM SDK gateway -> configured model providers
                    +-> disclosure/event engine -> point-in-time radar snapshots
```

## Frontend

Browser requests use the same-origin `/gateway/api/v1/*` development proxy, which maps to the
unchanged public `/api/v1/*` REST contract. This avoids embedded-browser localhost security
blocks while preserving cookie, CSRF, and frontend/database boundaries.

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
- AI research receives one immutable research snapshot, emits a versioned Pydantic document and
  persists its evidence map. It cannot query provider payloads or user records.

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

AI jobs use the same application service from CLI and Celery. An atomic idempotency key covers the
snapshot, canonical context, prompt, schema and ordered model route. Each configured model is
attempted at most once, calls have bounded timeouts, and only a fully schema/citation/safety-valid
result is persisted. An expired 30-minute lease may be reclaimed; a failed run requires explicit
retry. API routes remain read-only and cannot trigger generation.

Peer benchmark jobs use the Phase 6 application service. They resolve the deterministic industry
universe first, then select already materialized metric points or valuation observations, calculate
median/quartile/percentile/rank, and persist immutable benchmark snapshots. GET routes read stored
results only; the frontend never calculates peer statistics.

## Shared versus user data

Shared: stocks, bars, financial reports, valuation observations, deterministic metrics, events,
evidence, public research snapshots, industry classifications and peer benchmark research.

User-owned: users, sessions, watchlists/items, alerts, preferences, chats, access grants and usage.
Every user-owned record and query carries `user_id`. Phase 8 implements alert preferences and
deliveries while keeping research signals global. Phase 11 adds invitation registration and
operator-issued activation without an in-product commerce flow. Phase 12 adds verified account
recovery, versioned legal acceptance and production-operability boundaries. Chats, automated
data-rights workflows and public launch remain deferred.

## Production runtime

The production Compose topology places Caddy in front of separately built web and API containers,
runs Alembic as a one-shot dependency, and keeps PostgreSQL and Redis private to the network. `/livez`
proves the process is responsive; `/readyz` independently reports PostgreSQL, migration-head and
Redis state. PostgreSQL or schema mismatch blocks readiness. Redis degradation is visible but does
not misrepresent the durable database as unavailable.

## Module boundaries

- `market_data`: symbols, stock master, bars and market provider adapters.
- `fundamentals`: financial providers, versions, typed statements, formulas and research service.
- `indicators`: future technical/statistical calculations.
- `research`: historical metric series, deterministic change rules, evidence and snapshot service.
- `research_engine`: future expansion boundary for richer structured orchestration.
- `change_engine`: implemented inside `research` until an extracted package is justified.
- `corporate_events`: disclosure ingestion, deterministic taxonomy, typed immutable event versions,
  evidence links and point-in-time radar snapshots.
- `event_engine`: reserved extraction boundary; implementation stays in `corporate_events` until
  measured reuse or scale justifies a package.
- `evidence_engine`: typed research evidence references and retained disclosure-document links.
- `ai_research`: snapshot-only context, prompt, validation, orchestration, immutable outputs and
  API read model.
- `peer_research`: industry taxonomy, peer universe resolution, benchmark statistics, peer evidence
  and read-only API models.
- `research_feed`: deterministic global signal projection, watchlist-scoped feed queries, coverage,
  in-app alert matching and user-owned delivery state.
- `screening`: versioned query validation, immutable market-wide screening snapshots,
  deterministic evidence-linked execution, natural-language candidate parsing and user-scoped
  saved-screen/result retrieval.
- `access_control`: invitation and activation code lifecycle, immutable plan versions, effective
  feature resolution, access limits and production activation gates.
- `operations_console`: role capabilities, step-up authorization, bounded operational actions,
  provider diagnostics and immutable audit; it coordinates existing services rather than bypassing
  their domain boundaries.
- `llm`: provider-neutral structured generation and per-attempt usage audit through LiteLLM SDK.

## Personalized research projection

Phase 8 projects immutable Phase 3 observations, Phase 6 peer-position observations and retained
Phase 7 corporate events into a single global `research_signals` stream. Exactly one source
reference is required for every signal. Personalization happens at read and delivery time through
watchlist membership; no per-user feed copies are stored. Feed cursors freeze a `query_cutoff` and
sort by known time, attention and signal identity so pagination remains stable while new signals
arrive. AI output is read-only enrichment and never triggers generation from a feed request.

Alert dispatch is keyed by signal identity and matcher version. Membership must predate the
signal's `known_at`; therefore historical projection is visible in the feed but never backfilled as
an alert. Cookie-authenticated writes require a same-session CSRF token and an allowed Origin.

## Research screening

Phase 9 creates a global immutable screening snapshot from retained Phase 2, 6 and 7 facts at one
knowledge cutoff. It stores typed source references rather than copied financial values. A closed
DSL is validated against server-owned catalogs before a Celery execution evaluates the snapshot.
Executions and results carry `user_id`; equivalent execution work is deduplicated. Missing or
incomplete coverage cannot satisfy a condition, especially a negative event condition. The web
client renders matched conditions and evidence links but performs no screening calculation.

Phase 10 keeps natural-language parsing outside the deterministic evaluator. Private text is
transported through a short-lived Redis key to a Celery task, then discarded. The LLM gateway may
only return a candidate `ScreenQuery`; policy, schema, source-span, numeric/unit, catalog and query
hash checks are deterministic. Saved screens persist only validated canonical DSL and provenance.
Catalog and coverage reads remain public-cacheable; parse, saved-screen and execution routes use
`private, no-store` responses and are always scoped by `user_id`.

Reference repositories remain isolated under `references/` and never enter product packages. See
`OPEN_SOURCE_REUSE.md` for source, commit, license and reuse decisions.

## Corporate disclosure and event radar

Corporate events are an API application module, not a frontend calculation. External data crosses
the Provider -> Normalizer -> Canonical Model -> Repository boundary. Disclosures, staged source
facts, immutable event versions and point-in-time radar snapshots remain separate persistence
layers. Radar attention is deterministic and versioned; the frontend only renders API results.
Phase 13 adds a coverage application module that reads retained global artifacts, writes immutable
priority-universe and coverage snapshots, and coordinates only explicitly planned bounded backfill.
It calls existing application services rather than vendor SDKs. The frontend reads the versioned
coverage API and never computes coverage, freshness, source health, or learning aggregates.

## Company research timeline

Phase 16 adds a query-only `company_timeline` application module over global `research_signals`.
It does not recalculate metrics, classify disclosures, mutate source artifacts, or create a worker.
Known-time ordering and upcoming effective-time ordering remain separate. Event Thread hydration
reads immutable event versions in ascending known-time order.
