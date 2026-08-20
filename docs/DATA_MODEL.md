# Phase 9 Data Model

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
Stock 1--* FundamentalMetricPoint
Stock 1--* ResearchSnapshot 1--* ResearchObservation
ResearchObservation 1--* ResearchObservationInput
Stock 1--* ResearchBuildRun
ResearchSnapshot 1--* AIResearchRun 1--0..1 AIResearchOutput
AIResearchRun 1--* LLMCall
Stock 1--* IndustryMembership *--1 Industry
Industry 1--* PeerBenchmarkSnapshot 1--* PeerBenchmarkMetricResult
PeerBenchmarkMetricResult 1--* PeerBenchmarkInput
Stock 1--* CompanyPeerMetricPosition
```

Shared market and financial facts are stored once globally. User-owned identity, session and
watchlist records are persisted with explicit `user_id` ownership from Phase 5 onward.

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

## Implemented Phase 3 tables

- `fundamental_metric_points`: addressable historical formula outputs keyed by symbol, metric,
  period, basis, metric version and input fingerprint. It stores report/valuation reference IDs,
  not duplicated source facts.
- `research_snapshots`: immutable structured result plus data, metric, rules, template, schema and
  producer versions. Equivalent snapshots have one deterministic identity.
- `research_observations`: queryable card fields plus the exact immutable observation payload.
- `research_observation_inputs`: normalized links from an observation to metric points, report
  revisions or valuation observations. A check constraint requires exactly one referenced input.
- `research_build_runs`: idempotency key, versions, status, redacted error and output snapshot.

Research observations are global shared data. No `user_id` is added because no private user input
participates in their construction. Future personalized annotations must be separate user-owned
records and must include `user_id`.

## Implemented Phase 4 tables

- `ai_research_runs`: deterministic idempotency identity, snapshot/context/prompt/schema/route
  hashes, pending/running/succeeded/failed status, current attempt, redacted error category and a
  reclaimable lease. Failed work is retried on the same row only when explicitly requested.
- `ai_research_outputs`: one immutable, schema-valid stock-health document per successful run,
  the exact public evidence mapping, actual provider/model, all version hashes and generation
  timestamp. `current` versus `stale` is derived at read time against the latest snapshot.
- `llm_calls`: each model attempt's route position, provider/model, token counts, latency,
  estimated cost, finish reason and redacted error code. Prompt text, provider response, API keys
  and chain-of-thought are never persisted.

AI research remains shared global research because Phase 4 uses no private user input. A future
user-specific AI feature must use separate user-owned records and enforce `user_id` on every query.

## Implemented Phase 5 tables

- `users`: email/password accounts for the internal beta. Password hashes use Argon2 through the
  authentication service; raw passwords are never stored.
- `user_sessions`: opaque HttpOnly cookie sessions stored as SHA-256 token hashes, with expiry,
  revocation, last-used time and bounded user-agent/IP metadata.
- `watchlists`: user-owned groups with a single default group per user and unique names per user.
- `watchlist_items`: symbol memberships keyed by watchlist and canonical stock symbol. Items do not
  duplicate shared market data and do not carry a redundant `user_id`; ownership is enforced through
  the parent watchlist.

Phase 5 entitlements are deterministic internal-beta limits only: five watchlist groups and thirty
total watchlist memberships per user. Paid plans, account deletion, email verification and password
reset are deferred.

Phase 8 adds a SHA-256 CSRF token hash to `user_sessions`. The readable CSRF cookie carries a
different opaque token from the HttpOnly session cookie; write requests must present the same CSRF
value in `X-CSRF-Token` and pass Origin validation.

## Implemented Phase 6 tables

- `industry_taxonomies`, `industries`, `industry_memberships`: versioned industry classification
  with source lineage and `known_at` support.
- `peer_benchmark_runs`: queryable idempotent build status.
- `peer_benchmark_snapshots`: immutable industry-level benchmark identity.
- `peer_benchmark_metric_results`: median, quartiles, status and invalid-value metadata by metric.
- `peer_benchmark_inputs`: references to the exact metric points or valuation observations used.
- `company_peer_metric_positions`: target-company values, numeric percentile and numeric rank.
- `peer_position_observations`: deterministic, neutral descriptions of significant percentile-band
  positions or changes. These are upstream research artifacts, not frontend calculations.

Peer research is global shared research and does not carry `user_id`.

## Phase 7 disclosure and event tables

- `disclosure_documents` retains source identity, URL and publication/knowledge/ingestion times.
- `disclosure_classifications` stores versioned deterministic classification outcomes.
- `corporate_event_source_facts` stages structured facts until evidence matching succeeds.
- `corporate_events` stores immutable typed event versions and thread lineage.
- `corporate_event_inputs` links each published event to its disclosure and optional source fact.
- `corporate_event_build_runs` records idempotent sync/build outcomes.
- `event_radar_snapshots` and `event_radar_snapshot_items` preserve point-in-time selection and
  versioned attention decisions.

## Phase 8 feed and alert tables

- `research_signals`: global immutable projection with exactly one upstream source FK, `known_at`,
  optional date-only `effective_on`, semantic dedup fingerprint and presentation payload.
- `research_signal_projection_runs`: idempotent source-artifact/projection-version audit.
- `user_research_alert_settings`: user-owned threshold and per-source switches.
- `user_research_alert_deliveries`: user/signal unique in-app deliveries and read time.
- `research_alert_dispatch_runs`: signal/matcher-version deduplication, lease and delivery counts.

There is intentionally no `user_feed_items` table. The feed joins global signals to current
watchlist membership at query time; only alert settings and deliveries are user-owned.

## Phase 9 screening tables

- `screening_snapshots`: immutable cutoff, producer-version and idempotency envelope for one
  eligible market universe.
- `screening_snapshot_members`: canonical stock membership plus deterministic eligibility and
  exclusion reason.
- `screening_snapshot_facts`: one typed upstream reference for an available metric, valuation,
  peer position, industry membership or event-radar fact.
- `screen_executions`: user-owned canonical query, query hash, lease, status and aggregate counts.
- `screen_results`: user-owned execution result ordering, matched-condition manifest and evidence
  reference manifest. Source numerical values remain in their canonical upstream tables.

Screen definitions are not persisted in Phase 9. The immutable execution stores the submitted
canonical query. Saved and shared screens are a later user-workspace capability.
