# Phase 2 Data Model

## Entity relationships

```text
Stock 1--* StockDailyBar
Stock 1--* FinancialReportRevision
FinancialReportRevision 1--0..1 IncomeStatementFact
FinancialReportRevision 1--0..1 BalanceSheetFact
FinancialReportRevision 1--0..1 CashFlowStatementFact
Stock 1--* FundamentalSnapshot 1--* FundamentalMetricValue
Stock 1--* ValuationObservation
Stock 1--* DataSyncRun
```

Shared market and financial facts are stored once globally. User-owned Watchlist records remain
behind the Phase 0 in-memory seam until the multi-user phase.

## Financial report identity

`financial_report_revisions` is append-only. A canonical version is identified by symbol,
provider, period, statement scope, normalizer version, and source-payload checksum. A later source
payload or normalizer creates another version; it does not overwrite historical facts.

`published_at` retains the source disclosure value and its precision. AKShare/Sina exposes a date,
so `known_at` is conservatively set to the following China-calendar day unless a later source
update is known. This is disclosure-aware, not intraday or backtest-grade point-in-time data.

Income and cash-flow facts are cumulative for Q1/H1/Q3/FY. Only deterministic metric code derives
standalone quarters. Balance-sheet facts are always point-in-time and are never differenced.

## Implemented Phase 2 tables

- `financial_report_revisions`: period, scope, publication/availability, provider revision,
  payload checksum, normalizer version, audit state, issuer type, and quality warnings.
- `income_statement_facts`, `balance_sheet_facts`, `cash_flow_statement_facts`: typed Decimal core
  facts linked one-to-one to a report revision. Derived values are not stored here.
- `fundamental_snapshots`: immutable data/formula-version envelope for deterministic research.
- `fundamental_metric_values`: value, status, unit, period basis, input revision IDs, and detail.
- `valuation_observations`: provider values keyed by symbol/date/metric/provider. Baidu market cap
  is normalized from 亿元 to CNY; PE/PB/PCF remain multiples.
- `data_sync_runs`: idempotency and redacted failure record for statements and valuation jobs.

The Phase 1 stock and daily-bar tables remain unchanged except for `stocks.issuer_type`. Bank
classification is derived from material bank-specific balance-sheet facts, not ticker allowlists.
