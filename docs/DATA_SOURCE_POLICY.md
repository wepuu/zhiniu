# Phase 2 data-source policy

AKShare is registered only as a development and technical-evaluation source. Its package license
does not establish permission to commercially display, cache, or redistribute the upstream market
data returned by individual endpoints.

Before any production or commercial use, legal/product owners must confirm the upstream source,
terms, attribution, display and redistribution rights, retention limits, service stability, and a
licensed replacement/fallback strategy. Until that review is recorded, all such fields are
`TBD / requires legal review`.

Phase 2 additionally evaluates AKShare's Sina financial-report endpoint and Baidu valuation
endpoint. These upstreams were selected only because their real schemas satisfy the technical
vertical slice: three statements include report date, announcement date, currency, audit state,
statement type and source update time; valuation exposes PE-TTM, PB, PCF and market cap history.
PS-TTM is not exposed and is returned as unavailable rather than fabricated.

Announcement precision is date-only, and the endpoint does not provide a complete historical
revision ledger. Zhaoniu therefore stores every payload/normalizer version it observes and applies
a conservative availability boundary, but does not claim backtest-grade point-in-time coverage.

Sync-run records retain provider identity, request window, counts, timing, status, and a redacted
exception class. Mock data may be used in isolated tests, but never as evidence of a successful
external-data acceptance run.

## Daily-bar upstream fallback

The Phase 23 staging adapter keeps AKShare `stock_zh_a_hist` (Eastmoney) as the primary source for
unadjusted Shanghai and Shenzhen daily bars. If its bounded retries end in a proxy, timeout,
connection, or rate-limit error, the same adapter may call AKShare `stock_zh_a_daily` (Sina) for the
same ticker and date range. It does not fall back on malformed payloads, canonical validation
failures, or Beijing Exchange symbols.

Sina rows retain `akshare_sina` as their canonical source. Sina volume is normalized as shares;
the Eastmoney path retains its existing lot-to-share conversion. Both paths pass the same Decimal,
OHLC, duplicate-date, nonnegative amount/volume, symbol, and deterministic ordering checks before
repository writes. A successful fallback is technical availability evidence only and does not
change AKShare's `development_evaluation` usage policy or grant commercial display rights.

## Phase 6 industry classification

Phase 6 introduces a development taxonomy named `akshare_dev_industry / phase6-dev-v1` by importing
the existing Phase 1 `stocks.industry_code` field into versioned industry tables when that field is
available. If the local development database has no industry field populated, the importer may add a
small `phase6_dev_seed` for explicit acceptance symbols such as `600519.SH` and `300750.SZ`. This
preserves source lineage and lets the peer benchmark engine run end-to-end, but it remains a
development and technical-validation source only.

Commercial display, redistribution, attribution and stability for this industry field are
`TBD / requires legal review`. A production taxonomy must be replaced by one confirmed official or
licensed source, with the exact source reference, version, ingestion date and reuse terms recorded.

## Corporate disclosures

AKShare is approved only as a Phase 7 development/evaluation adapter. Each stored record identifies
the actual upstream owner (CNInfo, Eastmoney or Sina). Commercial use, redistribution, attribution,
availability and stability remain `TBD / requires legal review`. Unmatched structured facts stay
staged and must not be exposed as source-backed public events.

## Phase 20 acceptance policy

Global `legal_review_status` and `data_use_status` flags do not grant a provider commercial or Beta
license. Provider acceptance evaluates `coverage_usage_scope` independently and fails closed.
AKShare evidence may pass technical retained-data checks under `development_evaluation`, but it
cannot make an invited-Beta baseline eligible until an approved source and usage scope are recorded.
