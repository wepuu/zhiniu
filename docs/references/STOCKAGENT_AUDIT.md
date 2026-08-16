# StockAgent bounded audit

- Repository: https://github.com/qilihei/StockAgent
- Evaluated commit: `82fbd6619e92e79172756d7c689bb1ec5dc0f8b6`
- Branch/date: `main`, 2026-08-16
- Repository license: MIT

## Findings

`AsyncDataSourceAdapter` exposes capability-oriented asynchronous methods. The AKShare, BaoStock,
and Tushare adapters explicitly run synchronous SDK calls in an executor, which confirms the right
edge-adapter pattern. Storage code uses bulk upserts and indexes, and Redis participates in a much
larger node/RPC/cache runtime.

The base adapter returns empty values for unsupported functions and individual adapters catch many
exceptions internally. Provider-normalized dictionaries include derived/provider fields and use
floating-point values. Mongo, Redis, collector, and node lifecycle implementations are coupled to
StockAgent's distributed runtime and do not fit Zhaoniu's PostgreSQL modular monolith.

## Decision

Adopt only the architectural lesson that synchronous SDK work belongs in an executor and that
capabilities should be explicit. Zhaoniu uses a narrow typed port, SQLAlchemy repositories, typed
failures, deterministic idempotency keys, and queryable sync runs. Redis caching and distributed
node orchestration are deferred. No source file or function migrated.

## Phase 2 addendum — financial indicators

`AgentServer/core/managers/tushare_manager.py` exposes `daily_basic` and `fina_indicator`, requests
a compact field set, sorts provider rows, and batches stock calls. It treats provider-computed ROE,
ROIC, FCFF and quarter metrics as returned dictionaries and catches failures as empty lists.

Zhaoniu retained the capability-oriented async edge and batching lesson only. Provider indicators
are not accepted as first-party formulas: report facts, period conversion, input revisions and
formula versions remain explicit. Tushare was not registered without credentials and an approved
data-use decision. No source code or formula was copied.
