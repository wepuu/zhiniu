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

Natural-language parsing, saved screen definitions, OR/NOT groups, historical public UI controls,
full-market backfill and automatic watchlist insertion are deferred. A future language parser may
only produce a candidate DSL document for validation and explicit user confirmation.
