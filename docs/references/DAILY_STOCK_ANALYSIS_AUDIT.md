# daily_stock_analysis bounded audit

- Repository: https://github.com/ZhuLinsen/daily_stock_analysis
- Evaluated commit: `5c964bf23bade6571d09a085fc42199882b77f8f`
- Branch/date: `main`, 2026-08-16
- Repository license: MIT

## Findings

The project keeps provider-specific fetchers behind a manager and records provider attempts. Its
AKShare implementation documents useful endpoint and Chinese-column mappings, while its symbol
utilities cover more markets than Phase 1 needs.

The implementation is not copied because its internal A-share identity is usually a bare ticker,
provider errors are broadly collapsed, and `BaseFetcher.get_daily_data` combines raw retrieval,
cleaning, fallback, and technical-indicator calculation. It also relies heavily on pandas floats.
Those choices conflict with Zhaoniu's canonical `ticker.exchange` identity, typed error taxonomy,
Decimal clean-data model, batch rejection, and separate derived-metrics layer.

## Decision

Rewrite a small A-share resolver, typed provider/fallback contracts, and AKShare adapter. Keep the
AKShare SDK call synchronous at the edge and expose a non-blocking application port through a
bounded thread. Normalize into Decimal canonical records, reject a bad batch before persistence,
and compute `pct_change` in deterministic first-party code. No source file or function migrated.

## Phase 2 addendum — fundamentals

`data_provider/fundamental_adapter.py` probes several AKShare indicator endpoints, extracts the
latest matching row with keyword heuristics, converts values to float, and returns a partial
fail-open bundle. The source-chain and capability-probing ideas are useful for product status, but
the adapter does not retain three-statement revisions, announcement availability, accounting
scope, Decimal facts, or formula input lineage.

Zhaoniu therefore did not migrate the adapter. Phase 2 uses an immutable filing envelope, typed
statement tables, field-specific validation, Decimal calculations, explicit unavailable states,
and versioned metric outputs. The reference's partial bundle is not a canonical accounting model.
