# Research Snapshot Contract

A Phase 3 snapshot is an immutable, point-in-time research document produced by deterministic
code. Its identity is derived from:

```text
symbol + data_version + metric_version + rule_set_version + template_version + producer_version
```

The input manifest records report revision IDs/checksums, metric point IDs/fingerprints and the
valuation cutoff. `knowledge_cutoff` answers “what could the system know at this time”; report
period and publication time remain separate.

## Build and read path

```text
FinancialReport / ValuationObservation
  -> deterministic historical MetricPoint
  -> versioned Change Rule
  -> ResearchObservation + evidence references
  -> immutable ResearchSnapshot
  -> versioned REST API
```

CLI and Celery call the same application service. Equivalent builds are deduplicated through a
queryable `research_build_runs` lease. Failed runs may retry, and running leases older than 30
minutes may be reclaimed. HTTP read routes do not start builds.

The stock page uses `GET /research/snapshot` for the first-view cards and
`GET /research/observations/{id}` for the evidence detail. A stock with a built snapshot and zero
observations returns an honest empty state; `not_built` is distinct from an operational error.

Evidence links point to canonical metric points, report revisions and valuation observations.
Provider records are not described as official disclosure PDFs unless a future licensed document
pipeline has actually ingested and verified them.
