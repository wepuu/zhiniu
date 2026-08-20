# Deterministic Research Screening Engine

Phase 9 adds active company discovery without introducing stock recommendations. The engine answers
one narrow question: which eligible companies match every validated fact condition in a fixed,
point-in-time research snapshot?

## Boundary and flow

```text
ScreenQuery -> allow-list validator -> immutable screening snapshot -> deterministic evaluator
            -> user-owned execution -> explainable result rows
```

The screening module never calls a vendor SDK or an LLM. It does not build SQL from user strings,
calculate financial metrics, assign a composite score, predict returns, or infer missing facts.
Numerical inputs reference existing metric points, valuations and peer positions. Industry and event
conditions reference their retained Phase 6/7 artifacts.

## Snapshot construction

`screening_snapshots` freeze a knowledge cutoff and all producer versions. Members contain the
eligible A-share universe and a deterministic exclusion reason. Facts store one typed upstream
reference, not a copied value. Source rows with `known_at` after the cutoff cannot enter the
snapshot. Event absence is evaluable only when the corresponding radar is healthy and complete;
unknown coverage never passes a negative condition.

Snapshots are global immutable research data. Executions and results are user-owned and every read
is scoped by `user_id`. Equivalent work is deduplicated by user, snapshot, canonical query hash and
engine version. A 30-minute lease permits safe recovery of abandoned jobs.

## Execution and evidence

The first version supports AND conjunctions with at most eight conditions. Unknown input fails the
match but is counted separately. Every retained result includes the matched condition label, exact
value/unit/date and upstream evidence identity. Default ordering is canonical symbol; supported
metric sorting is deterministic and never presented as investment quality.

CLI and Celery call the same application service:

```text
uv run python -m zhaoniu_api.cli build-screening-snapshot
uv run python -m zhaoniu_api.cli validate-screen --query-file screen.json
uv run python -m zhaoniu_api.cli execute-screen --query-file screen.json --user-email user@example.com
```

## Phase 10 language and workspace layer

Phase 10 adds a deliberately thin layer above the deterministic engine:

```text
private text -> policy gate -> structured parser -> grounding validator
             -> candidate ScreenQuery -> explicit user confirmation -> Phase 9 engine
```

The parser never executes a query, selects companies, calculates metrics, or bypasses the catalog.
Raw text is held in Redis for at most ten minutes while the background task runs and is not stored
in PostgreSQL, LLM audit rows, or saved-screen records. Only the input HMAC, bounded source spans,
validated structured candidate and version hashes are retained. A confirmed candidate must match
the submitted canonical query hash before it can be executed.

Saved screens are user-owned, limited to ten per internal-beta account, and retain a canonical DSL
document plus catalog/criteria-contract provenance. Compatibility is computed on read as
`compatible`, `catalog_changed`, or `invalid`; reruns always use the latest immutable screening
snapshot. OR/NOT groups, shared templates, historical public UI controls, full-market backfill and
automatic watchlist insertion remain deferred.
